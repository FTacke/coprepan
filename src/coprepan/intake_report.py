"""What an intake measured, read from the evidence it left (decision CPD-0029). Read-only.

Everything here is a derived view of primary evidence — the request log, the discovery tables, the
admission labels — restricted to the runs of one intake, and can be rebuilt from it. Three things:

- :func:`measure` — per channel, outlet and country: what was polled, what was listed and how new it
  was, what was requested, how it answered, what the experimental extractor made of it;
- the **anomaly flags** of a fetched page (`flags_of`): mechanical hints from its URL and from the
  extraction's own measurements. A flag is a reason to look, never a judgement and never a label a
  person gave; nothing is filtered, removed or released on its account;
- :func:`review_package` — a stratified, deterministic sample of fetched pages for a later human
  review, every judgement field empty.

"New" is said carefully: a URL found for the first time is not thereby an article published during
the intake (see `intake.novelty`).
"""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from . import discovery, intake, naming
from .canonical import sha256_bytes

MEASUREMENT_SCHEMA = naming.schema_id("intake-measurement", 1)
REVIEW_SCHEMA = naming.schema_id("intake-review-package", 1)
FLAGGER = "intake-anomaly-flags/1"
ARTICLE_TEXT_MIN = 500          # characters of body text under the baseline extractor; below it the extraction is flagged, not the page
REVIEW_PER_OUTLET = 4
# Outlets a person singled out for a closer look after the qualification runs: their numbers are shown apart, nothing else follows from the list.
WATCHED = ("hn_criterio", "cu_14ymedio", "ni_confidencial", "mx_el_universal", "pa_diaadia", "pa_metro_libre", "ve_eluniversal", "pe_elperuano")
_URL_FLAGS = (
    ("section_or_listing_url", re.compile(r"/(?:seccion|secciones|section|category|categoria|categorias|tag|tags|etiqueta|etiquetas|tema|temas|topic|archivo|archive|page|pagina)(?:/|$)", re.I)),
    ("author_page_url", re.compile(r"/(?:autor|autores|author|authors|firma|firmas|columnista|columnistas|staff)/[^/]+/?$", re.I)),
    ("gallery_or_video_url", re.compile(r"/(?:video|videos|galeria|galerias|fotogaleria|fotogalerias|fotos|gallery|multimedia|podcast|podcasts|audio|en-vivo|live|envivo)(?:/|$)", re.I)),
    ("sponsored_url", re.compile(r"(?:patrocinad|sponsor|brand-?(?:lab|studio|voice|ed)|publirreportaje|publicidad|contenido-de-marca|branded|advertorial|partner-?content)", re.I)),
)


def _rows(path: Path) -> Iterator[dict[str, Any]]:
    """The rows of a table, one at a time (a table may be far larger than memory should hold)."""
    if not path.exists():
        return
    with open(path, "rb") as handle:
        for line in handle:
            try:
                yield json.loads(line)
            except ValueError:
                pass                 # a torn last line of a table that is being written


def flags_of(url: str, status: int | None, label: Mapping[str, Any] | None) -> list[str]:
    """Mechanical reasons to look at a fetched page. Derived from the URL and the extraction's measurements only."""
    flags = []
    if not isinstance(status, int) or not 200 <= status < 300:
        return ["not_a_2xx_answer"]
    path = re.sub(r"^https?://[^/]+", "", url or "")
    flags += [name for name, pattern in _URL_FLAGS if pattern.search(path)]
    if path.strip("/") == "" or (path.count("/") <= 1 and not re.search(r"\d|-.*-", path)):
        flags.append("front_or_top_level_page_url")
    if label is None:
        return flags + ["no_label"]
    reasons = {reason["reason"] for reason in label.get("reasons") or []}
    characters = (label.get("measurements") or {}).get("body_characters")
    if reasons & {"not_extractable"}:
        flags.append("extractor_error")
    if "no_body_text" in reasons or characters == 0:
        flags.append("empty_extraction")
    elif isinstance(characters, int) and characters < ARTICLE_TEXT_MIN:
        flags.append("very_short_text")                    # a teaser before a paywall looks like this too; the flag does not say which
    flags += [name for name in ("no_title", "publication_date_unknown", "duplicate_body_of_other_document", "no_document") if name in reasons]
    return flags


