"""Build the source-discovery inventory: per outlet, what is known about how it can be read (CPD-0019 §7).

One deterministic join of four kinds of evidence, each kept apart and named:

* the **registry** (what was imported from the legacy system, what is registered);
* the **legacy discovery audit** (``scripts/legacy_discovery_audit.py``): what the legacy system's own
  records show about each channel and each outlet;
* **prediscovery research** files: what passive research found on a stated day — search results and
  third-party pages only, no request to any publisher. Hypotheses, never observations of a server;
* the **replay of a canary's preserved answers** (``scripts/replay_canary_findings.py``) and the
  canary's verification: the only observations of real servers there are.

The inventory states for every outlet six analytic flags (IMPORTED, DISCOVERED, QUALIFIED,
REGISTERED, ACQUISITION_VERIFIED, OPERATIONALLY_STABLE), a route class, obstacles and a priority
with the rule that produced it. The flags are a reading aid, not a state machine: no normative state
of the registry or of a fetch is changed by them.

Forward-only: an inventory is written once per version. A later run with new evidence writes a new
version beside the old one; it does not rewrite a prediscovery file or an earlier inventory.

    python scripts/build_source_discovery_inventory.py --registry … --legacy-audit … \
        --prediscovery g1.json g2.json g3.json --canary-replay … --canary-items outlet=n … \
        --version 2026-10-09.1 --out-json … --out-md …
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "coprepan-source-discovery-inventory/v1"
FLAGS = ("IMPORTED", "DISCOVERED", "QUALIFIED", "REGISTERED", "ACQUISITION_VERIFIED", "OPERATIONALLY_STABLE")
STANDARD_TYPES = ("rss", "atom", "news_sitemap", "section_feed", "sitemap")
ACQUISITION_VERIFIED_MIN_ITEMS = 5
RULES = {
    "IMPORTED": "the outlet or channel is a row of the legacy import (registry `legacy_observed`)",
    "DISCOVERED": "at least one possible discovery channel is known: a legacy channel, or a candidate of a prediscovery file. "
                  "Known is not tested",
    "QUALIFIED": "COPREPAN 3.0 itself has read a channel document of the outlet from a real server and the current parser finds "
                 "at least one item entry with a usable address in it (from preserved bytes; a replay counts, a search result does not)",
    "REGISTERED": "registry `registration_status` is `registered` (a registration record exists)",
    "ACQUISITION_VERIFIED": f"in one bounded run at least {ACQUISITION_VERIFIED_MIN_ITEMS} item pages of the outlet were answered 2xx, "
                            "are RAW_PRESERVED with verified fixity, and their extraction was replayed without network. One run: "
                            "a technical single success, nothing about duration",
    "OPERATIONALLY_STABLE": "ACQUISITION_VERIFIED in at least three runs on at least three different days within an observation "
                            "window of at least fourteen days, with no access-control hold in between. No outlet can have it yet",
}
PRIORITY_RULE = ("priority_score = country_need x feasibility x coverage_gain. country_need: 3 when no outlet of the country was "
                 "LEGACY_PRODUCTIVE_REPEATED, 2 when exactly one was, else 1. feasibility: 3 for a standard channel candidate with "
                 "search evidence of 2026-10-09 or legacy success evidence, 2 for a standard or index candidate with legacy "
                 "evidence only, 1 for a listing-only or pattern-inferred route, 0 when the outlet is closed, held by an access "
                 "control or has no known route. coverage_gain: 2 when the legacy system never got a usable article from the "
                 "outlet (LEGACY_NEVER_PRODUCTIVE, LEGACY_NO_CHANNEL), else 1. A stated scenario rule for ordering work, not a "
                 "measurement and not a statement about an outlet's worth")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def route_class(status: str, held: bool, candidates: list[dict[str, Any]], legacy_channels: list[dict[str, Any]]) -> str:
    if status == "closed":
        return "CLOSED"
    if held:
        return "ACCESS_CONTROL_HOLD"
    types = {c["type"] for c in candidates if c.get("url")} | {"sitemap_index" if c["kind"] == "sitemap_index" else c["kind"] for c in legacy_channels}
    types.discard("unknown")
    if types & set(STANDARD_TYPES):
        return "STANDARD_CHANNEL_CANDIDATE"
    if "sitemap_index" in types:
        return "INDEX_EXPANSION_CANDIDATE"
    if "html_listing" in types:
        return "LISTING_ONLY"
    return "NO_ROUTE_KNOWN"


def feasibility(route: str, candidates: list[dict[str, Any]], legacy_channels: list[dict[str, Any]]) -> int:
    if route in ("CLOSED", "ACCESS_CONTROL_HOLD", "NO_ROUTE_KNOWN"):
        return 0
    if route == "LISTING_ONLY":
        return 1
    standard_now = [c for c in candidates if c.get("url") and c["type"] in STANDARD_TYPES]
    legacy_success = any(c["legacy_productivity_class"].startswith("PRODUCTIVE") for c in legacy_channels)
    if route == "STANDARD_CHANNEL_CANDIDATE" and (any(c["evidence_level"] == "search_evidence" for c in standard_now) or legacy_success):
        return 3
    if all(c["evidence_level"] == "cms_pattern_inference" for c in candidates if c.get("url")) and not legacy_channels:
        return 1
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--legacy-audit", type=Path, required=True)
    parser.add_argument("--prediscovery", type=Path, nargs="+", required=True)
    parser.add_argument("--canary-replay", type=Path, required=True)
    parser.add_argument("--canary-verification", type=Path, required=True)
    parser.add_argument("--canary-measurement", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, required=True)
    arguments = parser.parse_args(argv)
    for out in (arguments.out_json, arguments.out_md):
        if out.exists():
            raise SystemExit(f"{out.name} exists: an inventory version is written once")

    registry, audit, replay = load(arguments.registry), load(arguments.legacy_audit), load(arguments.canary_replay)
    verification, measurement = load(arguments.canary_verification), load(arguments.canary_measurement)
    research: dict[str, dict[str, Any]] = {}
    proposals: list[dict[str, Any]] = []
    checked_on = set()
    for path in arguments.prediscovery:
        document = load(path)
        checked_on.add(document["checked_on"])
        for outlet in document["outlets"]:
            if outlet["outlet_id"] in research:
                raise SystemExit(f"{outlet['outlet_id']} is in two prediscovery files")
            research[outlet["outlet_id"]] = {**outlet, "_file": path.name}
        proposals += [{**proposal, "_file": path.name} for proposal in document["proposed_new_outlets"]]

    held_origins = replay["origins_held_for_a_next_canary"]
    replay_documents: dict[str, list[dict[str, Any]]] = {}
    for row in replay["channel_documents"]:
        replay_documents.setdefault(row["outlet_id"], []).append(row)
    replay_robots = {row["outlet_id"]: row for row in replay["robots_files"]}
    canary_items = {outlet: row["items_fetched"] for outlet, row in measurement["outlets"].items()}
    canary_verified = verification["status"] == "PASS"
    repeated_by_country = Counter(o["country_id"] for o in audit["outlets"].values() if o["outlet_class"] == "LEGACY_PRODUCTIVE_REPEATED")

    outlets = []
    for entry in registry["outlets"]:
        outlet_id = entry["outlet_id"]
        legacy, found = audit["outlets"][outlet_id], research.get(outlet_id)
        if found is None:
            raise SystemExit(f"{outlet_id}: no prediscovery record")
        legacy_by_channel = {c["channel_id"]: c for c in legacy["channels"]}
        observed = {row["channel_id"]: row for row in replay_documents.get(outlet_id, [])}
        channels = []
        for channel in entry["channels"]:
            past = legacy_by_channel[channel["channel_id"]]
            seen = observed.get(channel["channel_id"])
            channels.append({
                "channel_id": channel["channel_id"], "kind": channel["kind"], "url": channel["url_history"][-1]["url"],
                "provenance": "legacy_import", "legacy_feed_id": past["legacy_feed_id"],
                "legacy_productivity_class": past["productivity_class"], "legacy_fail_category": past.get("fail_category"),
                "legacy_status": past["legacy_status"].get("status"), "legacy_last_success_at": past["legacy_status"].get("last_success_at"),
                "v3_observation": None if seen is None else {
                    "from": "replay of the canary answer of 2026-10-08 under the current parser", "final_url": seen["url"],
                    "outcome": seen["outcome_now"], "format": seen["format"], "item_entries_with_url": seen["item_entries_with_url"],
                    "child_documents": seen["child_documents"], "body_sha256": seen["body_sha256"]},
                "flags": [flag for flag, on in (("IMPORTED", True), ("DISCOVERED", True),
                                                ("QUALIFIED", bool(seen and seen["outcome_now"] == "PARSED" and seen["item_entries_with_url"] > 0)),
                                                ("REGISTERED", entry["registration_status"] == "registered")) if on],
            })
        candidates = [{"type": c["type"], "url": c.get("url"), "evidence_level": c["evidence_level"], "source": c.get("source"),
                       "note": c.get("note"), "checked_on": load_checked(found, arguments.prediscovery), "provenance": found["_file"]}
                      for c in found["candidate_channels"]]
        status = found["operating_status"]["value"]
        held = sorted(origin for origin in held_origins if origin in entry["web_origins"])
        route = route_class(status, bool(held), candidates, channels)
        need = 3 if repeated_by_country[entry["country_id"]] == 0 else 2 if repeated_by_country[entry["country_id"]] == 1 else 1
        feasible = feasibility(route, candidates, channels)
        gain = 2 if legacy["outlet_class"] in ("LEGACY_NEVER_PRODUCTIVE", "LEGACY_NO_CHANNEL") else 1
        items = canary_items.get(outlet_id, 0)
        flags = {
            "IMPORTED": True,
            "DISCOVERED": bool(channels) or any(c["url"] for c in candidates),
            "QUALIFIED": any("QUALIFIED" in c["flags"] for c in channels),
            "REGISTERED": entry["registration_status"] == "registered",
            "ACQUISITION_VERIFIED": canary_verified and items >= ACQUISITION_VERIFIED_MIN_ITEMS,
            "OPERATIONALLY_STABLE": False,
        }
        articles = legacy["articles_in_database"]
        robots_row = replay_robots.get(outlet_id)
        outlets.append({
            "outlet_id": outlet_id, "country_id": entry["country_id"], "display_name": entry["display_names"][0]["name"],
            "web_origins": entry["web_origins"], "registration_status": entry["registration_status"],
            "flags": [flag for flag in FLAGS if flags[flag]],
            "legacy": {
                "outlet_class": legacy["outlet_class"], "ok_rows": articles.get("ok_rows", 0), "rows": articles.get("rows", 0),
                "article_status": articles.get("by_status", {}), "ok_fetch_days": articles.get("ok_fetch_days", 0),
                "first_ok_fetch_day": articles.get("first_ok_fetch_day"), "last_ok_fetch_day": articles.get("last_ok_fetch_day"),
                "json_raw_files": (legacy["on_disk"].get("json_raw") or {}).get("files", 0) if isinstance(legacy.get("on_disk"), dict) else None,
                "channels_by_productivity_class": legacy["channel_counts"]["by_productivity_class"],
                "last_discovery_run": legacy["discovery_runs"].get("last_run_category"),
                "discovery_run_categories": legacy["discovery_runs"].get("by_category", {}),
            },
            "channels": channels,
            "research": {
                "checked_on": load_checked(found, arguments.prediscovery), "provenance": found["_file"],
                "method": "passive web research; no request to any publisher; every entry is a hypothesis for a gated probe",
                "operating_status": found["operating_status"], "current_origins": found.get("current_origins", []),
                "cms": found.get("cms"), "candidate_channels": candidates, "obstacles": found.get("obstacles", []),
                "owner_group": found.get("owner_group"), "outlet_type": found.get("outlet_type"), "city": found.get("city"),
                "recommended_approach": found.get("recommended_approach"), "research_priority": found.get("priority"),
                "research_priority_reason": found.get("priority_reason"), "open_questions": found.get("open_questions", []),
            },
            "v3_evidence": {
                "canary_2026_10_08": None if outlet_id not in measurement["outlets"] else {
                    "run_id": measurement["run_id"], "real_requests": measurement["outlets"][outlet_id]["real_requests"],
                    "items_fetched": items, "verification": verification["status"],
                    "robots_readable_now": None if robots_row is None else not robots_row["parse_error_now"],
                    "robots_sitemaps": [] if robots_row is None else robots_row["sitemaps"]},
                "access_control_hold": [{"origin": origin, "class": held_origins[origin],
                                         "basis": "preserved answer of 2026-10-08, read by the current classifier"} for origin in held],
            },
            "route_class": route,
            "structural_notes": sorted({note for note in (
                "origins differ between registry and research" if set(found.get("current_origins") or entry["web_origins"]) != set(entry["web_origins"]) else None,
                "only sitemap indexes among the legacy channels: the legacy system never expanded one" if channels and all(c["kind"] == "sitemap_index" for c in channels) else None,
                "legacy discovery ended on its TDM opt-out heuristic" if legacy["discovery_runs"].get("last_run_category") == "tdm_opt_out_detected" else None,
                "legacy fetched pages and its extractor rejected nearly all of them" if articles.get("rows", 0) >= 100 and articles.get("ok_rows", 0) * 20 < articles.get("rows", 0) else None,
            ) if note}),
            "priority": {"score": need * feasible * gain, "country_need": need, "feasibility": feasible, "coverage_gain": gain},
        })

    by_flag = {flag: sum(1 for o in outlets if flag in o["flags"]) for flag in FLAGS}
    inventory = {
        "schema": SCHEMA, "inventory_version": arguments.version,
        "what_this_is": "a reading aid that joins evidence of four kinds; the registry, the request log and the preserved packs stay the records",
        "inputs": {
            "registry": {"file": arguments.registry.name, "sha256": sha256_of(arguments.registry)},
            "legacy_audit": {"file": arguments.legacy_audit.name, "sha256": sha256_of(arguments.legacy_audit), "schema": audit["schema"],
                             "legacy_database_sha256": audit["inputs"]["database_copy"]["sha256"]},
            "prediscovery": [{"file": path.name, "sha256": sha256_of(path)} for path in arguments.prediscovery],
            "canary_replay": {"file": arguments.canary_replay.name, "sha256": sha256_of(arguments.canary_replay)},
            "canary_verification": {"file": arguments.canary_verification.name, "sha256": sha256_of(arguments.canary_verification)},
            "canary_measurement": {"file": arguments.canary_measurement.name, "sha256": sha256_of(arguments.canary_measurement)},
        },
        "prediscovery_checked_on": sorted(checked_on),
        "flag_rules": RULES, "priority_rule": PRIORITY_RULE,
        "totals": {
            "outlets": len(outlets), "channels": sum(len(o["channels"]) for o in outlets),
            "researched_candidate_channels": sum(len(o["research"]["candidate_channels"]) for o in outlets),
            "outlets_by_flag": by_flag,
            "channels_qualified": sum(1 for o in outlets for c in o["channels"] if "QUALIFIED" in c["flags"]),
            "outlets_by_route_class": dict(sorted(Counter(o["route_class"] for o in outlets).items())),
            "outlets_by_legacy_class": dict(sorted(Counter(o["legacy"]["outlet_class"] for o in outlets).items())),
            "outlets_by_operating_status": dict(sorted(Counter(o["research"]["operating_status"]["value"] for o in outlets).items())),
            "countries": len({o["country_id"] for o in outlets}),
            "countries_with_acquisition_verified_outlet": sorted({o["country_id"] for o in outlets if "ACQUISITION_VERIFIED" in o["flags"]}),
            "countries_without_legacy_repeated_outlet": sorted({o["country_id"] for o in outlets} - set(repeated_by_country)),
        },
        "outlets": outlets,
        "proposed_new_outlets": [{k: v for k, v in proposal.items() if k != "_file"} | {"provenance": proposal["_file"], "status": "PROPOSAL_ONLY"}
                                 for proposal in sorted(proposals, key=lambda p: (p["country_id"], p["name"]))],
    }
    arguments.out_json.write_bytes((json.dumps(inventory, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    arguments.out_md.write_bytes(render(inventory).encode("utf-8"))
    print(json.dumps(inventory["totals"], indent=1, sort_keys=True))
    return 0


def load_checked(found: dict[str, Any], files: list[Path]) -> str:
    return next(load(path)["checked_on"] for path in files if path.name == found["_file"])


def render(inventory: dict[str, Any]) -> str:
    totals = inventory["totals"]
    lines = [
        f"# Source discovery inventory — version {inventory['inventory_version']}", "",
        "**Generated** by `scripts/build_source_discovery_inventory.py` from the JSON beside it; do not edit. A reading aid: the",
        "registry, the request log and the preserved packs stay the records. Prediscovery entries are **hypotheses** from passive",
        "research (search results and third-party pages; no request to any publisher) and are not observations of a server.", "",
        f"Outlets: {totals['outlets']} in {totals['countries']} countries. Legacy channels: {totals['channels']}. "
        f"Researched candidate channels: {totals['researched_candidate_channels']}.", "",
        "| Flag | Outlets | Rule |", "|---|---|---|"]
    lines += [f"| `{flag}` | {totals['outlets_by_flag'][flag]} | {inventory['flag_rules'][flag]} |" for flag in FLAGS]
    lines += ["", "Route classes: " + ", ".join(f"`{k}` {v}" for k, v in totals["outlets_by_route_class"].items()) + ".", "",
              "Priority: " + inventory["priority_rule"] + ".", "",
              "| Outlet | Legacy class | Legacy `ok` rows | Status (research) | Route class | Flags | Best researched candidate (evidence) | Score |",
              "|---|---|---|---|---|---|---|---|"]
    order = {"search_evidence": 0, "legacy_evidence": 1, "cms_pattern_inference": 2, "unknown": 3}
    for outlet in inventory["outlets"]:
        with_url = sorted((c for c in outlet["research"]["candidate_channels"] if c["url"] and "<" not in c["url"] and ".." not in c["url"]),
                          key=lambda c: (c["type"] == "html_listing", order.get(c["evidence_level"], 9)))
        best = f"{with_url[0]['type']} `{with_url[0]['url']}` ({with_url[0]['evidence_level']})" if with_url else "none"
        lines.append(f"| `{outlet['outlet_id']}` | {outlet['legacy']['outlet_class'].replace('LEGACY_', '')} | {outlet['legacy']['ok_rows']} | "
                     f"{outlet['research']['operating_status']['value']} | {outlet['route_class']} | "
                     f"{', '.join(f.replace('ACQUISITION_', 'ACQ_') for f in outlet['flags'])} | {best} | {outlet['priority']['score']} |")
    lines += ["", f"## Proposed new outlets ({len(inventory['proposed_new_outlets'])}; proposals only, nothing registered)", "",
              "| Country | Name | Origin | First candidate (evidence) |", "|---|---|---|---|"]
    for proposal in inventory["proposed_new_outlets"]:
        with_url = [c for c in proposal.get("candidate_channels", []) if c.get("url")]
        best = f"{with_url[0]['type']} `{with_url[0]['url']}` ({with_url[0]['evidence_level']})" if with_url else "none found"
        lines.append(f"| {proposal['country_id']} | {proposal['name']} | {proposal.get('origin') or 'unknown'} | {best} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
