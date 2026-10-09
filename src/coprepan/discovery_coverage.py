"""What a discovery pass listed and what its limits kept out — a derived report (CPD-0019 §5).

A discovery budget bounds candidates and documents per pass. Whether that bound costs coverage is a
question about evidence, not about the limit: this module answers it from the discovery tables alone
— how many entries a channel listed, how many became candidates, how many were turned away because
the candidate budget of the pass was spent, which documents a channel named and nobody read — and,
where the channel states publication instants, whether what was turned away is older or newer than
what was kept.

It reads; it changes nothing, switches nothing and recommends no limit.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Mapping

from . import discovery, naming

COVERAGE_SCHEMA = naming.schema_id("discovery-coverage", 1)
BUDGET_PROBLEM = "candidate_budget_exhausted"


def _instant(text: str | None) -> datetime | None:
    """A publication hint as an instant: ISO 8601 or the RFC 822 form of feeds; else ``None``."""
    if not text:
        return None
    for parse in (datetime.fromisoformat, parsedate_to_datetime):
        try:
            value = parse(text.strip())
        except (TypeError, ValueError):
            continue
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return None


def _span(instants: list[datetime]) -> dict[str, Any] | None:
    if not instants:
        return None
    return {"oldest": min(instants).astimezone(timezone.utc).isoformat(), "newest": max(instants).astimezone(timezone.utc).isoformat(),
            "dated_entries": len(instants)}


def coverage(tables: discovery.DiscoveryTables, run_id: str | None = None) -> dict[str, Any]:
    """Per channel (of one run, or of every run): listed, kept, turned away, named and not read."""
    inputs = [row for row in tables.inputs if run_id is None or row["run_id"] == run_id]
    events = [row for row in tables.events.values() if run_id is None or row["run_id"] == run_id]
    read_urls: dict[str, set[str]] = {}
    for row in inputs:
        if row["outcome"] != discovery.OUTCOME_UNAVAILABLE:
            read_urls.setdefault(row["channel_id"], set()).update({row["document_url"], row.get("final_url") or row["document_url"]})
    channels: dict[str, Any] = {}
    for channel_id in sorted({row["channel_id"] for row in inputs} | {row["channel_id"] for row in events}):
        own_inputs = [row for row in inputs if row["channel_id"] == channel_id]
        own = [row for row in events if row["channel_id"] == channel_id]
        items = [row for row in own if row["relation"] == discovery.RELATION_ITEM]
        kept = [row for row in items if row["candidate_id"] is not None]
        dropped = [row for row in items if row["problem"] == BUDGET_PROBLEM]
        named = [row for row in own if row["relation"] in (discovery.RELATION_CHILD_DOCUMENT, discovery.RELATION_NEXT_PAGE) and row["resolved_url"]]
        named_urls = list(dict.fromkeys(row["resolved_url"] for row in named))
        not_read = [url for url in named_urls if url not in read_urls.get(channel_id, set())]
        kept_at = [at for at in (_instant(row["hints"].get("published") or row["hints"].get("lastmod")) for row in kept) if at]
        dropped_at = [at for at in (_instant(row["hints"].get("published") or row["hints"].get("lastmod")) for row in dropped) if at]
        channels[channel_id] = {
            "documents": dict(sorted(Counter(row["outcome"] for row in own_inputs).items())),
            "document_problems": dict(sorted(Counter(problem for row in own_inputs for problem in row["problems"]).items())),
            "item_entries": len(items),
            "item_entries_with_candidate": len(kept),
            "distinct_candidates_listed": len({row["candidate_id"] for row in kept}),
            "item_entries_turned_away_by_candidate_budget": len(dropped),
            "other_item_problems": dict(sorted(Counter(row["problem"] for row in items if row["problem"] and row["problem"] != BUDGET_PROBLEM).items())),
            "documents_named": len(named_urls), "documents_named_and_not_read": len(not_read),
            "not_read_sample": not_read[:5],
            "kept_dates": _span(kept_at), "turned_away_dates": _span(dropped_at),
            # Only where both sides carry dates: how many of the entries turned away are newer than
            # the oldest entry that was kept. 0 means the budget cut the old end of the listing.
            "turned_away_newer_than_oldest_kept": (sum(1 for at in dropped_at if at > min(kept_at)) if kept_at and dropped_at else None),
        }
    totals = Counter()
    for record in channels.values():
        for key in ("item_entries", "item_entries_with_candidate", "item_entries_turned_away_by_candidate_budget",
                    "documents_named", "documents_named_and_not_read"):
            totals[key] += record[key]
    return {"schema": COVERAGE_SCHEMA, "run_id": run_id, "parser_versions": sorted({row["parser"] for row in inputs}),
            "totals": dict(sorted(totals.items())), "channels": channels,
            "limits": ["a report of what was listed in the documents that were read; it cannot see what an unread document lists",
                       "dates are the channel's own hints, as written; an entry without a readable date is not in a date span"]}


def frontier(tables: discovery.DiscoveryTables, channel_id: str) -> list[Mapping[str, Any]]:
    """The documents a channel has named and no pass has read, in the order a pass would read them:
    where an incremental continuation would start. Derived from events and inputs; nothing is stored.
    """
    read = {url for row in tables.inputs if row["channel_id"] == channel_id and row["outcome"] != discovery.OUTCOME_UNAVAILABLE
            for url in (row["document_url"], row.get("final_url") or row["document_url"])}
    seen: dict[str, discovery.ChannelEntry] = {}
    for row in tables.events.values():
        if row["channel_id"] == channel_id and row["relation"] == discovery.RELATION_CHILD_DOCUMENT and row["resolved_url"] \
                and row["resolved_url"] not in read:
            # the latest statement about a child wins: its lastmod is what a later pass would see
            seen[row["resolved_url"]] = discovery.ChannelEntry(row["position"], row["relation"], row["observed_url"],
                                                               row["resolved_url"], row["hints"])
    ordered = sorted(seen.values(), key=discovery.expansion_priority)
    return [{"url": entry.url, "lastmod": entry.hints.get("lastmod"), "priority": list(discovery.expansion_priority(entry)[:2])}
            for entry in ordered]
