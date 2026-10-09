"""Per-outlet and per-channel evaluation of one canary run, read from the runtime workspace (read-only).

    python scripts/evaluate_canary_run.py --run <run_id> --out <file>

What a receipt counts per run, this states per outlet and per channel: which channel documents were
asked for and how they answered, what they listed, what the candidate filter decided, which item
pages were requested, how they answered, and what the experimental extractor made of them. It is a
derived view of primary evidence (request log, discovery tables, qualifications, admission labels)
and can be rebuilt from it; it adds no judgement about an outlet. Body-text figures measure the
extractor, not the pages.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from coprepan import storage_roots  # noqa: E402
from coprepan.canonical import record_json  # noqa: E402

SCHEMA = "coprepan-canary-run-evaluation/v1"
ARTICLE_TEXT_MIN = 500      # characters of body text under the baseline extractor; below it the extraction is flagged, not the page


def rows(path: Path) -> list[dict[str, Any]]:
    out = []
    for line in path.read_bytes().splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            pass                 # a torn last line of a table that is being written
    return out


def evaluate(workspace: Path, run_id: str) -> dict[str, Any]:
    log = [r for r in rows(workspace / "requests" / "requests.jsonl") if r.get("run_id") == run_id]
    planned = {r["request_id"]: r for r in log if r["event"] == "PLANNED"}
    events = [r for r in rows(workspace / "discovery" / "events.jsonl") if r.get("run_id") == run_id]
    inputs = [r for r in rows(workspace / "discovery" / "inputs.jsonl") if r.get("run_id") == run_id]
    decisions = [r for r in rows(workspace / "discovery" / "qualifications.jsonl") if r.get("run_id") == run_id]
    labels = {r["fetch_id"]: r for r in rows(workspace / "admission" / "labels.jsonl")}
    outlets: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "requests": Counter(), "refused": Counter(), "access_classes": Counter(), "robots_evidence": Counter(), "research_overrides": 0,
        "channels": defaultdict(lambda: {"documents": [], "inputs": [], "entries": 0, "entry_problems": Counter(), "candidates_listed": 0,
                                         "items_requested": 0, "items_2xx": 0}),
        "items": [], "redirect_hops": 0})
    for row in log:
        if row["event"] == "PLANNED":
            continue
        plan = planned.get(row["request_id"], {})
        outlet = outlets[plan.get("outlet_id", "?")]
        result = row.get("result") or {}
        status = result.get("status")
        layers = row.get("policy_layers") or {}
        if layers.get("access_class_observed"):
            outlet["access_classes"][layers["access_class_observed"]] += 1
        if layers.get("robots_evidence"):
            outlet["robots_evidence"][layers["robots_evidence"]] += 1
        if layers.get("acquisition_decision") == "ALLOW_RESEARCH_OVERRIDE":
            outlet["research_overrides"] += 1
        delay = (row.get("policy_hints") or {}).get("robots_crawl_delay")
        try:
            delay = float(delay) if delay is not None else None
        except (TypeError, ValueError):
            delay = None                 # a crawl delay that is not a number is recorded in the robots evidence, not here
        if delay is not None:
            outlet["crawl_delay"] = max(outlet.get("crawl_delay") or 0, delay)
        hops = max(0, len(row.get("fetch_ids") or []) - 1)
        outlet["redirect_hops"] += hops
        if row["final"] != "FETCHED":
            outlet["refused"][f"{row['fetch_kind']}:{(row.get('policy_reasons') or [row['final']])[0]}"] += 1
            if row["fetch_kind"] == "channel_document" and plan.get("channel_id"):
                outlet["channels"][plan["channel_id"]]["documents"].append({"url": plan.get("url"), "outcome": (row.get("policy_reasons") or [row["final"]])[0]})
            continue
        outlet["requests"][f"{row['fetch_kind']}:{status}"] += 1
        if row["fetch_kind"] == "channel_document" and plan.get("channel_id"):
            outlet["channels"][plan["channel_id"]]["documents"].append({"url": plan.get("url"), "status": status, "final_url": result.get("final_url"),
                                                                        "redirect_hops": hops, "expansion_depth": plan.get("expansion_depth", 0)})
        if row["fetch_kind"] == "item":
            fetch_id = (row.get("fetch_ids") or [None])[-1]
            label = labels.get(fetch_id)
            characters = label["measurements"]["body_characters"] if label else None
            channel = outlet["channels"][plan["channel_id"]] if plan.get("channel_id") else None
            ok = isinstance(status, int) and 200 <= status < 300
            if channel is not None:
                channel["items_requested"] += 1
                channel["items_2xx"] += int(ok)
            outlet["items"].append({"url": plan.get("url"), "final_url": result.get("final_url"), "status": status, "channel_id": plan.get("channel_id"),
                                    "redirect_hops": hops, "body_characters": characters, "fetch_id": fetch_id,
                                    "redirect_not_followed": result.get("redirect_not_followed")})
    for row in inputs:
        outlet_id = row["channel_id"].split(":ch:")[0]
        outlets[outlet_id]["channels"][row["channel_id"]]["inputs"].append(
            {"outcome": row["outcome"], "format": row.get("format"), "entries": row.get("entries"), "problems": row.get("problems") or [], "depth": row.get("depth")})
    listed: dict[str, set[str]] = defaultdict(set)
    for row in events:
        channel = outlets[row["outlet_id"]]["channels"][row["channel_id"]]
        channel["entries"] += 1
        if row.get("problem"):
            channel["entry_problems"][row["problem"]] += 1
        if row.get("candidate_id"):
            listed[row["channel_id"]].add(row["candidate_id"])
    for channel_id, candidates in listed.items():
        outlets[channel_id.split(":ch:")[0]]["channels"][channel_id]["candidates_listed"] = len(candidates)
    by_outlet_decisions: dict[str, Counter] = defaultdict(Counter)
    for row in decisions:
        by_outlet_decisions[row["outlet_id"]][f"{row['decision']}:{(row.get('reasons') or [''])[0]}"] += 1

    summary = {}
    for outlet_id in sorted(outlets):
        outlet = outlets[outlet_id]
        good = [item for item in outlet["items"] if isinstance(item["status"], int) and 200 <= item["status"] < 300]
        characters = [item["body_characters"] for item in good if item["body_characters"] is not None]
        requests_total = sum(outlet["requests"].values()) + outlet["redirect_hops"]
        summary[outlet_id] = {
            "requests_answered": dict(sorted(outlet["requests"].items())), "redirect_hops": outlet["redirect_hops"], "refused": dict(sorted(outlet["refused"].items())),
            "access_classes_observed": dict(sorted(outlet["access_classes"].items())), "robots_evidence": dict(sorted(outlet["robots_evidence"].items())),
            "requests_under_research_override": outlet["research_overrides"], "robots_crawl_delay_seconds": outlet.get("crawl_delay"),
            "channels": {channel_id: {**channel, "entry_problems": dict(sorted(channel["entry_problems"].items()))} for channel_id, channel in sorted(outlet["channels"].items())},
            "candidate_decisions": dict(sorted(by_outlet_decisions[outlet_id].items())),
            "items_requested": len(outlet["items"]), "items_2xx": len(good),
            "item_statuses": dict(sorted(Counter(str(item["status"]) for item in outlet["items"]).items())),
            "items": [{key: item[key] for key in ("url", "final_url", "status", "channel_id", "redirect_hops", "body_characters", "redirect_not_followed")} for item in outlet["items"]],
            "extraction": {"labelled": len(characters), "body_characters_median": int(statistics.median(characters)) if characters else None,
                           "body_characters_min": min(characters) if characters else None, "body_characters_max": max(characters) if characters else None,
                           "below_the_article_text_floor": sum(1 for value in characters if value < ARTICLE_TEXT_MIN), "floor": ARTICLE_TEXT_MIN,
                           "note": "the experimental baseline extractor; a short text flags the extraction, not the page"},
            "requests_per_2xx_item": round(requests_total / len(good), 2) if good else None}
    return {"schema": SCHEMA, "run_id": run_id, "outlets": summary,
            "totals": {"outlets": len(summary), "outlets_with_2xx_items": sum(1 for o in summary.values() if o["items_2xx"]),
                       "items_2xx": sum(o["items_2xx"] for o in summary.values()), "items_requested": sum(o["items_requested"] for o in summary.values())}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=None)
    arguments = parser.parse_args(argv)
    if arguments.out.exists():
        raise SystemExit(f"{arguments.out.name} exists: an evaluation is written once")
    workspace = arguments.workspace or storage_roots.resolve_configured_roles(env=storage_roots.workstation_environment())["RUNTIME"]
    evaluation = evaluate(workspace, arguments.run)
    arguments.out.write_bytes(record_json(evaluation))
    print(json.dumps(evaluation["totals"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
