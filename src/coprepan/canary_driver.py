"""The staged driver of the first real acquisition canary (decision CPD-0016).

An **orchestration**, not a second pipeline. Everything it does is done by a component that already
exists and is tested: the HTTP fetcher behind the policy gate, discovery, candidate qualification,
the schedule, the pack, :func:`coprepan.core_pipeline.preserve_pack` (with the outage spool),
document identity, extraction, technical admission, recovery. What it adds is the order, the hard
request budgets, the checkpoints between stages and a receipt that can be re-derived from evidence.

```text
A  probe       per outlet: robots evidence and the first selected channel document (no item request)
B  discovery   per outlet: the second selected channel document
C  item fetch  per outlet: due candidates, within the item budget of the outlet and of the run
D  preserve    per outlet: seal, preserve_pack (direct, or spooled when the target is away), drain
E  derive      per outlet: identity, baseline extraction and technical admission — of RAW_PRESERVED input only
```

**Budgets count real requests.** Every transport call is counted — a redirect hop, a robots file, a
request that failed — by the fetcher itself, and the counts are re-derived from the fetch records
when a run is resumed or a receipt is written. A fetch that cannot be finished inside its budget is
not started (it is a recorded refusal); a call that would exceed a budget raises
:class:`BudgetExceeded`, which is an integrity failure of the run, not an outcome.

**Nothing is made up.** An outlet that refuses, a 404, a 429, a bot challenge are evidence and end
that path; the driver never looks for another way in.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import (acquisition, admission, canary, core_pipeline, crawler_identity, discovery, extraction, fetcher as F,
               freeze, http_acquisition, naming, outage_spool, pack, policy, preservation, preservation_target, recovery, registry,
               schedule, storage_contract, storage_roots)
from .canonical import canonical_json, record_json, sha256_bytes, write_bytes_exclusive
from .identity import format_instant
from .storage_roots import CHECKOUT

DRIVER_VERSION = "canary-driver/1"
RECEIPT_SCHEMA = naming.schema_id("canary-receipt", 1)
HARD_ITEM_REQUESTS = 100            # the brief's ceiling; no budget may exceed it
KIND_ORDER = ("rss", "atom", "sitemap", "sitemap_index")
ITEM, OTHER = "item", "other"       # budget groups; "other" is robots files and channel documents
STAGES = ("A_probe", "B_discovery", "C_item_fetch", "D_preserve", "E_derive")
GIB = 1024 ** 3

# Transport limits of the canary. One attempt per call: a retry is the schedule's decision, a day
# later or an hour later, never a loop inside a call. The numbers are choices, not measurements.
CANARY_LIMITS = F.FetchLimits(timeout_seconds=30, max_redirects=3, max_body_bytes=8 * 1024 * 1024, max_attempts=1,
                              backoff_base_seconds=60, backoff_max_seconds=3600)
# Spool bounds for the canary. Chosen limits, not an estimate of anything.
CANARY_SPOOL = outage_spool.SpoolPolicy(min_free_bytes=20 * GIB, max_spool_bytes=10 * GIB)


class BudgetExceeded(RuntimeError):
    """A request would have gone over a budget. A defect of the run, never an outcome."""


class CanaryStopped(RuntimeError):
    """The run stops because a precondition or an integrity check no longer holds."""


@dataclass(frozen=True)
class CanaryBudget:
    """Every limit of the canary. All of them are pinned in the acquisition baseline."""

    outlets: int = 5
    channels_per_outlet: int = 2
    item_requests_total: int = 80
    item_requests_per_outlet: int = 16
    other_requests_per_outlet: int = 8
    discovery_max_depth: int = 2
    discovery_max_documents: int = 3
    discovery_max_candidates: int = 200
    discovery_max_bytes: int = 4 * 1024 * 1024

    def __post_init__(self) -> None:
        for name, value in self.as_record().items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer: {value!r}")
        if self.item_requests_total > HARD_ITEM_REQUESTS:
            raise ValueError(f"the item budget is at most {HARD_ITEM_REQUESTS} requests in total")
        if self.item_requests_per_outlet > self.item_requests_total:
            raise ValueError("an outlet's item budget cannot exceed the run's")

    @property
    def discovery(self) -> discovery.DiscoveryBudget:
        return discovery.DiscoveryBudget(max_depth=self.discovery_max_depth, max_documents=self.discovery_max_documents,
                                         max_candidates=self.discovery_max_candidates, max_bytes=self.discovery_max_bytes)

    @property
    def total_requests_ceiling(self) -> int:
        return self.item_requests_total + self.outlets * self.other_requests_per_outlet

    def as_record(self) -> dict[str, int]:
        return {"outlets": self.outlets, "channels_per_outlet": self.channels_per_outlet,
                "item_requests_total": self.item_requests_total, "item_requests_per_outlet": self.item_requests_per_outlet,
                "other_requests_per_outlet": self.other_requests_per_outlet, "discovery_max_depth": self.discovery_max_depth,
                "discovery_max_documents": self.discovery_max_documents, "discovery_max_candidates": self.discovery_max_candidates,
                "discovery_max_bytes": self.discovery_max_bytes}


# --- what is selected ---------------------------------------------------------------------------------


def select_channels(outlet: Mapping[str, Any], disabled: Sequence[str], limit: int) -> list[str]:
    """The channels a canary reads for an outlet: at most ``limit``, one of each kind first in the
    order ``rss, atom, sitemap, sitemap_index``, in the registry's own order, never a disabled one.
    Deterministic: the same registry gives the same selection.
    """
    usable = [c for c in outlet["channels"] if c["kind"] in KIND_ORDER and c["channel_id"] not in disabled]
    picked: list[str] = []
    for kind in KIND_ORDER:
        for channel in usable:
            if channel["kind"] == kind and channel["channel_id"] not in picked:
                picked.append(channel["channel_id"])
                break
    for channel in usable:                                   # still room: more of the kinds already used
        if channel["channel_id"] not in picked:
            picked.append(channel["channel_id"])
    return picked[:limit]


def driver_pin(budget: CanaryBudget, registry_: registry.Registry, outlet_ids: Sequence[str], disabled: Sequence[str]) -> dict[str, Any]:
    """What the acquisition baseline pins about the driver: its version, budgets, limits, stages,
    the outlets and the channels it would read. Nothing volatile, no location.
    """
    return {
        "driver": DRIVER_VERSION, "stages": list(STAGES), "budget": budget.as_record(),
        "fetch_limits": {name: getattr(CANARY_LIMITS, name) for name in ("timeout_seconds", "max_redirects", "max_body_bytes",
                                                                         "max_attempts", "backoff_base_seconds", "backoff_max_seconds")},
        "spool_policy": {"min_free_bytes": CANARY_SPOOL.min_free_bytes, "max_spool_bytes": CANARY_SPOOL.max_spool_bytes},
        "outlets": {outlet_id: select_channels(registry_.resolve(outlet_id), disabled, budget.channels_per_outlet)
                    for outlet_id in sorted(outlet_ids)},
        "channel_selection": "one channel of each kind in the order rss, atom, sitemap, sitemap_index, then more of those kinds; "
                             "registry order; never a disabled channel",
        "extractor": extraction.BASELINE.stage_version, "extractor_lifecycle": extraction.BASELINE.lifecycle,
        "admission_ruleset": admission.RULESET, "hard_item_request_ceiling": HARD_ITEM_REQUESTS,
    }


def canary_pin(budget: CanaryBudget, registry_: registry.Registry, outlet_ids: Sequence[str], disabled: Sequence[str],
               preservation_root: Path) -> dict[str, Any]:
    """The ``canary`` block of the acquisition baseline: the driver, the five outlets as registered
    (digest of each record, URL rules), the storage contract and the identity of the preservation
    target. **No location of any disk enters it**: a root is a machine's configuration, the target's
    identity is its marker.
    """
    marker = preservation_target.read_target(preservation_root)
    if marker is None:
        raise CanaryStopped("the preservation target has no identity")
    return {
        "driver": driver_pin(budget, registry_, outlet_ids, disabled),
        "outlets": {outlet_id: {"record_sha256": sha256_bytes(canonical_json(registry_.resolve(outlet_id))),
                                "url_rules": registry_.resolve(outlet_id)["url_rules"]} for outlet_id in sorted(outlet_ids)},
        "storage_contract_sha256": storage_contract.read_pin()["bundle_sha256"],
        "storage_target": {"target_id": marker["target_id"], "marker_sha256": sha256_bytes(canonical_json(marker))},
        "schemas": freeze.schema_ids(),
    }


# --- the budgeted fetcher -----------------------------------------------------------------------------


def request_group(fetch_kind: str) -> str:
    return ITEM if fetch_kind == acquisition.FETCH_KIND_ITEM else OTHER


class BudgetedFetcher(F.HttpFetcher):
    """The ordinary fetcher with every transport call counted against the canary's budgets.

    A fetch is started only when a whole fetch (the largest redirect chain the limits allow) fits
    into what is left; otherwise it is refused, with the reason on record. A call that would still
    go over raises :class:`BudgetExceeded`.
    """

    def __init__(self, *, budget: CanaryBudget, used: Mapping[tuple[str, str], int] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.budget = budget
        self.used: Counter[tuple[str, str]] = Counter(used or {})
        self._context: tuple[str | None, str | None] = (None, None)

    # -- accounting ----------------------------------------------------------------------------------
    def used_total(self, group: str | None = None) -> int:
        return sum(count for (_, g), count in self.used.items() if group in (None, g))

    def remaining(self, outlet_id: str, group: str) -> int:
        per = self.budget.item_requests_per_outlet if group == ITEM else self.budget.other_requests_per_outlet
        cap = per - self.used[(outlet_id, group)]
        if group == ITEM:
            cap = min(cap, self.budget.item_requests_total - self.used_total(ITEM))
        else:
            cap = min(cap, self.budget.total_requests_ceiling - self.used_total())
        return cap

    @property
    def headroom(self) -> int:
        return self.limits.max_redirects + 1                # one attempt, as long a chain as the limits allow

    # -- the guarded entry points --------------------------------------------------------------------
    def fetch(self, request: F.FetchRequest, *, planned_at: datetime | None = None) -> F.FetchOutcome:
        group = request_group(request.fetch_kind)
        if self.remaining(request.outlet_id, group) < self.headroom:
            planned_at = planned_at or self.clock()
            decision = policy.PolicyDecision(policy.DENY, ("canary_budget_exhausted",), self.gate.policy["policy_version"],
                                             {"budget_group": group, "remaining": self.remaining(request.outlet_id, group)})
            return F.FetchOutcome(request, F.request_id(request, planned_at), F.FINAL_DENIED, decision)
        previous, self._context = self._context, (request.outlet_id, group)
        try:
            return super().fetch(request, planned_at=planned_at)
        finally:
            self._context = previous

    def robots_evidence(self, outlet_id: str, origin: str):
        if (outlet_id, origin) not in self._robots and self.remaining(outlet_id, OTHER) < self.headroom:
            return F.robots.RobotsEvidence(F.robots.EVIDENCE_NOT_CONSULTED, detail="canary_budget_exhausted")
        previous, self._context = self._context, (outlet_id, OTHER)
        try:
            return super().robots_evidence(outlet_id, origin)
        finally:
            self._context = previous

    def _request(self, url: str, extra: Sequence[tuple[str, str]] = ()):
        outlet_id, group = self._context
        if outlet_id is None or group is None:
            raise BudgetExceeded("a transport call outside any budgeted context")
        if self.remaining(outlet_id, group) < 1:
            raise BudgetExceeded(f"{outlet_id}: the {group} budget is spent")
        self.used[(outlet_id, group)] += 1
        return super()._request(url, extra)


# --- evidence-derived accounting ----------------------------------------------------------------------


def pack_ids(workspace: core_pipeline.Workspace) -> list[str]:
    """Every pack of the workspace, open or sealed."""
    found = set()
    if workspace.packs.is_dir():
        for path in workspace.packs.iterdir():
            name = path.name
            for suffix in (".warc.gz.open", ".warc.gz"):
                if name.endswith(suffix) and pack.is_pack_id(name[: -len(suffix)]):
                    found.add(name[: -len(suffix)])
    return sorted(found)


def fetch_records(workspace: core_pipeline.Workspace) -> list[dict[str, Any]]:
    """Every fetch record in the workspace's packs, read from the packs themselves."""
    records = []
    for identifier in pack_ids(workspace):
        sealed = workspace.packs / f"{identifier}.warc.gz"
        path = sealed if sealed.exists() else workspace.packs / f"{identifier}.warc.gz.open"
        for entry in pack.scan(path, identifier):
            records.append(pack.read_fetch_record(path, entry))
    return records


