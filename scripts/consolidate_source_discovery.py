"""Consolidate every discovery finding into one qualification overview per source (CPD-0020 §5).

Joins, deterministically: the source-discovery inventory (registry, legacy audit, the three
prediscovery files, the first canary), the operator's external research supplement, and the
registration proposals with their reviews. It writes

* a machine-readable **qualification overview** (one record per registry outlet and per outlet
  candidate outside the registry, the classification of every supplement entry, the identity cases,
  a coverage table per country), and
* a **coverage report** page generated from it.

It is not a registry and creates none: an outlet candidate here has no ``outlet_id`` of the registry,
only a *proposed* one, and nothing is registered, qualified or acquired by being listed.

Analytic stages, a reading aid (the registry's own states are untouched):

    RESEARCHED -> CANDIDATE -> TECHNICALLY_QUALIFIED -> REGISTERED -> ACQUISITION_VERIFIED -> OPERATIONALLY_STABLE

The order is the order of evidence needed, not a ladder every source climbs: an outlet can be
REGISTERED without being TECHNICALLY_QUALIFIED. Each record lists the stages it has.

An overview version is written once.

    python scripts/consolidate_source_discovery.py --inventory … --supplement … --proposal … [--proposal …] \\
        --review … --version 2026-10-09.2 --out-json … --out-md …
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

SCHEMA = "coprepan-source-qualification-overview/v1"
STAGES = ("RESEARCHED", "CANDIDATE", "TECHNICALLY_QUALIFIED", "REGISTERED", "ACQUISITION_VERIFIED", "OPERATIONALLY_STABLE")
CLASSES = {
    "KNOWN_IDENTICAL": "the address is a channel of the registry already",
    "KNOWN_ADDITIONAL_EVIDENCE": "the address, a variant of it, or the feed a hub page documents was known from the registry or from earlier research; the supplement adds evidence",
    "NEW_CHANNEL_FOR_EXISTING_OUTLET": "a registry outlet; no earlier file names this address or the feed it documents",
    "OUTLET_ALREADY_PROPOSED": "not in the registry; the outlet is among the 60 proposals of the prediscovery files",
    "NEW_OUTLET_CANDIDATE": "not in the registry and not among the earlier proposals",
}
STAGE_RULES = {
    "RESEARCHED": "named in a research file with a source",
    "CANDIDATE": "a concrete discovery address is on file with an evidence level other than `unknown`",
    "TECHNICALLY_QUALIFIED": "this project read a channel document of the outlet from a real server and the current parser finds an item entry in it (the inventory's QUALIFIED)",
    "REGISTERED": "registry `registration_status` is `registered`",
    "ACQUISITION_VERIFIED": "the inventory's ACQUISITION_VERIFIED: at least 5 item pages 2xx, preserved, verified and replayed in one bounded run",
    "OPERATIONALLY_STABLE": "three such runs on three days within at least fourteen days, no hold in between (CPD-0019 §8)",
}
# Addresses a supplement entry gives only in its notes, as written there. Feeds a hub page documents.
NOTED_ADDRESSES = {
    "ec_el_universo": ["https://www.eluniverso.com/arc/outboundfeeds/rss/?outputType=xml"],
    "co_el_tiempo": ["https://www.eltiempo.com/rss/colombia.xml"],
    "pr_el_nuevo_dia": ["https://www.elnuevodia.com/arc/outboundfeeds/rss/?outputType=xml"],
    "uy_el_observador": ["https://www.elobservador.com.uy/rss/pages/ultimo-momento.xml"],
    "uy_montevideo_portal": ["https://www.montevideo.com.uy/anxml.aspx?58", "https://www.montevideo.com.uy/anxml.aspx?1303"],
    "bo_opinion": ["https://www.opinion.com.bo/rss/cochabamba/"],
    "ar_el_tribuno": ["https://www.eltribuno.com/rss-new/salta.rss", "https://www.eltribuno.com/rss-new/politica.rss"],
}
# What to do with each supplement entry. A judgement of this consolidation, with its reason; the
# classification above is computed, this is not.
DISPOSITIONS = {
    "ec_el_universo": ("EVIDENCE_FOR_REVIEWED_WAVE", "the publisher's own RSS page corroborates the Arc feed already in the reviewed first wave; the wave is not changed"),
    "ec_el_comercio": ("EVIDENCE_ONLY", "the channel is in the registry; first-party corroboration, no new channel"),
    "ni_articulo66": ("WAVE_C", "independent Nicaraguan outlet; a yearly archive with numbered pages (a structure no wave has) beside a feed named by earlier research"),
    "ni_nicaragua_investiga": ("WAVE_C", "second independent Nicaraguan outlet; a feed named by earlier research; the supplement shows current sections"),
    "cu_14ymedio": ("WAVE_C", "independent Cuban outlet; a feed named by earlier research and a section listing"),
    "cu_cubanet": ("WAVE_C", "independent Cuban outlet; a feed named by earlier research and a news archive"),
    "cu_diario_de_cuba": ("LATER_WAVE", "a third independent Cuban outlet known by a section page only: a listing without a feed; after the first listing outlets have run"),
    "uy_montevideo_portal": ("WAVE_C", "publisher-documented RSS catalogue, named by two independent research files; a feed address that is a query string"),
    "bo_opinion": ("WAVE_C", "publisher-documented RSS catalogue and a third-party crawler reading it; regional daily (Cochabamba)"),
    "ar_el_tribuno": ("WAVE_C", "publisher-documented RSS catalogue; regional daily (Salta); not in any earlier file"),
    "pr_noticel": ("WAVE_C", "an independent Puerto Rican outlet known by a chronological category page only: a listing read without an allow rule, its candidates waiting"),
    "hn_criterio": ("WAVE_C", "Honduran outlet while the origin of Proceso Digital is held; a feed a third-party crawler reads and a category listing"),
    "mx_expansion": ("NEEDS_CURRENT_EVIDENCE", "the hub page is known, no feed address is: nothing to register yet; a business title, not a general daily"),
    "sv_el_faro": ("DIFFERENT_CADENCE", "monthly editions on a beta host: not comparable to a daily feed; needs its own schedule and an origin decision"),
    "pr_el_nuevo_dia": ("LATER_WAVE", "a publisher-documented Arc feed for an outlet the registry holds only sitemap indexes for; the outlet is paywalled since 2017 by research"),
    "uy_el_observador": ("LATER_WAVE", "a publisher-documented latest-news feed for an outlet the registry holds only sitemaps for"),
    "py_abc_color": ("EVIDENCE_ONLY", "a 2019 page describing feeds the registry already holds with a query suffix: a variant, not a new channel"),
    "co_el_tiempo": ("HOLD_LEGAL_REVIEW", "the publisher's RSS page states personal, non-commercial use and restricts AI use: a licence and TDM decision of the operator comes before any registration"),
    "mx_el_siglo_de_torreon": ("NEEDS_CURRENT_EVIDENCE", "documentation of 2008; a feed directory names another address; neither is current evidence"),
}
DISPOSITION_MEANING = {
    "WAVE_C": "proposed for the third canary wave (a registration proposal exists; nothing is registered)",
    "LATER_WAVE": "worth a registration proposal after the waves in hand",
    "EVIDENCE_FOR_REVIEWED_WAVE": "attached as evidence to an outlet of the reviewed first wave; the wave is unchanged",
    "EVIDENCE_ONLY": "recorded as additional evidence; no action",
    "NEEDS_CURRENT_EVIDENCE": "not usable as it stands: no current address",
    "DIFFERENT_CADENCE": "a publication rhythm the canary procedure does not fit",
    "HOLD_LEGAL_REVIEW": "an operator decision on rights comes first; not to be requested",
}


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def host_of(url: str | None) -> str | None:
    """The host of an address, lower-cased, without a leading ``www.``; ``None`` when there is none."""
    if not url:
        return None
    found = re.search(r"https?://[^\s)]+", url)
    try:
        host = (urlsplit(found.group(0) if found else url).hostname or "").lower()
    except ValueError:
        return None
    return host[4:] if host.startswith("www.") else host or None


def address_key(url: str, with_query: bool = True) -> tuple[str, str, tuple]:
    """An address without its scheme, a leading ``www.`` and a trailing slash; the query sorted."""
    parts = urlsplit(url)
    return (host_of(url) or "", parts.path.rstrip("/"), tuple(sorted(parse_qsl(parts.query, keep_blank_values=True))) if with_query else ())


def title_key(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"\(.*?\)", "", folded)).strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--supplement", type=Path, required=True)
    parser.add_argument("--proposal", type=Path, action="append", default=[])
    parser.add_argument("--review", type=Path, action="append", default=[])
    parser.add_argument("--version", required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, required=True)
    arguments = parser.parse_args(argv)
    for out in (arguments.out_json, arguments.out_md):
        if out.exists():
            raise SystemExit(f"{out.name} exists: an overview version is written once")

    inventory, supplement = load(arguments.inventory), load(arguments.supplement)
    proposals, reviews = [load(path) for path in arguments.proposal], [load(path) for path in arguments.review]
    outlets = {outlet["outlet_id"]: outlet for outlet in inventory["outlets"]}

    # --- what is known, by address and by host -----------------------------------------------------
    registry_exact, registry_loose, research_exact, research_loose = {}, {}, {}, {}
    registry_hosts: dict[str, set[str]] = {}
    for outlet in outlets.values():
        for origin in outlet["web_origins"]:
            registry_hosts.setdefault(host_of(origin), set()).add(outlet["outlet_id"])
        for channel in outlet["channels"]:
            registry_exact[address_key(channel["url"])] = channel["channel_id"]
            registry_loose[address_key(channel["url"], False)] = channel["channel_id"]
        for candidate in outlet["research"]["candidate_channels"]:
            if candidate["url"] and "<" not in candidate["url"] and candidate["url"].startswith("http"):
                research_exact[address_key(candidate["url"])] = (outlet["outlet_id"], candidate["provenance"], candidate["evidence_level"])
                research_loose[address_key(candidate["url"], False)] = (outlet["outlet_id"], candidate["provenance"], candidate["evidence_level"])
    proposed_by_host: dict[str, dict[str, Any]] = {}
    for proposal in inventory["proposed_new_outlets"]:
        hosts = {host_of(proposal.get("origin"))} | {host_of(c.get("url")) for c in proposal.get("candidate_channels", [])}
        for host in hosts - {None}:
            proposed_by_host.setdefault(host, proposal)
    proposed_by_title = {(p["country_id"], title_key(p["name"])): p for p in inventory["proposed_new_outlets"]}

    # --- the supplement, entry by entry --------------------------------------------------------------
    entries = []
    for entry in supplement["candidates"]:
        identifier, url = entry["outlet_id_candidate"], entry["discovery_url"]
        noted = NOTED_ADDRESSES.get(identifier, [])
        in_registry = identifier in outlets
        earlier = proposed_by_host.get(host_of(url)) or proposed_by_title.get((entry["country_id"], title_key(entry["outlet_name"])))
        matches = []
        for address in [url, *noted]:
            key, loose = address_key(address), address_key(address, False)
            if key in registry_exact:
                matches.append({"address": address, "match": "registry_channel", "ref": registry_exact[key]})
            elif key in research_exact:
                matches.append({"address": address, "match": "earlier_research", "ref": list(research_exact[key])})
            elif loose in registry_loose:
                matches.append({"address": address, "match": "registry_channel_variant", "ref": registry_loose[loose]})
            elif loose in research_loose:
                matches.append({"address": address, "match": "earlier_research_variant", "ref": list(research_loose[loose])})
            elif earlier and any(c.get("url") and address_key(c["url"], False) == loose for c in earlier.get("candidate_channels", [])):
                matches.append({"address": address, "match": "earlier_proposal", "ref": earlier["name"]})
        if in_registry:
            if any(m["address"] == url and m["match"] == "registry_channel" for m in matches):
                classification = "KNOWN_IDENTICAL"
            elif matches:
                classification = "KNOWN_ADDITIONAL_EVIDENCE"
            else:
                classification = "NEW_CHANNEL_FOR_EXISTING_OUTLET"
        else:
            classification = "OUTLET_ALREADY_PROPOSED" if earlier else "NEW_OUTLET_CANDIDATE"
        registry_owner = sorted(registry_hosts.get(host_of(url), set()))
        disposition, reason = DISPOSITIONS[identifier]
        conflicts = []
        if identifier == "mx_el_siglo_de_torreon":
            conflicts.append("the supplement's feed address (documentation of 2008) and the address a feed directory lists differ; neither is confirmed current")
        if in_registry and registry_owner and registry_owner != [identifier]:
            conflicts.append(f"the address is on a host that is an origin of {registry_owner}")
        if not in_registry and registry_owner:
            conflicts.append(f"host is an origin of registry outlet(s) {registry_owner}")
        entries.append({
            "outlet_id_candidate": identifier, "country_id": entry["country_id"], "outlet_name": entry["outlet_name"],
            "discovery_kind": entry["discovery_kind"], "discovery_url": url, "addresses_in_notes": noted,
            "evidence_grade": entry["evidence_grade"], "evidence_url": entry["evidence_url"], "supplement_priority": entry["priority"],
            "supplement_relation": entry["registry_relation"], "in_registry": in_registry,
            "earlier_proposal": None if earlier is None or in_registry else {"name": earlier["name"], "provenance": earlier["provenance"], "origin": earlier.get("origin")},
            "matches": matches, "classification": classification, "conflicting_evidence": conflicts,
            "requires_specific_legal_review": entry["requires_specific_legal_review"],
            "disposition": disposition, "disposition_reason": reason, "status": "RESEARCH_ONLY / NOT_REGISTERED / NOT_LIVE_VALIDATED"})

    # --- waves -------------------------------------------------------------------------------------
    membership: dict[str, list[str]] = {}
    for proposal in proposals:
        for item in proposal.get("proposed", []):
            membership.setdefault(item["outlet_id"], []).append(f"{proposal['wave']}: proposed" if "wave" in proposal else "extended canary: proposed")
        for item in proposal.get("new_outlets", []):
            membership.setdefault(item["outlet_id"], []).append(f"{proposal['wave']}: proposed")
    recommendation = {e["outlet_id"]: e["recommendation"] for review in reviews for e in review["entries"]}
    by_candidate = {e["outlet_id_candidate"]: e for e in entries}

    # --- one record per registry outlet ----------------------------------------------------------------
    sources = []
    for outlet in outlets.values():
        flags = set(outlet["flags"])
        stages = [stage for stage, on in (("RESEARCHED", True), ("CANDIDATE", "DISCOVERED" in flags), ("TECHNICALLY_QUALIFIED", "QUALIFIED" in flags),
                                          ("REGISTERED", "REGISTERED" in flags), ("ACQUISITION_VERIFIED", "ACQUISITION_VERIFIED" in flags),
                                          ("OPERATIONALLY_STABLE", "OPERATIONALLY_STABLE" in flags)) if on]
        extra = by_candidate.get(outlet["outlet_id"])
        sources.append({
            "outlet_id": outlet["outlet_id"], "country_id": outlet["country_id"], "display_name": outlet["display_name"],
            "in_registry": True, "registration_status": outlet["registration_status"], "stages": stages,
            "legacy_class": outlet["legacy"]["outlet_class"], "legacy_ok_rows": outlet["legacy"]["ok_rows"],
            "route_class": outlet["route_class"], "operating_status": outlet["research"]["operating_status"]["value"],
            "legacy_channels": len(outlet["channels"]), "researched_channels": len(outlet["research"]["candidate_channels"]),
            "access_control_hold": bool(outlet["v3_evidence"]["access_control_hold"]),
            "waves": (["first canary (2026-10-08)"] if outlet["v3_evidence"]["canary_2026_10_08"] else []) + membership.get(outlet["outlet_id"], []),
            "review_recommendation": recommendation.get(outlet["outlet_id"]),
            "supplement": None if extra is None else {"classification": extra["classification"], "disposition": extra["disposition"]},
            "priority_score": outlet["priority"]["score"]})

    # --- outlet candidates outside the registry: the 60 proposals and the supplement, one record per outlet ---
    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    for proposal in inventory["proposed_new_outlets"]:
        addresses = [{"url": c["url"], "type": c["type"], "evidence": c["evidence_level"], "from": proposal["provenance"]}
                     for c in proposal.get("candidate_channels", []) if c.get("url") and "<" not in c["url"] and c["url"].startswith("http")]
        candidates[(proposal["country_id"], title_key(proposal["name"]))] = {
            "name": proposal["name"], "country_id": proposal["country_id"], "origin": proposal.get("origin"), "addresses": addresses,
            "named_in": [proposal["provenance"]], "proposed_outlet_id": None}
    for entry in entries:
        if entry["in_registry"]:
            continue
        key = (entry["country_id"], title_key(entry["earlier_proposal"]["name"])) if entry["earlier_proposal"] else (entry["country_id"], title_key(entry["outlet_name"]))
        record = candidates.setdefault(key, {"name": entry["outlet_name"], "country_id": entry["country_id"], "origin": None, "addresses": [],
                                             "named_in": [], "proposed_outlet_id": None})
        record["proposed_outlet_id"] = entry["outlet_id_candidate"]
        record["named_in"].append(arguments.supplement.name)
        known = {address_key(a["url"]) for a in record["addresses"]}
        for address in [entry["discovery_url"], *entry["addresses_in_notes"]]:
            if address_key(address) not in known:
                record["addresses"].append({"url": address, "type": entry["discovery_kind"], "evidence": entry["evidence_grade"], "from": arguments.supplement.name})
        record["supplement"] = {"classification": entry["classification"], "disposition": entry["disposition"], "priority": entry["supplement_priority"]}
    candidate_records = []
    for key in sorted(candidates):
        record = candidates[key]
        concrete = [a for a in record["addresses"] if a["evidence"] != "unknown"]
        record["stages"] = ["RESEARCHED"] + (["CANDIDATE"] if concrete else [])
        record["in_registry"] = False
        record["waves"] = membership.get(record["proposed_outlet_id"] or "", [])
        record["host_is_a_registry_origin_of"] = sorted({o for a in record["addresses"] for o in registry_hosts.get(host_of(a["url"]), set())})
        candidate_records.append(record)

    # --- identity cases: facts from the files, and what stays open --------------------------------------
    def facts(outlet_id: str) -> dict[str, Any]:
        outlet = outlets[outlet_id]
        return {"web_origins": outlet["web_origins"], "channel_hosts": sorted({host_of(c["url"]) for c in outlet["channels"]}),
                "research_origins": outlet["research"]["current_origins"], "operating_status": outlet["research"]["operating_status"]["value"],
                "legacy_class": outlet["legacy"]["outlet_class"], "legacy_ok_rows": outlet["legacy"]["ok_rows"]}

    titles = Counter()
    by_title: dict[str, list[str]] = {}
    for outlet in outlets.values():
        by_title.setdefault(title_key(outlet["display_name"]), []).append(outlet["outlet_id"])
    for record in candidate_records:
        by_title.setdefault(title_key(record["name"]), []).append(f"candidate:{record['country_id']}:{record['name']}")
    same_title = {title: sorted(ids) for title, ids in sorted(by_title.items()) if len(ids) > 1}
    shared_hosts = {host: sorted(ids) for host, ids in sorted(registry_hosts.items()) if host and len(ids) > 1}
    foreign = {o["outlet_id"]: sorted({host_of(c["url"]) for c in o["channels"]} - {host_of(origin) for origin in o["web_origins"]})
               for o in outlets.values() if {host_of(c["url"]) for c in o["channels"]} - {host_of(origin) for origin in o["web_origins"]}}
    identity_cases = [
        {"case": "pr_primera_hora", "facts": facts("pr_primera_hora"),
         "finding": "every channel of the outlet is on another outlet's host (elnuevodia.com, the same three addresses as pr_el_nuevo_dia): the outlet has no channel of its own",
         "recommendation": "at registration review: give pr_primera_hora no channel from elnuevodia.com; a channel on primerahora.com is known only by pattern inference; keep both outlets apart (one publisher group, two titles)",
         "decision": "OPEN (O-11 review); nothing changed"},
        {"case": "cl_el_mercurio", "facts": facts("cl_el_mercurio"),
         "finding": "the registry outlet named El Mercurio has the origin emol.com, the group's free portal; the newspaper's own content is behind a subscription by research",
         "recommendation": "decide whether the outlet is Emol (then name it so, by a new display name with dates, never a new id) or El Mercurio (then emol.com is not its origin)",
         "decision": "OPEN (operator, corpus supply); the outlet is NEEDS_VERIFICATION in the review"},
        {"case": "ni_confidencial", "facts": facts("ni_confidencial"),
         "finding": "third parties read the feed on the apex host; the newsroom works from Costa Rica; the country of the outlet is the country it reports on",
         "recommendation": "register the apex host as a second origin; keep country_id ni; record the seat as an attribute when the registry has one for it, not as the country",
         "decision": "OPEN (O-11 review; listed in the proposal)"},
        {"case": "bo_la_razon", "facts": facts("bo_la_razon"),
         "finding": "research finds current content under larazon.bo and a third party reports the registry origin blocked",
         "recommendation": "an origin change is a dated addition of an origin after review, never a rewrite; the legacy alias stays",
         "decision": "OPEN (O-11 review)"},
        {"case": "ni_la_prensa", "facts": facts("ni_la_prensa"),
         "finding": "research finds the outlet at laprensani.com since 2023 and warns of an impersonation site: the origin must be pinned exactly",
         "recommendation": "as bo_la_razon; verify the origin against the outlet's own statement before registering",
         "decision": "OPEN (O-11 review)"},
        {"case": "closed outlets", "facts": {outlet_id: facts(outlet_id) for outlet_id in ("bo_pagina_siete", "gt_elperiodico")},
         "finding": "research finds both closed in 2023; the legacy corpus holds 10 accepted articles of bo_pagina_siete and none of gt_elperiodico",
         "recommendation": "keep both in the registry as proposed and never register them for acquisition; historical articles keep their outlet",
         "decision": "OPEN (registry attribute for a closed outlet does not exist)"},
        {"case": "same title, different outlets", "facts": same_title,
         "finding": "titles that occur more than once across countries among registry outlets and outlet candidates",
         "recommendation": "the country prefix of the id keeps them apart; never merge by title",
         "decision": "no action"},
        {"case": "hosts shared by registry outlets", "facts": {"origins": shared_hosts, "channels_on_a_host_that_is_not_an_origin": foreign},
         "finding": "origin hosts that belong to more than one registry outlet, and outlets with channels on a host that is not one of their origins (a feed on a foreign host is a channel origin, never an outlet origin)",
         "recommendation": "none beyond the cases above", "decision": "no action"},
    ]

    # --- coverage per country --------------------------------------------------------------------------
    countries = sorted({s["country_id"] for s in sources} | {c["country_id"] for c in candidate_records})
    coverage = {}
    for country in countries:
        own = [s for s in sources if s["country_id"] == country]
        outside = [c for c in candidate_records if c["country_id"] == country]
        coverage[country] = {
            "registry_outlets": len(own),
            "legacy_outlets_with_accepted_articles": sum(1 for s in own if s["legacy_ok_rows"] > 0),
            "legacy_outlets_repeated": sum(1 for s in own if s["legacy_class"] == "LEGACY_PRODUCTIVE_REPEATED"),
            "registered": sum(1 for s in own if "REGISTERED" in s["stages"]),
            "technically_qualified": sum(1 for s in own if "TECHNICALLY_QUALIFIED" in s["stages"]),
            "acquisition_verified": sum(1 for s in own if "ACQUISITION_VERIFIED" in s["stages"]),
            "operationally_stable": 0,
            "in_a_proposed_wave": sorted(s["outlet_id"] for s in own if any("proposed" in w for w in s["waves"]))
            + sorted(c["proposed_outlet_id"] for c in outside if c["waves"]),
            "outlet_candidates_outside_the_registry": len(outside),
            "closed_or_held": sorted(s["outlet_id"] for s in own if s["route_class"] in ("CLOSED", "ACCESS_CONTROL_HOLD")),
        }

    overview = {
        "schema": SCHEMA, "overview_version": arguments.version,
        "what_this_is": "a reading aid over the evidence files; not a registry. Research entries are hypotheses; only TECHNICALLY_QUALIFIED and later rest on this project's own observation",
        "inputs": {"inventory": {"file": arguments.inventory.name, "sha256": sha256_of(arguments.inventory)},
                   "supplement": {"file": arguments.supplement.name, "sha256": sha256_of(arguments.supplement), "status": supplement["kind"]},
                   "proposals": [{"file": path.name, "sha256": sha256_of(path)} for path in arguments.proposal],
                   "reviews": [{"file": path.name, "sha256": sha256_of(path)} for path in arguments.review]},
        "stage_rules": STAGE_RULES, "classification_rules": CLASSES, "disposition_meaning": DISPOSITION_MEANING,
        "normalisation": "addresses are compared without scheme, a leading `www.` and a trailing slash, with the query sorted; a match that ignores the query is a `variant`; outlets are matched by registry id, then by host, then by country and title",
        "totals": {
            "registry_outlets": len(sources), "outlet_candidates_outside_the_registry": len(candidate_records),
            "supplement_entries": len(entries),
            "supplement_by_classification": dict(sorted(Counter(e["classification"] for e in entries).items())),
            "supplement_by_disposition": dict(sorted(Counter(e["disposition"] for e in entries).items())),
            "registry_outlets_by_stage": {stage: sum(1 for s in sources if stage in s["stages"]) for stage in STAGES},
            "outlet_candidates_by_stage": {stage: sum(1 for c in candidate_records if stage in c["stages"]) for stage in STAGES[:2]},
            "countries": len(countries),
            "countries_with_acquisition_verified": sorted(c for c, row in coverage.items() if row["acquisition_verified"]),
        },
        "supplement": entries, "sources": sources, "outlet_candidates": candidate_records, "identity_cases": identity_cases,
        "coverage_by_country": coverage,
    }
    arguments.out_json.write_bytes((json.dumps(overview, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    arguments.out_md.write_bytes(render(overview).encode("utf-8"))
    print(json.dumps(overview["totals"], indent=1, sort_keys=True))
    return 0


def render(overview: dict[str, Any]) -> str:
    totals = overview["totals"]
    lines = [
        f"# Source coverage report — overview version {overview['overview_version']}", "",
        "**Generated** by `scripts/consolidate_source_discovery.py` from the JSON beside it; do not edit. A reading aid over the",
        "evidence files, not a registry. Research is a hypothesis; only `TECHNICALLY_QUALIFIED` and later rest on this project's own",
        "observation of a server. Coverage of a country is not representativeness: owner, type, region and time are not in this table.", "",
        f"Registry outlets: {totals['registry_outlets']}. Outlet candidates outside the registry: {totals['outlet_candidates_outside_the_registry']}. "
        f"Countries: {totals['countries']}.", "",
        "| Stage | Registry outlets | Rule |", "|---|---|---|"]
    lines += [f"| `{stage}` | {totals['registry_outlets_by_stage'][stage]} | {overview['stage_rules'][stage]} |" for stage in STAGES]
    lines += ["", "## Coverage by country", "",
              "| Country | Registry | Legacy: any accepted | Legacy: repeated | Registered | Qualified | Acquisition verified | In a proposed wave | Candidates outside | Closed or held |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for country, row in overview["coverage_by_country"].items():
        lines.append(f"| {country} | {row['registry_outlets']} | {row['legacy_outlets_with_accepted_articles']} | {row['legacy_outlets_repeated']} | {row['registered']} | "
                     f"{row['technically_qualified']} | {row['acquisition_verified']} | {len(row['in_a_proposed_wave'])} | {row['outlet_candidates_outside_the_registry']} | "
                     f"{', '.join(f'`{o}`' for o in row['closed_or_held']) or '—'} |")
    lines += ["", f"## The research supplement ({totals['supplement_entries']} entries; RESEARCH_ONLY)", "",
              "| Entry | Country | Classification | Matches in earlier files | Disposition | Reason |", "|---|---|---|---|---|---|"]
    for entry in overview["supplement"]:
        matched = "; ".join(f"{m['match']}" for m in entry["matches"]) or ("earlier proposal: " + entry["earlier_proposal"]["name"] if entry["earlier_proposal"] else "none")
        lines.append(f"| `{entry['outlet_id_candidate']}` | {entry['country_id']} | {entry['classification']} | {matched} | {entry['disposition']} | {entry['disposition_reason']} |")
    lines += ["", "Classifications: " + "; ".join(f"`{k}` — {v}" for k, v in overview["classification_rules"].items()) + ".", "",
              "## Identity cases", "", "| Case | Finding | Recommendation | Decision |", "|---|---|---|---|"]
    lines += [f"| {case['case']} | {case['finding']} | {case['recommendation']} | {case['decision']} |" for case in overview["identity_cases"]]
    lines += ["", "## Outlet candidates outside the registry", "", "| Country | Name | Proposed id | Stages | Named in | Wave |", "|---|---|---|---|---|---|"]
    for record in overview["outlet_candidates"]:
        lines.append(f"| {record['country_id']} | {record['name']} | {('`' + record['proposed_outlet_id'] + '`') if record['proposed_outlet_id'] else '—'} | "
                     f"{', '.join(record['stages'])} | {len(record['named_in'])} file(s) | {'; '.join(record['waves']) or '—'} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
