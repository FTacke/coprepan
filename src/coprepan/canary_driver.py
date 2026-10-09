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

from . import (access_control, acquisition, admission, canary, candidate_filter, core_pipeline, crawler_identity, discovery, extraction, fetcher as F,
               freeze, http_acquisition, naming, outage_spool, pack, policy, preservation, preservation_target, recovery, registry,
               schedule, storage_contract, storage_roots)
from .canonical import canonical_json, record_json, sha256_bytes, write_bytes_exclusive
from .identity import format_instant
from .storage_roots import CHECKOUT

# /2: the policy layers of CPD-0017 in pin, start state and receipt.
# /3 (CPD-0019): requests are counted hop by hop instead of reserving a whole redirect chain per fetch;
#     part of an outlet's robots / channel budget is reserved for the documents a channel names
#     (the second level of a sitemap index); the budget is that of the frozen baseline, not of the
#     workspace; outlet candidate rules are applied; listing channels need an allow rule; holds are
#     re-derived from preserved answers under the current classifier.
DRIVER_VERSION = "canary-driver/3"
RECEIPT_SCHEMA = naming.schema_id("canary-receipt", 1)
HARD_ITEM_REQUESTS = 100            # the brief's ceiling; no budget may exceed it
KIND_ORDER = ("rss", "atom", "sitemap", "sitemap_index", "archive", "section_page")
# An HTML listing lists its navigation too: such a channel is read only for an outlet whose reviewed
# candidate rules say which paths are items (a non-empty `allow_path_patterns`).
LISTING_KINDS = ("archive", "section_page")
# Budget groups. "other" is robots files and the registered channel documents; "expansion" is what a
# channel document names (a sitemap of an index, a next page). Both draw on one per-outlet budget.
ITEM, OTHER, EXPANSION = "item", "other", "expansion"
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
    # Of the `other_requests_per_outlet`, this many are kept for the documents a channel names: robots
    # files and the registered channel documents can never use them up (canary finding F4). It
    # raises no limit: an outlet is still asked at most `other_requests_per_outlet` non-item requests.
    expansion_requests_reserved_per_outlet: int = 3
    discovery_max_depth: int = 2
    discovery_max_documents: int = 4
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
        if self.expansion_requests_reserved_per_outlet > self.other_requests_per_outlet:
            raise ValueError("the reserved part of an outlet's robots / channel budget cannot exceed that budget")

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
                "other_requests_per_outlet": self.other_requests_per_outlet,
                "expansion_requests_reserved_per_outlet": self.expansion_requests_reserved_per_outlet,
                "discovery_max_depth": self.discovery_max_depth,
                "discovery_max_documents": self.discovery_max_documents, "discovery_max_candidates": self.discovery_max_candidates,
                "discovery_max_bytes": self.discovery_max_bytes}


# --- what is selected ---------------------------------------------------------------------------------