def transport_calls(record: Mapping[str, Any]) -> int:
    """The real requests behind one fetch record: the first request plus one per redirect followed."""
    return 1 + len(record["response"]["redirect_chain"])


def tally_from_evidence(workspace: core_pipeline.Workspace, run_id: str | None = None) -> Counter[tuple[str, str]]:
    """``{(outlet, group): real requests}`` re-derived from the fetch records (all runs, or one)."""
    used: Counter[tuple[str, str]] = Counter()
    for record in fetch_records(workspace):
        if run_id is None or record["run_id"] == run_id:
            used[(record["outlet_id"], request_group(record["fetch_kind"]))] += transport_calls(record)
    return used


# --- the run ------------------------------------------------------------------------------------------


@dataclass
class OutletResult:
    outlet_id: str
    channels: list[str]
    stages: dict[str, Any] = field(default_factory=dict)
    stopped: str | None = None


def _checkpoint(workspace: core_pipeline.Workspace, label: str, checkpoints: list[dict[str, Any]]) -> None:
    """Recovery diagnosis between stages: continue on CLEAN or resumable; repair what repair supports; stop on damage."""
    diagnosis = recovery.diagnose(workspace.root)
    if diagnosis["classification"] == recovery.NEEDS_REPAIR:
        recovery.repair(workspace.root)
        diagnosis = recovery.diagnose(workspace.root)
    checkpoints.append({"after": label, "classification": diagnosis["classification"]})
    if diagnosis["classification"] in (recovery.DAMAGED, recovery.NEEDS_REPAIR):
        raise CanaryStopped(f"after {label}: the workspace is {diagnosis['classification']}")


