"""The source-health matrix: every documented outlet and channel, from stored evidence only (no request).

    python scripts/build_source_health.py [--workspace RUNTIME] [--out-dir docs/intake/source_health] [--as-of YYYY-MM-DD]

Reads (all tracked, plus the workspace when given):

* ``config/outlet_registry.json`` -- every registered or proposed outlet;
* ``config/source_discovery/source_inventory_2026-10-10.1.json`` -- every documented hypothesis, also the unregistered ones;
* ``config/intake/intake_readiness_2026-10-10.1.json`` -- what is qualified for an intake, held, not ready or excluded;
* ``config/acquisition_policy.json`` -- disabled channels and outlets;
* ``docs/intake/reports/in1-20261010-24h/`` -- the 24-hour intake: measurement (per outlet, channel and item) and receipt;
* with ``--workspace``: the holds derived from every stored answer (``canary_driver.access_holds_from_evidence``), the holds the
  controller would apply at a start today.

Writes ``source_health_<as-of>.json`` (machine-readable) and ``source_health_<as-of>.md`` (the human matrix).

The recommendation of an outlet is a **technical screening**, not a scientific judgement and not an access decision; the thresholds
are named in the output (``SCREENING``) and every class says which evidence decided it:

* ``HELD`` -- an access hold covers the outlet (all its origins or all its channels), in the readiness file or in the evidence;
* ``NOT_REGISTERED`` -- a documented hypothesis without a registry record;
* ``REQUALIFICATION_REQUIRED`` -- registered but not qualified for an intake (the readiness file's reason), or qualified and the
  24-hour intake gave no item page, or no new article, or a channel that never answered;
* ``REPAIR_REQUIRED`` -- qualified, pages were fetched, and at least half of the 2xx pages are flagged empty or very short: the
  extraction (or the URL selection) is the problem, to be reviewed on the named cases;
* ``READY_WITH_LIMITATIONS`` -- usable, with named limitations (a held URL, undated channels, duplicates, short texts, a part of
  the new articles left behind by the budget, a channel unavailable in some polls, an open extraction note);
* ``READY`` -- none of that.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

SCHEMA = "coprepan-source-health/v1"
EVIDENCE_RUN = "in1-20261010-24h"
SCREENING = {
    "repair_short_or_empty_share": 0.5,       # >= this share of 2xx pages empty or very short -> REPAIR_REQUIRED
    "limitation_short_or_empty_share": 0.2,   # >= this share -> a limitation
    "limitation_duplicate_share": 0.2,
    "limitation_undated_share": 0.5,          # pages whose publication date is unknown
    "budget_left_behind_share": 0.5,          # new dated articles discovered but not fetched, as a share of those discovered
    "item_ceiling_per_outlet": 120,           # the 24-hour plan's item_requests_per_outlet
    "note": "screening thresholds of the source-health matrix (2026-11-14); technical findings for review, not quality judgements",
}
SHORT = ("empty_extraction", "very_short_text")
URL_SHAPE = ("front_or_top_level_page_url", "author_page_url", "gallery_or_video_url", "sponsored_url")


def _load(relative: str) -> Any:
    return json.loads((REPO / relative).read_text(encoding="utf-8"))


def _origin(url: str) -> str:
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _channel_status(stats: dict | None) -> tuple[str, list[str]]:
    if not stats:
        return "NOT_POLLED", ["not polled in the 24-hour intake"]
    notes = []
    polls, read, unavailable = stats.get("polls", 0), stats.get("documents_read", 0), stats.get("documents_unavailable", 0)
    first = stats.get("candidates_first_listed") or {}
    new = first.get("new_dated_in_window", 0) + first.get("new_undated_later_poll", 0)
    if read == 0:
        return "UNAVAILABLE", [f"{polls} polls, no document read ({unavailable} unavailable)"]
    if unavailable:
        notes.append(f"{unavailable} of {read + unavailable} documents unavailable")
    if new == 0:
        if first.get("older_than_window", 0):
            notes.append(f"{first['older_than_window']} entries first listed, every one dated before the intake window: an archive or section "
                         "listing, not a news stream")
            return "HISTORICAL_ENTRIES_ONLY", notes
        status = "NO_NEW_ENTRIES" if sum(first.values()) == 0 else "STOCK_ONLY"
        notes.append("no entry first listed during the intake was new by its channel's dates or later polls")
        return status, notes
    return ("PARTIALLY_UNAVAILABLE" if unavailable else "OK"), notes


def build(workspace: Path | None, as_of: str) -> dict[str, Any]:
    registry = {o["outlet_id"]: o for o in _load("config/outlet_registry.json")["outlets"]}
    inventory = {o["outlet_id"]: o for o in _load("config/source_discovery/source_inventory_2026-10-10.1.json")["outlets"]}
    readiness = _load("config/intake/intake_readiness_2026-10-10.1.json")
    ready = {o["outlet_id"]: o for o in readiness["outlets"]}
    policy = _load("config/acquisition_policy.json")
    measurement = _load(f"docs/intake/reports/{EVIDENCE_RUN}/measurement.json")
    receipt = _load(f"docs/intake/reports/{EVIDENCE_RUN}/receipt.json")
    held_origins = dict(readiness.get("held_origins") or {})
    held_urls = dict(readiness.get("held_urls") or {})
    arose = {k: v for k, v in (receipt.get("holds_that_arose") or {}).items()}
    evidence_holds: dict[str, str] | None = None
    if workspace is not None:
        from coprepan import canary_driver, core_pipeline

        evidence_holds = canary_driver.access_holds_from_evidence(core_pipeline.Workspace(workspace), reclassify=True)
    holds_now = dict(evidence_holds) if evidence_holds is not None else {**held_origins, **held_urls, **arose}
    disabled_channels = set(policy.get("disabled_channels") or [])
    disabled_outlets = set(policy.get("disabled_outlets") or [])
    ids = sorted(set(registry) | set(inventory))
    rows = []
    for oid in ids:
        reg, inv, rd = registry.get(oid), inventory.get(oid), ready.get(oid)
        meas = (measurement.get("outlets") or {}).get(oid)
        country = (reg or inv or {}).get("country_id")
        origins = list((rd or reg or inv or {}).get("web_origins") or [])
        channels_src = (rd or {}).get("channels") or []
        channel_rows = []
        for ch in channels_src:
            stats = ((meas or {}).get("channels") or {}).get(ch["channel_id"])
            status, notes = _channel_status(stats) if rd else ("NOT_QUALIFIED", [])
            held = holds_now.get(ch["url"]) or (holds_now.get(_origin(ch["url"])))
            if held:
                status, notes = "HELD", [f"held: {held}"]
            if ch["channel_id"] in disabled_channels:
                status, notes = "DISABLED_BY_POLICY", ["disabled in the acquisition policy"]
            channel_rows.append({"channel_id": ch["channel_id"], "kind": ch["kind"], "url": ch["url"], "status": status, "notes": notes,
                                 "polls": (stats or {}).get("polls"), "entries_listed": (stats or {}).get("entries_listed"),
                                 "candidates_first_listed": (stats or {}).get("candidates_first_listed"),
                                 "items_requested": (stats or {}).get("items_requested"), "items_2xx": (stats or {}).get("items_2xx")})
        for url, why in ((rd or {}).get("channels_not_usable") or {}).items():
            channel_rows.append({"channel_id": None, "kind": None, "url": url, "status": "NOT_USABLE", "notes": [str(why)]})
        row: dict[str, Any] = {"outlet_id": oid, "country_id": country, "name": (inv or {}).get("name"),
                               "registration": (reg or {}).get("registration_status") or "not registered",
                               "inventory_stage": (inv or {}).get("stage"), "qualified_for_intake": rd is not None,
                               "tier": (rd or {}).get("tier"), "channels": channel_rows,
                               "last_evidence": None, "discovery": None, "article_fetch": None, "extraction": None,
                               "novelty_coverage": None, "access": "no hold", "anomalies": [], "repair_need": [], "repair_done": [],
                               "uncertainty": [], "review_cases": []}
        # access
        origin_holds = sorted({holds_now[o] for o in origins if o in holds_now})
        all_channels_held = bool(channel_rows) and all(c["status"] in ("HELD", "DISABLED_BY_POLICY", "NOT_USABLE") for c in channel_rows)
        in_hold_list = oid in set(readiness.get("holds") or [])
        if origin_holds or in_hold_list or (rd and all_channels_held):
            row["access"] = "HELD: " + ", ".join(origin_holds or ["named in the readiness file's holds" if in_hold_list else "every channel held"])
        elif any(c["status"] == "HELD" for c in channel_rows):
            row["access"] = "a channel URL is held"
        if oid in disabled_outlets:
            row["access"] = "DISABLED_BY_POLICY"
        # evidence of the 24-hour intake
        if meas:
            items = meas.get("items") or []
            twoxx = meas.get("items_2xx", 0)
            flags = Counter(f for it in items for f in it.get("flags") or [])
            short = sum(1 for it in items if set(it.get("flags") or []) & set(SHORT) and str(it.get("status")) == "200")
            dup = flags.get("duplicate_body_of_other_document", 0)
            undated = flags.get("publication_date_unknown", 0)
            shape = sum(flags.get(f, 0) for f in URL_SHAPE)
            first = meas.get("candidates_first_listed_in_the_intake") or {}
            by_novelty = meas.get("items_2xx_by_novelty") or {}
            new_found = first.get("new_dated_in_window", 0)
            new_fetched = by_novelty.get("new_dated_in_window", 0)
            new_any = new_fetched + by_novelty.get("new_undated_later_poll", 0)
            left = new_found - new_fetched
            row["last_evidence"] = {"run": EVIDENCE_RUN, "dates": "2026-10-10/11", "item_pages_2xx": twoxx}
            unavailable = [c for c in channel_rows if c["status"] == "UNAVAILABLE"]
            row["discovery"] = ("NO_CHANNEL_ANSWERED" if channel_rows and len(unavailable) == len([c for c in channel_rows if c["channel_id"]])
                                else "CHANNEL_UNAVAILABLE_IN_PART" if unavailable or any(c["status"] == "PARTIALLY_UNAVAILABLE" for c in channel_rows)
                                else "OK")
            row["article_fetch"] = {"requested": meas.get("items_requested", 0), "2xx": twoxx, "statuses": meas.get("item_statuses"),
                                    "technically_usable": meas.get("technically_usable", 0),
                                    "refused_or_failed": meas.get("refused_or_failed"), "transport_calls": meas.get("transport_calls")}
            row["extraction"] = {"body_characters_median": meas.get("body_characters_median"), "empty_or_very_short": short,
                                 "duplicate_bodies": dup, "url_shape_flags": shape, "date_unknown": undated,
                                 "open_note_in_readiness": bool((rd or {}).get("extraction_open"))}
            row["novelty_coverage"] = {"new_dated_discovered": new_found, "new_dated_fetched_2xx": new_fetched,
                                       "new_undated_later_poll_2xx": by_novelty.get("new_undated_later_poll", 0),
                                       "new_dated_left_unfetched": max(0, left),
                                       "older_than_window_discovered": first.get("older_than_window", 0),
                                       "stock_first_poll_undated_discovered": first.get("first_poll_undated", 0),
                                       "median_seconds_publication_to_request": meas.get("seconds_from_publication_hint_to_request_median")}
            share = lambda n: (n / twoxx) if twoxx else 0.0  # noqa: E731
            if short:
                row["anomalies"].append(f"{short} of {twoxx} pages empty or very short")
            if dup:
                row["anomalies"].append(f"{dup} duplicate bodies")
            if undated:
                row["anomalies"].append(f"{undated} pages with unknown publication date")
            if shape:
                row["anomalies"].append(f"{shape} URLs shaped like a front, author, gallery or sponsored page")
            if meas.get("refused_or_failed"):
                row["anomalies"].append(f"refused or failed: {meas['refused_or_failed']}")
            row["review_cases"] = [{"fetch_id": it["fetch_id"], "url": it["url"], "flags": it["flags"], "body_characters": it.get("body_characters")}
                                   for it in items if set(it.get("flags") or []) & (set(SHORT) | set(URL_SHAPE))][:5]
            limitations = []
            if row["access"] != "no hold":
                limitations.append(row["access"])
            if share(short) >= SCREENING["limitation_short_or_empty_share"]:
                limitations.append("many short or empty extractions")
            if share(dup) >= SCREENING["limitation_duplicate_share"]:
                limitations.append("many duplicate bodies")
            if share(undated) >= SCREENING["limitation_undated_share"] or (new_found == 0 and new_any > 0):
                limitations.append("channels give no dates: novelty only from later polls")
            if new_found and left / new_found >= SCREENING["budget_left_behind_share"]:
                limitations.append(f"{left} of {new_found} new dated articles discovered were not fetched (budget)")
            if meas.get("items_requested", 0) >= SCREENING["item_ceiling_per_outlet"]:
                limitations.append("hit the per-outlet item ceiling")
            if row["discovery"] != "OK":
                limitations.append("a channel unavailable in some or all polls")
            if (rd or {}).get("extraction_open"):
                limitations.append("an open extraction note in the readiness file")
            if row["access"].startswith("HELD") or row["access"] == "DISABLED_BY_POLICY":
                recommendation, why = "HELD", [row["access"]]
            elif twoxx == 0:
                recommendation, why = "REQUALIFICATION_REQUIRED", ["no item page in the 24-hour intake"] + [n for c in channel_rows for n in c["notes"]][:3]
            elif new_any == 0:
                historical = [c["channel_id"] for c in channel_rows if c["status"] == "HISTORICAL_ENTRIES_ONLY"]
                recommendation, why = "REQUALIFICATION_REQUIRED", (
                    [f"no new article in 24 hours: {', '.join(historical)} listed only entries dated before the window (not a news stream); "
                     "find the outlet's news channel (a live requalification)"] if historical else ["no new article in 24 hours (stock pages only)"])
                row["repair_need"].append("channel: the registered channel is not a current news stream; a registry change after live requalification")
            elif share(short) >= SCREENING["repair_short_or_empty_share"]:
                recommendation, why = "REPAIR_REQUIRED", [f"{short} of {twoxx} pages empty or very short: review the extraction and the URL selection on the review cases"]
                row["repair_need"].append("extraction or URL selection (review cases named); no rule changed by this matrix")
            elif limitations:
                recommendation, why = "READY_WITH_LIMITATIONS", limitations
            else:
                recommendation, why = "READY", []
            row["uncertainty"].append("one 24-hour run of 2026-10-10/11; behaviour since then is not observed (no request since 2026-10-11)")
        else:
            if rd is not None:
                recommendation, why = "REQUALIFICATION_REQUIRED", ["qualified, but not part of the 24-hour intake's evidence"]
            elif oid in set(readiness.get("holds") or []) or row["access"].startswith("HELD"):
                recommendation, why = "HELD", [row["access"] if row["access"] != "no hold" else "named in the readiness file's holds"]
            elif reg is None:
                recommendation, why = "NOT_REGISTERED", [f"inventory stage {(inv or {}).get('stage')}: {(inv or {}).get('next_step')}"]
            else:
                reason = (readiness.get("not_ready") or {}).get(oid) or (readiness.get("excluded") or {}).get(oid)
                recommendation, why = "REQUALIFICATION_REQUIRED", [f"not qualified for an intake: {reason or 'not in the readiness file'}"]
            if inv:
                row["last_evidence"] = {"inventory_stage": inv.get("stage"), "item_pages_2xx_all_runs": inv.get("item_pages_2xx_all_runs"),
                                        "verified_runs": inv.get("verified_runs"), "verified_days": inv.get("verified_days")}
            row["uncertainty"].append("no 24-hour evidence")
        row["recommendation"], row["because"] = recommendation, why
        rows.append(row)
    counts = Counter(r["recommendation"] for r in rows)
    qualified = [r for r in rows if r["qualified_for_intake"]]
    return {"schema": SCHEMA, "as_of": as_of, "evidence": {"run": EVIDENCE_RUN, "readiness_version": readiness.get("readiness_version"),
            "inventory": "source_inventory_2026-10-10.1", "holds_from": "the workspace's stored answers" if evidence_holds is not None else "the readiness file and the 24-hour receipt",
            "holds_now": len(holds_now)}, "screening": SCREENING,
            "totals": {"outlets_documented": len(rows), "registered": sum(1 for r in rows if r["registration"] == "registered"),
                       "proposed": sum(1 for r in rows if r["registration"] == "proposed"), "not_registered": sum(1 for r in rows if r["registration"] == "not registered"),
                       "qualified_for_intake": len(qualified), "qualified_channels": sum(len([c for c in r["channels"] if c["channel_id"]]) for r in qualified),
                       "countries_qualified": len({r["country_id"] for r in qualified}), "recommendations": dict(sorted(counts.items())),
                       "operationally_stable": 0},
            "not_a_claim": "a technical screening from stored evidence; no outlet is OPERATIONALLY_STABLE (CPD-0025: three verified runs on three days); no access decision is made or changed",
            "outlets": rows}


def render(doc: dict[str, Any]) -> str:
    t = doc["totals"]
    lines = [f"# Source-health matrix — {doc['as_of']}", "",
             f"Built by `scripts/build_source_health.py` from stored evidence only (no request). Evidence: the 24-hour intake "
             f"`{doc['evidence']['run']}`, readiness `{doc['evidence']['readiness_version']}`, `{doc['evidence']['inventory']}`; holds from "
             f"{doc['evidence']['holds_from']} ({doc['evidence']['holds_now']}). **{doc['not_a_claim']}.**", "",
             f"Documented outlets {t['outlets_documented']} (registered {t['registered']}, proposed {t['proposed']}, not registered "
             f"{t['not_registered']}); qualified for an intake {t['qualified_for_intake']} with {t['qualified_channels']} channels in "
             f"{t['countries_qualified']} countries. Recommendations: "
             + ", ".join(f"`{k}` {v}" for k, v in t["recommendations"].items()) + ".", "",
             "Screening thresholds: " + ", ".join(f"{k} {v}" for k, v in doc["screening"].items() if k != "note") + f" — {doc['screening']['note']}.", "",
             "## Qualified outlets (24-hour evidence)", "",
             "| Country | Outlet | Channels (kind: status) | 2xx / requested | New dated found → fetched (left) | Undated-new 2xx | Short/empty · dup · undated | Access | Recommendation | Because |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(doc["outlets"], key=lambda x: (x["country_id"] or "", x["outlet_id"])):
        if not r["qualified_for_intake"]:
            continue
        ch = "; ".join(f"{c['kind'] or '—'}: {c['status']}" for c in r["channels"])
        af, nc, ex = r["article_fetch"] or {}, r["novelty_coverage"] or {}, r["extraction"] or {}
        lines.append(f"| {r['country_id']} | `{r['outlet_id']}` | {ch} | {af.get('2xx', '—')} / {af.get('requested', '—')} | "
                     f"{nc.get('new_dated_discovered', '—')} → {nc.get('new_dated_fetched_2xx', '—')} ({nc.get('new_dated_left_unfetched', '—')}) | "
                     f"{nc.get('new_undated_later_poll_2xx', '—')} | {ex.get('empty_or_very_short', '—')} · {ex.get('duplicate_bodies', '—')} · {ex.get('date_unknown', '—')} | "
                     f"{r['access']} | `{r['recommendation']}` | {'; '.join(r['because'])} |")
    lines += ["", "## Not qualified for an intake (registered, proposed, held or not registered)", "",
              "| Country | Outlet | Registration | Inventory stage | Recommendation | Because |", "|---|---|---|---|---|---|"]
    for r in sorted(doc["outlets"], key=lambda x: (x["country_id"] or "", x["outlet_id"])):
        if r["qualified_for_intake"]:
            continue
        lines.append(f"| {r['country_id']} | `{r['outlet_id']}` | {r['registration']} | {r['inventory_stage'] or '—'} | `{r['recommendation']}` | {'; '.join(r['because'])} |")
    lines += ["", "Review cases (fetch ids of flagged pages, up to five per outlet) and every channel's counts are in the JSON file beside this one.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=REPO / "docs" / "intake" / "source_health")
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args(argv)
    doc = build(args.workspace, args.as_of)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / f"source_health_{args.as_of}.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (args.out_dir / f"source_health_{args.as_of}.md").write_text(render(doc), encoding="utf-8", newline="\n")
    print(json.dumps(doc["totals"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
