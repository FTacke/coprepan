"""An acquisition run over HTTP (CPD-0006 §6, CPD-0007).

```text
registered channel → [policy gate] → fetch channel document → discovery (events, candidates)
    candidate → qualification → schedule (is it due?) → [policy gate] → fetch item
        → fetch record → open pack → ledger
```

followed, by the caller, by the stages that already exist: seal and preserve
(:func:`coprepan.core_pipeline.preserve_pack` — the entry that keeps a pack pending, in the outage
spool where one is usable, when the preservation target cannot be reached; CPD-0015), identity and extraction
(:func:`coprepan.core_pipeline.identify_and_extract`), admission labels
(:func:`coprepan.admission.label_pack`).

This module contains no network code of its own — it drives a fetcher — and no permission of its
own: whether anything may be requested is the policy gate's answer, per request, and *when* a
candidate is asked again is the schedule policy's. With the tracked configuration nothing external
can be requested at all.

Every request is written to a request log *before* it is made and again when it has ended. A
planned request without an end is an interrupted one: visible, and repeatable by a later call.
Everything a server sent — error pages, robots files, the answers of failed attempts — is
recorded as a fetch. No row of the log is ever rewritten.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import __version__, acquisition, candidate_filter, crawler_identity, discovery, naming, pack, schedule
from .acquisition import AcquisitionRun
from .core_pipeline import COMPONENT_VERSIONS, Workspace, record_exchange
from .exclusive import writes_workspace
from .fetcher import FINAL_FETCHED, FetchOutcome, FetchRequest, HttpFetcher, request_id
from .identity import IdentityError, canonical_url_key, format_instant
from .jsonl import append_chained, read_chained
from .registry import Registry

REQUEST_LOG_SCHEMA = naming.schema_id("request-log", 2)  # v2: chained rows (CPD-0010)
EVENT_PLANNED, EVENT_FINISHED = "PLANNED", "FINISHED"
PERMANENT_REDIRECTS = (301, 308)


def http_fetch_run(started_at: datetime, outlet_ids: Sequence[str], configuration: dict[str, Any],
                   identity: crawler_identity.CrawlerIdentity) -> AcquisitionRun:
    """The run identity of an HTTP acquisition: it covers the crawler identity and the limits."""
    return AcquisitionRun(
        kind=acquisition.RUN_KIND_HTTP_FETCH,
        started_at=started_at,
        outlet_ids=tuple(sorted(set(outlet_ids))),
        discovery_method="registered_channels",
        software_version=__version__,
        component_versions={**COMPONENT_VERSIONS, "fetcher": crawler_identity.FETCHER_VERSION,
                            "channel_parser": discovery.PARSER_VERSION, "fetch_planner": schedule.PLANNER_VERSION,
                            "candidate_filter": candidate_filter.GENERIC_RULESET},
        configuration={**configuration, "crawler_identity_sha256": identity.sha256, "user_agent": identity.user_agent},
    )


def request_log_path(workspace: Workspace) -> Path:
    return workspace.root / "requests" / "requests.jsonl"


def request_rows(workspace: Workspace) -> list[dict[str, Any]]:
    return read_chained(request_log_path(workspace), REQUEST_LOG_SCHEMA)


def discovery_tables(workspace: Workspace) -> discovery.DiscoveryTables:
    return discovery.DiscoveryTables(workspace.root / "discovery")


def qualification_table(workspace: Workspace) -> candidate_filter.QualificationTable:
    return candidate_filter.QualificationTable(workspace.root / "discovery" / "qualifications.jsonl")


def answered_candidates(workspace: Workspace) -> set[str]:
    """Candidates for which some request has ended with a response of any status."""
    return {row["candidate_id"] for row in request_rows(workspace)
            if row["event"] == EVENT_FINISHED and row["final"] == FINAL_FETCHED and row.get("candidate_id")}


def unfinished_requests(workspace: Workspace) -> list[dict[str, Any]]:
    """Requests that were planned and never ended: the process stopped in between."""
    rows = request_rows(workspace)
    finished = {row["request_id"] for row in rows if row["event"] == EVENT_FINISHED}
    return [row for row in rows if row["event"] == EVENT_PLANNED and row["request_id"] not in finished]


def derived_candidates(workspace: Workspace) -> dict[str, list[dict[str, Any]]]:
    """Every candidate row the evidence supports, by candidate id (CPD-0010).

    A candidate is derived state: either its first discovery event gave rise to it, or a request
    that was permanently redirected did (the request log row carries the target and its key).
    Both can name one candidate, in which case whichever came first made it and either row is
    consistent.
    """
    tables = discovery_tables(workspace)
    out: dict[str, list[dict[str, Any]]] = {
        identifier: [discovery.candidate_from_event(event)] for identifier, event in tables._first_event.items()}
    rows = request_rows(workspace)
    channel_of = {row["request_id"]: row["channel_id"] for row in rows if row["event"] == EVENT_PLANNED}
    for row in rows:
        result = row.get("result") or {}
        if row["event"] == EVENT_FINISHED and result.get("moved_permanently_to") and row.get("attributed_from") is None:
            out.setdefault(result["moved_permanently_to"], []).append({
                "candidate_id": result["moved_permanently_to"], "outlet_id": row["candidate_id"].split(":cand:")[0], "url_key": result["final_url_key"], "fetch_url": result["final_url"],
                "first_event_id": None, "first_channel_id": channel_of.get(row["request_id"]), "first_listed_at": row["finished_at"],
                "discovered_via": "permanent_redirect", "redirected_from": row["candidate_id"]})
    return out


def candidate_consistency(workspace: Workspace) -> dict[str, list[str]]:
    """The stored candidate table against what the evidence supports. Reads only."""
    derived, stored = derived_candidates(workspace), discovery_tables(workspace).candidates
    return {
        "missing": sorted(set(derived) - set(stored)),
        "unsupported": sorted(set(stored) - set(derived)),
        "different": sorted(identifier for identifier in set(stored) & set(derived)
                            if {k: v for k, v in stored[identifier].items() if k != "schema"} not in derived[identifier]),
    }


@writes_workspace("complete the candidate table")
def complete_candidates(workspace: Workspace) -> list[str]:
    """Append the candidates the evidence supports and the table lacks. Never changes or removes
    a row: a stored candidate that the evidence does not support is reported by
    :func:`candidate_consistency` and left for a person.
    """
    derived, tables = derived_candidates(workspace), discovery_tables(workspace)
    added = []
    for identifier in sorted(set(derived) - set(tables.candidates)):
        tables.add_candidate(derived[identifier][0])
        added.append(identifier)
    return added


def _own_key(rules, url: str | None) -> str | None:
    try:
        return canonical_url_key(rules, requested_url=url).key if url else None
    except IdentityError:
        return None


@writes_workspace("HTTP acquisition run")
def run_http_acquisition(
    workspace: Workspace,
    registry: Registry,
    run: AcquisitionRun,
    outlet_id: str,
    *,
    fetcher: HttpFetcher,
    channel_ids: Sequence[str],
    budget: discovery.DiscoveryBudget,
    max_item_fetches: int,
    schedule_policy: schedule.SchedulePolicy,
    clock: Callable[[], datetime],
    candidate_rules: Mapping[str, Mapping[str, Any]] | None = None,
    use_robots_sitemaps: bool = False,
    select_due: Callable[[Sequence[schedule.CandidateState], Any], Sequence[schedule.CandidateState]] | None = None,
    tables: discovery.DiscoveryTables | None = None,
) -> dict[str, Any]:
    """Discover through the given channels of one registered outlet and fetch what is due.

    ``select_due``: which of the due candidates are requested, and in which order — given every due
    candidate and the discovery tables, it returns the ones to ask for; at most ``max_item_fetches``
    of them are. Without it the planner's own order holds (oldest due first). It chooses among what
    the planner says is due and what the filter qualified; it can add nothing.

    ``tables``: the discovery tables of this workspace as the caller has loaded them — for a caller
    that makes many calls in one process and is the workspace's only writer (the intake controller).
    They were authenticated when they were loaded, and every row this call adds is added to them.
    Without it they are read, and authenticated, at every call.

    Resumable: a second call with the same run completes what the first left undone. Returns a
    summary; everything it says is also on record in the workspace.

    ``use_robots_sitemaps``: also read the sitemaps an origin's robots file names, as one more
    discovery source (recorded under the reserved source ``…:ch:robots_sitemaps``). Off unless
    asked for: which sources an outlet is read through is a registration matter.
    """
    outlet = registry.resolve(outlet_id)
    rules = registry.url_rules(outlet_id)
    channels = {channel["channel_id"]: channel for channel in outlet["channels"]}
    unknown = [identifier for identifier in channel_ids if identifier not in channels]
    if unknown:
        raise acquisition.AcquisitionError(f"not channels of {outlet_id}: {unknown}")
    if run.kind != acquisition.RUN_KIND_HTTP_FETCH:
        raise acquisition.AcquisitionError(f"an HTTP acquisition needs a run of kind http_fetch, not {run.kind}")
    # The evidence this run adds to must authenticate before the first request is made.
    request_rows(workspace)
    tables = discovery_tables(workspace) if tables is None else tables
    acquisition.open_run(workspace.root, run)
    ledger = workspace.ledger()
    packs: dict[str, pack.OpenPack] = {}
    log = request_log_path(workspace)
    finals: Counter[str] = Counter()
    recorded: Counter[str] = Counter()

    def record(outlet_of: str, exchange: acquisition.RecordedExchange) -> str:
        fetch_record, status = record_exchange(workspace, ledger, packs, run, outlet_of, exchange)
        recorded[status] += 1
        return fetch_record["fetch_id"]

    def result_of(request: FetchRequest, outcome: FetchOutcome) -> dict[str, Any]:
        """What scheduling needs to know about how a request ended — a summary of recorded facts."""
        last = outcome.last
        if last is None:
            return {}
        result: dict[str, Any] = {"status": last.status, "final_url": last.final_url, "failure_reason": last.failure_reason,
                                  "redirect_statuses": list(last.redirect_statuses),
                                  "redirect_not_followed": last.redirect_not_followed,
                                  "revalidates": dict(last.revalidates) if last.revalidates else None}
        if last.body is not None:
            result.update(acquisition.validators_of(last.response_headers))
            result["body_sha256"] = acquisition.sha256_bytes(last.body) if last.status != 304 else None
            final_key = _own_key(rules, last.final_url)
            if (request.fetch_kind == acquisition.FETCH_KIND_ITEM and request.candidate_id and final_key
                    and any(status in PERMANENT_REDIRECTS for status in last.redirect_statuses)):
                target = discovery.candidate_id(outlet_id, final_key)
                if target != request.candidate_id:
                    result["moved_permanently_to"], result["final_url_key"] = target, final_key
        return result

    def fetch(request: FetchRequest) -> tuple[FetchOutcome, list[str]]:
        planned_at = clock()
        identifier = request_id(request, planned_at)
        append_chained(log, REQUEST_LOG_SCHEMA, {
            "event": EVENT_PLANNED, "request_id": identifier, "run_id": run.run_id, "url": request.url,
            "outlet_id": request.outlet_id, "fetch_kind": request.fetch_kind, "channel_id": request.channel_id,
            "candidate_id": request.candidate_id, "conditional": bool(request.conditional_headers),
            "expansion_depth": request.expansion_depth, "planned_at": format_instant(planned_at)})
        outcome = fetcher.fetch(request, planned_at=planned_at)
        fetch_ids = [record(request.outlet_id, exchange) for exchange in outcome.exchanges]
        while fetcher.robots_exchanges:  # robots answers are evidence of the decision: preserved like any fetch
            record(*fetcher.robots_exchanges.pop(0))
        result = result_of(request, outcome)
        finished = {
            "event": EVENT_FINISHED, "request_id": identifier, "run_id": run.run_id, "url": request.url,
            "fetch_kind": request.fetch_kind, "candidate_id": request.candidate_id, "final": outcome.final,
            "policy_decision": outcome.decision.decision, "policy_reasons": list(outcome.decision.reasons),
            "policy_version": outcome.decision.policy_version, "retry_at": outcome.decision.retry_at,
            "policy_hints": {"robots_crawl_delay": outcome.decision.evidence.get("robots_crawl_delay")},
            # The three layers of CPD-0017, as the gate stated them for this request.
            "policy_layers": {name: outcome.decision.evidence.get(name) for name in (
                "robots_evidence", "robots_rule", "robots_txt_sha256", "research_tdm", "acquisition_decision", "hold_class",
                "access_class_observed", "override")},
            "fetch_ids": fetch_ids, "result": result,
            "attempts": [{"number": a.number, "retry": a.retry, "delay_seconds": a.delay_seconds,
                          "retry_after": a.retry_after} for a in outcome.attempts],
            "finished_at": format_instant(clock())}
        append_chained(log, REQUEST_LOG_SCHEMA, finished)
        if result.get("moved_permanently_to"):
            # The answer belongs to another URL of the outlet for good. That URL becomes a
            # candidate of its own, already answered by this very request; the old candidate is
            # never asked again. Both rows stay: nothing about the old URL is lost.
            target = result["moved_permanently_to"]
            tables.add_candidate({"candidate_id": target, "outlet_id": outlet_id, "url_key": result["final_url_key"],
                                  "fetch_url": result["final_url"], "first_event_id": None,
                                  "first_channel_id": request.channel_id, "first_listed_at": finished["finished_at"],
                                  "discovered_via": "permanent_redirect", "redirected_from": request.candidate_id})
            append_chained(log, REQUEST_LOG_SCHEMA, {**finished, "candidate_id": target, "attributed_from": request.candidate_id,
                                                 "result": {**result, "moved_permanently_to": None}})
        finals[f"{request.fetch_kind}:{outcome.final}"] += 1
        return outcome, fetch_ids

    def provider_for(channel_id: str | None):
        def provider(url: str, depth: int):
            outcome, fetch_ids = fetch(FetchRequest(url, outlet_id, acquisition.FETCH_KIND_CHANNEL_DOCUMENT, channel_id,
                                                    expansion_depth=depth))
            last = outcome.last
            if outcome.final != FINAL_FETCHED or last is None:
                reason = outcome.decision.reasons[0] if not outcome.attempts else (last.failure_reason or "no_response")
                return discovery.DocumentUnavailable(url, f"{outcome.final}: {reason}", fetch_ids[-1] if fetch_ids else None)
            if not 200 <= last.status < 300:
                return discovery.DocumentUnavailable(url, f"http_{last.status}", fetch_ids[-1])
            return discovery.ChannelDocument(url, last.final_url or url, fetch_ids[-1], last.body,
                                             acquisition._content_type(last.response_headers),
                                             acquisition.content_encoding_of(last.response_headers))
        return provider

    discoveries = []

    def discover(source_id: str, start_url: str, gate_channel: str | None) -> None:
        result = discovery.discover_channel(tables, rules, channel_id=source_id, start_url=start_url,
                                            provider=provider_for(gate_channel), budget=budget, run_id=run.run_id,
                                            discovered_at=clock())
        discoveries.append({"channel_id": source_id, "start_url": start_url, "documents_read": result.documents_read,
                            "events_new": result.events_new, "candidates_new": len(result.candidates_new),
                            "stopped_by": result.stopped_by, "notes": result.notes})

    for channel_id in channel_ids:
        discover(channel_id, channels[channel_id]["url_history"][-1]["url"], channel_id)
    if use_robots_sitemaps:
        # One more discovery input, with no special standing: what a robots file names is read
        # like any other channel document, through the same gate and the same budget.
        registered = {channel["url_history"][-1]["url"] for channel in channels.values()}
        source = f"{outlet_id}:ch:{discovery.ROBOTS_SITEMAP_SLUG}"
        for sitemap in sorted({url for evidence in fetcher.robots_seen(outlet_id) for url in evidence.rules.sitemaps}):
            if sitemap not in registered:
                discover(source, sitemap, None)

    # Qualification: every known candidate gets a decision under the current rules, on record.
    qualifications = qualification_table(workspace)
    channel_keys = frozenset(key for key in (_own_key(rules, c["url_history"][-1]["url"]) for c in channels.values()) if key)
    outlet_rules = (candidate_rules or {}).get(outlet_id)
    listing_ids = frozenset(c["channel_id"] for c in channels.values() if c["kind"] in candidate_filter.LISTING_KINDS)

    def own_candidates() -> dict[str, dict[str, Any]]:
        """The candidates of *this* outlet. A workspace holds the candidates of every outlet that was
        ever read in it; an outlet's run qualifies, schedules and requests its own and no other
        (canary finding F3: the others were planned under this outlet's id and refused at the gate).
        """
        return {identifier: row for identifier, row in tables.candidates.items() if row["outlet_id"] == outlet_id}

    def qualify_all() -> tuple[dict[str, Any], dict[str, Any]]:
        decided_at = format_instant(clock())
        # What decides that a candidate was listed by a listing is the **document**, not only the kind the channel is
        # registered as (wave B, finding F9: a registered feed URL redirected to the home page, the page was read as an
        # HTML listing, and what it linked — sections among the articles — was requested without an allow rule).
        html_inputs = {row["input_fetch_id"] for row in tables.inputs if row.get("format") == "html_listing"}

        def listings_for(row: dict[str, Any]) -> frozenset[str]:
            first = tables.events.get(row["first_event_id"])
            return listing_ids | {row["first_channel_id"]} if first is not None and first["input_fetch_id"] in html_inputs else listing_ids

        decided = {identifier: qualifications.decide(row, outlet_rules=outlet_rules, channel_url_keys=channel_keys,
                                                     run_id=run.run_id, decided_at=decided_at, listing_channel_ids=listings_for(row))
                   for identifier, row in own_candidates().items()}
        return decided, {identifier: tables.candidates[identifier] for identifier, row in decided.items()
                         if row["decision"] == candidate_filter.QUALIFIED}

    decisions, qualified = qualify_all()

    # Schedule: which qualified candidates are due now.
    due, _ = schedule.plan(qualified, request_rows(workspace), schedule_policy, now=clock(),
                           current_policy_version=fetcher.gate.policy["policy_version"],
                           limit=max_item_fetches if select_due is None else len(qualified))
    if select_due is not None:
        allowed = {state.candidate_id for state in due}
        due = [state for state in select_due(due, tables) if state.candidate_id in allowed][:max_item_fetches]
    for item in due:
        candidate = tables.candidates[item.candidate_id]
        # A candidate first seen through the robots source has no registered channel to be gated under.
        gate_channel = candidate["first_channel_id"] if candidate["first_channel_id"] in channels else None
        # A conditional request asks the server to confirm a body. It is only sent for a body
        # that is preserved: the request log says a response came back, the ledger says whether
        # its bytes are safe. Otherwise the page is simply asked for again.
        conditional = dict(item.conditional or {})
        if conditional and ledger.state(conditional["revalidates_fetch_id"]) != "RAW_PRESERVED":
            conditional = {}
        fetch(FetchRequest(candidate["fetch_url"], outlet_id, acquisition.FETCH_KIND_ITEM, gate_channel,
                           candidate["candidate_id"], **conditional))

    decisions, qualified = qualify_all()  # a permanent redirect may have added a candidate during the run
    _, states = schedule.plan(qualified, request_rows(workspace), schedule_policy, now=clock(),
                              current_policy_version=fetcher.gate.policy["policy_version"], limit=0)
    return {
        "run_id": run.run_id, "open_pack_ids": sorted(packs), "discovery": discoveries,
        "requests": dict(sorted(finals.items())), "recorded": dict(sorted(recorded.items())),
        "candidates_known": len(own_candidates()),
        "qualification": dict(sorted(Counter(row["decision"] for row in decisions.values()).items())),
        "candidates_requested": len(due),
        "lifecycle": dict(sorted(Counter(state.state for state in states.values()).items())),
    }
