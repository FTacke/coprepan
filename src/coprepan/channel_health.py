"""Channel health, derived from what was observed (CPD-0007 §5).

Health is a **reading of the evidence**, computed when asked for: the discovery inputs and events
of a channel, run by run. It is not a stored, mutable score — the legacy feed score was one, and
it deactivated healthy feeds for good because "no new URL" counted as "empty" (legacy archaeology
F-9).

Two consequences are built in:

* a channel that parses and lists nothing *new* is ``STALE``, which is information about the
  channel's output, not a fault and not a reason to stop reading it;
* **health activates and deactivates nothing.** Whether a channel is read is the registry's and
  the policy's decision. ``DISABLED`` here reports a switch somebody else set.

The two thresholds are inputs (:class:`HealthPolicy`); neither has a built-in value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from . import discovery

HEALTH_VERSION = "channel-health/1"
HEALTHY, DEGRADED, STALE, FAILING, DISABLED, UNKNOWN = "HEALTHY", "DEGRADED", "STALE", "FAILING", "DISABLED", "UNKNOWN"
STATES = (HEALTHY, DEGRADED, STALE, FAILING, DISABLED, UNKNOWN)


@dataclass(frozen=True)
class HealthPolicy:
    failing_after_consecutive_failures: int      # this many runs in a row whose channel document was not read
    stale_after_runs_without_new_candidates: int  # this many readable runs in a row that listed nothing new

    def __post_init__(self) -> None:
        for name in ("failing_after_consecutive_failures", "stale_after_runs_without_new_candidates"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} is a positive integer: {value!r}")


def observations(tables: discovery.DiscoveryTables, channel_id: str) -> list[dict[str, Any]]:
    """One observation per run that read the channel, in the order the runs first appear."""
    runs: dict[str, dict[str, Any]] = {}
    for row in tables.inputs:
        if row["channel_id"] != channel_id:
            continue
        seen = runs.setdefault(row["run_id"], {"run_id": row["run_id"], "read_at": row["read_at"], "root_outcome": None,
                                               "root_format": None, "root_final_url": None, "root_problems": [],
                                               "documents": 0, "documents_failed": 0, "events": 0,
                                               "candidates_listed": set(), "candidates_new": set()})
        seen["documents"] += 1
        if row["depth"] == 0 and seen["root_outcome"] is None:
            seen.update(root_outcome=row["outcome"], root_format=row["format"], root_final_url=row.get("final_url"),
                        root_problems=list(row["problems"]))
        elif row["outcome"] != discovery.OUTCOME_PARSED:
            seen["documents_failed"] += 1
    for event in tables.events.values():
        if event["channel_id"] != channel_id or event["run_id"] not in runs:
            continue
        seen = runs[event["run_id"]]
        seen["events"] += 1
        if event["candidate_id"]:
            seen["candidates_listed"].add(event["candidate_id"])
            if tables.candidates[event["candidate_id"]]["first_event_id"] == event["event_id"]:
                seen["candidates_new"].add(event["candidate_id"])
    return [{**seen, "candidates_listed": len(seen["candidates_listed"]), "candidates_new": len(seen["candidates_new"])}
            for seen in runs.values()]


def health(tables: discovery.DiscoveryTables, channel_id: str, policy: HealthPolicy, *,
           disabled_channels: Sequence[str] = ()) -> dict[str, Any]:
    """The health of a channel with the evidence it rests on. Pure; stores nothing."""
    seen = observations(tables, channel_id)
    readable = [o["root_outcome"] == discovery.OUTCOME_PARSED for o in seen]
    failures = next((index for index, ok in enumerate(reversed(readable)) if ok), len(readable))
    without_new = 0
    for observation in reversed(seen):
        if observation["root_outcome"] != discovery.OUTCOME_PARSED or observation["candidates_new"]:
            break
        without_new += 1
    notes = []
    roots = [o["root_final_url"] for o in seen if o["root_final_url"]]
    if len(roots) >= 2 and roots[-1] != roots[-2]:
        notes.append(f"the channel document was answered at another URL than before: {roots[-2]} → {roots[-1]}")

    if channel_id in disabled_channels:
        state, reason = DISABLED, "switched off in the acquisition policy; health does not switch it back on"
    elif not seen:
        state, reason = UNKNOWN, "never read"
    elif failures >= policy.failing_after_consecutive_failures:
        state, reason = FAILING, f"channel document not readable in the last {failures} run(s)"
    elif failures:
        state, reason = DEGRADED, f"channel document not readable in the last run: {'; '.join(seen[-1]['root_problems']) or seen[-1]['root_outcome']}"
    elif seen[-1]["documents_failed"]:
        state, reason = DEGRADED, f"{seen[-1]['documents_failed']} of {seen[-1]['documents']} documents of the last run were not readable"
    elif without_new >= policy.stale_after_runs_without_new_candidates:
        state, reason = STALE, f"readable, and nothing new listed in the last {without_new} run(s) — not a fault"
    else:
        state, reason = HEALTHY, "readable and listing"
    return {
        "channel_id": channel_id, "state": state, "reason": reason, "version": HEALTH_VERSION,
        "evidence": {
            "runs_observed": len(seen), "consecutive_unreadable_runs": failures,
            "consecutive_readable_runs_without_new_candidates": without_new,
            "last_readable_run": next((o["run_id"] for o in reversed(seen) if o["root_outcome"] == discovery.OUTCOME_PARSED), None),
            "last_run": {key: seen[-1][key] for key in ("run_id", "read_at", "root_outcome", "root_format", "documents",
                                                        "documents_failed", "events", "candidates_listed", "candidates_new")} if seen else None,
        },
        "notes": notes,
        "effect": "none: health is a report; it changes no registration and no policy",
    }


def report(tables: discovery.DiscoveryTables, channel_ids: Sequence[str], policy: HealthPolicy, *,
           disabled_channels: Sequence[str] = ()) -> list[dict[str, Any]]:
    return [health(tables, identifier, policy, disabled_channels=disabled_channels) for identifier in channel_ids]
