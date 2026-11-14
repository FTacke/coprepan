"""The weekend source qualification of 2026-11-14/15, evaluated from its own evidence (no request, no storage root but the runtime
workspace, read-only).

Input: the receipts of the canaries run under one delegated authorisation (``docs/canary/evidence/*/canary-receipt-*.json`` whose
``operator_authorization.authorization_id`` is the one named) and the runtime workspace (packs, request log, discovery tables).

Output, per tested outlet, four dimensions kept apart (no single READY):

* ``DISCOVERY_FUNCTIONAL`` -- a selected channel document answered 2xx and listed at least one entry;
* ``NEW_ARTICLE_COVERAGE`` -- entries dated within the window before the request (default 72 h: a weekend publishes less, so an
  older newest entry on a weekend is ``NO_RECENT_ENTRY_AT_THE_WEEKEND``, not a defect); ``UNDATED`` when the channel states no date;
* ``RAW_ACQUISITION_FUNCTIONAL`` -- item pages requested and answered 2xx, refusals and access signals;
* ``TEXT_EXTRACTION_QUALITY`` -- the experimental baseline extractor (``baseline_html``, not validated, CPD-0018) run on the local
  bytes: body characters, short pages, title, publication date found; and the two measured candidate rules of the article boundary
  (``header`` rule A, rule B) beside it, as a diagnostic -- no method is chosen here.

Every number is measured on the named evidence; the thresholds of the screening are stated in the output and are screening
choices, not scientific criteria.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from coprepan import canary_driver as D, core_pipeline, extraction as E, http_acquisition as H, pack, storage_roots  # noqa: E402

SCHEMA = "coprepan-weekend-qualification/v1"
SCREENING = {"recent_window_hours": 72, "stale_after_days": 7, "short_body_characters": 500, "good_median_characters": 1500,
             "short_share_limited": 0.2, "short_share_poor": 0.5, "raw_functional_min_pages": 3}


def coverage_of(channels, started, weekend):
    """``NEW_ARTICLE_COVERAGE`` from the channels as they answered: ``CURRENT`` (an entry dated inside the window), ``UNDATED``
    (entries, none dated), ``STALE_CHANNEL`` (the newest dated entry older than ``stale_after_days``: the channel is not kept
    current, whatever the day), ``NO_RECENT_ENTRY_AT_THE_WEEKEND`` / ``NO_RECENT_ENTRY`` (newest entry between the two), or
    ``NO_ENTRIES``. A quiet weekend is not a defect; a channel months behind is."""
    listed = sum(c["entries_listed"] for c in channels)
    if not listed:
        return "NO_ENTRIES"
    if sum(c["entries_recent"] for c in channels):
        return "CURRENT"
    newest = [_instant(c["newest_entry"]) for c in channels if c["newest_entry"]]
    if not newest:
        return "UNDATED"
    if max(newest) < started - timedelta(days=SCREENING["stale_after_days"]):
        return "STALE_CHANNEL"
    return "NO_RECENT_ENTRY_AT_THE_WEEKEND" if weekend else "NO_RECENT_ENTRY"


def _instant(text):
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            value = parsedate_to_datetime(text)
        except (TypeError, ValueError, IndexError):
            match = re.match(r"(\d{4}-\d{2}-\d{2})", text)
            if not match:
                return None
            value = datetime.fromisoformat(match.group(1))
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _hint_date(hints):
    for key in ("published", "lastmod", "updated", "news_publication_date", "pubDate", "date"):
        found = _instant((hints or {}).get(key))
        if found:
            return found
    return None


def _median(values):
    return statistics.median(values) if values else None


def _rule_chars(text):
    """Body characters under the baseline's ancestor rule as it is, and under the two measured repairs (A: only a non-body element
    between the container and the block excludes it; B: as A, but a nav/aside/footer above the container still excludes)."""
    parser = E._Parser()
    parser.feed(text)
    parser.close()
    container = next((name for name in E._CONTAINERS if name in parser.containers), None)
    as_is = rule_a = rule_b = 0
    title = False
    for item in parser.raw:
        anc = item["ancestors"]
        if item["tag"] == "h1" and not title:
            title = True
            continue
        if item["tag"] == "figcaption" or container is None or container not in anc:
            continue
        i = anc.index(container)
        below, above = anc[i + 1:], anc[:i]
        if not E._NON_BODY_ANCESTORS.intersection(anc):
            as_is += len(item["text"])
        if not E._NON_BODY_ANCESTORS.intersection(below):
            rule_a += len(item["text"])
            if not {"nav", "aside", "footer"}.intersection(above):
                rule_b += len(item["text"])
    return as_is, rule_a, rule_b


def build(workspace: core_pipeline.Workspace, receipts: list[dict], registry_doc: dict, matrix: dict) -> dict:
    by_id = {o["outlet_id"]: o for o in registry_doc["outlets"]}
    run_ids = {r["run_id"] for r in receipts}
    records = [r for r in D.fetch_records(workspace) if r["run_id"] in run_ids]
    tables = H.discovery_tables(workspace)
    events_by_run_channel = defaultdict(list)
    for event in tables.events.values():
        if event.get("run_id") in run_ids and event.get("relation") == "item":
            events_by_run_channel[(event["run_id"], event["channel_id"])].append(event)
    first_in_run = Counter()
    for row in tables.candidates.values():
        event = tables.events.get(row.get("first_event_id"))
        if event and event.get("run_id") in run_ids:
            first_in_run[row["outlet_id"]] += 1
    states = workspace.ledger().states()
    locate = {}
    for identifier in {p for r in receipts for p in r["packs"]}:
        path = workspace.packs / f"{identifier}.warc.gz"
        for entry in pack.scan(path, identifier):
            locate[entry.fetch_id] = (path, entry)
    outlets = {}
    for receipt in receipts:
        started = _instant(receipt["started_at"])
        window = started - timedelta(hours=SCREENING["recent_window_hours"])
        weekend = started.astimezone(timezone(timedelta(hours=1))).weekday() >= 5
        for oid in receipt["outlets"]:
            mine = [r for r in records if r["run_id"] == receipt["run_id"] and r["outlet_id"] == oid]
            channels = []
            for cid in receipt["channels"].get(oid, []):
                url = next(c["url_history"][-1]["url"] for c in by_id[oid]["channels"] if c["channel_id"] == cid)
                doc = [r for r in mine if r["fetch_kind"] == "channel_document" and r["request"]["requested_url"] == url]
                events = events_by_run_channel.get((receipt["run_id"], cid), [])
                dates = [d for d in (_hint_date(e.get("hints")) for e in events) if d]
                status = (str(doc[0]["response"]["status"]) if doc and doc[0]["outcome"] == "FETCHED"
                          else (f"failed:{doc[0]['failure_reason']}" if doc else "not requested"))
                channels.append({"channel_id": cid, "url": url, "kind": next(c["kind"] for c in by_id[oid]["channels"] if c["channel_id"] == cid),
                                 "status": status, "entries_listed": len(events), "entries_dated": len(dates),
                                 "entries_recent": sum(1 for d in dates if d >= window), "newest_entry": max(dates).isoformat() if dates else None})
            expansions = sum(1 for r in mine if r["fetch_kind"] == "channel_document" and r["request"]["requested_url"] not in {c["url"] for c in channels})
            items = [r for r in mine if r["fetch_kind"] == "item"]
            ok_items = [r for r in items if r["outcome"] == "FETCHED" and 200 <= int(r["response"]["status"]) < 300]
            statuses = Counter(str(r["response"]["status"]) if r["outcome"] == "FETCHED" else f"failed:{r['failure_reason']}" for r in items)
            robots = [r for r in mine if r["fetch_kind"] == "robots_txt"]
            bodies, as_is_l, a_l, b_l, titles, dated, short = [], [], [], [], 0, 0, 0
            for r in ok_items:
                if r["fetch_id"] not in locate:
                    continue
                path, entry = locate[r["fetch_id"]]
                stored = pack.read_fetch_record(path, entry)
                body = pack.read_body(path, entry)
                result = E.BASELINE.run(body, body_sha256=stored["body_sha256"], **core_pipeline._extraction_arguments(stored))
                text = result.body_text if result.outcome == E.OUTCOME_EXTRACTED else ""
                bodies.append(len(text))
                short += len(text) < SCREENING["short_body_characters"]
                metadata = result.record.get("metadata") or {}
                titles += bool((metadata.get("title") or {}).get("value") if isinstance(metadata.get("title"), dict) else metadata.get("title"))
                dated += bool((metadata.get("publication_date") or {}).get("value") if isinstance(metadata.get("publication_date"), dict) else metadata.get("publication_date"))
                try:
                    raw = E.decode_content(body, stored["response"].get("content_encoding") or "identity")
                    decoded, _ = E._decode(raw, E.declared_charset_of(stored["response"]["headers"]))
                    x, a, b = _rule_chars(decoded)
                    as_is_l.append(x), a_l.append(a), b_l.append(b)
                except Exception:  # noqa: BLE001 -- a diagnostic; a page it cannot read is counted out, not guessed
                    pass
            discovery = ("FUNCTIONAL" if any(c["status"].startswith("2") and c["entries_listed"] for c in channels)
                         else "ANSWERED_WITHOUT_ENTRIES" if any(c["status"].startswith("2") for c in channels)
                         else "FAILED" if channels and any(c["status"] != "not requested" for c in channels) else "NOT_REACHED")
            coverage = coverage_of(channels, started, weekend)
            access = sorted(k for k in statuses if k in ("401", "403", "429") or "challenge" in k)
            raw = ("FUNCTIONAL" if len(ok_items) >= SCREENING["raw_functional_min_pages"] else "PARTIAL" if ok_items
                   else "ACCESS_SIGNAL" if access else "FAILED" if items else "NOT_ATTEMPTED")
            med = _median(bodies)
            share = short / len(bodies) if bodies else None
            quality = ("NOT_MEASURED" if not bodies else "POOR" if (med or 0) < SCREENING["short_body_characters"] or share > SCREENING["short_share_poor"]
                       else "LIMITED" if (med or 0) < SCREENING["good_median_characters"] or share > SCREENING["short_share_limited"] else "GOOD")
            prior = matrix.get(oid, {})
            outlets[oid] = {
                "outlet_id": oid, "country_id": by_id[oid]["country_id"],
                "name": (by_id[oid].get("display_names") or [oid])[0] if isinstance(by_id[oid].get("display_names"), list) else oid,
                "prior_recommendation": prior.get("recommendation"), "run_id": receipt["run_id"], "requested_at": receipt["started_at"],
                "requests": receipt["requests"]["by_outlet"].get(oid), "robots": [str(r["response"]["status"]) if r["outcome"] == "FETCHED" else r["failure_reason"] for r in robots],
                "channels": channels, "expansion_documents": expansions, "candidates_first_listed_here": first_in_run.get(oid, 0),
                "items": {"requested": len(items), "answered_2xx": len(ok_items), "statuses": dict(statuses)},
                "extraction": {"pages": len(bodies), "body_characters_median": med, "under_500": short, "title_found": titles, "publication_date_found": dated,
                               "candidate_rules_median": {"as_is": _median(as_is_l), "rule_a": _median(a_l), "rule_b": _median(b_l)}},
                "preservation": {"pending_in_workspace": sum(1 for r in mine if states.get(r["fetch_id"]) == "PRESERVATION_PENDING"),
                                 "raw_preserved": sum(1 for r in mine if states.get(r["fetch_id"]) == "RAW_PRESERVED")},
                "DISCOVERY_FUNCTIONAL": discovery, "NEW_ARTICLE_COVERAGE": coverage, "RAW_ACQUISITION_FUNCTIONAL": raw,
                "TEXT_EXTRACTION_QUALITY": quality, "access_signals": access,
            }
    budget = {"transport_requests": sum(r["requests"]["total"] for r in receipts), "item_requests": sum(r["requests"]["item"] for r in receipts),
              "fetcher_transport_calls": sum(r.get("fetcher_transport_calls") or 0 for r in receipts),
              "by_run": {r["run_id"]: {"wave": (r.get("operator_authorization") or {}).get("wave"), "requests": r["requests"]["total"],
                                       "status": r.get("status")} for r in receipts}}
    return {"schema": SCHEMA, "screening": SCREENING, "runs": sorted(run_ids), "budget": budget, "outlets": outlets,
            "totals": {dim: dict(Counter(o[dim] for o in outlets.values())) for dim in
                       ("DISCOVERY_FUNCTIONAL", "NEW_ARTICLE_COVERAGE", "RAW_ACQUISITION_FUNCTIONAL", "TEXT_EXTRACTION_QUALITY")}}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--authorization-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, default=REPOSITORY / "docs" / "canary" / "evidence",
                        help="the directory of the canaries' evidence (default: this checkout's)")
    parser.add_argument("--runtime", type=Path, default=None,
                        help="the runtime workspace (default: COPREPAN_RUNTIME_ROOT of the workstation environment)")
    arguments = parser.parse_args(argv)
    receipts = []
    for path in sorted(arguments.evidence.glob("*/canary-receipt-*.json")):
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if (receipt.get("operator_authorization") or {}).get("authorization_id") == arguments.authorization_id:
            receipts.append(receipt)
    # Read only: the runtime root is taken as configured, without the write probe of storage_roots.resolve_root.
    runtime = arguments.runtime or Path(storage_roots.workstation_environment().get("COPREPAN_RUNTIME_ROOT") or ".")
    if not runtime.is_dir():
        parser.error(f"the runtime workspace is not there: {runtime}")
    workspace = core_pipeline.Workspace(runtime)
    registry_doc = json.loads((REPOSITORY / "config" / "outlet_registry.json").read_text(encoding="utf-8"))
    matrix = {r["outlet_id"]: r for r in json.loads((REPOSITORY / "docs/intake/source_health/source_health_2026-11-14.json").read_text(encoding="utf-8"))["outlets"]}
    result = build(workspace, receipts, registry_doc, matrix)
    arguments.out.write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"runs": len(result["runs"]), "outlets": len(result["outlets"]), "totals": result["totals"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