def run_canary(
    workspace: core_pipeline.Workspace,
    registry_: registry.Registry,
    run: acquisition.AcquisitionRun,
    *,
    outlet_ids: Sequence[str],
    fetcher: BudgetedFetcher,
    schedule_policy: schedule.SchedulePolicy,
    clock: Callable[[], datetime],
    preservation_root: Callable[[], Path],
    spool_root: Callable[[], Path] | None,
    spool_policy: outage_spool.SpoolPolicy | None,
    disabled_channels: Sequence[str] = (),
    extractor: extraction.Extractor = extraction.BASELINE,
) -> dict[str, Any]:
    """Run the stages for the given outlets and return what happened. Resumable: stages whose work is
    already on record for this run are not repeated, and the budgets are those of the evidence.
    """
    budget = fetcher.budget
    if len(set(outlet_ids)) != budget.outlets or any(o not in run.outlet_ids for o in outlet_ids):
        raise CanaryStopped(f"the canary is exactly {budget.outlets} registered outlets of its run")
    for outlet_id in outlet_ids:
        registry_.resolve(outlet_id)                        # registered, or a refusal
    results = {o: OutletResult(o, select_channels(registry_.resolve(o), disabled_channels, budget.channels_per_outlet)) for o in outlet_ids}
    checkpoints: list[dict[str, Any]] = []
    packs_of: dict[str, set[str]] = {o: set() for o in outlet_ids}
    request_rows_before = http_acquisition.request_rows(workspace)

    def channel_documents_done(outlet_id: str, channel_id: str) -> bool:
        return any(row["event"] == http_acquisition.EVENT_FINISHED and row["run_id"] == run.run_id and row["fetch_kind"] == "channel_document"
                   and row["url"] == _channel_url(registry_, outlet_id, channel_id) for row in http_acquisition.request_rows(workspace))

    def acquire(outlet_id: str, channels: Sequence[str], items: int) -> dict[str, Any]:
        summary = http_acquisition.run_http_acquisition(
            workspace, registry_, run, outlet_id, fetcher=fetcher, channel_ids=list(channels), budget=budget.discovery,
            max_item_fetches=items, schedule_policy=schedule_policy, clock=clock)
        packs_of[outlet_id].update(summary["open_pack_ids"])
        return summary

    # A and B go over all outlets before C starts: the first contact with every outlet is the smallest one.
    for stage, index in (("A_probe", 0), ("B_discovery", 1)):
        for outlet_id in outlet_ids:
            result = results[outlet_id]
            if index >= len(result.channels):
                result.stages[stage] = "no channel selected"
                continue
            channel_id = result.channels[index]
            if channel_documents_done(outlet_id, channel_id):
                result.stages[stage] = "already on record"
                continue
            result.stages[stage] = acquire(outlet_id, [channel_id], 0)
        _checkpoint(workspace, stage, checkpoints)

    for outlet_id in outlet_ids:                            # C, D, E per outlet, with a checkpoint after each
        result = results[outlet_id]
        result.stages["C_item_fetch"] = acquire(outlet_id, [], budget.item_requests_per_outlet)
        _checkpoint(workspace, f"C_item_fetch:{outlet_id}", checkpoints)
        result.stages["D_preserve"] = _preserve(workspace, _outlet_packs(workspace, outlet_id),
                                                preservation_root, spool_root, spool_policy, clock)
        result.stages["E_derive"] = _derive(workspace, registry_, preservation_root, result.stages["D_preserve"],
                                            extractor, clock)
        _checkpoint(workspace, f"E_derive:{outlet_id}", checkpoints)

    drained = (core_pipeline.drain_spooled_packs(workspace, spool_root=spool_root(), preservation_root=preservation_root, now=clock())
               if spool_root is not None and _spool_pending(spool_root) else {"drained": [], "packs_preserved": [], "packs_pending": []})
    return {"outlets": {o: {"channels": r.channels, "stages": r.stages, "stopped": r.stopped} for o, r in results.items()},
            "checkpoints": checkpoints, "drain": drained, "request_rows_before": len(request_rows_before)}


