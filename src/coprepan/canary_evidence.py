"""What a finished canary run is held against: measurement for O-4 and verification from evidence.

Two read-only functions of one run's workspace and preservation root (CPD-0016):

* :func:`measure` — the sizes the capacity model has been waiting for, each labelled
  ``MEASURED`` (read off files or records), ``DERIVED`` (computed from measured values by a stated step),
  ``ASSUMED`` or ``PROJECTED``; and the projections, which are conditional statements about volume and say
  so. **A five-outlet canary measures sizes, not a crawl rate.** The number of fetches per outlet in the
  canary is the budget's, not the web's.
* :func:`verify` — the checks of the end of a canary: read-back of the preserved packs, fixity of every
  body, replay of the extractions with the network made unavailable, the identity tables held against
  a rebuild, the recovery diagnosis, and the run receipt re-derived from evidence and compared with the
  one the run wrote.
"""

from __future__ import annotations

import json
import socket
import statistics
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from . import acquisition, canary_driver as D, capacity, core_pipeline, extraction, naming, outage_spool, pack, preservation, recovery
from .canonical import sha256_bytes

MEASUREMENT_SCHEMA = naming.schema_id("canary-measurement", 1)
VERIFICATION_SCHEMA = naming.schema_id("canary-verification", 1)
MEASURED, DERIVED, ASSUMED, PROJECTED = "MEASURED", "DERIVED", "ASSUMED", "PROJECTED"
CAPACITY_LABEL = {MEASURED: capacity.MEASURED, DERIVED: capacity.ESTIMATED, ASSUMED: capacity.ASSUMED, PROJECTED: capacity.ASSUMED}
GIB, TIB = 1024 ** 3, 1024 ** 4


def _size(path: Path) -> int:
    return path.stat().st_size if path.is_file() else sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.is_dir() else 0


