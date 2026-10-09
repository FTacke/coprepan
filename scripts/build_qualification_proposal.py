"""One registration proposal for every outlet hypothesis the repository knows, and a disposition for each (CPD-0025).

Reads the registry, the source-discovery inventory, the qualification overview and what the canaries
have shown, and decides by stated rules — never by hand — whether a hypothesis can be registered for a
bounded qualification or is deferred, and why. It registers nothing: the proposal it writes is applied
with ``scripts/apply_registration_proposal.py``.

    python scripts/build_qualification_proposal.py --date 2026-10-09 --out-proposal <file> --out-dispositions <file>

The rules, in order (the first that applies decides):

- an outlet that is registered already keeps its registration;
- ``LEGAL_HOLD``: an outlet excluded until a licence / TDM decision (``co_el_tiempo``);
- ``CLOSED``: research found the outlet closed;
- ``DOMAIN_CHANGE``: research found it moved to another host — its canonical origin would be a dead one;
- ``IDENTITY_OPEN``: an identity case recorded as open (which title an origin belongs to; channels on another outlet's host);
- ``NO_ORIGIN`` / ``HOST_HELD``: no origin is known, or the host is an origin of another outlet;
- ``NO_EVIDENCED_CHANNEL``: no channel is known from the legacy system, a search result or the publisher —
  an address inferred from how a content system usually looks is a guess, and a guess is not requested;
- otherwise ``REGISTER``: identity, country and origin are known and at least one channel is evidenced.

Nothing here is a claim that a channel works: every address is a hypothesis until a canary has read it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from coprepan import naming, registry as registry_module  # noqa: E402
from coprepan.canonical import record_json, sha256_bytes  # noqa: E402

DISCOVERY = REPOSITORY / "config" / "source_discovery"
INVENTORY = DISCOVERY / "source_discovery_inventory_2026-10-09.1.json"
OVERVIEW = DISCOVERY / "source_qualification_overview_2026-10-09.2.json"
PROPOSAL_SCHEMA = "coprepan-registry-registration-proposal/v1"
DISPOSITION_SCHEMA = "coprepan-qualification-dispositions/v1"
LEGAL_HOLD = {"co_el_tiempo": "excluded until a separate licence / TDM decision (the operator's brief of 2026-10-09)"}
IDENTITY_OPEN = {
    "pr_primera_hora": "every channel the registry holds for it is on the host of pr_el_nuevo_dia; it has no evidenced channel of its own",
    "cl_el_mercurio": "the registry's origin is emol.com, the group's free portal; whether the outlet is Emol or El Mercurio is an open corpus-supply decision"}
# The IANA zone of the outlet's country (of its capital where the country has several): the basis of every earlier registration.
TIMEZONES = {"ar": "America/Argentina/Buenos_Aires", "bo": "America/La_Paz", "cl": "America/Santiago", "co": "America/Bogota",
             "cr": "America/Costa_Rica", "cu": "America/Havana", "do": "America/Santo_Domingo", "ec": "America/Guayaquil", "es": "Europe/Madrid",
             "gt": "America/Guatemala", "hn": "America/Tegucigalpa", "mx": "America/Mexico_City", "ni": "America/Managua", "pa": "America/Panama",
             "pe": "America/Lima", "pr": "America/Puerto_Rico", "py": "America/Asuncion", "sv": "America/El_Salvador", "us": "America/New_York",
             "uy": "America/Montevideo", "ve": "America/Caracas"}
EVIDENCED = ("search_evidence", "publisher_documented", "publisher_page_observed")
KIND_OF = {"rss": "rss", "section_feed": "rss", "publisher_rss": "rss", "atom": "atom", "news_sitemap": "sitemap", "sitemap": "sitemap",
           "sitemap_index": "sitemap_index", "html_listing": "section_page", "publisher_html_section": "section_page",
           "publisher_html_archive": "archive", "publisher_html_edition": "section_page", "publisher_html_sections": "section_page"}
USABLE_KINDS = ("rss", "atom", "sitemap", "sitemap_index", "section_page", "archive")
LEGACY_RANK = {"PRODUCTIVE_REPEATED": 0, "PRODUCTIVE_ONCE_OR_SPORADIC": 1, "NO_EVIDENCE": 3, "NEVER_SUCCESSFUL": 4}
STATUS_RANK = {"active": 0, "technically_empty": 1, "inactive": 2}
UNKNOWN_FIELDS = ["access_model", "city", "medium", "outlet_group", "outlet_type", "region", "scope"]
HOW_RESEARCH = "passive web research of 2026-10-09 (search results and third-party pages); no page of the outlet was fetched by this project"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def host(address: str) -> str:
    name = (urlsplit(address).hostname or "").lower()
    return name[4:] if name.startswith("www.") else name


def origin_of(address: str) -> str:
    parts = urlsplit(address)
    return f"{parts.scheme}://{parts.netloc.lower()}"


def new_channels(outlet_id: str, origins: list[str], candidates: list[dict[str, Any]], known_urls: set[str], taken: set[str]) -> list[dict[str, Any]]:
    """Channels to add from research: evidenced, of a usable kind, on an origin of the outlet, not known yet."""
    hosts, added, counters = {host(origin) for origin in origins}, [], {}
    for candidate in candidates:
        kind = KIND_OF.get(candidate["type"])
        level = candidate.get("evidence_level") or candidate.get("evidence")
        if kind is None or level not in EVIDENCED or candidate["url"] in known_urls or host(candidate["url"]) not in hosts:
            continue
        known_urls.add(candidate["url"])
        while True:
            counters[kind] = counters.get(kind, 0) + 1
            identifier = f"{outlet_id}:ch:{kind}_r{counters[kind]:03d}"
            if identifier not in taken:
                break
        taken.add(identifier)
        added.append({"channel_id": identifier, "kind": kind, "url": candidate["url"], "valid_from": "unknown",
                      "_evidence": {"claim": f"channel {identifier} ({kind}) at {candidate['url']}: {level}; a hypothesis until a canary has read it",
                                    "how": HOW_RESEARCH, "source": str(candidate.get("source") or candidate.get("from") or "research file of 2026-10-09")}})
    return added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--date", required=True)
    parser.add_argument("--out-proposal", type=Path, required=True)
    parser.add_argument("--out-dispositions", type=Path, required=True)
    arguments = parser.parse_args(argv)
    for out in (arguments.out_proposal, arguments.out_dispositions):
        if out.exists():
            raise SystemExit(f"{out.name} exists: written once")

    registry_document = load(REPOSITORY / "config" / "outlet_registry.json")
    inventory = {outlet["outlet_id"]: outlet for outlet in load(INVENTORY)["outlets"]}
    overview = load(OVERVIEW)
    held_hosts = {host(origin): outlet["outlet_id"] for outlet in registry_document["outlets"] for origin in outlet["web_origins"]}
    registry_ids = {outlet["outlet_id"] for outlet in registry_document["outlets"]}
    taken_ids = set(registry_ids)
    proposed, arriving, dispositions = [], [], []

    for outlet in registry_document["outlets"]:
        identifier, country = outlet["outlet_id"], outlet["country_id"]
        name = outlet["display_names"][-1]["name"]
        base = {"outlet_id": identifier, "country_id": country, "name": name, "in_registry_before": True, "origins": outlet["web_origins"]}
        if outlet["registration_status"] == "registered":
            dispositions.append({**base, "disposition": "ALREADY_REGISTERED", "reason": "registered by an earlier record"})
            continue
        known = inventory[identifier]
        status = known["research"]["operating_status"]
        usable = [c for c in outlet["channels"] if c["kind"] in USABLE_KINDS]
        added = new_channels(identifier, outlet["web_origins"], known["research"]["candidate_channels"],
                             {c["url_history"][-1]["url"] for c in outlet["channels"]}, {c["channel_id"] for c in outlet["channels"]})
        if identifier in LEGAL_HOLD:
            decision = ("LEGAL_HOLD", LEGAL_HOLD[identifier])
        elif status["value"] == "closed":
            decision = ("CLOSED", status["evidence"])
        elif status["value"] == "moved":
            decision = ("DOMAIN_CHANGE", status["evidence"])
        elif identifier in IDENTITY_OPEN:
            decision = ("IDENTITY_OPEN", IDENTITY_OPEN[identifier])
        elif not outlet["web_origins"]:
            decision = ("NO_ORIGIN", "the registry holds no origin for it")
        elif not usable and not added:
            decision = ("NO_EVIDENCED_CHANNEL", "no channel from the legacy system, a search result or the publisher; addresses inferred from a content system's usual layout are not requested")
        else:
            decision = ("REGISTER", "identity, country and origin known; at least one evidenced channel")
        dispositions.append({**base, "disposition": decision[0], "reason": decision[1], "operating_status": status["value"],
                             "legacy_class": known["legacy"]["outlet_class"] if isinstance(known.get("legacy"), dict) and "outlet_class" in known["legacy"] else None})
        if decision[0] != "REGISTER":
            continue
        by_legacy = {c["channel_id"]: c for c in known["channels"]}

        def rank(channel: dict[str, Any]) -> tuple[int, int]:
            past = by_legacy.get(channel["channel_id"])
            return (LEGACY_RANK.get(past["legacy_productivity_class"], 3), STATUS_RANK.get(past["legacy_status"], 2)) if past else (2, 0)

        every = [*outlet["channels"], *added]
        order = [c["channel_id"] for c in sorted(every, key=lambda c: (*rank(c), every.index(c)))]
        evidence = [{"claim": f"operating status: {status['value']} — {status['evidence']}", "how": HOW_RESEARCH, "source": str(status.get("source") or "research file of 2026-10-09")},
                    {"claim": f"{len(outlet['channels'])} channels of the legacy import, ordered by what the legacy system recorded about them (productive first); none tested by this project",
                     "how": "the legacy discovery audit of 2026-10-09, read from a copy of the legacy database", "source": "config/source_discovery/legacy_discovery_audit_2026-10-09.json"},
                    *[c["_evidence"] for c in added]]
        proposed.append({
            "outlet_id": identifier, "display_name": name, "attributes_set": {"same_outlet_basis": "not_applicable", "timezone": TIMEZONES[country]},
            "attributes_left_unknown": UNKNOWN_FIELDS, "web_origins": outlet["web_origins"],
            "url_rules": {"version": f"{identifier}-url-rules/v1", "basis": "the generic rules (no significant query parameter, no variant marker); not derived from this outlet's URLs"},
            "new_channels": [{k: v for k, v in c.items() if k != "_evidence"} for c in added], "channel_order": order, "channels_disabled_for_the_canary": [],
            "review_notes_cleared": list(outlet["review_notes"]), "judgements_for_the_reviewer": [], "legacy_class": dispositions[-1]["legacy_class"],
            "route_class": known["route_class"], "why_in_the_set": "every outlet hypothesis with an evidenced channel is qualified (CPD-0025)", "evidence": evidence})

    for candidate in overview["outlet_candidates"]:
        country, name = candidate["country_id"], candidate["name"]
        identifier = candidate["proposed_outlet_id"] or f"{country}_{registry_module.propose_slug(name)}"
        base = {"outlet_id": identifier, "country_id": country, "name": name, "in_registry_before": False, "origins": [candidate["origin"]] if candidate["origin"] else []}
        if identifier in registry_ids:        # a research candidate that has entered the registry since (wave C): one hypothesis, its registry row
            continue
        if not candidate["origin"]:
            decision = ("NO_ORIGIN", "research names the outlet and no origin")
        elif host(candidate["origin"]) in held_hosts or candidate["host_is_a_registry_origin_of"]:
            decision = ("HOST_HELD", f"its host is an origin of {held_hosts.get(host(candidate['origin'])) or candidate['host_is_a_registry_origin_of']}")
        elif not naming.is_outlet_id(identifier) or identifier in taken_ids:
            decision = ("IDENTITY_OPEN", f"no free outlet id follows from the name ({identifier!r})")
        else:
            origin = origin_of(candidate["origin"])
            added = new_channels(identifier, [origin], candidate["addresses"], set(), set())
            decision = ("REGISTER", "identity, country and origin known from research; at least one evidenced channel") if added else (
                "NO_EVIDENCED_CHANNEL", "no channel from a search result or the publisher; addresses inferred from a content system's usual layout are not requested")
        dispositions.append({**base, "disposition": decision[0], "reason": decision[1], "operating_status": None, "legacy_class": None})
        if decision[0] != "REGISTER":
            continue
        taken_ids.add(identifier)
        held_hosts[host(origin)] = identifier
        arriving.append({
            "outlet_id": identifier, "country_id": country, "display_name": name,
            "attributes_set": {"same_outlet_basis": "not_applicable", "timezone": TIMEZONES[country]}, "attributes_left_unknown": UNKNOWN_FIELDS,
            "web_origins": [origin], "url_rules": {"version": f"{identifier}-url-rules/v1", "basis": "the generic rules; not derived from this outlet's URLs"},
            "new_channels": [{k: v for k, v in c.items() if k != "_evidence"} for c in added], "channel_order": [c["channel_id"] for c in added],
            "channels_disabled_for_the_canary": [],
            "judgements_for_the_reviewer": ["new to the registry: the id follows from the name; what kind of outlet it is (daily, digital native, broadcaster's site) is left unknown and is a corpus-supply judgement"],
            "supplement_priority": None, "why_in_the_set": "every outlet hypothesis with an evidenced channel is qualified (CPD-0025)",
            "evidence": [{"claim": f"the outlet {name} ({country}) at {origin}, named in {', '.join(candidate['named_in'])}", "how": HOW_RESEARCH,
                          "source": ", ".join(candidate["named_in"])}, *[c["_evidence"] for c in added]]})

    dispositions.sort(key=lambda row: (row["outlet_id"], row["in_registry_before"]))
    counts: dict[str, int] = {}
    for row in dispositions:
        counts[row["disposition"]] = counts.get(row["disposition"], 0) + 1
    proposal = {
        "schema": PROPOSAL_SCHEMA, "gate": "O-11", "record_stem": "qualification", "prepared_on": arguments.date,
        "status": "PROPOSAL — nothing in it is registered; it becomes a registration only when scripts/apply_registration_proposal.py is run with --write",
        "purpose": "every outlet hypothesis of the repository that has a known identity, country and origin and at least one evidenced channel, registered for a bounded qualification (CPD-0025)",
        "selection_rule": "by rule, not by choice: all hypotheses of the registry and of the research files, less those the rules of scripts/build_qualification_proposal.py defer (legal hold, closed, moved, open identity, no origin, host held, no evidenced channel)",
        "not_a_claim": "a registration for qualification; not a sample of the press of any country; no channel in it has been tested by this project; every address is a hypothesis; a registered outlet is not an outlet that yields articles",
        "timezone_basis": "the IANA zone of the outlet's country (of its capital where the country has several)",
        "inputs": {"registry_sha256_before": sha256_bytes(record_json(registry_document)),
                   "inventory": {"file": INVENTORY.name, "sha256": sha256_bytes(INVENTORY.read_bytes())},
                   "overview": {"file": OVERVIEW.name, "sha256": sha256_bytes(OVERVIEW.read_bytes())}},
        "policy_version_after": "canary/2026-10-09.1", "candidate_rules": {}, "candidate_rules_basis": "none: rules are written from preserved listing pages only",
        "open_for_the_operator": ["whether each outlet belongs in a press corpus (several are digital natives or broadcasters' sites); every such attribute is left unknown"],
        "proposed": proposed, "new_outlets": arriving}
    document = {"schema": DISPOSITION_SCHEMA, "prepared_on": arguments.date, "rules": __doc__.split("The rules, in order")[1].split("Nothing here")[0].strip(),
                "inputs": proposal["inputs"], "hypotheses": len(dispositions), "by_disposition": dict(sorted(counts.items())), "dispositions": dispositions}
    arguments.out_proposal.write_bytes(record_json(proposal))
    arguments.out_dispositions.write_bytes(record_json(document))
    print(json.dumps({"hypotheses": len(dispositions), "by_disposition": document["by_disposition"], "proposed": len(proposed), "new_outlets": len(arriving)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