def measure(workspace: Path, plan: Mapping[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
    """The measurement of an intake from its evidence."""
    workspace = Path(workspace)
    runs = set(state["run_ids"])
    started = datetime.fromisoformat(state["started_at_utc"].replace("Z", "+00:00"))
    country = {outlet["outlet_id"]: outlet["country_id"] for outlet in plan["outlets"]}
    planned, finished = {}, []
    for row in _rows(workspace / "requests" / "requests.jsonl"):
        if row.get("run_id") in runs:
            if row["event"] == "PLANNED":
                planned[row["request_id"]] = row
            elif not row.get("attributed_from"):
                finished.append(row)
    labels = {row["fetch_id"]: row for row in _rows(workspace / "admission" / "labels.jsonl") if row.get("run_id") in runs}
    candidates = {row["candidate_id"]: row for row in _rows(workspace / "discovery" / "candidates.jsonl") if row["outlet_id"] in country}
    wanted_events = {row["first_event_id"] for row in candidates.values() if row.get("first_event_id")}
    first_events: dict[str, dict[str, Any]] = {}
    channels: dict[str, dict[str, Any]] = defaultdict(lambda: {"polls": 0, "documents_read": 0, "documents_unavailable": 0, "entries_listed": 0,
                                                              "candidates_first_listed": Counter(), "items_requested": 0, "items_2xx": 0})
    for row in _rows(workspace / "discovery" / "events.jsonl"):
        if row["event_id"] in wanted_events:
            first_events[row["event_id"]] = {"hints": row.get("hints") or {}}
        if row.get("run_id") in runs:
            channels[row["channel_id"]]["entries_listed"] += 1
    for row in _rows(workspace / "discovery" / "inputs.jsonl"):
        if row.get("run_id") in runs:
            channel = channels[row["channel_id"]]
            channel["polls"] += int(row.get("depth", 0) == 0)
            channel["documents_read" if row["outcome"] != "UNAVAILABLE" else "documents_unavailable"] += 1
    novelty: dict[str, str] = {}
    for identifier, row in candidates.items():
        kind = intake.novelty(row, first_events.get(row.get("first_event_id")), started, state["first_poll_done"])
        novelty[identifier] = kind
        if kind != intake.KNOWN_BEFORE:
            channels[row["first_channel_id"]]["candidates_first_listed"][kind] += 1

    outlets: dict[str, dict[str, Any]] = defaultdict(lambda: {"requests": Counter(), "refused": Counter(), "access_classes": Counter(), "items": [], "transport_calls": 0})
    for row in finished:
        plan_row = planned.get(row["request_id"], {})
        outlet = outlets[plan_row.get("outlet_id", "?")]
        result = row.get("result") or {}
        outlet["transport_calls"] += len(row.get("fetch_ids") or []) + len(result.get("redirect_statuses") or [])
        observed = (row.get("policy_layers") or {}).get("access_class_observed")
        if observed:
            outlet["access_classes"][observed] += 1
        if row["final"] != "FETCHED":
            outlet["refused"][f"{row['fetch_kind']}:{(row.get('policy_reasons') or [result.get('failure_reason') or row['final']])[0]}"] += 1
            continue
        outlet["requests"][f"{row['fetch_kind']}:{result.get('status')}"] += 1
        if row["fetch_kind"] != "item":
            continue
        fetch_id = (row.get("fetch_ids") or [None])[-1]
        label = labels.get(fetch_id)
        status = result.get("status")
        candidate = candidates.get(row.get("candidate_id") or "", {})
        event = first_events.get(candidate.get("first_event_id"))
        published = discovery.entry_instant(event["hints"]) if event else None
        item = {"fetch_id": fetch_id, "url": plan_row.get("url"), "final_url": result.get("final_url"), "status": status, "channel_id": plan_row.get("channel_id"),
                "candidate_id": row.get("candidate_id"), "novelty": novelty.get(row.get("candidate_id") or "", "unknown"),
                "published_hint_utc": published.isoformat() if published else None, "first_listed_at": candidate.get("first_listed_at"),
                "requested_at": plan_row.get("planned_at"), "technical_status": label["technical_status"] if label else None,
                "body_characters": (label.get("measurements") or {}).get("body_characters") if label else None,
                "flags": flags_of(result.get("final_url") or plan_row.get("url") or "", status, label)}
        outlet["items"].append(item)
        if plan_row.get("channel_id"):
            channels[plan_row["channel_id"]]["items_requested"] += 1
            channels[plan_row["channel_id"]]["items_2xx"] += int(isinstance(status, int) and 200 <= status < 300)

    per_outlet = {}
    for entry in plan["outlets"]:
        outlet_id, outlet = entry["outlet_id"], outlets.get(entry["outlet_id"], {"requests": Counter(), "refused": Counter(), "access_classes": Counter(), "items": [], "transport_calls": 0})
        good = [item for item in outlet["items"] if isinstance(item["status"], int) and 200 <= item["status"] < 300]
        characters = [item["body_characters"] for item in good if item["body_characters"] is not None]
        delays = []
        for item in good:
            if item["published_hint_utc"] and item["requested_at"] and item["novelty"] == intake.NEW_IN_WINDOW:
                delays.append((datetime.fromisoformat(item["requested_at"].replace("Z", "+00:00")) - datetime.fromisoformat(item["published_hint_utc"])).total_seconds())
        own = {channel["channel_id"] for channel in entry["channels"]}
        listed = Counter()
        for channel_id in own:
            listed.update(channels[channel_id]["candidates_first_listed"])
        per_outlet[outlet_id] = {
            "country_id": entry["country_id"], "tier": entry["tier"], "watched": outlet_id in WATCHED,
            "requests_answered": dict(sorted(outlet["requests"].items())), "refused_or_failed": dict(sorted(outlet["refused"].items())),
            "transport_calls": outlet["transport_calls"], "access_classes_observed": dict(sorted(outlet["access_classes"].items())),
            "held": state["holds"].get(outlet_id), "candidates_first_listed_in_the_intake": dict(sorted(listed.items())),
            "items_requested": len(outlet["items"]), "items_2xx": len(good),
            "items_2xx_by_novelty": dict(sorted(Counter(item["novelty"] for item in good).items())),
            "item_statuses": dict(sorted(Counter(str(item["status"]) for item in outlet["items"]).items())),
            "technically_usable": sum(1 for item in good if item["technical_status"] == "TECHNICALLY_USABLE"),
            "body_characters_median": int(statistics.median(characters)) if characters else None,
            "flags": dict(sorted(Counter(flag for item in good for flag in item["flags"]).items())),
            "items_2xx_without_any_flag": sum(1 for item in good if not item["flags"]),
            "seconds_from_publication_hint_to_request_median": int(statistics.median(delays)) if delays else None,
            "channels": {channel_id: {**channels[channel_id], "candidates_first_listed": dict(sorted(channels[channel_id]["candidates_first_listed"].items()))}
                         for channel_id in sorted(own)},
            "items": outlet["items"]}
    per_country: dict[str, dict[str, Any]] = {}
    for outlet_id, outlet in per_outlet.items():
        bucket = per_country.setdefault(outlet["country_id"], {"outlets": 0, "outlets_with_2xx_items": 0, "items_requested": 0, "items_2xx": 0, "new_dated_in_window_2xx": 0,
                                                              "new_undated_later_poll_2xx": 0, "technically_usable": 0, "transport_calls": 0})
        bucket["outlets"] += 1
        bucket["outlets_with_2xx_items"] += int(outlet["items_2xx"] > 0)
        for key in ("items_requested", "items_2xx", "technically_usable", "transport_calls"):
            bucket[key] += outlet[key]
        bucket["new_dated_in_window_2xx"] += outlet["items_2xx_by_novelty"].get(intake.NEW_IN_WINDOW, 0)
        bucket["new_undated_later_poll_2xx"] += outlet["items_2xx_by_novelty"].get(intake.NEW_UNDATED, 0)
    totals = {key: sum(bucket[key] for bucket in per_country.values()) for key in ("outlets", "outlets_with_2xx_items", "items_requested", "items_2xx",
                                                                                   "new_dated_in_window_2xx", "new_undated_later_poll_2xx", "technically_usable", "transport_calls")}
    totals["candidates_first_listed_in_the_intake"] = dict(sorted(Counter(kind for kind in novelty.values() if kind != intake.KNOWN_BEFORE).items()))
    totals["flags"] = dict(sorted(Counter(flag for outlet in per_outlet.values() for flag, count in outlet["flags"].items() for _ in range(count)).items()))
    return {"schema": MEASUREMENT_SCHEMA, "intake_id": plan["intake_id"], "flagger": FLAGGER, "started_at_utc": state["started_at_utc"], "deadline_at_utc": state["deadline_at_utc"],
            "cycles": state["cycle"], "totals": totals, "countries": dict(sorted(per_country.items())), "outlets": per_outlet,
            "novelty_classes": {intake.NEW_IN_WINDOW: "first listed during the intake, and its channel dates it inside the intake window",
                                intake.NEW_UNDATED: "first listed in a poll after its channel's first poll of the intake; the channel states no date",
                                intake.FIRST_POLL_UNDATED: "first listed at its channel's first poll of the intake, undated: stock, not known to be new",
                                intake.OLDER: "first listed during the intake; its channel dates it before the intake began",
                                intake.KNOWN_BEFORE: "listed before the intake began"},
            "not_a_claim": "counts of one bounded intake under an experimental extractor; flags are mechanical hints, not labels a person gave; "
                           "no statement about an outlet's output, about the press of a country or about suitability for a release"}


def review_package(measurement: Mapping[str, Any]) -> dict[str, Any]:
    """A stratified sample of fetched pages for a later human review: per outlet up to ``REVIEW_PER_OUTLET`` 2xx pages, flagged
    and unflagged alternating, chosen by the digest of the fetch id — the same evidence always gives the same sample.
    Every judgement field is empty: nothing here was labelled by a person, and nothing is to be read as if it were.
    """
    sample = []
    for outlet_id, outlet in sorted(measurement["outlets"].items()):
        good = sorted((item for item in outlet["items"] if isinstance(item["status"], int) and 200 <= item["status"] < 300 and item["fetch_id"]),
                      key=lambda item: sha256_bytes(item["fetch_id"].encode("utf-8")))
        flagged, plain = [item for item in good if item["flags"]], [item for item in good if not item["flags"]]
        chosen = []
        while len(chosen) < REVIEW_PER_OUTLET and (flagged or plain):
            for group in (plain, flagged):
                if group and len(chosen) < REVIEW_PER_OUTLET:
                    chosen.append(group.pop(0))
        for item in chosen:
            sample.append({"outlet_id": outlet_id, "country_id": outlet["country_id"], "fetch_id": item["fetch_id"], "url": item["final_url"] or item["url"],
                           "channel_id": item["channel_id"], "novelty": item["novelty"], "automated_flags": item["flags"], "body_characters": item["body_characters"],
                           "human_review": {"is_article": None, "published_in_window": None, "text_complete": None, "reviewer": None, "reviewed_at": None, "note": None}})
    return {"schema": REVIEW_SCHEMA, "intake_id": measurement["intake_id"], "flagger": measurement["flagger"], "per_outlet": REVIEW_PER_OUTLET, "pages": len(sample),
            "strata": dict(sorted(Counter(row["country_id"] for row in sample).items())),
            "status": "PREPARED — no page has been reviewed; every human_review field is empty and stays empty until a person fills it",
            "sample": sample}


def render(receipt: Mapping[str, Any], measurement: Mapping[str, Any], plan: Mapping[str, Any], disarmed: Sequence[str] | None = None) -> str:
    """The final report of an intake as Markdown. Every number is the receipt's or the measurement's."""
    totals, lines = measurement["totals"], []
    add = lines.append
    add(f"# Intake {receipt['intake_id']} — final report")
    add("")
    add("Written by the finalizer from the intake's evidence. No number here was typed by hand: each is in `receipt.json` or `measurement.json` beside this file.")
    add("")
    add("## Outcome")
    add("")
    add(f"- Outcome: **{receipt['outcome']}**" + (f" — {receipt['stopped_because']}" if receipt.get("stopped_because") else ""))
    add(f"- Started {receipt['started_at_utc']}, deadline {receipt['deadline_at_utc']}, finalized {receipt['finalized_at_utc']} (UTC)")
    add(f"- Cycles {receipt['cycles']}, acquisition runs {receipt['runs']}, restarts of the controller {receipt['restarts']}, outlet errors on record {receipt['errors']}")
    add(f"- Verification: **{receipt['verification']['status']}**")
    if disarmed is not None:
        add("- Disarming: " + ("`external_acquisition` is `disabled` in the file, in HEAD and on origin/main" if not disarmed else "**NOT CLEAN** — " + "; ".join(disarmed)))
    add("")
    add("## Scope and budgets")
    add("")
    budget = plan["budget"]
    add(f"- Plan: {plan['totals']['outlets']} outlets ({plan['totals']['tier_a']} tier A, {plan['totals']['tier_b']} tier B), {plan['totals']['channels']} channels, "
        f"{len(plan['totals']['countries'])} countries; policy `{plan['policy_version']}`")
    add(f"- Requests: {receipt['requests']['total']} of at most {budget['total_requests']} ({receipt['requests']['item']} item, {receipt['requests']['other']} other)")
    add(f"- Per outlet at most {budget['item_requests_per_outlet']} item requests ({budget['item_requests_per_outlet_hour']} in an hour), per origin {budget['item_requests_per_origin']}")
    add("")
    add("## Verification")
    add("")
    add("| Check | Status | Detail |")
    add("|---|---|---|")
    for check in receipt["verification"]["checks"]:
        add(f"| `{check['check']}` | {check['status']} | {str(check['detail']).replace('|', '/')} |")
    add("")
    add("## What was fetched")
    add("")
    add(f"- Item pages requested {totals['items_requested']}, answered 2xx {totals['items_2xx']}, technically usable under the experimental extractor {totals['technically_usable']}")
    add(f"- Of the 2xx pages: {totals['new_dated_in_window_2xx']} first listed during the intake and dated inside its window; "
        f"{totals['new_undated_later_poll_2xx']} first listed in a later poll without a date; the rest is stock or older")
    add(f"- Candidates first listed during the intake, by class: {json.dumps(totals['candidates_first_listed_in_the_intake'], ensure_ascii=False)}")
    add(f"- Outlets with at least one 2xx item page: {totals['outlets_with_2xx_items']} of {totals['outlets']}")
    add(f"- Answers by class: {json.dumps(receipt['response_classes'], ensure_ascii=False)}")
    add("")
    add("A URL found for the first time is not thereby an article published during the intake. Only the two classes named above say *new*; see `novelty_classes` in the measurement.")
    add("")
    add("## By country")
    add("")
    add("| Country | Outlets | With 2xx pages | Item requests | 2xx | New, dated in window | New, undated | Technically usable |")
    add("|---|---|---|---|---|---|---|---|")
    for country_id, row in measurement["countries"].items():
        add(f"| {country_id} | {row['outlets']} | {row['outlets_with_2xx_items']} | {row['items_requested']} | {row['items_2xx']} | {row['new_dated_in_window_2xx']} | "
            f"{row['new_undated_later_poll_2xx']} | {row['technically_usable']} |")
    add("")
    add("## By outlet")
    add("")
    add("| Outlet | Tier | Item requests | 2xx | New, dated | New, undated | Usable | Median body characters | Without a flag | Held |")
    add("|---|---|---|---|---|---|---|---|---|---|")
    for outlet_id, row in measurement["outlets"].items():
        add(f"| {outlet_id}{' (watched)' if row['watched'] else ''} | {row['tier']} | {row['items_requested']} | {row['items_2xx']} | "
            f"{row['items_2xx_by_novelty'].get(intake.NEW_IN_WINDOW, 0)} | {row['items_2xx_by_novelty'].get(intake.NEW_UNDATED, 0)} | {row['technically_usable']} | "
            f"{row['body_characters_median'] if row['body_characters_median'] is not None else '—'} | {row['items_2xx_without_any_flag']} | {row['held'] or ''} |")
    add("")
    add("## Automated anomaly flags")
    add("")
    add(f"Flagger `{measurement['flagger']}`: mechanical hints from the URL and the extraction's measurements. A flag is a reason to look, not a judgement; no page was removed.")
    add("")
    for flag, count in totals["flags"].items():
        add(f"- `{flag}`: {count}")
    add("")
    add("## Holds that arose")
    add("")
    for key, value in (receipt.get("holds_that_arose") or {}).items():
        add(f"- `{key}`: {value}")
    if not receipt.get("holds_that_arose"):
        add("- none")
    add("")
    add("## What this is not")
    add("")
    add(f"{measurement['not_a_claim']}.")
    add("")
    return "\n".join(lines)


__all__ = ["measure", "review_package", "render", "flags_of", "WATCHED", "FLAGGER"]
