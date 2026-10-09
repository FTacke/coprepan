"""The source inventory after qualification, and the intake-readiness configuration that follows from it (CPD-0025).

    python scripts/build_intake_readiness.py --version 2026-10-09.1 --out-inventory <file> --out-readiness <file> --out-md <file>

Everything is derived from tracked files: the registry, the dispositions, the registration records, the
candidate rules, the policy, and for every canary run its frozen baseline, receipt, verification and
evaluation (``docs/canary/evidence/<run>/``). Nothing is read from the runtime workspace or the network;
the same inputs give the same files.

Stages (CPD-0025 §2), per outlet, from evidence only:

- ``ACQUISITION_VERIFIED``: in one verified run, item pages of the outlet answered 2xx and were preserved
  and replayed — at least 5 where the run allowed 10 or more item requests per outlet, at least 3 where it
  allowed fewer;
- ``TECHNICALLY_QUALIFIED``: a channel document of the outlet was read from its server (2xx), parsed, and
  listed at least one candidate on a registered origin;
- ``REGISTERED``: a registration record exists; nothing more is shown;
- not registered: the disposition says why.

``OPERATIONALLY_STABLE`` (three verified runs on three days within fourteen days) is computed and is
expected to be empty.

A readiness configuration is a starting point for a later, separately authorised intake. It starts
nothing and activates nothing; its intervals are stated starting values, not measurements.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from coprepan.canonical import record_json, sha256_bytes  # noqa: E402

CONFIG = REPOSITORY / "config"
EVIDENCE = REPOSITORY / "docs" / "canary" / "evidence"
INVENTORY_SCHEMA = "coprepan-source-inventory/v2"
READINESS_SCHEMA = "coprepan-intake-readiness/v1"
LISTING_KINDS = ("section_page", "archive")
HOLD_REASONS = ("access_control_observed",)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def runs() -> list[dict[str, Any]]:
    baselines = {b["manifest_sha256"]: (path.name, b) for path in sorted((REPOSITORY / "docs" / "canary").glob("BASELINE_FROZEN_*.json")) for b in [load(path)]}
    found = []
    for directory in sorted(p for p in EVIDENCE.iterdir() if p.is_dir()):
        receipt = load(next(directory.glob("canary-receipt-*.json")))
        evaluation_path = directory / "evaluation.json"
        if not evaluation_path.exists():
            raise SystemExit(f"{directory.name}: no evaluation.json (scripts/evaluate_canary_run.py)")
        # A verification that was run again after the workspace finding it named had been resolved lies beside the first
        # one, which is never rewritten; the later file is the one that counts, and both are named in the inventory.
        again = sorted(directory.glob("verification_after_*.json"))
        later = again[-1] if again else directory / "verification.json"
        verification = load(later)
        name, baseline = baselines[receipt["baseline_id"]]
        pinned = baseline["canary"].get("authorization")
        found.append({"run_id": receipt["run_id"], "day": receipt["started_at"][:10], "receipt": receipt, "evaluation": load(evaluation_path),
                      "verification": verification["status"], "verification_file": later.name,
                      "verification_as_first_run": load(directory / "verification.json")["status"],
                      "baseline_file": name, "item_budget_per_outlet": baseline["canary"]["driver"]["budget"]["item_requests_per_outlet"],
                      "operator_mode": pinned["mode"] if pinned else "INTERACTIVE_OPERATOR", "wave": pinned["wave"] if pinned else None})
    return found


def channel_class(kind: str, seen: list[dict[str, Any]], has_rule: bool, disabled: bool) -> str:
    """What the evidence says about one channel, from every run that read it; the latest reading decides."""
    if disabled:
        return "DISABLED"
    if not seen:
        return "NOT_READ"
    last = seen[-1]
    documents, inputs = last["documents"], last["inputs"]
    if documents and all("outcome" in d for d in documents):
        return "REFUSED_" + documents[0]["outcome"].upper()
    statuses = [d.get("status") for d in documents if "status" in d]
    if statuses and not any(isinstance(s, int) and 200 <= s < 300 for s in statuses):
        return f"HTTP_{statuses[0]}"
    if any(i["outcome"] == "UNPARSEABLE" for i in inputs) and not any(i["outcome"] == "PARSED" for i in inputs):
        return "UNPARSEABLE"
    if not any(i["outcome"] == "PARSED" for i in inputs):
        return "UNAVAILABLE"
    html = any(i.get("format") == "html_listing" for i in inputs)
    if last["entries"] == 0:
        return "PARSED_NO_ENTRIES"
    if last["candidates_listed"] == 0:
        return "ENTRIES_OFF_ORIGIN" if last["entry_problems"].get("off_origin") else "PARSED_NO_CANDIDATES"
    if last["candidates_listed"] <= 2 and last["entries"] >= 10 and not last["entry_problems"]:
        return "IDENTITY_COLLAPSE"
    if html or kind in LISTING_KINDS:
        return "LISTING_WITH_RULE" if has_rule else "LISTING_READ_NEEDS_RULE"
    return "WORKS"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--version", required=True)
    parser.add_argument("--out-inventory", type=Path, required=True)
    parser.add_argument("--out-readiness", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, required=True)
    arguments = parser.parse_args(argv)
    for out in (arguments.out_inventory, arguments.out_readiness, arguments.out_md):
        if out.exists():
            raise SystemExit(f"{out.name} exists: a version is written once")

    registry = load(CONFIG / "outlet_registry.json")
    policy = load(CONFIG / "acquisition_policy.json")
    rules = load(CONFIG / "candidate_rules.json")["outlets"]
    dispositions_path = sorted((CONFIG / "source_discovery").glob("qualification_dispositions_*.json"))[-1]
    dispositions = {row["outlet_id"]: row for row in load(dispositions_path)["dispositions"]}
    new_ids = {entry["outlet_id"] for path in sorted((CONFIG / "registry_review").glob("*_registration_*.json")) for entry in load(path)["registered"] if entry.get("new_outlet")}
    all_runs = runs()
    by_outlet: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for run in all_runs:
        for outlet_id, evaluation in run["evaluation"]["outlets"].items():
            by_outlet[outlet_id].append((run, evaluation))
    for run in all_runs:                       # an outlet a run was armed for and that planned nothing (a hold before any request)
        for outlet_id in run["receipt"]["outlets"]:
            if all(r["run_id"] != run["run_id"] for r, _ in by_outlet[outlet_id]):
                by_outlet[outlet_id].append((run, None))
    for outlet_id in by_outlet:
        by_outlet[outlet_id].sort(key=lambda pair: pair[0]["receipt"]["started_at"])

    outlets = []
    registered_rows = {o["outlet_id"]: o for o in registry["outlets"]}
    for outlet_id in sorted(dispositions):
        disposition = dispositions[outlet_id]
        row = registered_rows.get(outlet_id)
        history = by_outlet.get(outlet_id, [])
        held = any(reason.split(":", 1)[1] in HOLD_REASONS for _, e in history if e for reason in e["refused"]) or any(
            "bot_challenge" in (run["receipt"]["policy_layers"]["by_outlet"].get(outlet_id, {}).get("access_classes_observed") or {}) for run, _ in history)
        verified_runs = []
        best = 0
        for run, evaluation in history:
            items = evaluation["items_2xx"] if evaluation else 0
            best = max(best, items)
            threshold = 5 if run["item_budget_per_outlet"] >= 10 else 3
            if run["verification"] == "PASS" and items >= threshold:
                verified_runs.append(run)
        channels = []
        qualified_channel = False
        for channel in (row["channels"] if row else []):
            seen = [e["channels"][channel["channel_id"]] for _, e in history if e and channel["channel_id"] in e["channels"]]
            klass = channel_class(channel["kind"], seen, outlet_id in rules, channel["channel_id"] in policy["disabled_channels"])
            items = sum(c["items_2xx"] for c in seen)
            qualified_channel = qualified_channel or klass in ("WORKS", "LISTING_WITH_RULE", "LISTING_READ_NEEDS_RULE")
            channels.append({"channel_id": channel["channel_id"], "kind": channel["kind"], "url": channel["url_history"][-1]["url"], "class": klass,
                             "read_in_runs": len(seen), "entries_last": seen[-1]["entries"] if seen else None,
                             "candidates_last": seen[-1]["candidates_listed"] if seen else None, "item_pages_2xx": items,
                             "formats": sorted({i["format"] for c in seen for i in c["inputs"] if i.get("format")})})
        if row is None or row["registration_status"] != "registered":
            stage, restriction, next_step = "NOT_REGISTERED", disposition["disposition"], "deferred: " + disposition["reason"]
        elif verified_runs:
            days = sorted({run["day"] for run in verified_runs})
            stage = "OPERATIONALLY_STABLE" if len(verified_runs) >= 3 and len(days) >= 3 else "ACQUISITION_VERIFIED"
            restriction, next_step = ("HELD_ACCESS_CONTROL" if held else None), ("held: not asked again" if held else "ready for a bounded intake")
        else:
            classes = Counter(c["class"] for c in channels if c["class"] != "NOT_READ")
            if held:
                restriction, next_step = "HELD_ACCESS_CONTROL", "held: a browser challenge was observed; not asked again, nothing worked around"
            elif not history:
                restriction, next_step = "NOT_TESTED", "registered and not asked in any run"
            elif best > 0:
                restriction, next_step = "FEW_ITEMS", "item pages were preserved, fewer than the stage asks: another bounded run"
            elif classes.get("LISTING_READ_NEEDS_RULE") and not classes.get("WORKS"):
                restriction, next_step = "LISTING_NEEDS_RULE", "the listing is preserved; an allow rule written from it comes before any item"
            elif classes.get("IDENTITY_COLLAPSE"):
                restriction, next_step = "URL_IDENTITY", "the entries fold into one URL key: the outlet's URL rules need a version of their own"
            elif classes.get("ENTRIES_OFF_ORIGIN"):
                restriction, next_step = "ORIGIN_MISMATCH", "the channel lists pages of a host that is not a registered origin: an amendment after review"
            elif classes.get("WORKS"):
                restriction, next_step = "ITEMS_NOT_2XX", "candidates were listed; no item page answered 2xx in the run"
            elif any(k.startswith("HTTP_") for k in classes):
                restriction, next_step = "CHANNEL_HTTP_ERROR", "every channel that was read answered with an error status: another evidenced channel is needed"
            elif classes.get("UNPARSEABLE"):
                restriction, next_step = "CHANNEL_UNPARSEABLE", "the channel answered and could not be parsed: a parser finding to examine"
            elif classes.get("REFUSED_ROBOTS_UNREACHABLE"):
                restriction, next_step = "ROBOTS_NOT_REACHED", "the robots file of the registered origin could not be read (a redirect to a host that is not registered, or no answer): nothing was requested"
            elif classes.get("REFUSED_ROBOTS_PARSE_ERROR"):
                restriction, next_step = "ROBOTS_UNREADABLE", "the host answered its robots address with something that is not a robots file: nothing was requested"
            elif any(k.startswith("REFUSED_") for k in classes):
                restriction, next_step = "REFUSED_BY_POLICY_OR_BUDGET", "the channel was not requested: " + ", ".join(sorted(k for k in classes if k.startswith("REFUSED_")))
            else:
                restriction, next_step = "NO_USABLE_ENTRIES", "the channel was read and listed nothing usable"
            stage = "TECHNICALLY_QUALIFIED" if qualified_channel and not held else "REGISTERED"
        last = history[-1] if history else None
        extraction = last[1]["extraction"] if last and last[1] else None
        outlets.append({
            "outlet_id": outlet_id, "country_id": disposition["country_id"], "name": disposition["name"],
            "registration_status": row["registration_status"] if row else "not_in_registry", "new_to_the_registry": outlet_id in new_ids,
            "web_origins": row["web_origins"] if row else disposition["origins"], "timezone": row["timezone"] if row else "unknown",
            "outlet_type": row["outlet_type"] if row else "unknown", "outlet_group": row["outlet_group"] if row else "unknown",
            "stage": stage, "restriction": restriction, "next_step": next_step,
            "item_pages_2xx_best_run": best, "item_pages_2xx_all_runs": sum(e["items_2xx"] for _, e in history if e),
            "verified_runs": [run["run_id"] for run in verified_runs], "verified_days": sorted({run["day"] for run in verified_runs}),
            "runs": [{"run_id": run["run_id"], "day": run["day"], "wave": run["wave"], "operator_mode": run["operator_mode"], "verification": run["verification"],
                      "item_budget": run["item_budget_per_outlet"], "items_requested": e["items_requested"] if e else 0, "items_2xx": e["items_2xx"] if e else 0,
                      "requests": run["receipt"]["requests"]["by_outlet"].get(outlet_id), "refused": e["refused"] if e else {},
                      "research_overrides": e["requests_under_research_override"] if e else 0} for run, e in history],
            "preservation": ("PASS" if all(run["verification"] == "PASS" for run, _ in history) else "FAIL") if history else "not_tested",
            "replay": ("PASS" if all(run["verification"] == "PASS" for run, _ in history) else "FAIL") if history else "not_tested",
            "channels": channels, "candidate_rule": rules[outlet_id]["version"] if outlet_id in rules else None,
            "extraction_last_run": extraction, "robots_crawl_delay_seconds": max([e.get("robots_crawl_delay_seconds") or 0 for _, e in history if e] or [0]) or None})

    stage_counts = Counter(o["stage"] for o in outlets)
    countries = {}
    for country in sorted({o["country_id"] for o in outlets}):
        mine = [o for o in outlets if o["country_id"] == country]
        usable = [o for o in mine if o["stage"] in ("ACQUISITION_VERIFIED", "OPERATIONALLY_STABLE") and o["restriction"] is None]
        countries[country] = {"hypotheses": len(mine), "registered": sum(o["registration_status"] == "registered" for o in mine),
                              "acquisition_verified": len(usable), "technically_qualified_only": sum(o["stage"] == "TECHNICALLY_QUALIFIED" for o in mine),
                              "with_any_preserved_item_page": sum(o["item_pages_2xx_all_runs"] > 0 for o in mine),
                              "working_channels": sum(1 for o in mine for c in o["channels"] if c["class"] in ("WORKS", "LISTING_WITH_RULE") and c["item_pages_2xx"] > 0),
                              "held": sorted(o["outlet_id"] for o in mine if o["restriction"] == "HELD_ACCESS_CONTROL"),
                              "verified_outlets": sorted(o["outlet_id"] for o in usable),
                              "new_to_the_registry_verified": sorted(o["outlet_id"] for o in usable if o["new_to_the_registry"])}
    by_type: dict[str, Counter] = defaultdict(Counter)
    for o in outlets:
        for c in o["channels"]:
            if c["class"] != "NOT_READ":
                key = (c["formats"][0] if c["formats"] else c["kind"])
                by_type[key][c["class"]] += 1
                if c["item_pages_2xx"]:
                    by_type[key]["channels_that_yielded_item_pages"] += 1
    requests_total = sum(run["receipt"]["requests"]["total"] for run in all_runs)
    inputs = {"registry": {"file": "outlet_registry.json", "sha256": sha256_bytes((CONFIG / "outlet_registry.json").read_bytes())},
              "dispositions": {"file": dispositions_path.name, "sha256": sha256_bytes(dispositions_path.read_bytes())},
              "candidate_rules": {"file": "candidate_rules.json", "sha256": sha256_bytes((CONFIG / "candidate_rules.json").read_bytes())},
              "policy_version": policy["policy_version"],
              "runs": [{"run_id": run["run_id"], "wave": run["wave"], "operator_mode": run["operator_mode"], "baseline": run["baseline_file"],
                        "verification": run["verification"], "verification_file": run["verification_file"],
                        "verification_as_first_run": run["verification_as_first_run"], "requests": run["receipt"]["requests"]["total"],
                        "item_pages_2xx": run["evaluation"]["totals"]["items_2xx"]} for run in all_runs]}
    inventory = {
        "schema": INVENTORY_SCHEMA, "inventory_version": arguments.version,
        "what_this_is": "every outlet hypothesis of the repository with its stage, from tracked evidence only; a stage is not a statement about the corpus, a registered outlet is not an outlet that yields articles, and one run shows nothing about stability",
        "stage_rules": __doc__.split("Stages (CPD-0025 §2), per outlet, from evidence only:")[1].split("A readiness configuration")[0].strip(),
        "inputs": inputs,
        "totals": {"hypotheses": len(outlets), "by_stage": dict(sorted(stage_counts.items())),
                   "by_restriction": dict(sorted(Counter(o["restriction"] or "none" for o in outlets).items())),
                   "registered": sum(o["registration_status"] == "registered" for o in outlets),
                   "with_any_preserved_item_page": sum(o["item_pages_2xx_all_runs"] > 0 for o in outlets),
                   "item_pages_2xx_all_runs": sum(o["item_pages_2xx_all_runs"] for o in outlets),
                   "countries_with_a_verified_outlet": sorted(c for c, v in countries.items() if v["acquisition_verified"]),
                   "real_requests_all_runs": requests_total},
        "by_country": countries, "by_discovery_type": {key: dict(sorted(value.items())) for key, value in sorted(by_type.items())}, "outlets": outlets}

    ready = [o for o in outlets if o["stage"] in ("ACQUISITION_VERIFIED", "OPERATIONALLY_STABLE") and o["restriction"] is None]
    partial = [o for o in outlets if o["stage"] not in ("ACQUISITION_VERIFIED", "OPERATIONALLY_STABLE", "NOT_REGISTERED") and o["item_pages_2xx_all_runs"] > 0 and o["restriction"] != "HELD_ACCESS_CONTROL"]

    def intake_entry(o: dict[str, Any], tier: str) -> dict[str, Any]:
        usable = [c for c in o["channels"] if c["class"] in ("WORKS", "LISTING_WITH_RULE")]
        return {"outlet_id": o["outlet_id"], "country_id": o["country_id"], "name": o["name"], "tier": tier, "web_origins": o["web_origins"],
                "channels": [{"channel_id": c["channel_id"], "kind": c["kind"], "url": c["url"], "formats": c["formats"], "entries_last": c["entries_last"],
                              "candidates_last": c["candidates_last"], "item_pages_2xx": c["item_pages_2xx"]} for c in usable],
                "channels_not_usable": {c["channel_id"]: c["class"] for c in o["channels"] if c["class"] not in ("WORKS", "LISTING_WITH_RULE", "NOT_READ")},
                "possible_redundancy": len(usable) > 1, "candidate_rule": o["candidate_rule"],
                "last_successful_acquisition": max((r["run_id"] for r in o["runs"] if r["items_2xx"]), default=None),
                "fixity_and_replay": o["replay"], "item_pages_2xx_all_runs": o["item_pages_2xx_all_runs"],
                "limits": {"min_interval_seconds_per_origin": max(policy["rate_limit"]["min_interval_seconds_per_origin"], o["robots_crawl_delay_seconds"] or 0),
                           "concurrent_requests_per_origin": 1, "robots_crawl_delay_seconds_observed": o["robots_crawl_delay_seconds"]},
                "starting_poll_interval_minutes": {"feed": 60, "news_sitemap": 60, "sitemap_index": 360, "listing": 120},
                "extraction_open": bool(o["extraction_last_run"] and o["extraction_last_run"]["labelled"] and o["extraction_last_run"]["below_the_article_text_floor"] * 2 >= o["extraction_last_run"]["labelled"]),
                "extraction_last_run": o["extraction_last_run"]}

    def priority(o: dict[str, Any]) -> tuple[int, str]:
        return (countries[o["country_id"]]["acquisition_verified"], o["outlet_id"])        # the thinnest countries first

    readiness = {
        "schema": READINESS_SCHEMA, "readiness_version": arguments.version,
        "status": "PREPARED — starts nothing and activates nothing; a 12- or 24-hour intake is a separate, separately authorised run; external_acquisition stays disabled",
        "derived_from": {"inventory_version": arguments.version, "inputs": inputs},
        "not_a_claim": "technical readiness from single bounded runs; no outlet is operationally stable; the poll intervals are starting values chosen for a first measurement, not measured rates; no statement about the press of any country",
        "tiers": {"A": "ACQUISITION_VERIFIED and not held: use", "B": "item pages preserved, fewer than the stage asks: use, and expect less"},
        "outlets": [intake_entry(o, "A") for o in sorted(ready, key=priority)] + [intake_entry(o, "B") for o in sorted(partial, key=priority)],
        "holds": sorted(o["outlet_id"] for o in outlets if o["restriction"] == "HELD_ACCESS_CONTROL"),
        "excluded": {o["outlet_id"]: o["restriction"] for o in outlets if o["stage"] == "NOT_REGISTERED"},
        "not_ready": {o["outlet_id"]: o["restriction"] for o in outlets if o["stage"] in ("REGISTERED", "TECHNICALLY_QUALIFIED") and o not in partial and o["restriction"] != "HELD_ACCESS_CONTROL"},
        "global_limits": {"min_interval_seconds_per_origin": policy["rate_limit"]["min_interval_seconds_per_origin"], "crawl_delay": policy["rate_limit"]["crawl_delay"],
                          "crawl_delay_max_seconds": policy["rate_limit"]["crawl_delay_max_seconds"], "concurrent_requests_per_origin": 1, "attempts_per_request": 1},
        "disabled_channels": policy["disabled_channels"], "candidate_rules": {key: value["version"] for key, value in sorted(rules.items())}}
    readiness["totals"] = {"outlets_tier_a": len(ready), "outlets_tier_b": len(partial),
                           "channels": sum(len(e["channels"]) for e in readiness["outlets"]),
                           "countries": sorted({e["country_id"] for e in readiness["outlets"]}),
                           "outlets_with_open_extraction": sum(e["extraction_open"] for e in readiness["outlets"])}

    lines = [f"# Source qualification {arguments.version}", "",
             "Generated by `scripts/build_intake_readiness.py` from tracked evidence. Not edited by hand. A stage is what the evidence shows, not a judgement about an outlet.", "",
             "## Totals", "", "| | |", "|---|---|",
             f"| outlet hypotheses | {len(outlets)} |", f"| registered | {inventory['totals']['registered']} |",
             *[f"| stage `{stage}` | {count} |" for stage, count in sorted(stage_counts.items())],
             f"| outlets with at least one preserved item page | {inventory['totals']['with_any_preserved_item_page']} |",
             f"| item pages (2xx) preserved, all runs | {inventory['totals']['item_pages_2xx_all_runs']} |",
             f"| real requests, all runs | {requests_total} |", "",
             "## By country", "", "| Country | Hypotheses | Registered | Verified | Qualified only | Any item page | Working channels | Held | Verified outlets |", "|---|---|---|---|---|---|---|---|---|",
             *[f"| {c} | {v['hypotheses']} | {v['registered']} | {v['acquisition_verified']} | {v['technically_qualified_only']} | {v['with_any_preserved_item_page']} | {v['working_channels']} | {len(v['held'])} | {', '.join(v['verified_outlets']) or '—'} |"
               for c, v in countries.items()], "",
             "## By discovery type (channels that were read)", "", "| Type | Result | Channels |", "|---|---|---|",
             *[f"| {key} | {klass} | {count} |" for key, value in sorted(by_type.items()) for klass, count in sorted(value.items())], "",
             "## By restriction (why an outlet is not verified)", "", "| Restriction | Outlets |", "|---|---|",
             *[f"| {key} | {count} |" for key, count in sorted(Counter(o['restriction'] or 'none (verified)' for o in outlets).items())], "",
             "## By outlet", "", "| Outlet | Country | Name | Registration | Stage | Channels read → class | Item pages 2xx (best run / all) | Preservation / replay | Restriction | Next |", "|---|---|---|---|---|---|---|---|---|---|"]
    for o in outlets:
        read = "; ".join(f"{c['channel_id'].split(':ch:')[1]} ({c['kind']}) → {c['class']}" for c in o["channels"] if c["class"] != "NOT_READ") or "—"
        lines.append(f"| `{o['outlet_id']}` | {o['country_id']} | {o['name']} | {o['registration_status']} | {o['stage']} | {read} | {o['item_pages_2xx_best_run']} / {o['item_pages_2xx_all_runs']} | "
                     f"{o['preservation']} / {o['replay']} | {o['restriction'] or '—'} | {o['next_step']} |")
    arguments.out_inventory.write_bytes(record_json(inventory))
    arguments.out_readiness.write_bytes(record_json(readiness))
    arguments.out_md.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    print(json.dumps({"totals": inventory["totals"], "readiness": readiness["totals"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