def _channel_url(registry_: registry.Registry, outlet_id: str, channel_id: str) -> str:
    for channel in registry_.resolve(outlet_id)["channels"]:
        if channel["channel_id"] == channel_id:
            return channel["url_history"][-1]["url"]
    raise CanaryStopped(f"{channel_id} is not a channel of {outlet_id}")


def _outlet_packs(workspace: core_pipeline.Workspace, outlet_id: str) -> list[str]:
    return [identifier for identifier in pack_ids(workspace) if pack.pack_outlet(identifier) == outlet_id]


def _spool_pending(spool_root: Callable[[], Path]) -> bool:
    try:
        return bool(outage_spool.pending_records(spool_root()))
    except storage_roots.StorageRefusal:
        return True


def _preserve(workspace, identifiers, preservation_root, spool_root, spool_policy, clock) -> dict[str, Any]:
    """Stage D. Each pack is preserved directly, or kept pending (spool or workspace) when the target is away."""
    out: dict[str, Any] = {}
    for identifier in identifiers:
        result = core_pipeline.preserve_pack(workspace, identifier, preservation_root=preservation_root, now=clock(),
                                             spool_root=spool_root, spool_policy=spool_policy)
        out[identifier] = {"state": result.state, "route": result.route, "pending_location": result.pending_location, "reason": result.reason}
    return out


