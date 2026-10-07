"""Re-fetch semantics: candidate lifecycle and a deterministic fetch plan (CPD-0007 §3).

Four things kept apart:

* the **fetch history** — the request log and the fetch records. Append-only; nothing here ever
  rewrites a row of it;
* the **candidate lifecycle** — a state *derived* from that history each time it is asked for,
  never stored, so it cannot drift from the evidence;
* the **document versions** — identity's business; a re-fetch only supplies new evidence;
* the **schedule** — a pure function ``(history, policy, now) → plan``. No daemon, no sleep, no
  adaptive scoring: the same history under the same policy at the same instant gives the same plan.

Every interval comes from the schedule policy (``config/schedule_policy.json``), which is part of
the open acquisition policy and ships ``NOT_DECIDED``. There is no built-in pace.

A candidate is never abandoned for good by a rule: ``SUSPENDED`` comes back after a cooldown,
``RETIRED`` and ``SETTLED`` are reversible by a new listing or a new policy, and none of them
removes anything.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import naming
from .identity import format_instant
from .storage_roots import CHECKOUT

SCHEDULE_SCHEMA = naming.schema_id("schedule-policy", 1)
DEFAULT_SCHEDULE_FILE = CHECKOUT / "config" / "schedule_policy.json"
PLANNER_VERSION = "fetch-planner/1"

# Outcome of one finished request, as the planner reads it.
SUCCESS, NOT_MODIFIED, NOT_FOUND, GONE = "SUCCESS", "NOT_MODIFIED", "NOT_FOUND", "GONE"
TRANSIENT_FAILURE, REFUSED_BY_SERVER, REDIRECT_NOT_FOLLOWED = "TRANSIENT_FAILURE", "REFUSED_BY_SERVER", "REDIRECT_NOT_FOLLOWED"
DENIED_BY_POLICY, DEFERRED_BY_POLICY, MOVED_PERMANENTLY = "DENIED_BY_POLICY", "DEFERRED_BY_POLICY", "MOVED_PERMANENTLY"

# Candidate lifecycle states (derived).
NEVER_FETCHED, FETCHED, SETTLED = "NEVER_FETCHED", "FETCHED", "SETTLED"
FAILING, SUSPENDED, ABSENT, RETIRED = "FAILING", "SUSPENDED", "ABSENT", "RETIRED"
REFUSED, DENIED, DEFERRED, MOVED = "REFUSED", "DENIED", "DEFERRED", "MOVED"
STATES = (NEVER_FETCHED, FETCHED, SETTLED, FAILING, SUSPENDED, ABSENT, RETIRED, REFUSED, DENIED, DEFERRED, MOVED)


class ScheduleNotDecided(RuntimeError):
    """The schedule policy is undecided or incomplete: no fetch is planned."""


@dataclass(frozen=True)
class SchedulePolicy:
    """Every interval and limit of re-fetching. All required; none has a default."""

    version: str
    revisit_after_success_seconds: float     # first revisit after a successful fetch
    revisit_backoff_factor: float            # each unchanged revisit multiplies the interval
    revisit_max_interval_seconds: float
    revisit_window_seconds: float            # after this long since the first success, stop revisiting
    retry_after_failure_seconds: float       # first retry after a transient failure
    failure_backoff_factor: float
    failure_max_interval_seconds: float
    max_consecutive_failures: int            # then SUSPENDED until the cooldown has passed
    failure_cooldown_seconds: float
    gone_recheck_seconds: float              # 404 / 410: look again after this long …
    max_gone_rechecks: int                   # … this many times, then RETIRED
    denied_recheck_seconds: float            # refused by the server or denied by an unchanged policy
    use_conditional_requests: bool

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version or self.version == "undecided":
            raise ScheduleNotDecided("a schedule policy has a version")
        for item in fields(self):
            value = getattr(self, item.name)
            if item.name == "version":
                continue
            if item.name == "use_conditional_requests":
                if not isinstance(value, bool):
                    raise ScheduleNotDecided("use_conditional_requests is true or false")
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ScheduleNotDecided(f"{item.name} is a non-negative number, not {value!r}")
        if self.revisit_backoff_factor < 1 or self.failure_backoff_factor < 1:
            raise ScheduleNotDecided("a backoff factor is at least 1")


def load_schedule_policy(path: Path | None = None) -> SchedulePolicy:
    """The decided schedule policy, or a refusal. Nothing is filled in for a missing value."""
    try:
        document = json.loads(Path(path or DEFAULT_SCHEDULE_FILE).read_text(encoding="utf-8"))
        if document["schema"] != SCHEDULE_SCHEMA:
            raise ValueError(f"schema {document['schema']!r}")
        if document["status"] != "DECIDED":
            raise ScheduleNotDecided("the schedule policy is NOT_DECIDED (config/schedule_policy.json)")
        return SchedulePolicy(**{item.name: document[item.name] for item in fields(SchedulePolicy)})
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ScheduleNotDecided(f"the schedule policy is not usable: {error}") from error


# --- history ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Outcome:
    """One finished request of a candidate, reduced to what scheduling needs."""

    kind: str
    at: datetime
    body_sha256: str | None = None
    fetch_id: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    not_before: datetime | None = None       # a Retry-After or a suppression end
    policy_version: str | None = None
    moved_to: str | None = None
    detail: str | None = None


def _instant(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(timezone.utc)


def outcome_of(row: Mapping[str, Any]) -> Outcome:
    """Classify a ``FINISHED`` request-log row. Total: every row gets exactly one kind."""
    at = _instant(row["finished_at"])
    result = row.get("result") or {}
    not_before = _instant(row["retry_at"]) if row.get("retry_at") else None
    common = dict(at=at, policy_version=row.get("policy_version"), fetch_id=(row.get("fetch_ids") or [None])[-1])
    if row["final"] == "DENIED":
        return Outcome(DENIED_BY_POLICY, detail=(row.get("policy_reasons") or ["unknown"])[0], **common)
    if row["final"] == "DEFERRED":
        return Outcome(DEFERRED_BY_POLICY, not_before=not_before, detail=(row.get("policy_reasons") or ["unknown"])[0], **common)
    retry_after = max((_instant(a["retry_after"]) for a in row.get("attempts", []) if a.get("retry_after")), default=None)
    if row["final"] != "FETCHED":
        return Outcome(TRANSIENT_FAILURE, not_before=retry_after, detail=result.get("failure_reason"), **common)
    status = result.get("status")
    if result.get("moved_permanently_to"):
        return Outcome(MOVED_PERMANENTLY, moved_to=result["moved_permanently_to"], **common)
    if isinstance(status, int) and 200 <= status < 300:
        return Outcome(SUCCESS, body_sha256=result.get("body_sha256"), etag=result.get("etag"),
                       last_modified=result.get("last_modified"), **common)
    if status == 304:
        return Outcome(NOT_MODIFIED if result.get("revalidates") else TRANSIENT_FAILURE,
                       body_sha256=(result.get("revalidates") or {}).get("body_sha256"),
                       detail=None if result.get("revalidates") else "304_without_a_conditional_request", **common)
    if status == 404:
        return Outcome(NOT_FOUND, **common)
    if status == 410:
        return Outcome(GONE, **common)
    if status == 429 or (isinstance(status, int) and status >= 500):
        return Outcome(TRANSIENT_FAILURE, not_before=retry_after, detail=f"http_{status}", **common)
    if isinstance(status, int) and 300 <= status < 400:
        return Outcome(REDIRECT_NOT_FOLLOWED, detail=result.get("redirect_not_followed"), **common)
    return Outcome(REFUSED_BY_SERVER, detail=f"http_{status}", **common)


def histories(request_rows: Sequence[Mapping[str, Any]]) -> dict[str, list[Outcome]]:
    """Per candidate, its finished item requests in the order they finished."""
    out: dict[str, list[Outcome]] = {}
    for row in request_rows:
        if row.get("event") == "FINISHED" and row.get("fetch_kind") == "item" and row.get("candidate_id"):
            out.setdefault(row["candidate_id"], []).append(outcome_of(row))
    return out


# --- lifecycle and plan -----------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateState:
    candidate_id: str
    state: str
    due_at: datetime | None
    reason: str
    attempts: int
    conditional: Mapping[str, str] | None = None
    moved_to: str | None = None

    def as_row(self) -> dict[str, Any]:
        return {"candidate_id": self.candidate_id, "state": self.state,
                "due_at": format_instant(self.due_at) if self.due_at else None, "reason": self.reason,
                "attempts": self.attempts, "conditional": dict(self.conditional) if self.conditional else None,
                "moved_to": self.moved_to, "planner": PLANNER_VERSION}


def _trailing(history: Sequence[Outcome], kinds: tuple[str, ...]) -> int:
    count = 0
    for outcome in reversed(history):
        if outcome.kind not in kinds:
            break
        count += 1
    return count


def lifecycle(candidate_id: str, first_listed_at: datetime, history: Sequence[Outcome], policy: SchedulePolicy,
              *, current_policy_version: str) -> CandidateState:
    """The state of one candidate and when — if ever — it is due again."""
    def state(name: str, due: datetime | None, reason: str, **extra: Any) -> CandidateState:
        return CandidateState(candidate_id, name, due, reason, len(history), **extra)

    if not history:
        return state(NEVER_FETCHED, first_listed_at, "listed and never requested")
    last = history[-1]
    seconds = lambda value: timedelta(seconds=value)  # noqa: E731

    if last.kind == MOVED_PERMANENTLY:
        return state(MOVED, None, "permanently redirected: the target is its own candidate", moved_to=last.moved_to)
    if last.kind in (SUCCESS, NOT_MODIFIED):
        successes = [o for o in history if o.kind in (SUCCESS, NOT_MODIFIED)]
        if last.at - successes[0].at >= seconds(policy.revisit_window_seconds):
            return state(SETTLED, None, "revisit window closed")
        unchanged, previous = 0, None
        for outcome in reversed(history):
            if outcome.kind not in (SUCCESS, NOT_MODIFIED):
                break
            if previous is not None and outcome.body_sha256 != previous:
                break
            previous = outcome.body_sha256
            unchanged += 1
        streak = unchanged - 1  # the first answer of a run of equal bodies is not "unchanged" yet
        interval = min(policy.revisit_after_success_seconds * policy.revisit_backoff_factor ** max(streak, 0),
                       policy.revisit_max_interval_seconds)
        conditional = None
        holder = next((o for o in reversed(history) if o.kind == SUCCESS), None)
        if policy.use_conditional_requests and holder is not None and holder.fetch_id and holder.body_sha256 \
                and holder.body_sha256 == last.body_sha256 and (holder.etag or holder.last_modified):
            conditional = {key: value for key, value in (("if_none_match", holder.etag), ("if_modified_since", holder.last_modified),
                                                         ("revalidates_fetch_id", holder.fetch_id),
                                                         ("revalidates_body_sha256", holder.body_sha256)) if value}
        return state(FETCHED, last.at + seconds(interval),
                     "unchanged since the previous answer" if streak > 0 else "answered; first revisit", conditional=conditional)
    if last.kind == TRANSIENT_FAILURE:
        failures = _trailing(history, (TRANSIENT_FAILURE,))
        if failures >= policy.max_consecutive_failures:
            return state(SUSPENDED, last.at + seconds(policy.failure_cooldown_seconds),
                         f"{failures} consecutive failures; due again after the cooldown")
        wait = min(policy.retry_after_failure_seconds * policy.failure_backoff_factor ** (failures - 1),
                   policy.failure_max_interval_seconds)
        due = last.at + seconds(wait)
        if last.not_before is not None and last.not_before > due:
            due = last.not_before  # the server asked for more patience than the policy's backoff
        return state(FAILING, due, f"transient failure ({last.detail}); attempt {failures} of {policy.max_consecutive_failures}")
    if last.kind in (NOT_FOUND, GONE):
        gone = _trailing(history, (NOT_FOUND, GONE))
        if gone > policy.max_gone_rechecks:
            return state(RETIRED, None, f"absent on {gone} consecutive requests")
        return state(ABSENT, last.at + seconds(policy.gone_recheck_seconds), f"{last.kind.lower()}; recheck {gone} of {policy.max_gone_rechecks}")
    if last.kind in (REFUSED_BY_SERVER, REDIRECT_NOT_FOLLOWED):
        return state(REFUSED, last.at + seconds(policy.denied_recheck_seconds), f"{last.kind.lower()} ({last.detail})")
    if last.kind == DEFERRED_BY_POLICY:
        return state(DEFERRED, last.not_before or last.at + seconds(policy.denied_recheck_seconds), f"deferred by policy ({last.detail})")
    # DENIED_BY_POLICY: a decision of a policy version. A new version is a new question.
    if last.policy_version != current_policy_version:
        return state(DENIED, last.at, f"denied under {last.policy_version}; the policy is now {current_policy_version}")
    return state(DENIED, last.at + seconds(policy.denied_recheck_seconds), f"denied by policy ({last.detail})")


def plan(
    candidates: Mapping[str, Mapping[str, Any]],
    request_rows: Sequence[Mapping[str, Any]],
    policy: SchedulePolicy,
    *,
    now: datetime,
    current_policy_version: str,
    limit: int,
) -> tuple[list[CandidateState], dict[str, CandidateState]]:
    """``(due now, every state)``. Due candidates come oldest-due first, then by id; at most
    ``limit`` of them. A candidate is due when ``due_at <= now``.
    """
    by_candidate = histories(request_rows)
    states = {
        identifier: lifecycle(identifier, _instant(row["first_listed_at"]), by_candidate.get(identifier, []), policy,
                              current_policy_version=current_policy_version)
        for identifier, row in candidates.items()
    }
    due = sorted((s for s in states.values() if s.due_at is not None and s.due_at <= now),
                 key=lambda s: (s.due_at, s.candidate_id))
    return due[:limit], states
