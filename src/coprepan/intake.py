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
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit

from . import (access_control, acquisition, canary_driver, core_pipeline, discovery, extraction, fetcher as F, http_acquisition, naming,
               outage_spool, pack, policy as policy_module, preservation, recovery, schedule)
from .canonical import record_json, sha256_bytes, write_bytes_atomic
from .exclusive import WorkspaceBusy, exclusive
from .identity import format_instant

CONTROLLER_VERSION = "intake-controller/1"
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

    def __post_init__(self) -> None:
        for name, value in self.as_record().items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer: {value!r}")
        if self.items_per_outlet_cycle > self.item_requests_per_outlet_hour or self.backlog_items_per_outlet_cycle > self.items_per_outlet_cycle:
            raise ValueError("a cycle asks an outlet for no more than its hourly limit, and for no more backlog than items")
        if self.cycle_seconds < 60 or self.duration_seconds < self.cycle_seconds:
            raise ValueError("a cycle is at least a minute and an intake at least a cycle")

    def as_record(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

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


def build_plan(readiness: Mapping[str, Any], *, intake_id: str, budget: IntakeBudget, policy: Mapping[str, Any], registry_sha256: str,
               readiness_sha256: str, outlets: Sequence[str] | None = None) -> dict[str, Any]:
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
    if outlets is not None and {o["outlet_id"] for o in chosen} | set(left_out) != set(outlets):
        raise IntakeStopped("an outlet named for the plan is not in the readiness file")
    chosen.sort(key=lambda outlet: outlet["outlet_id"])
    return {"schema": PLAN_SCHEMA, "intake_id": intake_id, "controller": CONTROLLER_VERSION, "budget": budget.as_record(),
            "poll_seconds_by_class": dict(POLL_SECONDS), "policy_version": policy["policy_version"],
            "derived_from": {"readiness_version": readiness["readiness_version"], "readiness_sha256": readiness_sha256, "registry_sha256": registry_sha256},
            "totals": {"outlets": len(chosen), "channels": sum(len(o["channels"]) for o in chosen), "countries": sorted({o["country_id"] for o in chosen}),
                       "tier_a": sum(o["tier"] == "A" for o in chosen), "tier_b": sum(o["tier"] == "B" for o in chosen)},
            "left_out": dict(sorted(left_out.items())), "outlets": chosen}


def validate_plan(plan: Mapping[str, Any], registry_: Any, policy: Mapping[str, Any], holds: Mapping[str, str]) -> IntakeBudget:
    """A plan can be run only against the registry, the policy and the holds as they are now. Raises with the reason."""
    if plan.get("schema") != PLAN_SCHEMA or plan.get("controller") != CONTROLLER_VERSION:
        raise IntakeStopped(f"not a {PLAN_SCHEMA} of {CONTROLLER_VERSION}")
    if plan["policy_version"] != policy["policy_version"]:
        raise IntakeStopped(f"the plan was made under policy {plan['policy_version']}; the policy is {policy['policy_version']}")
    budget = IntakeBudget(**plan["budget"])
    for outlet in plan["outlets"]:
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
        "intake": {"controller": CONTROLLER_VERSION, "intake_id": plan["intake_id"], "plan": plan_path, "plan_sha256": sha256_bytes(record_json(dict(plan))),
                   "budget": dict(plan["budget"]), "totals": dict(plan["totals"]), "poll_seconds_by_class": dict(POLL_SECONDS),
                   "pace_margin_seconds": PACE_MARGIN_SECONDS, "retries_of_a_failed_candidate": RETRIES_OF_A_FAILED_CANDIDATE,
                   "fetch_limits": {name: getattr(canary_driver.CANARY_LIMITS, name) for name in ("timeout_seconds", "max_redirects", "max_body_bytes", "max_attempts")},
                   "selection": "never a page fetched before; first what was first listed during the intake and is dated inside its window (newest first), "
                                "then what a later poll listed first without a date, then at most backlog_items_per_outlet_cycle of the rest",
                   "extractor": extraction.BASELINE.stage_version},
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
                 permitted: Callable[[], str | None] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.budget, self.deadline, self.permitted = budget, deadline, permitted
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
            if self.items_by_outlet[outlet_id] >= self.budget.item_requests_per_outlet:
                return "intake_budget_exhausted: outlet"
            if self._in_the_last_hour(outlet_id) >= self.budget.item_requests_per_outlet_hour:
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
    return {"schema": STATE_SCHEMA, "intake_id": plan["intake_id"], "controller": CONTROLLER_VERSION, "status": RUNNING,
            "started_at_utc": format_instant(started_at), "deadline_at_utc": format_instant(deadline),
            "started_at_local": started_at.astimezone().isoformat(timespec="seconds"), "deadline_at_local": deadline.astimezone().isoformat(timespec="seconds"),
            "plan_sha256": sha256_bytes(record_json(dict(plan))), "baseline": dict(baseline),
            "cycle": 0, "cycle_started_at": None, "run_ids": [], "channel_last_poll": {}, "first_poll_done": {}, "outlets_done_in_cycle": [],
            "requests_total": 0, "items_by_outlet": {}, "item_pages_2xx": 0, "errors": [], "holds": {}, "restarts": 0,
            "preservation": "nothing pending", "last_checkpoint_at": format_instant(started_at), "finalized": None}


def _log(state_dir: Path, message: str) -> None:
    with open(Path(state_dir) / LOG_FILE, "a", encoding="utf-8", newline="\n") as handle:
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
                                limits=canary_driver.CANARY_LIMITS, clock=env.clock, sleep=env.sleep, access_holds=holds, **dict(env.fetcher_options or {}))
        # Read, and authenticated, once: this process is the workspace's only writer for as long as it runs.
        tables = http_acquisition.discovery_tables(env.workspace)
        _log(state_dir, f"controller started: cycle {state['cycle']}, {fetcher.total} requests used, deadline {state['deadline_at_utc']}")
        while env.clock() < fetcher.last_decision_at and not (state_dir / STOP_FILE).exists():
            cycle_started = env.clock()
            refusal = env.still_permitted() if env.still_permitted is not None else None
            if refusal is not None:                                 # the switch was turned off, or what the baseline pins has changed
                return _stop(state_dir, state, BLOCKED, refusal)
            pending = _finish_open_packs(env, [o["outlet_id"] for o in plan["outlets"]], sealed_pending=True)
            waiting = sorted(identifier for identifier, result in pending.items() if result != preservation.STATE_PRESERVED)
            state["preservation"] = f"pending: {waiting}" if waiting else "nothing pending"
            if waiting:
                # What was received is not safe yet (the target is away): nothing more is asked for until it is.
                write_state(state_dir, state)
                _log(state_dir, f"preservation pending for {len(waiting)} packs: no request until they are preserved")
                env.sleep(min(300.0, max(1.0, (fetcher.last_decision_at - env.clock()).total_seconds())))
                continue
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
            for outlet in outlets:
                if env.clock() >= fetcher.last_decision_at or (state_dir / STOP_FILE).exists() or state["preservation"] != "nothing pending":
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
                    pending = [identifier for identifier, result in preserved.items() if result["state"] != preservation.STATE_PRESERVED]
                    state["preservation"] = f"pending: {pending}" if pending else "nothing pending"
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
                write_state(state_dir, state)
            acquisition.close_run(env.workspace.root, run_, finished_at=env.clock(), status="COMPLETED", counts=dict(counts),
                                  pack_ids=[], errors=[e["error"] for e in state["errors"] if e["cycle"] == state["cycle"]][:20])
            diagnosis = recovery.diagnose(env.workspace.root)
            if diagnosis["classification"] == recovery.NEEDS_REPAIR:
                recovery.repair(env.workspace.root)
                diagnosis = recovery.diagnose(env.workspace.root)
            if diagnosis["classification"] in (recovery.DAMAGED, recovery.NEEDS_REPAIR):
                return _stop(state_dir, state, FAILED, f"after cycle {state['cycle']} the workspace is {diagnosis['classification']}: {diagnosis.get('damaged') or diagnosis.get('needs_repair')}")
            _log(state_dir, f"cycle {state['cycle']} done: {fetcher.total} requests in all, {sum(fetcher.items_by_outlet.values())} item requests")
            write_state(state_dir, state)
            next_cycle = min(cycle_started + timedelta(seconds=budget.cycle_seconds), fetcher.last_decision_at)
            while env.clock() < next_cycle and not (state_dir / STOP_FILE).exists() and state["preservation"] == "nothing pending":
                env.sleep(min(5.0, max(0.01, (next_cycle - env.clock()).total_seconds())))
        if (state_dir / STOP_FILE).exists() and env.clock() < fetcher.last_decision_at:
            return _stop(state_dir, state, STOPPED, "a stop was requested")
        state["status"] = FINALIZING
        write_state(state_dir, state)
        _log(state_dir, f"no further request: the deadline is {state['deadline_at_utc']}")
        return state


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
        waiting = {subject for subject, held in env.workspace.ledger().states().items() if held == "PRESERVATION_PENDING"}
        if waiting:
            identifiers |= set(canary_driver.packs_holding(env.workspace, waiting))
    for identifier in sorted(identifiers):
        if pack.pack_outlet(identifier) in wanted:
            preserved = canary_driver._preserve(env.workspace, [identifier], env.preservation_root, env.spool_root, env.spool_policy, env.clock)
            canary_driver._derive(env.workspace, env.registry, env.preservation_root, preserved, extraction.BASELINE, env.clock)
            done[identifier] = preserved[identifier]["state"]
    return done


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
        diagnosis = recovery.diagnose(env.workspace.root, env.preservation_root(), env.registry)
        check("recovery_diagnosis", diagnosis["classification"] == recovery.CLEAN, f"{diagnosis['classification']}; identity {diagnosis.get('identity_rebuild', {}).get('status')}")
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
            "preservation": state["preservation"], "holds": state["holds"], "errors": len(state["errors"]), "restarts": state["restarts"],
            "last_checkpoint_at": state["last_checkpoint_at"], "finalized": state["finalized"]}


__all__ = ["IntakeBudget", "IntakeFetcher", "IntakeStopped", "Environment", "build_plan", "validate_plan", "run", "finalize", "initial_state", "read_state",
           "write_state", "status_line", "selector", "novelty", "used_from_evidence", "WorkspaceBusy"]
