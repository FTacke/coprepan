"""Registry review package (master plan O-11).

Turns the registry proposal into something a person can review in one sitting: per outlet what is
known, what is not, what looks wrong, and one recommended action — plus the handful of cases that
need a judgement no program can make.

It **recommends and never registers**. It invents no attribute: a field the legacy database did
not hold is listed as unknown. It consults nothing outside the repository.

**Id convention proposed here** (replacing the inherited legacy spelling, which mixes
``el_pais`` and ``elpais``): ``{country_id}_{ASCII slug of the display name}`` — words separated
by ``_``, accents folded, punctuation dropped. One rule for all outlets, derived from the name a
reader knows. The legacy code stays what it is: provenance, kept as an alias. A recommended id
becomes an id only when a reviewer registers it.

**Channel id convention proposed here:** ``{outlet_id}:ch:{kind}_{slug of the URL path}``, with
the host in the slug when the channel does not live on the outlet's own origin.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from . import naming, registry
from .canonical import record_json, sha256_bytes, sha256_file
from .identity import IdentityError, normalise_origin
from .storage_roots import CHECKOUT

REVIEW_SCHEMA = naming.schema_id("registry-review", 1)
UNKNOWN_FIELDS = ("outlet_type", "outlet_group", "city", "region", "scope", "access_model", "medium", "timezone", "same_outlet_basis")

ACTION_SAME_OUTLET = "DECIDE_ONE_OUTLET_OR_TWO"
ACTION_CHANNELS_ELSEWHERE = "CHECK_CHANNEL_ATTRIBUTION"
ACTION_NO_CHANNELS = "FIND_CHANNELS_OR_LEAVE_UNREGISTERED"
ACTION_ROUTINE = "CONFIRM_ID_AND_COMPLETE_ATTRIBUTES"
_SLUG_LIMIT = 40


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _site(host: str) -> str:
    """A host without the prefixes that name the same site (``www.``, ``m.``)."""
    return re.sub(r"^(?:www|m|amp)\.", "", host)


def recommended_outlet_id(country_id: str, display_name: str) -> str | None:
    slug = registry.propose_slug(display_name)
    value = f"{country_id}_{slug}"
    return value if slug and naming.is_outlet_id(value) else None


def recommended_channel_slug(kind: str, url: str, own_sites: set[str]) -> str:
    parts = urlsplit(url)
    path = re.sub(r"\.(?:xml|rss|atom|php|aspx?|html?)$", "", parts.path, flags=re.IGNORECASE)
    slug = registry.propose_slug(f"{path} {parts.query}")
    slug = re.sub(rf"^(?:{kind}|rss|feed|feeds|sitemap|sitemaps)_", "", slug)
    if slug in ("", kind, "rss", "feed", "feeds", "sitemap", "sitemaps", "index"):
        slug = "root" if slug in ("", "index") else "main"
    host = _host(url)
    if _site(host) not in own_sites:
        slug = f"{registry.propose_slug(_site(host))}_{slug}"
    if len(slug) > _SLUG_LIMIT:
        slug = f"{slug[:_SLUG_LIMIT - 9].rstrip('_')}_{sha256_bytes(url.encode('utf-8'))[:8]}"
    return f"{kind}_{slug}"


def build_review(document: Mapping[str, Any]) -> dict[str, Any]:
    """The review package for a registry document. Pure and deterministic."""
    outlets = list(registry.validate_registry(document).outlets.values())
    site_owner: dict[str, list[str]] = defaultdict(list)
    for outlet in outlets:
        for origin in outlet["web_origins"]:
            site_owner[_site(_host(origin))].append(outlet["outlet_id"])
    recommended = {o["outlet_id"]: recommended_outlet_id(o["country_id"], o["display_names"][0]["name"]) for o in outlets}
    id_count = Counter(value for value in recommended.values() if value)
    names_in_country = Counter((o["country_id"], o["display_names"][0]["name"].casefold()) for o in outlets)
    names_anywhere = Counter(o["display_names"][0]["name"].casefold() for o in outlets)

    entries, cases = [], []
    for outlet in outlets:
        outlet_id, name = outlet["outlet_id"], outlet["display_names"][0]["name"]
        sources = outlet["legacy_observed"].get("sources", [])
        own_sites = {_site(_host(origin)) for origin in outlet["web_origins"]}
        warnings: list[str] = []

        new_id = recommended[outlet_id]
        if new_id is None:
            warnings.append("no_id_can_be_derived_from_the_display_name")
        elif new_id != outlet_id:
            warnings.append("id_spelling_differs_from_the_convention")
        if any(not alias["slug"].isascii() for alias in outlet["legacy_aliases"]):
            warnings.append("legacy_code_is_not_ascii")
        if new_id and id_count[new_id] > 1:
            warnings.append("recommended_id_collides_within_the_registry")
        if names_in_country[(outlet["country_id"], name.casefold())] > 1:
            warnings.append("display_name_shared_within_the_country")
        if names_anywhere[name.casefold()] > 1:
            warnings.append("display_name_shared_across_countries")  # information: ids stay distinct by country
        if any(origin.startswith("http://") for origin in outlet["web_origins"]):
            warnings.append("origin_is_plain_http")
        if not outlet["web_origins"]:
            warnings.append("no_web_origin")
        if len(sources) > 1:
            warnings.append("several_legacy_sources_fold_to_this_entry")
        if any(not source.get("is_active", 1) for source in sources):
            warnings.append("legacy_source_was_inactive")

        channels, used, additional_origins, foreign_hosts, other_outlets = [], Counter(), set(), set(), set()
        for channel in outlet["channels"]:
            url = channel["url_history"][-1]["url"]
            host, legacy = _host(url), channel["legacy_observed"]
            notes = []
            if _site(host) in own_sites:
                try:
                    origin = normalise_origin(f"{urlsplit(url).scheme}://{urlsplit(url).netloc}")
                    if origin not in outlet["web_origins"]:
                        additional_origins.add(origin)
                        notes.append("host_is_a_variant_of_the_outlet_origin")
                except (IdentityError, ValueError):
                    notes.append("unusable_channel_url")
            else:
                owners = [other for other in site_owner.get(_site(host), []) if other != outlet_id]
                if owners:
                    other_outlets.update(owners)
                    notes.append("host_is_the_origin_of_another_outlet")
                else:
                    foreign_hosts.add(host)
                    notes.append("host_is_not_an_origin_of_the_outlet")
            if channel["kind"] == "unknown":
                notes.append("legacy_type_unknown")
            slug = recommended_channel_slug(channel["kind"], url, own_sites)
            used[slug] += 1
            if used[slug] > 1:
                slug = f"{slug}_{used[slug]}"
            channels.append({
                "channel_id": channel["channel_id"],
                "recommended_channel_id": f"{new_id or outlet_id}:ch:{slug}",
                "kind": channel["kind"], "url": url,
                "legacy_feed_id": legacy.get("id"), "legacy_status": legacy.get("status"),
                "legacy_is_active": legacy.get("is_active"), "legacy_discovered_by": legacy.get("discovered_by"),
                "legacy_last_fail_reason": legacy.get("last_fail_reason"),
                "notes": notes,
            })
        if not channels:
            warnings.append("no_channel")
        elif not any(c["legacy_status"] == "active" for c in channels):
            warnings.append("no_channel_was_active_in_legacy")
        if foreign_hosts:
            warnings.append("channels_on_hosts_that_are_not_the_outlet")
        if other_outlets:
            warnings.append("channels_on_the_origin_of_another_outlet")
        if any(c["kind"] == "unknown" for c in channels):
            warnings.append("channels_of_unknown_type")

        if "recommended_id_collides_within_the_registry" in warnings or "display_name_shared_within_the_country" in warnings \
                or "several_legacy_sources_fold_to_this_entry" in warnings:
            action = ACTION_SAME_OUTLET
        elif other_outlets or foreign_hosts:
            action = ACTION_CHANNELS_ELSEWHERE
        elif not channels:
            action = ACTION_NO_CHANNELS
        else:
            action = ACTION_ROUTINE
        if other_outlets:
            cases.append({"case": "channels_on_the_origin_of_another_outlet", "outlets": sorted({outlet_id, *other_outlets}),
                          "question": "Are these one publisher's outlets sharing infrastructure, or were the channels attributed to the wrong outlet?"})

        entries.append({
            "outlet_id": outlet_id,
            "recommended_outlet_id": new_id,
            "display_name": name,
            "country_id": outlet["country_id"],
            "legacy": [{"source_id": s.get("id"), "country_code": s.get("country_code"), "newspaper_code": s.get("newspaper_code"),
                        "is_active": s.get("is_active"), "legal_basis": s.get("legal_basis") or None,
                        "base_url": s.get("base_url")} for s in sources],
            "web_origins": list(outlet["web_origins"]),
            "additional_origin_candidates": sorted(additional_origins),
            "hosts_not_of_the_outlet": sorted(foreign_hosts),
            "publisher": "unknown",
            "publisher_evidence": ([f"shares a host with {', '.join(sorted(other_outlets))}"] if other_outlets else []),
            "channel_count": len(channels),
            "channel_kinds": dict(sorted(Counter(c["kind"] for c in channels).items())),
            "channel_legacy_statuses": dict(sorted(Counter(str(c["legacy_status"]) for c in channels).items())),
            "channels": channels,
            "unknown_fields": [f for f in UNKNOWN_FIELDS if outlet[f] == registry.UNKNOWN],
            "url_rules_are_placeholder": outlet["url_rules"]["version"] == "proposed",
            "warnings": warnings,
            "recommended_action": action,
        })

    for value, count in sorted(id_count.items()):
        if count > 1:
            cases.append({"case": "recommended_id_collision", "outlets": sorted(k for k, v in recommended.items() if v == value),
                          "question": f"Two entries would both become {value}: one outlet or two?"})
    for (country, name), count in sorted(names_in_country.items()):
        if count > 1:
            cases.append({"case": "same_display_name_in_one_country",
                          "outlets": sorted(o["outlet_id"] for o in outlets if o["country_id"] == country and o["display_names"][0]["name"].casefold() == name),
                          "question": "Same name in the same country: one outlet or two?"})
    cases = sorted({json.dumps(case, sort_keys=True, ensure_ascii=False): case for case in cases}.values(),
                   key=lambda case: (case["case"], case["outlets"]))

    return {
        "schema": REVIEW_SCHEMA,
        "status": "RECOMMENDATION_ONLY — nothing in this package registers an outlet",
        "id_convention": "{country_id}_{ASCII slug of the display name, words separated by '_'}",
        "channel_id_convention": "{outlet_id}:ch:{kind}_{slug of the URL path; host first when the channel is not on the outlet's origin}",
        "summary": {
            "outlets": len(entries),
            "channels": sum(e["channel_count"] for e in entries),
            "ids_changed_by_the_convention": sum(1 for e in entries if e["recommended_outlet_id"] not in (None, e["outlet_id"])),
            "by_recommended_action": dict(sorted(Counter(e["recommended_action"] for e in entries).items())),
            "by_warning": dict(sorted(Counter(w for e in entries for w in e["warnings"]).items())),
            "review_cases": len(cases),
        },
        "review_cases": cases,
        "legacy_to_recommended_id": [
            {"country_code": alias["country_code"], "legacy_slug": alias["slug"], "imported_outlet_id": o["outlet_id"],
             "recommended_outlet_id": recommended[o["outlet_id"]], "mapping_status": alias["mapping_status"]}
            for o in outlets for alias in o["legacy_aliases"]
        ],
        "outlets": entries,
    }


def render_markdown(review: Mapping[str, Any], registry_sha256: str) -> str:
    """The package as a page to read. Generated: edit the generator, not the page."""
    summary = review["summary"]
    lines = [
        "# Registry review package",
        "",
        "**Status: GENERATED — a recommendation for human review. It registers nothing.** Produced by",
        "`python -m coprepan.registry_review` from `config/outlet_registry.json`",
        f"(SHA-256 `{registry_sha256}`); a test fails if this page and the registry drift apart.",
        "What the reviewer decides: [`INDEX.md`](INDEX.md) §16–§17. Full data per outlet and channel:",
        "[`config/registry_review/outlet_review_package.json`](../../config/registry_review/outlet_review_package.json).",
        "",
        "## Summary",
        "",
        "| Quantity | Value |",
        "|---|---|",
        f"| outlets / channels | {summary['outlets']} / {summary['channels']} |",
        f"| ids that change under the proposed convention | {summary['ids_changed_by_the_convention']} |",
        f"| cases that need a judgement | {summary['review_cases']} |",
    ]
    lines += [f"| action `{action}` | {count} |" for action, count in summary["by_recommended_action"].items()]
    lines += ["", "Id convention proposed: `" + review["id_convention"] + "`.", "", "## Warnings", "", "| Warning | Outlets |", "|---|---|"]
    lines += [f"| `{warning}` | {count} |" for warning, count in summary["by_warning"].items()]
    lines += ["", "## Cases that need a judgement", "", "| Case | Outlets | Question |", "|---|---|---|"]
    lines += [f"| `{case['case']}` | {', '.join('`' + o + '`' for o in case['outlets'])} | {case['question']} |" for case in review["review_cases"]]
    lines += ["", "## Legacy name → recommended id", "", "| Legacy | Imported id | Recommended id | Changed |", "|---|---|---|---|"]
    lines += [f"| `{row['country_code']}/{row['legacy_slug']}` | `{row['imported_outlet_id']}` | `{row['recommended_outlet_id']}` | "
              f"{'yes' if row['recommended_outlet_id'] != row['imported_outlet_id'] else ''} |" for row in review["legacy_to_recommended_id"]]
    lines += ["", "## Outlets", "",
              "| Recommended id | Name | Origins | Channels | Action | Warnings |", "|---|---|---|---|---|---|"]
    for entry in review["outlets"]:
        kinds = ", ".join(f"{count} {kind}" for kind, count in entry["channel_kinds"].items()) or "none"
        origins = "<br>".join(entry["web_origins"] + [f"+ {o}" for o in entry["additional_origin_candidates"]]
                              + [f"? {h}" for h in entry["hosts_not_of_the_outlet"]])
        warnings = "<br>".join(f"`{w}`" for w in entry["warnings"] if w != "display_name_shared_across_countries")
        lines.append(f"| `{entry['recommended_outlet_id']}` | {entry['display_name']} | {origins} | {kinds} | `{entry['recommended_action']}` | {warnings} |")
    lines += ["", "`+` an origin seen on the outlet's own channels that is not yet a registered origin; `?` a host of a",
              "channel that is not the outlet's. Unknown for every outlet: " + ", ".join(f"`{f}`" for f in UNKNOWN_FIELDS)
              + "; URL rules are placeholders.", ""]
    return "\n".join(lines)


def write_package(registry_path: Path, json_out: Path, markdown_out: Path) -> dict[str, Any]:
    review = build_review(json.loads(Path(registry_path).read_text(encoding="utf-8")))
    review["registry_sha256"] = sha256_file(Path(registry_path))[0]
    Path(json_out).write_bytes(record_json(review))
    Path(markdown_out).write_bytes(render_markdown(review, review["registry_sha256"]).encode("utf-8"))
    return review


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regenerate the registry review package from the tracked registry.")
    parser.add_argument("--registry", type=Path, default=CHECKOUT / "config" / "outlet_registry.json")
    parser.add_argument("--json-out", type=Path, default=CHECKOUT / "config" / "registry_review" / "outlet_review_package.json")
    parser.add_argument("--markdown-out", type=Path, default=CHECKOUT / "docs" / "corpus_supply" / "REGISTRY_REVIEW_PACKAGE.md")
    arguments = parser.parse_args(argv)
    review = write_package(arguments.registry, arguments.json_out, arguments.markdown_out)
    print(json.dumps(review["summary"], indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
