"""A bounded, timed intake over the qualified source stock (decision CPD-0029).

A canary asks each outlet once. An intake asks again and again for a fixed time — it polls the channels of
a frozen **plan**, requests what is new, preserves every answer, and stops at a deadline that was fixed
when it started. It is orchestration only: the requests are `fetcher.HttpFetcher`'s through the policy
gate, discovery and candidate qualification are `http_acquisition.run_http_acquisition`'s, preservation,
identity and labels are the pipeline's. Nothing here parses, fetches or stores by itself.

What this module adds:

- the **plan** (`build_plan`): which outlets and channels, how often each channel is polled, the budgets;
- the **budgeted fetcher** (`IntakeFetcher`): every transport call counted against the intake's budgets —
  per outlet, per outlet and hour, per origin, in all — and refused after the deadline;
- the **selection** of what is requested (`selector`): what was first seen during the intake and is dated
  inside its window first, then what is new and undated, and only a small rest for older listings. Pages
  that were fetched before are not fetched again;
- the **controller** (`run`): cycles over the outlets, one acquisition call per outlet and cycle, a state
  file after every outlet, a deadline that survives a restart, budgets re-derived from the evidence;
- the **finalizer** (`finalize`): seal and preserve what is open, verify, write the receipt and the report.

The state file is a view for the operator and a checkpoint for the schedule; what was requested and
received is in the workspace's own evidence, and the budgets are counted from it at every start.
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit

from . import (access_control, acquisition, canary_driver, core_pipeline, discovery, extraction, fetcher as F, http_acquisition,
               incremental_check, naming, outage_spool, pack, policy as policy_module, preservation, recovery, schedule)
from .canonical import record_json, sha256_bytes, write_bytes_atomic
from .exclusive import WorkspaceBusy, exclusive
from .identity import format_instant

#: /2 (CPD-0033): pending within the resource policy's bounds no longer stops the requests; PAUSE_IO and the RUNTIME floor
#: pause them; the finalizer re-hashes only its own packs' masters on the root. A plan of /1 is history and is not run by /2.
#: /3 (CPD-0037, 2026-11-15): a cycle polls the outlets one after another and then requests their items **interleaved** --
#: one item per outlet and turn, round the outlets, so that the next request goes to another origin while one waits out its
#: pacing (one request at a time, every origin's interval and Crawl-delay as before); an allowance per outlet in the plan
#: (by measured volume); the items still due at the cycle's end stay due; a drain period at the end polls nothing; the check
#: after a cycle is incremental (incremental_check); the request log, the qualification table and the ledger are held across
#: the calls of the process (the only writer). A plan of /2 is run by /2's code path unchanged (the prepared canary
#: in2-20261114-canary is a /2 plan).
CONTROLLER_VERSION = "intake-controller/3"
CONTROLLER_2 = "intake-controller/2"
CONTROLLERS = (CONTROLLER_2, CONTROLLER_VERSION)
ALLOWANCE_KEYS = ("items_per_cycle", "item_requests_per_hour", "item_requests")
PLAN_SCHEMA = naming.schema_id("intake-plan", 1)
STATE_SCHEMA = naming.schema_id("intake-state", 1)
RECEIPT_SCHEMA = naming.schema_id("intake-receipt", 1)
RUNNING, STOPPED, COMPLETED, FAILED, BLOCKED, FINALIZING = "RUNNING", "STOPPED", "COMPLETED", "FAILED", "BLOCKED", "FINALIZING"
STATE_FILE, STOP_FILE, LOG_FILE = "state.json", "STOP", "controller.log"
USABLE = ("WORKS", "LISTING_WITH_RULE")
# How often a channel is polled, by what it is and how much it listed when it was last read. Starting values for a
# first measurement (CPD-0029), not measured rates.
POLL_SECONDS = {"feed": 3600, "sitemap": 3600, "large_sitemap": 6 * 3600, "sitemap_index": 6 * 3600, "listing": 2 * 3600, "bulk": 12 * 3600}
LARGE_SITEMAP_ENTRIES = 500          # a sitemap that lists more than this is not a news sitemap: polled like an index
BULK_ENTRIES = 5000                  # a channel that lists more than this is an archive, not a news channel: not polled when the outlet has another
PACE_MARGIN_SECONDS = 90             # no request is decided in the last 90 s: the longest pacing (a crawl delay of 60 s) ends before the deadline
RETRIES_OF_A_FAILED_CANDIDATE = 1    # a candidate whose request failed is asked once more during an intake, and no further


class IntakeStopped(RuntimeError):
    """The intake cannot go on: a precondition or an integrity check does not hold."""


@dataclass(frozen=True)
class IntakeBudget:
    """Every limit of an intake. All of them are in the plan, and the plan is pinned by the baseline."""

    duration_seconds: int
    cycle_seconds: int
    item_requests_per_outlet: int
    item_requests_per_outlet_hour: int
    item_requests_per_origin: int
    total_requests: int
    items_per_outlet_cycle: int
    backlog_items_per_outlet_cycle: int
    discovery_max_depth: int = 2
    discovery_max_documents: int = 4
    discovery_max_candidates: int = 200
    discovery_max_bytes: int = 4 * 1024 * 1024
    drain_seconds: int = 0                 # /3: the last seconds of an intake poll nothing; items listed before are requested

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer: {value!r}")
        if self.items_per_outlet_cycle > self.item_requests_per_outlet_hour or self.backlog_items_per_outlet_cycle > self.items_per_outlet_cycle:
            raise ValueError("a cycle asks an outlet for no more than its hourly limit, and for no more backlog than items")
        if self.cycle_seconds < 60 or self.duration_seconds < self.cycle_seconds:
            raise ValueError("a cycle is at least a minute and an intake at least a cycle")
        if self.drain_seconds and self.drain_seconds >= self.duration_seconds - self.cycle_seconds:
            raise ValueError("the drain period leaves at least one cycle of polls")

    def as_record(self) -> dict[str, int]:
        # drain_seconds is written only when it is used: a /2 plan's budget stays the record it was
        return {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "drain_seconds" or self.drain_seconds}

    @property
    def discovery(self) -> discovery.DiscoveryBudget:
        return discovery.DiscoveryBudget(max_depth=self.discovery_max_depth, max_documents=self.discovery_max_documents,
                                         max_candidates=self.discovery_max_candidates, max_bytes=self.discovery_max_bytes)


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc.lower()}"


def channel_class(channel: Mapping[str, Any]) -> str:
    """How a channel of the readiness file is polled: by its kind, what it was read as, and how much it listed."""
    formats, kind, entries = set(channel.get("formats") or ()), channel["kind"], channel.get("entries_last") or 0
    if entries > BULK_ENTRIES:
        return "bulk"                                    # an outlet's only channel, and an archive: twice a day at most
    if "html_listing" in formats or kind in ("section_page", "archive"):
        return "listing"
    if "sitemap_index" in formats or kind == "sitemap_index":
        return "sitemap_index"
    if kind == "sitemap" or "sitemap_urlset" in formats:
        return "large_sitemap" if entries > LARGE_SITEMAP_ENTRIES else "sitemap"
    return "feed"


def default_allowance(budget: IntakeBudget) -> dict[str, int]:
    return {"items_per_cycle": budget.items_per_outlet_cycle, "item_requests_per_hour": budget.item_requests_per_outlet_hour,
            "item_requests": budget.item_requests_per_outlet}


def build_plan(readiness: Mapping[str, Any], *, intake_id: str, budget: IntakeBudget, policy: Mapping[str, Any], registry_sha256: str,
               readiness_sha256: str, outlets: Sequence[str] | None = None, allowances: Mapping[str, Mapping[str, int]] | None = None,
               controller: str = CONTROLLER_VERSION) -> dict[str, Any]:
    """The plan of an intake from an intake-readiness file: its outlets (all, or the named ones), their usable
    channels with a poll interval each, and the budgets. Deterministic; decides nothing the readiness file did not.

    A channel is left out when it is disabled, when its URL or its host is held, or when it is an archive (more than
    `BULK_ENTRIES` entries) and the outlet has another usable channel — an old stock must not dominate an intake.
    """
    held_origins, held_urls = set(readiness.get("held_origins") or {}), set(readiness.get("held_urls") or {})
    chosen, left_out = [], {}
    for entry in readiness["outlets"]:
        if outlets is not None and entry["outlet_id"] not in outlets:
            continue
        if set(entry["web_origins"]) & held_origins:
            left_out[entry["outlet_id"]] = "an origin of the outlet is held"
            continue
        channels = []
        for channel in entry["channels"]:
            if channel["channel_id"] in policy["disabled_channels"] or channel["url"] in held_urls or _origin(channel["url"]) in held_origins:
                continue
            channels.append({"channel_id": channel["channel_id"], "kind": channel["kind"], "url": channel["url"], "poll_class": channel_class(channel),
                             "entries_last": channel.get("entries_last")})
        small = [c for c in channels if (c["entries_last"] or 0) <= BULK_ENTRIES]
        dropped = [c["channel_id"] for c in channels if c not in small] if small else []
        channels = small or channels
        for channel in channels:
            channel["poll_seconds"] = POLL_SECONDS[channel["poll_class"]]
        if not channels:
            left_out[entry["outlet_id"]] = "no usable channel"
            continue
        chosen.append({"outlet_id": entry["outlet_id"], "country_id": entry["country_id"], "tier": entry["tier"], "web_origins": entry["web_origins"],
                       "channels": channels, "bulk_channels_not_polled": dropped, "candidate_rule": entry.get("candidate_rule"),
                       "robots_crawl_delay_seconds_observed": entry["limits"].get("robots_crawl_delay_seconds_observed")})
        if controller != CONTROLLER_2:
            chosen[-1]["allowance"] = {**default_allowance(budget), **dict((allowances or {}).get(entry["outlet_id"]) or {})}
    if outlets is not None and {o["outlet_id"] for o in chosen} | set(left_out) != set(outlets):
        raise IntakeStopped("an outlet named for the plan is not in the readiness file")
    if controller not in CONTROLLERS:
        raise IntakeStopped(f"not a controller this package runs: {controller}")
    chosen.sort(key=lambda outlet: outlet["outlet_id"])
    return {"schema": PLAN_SCHEMA, "intake_id": intake_id, "controller": controller, "budget": budget.as_record(),
            "poll_seconds_by_class": dict(POLL_SECONDS), "policy_version": policy["policy_version"],
            "derived_from": {"readiness_version": readiness["readiness_version"], "readiness_sha256": readiness_sha256, "registry_sha256": registry_sha256},
            "totals": {"outlets": len(chosen), "channels": sum(len(o["channels"]) for o in chosen), "countries": sorted({o["country_id"] for o in chosen}),
                       "tier_a": sum(o["tier"] == "A" for o in chosen), "tier_b": sum(o["tier"] == "B" for o in chosen)},
            "left_out": dict(sorted(left_out.items())), "outlets": chosen}


def validate_plan(plan: Mapping[str, Any], registry_: Any, policy: Mapping[str, Any], holds: Mapping[str, str]) -> IntakeBudget:
    """A plan can be run only against the registry, the policy and the holds as they are now. Raises with the reason."""
    if plan.get("schema") != PLAN_SCHEMA or plan.get("controller") not in CONTROLLERS:
        raise IntakeStopped(f"not a {PLAN_SCHEMA} of {' or '.join(CONTROLLERS)}")
    if plan["policy_version"] != policy["policy_version"]:
        raise IntakeStopped(f"the plan was made under policy {plan['policy_version']}; the policy is {policy['policy_version']}")
    budget = IntakeBudget(**plan["budget"])
    if plan["controller"] == CONTROLLER_2 and budget.drain_seconds:
        raise IntakeStopped(f"{CONTROLLER_2} has no drain period")
    maxima = default_allowance(budget)
    for outlet in plan["outlets"]:
        allowance = outlet.get("allowance")
        if plan["controller"] == CONTROLLER_2:
            if allowance is not None:
                raise IntakeStopped(f"{CONTROLLER_2} has no allowance per outlet")
        else:
            if not isinstance(allowance, Mapping) or set(allowance) != set(ALLOWANCE_KEYS):
                raise IntakeStopped(f"{outlet['outlet_id']}: an allowance of exactly {list(ALLOWANCE_KEYS)}")
            for key in ALLOWANCE_KEYS:
                value = allowance[key]
                if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maxima[key]:
                    raise IntakeStopped(f"{outlet['outlet_id']}: {key} {value!r} is not a whole number up to the budget's {maxima[key]}")
            if allowance["items_per_cycle"] > allowance["item_requests_per_hour"]:
                raise IntakeStopped(f"{outlet['outlet_id']}: a cycle asks for no more than the outlet's hour allows")
        registered = registry_.resolve(outlet["outlet_id"])                 # registered, or a refusal
        known = {c["channel_id"]: c["url_history"][-1]["url"] for c in registered["channels"]}
        for channel in outlet["channels"]:
            if known.get(channel["channel_id"]) != channel["url"]:
                raise IntakeStopped(f"{channel['channel_id']}: not a channel of the registry at that address")
            if channel["channel_id"] in policy["disabled_channels"]:
                raise IntakeStopped(f"{channel['channel_id']}: disabled by the policy")
            if channel["url"] in holds or _origin(channel["url"]) in holds:
                raise IntakeStopped(f"{channel['channel_id']}: held ({holds.get(channel['url']) or holds.get(_origin(channel['url']))})")
        held = [origin for origin in registered["web_origins"] if origin in holds]
        if held:
            raise IntakeStopped(f"{outlet['outlet_id']}: its origin {held[0]} is held")
    if len({o["outlet_id"] for o in plan["outlets"]}) != len(plan["outlets"]) or not plan["outlets"]:
        raise IntakeStopped("a plan names each outlet once, and at least one")
    return budget


# --- the authorisation and the baseline pin -------------------------------------------------------------------

AUTHORIZATION_SCHEMA = naming.schema_id("intake-authorization", 1)
MODE_DELEGATED_INTAKE = "DELEGATED_INTAKE_AUTHORIZATION"
AUTHORIZATION_RECORDS = "config/intake/authorizations"
_AUTHORIZATION_KEYS = {"schema", "authorization_id", "kind", "issued_on", "issued_by", "issued_to", "source", "valid_until", "policy_versions", "intake", "conditions"}
_CEILINGS = ("duration_seconds", "item_requests_per_outlet", "item_requests_per_outlet_hour", "item_requests_per_origin", "total_requests")


def validate_authorization(record: Any) -> None:
    """The form of an intake authorisation record. It says who commissioned which intake, within which ceilings."""
    if not isinstance(record, Mapping) or set(record) != _AUTHORIZATION_KEYS:
        raise IntakeStopped(f"an intake authorisation has exactly the fields {sorted(_AUTHORIZATION_KEYS)}")
    if record["schema"] != AUTHORIZATION_SCHEMA or record["kind"] != MODE_DELEGATED_INTAKE:
        raise IntakeStopped(f"not a {MODE_DELEGATED_INTAKE} of {AUTHORIZATION_SCHEMA}")
    for name in ("authorization_id", "issued_on", "issued_by", "issued_to", "valid_until"):
        if not isinstance(record[name], str) or not record[name].strip():
            raise IntakeStopped(f"{name} is stated")
    for name in ("issued_on", "valid_until"):
        try:
            datetime.strptime(record[name], "%Y-%m-%d")
        except ValueError as error:
            raise IntakeStopped(f"{name} is a date") from error
    if not isinstance(record["source"], Mapping) or not str(record["source"].get("commission") or "").strip():
        raise IntakeStopped("an authorisation names the commission it rests on")
    if not isinstance(record["policy_versions"], list) or not record["policy_versions"] or not isinstance(record["conditions"], list):
        raise IntakeStopped("an authorisation names the policy versions it holds under, and its conditions")
    scope = record["intake"]
    if not isinstance(scope, Mapping) or set(scope) != {"intake_id", "plan", "plan_sha256", "ceilings", "excluded_outlets"}:
        raise IntakeStopped("the intake of an authorisation is: intake_id, plan, plan_sha256, ceilings, excluded_outlets")
    if set(scope["ceilings"]) != set(_CEILINGS) or any(isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in scope["ceilings"].values()):
        raise IntakeStopped(f"the ceilings are whole numbers for exactly {list(_CEILINGS)}")


def check_authorization(record: Mapping[str, Any], plan: Mapping[str, Any], *, plan_path: str, policy_version: str, today: Any) -> None:
    """Whether the record covers exactly this plan, now. Raises with the reason; adds no permission of its own."""
    validate_authorization(record)
    scope = record["intake"]
    if scope["intake_id"] != plan["intake_id"] or scope["plan"] != plan_path:
        raise IntakeStopped("the authorisation names another intake or another plan file")
    if scope["plan_sha256"] != sha256_bytes(record_json(dict(plan))):
        raise IntakeStopped("the plan is not the plan the authorisation names (digest)")
    if policy_version not in record["policy_versions"]:
        raise IntakeStopped(f"the authorisation does not hold under policy {policy_version}")
    if not record["issued_on"] <= today.isoformat() <= record["valid_until"]:
        raise IntakeStopped(f"the authorisation is valid from {record['issued_on']} to {record['valid_until']}; today is {today.isoformat()}")
    over = [name for name in _CEILINGS if plan["budget"][name] > scope["ceilings"][name]]
    if over:
        raise IntakeStopped(f"the plan exceeds the authorised ceiling of: {', '.join(over)}")
    excluded = sorted(set(scope["excluded_outlets"]) & {outlet["outlet_id"] for outlet in plan["outlets"]})
    if excluded:
        raise IntakeStopped(f"the plan names outlets the authorisation excludes: {excluded}")


def authorization_block(record: Mapping[str, Any], record_path: str, record_bytes: bytes) -> dict[str, Any]:
    """What a baseline pins about the authorisation it was built under."""
    return {"mode": MODE_DELEGATED_INTAKE, "authorization_id": record["authorization_id"], "record": record_path, "record_sha256": sha256_bytes(record_bytes),
            "issued_by": record["issued_by"], "issued_to": record["issued_to"], "intake_id": record["intake"]["intake_id"]}


def intake_pin(plan: Mapping[str, Any], plan_path: str, authorization: Mapping[str, Any], registry_: Any, preservation_root: Path,
               acquisition_policy: Mapping[str, Any], repository: Path = canary_driver.CHECKOUT) -> dict[str, Any]:
    """The ``canary`` block of the baseline of an intake: the controller, the plan by digest, the budgets, the outlets as
    registered, and — as for every canary — the research-TDM layer, the classifiers, the public crawler page and the identity
    of the preservation target. No location of any disk enters it.
    """
    from . import freeze, preservation_target, storage_contract
    from .canonical import canonical_json

    marker = preservation_target.read_target(preservation_root)
    if marker is None:
        raise IntakeStopped("the preservation target has no identity")
    return {
        "authorization": dict(authorization),
        "intake": {"controller": plan["controller"], "intake_id": plan["intake_id"], "plan": plan_path, "plan_sha256": sha256_bytes(record_json(dict(plan))),
                   "budget": dict(plan["budget"]), "totals": dict(plan["totals"]), "poll_seconds_by_class": dict(POLL_SECONDS),
                   "pace_margin_seconds": PACE_MARGIN_SECONDS, "retries_of_a_failed_candidate": RETRIES_OF_A_FAILED_CANDIDATE,
                   "fetch_limits": {name: getattr(canary_driver.CANARY_LIMITS, name) for name in ("timeout_seconds", "total_seconds", "max_redirects", "max_body_bytes", "max_attempts")},
                   "selection": "never a page fetched before; first what was first listed during the intake and is dated inside its window (newest first), "
                                "then what a later poll listed first without a date, then at most backlog_items_per_outlet_cycle of the rest",
                   "extractor": extraction.BASELINE.stage_version,
                   **({"interleaving": "polls outlet after outlet; then one item per outlet and turn, round the outlets, until every "
                                       "outlet's allowance is spent, nothing is due or the cycle ends; what is still due stays due",
                       "workspace_check": incremental_check.CHECK_VERSION} if plan["controller"] != CONTROLLER_2 else {})},
        "research_tdm": policy_module.research_tdm_pin(acquisition_policy),
        "access_control_classifier": access_control.CLASSIFIER_VERSION,
        "robots_parser": F.robots.PARSER_VERSION,
        "crawler_page": canary_driver.crawler_page_pin(repository),
        "outlets": {outlet["outlet_id"]: {"record_sha256": sha256_bytes(canonical_json(registry_.resolve(outlet["outlet_id"])))} for outlet in plan["outlets"]},
        "storage_contract_sha256": storage_contract.read_pin()["bundle_sha256"],
        "storage_target": {"target_id": marker["target_id"], "marker_sha256": sha256_bytes(canonical_json(marker))},
        "schemas": freeze.schema_ids(),
    }


# --- the budgeted fetcher ----------------------------------------------------------------------------


class IntakeFetcher(F.HttpFetcher):
    """The ordinary fetcher with every transport call counted against the intake's budgets, and nothing asked after
    the deadline. A redirect hop is a request. A request that does not fit is not made, and the refusal is on record.
    """

    def __init__(self, *, budget: IntakeBudget, deadline: datetime, used: Mapping[str, Any] | None = None,
                 permitted: Callable[[], str | None] | None = None, allowances: Mapping[str, Mapping[str, int]] | None = None,
                 **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.budget, self.deadline, self.permitted = budget, deadline, permitted
        self.allowances = dict(allowances or {})            # /3: an outlet's own item limits (none above the budget's)
        # A request is decided, then paced, then sent. Nothing is decided so late that its pacing could carry it past the deadline.
        self.last_decision_at = deadline - timedelta(seconds=PACE_MARGIN_SECONDS)
        used = used or {}
        self.total = int(used.get("total", 0))
        self.items_by_outlet: Counter[str] = Counter(used.get("items_by_outlet") or {})
        self.items_by_origin: Counter[str] = Counter(used.get("items_by_origin") or {})
        self.item_times: dict[str, list[datetime]] = {outlet: list(times) for outlet, times in (used.get("item_times") or {}).items()}
        self._context: tuple[str | None, str | None] = (None, None)

    def _in_the_last_hour(self, outlet_id: str) -> int:
        since = self.clock() - timedelta(hours=1)
        self.item_times[outlet_id] = [at for at in self.item_times.get(outlet_id, []) if at > since]
        return len(self.item_times[outlet_id])

    def refusal(self, outlet_id: str | None, kind: str | None, url: str) -> str | None:
        """Why the next transport call for this request must not be made, or ``None``."""
        if self.clock() >= self.last_decision_at:
            return "intake_deadline_reached"
        if self.permitted is not None and self.permitted() is not None:
            return "intake_permission_withdrawn"                # the switch was turned off under a running intake: the next request is not made
        if self.total >= self.budget.total_requests:
            return "intake_budget_exhausted: total"
        if kind == acquisition.FETCH_KIND_ITEM and outlet_id is not None:
            own = self.allowances.get(outlet_id) or {}
            if self.items_by_outlet[outlet_id] >= own.get("item_requests", self.budget.item_requests_per_outlet):
                return "intake_budget_exhausted: outlet"
            if self._in_the_last_hour(outlet_id) >= own.get("item_requests_per_hour", self.budget.item_requests_per_outlet_hour):
                return "intake_budget_exhausted: outlet_hour"
            if self.items_by_origin[_origin(url)] >= self.budget.item_requests_per_origin:
                return "intake_budget_exhausted: origin"
        return None

    def _denied(self, reason: str) -> policy_module.PolicyDecision:
        return policy_module.PolicyDecision(policy_module.DENY, (reason.split(":")[0],), self.gate.policy["policy_version"], {"intake": reason})

    def fetch(self, request: F.FetchRequest, *, planned_at: datetime | None = None) -> F.FetchOutcome:
        reason = self.refusal(request.outlet_id, request.fetch_kind, request.url)
        if reason is not None:
            planned_at = planned_at or self.clock()
            return F.FetchOutcome(request, F.request_id(request, planned_at), F.FINAL_DENIED, self._denied(reason))
        previous, self._context = self._context, (request.outlet_id, request.fetch_kind)
        try:
            return super().fetch(request, planned_at=planned_at)
        finally:
            self._context = previous

    def robots_evidence(self, outlet_id: str, origin: str):
        if (outlet_id, origin) not in self._robots and self.refusal(outlet_id, acquisition.FETCH_KIND_ROBOTS, origin) is not None:
            return F.robots.RobotsEvidence(F.robots.EVIDENCE_NOT_CONSULTED, detail="intake_budget_or_deadline")
        previous, self._context = self._context, (outlet_id, acquisition.FETCH_KIND_ROBOTS)
        try:
            return super().robots_evidence(outlet_id, origin)
        finally:
            self._context = previous

    def _decide(self, request: F.FetchRequest, url: str) -> policy_module.PolicyDecision:
        outlet_id, kind = self._context
        reason = self.refusal(outlet_id, kind, url)            # asked for the first request of a fetch and for every redirect hop
        if reason is not None:
            return self._denied(reason)
        return super()._decide(request, url)

    def _request(self, url: str, extra: Sequence[tuple[str, str]] = ()):
        outlet_id, kind = self._context
        reason = self.refusal(outlet_id, kind, url)
        if reason is not None or outlet_id is None:
            raise IntakeStopped(f"a transport call that must not be made: {reason or 'outside any intake context'}")
        self.total += 1
        if kind == acquisition.FETCH_KIND_ITEM:
            self.items_by_outlet[outlet_id] += 1
            self.items_by_origin[_origin(url)] += 1
            self.item_times.setdefault(outlet_id, []).append(self.clock())
        return super()._request(url, extra)

    def _pace(self, origin: str) -> None:
        super()._pace(origin)
        if self.clock() >= self.deadline:                      # cannot happen while the margin covers the longest pacing; if it does, nothing is sent
            raise IntakeStopped("the pacing of a request ran past the deadline: the request is not sent")

    def used(self) -> dict[str, Any]:
        return {"total": self.total, "items_by_outlet": dict(sorted(self.items_by_outlet.items())), "items_by_origin": dict(sorted(self.items_by_origin.items()))}


def used_from_evidence(workspace: core_pipeline.Workspace, run_ids: Sequence[str], now: datetime) -> dict[str, Any]:
    """The budgets an intake has spent, counted from its fetch records: a restart does not get a second budget."""
    wanted, total = set(run_ids), 0
    by_outlet: Counter[str] = Counter()
    by_origin: Counter[str] = Counter()
    times: dict[str, list[datetime]] = {}
    if not wanted:
        return {"total": 0, "items_by_outlet": {}, "items_by_origin": {}, "item_times": {}}
    for record in canary_driver.fetch_records(workspace):
        if record["run_id"] not in wanted:
            continue
        calls = canary_driver.transport_calls(record)
        total += calls
        if record["fetch_kind"] == acquisition.FETCH_KIND_ITEM:
            by_outlet[record["outlet_id"]] += calls
            final = (record.get("response") or {}).get("final_url") or ""
            by_origin[_origin(final)] += calls
            at = datetime.fromisoformat(record["fetch_started_at"].replace("Z", "+00:00"))
            if at > now - timedelta(hours=1):
                times.setdefault(record["outlet_id"], []).extend([at] * calls)
    return {"total": total, "items_by_outlet": dict(by_outlet), "items_by_origin": dict(by_origin), "item_times": times}


# --- what is requested --------------------------------------------------------------------------------

NEW_IN_WINDOW, NEW_UNDATED, FIRST_POLL_UNDATED, OLDER = "new_dated_in_window", "new_undated_later_poll", "first_poll_undated", "older_than_window"
KNOWN_BEFORE = "known_before_intake"


def novelty(candidate: Mapping[str, Any], first_event: Mapping[str, Any] | None, started_at: datetime, first_poll_done: Mapping[str, str]) -> str:
    """What a candidate is to an intake, from when it was first listed and what its channel says about its date.

    A URL that is found for the first time is not thereby an article published during the intake: what a channel lists
    at its first poll is its stock. Only a date inside the window, or a first listing in a *later* poll, says new.
    """
    listed = datetime.fromisoformat(candidate["first_listed_at"].replace("Z", "+00:00"))
    if listed < started_at:
        return KNOWN_BEFORE
    published = discovery.entry_instant(first_event["hints"]) if first_event else None
    if published is not None:
        return NEW_IN_WINDOW if published >= started_at else OLDER
    done = first_poll_done.get(candidate["first_channel_id"])
    first_poll = done is None or listed <= datetime.fromisoformat(done.replace("Z", "+00:00"))
    return FIRST_POLL_UNDATED if first_poll else NEW_UNDATED


def selector(started_at: datetime, first_poll_done: Mapping[str, str], backlog_per_cycle: int) -> Callable[[Sequence[schedule.CandidateState], Any], list[schedule.CandidateState]]:
    """The order in which an intake requests: new and dated inside the window (newest first), then new and undated,
    then at most ``backlog_per_cycle`` of the rest (the most recently listed first). Never a page that was fetched before.
    """
    def select(due: Sequence[schedule.CandidateState], tables: Any) -> list[schedule.CandidateState]:
        fresh, undated, backlog = [], [], []
        for state in due:
            if state.state not in (schedule.NEVER_FETCHED, schedule.FAILING) or state.attempts > RETRIES_OF_A_FAILED_CANDIDATE:
                continue                                           # a revisit of a fetched page is not an intake's business
            candidate = tables.candidates[state.candidate_id]
            event = tables.first_event_of(state.candidate_id)
            kind = novelty(candidate, event, started_at, first_poll_done)
            published = discovery.entry_instant(event["hints"]) if event else None
            if kind == NEW_IN_WINDOW:
                fresh.append((-published.timestamp(), state.candidate_id, state))
            elif kind == NEW_UNDATED:
                undated.append((candidate["first_listed_at"], state.candidate_id, state))
            else:
                backlog.append((published.timestamp() if published else 0.0, candidate["first_listed_at"], state.candidate_id, state))
        undated.sort(key=lambda row: (row[0], row[1]), reverse=True)
        backlog.sort(key=lambda row: row[:3], reverse=True)        # the most recently dated first, then the most recently listed
        return [row[-1] for row in sorted(fresh, key=lambda row: row[:2])] + [row[-1] for row in undated] + [row[-1] for row in backlog[:backlog_per_cycle]]
    return select


# --- state ---------------------------------------------------------------------------------------------


def state_path(state_dir: Path) -> Path:
    return Path(state_dir) / STATE_FILE


def read_state(state_dir: Path) -> dict[str, Any]:
    try:
        state = json.loads(state_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise IntakeStopped(f"the intake has no readable state: {error}") from error
    if state.get("schema") != STATE_SCHEMA:
        raise IntakeStopped(f"not a {STATE_SCHEMA}")
    return state


def write_state(state_dir: Path, state: Mapping[str, Any]) -> None:
    write_bytes_atomic(state_path(state_dir), record_json(dict(state)))     # whole or absent, never half


def initial_state(plan: Mapping[str, Any], *, started_at: datetime, baseline: Mapping[str, Any]) -> dict[str, Any]:
    """The state an intake starts with. The clock starts here: the deadline is fixed now and never moved."""
    deadline = started_at + timedelta(seconds=plan["budget"]["duration_seconds"])
    return {"schema": STATE_SCHEMA, "intake_id": plan["intake_id"], "controller": plan["controller"], "status": RUNNING,
            "started_at_utc": format_instant(started_at), "deadline_at_utc": format_instant(deadline),
            "started_at_local": started_at.astimezone().isoformat(timespec="seconds"), "deadline_at_local": deadline.astimezone().isoformat(timespec="seconds"),
            "plan_sha256": sha256_bytes(record_json(dict(plan))), "baseline": dict(baseline),
            "cycle": 0, "cycle_started_at": None, "run_ids": [], "channel_last_poll": {}, "first_poll_done": {}, "outlets_done_in_cycle": [],
            "requests_total": 0, "items_by_outlet": {}, "item_pages_2xx": 0, "errors": [], "holds": {}, "restarts": 0,
            "preservation": "nothing pending", "last_checkpoint_at": format_instant(started_at), "finalized": None}


LOG_MAX_BYTES = 4 * 1024 * 1024      # CPD-0035: the controller log is kept to this size and one previous generation (``controller.log.1``)


def _log(state_dir: Path, message: str) -> None:
    path = Path(state_dir) / LOG_FILE
    try:
        if path.stat().st_size > LOG_MAX_BYTES:
            os.replace(path, path.with_name(LOG_FILE + ".1"))         # the controller's own log: the older generation is replaced
    except OSError:
        pass
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{format_instant(datetime.now(timezone.utc))} {message}\n")


# --- the controller ---------------------------------------------------------------------------------------


@dataclass
class Environment:
    """What a controller runs against. Everything a test replaces is here."""

    workspace: core_pipeline.Workspace
    registry: Any
    policy: Mapping[str, Any]
    identity: Any
    schedule_policy: schedule.SchedulePolicy
    candidate_rules: Mapping[str, Mapping[str, Any]]
    preservation_root: Callable[[], Path]
    spool_root: Callable[[], Path] | None
    spool_policy: outage_spool.SpoolPolicy | None
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    sleep: Callable[[float], None] = time.sleep
    fetcher_options: Mapping[str, Any] | None = None       # tests: connect_override
    # Asked before every cycle: ``None``, or why no further request may be made (the switch is off, a pinned file changed).
    still_permitted: Callable[[], str | None] | None = None
    # CPD-0033: the resource policy. With it, an intake goes on while what is pending stays inside the policy's bounds
    # (count, bytes, age, and the RUNTIME free-space floor) and pauses beyond them; the operator's PAUSE_IO file pauses it.
    # Without it (``None``) nothing more is asked while anything is pending -- the behaviour of intake-controller/1.
    resource_policy: Any = None


def pending_refusal(env: "Environment", waiting: Sequence[str], now: datetime) -> str | None:
    """Why no further request may be made while ``waiting`` packs are pending (CPD-0033), or ``None``.

    The received bytes of a pending pack are complete and verified in the workspace (and in the spool when it had room):
    an honest ``PENDING`` (contract P4/P5). They are safe only within what the local disk guarantees, so the intake goes
    on asking only while the pending packs are within the policy's bounds of count, bytes and age and the RUNTIME volume
    is above its floor. Without a resource policy every pending pack stops the requests, as before.
    """
    if not waiting:
        return None
    policy = env.resource_policy
    if policy is None:
        return f"{len(waiting)} packs pending and no resource policy: nothing is asked until they are preserved"
    if len(waiting) > policy.pending_max_packs:
        return f"{len(waiting)} packs pending, more than the policy's {policy.pending_max_packs}"
    size, oldest = 0, None
    for identifier in waiting:
        try:
            stat = (env.workspace.packs / f"{identifier}.warc.gz").stat()
        except OSError:
            return f"{identifier}: pending, and its sealed pack cannot be read in the workspace"
        size += stat.st_size
        sealed = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
        oldest = sealed if oldest is None or sealed < oldest else oldest
    if size > policy.pending_max_bytes:
        return f"{size} bytes pending, more than the policy's {policy.pending_max_bytes}"
    if oldest is not None and now - oldest > timedelta(hours=policy.pending_max_age_hours):
        return f"the oldest pending pack was sealed {oldest.isoformat(timespec='seconds')}, more than {policy.pending_max_age_hours} h ago"
    from . import resource_policy as R

    return R.free_space_refusal("RUNTIME", env.workspace.root, policy)


def io_refusal(env: "Environment") -> str | None:
    """Why the intake must not make a request now for a reason of shared resources (CPD-0033): the operator's PAUSE_IO
    file, or the RUNTIME volume below its floor. ``None`` without a resource policy."""
    if env.resource_policy is None:
        return None
    from . import resource_policy as R

    return R.paused(env.workspace.root) or R.free_space_refusal("RUNTIME", env.workspace.root, env.resource_policy)


def _due_channels(outlet: Mapping[str, Any], state: Mapping[str, Any], now: datetime) -> list[str]:
    due = []
    for channel in outlet["channels"]:
        last = state["channel_last_poll"].get(channel["channel_id"])
        if last is None or now - datetime.fromisoformat(last.replace("Z", "+00:00")) >= timedelta(seconds=channel["poll_seconds"]):
            due.append(channel["channel_id"])
    return due


def run(plan: Mapping[str, Any], state_dir: Path, environment: Environment) -> dict[str, Any]:
    """Run the intake until its deadline, a stop request or a systemic failure. Returns the state it leaves.

    Restartable at any point: the deadline and the plan are those of the state file, the budgets are counted from the
    fetch records of the intake's runs, and holds are derived from every preserved answer. One controller at a time.
    """
    state_dir = Path(state_dir)
    env = environment
    with exclusive(state_dir, "intake controller"):
        state = read_state(state_dir)
        if state["status"] != RUNNING:
            return state
        if state["plan_sha256"] != sha256_bytes(record_json(dict(plan))):
            raise IntakeStopped("the plan is not the plan this intake was started with")
        holds = canary_driver.access_holds_from_evidence(env.workspace, reclassify=True)
        # The plan was validated against the holds when the intake was started. A hold that arose since stops the
        # requests it covers (the fetcher's own rule), not the intake: an outlet that is held is passed over.
        budget = validate_plan(plan, env.registry, env.policy, {})
        started_at = datetime.fromisoformat(state["started_at_utc"].replace("Z", "+00:00"))
        deadline = datetime.fromisoformat(state["deadline_at_utc"].replace("Z", "+00:00"))
        for run_id in acquisition.unfinished_runs(env.workspace.root):      # a cycle the last process did not finish
            if run_id in state["run_ids"]:
                acquisition.close_run(env.workspace.root, _RunRef(run_id), finished_at=env.clock(), status="FAILED", counts={}, pack_ids=[],
                                      errors=["the controller process ended before this cycle did; the intake went on in a new cycle"])
                state["restarts"] += 1
        _finish_open_packs(env, [o["outlet_id"] for o in plan["outlets"]])
        fetcher = IntakeFetcher(budget=budget, deadline=deadline, used=used_from_evidence(env.workspace, state["run_ids"], env.clock()), permitted=env.still_permitted,
                                identity=env.identity, gate=policy_module.PolicyGate(env.policy, env.registry, env.identity),
                                limits=canary_driver.CANARY_LIMITS, clock=env.clock, sleep=env.sleep, access_holds=holds,
                                allowances={o["outlet_id"]: o["allowance"] for o in plan["outlets"] if "allowance" in o},
                                **dict(env.fetcher_options or {}))
        # Read, and authenticated, once: this process is the workspace's only writer for as long as it runs.
        tables = http_acquisition.discovery_tables(env.workspace)
        interleaved = plan["controller"] != CONTROLLER_2
        loaded = _held_evidence(env, tables) if interleaved else None
        check: dict[str, Any] = {}
        _log(state_dir, f"controller started: cycle {state['cycle']}, {fetcher.total} requests used, deadline {state['deadline_at_utc']}")
        while env.clock() < fetcher.last_decision_at and not (state_dir / STOP_FILE).exists():
            cycle_started = env.clock()
            refusal = env.still_permitted() if env.still_permitted is not None else None
            if refusal is not None:                                 # the switch was turned off, or what the baseline pins has changed
                return _stop(state_dir, state, BLOCKED, refusal)
            if env.resource_policy is None:                         # intake-controller/1 behaviour: every pending pack, every time
                pending = _finish_open_packs(env, [o["outlet_id"] for o in plan["outlets"]], sealed_pending=True)
                waiting = {identifier for identifier, result in pending.items() if result != preservation.STATE_PRESERVED}
            else:
                waiting = _catch_up(env, state, [o["outlet_id"] for o in plan["outlets"]], cycle_started)
            state["preservation"] = _pending_text(waiting)
            hold = pending_refusal(env, sorted(waiting), cycle_started) or io_refusal(env)
            if hold is not None:
                # What was received is not safe enough to receive more (the target is away beyond the local bounds), or the
                # operator paused shared I/O, or the local disk is low: nothing more is asked for until that changes.
                if state.get("held_because") != hold:                # an expected, lasting hold is logged once, not every five minutes
                    _log(state_dir, f"no request: {hold}")
                state["held_because"] = hold
                write_state(state_dir, state)
                env.sleep(min(300.0, max(1.0, (fetcher.last_decision_at - env.clock()).total_seconds())))
                continue
            state["held_because"] = None
            state["cycle"] += 1
            state["cycle_started_at"], state["outlets_done_in_cycle"] = format_instant(cycle_started), []
            outlets = [o for o in plan["outlets"]]
            shift = (state["cycle"] - 1) % len(outlets)
            outlets = outlets[shift:] + outlets[:shift]             # every outlet is first in turn: none is always served last
            run_ = http_acquisition.http_fetch_run(cycle_started, [o["outlet_id"] for o in outlets],
                                                   {"intake_id": plan["intake_id"], "cycle": state["cycle"], "controller": CONTROLLER_VERSION,
                                                    "budget": budget.as_record(), "plan_sha256": state["plan_sha256"]}, env.identity)
            state["run_ids"].append(run_.run_id)
            write_state(state_dir, state)                           # the run is the intake's before it is opened: a restart finds it
            acquisition.open_run(env.workspace.root, run_)
            counts: Counter[str] = Counter()
            blocked: str | None = None
            if interleaved:
                blocked, stopped = _interleaved_cycle(env, plan, state, state_dir, budget, fetcher, run_, outlets, loaded, started_at,
                                                      cycle_started, deadline, waiting, holds, counts)
                if stopped is not None:
                    return stopped
            for outlet in ([] if interleaved else outlets):
                if env.clock() >= fetcher.last_decision_at or (state_dir / STOP_FILE).exists() or blocked is not None:
                    break
                refusal = env.still_permitted() if env.still_permitted is not None else None
                if refusal is not None:
                    return _stop(state_dir, state, BLOCKED, refusal)
                if set(outlet["web_origins"]) & set(fetcher.access_holds):
                    state["holds"][outlet["outlet_id"]] = "an origin of the outlet is held"
                    continue
                channels = [c for c in _due_channels(outlet, state, env.clock())
                            if next(x["url"] for x in outlet["channels"] if x["channel_id"] == c) not in fetcher.access_holds]
                try:
                    summary = http_acquisition.run_http_acquisition(
                        env.workspace, env.registry, run_, outlet["outlet_id"], fetcher=fetcher, channel_ids=channels, budget=budget.discovery,
                        max_item_fetches=budget.items_per_outlet_cycle, schedule_policy=env.schedule_policy, clock=env.clock,
                        candidate_rules=env.candidate_rules, tables=tables,
                        select_due=selector(started_at, state["first_poll_done"], budget.backlog_items_per_outlet_cycle))
                    preserved = canary_driver._preserve(env.workspace, summary["open_pack_ids"], env.preservation_root, env.spool_root, env.spool_policy, env.clock)
                    canary_driver._derive(env.workspace, env.registry, env.preservation_root, preserved, extraction.BASELINE, env.clock)
                    for identifier, result in preserved.items():
                        (waiting.discard if result["state"] == preservation.STATE_PRESERVED else waiting.add)(identifier)
                    state["preservation"] = _pending_text(waiting)
                    counts.update({f"requests_{key}": value for key, value in summary["requests"].items()})
                    counts["candidates_requested"] += summary["candidates_requested"]
                except (acquisition.AcquisitionError, pack.PackError, preservation.PreservationError, discovery.DiscoveryError, OSError, ValueError, KeyError) as error:
                    # One outlet's trouble is that outlet's: it is on record, and the others go on. What it left open is
                    # sealed and preserved at the next start of a cycle or by the finalizer.
                    state["errors"].append({"at": format_instant(env.clock()), "cycle": state["cycle"], "outlet_id": outlet["outlet_id"],
                                            "error": f"{type(error).__name__}: {str(error)[:300]}"})
                    _log(state_dir, f"outlet error {outlet['outlet_id']}: {type(error).__name__}: {str(error)[:200]}")
                    tables = http_acquisition.discovery_tables(env.workspace)      # as they are on disk, whatever the failed call left in memory
                    if len([e for e in state["errors"] if e["cycle"] == state["cycle"]]) > max(5, len(outlets) // 3):
                        return _stop(state_dir, state, FAILED, "more than a third of the outlets failed in one cycle: a systemic fault, not an outlet's")
                now = env.clock()
                for channel_id in channels:
                    state["channel_last_poll"][channel_id] = format_instant(cycle_started)
                    state["first_poll_done"].setdefault(channel_id, format_instant(now))
                state["outlets_done_in_cycle"].append(outlet["outlet_id"])
                state["requests_total"], state["items_by_outlet"] = fetcher.total, dict(sorted(fetcher.items_by_outlet.items()))
                state["holds"].update({key: value for key, value in fetcher.access_holds.items() if key not in holds})
                state["last_checkpoint_at"] = format_instant(now)
                blocked = pending_refusal(env, sorted(waiting), now) or io_refusal(env)
                state["held_because"] = blocked
                write_state(state_dir, state)
            acquisition.close_run(env.workspace.root, run_, finished_at=env.clock(), status="COMPLETED", counts=dict(counts),
                                  pack_ids=[], errors=[e["error"] for e in state["errors"] if e["cycle"] == state["cycle"]][:20])
            if interleaved:                                     # /3: what this cycle (and anything since the last check) added
                diagnosis, check["state"] = incremental_check.checkpoint(env.workspace.root, check.get("state"), now=env.clock())
                if diagnosis["classification"] == recovery.NEEDS_REPAIR:
                    recovery.repair(env.workspace.root)
                    diagnosis, check["state"] = incremental_check.checkpoint(env.workspace.root, None, now=env.clock())
                    loaded = _held_evidence(env, None)          # a repair moved bytes aside: read the evidence again
                state["last_check"] = (diagnosis.get("check") or {}).get("mode")
            else:
                diagnosis = recovery.diagnose(env.workspace.root)
                if diagnosis["classification"] == recovery.NEEDS_REPAIR:
                    recovery.repair(env.workspace.root)
                    diagnosis = recovery.diagnose(env.workspace.root)
            if diagnosis["classification"] in (recovery.DAMAGED, recovery.NEEDS_REPAIR):
                return _stop(state_dir, state, FAILED, f"after cycle {state['cycle']} the workspace is {diagnosis['classification']}: {diagnosis.get('damaged') or diagnosis.get('needs_repair')}")
            _log(state_dir, f"cycle {state['cycle']} done: {fetcher.total} requests in all, {sum(fetcher.items_by_outlet.values())} item requests")
            write_state(state_dir, state)
            next_cycle = min(cycle_started + timedelta(seconds=budget.cycle_seconds), fetcher.last_decision_at)
            while env.clock() < next_cycle and not (state_dir / STOP_FILE).exists() and blocked is None:
                env.sleep(min(5.0, max(0.01, (next_cycle - env.clock()).total_seconds())))
        if (state_dir / STOP_FILE).exists() and env.clock() < fetcher.last_decision_at:
            return _stop(state_dir, state, STOPPED, "a stop was requested")
        state["status"] = FINALIZING
        write_state(state_dir, state)
        _log(state_dir, f"no further request: the deadline is {state['deadline_at_utc']}")
        return state


_OUTLET_ERRORS = (acquisition.AcquisitionError, pack.PackError, preservation.PreservationError, discovery.DiscoveryError, OSError,
                  ValueError, KeyError)


def _held_evidence(env: "Environment", tables: Any) -> dict[str, Any]:
    """/3: the evidence the only writer holds across its calls, each read in full once and then extended by what is appended."""
    return {"tables": tables if tables is not None else http_acquisition.discovery_tables(env.workspace),
            "log": http_acquisition.RequestLog(env.workspace), "qualifications": http_acquisition.qualification_table(env.workspace),
            "ledger": env.workspace.ledger()}


class _Queue:
    """/3: an outlet's items of one cycle -- chosen once, by the intake's selector, up to its allowance -- handed out one at a
    time, each only while the planner still says it is due."""

    def __init__(self, select: Callable[[Sequence[schedule.CandidateState], Any], list[schedule.CandidateState]], allowance: int) -> None:
        self.select, self.allowance, self.order, self.given = select, allowance, None, 0

    @property
    def exhausted(self) -> bool:
        return self.given >= self.allowance or (self.order is not None and not self.order)

    def __call__(self, due: Sequence[schedule.CandidateState], tables: Any) -> list[schedule.CandidateState]:
        if self.order is None:
            self.order = [state.candidate_id for state in self.select(due, tables)][:self.allowance]
        allowed = {state.candidate_id: state for state in due}
        while self.order and self.given < self.allowance:
            candidate = self.order.pop(0)
            if candidate in allowed:
                self.given += 1
                return [allowed[candidate]]
        return []


def _interleaved_cycle(env: "Environment", plan: Mapping[str, Any], state: dict[str, Any], state_dir: Path, budget: IntakeBudget,
                       fetcher: IntakeFetcher, run_: Any, outlets: Sequence[Mapping[str, Any]], loaded: dict[str, Any], started_at: datetime,
                       cycle_started: datetime, deadline: datetime, waiting: set[str], holds: Mapping[str, str],
                       counts: Counter[str]) -> tuple[str | None, dict[str, Any] | None]:
    """One cycle of intake-controller/3. Returns ``(why no more is asked, or None; the state of a stopped intake, or None)``.

    1. **Polls**, outlet after outlet (the outlets in the cycle's rotated order): every due channel of an outlet in one call.
       In the drain period nothing is polled.
    2. **Items, interleaved**: round the outlets, one item per outlet and turn, so that consecutive requests go to different
       origins and each origin's pacing runs while the others are asked. An outlet leaves the round when its allowance of the
       cycle is spent or nothing more is due; the round ends with the cycle. What is still due then stays due.
    3. **Preservation**, outlet by outlet, as in /2.
    """
    cycle_end = min(cycle_started + timedelta(seconds=budget.cycle_seconds), fetcher.last_decision_at)
    draining = bool(budget.drain_seconds) and cycle_started >= deadline - timedelta(seconds=budget.drain_seconds)
    packs_of: dict[str, set[str]] = {o["outlet_id"]: set() for o in outlets}

    def stop_requested() -> bool:
        return env.clock() >= fetcher.last_decision_at or (state_dir / STOP_FILE).exists()

    def acquire(outlet: Mapping[str, Any], channels: list[str], items: int, select: Any) -> dict[str, Any] | None:
        try:
            summary = http_acquisition.run_http_acquisition(
                env.workspace, env.registry, run_, outlet["outlet_id"], fetcher=fetcher, channel_ids=channels, budget=budget.discovery,
                max_item_fetches=items, schedule_policy=env.schedule_policy, clock=env.clock, candidate_rules=env.candidate_rules,
                select_due=select, tables=loaded["tables"], request_log=loaded["log"], qualifications=loaded["qualifications"],
                ledger=loaded["ledger"])
        except _OUTLET_ERRORS as error:
            state["errors"].append({"at": format_instant(env.clock()), "cycle": state["cycle"], "outlet_id": outlet["outlet_id"],
                                    "error": f"{type(error).__name__}: {str(error)[:300]}"})
            _log(state_dir, f"outlet error {outlet['outlet_id']}: {type(error).__name__}: {str(error)[:200]}")
            loaded.update(_held_evidence(env, None))          # as it is on disk, whatever the failed call left in memory
            return None
        packs_of[outlet["outlet_id"]].update(summary["open_pack_ids"])
        counts.update({f"requests_{key}": value for key, value in summary["requests"].items()})
        counts["candidates_requested"] += summary["candidates_requested"]
        return summary

    def too_many_errors() -> bool:
        return len([e for e in state["errors"] if e["cycle"] == state["cycle"]]) > max(5, len(outlets) // 3)

    # 1. polls
    reachable = []
    for outlet in outlets:
        if stop_requested():
            break
        refusal = env.still_permitted() if env.still_permitted is not None else None
        if refusal is not None:
            return None, _stop(state_dir, state, BLOCKED, refusal)
        if set(outlet["web_origins"]) & set(fetcher.access_holds):
            state["holds"][outlet["outlet_id"]] = "an origin of the outlet is held"
            continue
        channels = [] if draining else [c for c in _due_channels(outlet, state, env.clock())
                                        if next(x["url"] for x in outlet["channels"] if x["channel_id"] == c) not in fetcher.access_holds]
        if channels:
            acquire(outlet, channels, 0, None)
            if too_many_errors():
                return None, _stop(state_dir, state, FAILED, "more than a third of the outlets failed in one cycle: a systemic fault, not an outlet's")
            now = env.clock()
            for channel_id in channels:
                state["channel_last_poll"][channel_id] = format_instant(cycle_started)
                state["first_poll_done"].setdefault(channel_id, format_instant(now))
        reachable.append(outlet)

    # 2. items, interleaved
    queues = {o["outlet_id"]: _Queue(selector(started_at, state["first_poll_done"], budget.backlog_items_per_outlet_cycle),
                                     (o.get("allowance") or default_allowance(budget))["items_per_cycle"]) for o in reachable}
    turn = [o for o in reachable if queues[o["outlet_id"]].allowance > 0]
    while turn and env.clock() < cycle_end and not stop_requested():
        refusal = env.still_permitted() if env.still_permitted is not None else None
        if refusal is not None:
            return None, _stop(state_dir, state, BLOCKED, refusal)
        for outlet in list(turn):
            if env.clock() >= cycle_end or stop_requested():
                break
            queue = queues[outlet["outlet_id"]]
            if set(outlet["web_origins"]) & set(fetcher.access_holds):
                turn = [o for o in turn if o is not outlet]        # leaves the round
                continue
            summary = acquire(outlet, [], 1, queue)
            if too_many_errors():
                return None, _stop(state_dir, state, FAILED, "more than a third of the outlets failed in one cycle: a systemic fault, not an outlet's")
            if summary is None or not summary["candidates_requested"] or queue.exhausted:
                turn = [o for o in turn if o is not outlet]        # leaves the round
    if turn:                                                   # the cycle ended before these outlets' items: they stay due
        cut = state.setdefault("items_left_at_cycle_end", {})
        for outlet in turn:
            left = len(queues[outlet["outlet_id"]].order or [])
            if left:
                cut[outlet["outlet_id"]] = cut.get(outlet["outlet_id"], 0) + left

    # 3. preservation, outlet by outlet
    blocked: str | None = None
    for outlet in reachable:
        identifier = outlet["outlet_id"]
        try:
            preserved = canary_driver._preserve(env.workspace, sorted(packs_of[identifier]), env.preservation_root, env.spool_root, env.spool_policy, env.clock)
            canary_driver._derive(env.workspace, env.registry, env.preservation_root, preserved, extraction.BASELINE, env.clock)
            for pack_id, result in preserved.items():
                (waiting.discard if result["state"] == preservation.STATE_PRESERVED else waiting.add)(pack_id)
        except _OUTLET_ERRORS as error:
            state["errors"].append({"at": format_instant(env.clock()), "cycle": state["cycle"], "outlet_id": identifier,
                                    "error": f"{type(error).__name__}: {str(error)[:300]}"})
            _log(state_dir, f"preservation error {identifier}: {type(error).__name__}: {str(error)[:200]}")
        now = env.clock()
        state["preservation"] = _pending_text(waiting)
        state["outlets_done_in_cycle"].append(identifier)
        state["requests_total"], state["items_by_outlet"] = fetcher.total, dict(sorted(fetcher.items_by_outlet.items()))
        state["holds"].update({key: value for key, value in fetcher.access_holds.items() if key not in holds})
        state["last_checkpoint_at"] = format_instant(now)
        blocked = pending_refusal(env, sorted(waiting), now) or io_refusal(env)
        state["held_because"] = blocked
        write_state(state_dir, state)
    return blocked, None


def _hourly(state: dict[str, Any], key: str, now: datetime, limit: int) -> int:
    """What is left of an hourly budget kept in the state file (so a restart does not refill it)."""
    hour = now.strftime("%Y-%m-%dT%H")
    bucket = state.get(key) or {}
    if bucket.get("hour") != hour:
        bucket = {"hour": hour, "used": 0}
    state[key] = bucket
    return max(0, limit - int(bucket.get("used") or 0))


def _spend(state: dict[str, Any], key: str, amount: int) -> None:
    state[key]["used"] = int(state[key].get("used") or 0) + amount


def _warm_cache(env: Environment, state: dict[str, Any], now: datetime) -> None:
    """The bounded warm-up of the manifest cache (CPD-0035): while the cache of the target lacks manifests, at most the policy's
    reads per hour, only when a transfer would be permitted. Once a check finds it complete it is not listed again for it
    (this process stores every manifest it binds). Any refusal of the root is left for the preservation step to meet."""
    known = state.get("manifest_cache") or {}
    if known.get("missing") == 0:
        return
    budget = _hourly(state, "cache_warm_hour", now, env.resource_policy.cache_warm_reads_per_hour)
    if budget == 0:
        return
    from . import preserved_index
    from .storage_roots import StorageRefusal

    try:
        root = env.preservation_root()
        cache = core_pipeline.content_index(env.workspace, root)
        if cache is None:
            return
        done = preserved_index.warm(cache, root, (core_pipeline.AREA_PACKS, core_pipeline.AREA_INDEXES), max_reads=budget)
    except (StorageRefusal, OSError) as error:
        from . import resource_policy as R

        if isinstance(error, OSError):
            R.report_failure(env.preservation_root, f"manifest cache warm-up: {type(error).__name__}")
        return
    _spend(state, "cache_warm_hour", done["read"])
    state["manifest_cache"] = {"missing": done["missing"], "checked_at": format_instant(now), "read_this_hour": state["cache_warm_hour"]["used"]}


def _catch_up(env: Environment, state: dict[str, Any], outlet_ids: Sequence[str], now: datetime) -> set[str]:
    """Seal what is open, then preserve a **bounded** part of the backlog (CPD-0035), oldest first; returns the packs still pending.

    * nothing is attempted while the root's gate holds new transfers (CO.RA.PAN degraded, slow or recovering, a back-off, the
      operator's pause): one local check, no contact, no attempt per pack;
    * at most ``catch_up_packs_per_hour`` packs (counted in the state file, so a restart after a long outage does not burst);
    * the first pack that stays pending ends the batch: the share went away again, or the manifest cache is still warming.
    """
    from . import resource_policy as R

    wanted = set(outlet_ids)
    opened = _finish_open_packs(env, outlet_ids)                           # the open packs: sealed, and preserved or spooled
    backlog = [p for p in canary_driver.pending_pack_ids(env.workspace) if pack.pack_outlet(p) in wanted]
    waiting = {p for p, result in opened.items() if result != preservation.STATE_PRESERVED} | set(backlog)
    held = R.transfer_held(env.preservation_root)
    info: dict[str, Any] = {"backlog": len(backlog), "attempted": 0, "preserved": 0, "held_because": held, "at": format_instant(now)}
    if backlog and held is None:
        _warm_cache(env, state, now)
        budget = _hourly(state, "catch_up_hour", now, env.resource_policy.catch_up_packs_per_hour)
        for identifier in sorted(backlog, key=lambda p: (p.rsplit("-", 2)[-2], p.rsplit("-", 2)[-1], p))[:budget]:
            preserved = canary_driver._preserve(env.workspace, [identifier], env.preservation_root, env.spool_root, env.spool_policy, env.clock)
            canary_driver._derive(env.workspace, env.registry, env.preservation_root, preserved, extraction.BASELINE, env.clock)
            info["attempted"] += 1
            _spend(state, "catch_up_hour", 1)
            if preserved[identifier]["state"] != preservation.STATE_PRESERVED:
                info["stopped_because"] = preserved[identifier].get("reason")
                break
            waiting.discard(identifier)
            info["preserved"] += 1
        info["budget_left_this_hour"] = max(0, budget - info["attempted"])
    state["catch_up"] = info
    return waiting


def _pending_text(waiting: set[str]) -> str:
    """What the state file says about preservation: ``nothing pending``, or the pending packs (named up to ten)."""
    if not waiting:
        return "nothing pending"
    names = sorted(waiting)
    return f"pending: {names}" if len(names) <= 10 else f"pending: {len(names)} packs, the first {names[:10]}"


class _RunRef:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id


def _stop(state_dir: Path, state: dict[str, Any], status: str, reason: str) -> dict[str, Any]:
    state["status"], state["stopped_because"] = status, reason
    write_state(state_dir, state)
    _log(state_dir, f"{status}: {reason}")
    return state


def _finish_open_packs(env: Environment, outlet_ids: Sequence[str], *, sealed_pending: bool = False) -> dict[str, Any]:
    """Seal, preserve and derive every pack of these outlets that is still open: nothing received stays unpreserved.
    ``sealed_pending``: also the sealed packs whose fetches are still pending (the target was away): preserving is repeatable.
    """
    done: dict[str, Any] = {}
    wanted = set(outlet_ids)
    identifiers = {path.name[: -len(".warc.gz.open")] for path in env.workspace.packs.glob("*.warc.gz.open") if path.stat().st_size}
    if sealed_pending:
        identifiers |= set(canary_driver.pending_pack_ids(env.workspace))
    for identifier in sorted(identifiers):
        if pack.pack_outlet(identifier) in wanted:
            preserved = canary_driver._preserve(env.workspace, [identifier], env.preservation_root, env.spool_root, env.spool_policy, env.clock)
            canary_driver._derive(env.workspace, env.registry, env.preservation_root, preserved, extraction.BASELINE, env.clock)
            done[identifier] = preserved[identifier]["state"]
    return done


def drain(plan: Mapping[str, Any], state_dir: Path, environment: Environment) -> int:
    """After the deadline, before the finalization (CPD-0035): one bounded catch-up step of the pending backlog -- the same
    budget per hour and the same gate as in the controller, so the end of an intake after an outage is no burst either.
    Makes no request. Returns how many packs are still pending (0: the finalizer may run)."""
    state_dir, env = Path(state_dir), environment
    with exclusive(state_dir, "intake drain"):
        state = read_state(state_dir)
        waiting = _catch_up(env, state, [o["outlet_id"] for o in plan["outlets"]], env.clock())
        state["preservation"] = _pending_text(waiting)
        write_state(state_dir, state)
        return len(waiting)


# --- the end ---------------------------------------------------------------------------------------------


def finalize(plan: Mapping[str, Any], state_dir: Path, environment: Environment, *, verify_bodies: bool = True) -> dict[str, Any]:
    """After the deadline (or a stop): preserve what is open, close what is open, verify, and write the receipt.
    Makes no request. Repeatable: a finalization that was interrupted is simply run again.
    """
    state_dir, env = Path(state_dir), environment
    with exclusive(state_dir, "intake finalizer"):
        state = read_state(state_dir)
        if state["status"] == RUNNING and env.clock() < datetime.fromisoformat(state["deadline_at_utc"].replace("Z", "+00:00")):
            raise IntakeStopped("the intake is running and its deadline has not come")
        outcome = state["status"] if state["status"] in (STOPPED, FAILED, BLOCKED) else COMPLETED
        _finish_open_packs(env, [o["outlet_id"] for o in plan["outlets"]])
        for run_id in acquisition.unfinished_runs(env.workspace.root):
            if run_id in state["run_ids"]:
                acquisition.close_run(env.workspace.root, _RunRef(run_id), finished_at=env.clock(), status="FAILED", counts={}, pack_ids=[],
                                      errors=["closed by the finalizer: the cycle was cut short by the deadline, a stop or the end of its process"])
        checks: list[dict[str, Any]] = []

        def check(name: str, ok: bool, detail: str) -> None:
            checks.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})

        runs = set(state["run_ids"])
        records = [r for r in canary_driver.fetch_records(env.workspace) if r["run_id"] in runs]
        states = env.workspace.ledger().states()
        open_left = [p.name for p in env.workspace.packs.glob("*.warc.gz.open") if p.stat().st_size]
        check("nothing_left_open", not open_left, f"{len(open_left)} open packs with content")
        expected = {r["fetch_id"] for r in records if states.get(r["fetch_id"]) != "FETCH_FAILED"}
        claimed = {f for f in expected if states.get(f) == "RAW_PRESERVED"}
        check("every_answer_is_raw_preserved", claimed == expected, f"{len(claimed)} RAW_PRESERVED of {len(expected)} answers with a body")
        problems, bodies, verified = [], 0, set()
        if verify_bodies:
            root = env.preservation_root()
            for identifier in sorted({canary_identifier for canary_identifier in _packs_of(env.workspace, records)}):
                try:
                    held = core_pipeline.open_preserved_pack(root, identifier)
                    for fetch_id, entry in held.entries.items():
                        if entry.body_sha256 is not None:
                            bodies += 1
                            if sha256_bytes(held.body(fetch_id)) != entry.body_sha256:
                                problems.append(f"{fetch_id}: body does not hash")
                            verified.add(fetch_id)
                except (core_pipeline.NotPreserved, preservation.PreservationError, pack.PackError, OSError) as error:
                    problems.append(f"{identifier}: {type(error).__name__}")
            check("preservation_readback_and_fixity", not problems and (bodies > 0 or not expected), f"{bodies} bodies read back from the preservation root; {problems[:5] or 'all verify'}")
            check("raw_preserved_matches_verified_bytes", claimed <= verified, f"{len(claimed & verified)} of {len(claimed)} RAW_PRESERVED answers have verified preserved bytes")
        # CPD-0033: the masters of this intake's own packs are re-hashed on the root, and the identity tables are checked for
        # self-consistency; every other pack of the workspace is not read. A whole-root read (every master, the identity
        # rebuild from every preserved pack) is the operator-ordered audit `scripts/preservation_audit.py`, never part of a
        # regular finalizer -- with a growing corpus on a shared link it is what made a finalizer expensive.
        diagnosis = recovery.diagnose(env.workspace.root, env.preservation_root(), master_scope=_packs_of(env.workspace, records))
        check("recovery_diagnosis", diagnosis["classification"] == recovery.CLEAN,
              f"{diagnosis['classification']}; masters of this intake re-hashed on the root: {diagnosis.get('masters_checked_on_root')}; "
              "identity tables: self-consistency (the rebuild against the root is the separate audit)")
        used = used_from_evidence(env.workspace, state["run_ids"], env.clock())
        budget = IntakeBudget(**plan["budget"])
        within = (used["total"] <= budget.total_requests and all(v <= budget.item_requests_per_outlet for v in used["items_by_outlet"].values())
                  and all(v <= budget.item_requests_per_origin for v in used["items_by_origin"].values()))
        check("budget_respected", within, f"{used['total']} requests of {budget.total_requests}; the most for one outlet {max(used['items_by_outlet'].values(), default=0)} of {budget.item_requests_per_outlet}")
        deadline = datetime.fromisoformat(state["deadline_at_utc"].replace("Z", "+00:00"))
        late = [r["fetch_id"] for r in records if datetime.fromisoformat(r["fetch_started_at"].replace("Z", "+00:00")) >= deadline]
        check("no_request_after_the_deadline", not late, f"{len(late)} requests started at or after {state['deadline_at_utc']}")
        items = [r for r in records if r["fetch_kind"] == acquisition.FETCH_KIND_ITEM and r["outcome"] == acquisition.OUTCOME_FETCHED]
        receipt = {
            "schema": RECEIPT_SCHEMA, "intake_id": plan["intake_id"], "controller": CONTROLLER_VERSION, "outcome": outcome,
            "started_at_utc": state["started_at_utc"], "deadline_at_utc": state["deadline_at_utc"], "finalized_at_utc": format_instant(env.clock()),
            "plan_sha256": state["plan_sha256"], "baseline": state["baseline"], "cycles": state["cycle"], "restarts": state["restarts"], "runs": len(state["run_ids"]),
            "requests": {"total": used["total"], "item": sum(used["items_by_outlet"].values()), "other": used["total"] - sum(used["items_by_outlet"].values())},
            "fetch_records": len(records), "item_pages_2xx": sum(1 for r in items if 200 <= (r["response"]["status"] or 0) < 300),
            "response_classes": dict(sorted(Counter(str((r.get("response") or {}).get("status")) if r["outcome"] == acquisition.OUTCOME_FETCHED else f"failed:{r.get('failure_reason')}" for r in records).items())),
            "outlets_with_item_pages": len({r["outlet_id"] for r in items if 200 <= (r["response"]["status"] or 0) < 300}),
            "errors": len(state["errors"]), "holds_that_arose": state["holds"], "stopped_because": state.get("stopped_because"),
            "verification": {"status": "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL", "checks": checks}}
        if outcome == COMPLETED and receipt["verification"]["status"] != "PASS":
            outcome = receipt["outcome"] = "PARTIAL"
        state["status"], state["finalized"] = outcome if outcome != "PARTIAL" else COMPLETED, {"at": receipt["finalized_at_utc"], "outcome": outcome, "verification": receipt["verification"]["status"]}
        state["requests_total"], state["item_pages_2xx"] = used["total"], receipt["item_pages_2xx"]
        write_bytes_atomic(state_dir / "receipt.json", record_json(receipt))
        write_state(state_dir, state)
        _log(state_dir, f"finalized: {outcome}; verification {receipt['verification']['status']}; {used['total']} requests, {receipt['item_pages_2xx']} item pages")
        return receipt


def _packs_of(workspace: core_pipeline.Workspace, records: Sequence[Mapping[str, Any]]) -> set[str]:
    """The packs that hold these fetch records (by outlet and UTC day of the request)."""
    wanted = {(r["outlet_id"], pack.utc_day_of(r["fetch_started_at"])) for r in records}
    found = set()
    for identifier in canary_driver.pack_ids(workspace):
        if (pack.pack_outlet(identifier), identifier.rsplit("-", 2)[-2]) in wanted:
            found.add(identifier)
    return found


def status_line(state: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    """What an operator reads off the state file at any time."""
    deadline = datetime.fromisoformat(state["deadline_at_utc"].replace("Z", "+00:00"))
    return {"intake_id": state["intake_id"], "status": state["status"], "started_at_local": state["started_at_local"], "deadline_at_local": state["deadline_at_local"],
            "remaining_seconds": max(0, int((deadline - now).total_seconds())), "cycle": state["cycle"], "outlets_done_in_cycle": len(state["outlets_done_in_cycle"]),
            "requests_total": state["requests_total"], "item_requests": sum(state["items_by_outlet"].values()), "outlets_with_item_requests": len(state["items_by_outlet"]),
            "preservation": state["preservation"], "held_because": state.get("held_because"), "holds": state["holds"], "errors": len(state["errors"]), "restarts": state["restarts"],
            "last_checkpoint_at": state["last_checkpoint_at"], "finalized": state["finalized"],
            "catch_up": state.get("catch_up"), "manifest_cache": state.get("manifest_cache"), "finalization_waits": state.get("finalization_waits")}


__all__ = ["IntakeBudget", "IntakeFetcher", "IntakeStopped", "Environment", "build_plan", "validate_plan", "run", "finalize", "initial_state", "read_state",
           "write_state", "status_line", "selector", "novelty", "used_from_evidence", "WorkspaceBusy"]
