"""CO.PRE.PAN's native export object and its way into ``crosscorpus-release/v1`` (CPD-0011).

**Nothing here has built, or can build today, a release of the corpus.** No corpus material exists,
no extractor is adopted, and an export of kind ``corpus`` is refused for any extractor that is not
``ACTIVE``. What exists is the contract of the object, a builder that is exercised on synthetic
pages, and the mapping native export → release member → release manifest → package → study
population, checked by ``release_contract``.

**The export** (``coprepan-export/v1``) is the smallest immutable, content-addressed thing a
release can name as a member::

    <exports root>/<export_id>/
        EXPORT_MANIFEST.json     what the export is; pins the two things below
        DOCUMENTS.jsonl          one record per document version (coprepan-export-document/v1)
        extraction/<fp[:2]>/<artifact_id>.json   the stored extraction records, byte for byte

* One export holds document versions of **one outlet**. How a release partitions an outlet's
  versions into exports is not fixed; what is fixed is that a version is delivered by exactly one
  member export of a release.
* ``export_id`` is ``cpx1-`` + 32 hex digits of the SHA-256 over the canonical JSON of
  ``EXPORT_MANIFEST.json``. The manifest does not contain the id and pins every other file, so the
  id covers the whole object, provenance included — and no document contains its own digest.
* The manifest carries no clock time, no host and no location: the same versions exported by the
  same code give the same id on every machine. When, where and by which run an export was built is
  execution provenance and is not part of the object.
* It contains extracted text and its provenance by id and hash: fetch, preserved body, pack,
  extraction fingerprint and artifact. **It contains no fetched page** and no pack.
* A corrected text is a new document version in a new export. Nothing is rewritten.
* The layer list is ``["extraction"]``. An annotation layer does not exist; carrying one is a new
  version of this schema, decided with the NLP stage. Token counts are therefore
  ``not_available`` in everything built from a ``v1`` export.

Not the same thing: the *release freeze* written here (``RELEASE_FREEZE.json``, contract §9) is
neither the acquisition baseline freeze of ``freeze.py`` (O-12) nor the legacy freeze manifest of
``legacy_freeze.py``. A *package* is a copy of a release for a purpose, never the release.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import __version__, admission, extraction, identity, layer_store, naming, pack
from . import release_contract as R
from .canonical import is_sha256, record_json, sha256_bytes, staging_path, write_bytes_exclusive

EXPORT_SCHEMA = naming.schema_id("export", 1)
EXPORT_DOCUMENT_SCHEMA = naming.schema_id("export-document", 1)
EXPORT_ID_PREFIX = "cpx1"
EXPORT_ID_HASH_LENGTH = 32
EXPORT_MANIFEST, EXPORT_DOCUMENTS = "EXPORT_MANIFEST.json", "DOCUMENTS.jsonl"
LAYER_EXTRACTION = "extraction"
EXPORT_LAYERS = (LAYER_EXTRACTION,)
KIND_CORPUS, KIND_FIXTURE = "corpus", "fixture"
EXPORT_KINDS = (KIND_CORPUS, KIND_FIXTURE)
BUILDER_TOOL = "coprepan.release_export"
BUILDER_VERSION = "release-export/1"
REPOSITORY = "coprepan"
PIPELINE_ID = "coprepan-pipeline"
OFFSET_REFERENCE = "code-point offsets, half-open, into the text of the token's unit"

STORED, ALREADY_STORED = "STORED", "ALREADY_STORED"
# Suffixes this builder never copies into a package, beyond the contract's list of source media:
# a fetched page is the source of a press release as audio is of a radio one (contract §8).
SOURCE_PAGE_SUFFIXES = (".warc", ".warc.gz", ".arc", ".arc.gz", ".cdx", ".cdxj")

_EXPORT_ID = re.compile(rf"{EXPORT_ID_PREFIX}-[0-9a-f]{{{EXPORT_ID_HASH_LENGTH}}}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_FIXTURE_RELEASE = re.compile(r"coprepan-0000\.[1-9]\d*")
_MANIFEST_FIELDS = ("schema", "corpus_id", "export_kind", "outlet_id", "provenance_class", "layers", "documents",
                    "payload", "components", "code")
_DOCUMENT_FIELDS = ("document_version_id", "document_id", "outlet_id", "extracted_text_sha256", "body_text_sha256",
                    "extraction", "source", "admission", "date", "date_state", "date_basis", "date_basis_state")


class ExportRefused(ValueError):
    """Material that cannot be stated as an export, a release, a package or a population without
    guessing, or that a gate does not let through."""


class ExportConflict(RuntimeError):
    """Another tree already has the name of this export. Nothing was written."""


class FreezeRefused(RuntimeError):
    """A release freeze was asked for without its preconditions."""


def export_id(manifest: Mapping[str, Any]) -> str:
    """``cpx1-`` + 32 hex digits of SHA-256 over the canonical JSON of the export manifest."""
    return f"{EXPORT_ID_PREFIX}-{R.document_digest(manifest)[:EXPORT_ID_HASH_LENGTH]}"


def is_export_id(value: object) -> bool:
    return isinstance(value, str) and _EXPORT_ID.fullmatch(value) is not None


def _instant(value: datetime) -> str:
    """``YYYY-MM-DDThh:mm:ss.ffffffZ`` — an input, never a clock read by this module."""
    return identity.format_instant(value)


def _commit(value: str) -> str:
    if not isinstance(value, str) or _COMMIT.fullmatch(value) is None:
        raise ExportRefused("code_commit is the full 40-digit hash of a clean, committed tree")
    return value


# --- building an export -----------------------------------------------------------------------------


def _document_record(outlet_id: str, kind: str, item: Mapping[str, Any]) -> tuple[dict[str, Any], str, bytes]:
    """One export document record with the path and bytes of its extraction record."""
    payload, source, label = item["extraction_payload"], item["source"], item["admission_label"]
    version = item["document_version_id"]
    try:
        record = R.parse_strict(payload)
    except R.NonCanonical as error:
        raise ExportRefused(f"{version}: the extraction record has no canonical form: {error}") from error
    if record.get("schema") != extraction.EXTRACTION_SCHEMA or record.get("outcome") != extraction.OUTCOME_EXTRACTED:
        raise ExportRefused(f"{version}: only an extracted text is exported")
    if payload != record_json(record):
        raise ExportRefused(f"{version}: the payload is not the stored form of the extraction record")
    text_sha256 = sha256_bytes(extraction.extracted_text_bytes(record["blocks"]))
    body_sha256 = sha256_bytes(extraction.body_text(record["blocks"]).encode("utf-8"))
    if (record["extracted_text_sha256"], record["body_text_sha256"]) != (text_sha256, body_sha256):
        raise ExportRefused(f"{version}: the extraction record's digests do not cover its blocks")
    document = item["document_id"]
    if not identity.is_document_id(document) or not document.startswith(outlet_id + ":"):
        raise ExportRefused(f"{version}: {document!r} is not a document of {outlet_id}")
    if identity.document_version_id(document, text_sha256) != version:
        raise ExportRefused(f"{version}: the version id does not belong to this extracted text")
    if not identity.is_fetch_id(source["fetch_id"]) or not is_sha256(source["body_sha256"]) or not pack.is_pack_id(source["pack_id"]):
        raise ExportRefused(f"{version}: the source is named by fetch id, body digest and pack id")
    if pack.pack_outlet(source["pack_id"]) != outlet_id or record["input"]["body_sha256"] != source["body_sha256"]:
        raise ExportRefused(f"{version}: the extraction was not made from the preserved body the source names")
    fingerprint = item["extraction_fingerprint"]
    stage_version = f"{record['extractor']['name']}/{record['extractor']['version']}"
    extractor = extraction.EXTRACTORS.get(stage_version)
    if kind == KIND_CORPUS:
        if extractor is None:
            raise ExportRefused(f"{version}: {stage_version} is not an extractor this package knows")
        extractor.require_active()  # nothing passes today: no extractor is adopted
    if (label.get("fetch_id"), label.get("document_version_id")) != (source["fetch_id"], version):
        raise ExportRefused(f"{version}: the admission label is not the label of this fetch and version")
    if label["technical_status"] != admission.TECHNICALLY_USABLE:
        raise ExportRefused(f"{version}: technically unusable ({', '.join(label['blocking_reasons'])}); labelled, not exported")
    if label["extraction_payload_sha256"] != sha256_bytes(payload) or label["extraction_fingerprint"] != fingerprint:
        raise ExportRefused(f"{version}: the admission label was given for another extraction")
    artifact = layer_store.artifact_id(fingerprint, sha256_bytes(payload))
    path = f"{LAYER_EXTRACTION}/{fingerprint[:2]}/{artifact}.json"
    dated = item.get("date")
    page_date = record["metadata"]["publication_date"]["value"] != extraction.UNKNOWN
    if dated is not None:
        if dated["basis"] not in extraction.DATE_BASES:
            raise ExportRefused(f"{version}: {dated['basis']!r} is not a basis a publication date can rest on")
        R.cohort_of(dated["date"])  # a calendar date, or ValueError
    state = R.KNOWN if dated is not None else (R.NOT_AVAILABLE if page_date else "unknown")
    return {
        "document_version_id": version, "document_id": document, "outlet_id": outlet_id,
        "extracted_text_sha256": text_sha256, "body_text_sha256": body_sha256,
        "extraction": {"path": path, "sha256": sha256_bytes(payload), "size": len(payload), "fingerprint": fingerprint,
                       "artifact_id": artifact, "extractor": stage_version},
        "source": {"fetch_id": source["fetch_id"], "body_sha256": source["body_sha256"], "pack_id": source["pack_id"]},
        "admission": {"ruleset": label["ruleset"], "technical_status": label["technical_status"],
                      "informing_reasons": sorted(entry["reason"] for entry in label["reasons"])},
        "date": dated["date"] if dated is not None else None, "date_state": state,
        "date_basis": dated["basis"] if dated is not None else None, "date_basis_state": state,
    }, path, payload


def export_files(*, outlet_id: str, documents: Sequence[Mapping[str, Any]], code_commit: str, export_kind: str,
                 date_parser: str | None = None) -> tuple[str, dict[str, bytes]]:
    """``(export_id, {contract path: bytes})`` of an export — computed, nothing written.

    Each of ``documents``: ``document_id``, ``document_version_id``, ``extraction_payload`` (the
    stored bytes of the extraction record), ``extraction_fingerprint``, ``source`` (``fetch_id``,
    ``body_sha256``, ``pack_id`` of the preserved fetch the text was extracted from),
    ``admission_label`` (the technical label of that fetch) and, only where a date was parsed,
    ``date`` (``{"date": "YYYY-MM-DD", "basis": …}``). A page value nobody parsed stays
    ``not_available``; a page without one is ``unknown``. No date is guessed.
    """
    if export_kind not in EXPORT_KINDS:
        raise ExportRefused(f"not an export kind: {export_kind!r}")
    if not naming.is_outlet_id(outlet_id):
        raise ExportRefused(f"not an outlet id: {outlet_id!r}")
    if not documents:
        raise ExportRefused("an export delivers at least one document version")
    if any(item.get("date") is not None for item in documents) != (date_parser is not None):
        raise ExportRefused("a parsed date names the component that parsed it, and only a parsed date does")
    records, files = [], {}
    for item in documents:
        record, path, payload = _document_record(outlet_id, export_kind, item)
        records.append(record)
        files[path] = payload
    versions = [record["document_version_id"] for record in records]
    if len(set(versions)) != len(versions):
        raise ExportRefused("a document version is delivered once")
    listing = [{"path": path, "sha256": sha256_bytes(data), "size": len(data)} for path, data in files.items()]
    extractors = sorted({record["extraction"]["extractor"] for record in records})
    manifest = {
        "schema": EXPORT_SCHEMA, "corpus_id": naming.CORPUS_ID, "export_kind": export_kind, "outlet_id": outlet_id,
        "provenance_class": "native_v3", "layers": list(EXPORT_LAYERS),
        "documents": {"schema": EXPORT_DOCUMENT_SCHEMA, "records": len(records), "sha256": R.record_set_digest(records)},
        "payload": {"files": len(listing), "bytes": sum(entry["size"] for entry in listing), "sha256": R.record_set_digest(listing)},
        "components": {
            "export_builder": BUILDER_VERSION, "extraction_schema": extraction.EXTRACTION_SCHEMA, "extractors": extractors,
            "extractor_lifecycles": {name: getattr(extraction.EXTRACTORS.get(name), "lifecycle", extraction.UNKNOWN) for name in extractors},
            "admission_rulesets": sorted({record["admission"]["ruleset"] for record in records}),
            "url_key_ruleset": identity.URL_KEY_RULESET, "date_parser": date_parser,
            "date_parser_state": R.KNOWN if date_parser is not None else R.NOT_AVAILABLE,
        },
        "code": {"repository": REPOSITORY, "commit": _commit(code_commit), "package_version": __version__},
    }
    files[EXPORT_DOCUMENTS] = R.record_set_bytes(records)
    files[EXPORT_MANIFEST] = record_json(manifest)
    return export_id(manifest), files


def _write_tree(final: Path, files: Mapping[str, bytes]) -> None:
    """Write a tree under a ``.part-`` name and give it its final name only if that name is free.
    A tree left under a ``.part-`` name by an interrupted write is never an export.
    """
    final.parent.mkdir(parents=True, exist_ok=True)
    staging = staging_path(final)
    for path, data in sorted(files.items()):
        if not R.is_contract_path(path):
            raise ExportRefused(f"not a contract path: {path!r}")
        write_bytes_exclusive(staging / Path(*path.split("/")), data)
    try:
        os.rename(staging, final)
    except OSError as error:
        raise ExportConflict(f"{final.name} appeared while it was being written; the staged tree is left under {staging.name}") from error


def _same_tree(directory: Path, files: Mapping[str, bytes]) -> bool:
    expected = sorted((path, sha256_bytes(data), len(data)) for path, data in files.items())
    try:
        return sorted((entry["path"], entry["sha256"], entry["size"]) for entry in R.tree_listing(directory)) == expected
    except R.PathInvalid:
        return False


def build_export(exports_root: Path, **arguments: Any) -> tuple[str, str]:
    """Write an export to ``<exports_root>/<export_id>/`` once. Returns ``(export_id, status)``:
    ``STORED``, or ``ALREADY_STORED`` when exactly this tree is there. A different tree under the
    id raises :class:`ExportConflict`; nothing is ever overwritten. Arguments: :func:`export_files`.
    """
    identifier, files = export_files(**arguments)
    final = Path(exports_root) / identifier
    if final.exists():
        if not _same_tree(final, files):
            raise ExportConflict(f"{identifier} exists and is not this export")
        return identifier, ALREADY_STORED
    _write_tree(final, files)
    problems = export_problems(final)
    if problems:
        raise ExportRefused(f"{identifier} does not verify after writing: {problems}")
    return identifier, STORED


# --- reading and verifying an export ----------------------------------------------------------------


def read_export(directory: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """``(manifest, document records)`` of an export that verifies; raises :class:`ExportRefused`."""
    problems = export_problems(directory)
    if problems:
        raise ExportRefused(f"{Path(directory).name}: " + "; ".join(problems))
    directory = Path(directory)
    return (R.parse_strict((directory / EXPORT_MANIFEST).read_bytes()), R.parse_records((directory / EXPORT_DOCUMENTS).read_bytes()))


def export_problems(directory: Path) -> list[str]:
    """Why a directory is not a ``coprepan-export/v1`` export under its own name. Empty: it is.
    Reads everything, repairs nothing.
    """
    directory = Path(directory)
    try:
        listing = {entry["path"]: entry for entry in R.tree_listing(directory)}
        manifest = R.parse_strict((directory / EXPORT_MANIFEST).read_bytes())
        records = R.parse_records((directory / EXPORT_DOCUMENTS).read_bytes())
    except (OSError, R.PathInvalid, R.NonCanonical) as error:
        return [f"not readable as an export: {error}"]
    if not isinstance(manifest, dict) or manifest.get("schema") != EXPORT_SCHEMA:
        return [f"not a {EXPORT_SCHEMA} manifest: refused by name, never read on a guess"]
    if tuple(sorted(manifest)) != tuple(sorted(_MANIFEST_FIELDS)):
        return ["the manifest does not have exactly the fields of the schema"]
    problems = []
    if export_id(manifest) != directory.name:
        problems.append(f"the manifest gives the id {export_id(manifest)}, not {directory.name}")
    if manifest["corpus_id"] != naming.CORPUS_ID or manifest["export_kind"] not in EXPORT_KINDS or manifest["layers"] != list(EXPORT_LAYERS):
        problems.append("corpus, kind or layers are not those of this schema version")
    pinned = manifest["documents"]
    if pinned["schema"] != EXPORT_DOCUMENT_SCHEMA or pinned["records"] != len(records) or pinned["sha256"] != R.record_set_digest(records):
        problems.append("the document records are not the pinned set")
    payload = sorted((path, entry) for path, entry in listing.items() if path not in (EXPORT_MANIFEST, EXPORT_DOCUMENTS))
    if any(not path.startswith(LAYER_EXTRACTION + "/") for path, _ in payload):
        problems.append("a file outside the declared layers: an export holds its manifest, its records and its layers")
    found = {"files": len(payload), "bytes": sum(entry["size"] for _, entry in payload),
             "sha256": R.record_set_digest([entry for _, entry in payload])}
    if found != manifest["payload"]:
        problems.append("the layer files are not the pinned ones")
    referenced = set()
    for record in records:
        version = record.get("document_version_id")
        if not isinstance(record, dict) or tuple(sorted(record)) != tuple(sorted(_DOCUMENT_FIELDS)):
            problems.append(f"{version}: not exactly the fields of {EXPORT_DOCUMENT_SCHEMA}")
            continue
        stored = listing.get(record["extraction"]["path"])
        if stored is None or (stored["sha256"], stored["size"]) != (record["extraction"]["sha256"], record["extraction"]["size"]):
            problems.append(f"{version}: its extraction record is not in the export")
            continue
        referenced.add(record["extraction"]["path"])
        try:
            text = R.parse_strict((directory / record["extraction"]["path"]).read_bytes())
            together = (record["outlet_id"] == manifest["outlet_id"] and record["document_id"].startswith(manifest["outlet_id"] + ":")
                        and sha256_bytes(extraction.extracted_text_bytes(text["blocks"])) == record["extracted_text_sha256"]
                        and identity.document_version_id(record["document_id"], record["extracted_text_sha256"]) == version
                        and text["input"]["body_sha256"] == record["source"]["body_sha256"])
        except (R.NonCanonical, KeyError, TypeError, ValueError):
            together = False
        if not together:
            problems.append(f"{version}: outlet, version id, extracted text and preserved body do not belong together")
        if (record["date"] is None) == (record["date_state"] == R.KNOWN) or record["date_state"] != record["date_basis_state"]:
            problems.append(f"{version}: a date and its basis are known together or not at all")
    if len({record.get("document_version_id") for record in records}) != len(records):
        problems.append("a document version is delivered twice")
    if referenced != {path for path, _ in payload}:
        problems.append("a layer file that no document record names")
    return problems


def member_record(directory: Path) -> dict[str, Any]:
    """The release member record of an export (contract §6.1): its native id, and the tree digest
    over **all** of its files.
    """
    manifest, records = read_export(directory)
    listing = R.tree_listing(directory)
    return {"export_id": Path(directory).name, "export_schema": manifest["schema"], "tree_sha256": R.record_set_digest(listing),
            "files": len(listing), "bytes": sum(entry["size"] for entry in listing), "documents": len(records)}


def document_records(directory: Path) -> list[dict[str, Any]]:
    """The release document records an export delivers (contract §7.1). The document is the
    document version; ``source_sha256`` is the digest of its extracted text; a token count does not
    exist for a ``v1`` export; ``audio_ms`` does not apply to writing.
    """
    _, records = read_export(directory)
    out = []
    for record in records:
        dated = record["date_state"] == R.KNOWN
        out.append({
            "document_id": record["document_version_id"], "export_id": Path(directory).name, "outlet_id": record["outlet_id"],
            "country_id": naming.outlet_country(record["outlet_id"]),
            "date": record["date"], "date_state": record["date_state"],
            "date_basis": record["date_basis"], "date_basis_state": record["date_basis_state"],
            "cohort": R.cohort_of(record["date"]) if dated else None, "cohort_state": record["date_state"],
            "tokens_counted": None, "tokens_counted_state": R.NOT_AVAILABLE,
            "audio_ms": None, "audio_ms_state": R.NOT_APPLICABLE,
            "source_sha256": record["extracted_text_sha256"], "source_sha256_state": R.KNOWN,
        })
    return out


# --- release ----------------------------------------------------------------------------------------

NOT_PINNED = {"state": R.NOT_AVAILABLE, "id": None, "sha256": None}
NO_ANALYSIS_LAYER = {"state": R.NOT_AVAILABLE, "contract": None, "manifest_sha256": None}


def build_release(
    release_directory: Path,
    *,
    release_id: str,
    release_kind: str,
    exports_root: Path,
    export_ids: Sequence[str],
    created_at: datetime,
    code_commit: str,
    selection_policy: Mapping[str, Any] | None = None,
    analysis_layer: Mapping[str, Any] | None = None,
    previous_directory: Path | None = None,
    replaced: Sequence[Mapping[str, str]] = (),
    removed: Sequence[Mapping[str, str]] = (),
    contract: R.Contract | None = None,
) -> str:
    """Write the manifest and record sets of a release into a new directory and return the
    manifest digest. **This does not make a release**: a release exists when its freeze record
    does (:func:`freeze_release`).

    ``replaced`` (``old``, ``new``, ``reason``) and ``removed`` (``export_id``, ``reason``) account
    for the difference to the previous release; what is new and neither is ``added``.
    """
    contract = contract or R.load_contract()
    fixture = _FIXTURE_RELEASE.fullmatch(release_id) is not None
    if not naming.is_release_id(release_id) or release_id == naming.LEGACY_RELEASE_ID:
        raise ExportRefused(f"not a release id of native CO.PRE.PAN material: {release_id!r}")
    if release_kind not in ("release", "provisional_export", "fixture") or fixture != (release_kind == "fixture"):
        raise ExportRefused("a release id with year 0000 marks a fixture, and only a fixture")
    members, documents, manifests = [], [], []
    for identifier in export_ids:
        if not is_export_id(identifier):
            raise ExportRefused(f"not an export id: {identifier!r}")
        manifest, _ = read_export(Path(exports_root) / identifier)
        if (manifest["export_kind"] == KIND_FIXTURE) != fixture:
            raise ExportRefused(f"{identifier}: a fixture export enters a fixture release, and nothing else does")
        manifests.append(manifest)
        members.append(member_record(Path(exports_root) / identifier))
        documents += document_records(Path(exports_root) / identifier)
    versions = [document["document_id"] for document in documents]
    if len(set(versions)) != len(versions):
        raise ExportRefused("a document version is delivered by exactly one member export of a release")
    if release_kind == "release" and (selection_policy or NOT_PINNED)["state"] != R.KNOWN:
        raise ExportRefused("a release pins its selection policy")

    previous = {"state": R.NOT_APPLICABLE, "release_id": None, "release_manifest_sha256": None}
    before: set[str] = set()
    if previous_directory is not None:
        earlier = R.verify_release(previous_directory, contract=contract)
        if not earlier.conformant:
            raise ExportRefused(f"the previous release does not verify: {earlier.codes}")
        named = R.parse_strict((Path(previous_directory) / R.RELEASE_MANIFEST).read_bytes())
        previous = {"state": R.KNOWN, "release_id": named["release_id"],
                    "release_manifest_sha256": R.release_manifest_digest(previous_directory)}
        before = {member["export_id"] for member in R.parse_records((Path(previous_directory) / R.MEMBERS).read_bytes())}
    now = {member["export_id"] for member in members}
    accounted = {item["new"] for item in replaced}
    tokens, tokens_state = R.stateful_sum(documents, "tokens_counted")
    audio, audio_state = R.stateful_sum(documents, "audio_ms")
    manifest = {
        "schema": R.MANIFEST_SCHEMA, "contract": R.CONTRACT, "corpus_id": naming.CORPUS_ID, "release_id": release_id,
        "release_kind": release_kind, "fixture": fixture, "modality": "written", "created_at": _instant(created_at),
        "previous_release": previous,
        "members": {"schema": R.MEMBER_SCHEMA, "records": len(members), "sha256": R.record_set_digest(members)},
        "documents": {"schema": R.DOCUMENT_SCHEMA, "records": len(documents), "sha256": R.record_set_digest(documents)},
        "coverage": None,
        "changes": {"added": sorted(now - before - accounted), "replaced": [dict(item) for item in replaced],
                    "removed": [dict(item) for item in removed]},
        "selection_policy": dict(selection_policy or NOT_PINNED),
        "date_semantics": "crosscorpus-date-semantics/v1",
        # A v1 export carries no annotation: CO.PRE.PAN cannot count under the shared denominator yet.
        "token_denominator": None, "token_denominator_state": R.NOT_AVAILABLE,
        "totals": {"exports": len(members), "documents": len(documents), "tokens_counted": tokens,
                   "tokens_counted_state": tokens_state, "audio_ms": audio, "audio_ms_state": audio_state},
        "anchors": {"document_kind": "document_version", "unit_kinds": list(extraction.BLOCK_KINDS), "producer_kinds": [],
                    "source_kind": "extracted_text", "source_included": False,
                    "offset_reference": OFFSET_REFERENCE, "offset_reference_state": R.KNOWN,
                    "time_reference": None, "time_reference_state": R.NOT_APPLICABLE},
        "vocabularies": {"date_basis": list(extraction.DATE_BASES), "export_schema": [EXPORT_SCHEMA]},
        "analysis_layer": dict(analysis_layer or NO_ANALYSIS_LAYER),
        "provenance": {
            "builder": {"repository": REPOSITORY, "commit": _commit(code_commit), "tool": BUILDER_TOOL, "tool_version": BUILDER_VERSION},
            "pipeline": {"id": PIPELINE_ID, "versions": sorted({version for m in manifests for version in
                                                                 [m["components"]["export_builder"], *m["components"]["extractors"],
                                                                  *m["components"]["admission_rulesets"]]})},
            "stack": dict(NOT_PINNED), "models": [], "configuration": [],
            "member_code_commits": sorted({m["code"]["commit"] for m in manifests}),
        },
    }
    coverage = R.derive_coverage(documents)
    manifest["coverage"] = {"schema": R.COVERAGE_SCHEMA, "records": len(coverage), "sha256": R.record_set_digest(coverage)}
    directory = Path(release_directory)
    if directory.exists():
        raise ExportRefused(f"{directory.name} exists: a release directory is written once")
    _write_tree(directory, {R.RELEASE_MANIFEST: record_json(manifest), R.MEMBERS: R.record_set_bytes(members),
                            R.DOCUMENTS: R.record_set_bytes(documents), R.COVERAGE: R.record_set_bytes(coverage)})
    pending = _unfrozen_objections(directory, exports_root, previous_directory, contract)
    if pending:
        raise ExportRefused(f"the manifest written does not verify: {pending}")
    return R.document_digest(manifest)


def _unfrozen_objections(directory: Path, exports_root: Path, previous_directory: Path | None, contract: R.Contract) -> list[str]:
    """What a check with every export present objects to, apart from the freeze record that does
    not exist yet. (A provisional export needs none.)
    """
    verdict = R.verify_release(directory, exports_root=exports_root, require_exports=True, previous_directory=previous_directory,
                               contract=contract)
    return [f"{o.code}: {o.where}: {o.detail}" for o in verdict.objections
            if (o.code, o.where) != ("REFERENCE_MISSING", R.RELEASE_FREEZE)]


def freeze_release(release_directory: Path, *, exports_root: Path, frozen_by: str, frozen_at: datetime, confirmation: str,
                   contract: R.Contract | None = None) -> dict[str, Any]:
    """The act that makes a manifest a release (contract §9.1): after a check with every export
    present has passed, and only when the person freezing states the manifest's digest. Writes
    ``RELEASE_FREEZE.json`` once; the manifest is not touched. A provisional export is never frozen.
    """
    contract, directory = contract or R.load_contract(), Path(release_directory)
    manifest = R.parse_strict((directory / R.RELEASE_MANIFEST).read_bytes())
    digest = R.document_digest(manifest)
    if manifest["release_kind"] == "provisional_export":
        raise FreezeRefused("a provisional export has no freeze record and is not a release")
    if confirmation != digest:
        raise FreezeRefused("a freeze is confirmed by stating the manifest's digest")
    if (directory / R.RELEASE_FREEZE).exists():
        raise FreezeRefused(f"{manifest['release_id']} is frozen; a release is frozen once")
    pending = _unfrozen_objections(directory, exports_root, None, contract)
    if pending:
        raise FreezeRefused(f"the release does not pass the check with every export present: {pending}")
    record = {"schema": R.FREEZE_SCHEMA, "contract": R.CONTRACT, "corpus_id": manifest["corpus_id"], "release_id": manifest["release_id"],
              "release_manifest_sha256": digest, "state": "FROZEN", "frozen_at": _instant(frozen_at), "frozen_by": frozen_by}
    if contract.problems(R.FREEZE_SCHEMA, record):
        raise FreezeRefused(f"not a freeze record: {contract.problems(R.FREEZE_SCHEMA, record)}")
    write_bytes_exclusive(directory / R.RELEASE_FREEZE, record_json(record))
    return record


# --- package ----------------------------------------------------------------------------------------


def build_package(
    package_directory: Path,
    *,
    release_directory: Path,
    exports_root: Path,
    package_kind: str,
    package_id: str,
    created_at: datetime,
    metadata: Mapping[str, Any],
    exports: str = "included",
    extra_files: Mapping[str, tuple[str, bytes]] | None = None,
    contract: R.Contract | None = None,
) -> str:
    """Write a distribution or archive package of one frozen release into a new directory and
    return the digest of its manifest. A package is a copy for a purpose: it can be rebuilt and is
    never the release. ``extra_files`` maps a contract path to ``(role, bytes)``.

    This is a local test of the mechanics. It writes where it is told to and publishes nothing; no
    distribution target, licence, access level or identifier is decided.
    """
    contract = contract or R.load_contract()
    release_directory, exports_root = Path(release_directory), Path(exports_root)
    frozen = R.verify_release(release_directory, exports_root=exports_root, require_exports=True, contract=contract)
    manifest = R.parse_strict((release_directory / R.RELEASE_MANIFEST).read_bytes()) if frozen.conformant else None
    if manifest is None or manifest["release_kind"] == "provisional_export":
        raise ExportRefused(f"a package is a copy of exactly one frozen release that verifies: {frozen.codes}")
    files: dict[str, tuple[str, bytes]] = {
        path: (role, (release_directory / path.split("/", 1)[1]).read_bytes()) for path, role in R.RELEASE_FILE_ROLES.items()}
    if exports == "included":
        for member in R.parse_records((release_directory / R.MEMBERS).read_bytes()):
            for entry in R.tree_listing(exports_root / member["export_id"]):
                files[f"exports/{member['export_id']}/{entry['path']}"] = (
                    "export_payload", (exports_root / member["export_id"] / Path(*entry["path"].split("/"))).read_bytes())
    for path, (role, data) in (extra_files or {}).items():
        if path in files or path.startswith(("release/", "exports/")) or path in (R.PACKAGE_MANIFEST, R.PACKAGE_FILES):
            raise ExportRefused(f"{path!r} is not a place for an additional file")
        files[path] = (role, data)
    for path in files:
        if path.casefold().endswith(R.FORBIDDEN_SUFFIXES + SOURCE_PAGE_SUFFIXES):
            raise ExportRefused(f"{path!r}: source media and fetched pages are never part of a package")
    listing = [{"path": path, "sha256": sha256_bytes(data), "size": len(data), "role": role} for path, (role, data) in files.items()]
    package = {
        "schema": R.PACKAGE_SCHEMA, "contract": R.CONTRACT, "package_kind": package_kind, "package_id": package_id,
        "created_at": _instant(created_at),
        "release": {"corpus_id": manifest["corpus_id"], "release_id": manifest["release_id"],
                    "release_manifest_sha256": R.document_digest(manifest)},
        "exports": exports, "contains_source_media": False,
        "files": {"schema": R.PACKAGE_FILE_SCHEMA, "records": len(listing), "sha256": R.record_set_digest(listing)},
        "metadata": {**metadata, "version": manifest["release_id"]},
    }
    directory = Path(package_directory)
    if directory.exists():
        raise ExportRefused(f"{directory.name} exists: a package is written into a new directory")
    _write_tree(directory, {**{path: data for path, (_, data) in files.items()},
                            R.PACKAGE_FILES: R.record_set_bytes(listing), R.PACKAGE_MANIFEST: record_json(package)})
    verdict = R.verify_package(directory, exports_root=None if exports == "included" else exports_root, contract=contract)
    if not verdict.conformant:
        raise ExportRefused(f"the package written does not verify: {[(o.code, o.where, o.detail) for o in verdict.objections]}")
    return R.document_digest(package)


# --- study population -------------------------------------------------------------------------------


def build_study_population(
    study_directory: Path,
    *,
    study_id: str,
    population_id: str,
    created_at: datetime,
    releases: Mapping[str, Path],
    selection: Mapping[str, Any],
    selected: Sequence[Mapping[str, Any]] = (),
    excluded: Sequence[Mapping[str, Any]] = (),
    analysis_layers: Mapping[str, Mapping[str, Any]] | None = None,
    analysis_code: Mapping[str, Any] | None = None,
    contract: R.Contract | None = None,
) -> str:
    """Freeze the population of one analysis over pinned releases and return the digest of its
    manifest. **The frozen ids are the identity of the population; the selection is its provenance.**

    ``releases`` maps a ``corpus_id`` to the release directory at hand. For a
    ``declarative_filter`` selection the selected documents are the filter's result minus
    ``excluded`` (records with a reason), and ``selected`` must be empty; for the other kinds both
    lists are given as selection records without ``corpus_id`` and ``release_id``, which are filled
    in from the document.

    What a study pins, per corpus: the release by id **and** release manifest digest, and — where
    it read analysis tables — the ``manifest_sha256`` of that ``crosscorpus-analysis/v1`` bundle
    (``analysis_layers``). Nothing else, and nothing less (CPD-0012, amending CPD-0008 §7).
    """
    contract = contract or R.load_contract()
    inputs, documents_of, release_of = [], {}, {}
    for corpus_id, place in sorted(releases.items()):
        verdict = R.verify_release(place, contract=contract)
        if not verdict.conformant:
            raise ExportRefused(f"the release of {corpus_id} does not verify: {verdict.codes}")
        manifest = R.parse_strict((Path(place) / R.RELEASE_MANIFEST).read_bytes())
        if manifest["corpus_id"] != corpus_id:
            raise ExportRefused(f"{manifest['release_id']} is not a release of {corpus_id}")
        release_of[corpus_id] = manifest["release_id"]
        documents_of[corpus_id] = R.parse_records((Path(place) / R.DOCUMENTS).read_bytes())
        inputs.append({"corpus_id": corpus_id, "release_id": manifest["release_id"],
                       "release_manifest_sha256": R.document_digest(manifest),
                       "analysis_layer": dict((analysis_layers or {}).get(corpus_id, NO_ANALYSIS_LAYER))})

    def complete(record: Mapping[str, Any]) -> dict[str, Any]:
        corpus_id = next((name for name, rows in documents_of.items()
                          if any(row["document_id"] == record["document_id"] for row in rows)), None)
        if corpus_id is None:
            raise ExportRefused(f"{record['id']}: its document is in no pinned release")
        return {"corpus_id": corpus_id, "release_id": release_of[corpus_id], "level": record["level"], "id_kind": record["id_kind"],
                "id": record["id"], "document_id": record["document_id"], "reason": record.get("reason")}

    excluded_records = [complete(record) for record in excluded]
    if selection["kind"] == "declarative_filter":
        if selected:
            raise ExportRefused("a declarative selection selects by its filter; only its exclusions are stated")
        dropped = {record["id"] for record in excluded_records}
        selected_records, chosen_anywhere = [], set()
        for entry in selection["filters"]:
            kind = "recording" if entry["corpus_id"] == naming.SIBLING_CORPUS_ID else "document_version"
            chosen = R.filter_documents(documents_of[entry["corpus_id"]], entry["all"])
            chosen_anywhere |= set(chosen)
            selected_records += [{"corpus_id": entry["corpus_id"], "release_id": release_of[entry["corpus_id"]], "level": "document",
                                  "id_kind": kind, "id": name, "document_id": name, "reason": None}
                                 for name in chosen if name not in dropped]
        if not dropped <= chosen_anywhere:
            raise ExportRefused("an exclusion of a declarative selection is a document its filter selects")
    else:
        selected_records = [complete(record) for record in selected]
    study = {
        "schema": R.STUDY_SCHEMA, "contract": R.CONTRACT, "study_id": study_id, "population_id": population_id,
        "created_at": _instant(created_at), "inputs": inputs,
        "selection": {"kind": selection["kind"], "tool": dict(selection["tool"]),
                      "filter_language": R.FILTER_LANGUAGE if selection["kind"] == "declarative_filter" else None,
                      "filters": [dict(entry) for entry in selection.get("filters", [])], "description": selection["description"]},
        "selected": {"schema": R.SELECTION_SCHEMA, "records": len(selected_records), "sha256": R.record_set_digest(selected_records)},
        "excluded": {"schema": R.SELECTION_SCHEMA, "records": len(excluded_records), "sha256": R.record_set_digest(excluded_records)},
        "exclusion_reasons": sorted({record["reason"] for record in excluded_records}),
        "totals": [R.study_totals(corpus_id, selected_records, documents_of[corpus_id]) for corpus_id in sorted(releases)],
        "analysis_code": dict(analysis_code or {"repository": None, "repository_state": R.NOT_AVAILABLE,
                                                "commit": None, "commit_state": R.NOT_AVAILABLE}),
    }
    directory = Path(study_directory)
    if directory.exists():
        raise ExportRefused(f"{directory.name} exists: a population is frozen once")
    _write_tree(directory, {R.STUDY_POPULATION: record_json(study), R.SELECTED: R.record_set_bytes(selected_records),
                            R.EXCLUDED: R.record_set_bytes(excluded_records)})
    verdict = R.verify_study(directory, {release_of[corpus_id]: Path(place) for corpus_id, place in releases.items()}, contract=contract)
    if not verdict.conformant:
        raise ExportRefused(f"the population written does not verify: {[(o.code, o.where, o.detail) for o in verdict.objections]}")
    return R.document_digest(study)