def canary_budget(outlets: int) -> CanaryBudget:
    """The budget of a canary of ``outlets`` outlets. Five outlets: the budget of CPD-0016. A wider
    canary (CPD-0019) keeps every per-outlet limit except the item budget, which is what the hard
    ceiling of item requests leaves for each outlet — more outlets, fewer pages of each.
    """
    if outlets == 5:
        return CanaryBudget()
    if not 6 <= outlets <= 15:
        raise CanaryStopped("a canary is five outlets, or six to fifteen")
    per_outlet = min(CanaryBudget().item_requests_per_outlet, (HARD_ITEM_REQUESTS - 4) // outlets)
    return CanaryBudget(outlets=outlets, item_requests_total=per_outlet * outlets, item_requests_per_outlet=per_outlet)


def select_channels(outlet: Mapping[str, Any], disabled: Sequence[str], limit: int,
                    candidate_rules: Mapping[str, Mapping[str, Any]] | None = None) -> list[str]:
    """The channels a canary reads for an outlet: at most ``limit``, one of each kind first in the
    order ``rss, atom, sitemap, sitemap_index, archive, section_page``, in the registry's own order,
    never a disabled one, and a listing channel only for an outlet with an allow rule.
    Deterministic: the same registry and rules give the same selection.
    """
    listing_allowed = bool(((candidate_rules or {}).get(outlet["outlet_id"]) or {}).get("allow_path_patterns"))
    usable = [c for c in outlet["channels"] if c["kind"] in KIND_ORDER and c["channel_id"] not in disabled
              and (c["kind"] not in LISTING_KINDS or listing_allowed)]
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


def driver_pin(budget: CanaryBudget, registry_: registry.Registry, outlet_ids: Sequence[str], disabled: Sequence[str],
               candidate_rules: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """What the acquisition baseline pins about the driver: its version, budgets, limits, stages,
    the outlets and the channels it would read. Nothing volatile, no location.
    """
    return {
        "driver": DRIVER_VERSION, "stages": list(STAGES), "budget": budget.as_record(),
        "fetch_limits": {name: getattr(CANARY_LIMITS, name) for name in ("timeout_seconds", "max_redirects", "max_body_bytes",
                                                                         "max_attempts", "backoff_base_seconds", "backoff_max_seconds")},
        "spool_policy": {"min_free_bytes": CANARY_SPOOL.min_free_bytes, "max_spool_bytes": CANARY_SPOOL.max_spool_bytes},
        "outlets": {outlet_id: select_channels(registry_.resolve(outlet_id), disabled, budget.channels_per_outlet, candidate_rules)
                    for outlet_id in sorted(outlet_ids)},
        "channel_selection": "one channel of each kind in the order rss, atom, sitemap, sitemap_index, archive, section_page, then "
                             "more of those kinds; registry order; never a disabled channel; a listing channel (archive, "
                             "section_page) only for an outlet with an allow rule",
        "expansion_order": discovery.EXPANSION_ORDER,
        "budget_accounting": "per transport call; a redirect hop that no longer fits is not followed; the budget is that of "
                             "the frozen baseline",
        "extractor": extraction.BASELINE.stage_version, "extractor_lifecycle": extraction.BASELINE.lifecycle,
        "admission_ruleset": admission.RULESET, "hard_item_request_ceiling": HARD_ITEM_REQUESTS,
    }


def crawler_page_pin(repository: Path = CHECKOUT) -> dict[str, Any]:
    """The public crawler page as deployed: the latest deployment receipt, and that the page it
    names is byte for byte the page of this checkout. A crawler that says one thing in its
    User-Agent's URL and does another is not started.
    """
    receipts = sorted((repository / "web").glob("DEPLOY_RECEIPT_*.json"))
    if not receipts:
        raise CanaryStopped("no deployment receipt of the public crawler page")
    receipt = json.loads(receipts[-1].read_text(encoding="utf-8"))
    deployed = {entry["path"]: entry["sha256"] for entry in receipt["after"]["files"]}
    page = sha256_bytes((repository / "web" / "coprepan" / "crawler" / "index.html").read_bytes())
    if deployed.get("crawler/index.html") != page:
        raise CanaryStopped("the crawler page of this checkout is not the page the latest deployment receipt records")
    if not all(entry.get("content_equals_source") for entry in receipt["public_check"]["pages"]):
        raise CanaryStopped("the latest deployment receipt does not record a public check that matched")
    return {"receipt": receipts[-1].name, "receipt_sha256": sha256_bytes(receipts[-1].read_bytes()),
            "crawler_page_sha256": page, "site_url": receipt["site_url"], "public_check_utc": receipt["public_check_utc"]}


def canary_pin(budget: CanaryBudget, registry_: registry.Registry, outlet_ids: Sequence[str], disabled: Sequence[str],
               preservation_root: Path, acquisition_policy: Mapping[str, Any], repository: Path = CHECKOUT,
               candidate_rules: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """The ``canary`` block of the acquisition baseline: the driver, the five outlets as registered
    (digest of each record, URL rules), the storage contract, the identity of the preservation
    target, the research-TDM layer of the policy (CPD-0017) and the public crawler page as deployed.
    **No location of any disk enters it**: a root is a machine's configuration, the target's
    identity is its marker.
    """
    marker = preservation_target.read_target(preservation_root)
    if marker is None:
        raise CanaryStopped("the preservation target has no identity")
    return {
        "driver": driver_pin(budget, registry_, outlet_ids, disabled, candidate_rules),
        "research_tdm": policy.research_tdm_pin(acquisition_policy),
        "access_control_classifier": access_control.CLASSIFIER_VERSION,
        "robots_parser": F.robots.PARSER_VERSION,
        "crawler_page": crawler_page_pin(repository),
        "outlets": {outlet_id: {"record_sha256": sha256_bytes(canonical_json(registry_.resolve(outlet_id))),
                                "url_rules": registry_.resolve(outlet_id)["url_rules"]} for outlet_id in sorted(outlet_ids)},
        "storage_contract_sha256": storage_contract.read_pin()["bundle_sha256"],
        "storage_target": {"target_id": marker["target_id"], "marker_sha256": sha256_bytes(canonical_json(marker))},
        "schemas": freeze.schema_ids(),
    }


# --- the budgeted fetcher -----------------------------------------------------------------------------


def request_group(fetch_kind: str, expansion_depth: int = 0) -> str:
    if fetch_kind == acquisition.FETCH_KIND_ITEM:
        return ITEM
    return EXPANSION if fetch_kind == acquisition.FETCH_KIND_CHANNEL_DOCUMENT and expansion_depth > 0 else OTHER


class BudgetedFetcher(F.HttpFetcher):
    """The ordinary fetcher with every transport call counted against the canary's budgets.

    Every transport call is counted when it is made. A fetch is started only while at least one
    request is left in its group, and a redirect is followed only while one is left: a hop that no
    longer fits is not requested, the redirect answer is the recorded response, and the refusal is
    on record (``canary_budget_exhausted``). A call that would still go over raises
    :class:`BudgetExceeded`.
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
        if group == ITEM:
            return min(self.budget.item_requests_per_outlet - self.used[(outlet_id, ITEM)],
                       self.budget.item_requests_total - self.used_total(ITEM))
        # Robots files, channel documents and what they name share one per-outlet budget; the
        # reserved part of it is out of reach for robots files and registered channel documents.
        non_item = self.budget.other_requests_per_outlet - self.used[(outlet_id, OTHER)] - self.used[(outlet_id, EXPANSION)]
        cap = non_item if group == EXPANSION else min(
            non_item, self.budget.other_requests_per_outlet - self.budget.expansion_requests_reserved_per_outlet - self.used[(outlet_id, OTHER)])
        return min(cap, self.budget.total_requests_ceiling - self.used_total())

    def _exhausted(self, group: str) -> policy.PolicyDecision:
        return policy.PolicyDecision(policy.DENY, ("canary_budget_exhausted",), self.gate.policy["policy_version"],
                                     {"budget_group": group, "remaining": 0})

    # -- the guarded entry points --------------------------------------------------------------------
    def fetch(self, request: F.FetchRequest, *, planned_at: datetime | None = None) -> F.FetchOutcome:
        group = request_group(request.fetch_kind, request.expansion_depth)
        if self.remaining(request.outlet_id, group) < 1:
            planned_at = planned_at or self.clock()
            return F.FetchOutcome(request, F.request_id(request, planned_at), F.FINAL_DENIED, self._exhausted(group))
        previous, self._context = self._context, (request.outlet_id, group)
        try:
            return super().fetch(request, planned_at=planned_at)
        finally:
            self._context = previous

    def robots_evidence(self, outlet_id: str, origin: str):
        if (outlet_id, origin) not in self._robots and self.remaining(outlet_id, OTHER) < 1:
            return F.robots.RobotsEvidence(F.robots.EVIDENCE_NOT_CONSULTED, detail="canary_budget_exhausted")
        previous, self._context = self._context, (outlet_id, OTHER)
        try:
            return super().robots_evidence(outlet_id, origin)
        finally:
            self._context = previous

    def _decide(self, request: F.FetchRequest, url: str) -> policy.PolicyDecision:
        # Asked for the first request of a fetch (where one request is known to be left) and for
        # every redirect hop: a hop is a request, and one that does not fit is not made.
        outlet_id, group = self._context
        if outlet_id is not None and group is not None and self.remaining(outlet_id, group) < 1:
            return self._exhausted(group)
        return super()._decide(request, url)

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


def packs_holding(workspace: core_pipeline.Workspace, fetch_ids: set[str]) -> list[str]:
    """The packs of the workspace that hold at least one of these fetch records."""
    held = []
    for identifier in pack_ids(workspace):
        sealed = workspace.packs / f"{identifier}.warc.gz"
        path = sealed if sealed.exists() else workspace.packs / f"{identifier}.warc.gz.open"
        if any(entry.fetch_id in fetch_ids for entry in pack.scan(path, identifier)):
            held.append(identifier)
    return held


def transport_calls(record: Mapping[str, Any]) -> int:
    """The real requests behind one fetch record: the first request plus one per redirect followed."""
    return 1 + len(record["response"]["redirect_chain"])


def access_holds_from_evidence(workspace: core_pipeline.Workspace, run_id: str | None = None, *,
                               reclassify: bool = False) -> dict[str, str]:
    """``{origin: access control}`` seen in the workspace's fetch records (all runs, or one): a run
    that is resumed or started again asks nothing more of an origin that has refused this crawler,
    until a person has looked at it.

    ``reclassify``: also hold an origin whose *stored answer* the current classifier recognises as
    an access control although the classifier of its day did not (canary finding F2). The stored
    record is not changed; this reads the answer again, from the pack, and says so by the class.
    """
    holds: dict[str, str] = {}
    for identifier in pack_ids(workspace):
        sealed = workspace.packs / f"{identifier}.warc.gz"
        path = sealed if sealed.exists() else workspace.packs / f"{identifier}.warc.gz.open"
        for entry in pack.scan(path, identifier):
            record = pack.read_fetch_record(path, entry)
            if run_id is not None and record["run_id"] != run_id:
                continue
            observed = record["policy"]["access_class_observed"]
            if reclassify and observed not in access_control.ORIGIN_HOLD and record["outcome"] == acquisition.OUTCOME_FETCHED:
                headers = [(header[0], header[1]) for header in record["response"]["headers"]]
                observed = access_control.classify_response(record["response"]["status"], headers, pack.read_body(path, entry))
            if observed in access_control.ORIGIN_HOLD:
                origin = policy._origin(record["response"]["final_url"])
                if origin:
                    holds.setdefault(origin, observed)
    return holds


def policy_layer_statistics(records: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]],
                            outlet_ids: Sequence[str]) -> dict[str, Any]:
    """What the three layers of CPD-0017 did in a run, from fetch records and the request log only."""
    def layers(row):
        return row.get("policy_layers") or {}

    def answered(record):
        return record["outcome"] == acquisition.OUTCOME_FETCHED and 200 <= record["response"]["status"] < 300

    def reserved(record):
        headers = record["response"]["headers"] if record["outcome"] == acquisition.OUTCOME_FETCHED else []
        return access_control.tdm_reservation([(h[0], h[1]) for h in headers]) is not None

    per_outlet: dict[str, Any] = {}
    for outlet_id in sorted(outlet_ids):
        own = [r for r in records if r["outlet_id"] == outlet_id]
        own_rows = [row for row in rows if _row_outlet(row, records) == outlet_id]
        robots_files = [r for r in own if r["fetch_kind"] == acquisition.FETCH_KIND_ROBOTS]
        overridden = [r for r in own if r["policy"]["policy_decision"] == policy.ALLOW_RESEARCH_OVERRIDE]
        per_outlet[outlet_id] = {
            "robots_files": [{"outcome": r["outcome"], "status": r["response"]["status"], "body_sha256": r["body_sha256"],
                              "access_class_observed": r["policy"]["access_class_observed"]} for r in robots_files],
            "robots_evidence": dict(sorted(Counter(str(layers(row).get("robots_evidence")) for row in own_rows).items())),
            "requests_allowed_by_robots": sum(1 for r in own if r["policy"]["robots_decision"] == "allowed"),
            "requests_under_research_override": len(overridden),
            "answered_2xx_under_research_override": sum(1 for r in overridden if answered(r)),
            "access_classes_observed": dict(sorted(Counter(r["policy"]["access_class_observed"] for r in own).items())),
            # A general machine-readable reservation, as a response header. Recorded; it does not
            # decide anything for scientific research (CPD-0017 §5).
            "general_tdm_reservation_observed": sum(1 for r in own if reserved(r)),
        }
    decisions = Counter(str(layers(row).get("acquisition_decision")) for row in rows)
    holds = Counter(str(layers(row).get("hold_class")) for row in rows if layers(row).get("hold_class"))
    return {
        "semantics": policy.ROBOTS_DECISION_SEMANTICS,
        "acquisition_decisions": dict(sorted(decisions.items())),
        "holds": dict(sorted(holds.items())),
        "outlets_with_applicable_disallow": sorted(o for o, s in per_outlet.items() if s["robots_evidence"].get(policy.ROBOTS_DISALLOW_OBSERVED)),
        "outlets_with_access_control": sorted(o for o, s in per_outlet.items()
                                              if set(s["access_classes_observed"]) & set(access_control.ACCESS_CONTROLS)),
        "requests_under_research_override": sum(s["requests_under_research_override"] for s in per_outlet.values()),
        "answered_2xx_under_research_override": sum(s["answered_2xx_under_research_override"] for s in per_outlet.values()),
        "requests_stopped_by_access_control": holds.get(policy.ACCESS_CONTROL_OBSERVED, 0),
        "direct_opt_outs": holds.get(policy.DIRECT_OPT_OUT, 0), "legal_review_holds": holds.get(policy.LEGAL_REVIEW_HOLD, 0),
        "by_outlet": per_outlet,
    }


def _row_outlet(row: Mapping[str, Any], records: Sequence[Mapping[str, Any]]) -> str | None:
    """The outlet of a FINISHED row: that of its PLANNED twin, else that of its fetch records."""
    if row.get("_outlet_id"):
        return row["_outlet_id"]
    return next((record["outlet_id"] for record in records if record["fetch_id"] in (row.get("fetch_ids") or ())), None)


def expansion_depths(workspace: core_pipeline.Workspace) -> dict[str, int]:
    """``{request_id: expansion depth}`` as the request log planned it. A request planned before the
    depth was recorded (driver ``/2``) has none and counts as depth 0.
    """
    return {row["request_id"]: int(row.get("expansion_depth") or 0) for row in http_acquisition.request_rows(workspace)
            if row["event"] == http_acquisition.EVENT_PLANNED}


def record_group(record: Mapping[str, Any], depths: Mapping[str, int]) -> str:
    """The budget group of a fetch record: its kind, and for a channel document its planned depth."""
    return request_group(record["fetch_kind"], depths.get(record.get("request_id") or "", 0))


def runs_of_baseline(workspace: core_pipeline.Workspace, baseline_id: str) -> set[str]:
    """The runs of the workspace that were started under one frozen baseline, by their run records."""
    found = set()
    runs = workspace.root / "runs"
    for directory in sorted(runs.iterdir()) if runs.is_dir() else []:
        try:
            record = json.loads((directory / "run.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(record, dict) and (record.get("configuration") or {}).get("baseline_id") == baseline_id:
            found.add(record.get("run_id"))
    return found


def tally_from_evidence(workspace: core_pipeline.Workspace, run_id: str | None = None, *,
                        baseline_id: str | None = None) -> Counter[tuple[str, str]]:
    """``{(outlet, group): real requests}`` re-derived from the fetch records — of all runs, of one
    run, or of every run started under one frozen baseline. A canary's budget is the budget of its
    baseline (CPD-0019): a canary that is started again does not get a second one, and a new
    canary, armed and frozen anew, does not inherit what an earlier one spent.
    """
    used: Counter[tuple[str, str]] = Counter()
    depths = expansion_depths(workspace)
    runs = runs_of_baseline(workspace, baseline_id) if baseline_id is not None else None
    for record in fetch_records(workspace):
        if (run_id is None or record["run_id"] == run_id) and (runs is None or record["run_id"] in runs):
            used[(record["outlet_id"], record_group(record, depths))] += transport_calls(record)
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
    candidate_rules: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run the stages for the given outlets and return what happened. Resumable: stages whose work is
    already on record for this run are not repeated, and the budgets are those of the evidence.
    """
    budget = fetcher.budget
    if len(set(outlet_ids)) != budget.outlets or any(o not in run.outlet_ids for o in outlet_ids):
        raise CanaryStopped(f"the canary is exactly {budget.outlets} registered outlets of its run")
    for outlet_id in outlet_ids:
        registry_.resolve(outlet_id)                        # registered, or a refusal
    results = {o: OutletResult(o, select_channels(registry_.resolve(o), disabled_channels, budget.channels_per_outlet, candidate_rules))
               for o in outlet_ids}
    checkpoints: list[dict[str, Any]] = []
    packs_of: dict[str, set[str]] = {o: set() for o in outlet_ids}
    request_rows_before = http_acquisition.request_rows(workspace)

    def channel_documents_done(outlet_id: str, channel_id: str) -> bool:
        return any(row["event"] == http_acquisition.EVENT_FINISHED and row["run_id"] == run.run_id and row["fetch_kind"] == "channel_document"
                   and row["url"] == _channel_url(registry_, outlet_id, channel_id) for row in http_acquisition.request_rows(workspace))

    def acquire(outlet_id: str, channels: Sequence[str], items: int) -> dict[str, Any]:
        summary = http_acquisition.run_http_acquisition(
            workspace, registry_, run, outlet_id, fetcher=fetcher, channel_ids=list(channels), budget=budget.discovery,
            max_item_fetches=items, schedule_policy=schedule_policy, clock=clock, candidate_rules=candidate_rules)
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
    driver_version: str = DRIVER_VERSION,
) -> dict[str, Any]:
    """The run receipt, every count **re-derived from evidence**: the fetch records of the packs, the
    request log, the ledger, the preservation manifests and the spool. No in-memory counter is read.

    A receipt is the receipt of **one run** in a workspace that may hold others: its packs are the
    packs that hold a fetch record of the run, its candidates the candidates first listed in it.
    ``driver_version`` is the driver that made the run (when an old receipt is re-derived).
    """
    records = [r for r in fetch_records(workspace) if r["run_id"] == run.run_id]
    all_rows = [row for row in http_acquisition.request_rows(workspace) if row["run_id"] == run.run_id]
    planned = {row["request_id"]: row["outlet_id"] for row in all_rows if row["event"] == http_acquisition.EVENT_PLANNED}
    rows = [{**row, "_outlet_id": planned.get(row["request_id"])} for row in all_rows if row["event"] == http_acquisition.EVENT_FINISHED]
    ledger = workspace.ledger()
    # "other" is every request that is not an item request, as in every receipt so far; how much of
    # it went to documents a channel named is stated beside it (`expansion_requests`).
    requests_by_outlet: dict[str, dict[str, int]] = {o: {ITEM: 0, OTHER: 0} for o in outlet_ids}
    expansion_by_outlet: dict[str, int] = {o: 0 for o in outlet_ids}
    depths = expansion_depths(workspace)
    statuses: Counter[str] = Counter()
    for record in records:
        group = record_group(record, depths)
        requests_by_outlet[record["outlet_id"]][ITEM if group == ITEM else OTHER] += transport_calls(record)
        if group == EXPANSION:
            expansion_by_outlet[record["outlet_id"]] += transport_calls(record)
        statuses[str(record["response"]["status"]) if record["outcome"] == acquisition.OUTCOME_FETCHED else f"failed:{record['failure_reason']}"] += 1
    refused = Counter(f"{row['final']}:{(row['policy_reasons'] or ['unknown'])[0]}" for row in rows if row["final"] in (F.FINAL_DENIED, F.FINAL_DEFERRED))
    fetch_ids = {r["fetch_id"] for r in records}
    states = {fetch_id: state for fetch_id, state in ledger.states().items() if fetch_id in fetch_ids}
    pending = []
    if spool_root is not None and spool_root.is_dir():
        pending = [{"area": r.get("area"), "object_id": r["object_id"]} for r in outage_spool.pending_records(spool_root)]
    packs_of_run = packs_holding(workspace, fetch_ids)
    preserved_bytes = 0
    if preservation_root is not None:
        for identifier in packs_of_run:
            for area in (core_pipeline.AREA_PACKS, core_pipeline.AREA_INDEXES):
                held = preservation.read_manifest(preservation_root, area, identifier)
                preserved_bytes += held["size_bytes"] if held and "size_bytes" in held else 0
    tables = http_acquisition.discovery_tables(workspace)
    # First listed in this run: by the run of its first event, or, for a candidate a permanent
    # redirect gave rise to, by the run of the request that was redirected.
    moved_here = {(row.get("result") or {}).get("moved_permanently_to") for row in rows} - {None}
    candidates = sum(1 for identifier, row in tables.candidates.items()
                     if (tables.events[row["first_event_id"]]["run_id"] == run.run_id if row.get("first_event_id") in tables.events
                         else identifier in moved_here))
    discoveries = sum(1 for r in records if r["fetch_kind"] == acquisition.FETCH_KIND_CHANNEL_DOCUMENT)
    items = [r for r in records if r["fetch_kind"] == acquisition.FETCH_KIND_ITEM]
    receipt = {
        "schema": RECEIPT_SCHEMA, "driver": driver_version, "run_id": run.run_id, "commit": commit, "baseline_id": baseline_id,
        "policy_version": policy_record["policy_version"], "schedule_policy_version": schedule_policy.version,
        "crawler_identity_sha256": identity.sha256, "user_agent": identity.user_agent, "storage_contract_sha256": storage_contract_sha256,
        "outlets": sorted(outlet_ids), "channels": {o: list(c) for o, c in sorted(channels.items())},
        "started_at": started_at, "finished_at": finished_at,
        "requests": {"total": sum(sum(v.values()) for v in requests_by_outlet.values()),
                     "item": sum(v[ITEM] for v in requests_by_outlet.values()), "other": sum(v[OTHER] for v in requests_by_outlet.values()),
                     "by_outlet": requests_by_outlet},
        "expansion_requests": {"total": sum(expansion_by_outlet.values()), "by_outlet": expansion_by_outlet},
        "response_classes": dict(sorted(statuses.items())),
        "refused": dict(sorted(refused.items())),
        "research_tdm": policy.research_tdm_pin(policy_record),
        "policy_layers": policy_layer_statistics(records, rows, outlet_ids),
        "counts": {"discovery_documents_fetched": discoveries, "candidates": candidates, "fetch_records": len(records),
                   "items_fetched": sum(1 for r in items if r["outcome"] == acquisition.OUTCOME_FETCHED),
                   "failed": sum(1 for r in records if r["outcome"] == acquisition.OUTCOME_FETCH_FAILED),
                   "refused": sum(refused.values()),
                   "preserved": sum(1 for s in states.values() if s == "RAW_PRESERVED"),
                   "pending": sum(1 for s in states.values() if s == "PRESERVATION_PENDING"),
                   "spooled_objects_pending": len(pending)},
        "bytes": {"received_bodies": sum(r["body_size_bytes"] for r in records if isinstance(r["body_size_bytes"], int)),
                  "preserved_objects": preserved_bytes},
        "packs": packs_of_run,
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
        try:
            changed = _git("diff", "--name-only", pinned_commit, head).splitlines()
        except subprocess.CalledProcessError as error:
            raise CanaryStopped("the pinned commit is not a commit of this repository") from error
        if any(not name.startswith(tuple(allowed_prefixes)) for name in changed):
            raise CanaryStopped(f"HEAD differs from the pinned commit beyond evidence files: {changed}")


def _after_the_run(arguments, environment, registered) -> int:
    """`verify` and `measure`: read-only, on the evidence of a finished run."""
    import shutil
    from types import SimpleNamespace

    from . import canary_evidence

    stored = json.loads(arguments.receipt.read_text(encoding="utf-8"))
    roles = storage_roots.resolve_configured_roles(env=environment)
    workspace = core_pipeline.Workspace(roles["RUNTIME"])
    if arguments.command == "measure":
        result = canary_evidence.measure(
            workspace, run_id=stored["run_id"], preservation_root=roles["PRESERVATION"],
            target_free_bytes=shutil.disk_usage(roles["PRESERVATION"]).free, new_filesystem_bytes=arguments.new_filesystem_bytes,
            legacy_sourced={"per_outlet_day_median": 115, "per_outlet_day_max": 367, "outlet_counts": [5, 53, 82]})
    else:
        identity = crawler_identity.load_identity()
        run = SimpleNamespace(run_id=stored["run_id"])
        # The policy version of a run is on record with every fetch it made. The tracked policy may have
        # moved on since; a run that fetched under exactly one version is re-derived under that one.
        policy_record = dict(policy.load_policy())
        recorded_versions = {r["policy"]["policy_version"] for r in fetch_records(workspace) if r["run_id"] == stored["run_id"]}
        if len(recorded_versions) == 1:
            policy_record["policy_version"] = recorded_versions.pop()
        rebuilt = build_receipt(
            workspace, run=run, commit=stored["commit"], baseline_id=stored["baseline_id"], policy_record=policy_record,
            schedule_policy=schedule.load_schedule_policy(), identity=identity, storage_contract_sha256=stored["storage_contract_sha256"],
            outlet_ids=stored["outlets"], channels=stored["channels"], preservation_root=roles["PRESERVATION"], spool_root=roles["SPOOL"],
            started_at=stored["started_at"], finished_at=stored["finished_at"], driver_version=stored["driver"])
        result = canary_evidence.verify(workspace, registered, run=run, preservation_root=roles["PRESERVATION"], spool_root=roles["SPOOL"],
                                        stored_receipt=stored, rebuilt_receipt=rebuilt)
    write_bytes_exclusive(arguments.out, record_json(result))
    print(json.dumps({"status": result.get("status", "MEASURED"), "out": arguments.out.name}, indent=2))
    return 0 if result.get("status", "PASS") == "PASS" else 1


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
    ver = commands.add_parser("verify", help="after a canary: read-back, fixity, replay without network, receipt re-derivation (no request)")
    ver.add_argument("--receipt", type=Path, required=True)
    ver.add_argument("--out", type=Path, required=True)
    mea = commands.add_parser("measure", help="after a canary: the O-4 measurement and its projections (no request)")
    mea.add_argument("--receipt", type=Path, required=True)
    mea.add_argument("--new-filesystem-bytes", type=int, default=None, help="nominal size of the planned file system, as stated by the operator")
    mea.add_argument("--out", type=Path, required=True)
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
    candidate_rules = candidate_filter.load_rules()
    if arguments.command == "pin":
        print(json.dumps(driver_pin(canary_budget(len(set(arguments.outlet))), registered, arguments.outlet, acquisition_policy["disabled_channels"],
                                    candidate_rules), indent=2, sort_keys=True))
        return 0

    if arguments.command in ("verify", "measure"):
        return _after_the_run(arguments, environment, registered)
    budget = canary_budget(len(set(arguments.outlet))) if arguments.command in ("baseline", "run") else None
    if arguments.command == "baseline":
        root = storage_roots.resolve_root("PRESERVATION", env=environment)
        readiness = preservation_target.check_readiness(root, required_free_bytes=arguments.required_free_bytes, now=datetime.now(timezone.utc))
        manifest = freeze.build_manifest(
            code_commit=arguments.commit, created_at=datetime.now(timezone.utc), operator=arguments.operator,
            test_baseline={"suite": "python -m pytest", "passed": arguments.tests_passed}, storage_target=readiness,
            scope=freeze.SCOPE_CANARY, canary=canary_pin(budget, registered, arguments.outlet, acquisition_policy["disabled_channels"], root, acquisition_policy,
                                                             candidate_rules=candidate_rules))
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
            budget, registered, arguments.outlet, acquisition_policy["disabled_channels"], roles_now["PRESERVATION"], acquisition_policy,
            candidate_rules=candidate_rules):
        raise CanaryStopped("the driver, its budgets, the outlets, the storage identity, the research-TDM policy or the "
                            "deployed crawler page differ from what the baseline pins")

    identity = crawler_identity.load_identity()
    schedule_policy = schedule.load_schedule_policy()
    roles = roles_now
    workspace = core_pipeline.Workspace(roles["RUNTIME"])
    clock = lambda: datetime.now(timezone.utc)  # noqa: E731
    started = clock()
    # The checkpoint immediately before the first real request: written once, before anything is asked.
    pending_at_start = outage_spool.pending_records(roles["SPOOL"]) if roles["SPOOL"].is_dir() else []
    start_state = {
        "schema": naming.schema_id("canary-start-state", 1), "driver": DRIVER_VERSION, "at": format_instant(started),
        "head": _git("rev-parse", "HEAD"), "origin_main_as_last_fetched": _git("rev-parse", "origin/main"),
        "pinned_commit": arguments.pinned_commit, "working_tree_clean": True, "approved_baseline_sha256": baseline["manifest_sha256"],
        "outlets": sorted(arguments.outlet), "policy_version": acquisition_policy["policy_version"],
        "policy_file_sha256": sha256_bytes((CHECKOUT / "config" / "acquisition_policy.json").read_bytes()),
        "crawler_identity": identity.as_record(), "preservation_target": baseline["canary"]["storage_target"],
        "research_tdm": baseline["canary"]["research_tdm"], "crawler_page": baseline["canary"]["crawler_page"],
        "budget": budget.as_record(), "hard_item_request_ceiling": HARD_ITEM_REQUESTS,
        "spool_pending_records": len(pending_at_start), "tests_passed": arguments.tests_passed, "preflight": report["status"],
    }
    if start_state["head"] != start_state["origin_main_as_last_fetched"]:
        raise CanaryStopped("HEAD is not origin/main as last fetched: push (or fetch) first")
    if pending_at_start:
        raise CanaryStopped("the spool holds pending objects: they are drained before a new canary starts")
    arguments.receipt_dir.mkdir(parents=True, exist_ok=True)
    run = http_acquisition.http_fetch_run(started, arguments.outlet, {"driver": DRIVER_VERSION, "baseline_id": baseline["manifest_sha256"],
                                                                      "budget": budget.as_record(), "pinned_commit": arguments.pinned_commit}, identity)
    write_bytes_exclusive(arguments.receipt_dir / f"canary-start-state-{run.run_id}.json", record_json({**start_state, "run_id": run.run_id}))
    gate = policy.PolicyGate(acquisition_policy, registered, identity)
    # The budget is that of the evidence of every run under this frozen baseline: a canary that is
    # started a second time does not get a second budget. The holds are those of the whole workspace,
    # whatever run met them, read again under the current classifier: a refusing origin is not asked again.
    used = tally_from_evidence(workspace, baseline_id=baseline["manifest_sha256"])
    fetcher = BudgetedFetcher(budget=budget, used=used, identity=identity, gate=gate, limits=CANARY_LIMITS, clock=clock, sleep=time.sleep,
                              access_holds=access_holds_from_evidence(workspace, reclassify=True))
    resolve = lambda role: (lambda: storage_roots.resolve_root(role, env=environment))  # noqa: E731
    outcome = run_canary(workspace, registered, run, outlet_ids=arguments.outlet, fetcher=fetcher, schedule_policy=schedule_policy, clock=clock,
                         preservation_root=resolve("PRESERVATION"), spool_root=resolve("SPOOL"), spool_policy=CANARY_SPOOL,
                         disabled_channels=acquisition_policy["disabled_channels"], candidate_rules=candidate_rules)
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