def _mean(values: Sequence[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def measure(
    workspace: core_pipeline.Workspace,
    *,
    run_id: str,
    preservation_root: Path,
    target_free_bytes: int | None,
    new_filesystem_bytes: int | None = None,
    legacy_sourced: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """The O-4 measurement of a run. ``target_free_bytes`` and ``new_filesystem_bytes`` are the free
    space of the interim target and the nominal size of the planned file system, **as the operator
    states them** (``None``: the comparison is left out, not guessed).
    """
    records, entries_of = [], {}
    for identifier in D.pack_ids(workspace):
        sealed = workspace.packs / f"{identifier}.warc.gz"
        path = sealed if sealed.exists() else workspace.packs / f"{identifier}.warc.gz.open"
        index = {entry.fetch_id: entry for entry in pack.scan(path, identifier)}
        for fetch_id, entry in index.items():
            record = pack.read_fetch_record(path, entry)
            if record["run_id"] == run_id:
                records.append(record)
                entries_of[fetch_id] = (identifier, entry)
    if not records:
        raise ValueError(f"{run_id}: no fetch record: nothing to measure")

    def group(record: Mapping[str, Any]) -> str:
        if record["outcome"] != acquisition.OUTCOME_FETCHED:
            return "failed_without_response"
        return f"{record['fetch_kind']}:{'2xx' if 200 <= record['response']['status'] < 300 else 'other_status'}"

    by_group: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        by_group[group(record)].append(record)

    def stored(record: Mapping[str, Any]) -> tuple[int, int]:
        """(response member bytes, metadata member bytes) as stored in the pack: compressed, with their WARC headers."""
        entry = entries_of[record["fetch_id"]][1]
        return (entry.response_length or 0, entry.metadata_length)

    # --- per group: what a fetch costs in the pack ---
    groups = {}
    for name, rows in sorted(by_group.items()):
        response = [stored(r)[0] for r in rows]
        metadata = [stored(r)[1] for r in rows]
        received = [r["body_size_bytes"] for r in rows if isinstance(r["body_size_bytes"], int)]
        groups[name] = {
            "fetches": len(rows), "received_body_bytes_mean": round(_mean(received)), "received_body_bytes_total": sum(received),
            "stored_response_member_bytes_mean": round(_mean(response)), "stored_response_member_bytes_total": sum(response),
            "stored_metadata_member_bytes_mean": round(_mean(metadata)), "label": MEASURED}

    packs = D.pack_ids(workspace)
    pack_file_bytes = sum(_size(workspace.packs / f"{p}.warc.gz") or _size(workspace.packs / f"{p}.warc.gz.open") for p in packs)
    index_bytes = sum(_size(workspace.packs / f"{p}.index.jsonl") for p in packs)
    manifest_bytes = sum(_size(workspace.packs / f"{p}.pack.json") for p in packs)
    member_bytes = sum(sum(stored(r)) for r in records)
    n = len(records)
    preserved_object_bytes = 0
    for identifier in packs:
        for area in (core_pipeline.AREA_PACKS, core_pipeline.AREA_INDEXES):
            held = preservation.read_manifest(preservation_root, area, identifier)
            preserved_object_bytes += held["size_bytes"] if held else 0
    preservation_manifest_bytes = _size(preservation_root / "preservation" / "manifests") if (preservation_root / "preservation" / "manifests").exists() else 0

    # --- the rest of the runtime workspace, and the extraction layer ---
    workspace_other = sum(_size(p) for p in workspace.root.iterdir() if p.name not in ("packs", "layers", ".writer.lock"))
    layers = _size(workspace.layers) if workspace.layers.exists() else 0
    items_extracted = sum(1 for p in workspace.layers.rglob("payload")) if workspace.layers.exists() else 0

    # --- per outlet ---
    outlets = {}
    for outlet in sorted({r["outlet_id"] for r in records}):
        rows = [r for r in records if r["outlet_id"] == outlet]
        items = [r for r in rows if r["fetch_kind"] == acquisition.FETCH_KIND_ITEM and r["outcome"] == acquisition.OUTCOME_FETCHED]
        outlets[outlet] = {
            "fetch_records": len(rows), "real_requests": sum(D.transport_calls(r) for r in rows), "items_fetched": len(items),
            "stored_bytes_per_fetch": round(_mean([sum(stored(r)) for r in rows])), "label": MEASURED}
    per_outlet_bytes = {o: v["stored_bytes_per_fetch"] for o, v in outlets.items()}
    candidates_per_channel = Counter(r["discovery"]["channel_id"] for r in records if r["fetch_kind"] == acquisition.FETCH_KIND_ITEM)

    measured = {
        "fetch_records": {"value": n, "label": MEASURED},
        "stored_bytes_per_fetch_members": {"value": round(member_bytes / n), "label": DERIVED, "how": "response + metadata members of every fetch, compressed, over fetch records"},
        "pack_file_bytes_per_fetch": {"value": round(pack_file_bytes / n), "label": DERIVED, "how": "pack file size over fetch records (includes the warcinfo record and container overhead)"},
        "pack_overhead_beyond_members_bytes_per_fetch": {"value": round((pack_file_bytes - member_bytes) / n), "label": DERIVED},
        "index_bytes_per_fetch": {"value": round(index_bytes / n), "label": DERIVED, "how": "index file size over fetch records"},
        "pack_manifest_bytes_total": {"value": manifest_bytes, "label": MEASURED},
        "preserved_object_bytes_total": {"value": preserved_object_bytes, "label": MEASURED, "how": "pack + index masters on the preservation root, from their manifests"},
        "preservation_manifest_bytes_total": {"value": preservation_manifest_bytes, "label": MEASURED, "how": "manifest files on the preservation root"},
        "workspace_other_bytes_per_fetch": {"value": round(workspace_other / n), "label": DERIVED, "how": "ledger, request log, discovery, identity, labels, run records over fetch records"},
        "extraction_layer_bytes_per_extracted_item": {"value": round(layers / items_extracted) if items_extracted else None, "label": DERIVED,
                                                      "how": "layer store size over stored extraction payloads"},
        "extraction_layer_bytes_total": {"value": layers, "label": MEASURED},
        "items_extracted": {"value": items_extracted, "label": MEASURED},
        "compression_ratio_stored_over_received": {"value": round(sum(stored(r)[0] for r in records) / max(1, sum(r["body_size_bytes"] for r in records if isinstance(r["body_size_bytes"], int))), 3), "label": DERIVED},
        "item_share_of_fetches": {"value": round(sum(len(v) for k, v in by_group.items() if k.startswith("item")) / n, 3), "label": DERIVED},
    }
    spread = {"per_outlet_stored_bytes_per_fetch": per_outlet_bytes,
              "min": min(per_outlet_bytes.values()), "mean": round(_mean(list(per_outlet_bytes.values()))), "max": max(per_outlet_bytes.values()),
              "label": DERIVED, "note": "outlet means; a spread over a handful of outlets, not a distribution of the press"}
    per_fetch_total = measured["pack_file_bytes_per_fetch"]["value"] + measured["index_bytes_per_fetch"]["value"]
    scenarios = {}
    pack_per_fetch = {"LOW": spread["min"], "CENTRAL": measured["stored_bytes_per_fetch_members"]["value"], "UPPER": spread["max"]}
    for name, per_fetch in pack_per_fetch.items():
        extras = (measured["index_bytes_per_fetch"]["value"] + measured["workspace_other_bytes_per_fetch"]["value"]
                  + (measured["extraction_layer_bytes_per_extracted_item"]["value"] or 0) * measured["item_share_of_fetches"]["value"])
        scenarios[name] = {"preserved_bytes_per_fetch": per_fetch + measured["index_bytes_per_fetch"]["value"],
                           "all_layers_bytes_per_fetch": round(per_fetch + extras),
                           "per_1000_fetches_mib": round(1000 * (per_fetch + extras) / 2**20, 2),
                           "per_100000_fetches_gib": round(100000 * (per_fetch + extras) / GIB, 2), "label": PROJECTED,
                           "basis": {"LOW": "smallest outlet mean", "CENTRAL": "mean over all fetch records", "UPPER": "largest outlet mean"}[name]}
    legacy = dict(legacy_sourced or {})
    annual = None
    if legacy:
        annual = {}
        for scenario, rate in (("legacy median fetches per outlet-day", legacy["per_outlet_day_median"]),
                               ("legacy maximum fetches per outlet-day", legacy["per_outlet_day_max"])):
            for outlets_count in legacy["outlet_counts"]:
                fetches_year = rate * outlets_count * 365
                for name in ("LOW", "CENTRAL", "UPPER"):
                    annual[f"{scenario} x {outlets_count} outlets x 365 days / {name}"] = {
                        "fetches_per_year": round(fetches_year), "label": ASSUMED,
                        "tib_per_year": round(fetches_year * scenarios[name]["all_layers_bytes_per_fetch"] / TIB, 3)}
    comparison = {}
    if target_free_bytes is not None:
        comparison["interim_target_free_bytes_stated"] = {"value": target_free_bytes, "label": "STATED_BY_OPERATOR_OR_READINESS"}
        comparison["canary_footprint_share_of_interim_free"] = {"value": round(preserved_object_bytes / target_free_bytes, 8), "label": DERIVED}
    if new_filesystem_bytes is not None:
        comparison["planned_filesystem_bytes_stated"] = {"value": new_filesystem_bytes, "label": "STATED_BY_OPERATOR"}
        if annual:
            comparison["years_to_fill_planned_filesystem"] = {
                key: (round(new_filesystem_bytes / (value["tib_per_year"] * TIB), 1) if value["tib_per_year"] else None) for key, value in annual.items()}
    dominant = max(("preserved raw packs", preserved_object_bytes), ("extraction layer", layers), ("workspace records", workspace_other),
                   ("preservation manifests", preservation_manifest_bytes), key=lambda item: item[1])
    return {"schema": MEASUREMENT_SCHEMA, "run_id": run_id, "groups": groups, "measured": measured, "outlets": outlets, "spread": spread,
            "items_per_channel": dict(sorted(candidates_per_channel.items())), "scenarios": scenarios, "annual_conditional": annual,
            "comparison": comparison, "dominant_component_in_the_canary": {"name": dominant[0], "bytes": dominant[1], "label": MEASURED},
            "limits": ["five outlets and a budget decide the fetch counts: this measures sizes, not a crawl rate",
                       "the sizes are those of the pages these outlets served on this day",
                       "technical storage sizing, not corpus representativeness"],
            "capacity_labels": CAPACITY_LABEL}


# --- verification -------------------------------------------------------------------------------------


@contextmanager
def network_unavailable() -> Iterator[None]:
    """Any attempt to open a connection raises for the duration: replay must not need one."""
    original = socket.socket.connect

    def refuse(self, address):  # noqa: ANN001
        raise OSError("the network is unavailable during replay")

    socket.socket.connect = refuse  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect = original  # type: ignore[assignment]


def verify(
    workspace: core_pipeline.Workspace,
    registry_: Any,
    *,
    run: acquisition.AcquisitionRun,
    preservation_root: Path,
    spool_root: Path | None,
    stored_receipt: Mapping[str, Any],
    rebuilt_receipt: Mapping[str, Any],
    sample_replay: int = 0,
) -> dict[str, Any]:
    """The checks at the end of a canary. Reads; changes nothing. ``sample_replay`` 0 = replay every extraction."""
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str) -> bool:
        checks.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        return ok

    # 1. recovery diagnosis, with the identity tables held against a rebuild from the preserved evidence
    diagnosis = recovery.diagnose(workspace.root, preservation_root, registry_)
    check("recovery_diagnosis", diagnosis["classification"] == recovery.CLEAN, f"{diagnosis['classification']}; identity {diagnosis.get('identity_rebuild', {}).get('status')}")

    # 2. read-back and fixity: every preserved pack opens (masters verified against their manifests) and every body hashes
    states = workspace.ledger().states()
    run_fetches = {r["fetch_id"] for r in D.fetch_records(workspace) if r["run_id"] == run.run_id}
    preserved_ids, bodies, pack_of = set(), 0, {}
    problems = []
    for identifier in D.pack_ids(workspace):
        try:
            held = core_pipeline.open_preserved_pack(preservation_root, identifier)
            for fetch_id, entry in held.entries.items():
                if entry.body_sha256 is not None:
                    bodies += 1
                    if sha256_bytes(held.body(fetch_id)) != entry.body_sha256:
                        problems.append(f"{fetch_id}: body does not hash")
                    preserved_ids.add(fetch_id)
                    pack_of[fetch_id] = identifier
        except (core_pipeline.NotPreserved, preservation.PreservationError, pack.PackError, OSError) as error:
            problems.append(f"{identifier}: {type(error).__name__}")
    check("preservation_readback_and_fixity", not problems and bodies > 0, f"{bodies} bodies read back from the preservation root; {problems or 'all verify'}")

    # 3. RAW_PRESERVED means verified bytes on the target — and the reverse
    claimed = {f for f in run_fetches if states.get(f) == "RAW_PRESERVED"}
    with_body = {f for f in run_fetches if states.get(f) != "FETCH_FAILED"}
    check("raw_preserved_matches_verified_bytes", claimed == preserved_ids & run_fetches == with_body,
          f"{len(claimed)} RAW_PRESERVED, {len(preserved_ids & run_fetches)} with verified preserved bytes, {len(with_body)} expected")

    # 4. replay of the extractions with the network unavailable
    replayed, differing = 0, []
    items = [r for r in D.fetch_records(workspace) if r["run_id"] == run.run_id and r["fetch_kind"] == acquisition.FETCH_KIND_ITEM
             and r["outcome"] == acquisition.OUTCOME_FETCHED and r["response"]["status"] != 304]
    chosen = items if not sample_replay else items[:sample_replay]
    with network_unavailable():
        for record in chosen:
            identifier = pack_of.get(record["fetch_id"])
            if identifier is None:
                differing.append(record["fetch_id"])           # no verified preserved copy to replay from
                continue
            try:
                result = core_pipeline.replay_extraction(workspace, preservation_root=preservation_root, identifier=identifier, fetch_id=record["fetch_id"])
            except (core_pipeline.NotPreserved, preservation.PreservationError, pack.PackError, extraction.ExtractionError, OSError, RuntimeError):
                differing.append(record["fetch_id"])
                continue
            replayed += 1
            if result["status"] != "ALREADY_STORED":
                differing.append(record["fetch_id"])
    check("replay_without_network", replayed > 0 and not differing, f"{replayed} extractions replayed from preserved bytes with the network unavailable; {len(differing)} differ")

    # 5. the receipt, re-derived from evidence, equals the one the run wrote (volatile fields excluded)
    # `operator_authorization` is copied from the frozen baseline by the run, not derived from the evidence.
    volatile = {"started_at", "finished_at", "fetcher_transport_calls", "checkpoints", "status", "operator_authorization"}
    # Every field the stored receipt states must be re-derived exactly. A field a later driver adds to
    # a receipt is not held against a receipt that was written before it existed.
    same = {k: v for k, v in stored_receipt.items() if k not in volatile} == {
        k: v for k, v in rebuilt_receipt.items() if k not in volatile and k in stored_receipt}
    check("receipt_rederived_from_evidence", same, "every count of the stored receipt equals the count derived from the packs, the log, the ledger and the manifests")
    check("receipt_request_count_equals_the_runs_own_counter",
          stored_receipt.get("fetcher_transport_calls") == stored_receipt["requests"]["total"],
          f"{stored_receipt.get('fetcher_transport_calls')} transport calls counted by the fetcher, {stored_receipt['requests']['total']} derived from fetch records")

    # 6. nothing pending
    pending = outage_spool.pending_records(spool_root) if spool_root is not None and spool_root.is_dir() else []
    check("no_pending_objects", not pending and not any(s == "PRESERVATION_PENDING" for f, s in states.items() if f in run_fetches), f"{len(pending)} spooled records")

    # 7. budgets
    budget_ok = stored_receipt["requests"]["item"] <= D.HARD_ITEM_REQUESTS
    check("budget_respected", budget_ok, f"{stored_receipt['requests']['item']} item requests (ceiling {D.HARD_ITEM_REQUESTS}), {stored_receipt['requests']['total']} in all")

    ok = all(c["status"] == "PASS" for c in checks)
    return {"schema": VERIFICATION_SCHEMA, "run_id": run.run_id, "status": "PASS" if ok else "FAIL", "checks": checks}