def _derive(workspace, registry_, preservation_root, preserved: Mapping[str, Any], extractor, clock) -> dict[str, Any]:
    """Stage E, for RAW_PRESERVED packs only. A pack that is only pending is not read."""
    out: dict[str, Any] = {}
    for identifier, state in preserved.items():
        if state["state"] != preservation.STATE_PRESERVED:
            out[identifier] = {"skipped": "not RAW_PRESERVED: " + str(state["state"])}
            continue
        results = core_pipeline.identify_and_extract(workspace, registry_, preservation_root=preservation_root(), identifier=identifier,
                                                     extractor=extractor, now=clock())
        labels = admission.label_pack(workspace, preservation_root=preservation_root(), identifier=identifier, results=results,
                                      extractor=extractor, labelled_at=format_instant(clock()))
        out[identifier] = {"documents": sum(1 for r in results if r.get("identity") == "assigned"),
                           "versions": sum(1 for r in results if r.get("document_version_id")),
                           "extracted": sum(1 for r in results if r.get("extraction_outcome") == "EXTRACTED"),
                           "labels": Counter(label["technical_status"] for label in labels)}
        out[identifier]["labels"] = dict(out[identifier]["labels"])
    return out


# --- the receipt --------------------------------------------------------------------------------------


def build_receipt(
    workspace: core_pipeline.Workspace,
    *,
    run: acquisition.AcquisitionRun,
    commit: str,
    baseline_id: str,
    policy_record: Mapping[str, Any],
    schedule_policy: schedule.SchedulePolicy,
    identity: crawler_identity.CrawlerIdentity,
    storage_contract_sha256: str,
    outlet_ids: Sequence[str],
    channels: Mapping[str, Sequence[str]],
    preservation_root: Path | None,
    spool_root: Path | None,
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    """The run receipt, every count **re-derived from evidence**: the fetch records of the packs, the
    request log, the ledger, the preservation manifests and the spool. No in-memory counter is read.
    """
    records = [r for r in fetch_records(workspace) if r["run_id"] == run.run_id]
    rows = [row for row in http_acquisition.request_rows(workspace) if row["run_id"] == run.run_id and row["event"] == http_acquisition.EVENT_FINISHED]
    ledger = workspace.ledger()
    requests_by_outlet: dict[str, dict[str, int]] = {o: {ITEM: 0, OTHER: 0} for o in outlet_ids}
    statuses: Counter[str] = Counter()
    for record in records:
        requests_by_outlet[record["outlet_id"]][request_group(record["fetch_kind"])] += transport_calls(record)
        statuses[str(record["response"]["status"]) if record["outcome"] == acquisition.OUTCOME_FETCHED else f"failed:{record['failure_reason']}"] += 1
    refused = Counter(f"{row['final']}:{(row['policy_reasons'] or ['unknown'])[0]}" for row in rows if row["final"] in (F.FINAL_DENIED, F.FINAL_DEFERRED))
    fetch_ids = {r["fetch_id"] for r in records}
    states = {fetch_id: state for fetch_id, state in ledger.states().items() if fetch_id in fetch_ids}
    pending = []
    if spool_root is not None and spool_root.is_dir():
        pending = [{"area": r.get("area"), "object_id": r["object_id"]} for r in outage_spool.pending_records(spool_root)]
    preserved_bytes = 0
    if preservation_root is not None:
        for identifier in pack_ids(workspace):
            for area in (core_pipeline.AREA_PACKS, core_pipeline.AREA_INDEXES):
                held = preservation.read_manifest(preservation_root, area, identifier)
                preserved_bytes += held["size_bytes"] if held and "size_bytes" in held else 0
    candidates = discoveries = 0
    tables = http_acquisition.discovery_tables(workspace)
    candidates = len(tables.candidates)
    discoveries = sum(1 for r in records if r["fetch_kind"] == acquisition.FETCH_KIND_CHANNEL_DOCUMENT)
    items = [r for r in records if r["fetch_kind"] == acquisition.FETCH_KIND_ITEM]
    receipt = {
        "schema": RECEIPT_SCHEMA, "driver": DRIVER_VERSION, "run_id": run.run_id, "commit": commit, "baseline_id": baseline_id,
        "policy_version": policy_record["policy_version"], "schedule_policy_version": schedule_policy.version,
        "crawler_identity_sha256": identity.sha256, "user_agent": identity.user_agent, "storage_contract_sha256": storage_contract_sha256,
        "outlets": sorted(outlet_ids), "channels": {o: list(c) for o, c in sorted(channels.items())},
        "started_at": started_at, "finished_at": finished_at,
        "requests": {"total": sum(sum(v.values()) for v in requests_by_outlet.values()),
                     "item": sum(v[ITEM] for v in requests_by_outlet.values()), "other": sum(v[OTHER] for v in requests_by_outlet.values()),
                     "by_outlet": requests_by_outlet},
        "response_classes": dict(sorted(statuses.items())),
        "refused": dict(sorted(refused.items())),
        "counts": {"discovery_documents_fetched": discoveries, "candidates": candidates, "fetch_records": len(records),
                   "items_fetched": sum(1 for r in items if r["outcome"] == acquisition.OUTCOME_FETCHED),
                   "failed": sum(1 for r in records if r["outcome"] == acquisition.OUTCOME_FETCH_FAILED),
                   "refused": sum(refused.values()),
                   "preserved": sum(1 for s in states.values() if s == "RAW_PRESERVED"),
                   "pending": sum(1 for s in states.values() if s == "PRESERVATION_PENDING"),
                   "spooled_objects_pending": len(pending)},
        "bytes": {"received_bodies": sum(r["body_size_bytes"] for r in records if isinstance(r["body_size_bytes"], int)),
                  "preserved_objects": preserved_bytes},
        "packs": pack_ids(workspace),
    }
    return receipt


# --- the command line ---------------------------------------------------------------------------------


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=CHECKOUT, capture_output=True, text=True, check=True).stdout.strip()


