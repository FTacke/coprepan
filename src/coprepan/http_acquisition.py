"""An acquisition run over HTTP: channels → discovery → candidates → item fetches (CPD-0006 §6).

```text
registered channel → [policy gate] → fetch channel document → discovery (events, candidates)
    candidate → [policy gate] → fetch item → fetch record → open pack → ledger
```

followed, by the caller, by the stages that already exist: seal and promote
(:func:`coprepan.core_pipeline.seal_and_preserve`), identity and extraction
(:func:`coprepan.core_pipeline.identify_and_extract`).

This module contains no network code of its own — it drives a fetcher — and no permission of its
own: whether anything may be requested is the policy gate's answer, per request. With the tracked
policy and identity nothing external can be requested at all.

Every request is written to a request log *before* it is made and again when it has ended. A
planned request without an end is an interrupted one: visible, and repeatable by a later call.
Everything a server sent — error pages, robots files, the answers of failed attempts — is
recorded as a fetch.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Sequence

from . import __version__, acquisition, crawler_identity, discovery, naming, pack
from .acquisition import AcquisitionRun
from .core_pipeline import COMPONENT_VERSIONS, Workspace, record_exchange
from .fetcher import FINAL_FETCHED, FetchOutcome, FetchRequest, HttpFetcher, request_id
from .identity import format_instant
from .jsonl import append_row, read_rows
from .registry import Registry

REQUEST_LOG_SCHEMA = naming.schema_id("request-log", 1)
EVENT_PLANNED, EVENT_FINISHED = "PLANNED", "FINISHED"


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
                            "channel_parser": discovery.PARSER_VERSION},
        configuration={**configuration, "crawler_identity_sha256": identity.sha256, "user_agent": identity.user_agent},
    )


def request_log_path(workspace: Workspace) -> Path:
    return workspace.root / "requests" / "requests.jsonl"


def discovery_tables(workspace: Workspace) -> discovery.DiscoveryTables:
    return discovery.DiscoveryTables(workspace.root / "discovery")


def fetched_candidates(workspace: Workspace) -> set[str]:
    """Candidates for which a request has ended with a response. Until a re-fetch schedule exists
    (Phase 2), such a candidate is not requested again.
    """
    return {row["candidate_id"] for row in read_rows(request_log_path(workspace), REQUEST_LOG_SCHEMA)
            if row["event"] == EVENT_FINISHED and row["final"] == FINAL_FETCHED and row.get("candidate_id")}


def unfinished_requests(workspace: Workspace) -> list[dict[str, Any]]:
    """Requests that were planned and never ended: the process stopped in between."""
    rows = read_rows(request_log_path(workspace), REQUEST_LOG_SCHEMA)
    finished = {row["request_id"] for row in rows if row["event"] == EVENT_FINISHED}
    return [row for row in rows if row["event"] == EVENT_PLANNED and row["request_id"] not in finished]


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
    clock: Callable[[], datetime],
) -> dict[str, Any]:
    """Discover through the given channels of one registered outlet and fetch what is new.

    Resumable: a second call with the same run completes what the first left undone. Returns a
    summary; everything it says is also on record in the workspace.
    """
    outlet = registry.resolve(outlet_id)
    rules = registry.url_rules(outlet_id)
    channels = {channel["channel_id"]: channel for channel in outlet["channels"]}
    unknown = [identifier for identifier in channel_ids if identifier not in channels]
    if unknown:
        raise acquisition.AcquisitionError(f"not channels of {outlet_id}: {unknown}")
    if run.kind != acquisition.RUN_KIND_HTTP_FETCH:
        raise acquisition.AcquisitionError(f"an HTTP acquisition needs a run of kind http_fetch, not {run.kind}")
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

    def fetch(request: FetchRequest) -> tuple[FetchOutcome, list[str]]:
        planned_at = clock()
        identifier = request_id(request, planned_at)
        append_row(log, REQUEST_LOG_SCHEMA, {
            "event": EVENT_PLANNED, "request_id": identifier, "run_id": run.run_id, "url": request.url,
            "outlet_id": request.outlet_id, "fetch_kind": request.fetch_kind, "channel_id": request.channel_id,
            "candidate_id": request.candidate_id, "planned_at": format_instant(planned_at)})
        outcome = fetcher.fetch(request, planned_at=planned_at)
        fetch_ids = [record(request.outlet_id, exchange) for exchange in outcome.exchanges]
        while fetcher.robots_exchanges:  # robots answers are evidence of the decision: preserved like any fetch
            record(*fetcher.robots_exchanges.pop(0))
        append_row(log, REQUEST_LOG_SCHEMA, {
            "event": EVENT_FINISHED, "request_id": identifier, "run_id": run.run_id, "url": request.url,
            "fetch_kind": request.fetch_kind, "candidate_id": request.candidate_id, "final": outcome.final,
            "policy_decision": outcome.decision.decision, "policy_reasons": list(outcome.decision.reasons),
            "policy_version": outcome.decision.policy_version, "retry_at": outcome.decision.retry_at,
            "fetch_ids": fetch_ids,
            "attempts": [{"number": a.number, "retry": a.retry, "delay_seconds": a.delay_seconds,
                          "retry_after": a.retry_after} for a in outcome.attempts],
            "finished_at": format_instant(clock())})
        finals[f"{request.fetch_kind}:{outcome.final}"] += 1
        return outcome, fetch_ids

    tables = discovery_tables(workspace)
    discoveries = []
    for channel_id in channel_ids:
        def provider(url: str, depth: int, channel_id: str = channel_id):
            outcome, fetch_ids = fetch(FetchRequest(url, outlet_id, acquisition.FETCH_KIND_CHANNEL_DOCUMENT, channel_id))
            last = outcome.last
            if outcome.final != FINAL_FETCHED or last is None:
                reason = outcome.decision.reasons[0] if not outcome.attempts else (last.failure_reason or "no_response")
                return discovery.DocumentUnavailable(url, f"{outcome.final}: {reason}", fetch_ids[-1] if fetch_ids else None)
            if not 200 <= last.status < 300:
                return discovery.DocumentUnavailable(url, f"http_{last.status}", fetch_ids[-1])
            return discovery.ChannelDocument(url, last.final_url or url, fetch_ids[-1], last.body,
                                             acquisition._content_type(last.response_headers),
                                             acquisition.content_encoding_of(last.response_headers))

        result = discovery.discover_channel(
            tables, rules, channel_id=channel_id, start_url=channels[channel_id]["url_history"][-1]["url"],
            provider=provider, budget=budget, run_id=run.run_id, discovered_at=clock())
        discoveries.append({"channel_id": channel_id, "documents_read": result.documents_read,
                            "events_new": result.events_new, "candidates_new": len(result.candidates_new),
                            "stopped_by": result.stopped_by, "notes": result.notes})

    done = fetched_candidates(workspace)
    planned = [row for identifier, row in tables.candidates.items() if identifier not in done][:max_item_fetches]
    for candidate in planned:
        fetch(FetchRequest(candidate["fetch_url"], outlet_id, acquisition.FETCH_KIND_ITEM,
                           candidate["first_channel_id"], candidate["candidate_id"]))
    return {
        "run_id": run.run_id, "open_pack_ids": sorted(packs), "discovery": discoveries,
        "requests": dict(sorted(finals.items())), "recorded": dict(sorted(recorded.items())),
        "candidates_known": len(tables.candidates), "candidates_requested": len(planned),
        "candidates_left": max(0, len(tables.candidates) - len(done) - len(planned)),
    }
