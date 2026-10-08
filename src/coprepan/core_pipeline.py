"""The first core section of the pipeline, wired together (decision CPD-0005):

```text
recorded exchanges → acquisition run + fetch records → open pack → sealed pack
    → promotion to the preservation root → document identity → extraction → document version
```

Every step is separately ledgered or content-addressed and can be repeated: a step that already
happened is recognised and skipped, never redone differently. Nothing here touches the network.
Acquisition is the *replay of recorded exchanges*; a live fetcher does not exist.

Stage order and gates enforced in code:

* only a **registered** outlet is acquired for (``Registry.resolve``);
* a fetch is ``FETCHED`` only after its bytes are in the pack and on disk;
* identity and extraction read **only** fetches whose ledger state is ``RAW_PRESERVED``, and read
  them from the preservation root, never from the workspace copy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import __version__, acquisition, extraction, layer_store, pack, preservation
from .acquisition import AcquisitionRun, RecordedExchange
from .canonical import sha256_bytes
from .document_identity import IdentityTables
from .exclusive import writes_workspace
from .identity import OffOriginError
from .ledger import PRESERVATION, Ledger
from .registry import Registry

AREA_PACKS = "raw"
AREA_INDEXES = "raw_index"

COMPONENT_VERSIONS = {
    "fetch_record": acquisition.FETCH_RECORD_SCHEMA,
    "pack_writer": pack.PACK_WRITER_VERSION,
    "preservation_policy": preservation.POLICY_VERSION,
}


class NotPreserved(RuntimeError):
    """A derived stage was asked to read a fetch that is not ``RAW_PRESERVED``."""


@dataclass(frozen=True)
class Workspace:
    """The layout of the runtime workspace. The root itself is resolved by the caller."""

    root: Path

    @property
    def packs(self) -> Path:
        return self.root / "packs"

    @property
    def ledger_path(self) -> Path:
        return self.root / "ledgers" / "preservation.jsonl"

    @property
    def identity(self) -> Path:
        return self.root / "identity"

    @property
    def layers(self) -> Path:
        return self.root / "layers"

    def ledger(self) -> Ledger:
        return Ledger(self.ledger_path, PRESERVATION)

    def layer_store(self) -> layer_store.LayerStore:
        self.layers.mkdir(parents=True, exist_ok=True)
        return layer_store.LayerStore(self.layers)


def recorded_replay_run(started_at: datetime, outlet_ids: Sequence[str], configuration: Mapping[str, Any]) -> AcquisitionRun:
    """The run identity of a replay of recorded exchanges under the current software."""
    return AcquisitionRun(
        kind=acquisition.RUN_KIND_RECORDED_REPLAY,
        started_at=started_at,
        outlet_ids=tuple(sorted(set(outlet_ids))),
        discovery_method="recorded_exchanges",
        software_version=__version__,
        component_versions=COMPONENT_VERSIONS,
        configuration=configuration,
    )


# --- acquisition ----------------------------------------------------------------------------------


@writes_workspace("acquire recorded exchanges")
def acquire_recorded(
    workspace: Workspace,
    registry: Registry,
    run: AcquisitionRun,
    outlet_id: str,
    exchanges: Iterable[RecordedExchange],
) -> dict[str, Any]:
    """Turn recorded exchanges into fetch records in open packs. Resumable: calling it again with
    the same run and exchanges completes what an interrupted call left undone and repeats nothing.
    """
    registry.resolve(outlet_id)
    acquisition.open_run(workspace.root, run)
    ledger = workspace.ledger()
    packs: dict[str, pack.OpenPack] = {}
    counts = {"fetched": 0, "fetch_failed": 0, "already_recorded": 0}
    for exchange in exchanges:
        _, status = record_exchange(workspace, ledger, packs, run, outlet_id, exchange)
        counts[status] += 1
    return {"run_id": run.run_id, "open_pack_ids": sorted(packs), "counts": counts}


def record_exchange(
    workspace: Workspace,
    ledger: Ledger,
    packs: dict[str, pack.OpenPack],
    run: AcquisitionRun,
    outlet_id: str,
    exchange: RecordedExchange,
) -> tuple[dict[str, Any], str]:
    """Put one exchange on record: fetch record, ledger, open pack — in that order of commitment.

    The ledger says ``FETCH_PLANNED`` before the bytes are written and ``FETCHED`` only after they
    are on disk. An exchange that is already recorded is recognised and not written twice.
    Returns the fetch record and ``fetched`` / ``fetch_failed`` / ``already_recorded``.
    """
    record = acquisition.build_fetch_record(run, outlet_id, exchange)
    fetch_id = record["fetch_id"]
    identifier = pack.pack_id(outlet_id, pack.utc_day_of(record["fetch_started_at"]))
    target = record["outcome"]
    state = ledger.state(fetch_id)
    if state not in (None, "DISCOVERED", "FETCH_PLANNED"):
        return record, "already_recorded"
    if identifier not in packs:
        packs[identifier] = pack.OpenPack(workspace.packs, identifier, opened_at=run.started_at)
    if state is None:
        ledger.transition(fetch_id, "DISCOVERED", at=exchange.fetch_started_at,
                          details={"run_id": run.run_id, "channel_id": record["discovery"]["channel_id"]})
    if state in (None, "DISCOVERED"):
        ledger.transition(fetch_id, "FETCH_PLANNED", at=exchange.fetch_started_at, details={"run_id": run.run_id})
    if fetch_id not in packs[identifier]:
        packs[identifier].append(record, exchange.body)
    ledger.transition(fetch_id, target, at=exchange.fetch_finished_at,
                      details={"pack_id": identifier, "failure_reason": record["failure_reason"]})
    return record, "fetched" if target == acquisition.OUTCOME_FETCHED else "fetch_failed"


# --- preservation ---------------------------------------------------------------------------------


def reconcile_ledger_with_pack(ledger: Ledger, identifier: str, entries: Sequence[pack.PackEntry], *, at: datetime) -> list[str]:
    """Complete the ledger from the evidence of a verified pack.

    A fetch is written to the pack *before* its ``FETCHED`` / ``FETCH_FAILED`` transition. A
    process that dies in between leaves the fetch in the pack — whole, verified by the scan that
    produced ``entries`` — and the ledger at ``FETCH_PLANNED``. The pack is the evidence that the
    fetch ended and how; the missing transition is recorded here, marked as reconciled. Nothing
    else is ever reconciled: a state the pack does not prove is not written.
    """
    reconciled = []
    for entry in entries:
        if ledger.state(entry.fetch_id) == "FETCH_PLANNED":
            ledger.transition(entry.fetch_id, entry.outcome, at=at,
                              details={"pack_id": identifier, "reconciled_from_pack": True})
            reconciled.append(entry.fetch_id)
    return reconciled


def pack_relative_path(identifier: str, suffix: str) -> str:
    outlet = pack.pack_outlet(identifier)
    return f"{outlet[:2]}/{outlet}/{identifier}{suffix}"


@writes_workspace("seal and preserve a pack")
def seal_and_preserve(
    workspace: Workspace, identifier: str, *, preservation_root: Path, now: datetime
) -> preservation.PromotionResult:
    """Seal a pack, promote it and its index, and only then mark its fetches ``RAW_PRESERVED``.

    Repeatable at every point: sealing, promotion and each ledger transition recognise their own
    completed state.
    """
    manifest = pack.seal(workspace.packs, identifier, sealed_at=now)
    ledger = workspace.ledger()
    index = pack.read_index(workspace.packs, identifier)
    reconcile_ledger_with_pack(ledger, identifier, index, at=now)
    entries = [entry for entry in index if entry.body_sha256 is not None]
    for entry in entries:
        if ledger.state(entry.fetch_id) == "FETCHED":
            ledger.transition(entry.fetch_id, "RAW_VERIFIED", at=now,
                              details={"pack_id": identifier, "pack_sha256": manifest["pack_sha256"]})
    for entry in entries:
        if ledger.state(entry.fetch_id) == "RAW_VERIFIED":
            ledger.transition(entry.fetch_id, "PRESERVATION_PENDING", at=now, details={"pack_id": identifier})

    result = preservation.promote(
        workspace.packs / f"{identifier}.warc.gz", root=preservation_root, area=AREA_PACKS, object_id=identifier,
        relative_path=pack_relative_path(identifier, ".warc.gz"), declared_sha256=manifest["pack_sha256"],
        details={"pack": manifest}, now=now,
    )
    preservation.promote(
        workspace.packs / f"{identifier}.index.jsonl", root=preservation_root, area=AREA_INDEXES,
        object_id=identifier, relative_path=pack_relative_path(identifier, ".index.jsonl"),
        declared_sha256=manifest["index_sha256"], details={"pack_id": identifier}, now=now,
    )
    # RAW_PRESERVED is a claim about bytes on the preservation root: both masters are re-read
    # and hashed before any fetch is given that state.
    for area in (AREA_PACKS, AREA_INDEXES):
        if not preservation.verify_master(preservation_root, area, identifier):
            raise preservation.PreservationError(f"{identifier}: promoted {area} master does not verify")
    for entry in entries:
        if ledger.state(entry.fetch_id) == "PRESERVATION_PENDING":
            ledger.transition(entry.fetch_id, "RAW_PRESERVED", at=now,
                              details={"pack_id": identifier, "master": result.relative_path})
    return result


@dataclass(frozen=True)
class PreservedPack:
    """A pack read from the preservation root, verified before anything is taken from it."""

    pack_id: str
    path: Path
    manifest: Mapping[str, Any]
    entries: Mapping[str, pack.PackEntry]

    def fetch_record(self, fetch_id: str) -> dict[str, Any]:
        return pack.read_fetch_record(self.path, self.entries[fetch_id])

    def body(self, fetch_id: str) -> bytes:
        return pack.read_body(self.path, self.entries[fetch_id])


def open_preserved_pack(preservation_root: Path, identifier: str) -> PreservedPack:
    """Open a preserved pack: master and index must verify against their manifests, and the index
    must be the one the pack manifest names.
    """
    held = preservation.read_manifest(preservation_root, AREA_PACKS, identifier)
    index = preservation.read_manifest(preservation_root, AREA_INDEXES, identifier)
    if held is None or index is None:
        raise NotPreserved(f"{identifier} is not on the preservation root")
    for area in (AREA_PACKS, AREA_INDEXES):
        if not preservation.verify_master(preservation_root, area, identifier):
            raise preservation.PreservationError(f"{identifier}: preserved {area} master does not verify")
    manifest = held["details"]["pack"]
    if index["sha256"] != manifest["index_sha256"] or held["sha256"] != manifest["pack_sha256"]:
        raise preservation.PreservationError(f"{identifier}: preserved index and pack do not belong together")
    entries = {}
    for line in (preservation_root / index["relative_path"]).read_bytes().split(b"\n")[:-1]:
        row = json.loads(line.decode("utf-8"))
        row.pop("schema"), row.pop("pack_id")
        entries[row["fetch_id"]] = pack.PackEntry(**row)
    return PreservedPack(identifier, preservation_root / held["relative_path"], manifest, entries)


# --- identity and extraction ----------------------------------------------------------------------


@writes_workspace("identity and extraction")
def identify_and_extract(
    workspace: Workspace,
    registry: Registry,
    *,
    preservation_root: Path,
    identifier: str,
    extractor: extraction.Extractor = extraction.BASELINE,
    now: datetime | None = None,
    identity_directory: Path | None = None,
    read_only_layers: bool = False,
    skip_unpreserved: bool = False,
) -> list[dict[str, Any]]:
    """Assign documents and versions for every fetched entry of a preserved pack.

    Reads bodies from the preservation root only, and only for fetches the ledger records as
    ``RAW_PRESERVED``. Idempotent: a second call finds every extraction in the layer store and
    every assignment in the identity tables.

    ``identity_directory`` / ``read_only_layers``: the rebuild of the identity tables from preserved
    evidence (CPD-0010) writes them to another, new directory and **writes no layer**: a stored
    extraction that verifies is used, any other is derived in memory and not stored.
    ``skip_unpreserved``: a fetch the ledger does not (yet) record as ``RAW_PRESERVED`` is left out
    instead of refused — the rebuild covers what is preserved and says nothing about the rest.
    """
    preserved = open_preserved_pack(preservation_root, identifier)
    ledger, tables = workspace.ledger(), IdentityTables(identity_directory or workspace.identity)
    store = (workspace.layer_store() if workspace.layers.is_dir() else None) if read_only_layers else workspace.layer_store()
    rules = registry.url_rules(pack.pack_outlet(identifier))
    results = []
    for fetch_id, entry in preserved.entries.items():
        if entry.body_sha256 is None:
            continue
        if ledger.state(fetch_id) != "RAW_PRESERVED":
            if skip_unpreserved:
                continue
            raise NotPreserved(f"{fetch_id} is {ledger.state(fetch_id)}, not RAW_PRESERVED")
        record = preserved.fetch_record(fetch_id)
        if record["fetch_kind"] != acquisition.FETCH_KIND_ITEM:
            continue  # a channel document or a robots file is evidence, never a document
        body = preserved.body(fetch_id)
        result: dict[str, Any] = {"fetch_id": fetch_id, "body_sha256": entry.body_sha256, "pack_id": identifier}
        if record.get("revalidates", "not_applicable") != "not_applicable":
            # A 304: the server confirmed an earlier body. No body here, so no key of its own and
            # no extraction: one more observation of the revalidated fetch's document and version.
            # A 304 is the server's statement about a body. It is believed only for a body this
            # corpus actually holds: the revalidated fetch must be preserved, with that very hash.
            target = record["revalidates"]
            if ledger.state(target["fetch_id"]) != "RAW_PRESERVED" or not _holds_body(ledger, preservation_root, target):
                results.append({**result, "identity": "revalidation_target_not_preserved", "document_id": None,
                                "document_version_id": None})
                continue
            assigned = tables.assign_revalidation(record)
            if assigned is None:
                results.append({**result, "identity": "revalidation_target_unknown", "document_id": None,
                                "document_version_id": None})
            else:
                results.append({**result, "identity": "assigned", "document_id": assigned[0], "is_new_document": False,
                                "url_key": tables.observations[fetch_id]["url_key"], "url_key_basis": "revalidation",
                                "extraction_outcome": "NOT_APPLICABLE", "extraction_fingerprint": None,
                                "extraction_artifact_id": None, "extraction_status": "NOT_APPLICABLE",
                                "document_version_id": assigned[1][-1] if assigned[1] else None,
                                "is_new_version": False, "duplicate_of": None})
            continue
        try:
            assignment = tables.assign_document(rules, record, body)
        except OffOriginError:
            results.append({**result, "identity": "off_origin", "document_id": None, "document_version_id": None})
            continue
        extracted, fingerprint, stored = _extract_stored(store, extractor, record, body, now, read_only=read_only_layers)
        result.update(
            identity="assigned", document_id=assignment.document_id, is_new_document=assignment.is_new_document,
            url_key=assignment.url_key, url_key_basis=assignment.url_key_basis,
            extraction_outcome=extracted.outcome, extraction_fingerprint=fingerprint,
            extraction_artifact_id=stored.artifact_id, extraction_status=stored.status,
            document_version_id=None, is_new_version=False, duplicate_of=None,
        )
        if extracted.outcome == extraction.OUTCOME_EXTRACTED:
            version = tables.assign_version(
                assignment.document_id, fetch_id,
                extracted_text_sha256=extracted.extracted_text_sha256, body_text_sha256=extracted.body_text_sha256,
                extractor=extractor.name, extractor_version=extractor.version, extraction_fingerprint=fingerprint,
                has_body_text=bool(extracted.body_text),
            )
            result.update(document_version_id=version.document_version_id, is_new_version=version.is_new_version,
                          duplicate_of=version.duplicate_of)
        results.append(result)
    return results


def _holds_body(ledger: Ledger, preservation_root: Path, target: Mapping[str, Any]) -> bool:
    """Whether the preservation root holds the fetch a 304 names, with the body hash it names."""
    held = next((record.details.get("pack_id") for record in ledger.records()
                 if record.subject == target["fetch_id"] and record.new_state == "RAW_PRESERVED"), None)
    if held is None:
        return False
    try:
        entry = open_preserved_pack(preservation_root, held).entries.get(target["fetch_id"])
    except (NotPreserved, preservation.PreservationError, pack.PackError):
        return False
    return entry is not None and entry.body_sha256 == target["body_sha256"]


def _extraction_arguments(record: Mapping[str, Any]) -> dict[str, str]:
    return {
        "content_type": record["response"]["content_type"],
        "declared_charset": extraction.declared_charset_of(record["response"]["headers"]),
        "content_encoding": record["response"]["content_encoding"],
    }


def extraction_fingerprint(extractor: extraction.Extractor, record: Mapping[str, Any]) -> str:
    inputs, parameters = extraction.fingerprint_inputs(record["body_sha256"], **_extraction_arguments(record))
    return layer_store.fingerprint(extraction.STAGE, extractor.stage_version, inputs, parameters)


class _Derived:
    """An extraction derived in memory and stored nowhere (the read-only rebuild)."""

    status = "DERIVED_NOT_STORED"

    def __init__(self, artifact_id: str) -> None:
        self.artifact_id = artifact_id


def _extract_stored(store, extractor, record, body, now, *, read_only=False):
    fingerprint = extraction_fingerprint(extractor, record)
    if read_only:
        # A layer is derived state. The rebuild uses a stored answer that verifies; a missing or
        # unverifiable one is derived again from the preserved bytes — and stored nowhere.
        try:
            held = store.get(extraction.STAGE, fingerprint) if store is not None else None
            if held is not None:
                store.read(extraction.STAGE, fingerprint)
        except layer_store.LayerStoreError:
            held = None
        if held is None:
            extracted = extractor.run(body, body_sha256=record["body_sha256"], **_extraction_arguments(record))
            return extracted, fingerprint, _Derived(layer_store.artifact_id(fingerprint, sha256_bytes(extracted.payload)))
    else:
        held = store.get(extraction.STAGE, fingerprint)
    if held is not None:
        stored_record = json.loads(store.read(extraction.STAGE, fingerprint).decode("utf-8"))
        # The fingerprint names the extractor version, not the record's schema. A stored answer
        # is used only as what it says it is: this schema, this extractor, this body.
        if (stored_record.get("schema"), stored_record.get("extractor"), (stored_record.get("input") or {}).get("body_sha256")) != (
                extraction.EXTRACTION_SCHEMA, {"name": extractor.name, "version": extractor.version}, record["body_sha256"]):
            raise layer_store.LayerStoreError(
                f"extraction {fingerprint[:16]}…: the stored record is not a {extraction.EXTRACTION_SCHEMA} record "
                f"of {extractor.stage_version} for this body; it is not reinterpreted")
        return extraction.Extraction(stored_record), fingerprint, held
    extracted = extractor.run(body, body_sha256=record["body_sha256"], **_extraction_arguments(record))
    stored = store.put(
        extraction.STAGE, fingerprint, extracted.payload,
        provenance={"fetch_id": record["fetch_id"], "run_id": record["run_id"], "software_version": __version__},
        now=now,
    )
    return extracted, fingerprint, stored


@writes_workspace("replay an extraction")
def replay_extraction(
    workspace: Workspace,
    *,
    preservation_root: Path,
    identifier: str,
    fetch_id: str,
    extractor: extraction.Extractor = extraction.BASELINE,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Re-derive one extraction from the preserved bytes and hold it against the stored answer.

    Same extractor version: the result must be byte-identical (``ALREADY_STORED``); a different
    result raises ``FingerprintConflict`` — non-determinism is an error, not a new version. A new
    extractor version has a new fingerprint and is stored beside the old answer, which stays.
    """
    preserved = open_preserved_pack(preservation_root, identifier)
    if workspace.ledger().state(fetch_id) != "RAW_PRESERVED":
        raise NotPreserved(f"{fetch_id} is not RAW_PRESERVED")
    record, body = preserved.fetch_record(fetch_id), preserved.body(fetch_id)
    extracted = extractor.run(body, body_sha256=record["body_sha256"], **_extraction_arguments(record))
    fingerprint = extraction_fingerprint(extractor, record)
    stored = workspace.layer_store().put(
        extraction.STAGE, fingerprint, extracted.payload,
        provenance={"fetch_id": fetch_id, "replay": True, "software_version": __version__}, now=now,
    )
    return {
        "fetch_id": fetch_id, "extractor": extractor.stage_version, "fingerprint": fingerprint,
        "artifact_id": stored.artifact_id, "status": stored.status,
        "payload_sha256": sha256_bytes(extracted.payload),
    }