def verify_checkout(pinned_commit: str, allowed_prefixes: Sequence[str] = ("docs/canary/", "docs/agent-runs/")) -> None:
    """The working tree is clean, and HEAD is the pinned commit or only evidence files beyond it."""
    if _git("status", "--porcelain"):
        raise CanaryStopped("the working tree is not clean")
    head = _git("rev-parse", "HEAD")
    if head != pinned_commit:
        changed = _git("diff", "--name-only", pinned_commit, head).splitlines()
        if any(not name.startswith(tuple(allowed_prefixes)) for name in changed):
            raise CanaryStopped(f"HEAD differs from the pinned commit beyond evidence files: {changed}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The staged driver of the first real canary. `run` makes real requests.")
    commands = parser.add_subparsers(dest="command", required=True)
    pin = commands.add_parser("pin", help="print what the baseline pins about the driver (no request)")
    pin.add_argument("--outlet", action="append", required=True)
    base = commands.add_parser("baseline", help="build the canary baseline manifest of this checkout (no request)")
    base.add_argument("--outlet", action="append", required=True)
    base.add_argument("--commit", required=True)
    base.add_argument("--operator", required=True)
    base.add_argument("--tests-passed", type=int, required=True)
    base.add_argument("--required-free-bytes", type=int, required=True)
    base.add_argument("--out", type=Path, required=True)
    frozen = commands.add_parser("freeze", help="the operator's act: freeze a baseline by stating its digest (no request)")
    frozen.add_argument("--manifest", type=Path, required=True)
    frozen.add_argument("--operator", required=True)
    frozen.add_argument("--confirm", required=True, help="the manifest's digest")
    frozen.add_argument("--out", type=Path, required=True)
    run_ = commands.add_parser("run", help="preflight, then the canary")
    run_.add_argument("--outlet", action="append", required=True)
    run_.add_argument("--pinned-commit", required=True)
    run_.add_argument("--approved-baseline", type=Path, required=True)
    run_.add_argument("--tests-passed", type=int, required=True)
    run_.add_argument("--required-free-bytes", type=int, required=True)
    run_.add_argument("--receipt-dir", type=Path, required=True, help="where the run receipt is written (once)")
    arguments = parser.parse_args(argv)

    environment = storage_roots.workstation_environment()
    registered = registry.load_registry(CHECKOUT / "config" / "outlet_registry.json")
    acquisition_policy = policy.load_policy()
    budget = CanaryBudget()
    if arguments.command == "pin":
        print(json.dumps(driver_pin(budget, registered, arguments.outlet, acquisition_policy["disabled_channels"]), indent=2, sort_keys=True))
        return 0

    if arguments.command == "baseline":
        root = storage_roots.resolve_root("PRESERVATION", env=environment)
        readiness = preservation_target.check_readiness(root, required_free_bytes=arguments.required_free_bytes, now=datetime.now(timezone.utc))
        manifest = freeze.build_manifest(
            code_commit=arguments.commit, created_at=datetime.now(timezone.utc), operator=arguments.operator,
            test_baseline={"suite": "python -m pytest", "passed": arguments.tests_passed}, storage_target=readiness,
            scope=freeze.SCOPE_CANARY, canary=canary_pin(budget, registered, arguments.outlet, acquisition_policy["disabled_channels"], root))
        write_bytes_exclusive(arguments.out, record_json(manifest))
        print(json.dumps({"state": manifest["state"], "blocking": manifest["blocking"], "manifest_sha256": manifest["manifest_sha256"]}, indent=2))
        return 0 if manifest["state"] == freeze.READY_TO_FREEZE else 1
    if arguments.command == "freeze":
        frozen_manifest = freeze.freeze(json.loads(arguments.manifest.read_text(encoding="utf-8")), operator=arguments.operator,
                                        confirmed_at=datetime.now(timezone.utc), confirmation=arguments.confirm)
        write_bytes_exclusive(arguments.out, record_json(frozen_manifest))
        print(json.dumps({"state": frozen_manifest["state"], "manifest_sha256": frozen_manifest["manifest_sha256"]}, indent=2))
        return 0

    # --- preconditions: all of them, before the first request ---
    roles_now = storage_roots.resolve_configured_roles(env=environment)
    verify_checkout(arguments.pinned_commit)
    baseline = json.loads(arguments.approved_baseline.read_text(encoding="utf-8"))
    if baseline.get("state") != freeze.FROZEN or not freeze.verify_manifest(baseline):
        raise CanaryStopped("the approved baseline is not a frozen manifest that verifies")
    report = canary.preflight(outlet_ids=arguments.outlet, tests_passed=arguments.tests_passed, tests_commit=arguments.pinned_commit,
                              code_commit=arguments.pinned_commit, approved_baseline=baseline,
                              required_free_bytes=arguments.required_free_bytes, now=datetime.now(timezone.utc), environment=environment)
    if report["status"] != canary.READY:
        print(json.dumps(report, indent=2))
        raise CanaryStopped("the preflight is not READY: no request is made")
    if baseline.get("scope") != freeze.SCOPE_CANARY or baseline.get("canary") != canary_pin(
            budget, registered, arguments.outlet, acquisition_policy["disabled_channels"], roles_now["PRESERVATION"]):
        raise CanaryStopped("the driver, its budgets, the outlets or the storage identity differ from what the baseline pins")

    identity = crawler_identity.load_identity()
    schedule_policy = schedule.load_schedule_policy()
    roles = roles_now
    workspace = core_pipeline.Workspace(roles["RUNTIME"])
    clock = lambda: datetime.now(timezone.utc)  # noqa: E731
    started = clock()
    run = http_acquisition.http_fetch_run(started, arguments.outlet, {"driver": DRIVER_VERSION, "baseline_id": baseline["manifest_sha256"],
                                                                      "budget": budget.as_record(), "pinned_commit": arguments.pinned_commit}, identity)
    gate = policy.PolicyGate(acquisition_policy, registered, identity)
    used = tally_from_evidence(workspace, run.run_id)
    fetcher = BudgetedFetcher(budget=budget, used=used, identity=identity, gate=gate, limits=CANARY_LIMITS, clock=clock, sleep=time.sleep)
    resolve = lambda role: (lambda: storage_roots.resolve_root(role, env=environment))  # noqa: E731
    outcome = run_canary(workspace, registered, run, outlet_ids=arguments.outlet, fetcher=fetcher, schedule_policy=schedule_policy, clock=clock,
                         preservation_root=resolve("PRESERVATION"), spool_root=resolve("SPOOL"), spool_policy=CANARY_SPOOL,
                         disabled_channels=acquisition_policy["disabled_channels"])
    receipt = build_receipt(
        workspace, run=run, commit=arguments.pinned_commit, baseline_id=baseline["manifest_sha256"], policy_record=acquisition_policy,
        schedule_policy=schedule_policy, identity=identity, storage_contract_sha256=baseline["canary"]["storage_contract_sha256"],
        outlet_ids=arguments.outlet, channels={o: r["channels"] for o, r in outcome["outlets"].items()},
        preservation_root=roles["PRESERVATION"], spool_root=roles["SPOOL"], started_at=format_instant(started), finished_at=format_instant(clock()))
    receipt["fetcher_transport_calls"] = fetcher.transport_calls
    receipt["checkpoints"] = outcome["checkpoints"]
    complete = receipt["counts"]["pending"] == 0 and receipt["counts"]["spooled_objects_pending"] == 0
    if complete:
        acquisition.close_run(workspace.root, run, finished_at=clock(), status="COMPLETED",
                              counts={"requests": receipt["requests"]["total"], "fetch_records": receipt["counts"]["fetch_records"]},
                              pack_ids=receipt["packs"])
    receipt["status"] = "COMPLETE" if complete else "INCOMPLETE_PENDING"
    arguments.receipt_dir.mkdir(parents=True, exist_ok=True)
    write_bytes_exclusive(arguments.receipt_dir / f"canary-receipt-{run.run_id}.json", record_json(receipt))
    print(json.dumps({"status": receipt["status"], "requests": receipt["requests"]["total"], "counts": receipt["counts"]}, indent=2))
    return 0 if complete else 1


if __name__ == "__main__":
    sys.exit(main())
