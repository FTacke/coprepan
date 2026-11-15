"""Phase-3 repair study and blind control (CPD-0040): ``article_html/0.3.0`` against ``0.2.0``, ``agency-credit/2`` against
``/1``, ``text-reuse/2`` against ``/1``, content-quality/3 on both extractions -- on every stored 2xx item page, offline and
read-only -- and the frozen, blinded human control sample.

Usage:
  python scripts/study_phase3_repair.py derive    (--runtime <workspace> | --page-cache <pages.jsonl.gz>) --out <rows.jsonl.gz>
  python scripts/study_phase3_repair.py summarize --rows <rows.jsonl.gz> --out <study.json>
  python scripts/study_phase3_repair.py draw      --rows <rows.jsonl.gz> (--runtime <workspace> | --page-cache <pages.jsonl.gz>)
                                                  --out-dir <repository evidence dir> --sheet <local reading sheet .html>
  python scripts/study_phase3_repair.py merge     --out-dir <repository evidence dir> --verdicts <filled verdicts .csv> --out <result.json>

The page cache is ``study_phase3_metadata.py cache``'s (publisher bytes: local only, outside the repository, deleted after the
study). ``derive`` writes one row per page outside the repository (identifiers, titles and subtitles of both extractions,
digests, features, both metadata envelopes, the text-reuse relations of both rules; no body text). ``summarize`` writes the
versioned evidence record. ``draw`` freezes the blind control: a manifest (population, exclusions, seed, strata, sizes, the
digests of everything below), the verdict form (case and question ids, the allowed answers, an empty answer column -- no
predictions), the key (the machine's answer to every question, its evidence, rule versions and feature values; not to be opened
before the verdicts are in), and the local reading sheet (the page evidence and the BODY texts, publisher text: local only).
``merge`` reads the filled form against the key and reports agreement per question, separately for the random and the
targeted component.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import gzip
import hashlib
import html as _html
import io
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))
sys.path.insert(0, str(REPOSITORY / "scripts"))

from coprepan import content_quality as Q, editorial_metadata as M, enrichment, extraction as E  # noqa: E402
from coprepan import extraction_article as A, provenance as P, text_reuse as R  # noqa: E402
import study_phase3_metadata as S3  # noqa: E402

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")
SEED = "phase3-blind-control-2026-11-15"
REVIEW_2026_11_15 = REPOSITORY / "docs" / "intake" / "quality" / "phase3_review_2026-11-15.md"
# Pages this run opened one by one while it repaired the rules (fetch id prefixes after "ft1:"): development cases, never drawn.
DEVELOPMENT_PREFIXES = (
    "87bceea3aa", "dcf263e57c", "52a11ea14f", "2f1d2b667a", "eb516bf8ac", "17f1ff5ebb", "ecc64f5d7c", "4302732ac4", "27b0c343f5",
    "a6314d18ab", "b240edf949", "c0988361b8", "53ba056eac", "dc4316ee3d", "2439442813", "e7f74a5895", "59aac63482", "43c72da09d",
    "0aa1c687b4", "96f2bba26f", "395df246d7", "74ed93045e", "2f7274c27b", "6133650e69", "08adbe3009", "4c48be6ed6", "9b92c18c8d",
    "eb92b3452f", "4fb39de688", "72c4e4ad7c", "52a11ea14f", "2f1d2b667a")
_AI_HIT = re.compile(r"\bIA\b|\bAI\b|inteligencia artificial|ChatGPT|Gemini|Copilot|\bClaude\b|traducci[oó]n autom[aá]tica|"
                     r"generad[oa]s? (?:con|por|autom)|traducid[oa] (?:con|por|autom)|voz sint[eé]tica", re.I)
_AGENCY_HIT = re.compile(r"\b(?:EFE|AFP|Reuters|AP|Associated Press|dpa|DPA|Europa Press|ANSA|Xinhua|Prensa Latina|Sputnik|Bloomberg|IPS|"
                         r"ATON|T[ée]lam|Notimex|Colprensa|Andina|ACAN|Agencias|France Presse)\b")


# --- derive ------------------------------------------------------------------------------------------------------------------


def _subs(record):
    return [{"index": b["index"], "basis": b["basis"], "text": b["text"][:300]} for b in record["blocks"] if b["kind"] == E.KIND_SUBTITLE]


def _title(record):
    return next((b["text"] for b in record["blocks"] if b["kind"] == "title"), None)


def derive(arguments) -> int:
    registry = json.loads((REPOSITORY / "config" / "outlet_registry.json").read_text(encoding="utf-8"))
    country = {o["outlet_id"]: o["country_id"] for o in registry["outlets"]}
    section_map = M.load_section_map()
    rows, bodies, records = [], [], {}
    timing = Counter()
    for page, body in S3.stored_pages(arguments):
        t = time.perf_counter()
        two = A.ARTICLE_2.run(body, body_sha256=page["body_sha256"], **page["args"])
        timing["extract_0_2_0"] += time.perf_counter() - t
        t = time.perf_counter()
        three = A.ARTICLE_3.run(body, body_sha256=page["body_sha256"], **page["args"])
        timing["extract_0_3_0"] += time.perf_counter() - t
        try:
            html, _ = E._decode(E.decode_content(body, page["args"]["content_encoding"] or "identity"), page["args"]["declared_charset"])
        except E.ContentDecodingError:
            html = ""
        common = dict(html=html, url=page["url"], outlet_id=page["outlet_id"], country_id=country.get(page["outlet_id"], "unknown"),
                      section_map=section_map)
        t = time.perf_counter()
        m1 = enrichment.derive(record=two.record, version=enrichment.VERSION, **common)
        timing["metadata_1_on_0_2_0"] += time.perf_counter() - t
        t = time.perf_counter()
        m2 = enrichment.derive(record=three.record, version=enrichment.VERSION_2, **common)
        timing["metadata_2_on_0_3_0"] += time.perf_counter() - t
        f2 = Q.features(two.record, http_status=page["status"], html=html) if two.outcome == E.OUTCOME_EXTRACTED else None
        f3 = Q.features(three.record, http_status=page["status"], html=html) if three.outcome == E.OUTCOME_EXTRACTED else None
        s2, s3 = P.ai_statements(two.record), P.ai_statements(three.record)
        if s2 or s3:
            records[page["fetch_id"]] = (two.record, three.record)
        published = three.record["metadata"]["publication_date"]["value"]
        published = published[:19] if DATE.match(published or "") else None
        if three.outcome == E.OUTCOME_EXTRACTED:
            bodies.append({"document_id": page["fetch_id"], "outlet_id": page["outlet_id"], "body_text": three.body_text,
                           "published": published, "fetched_at": page["fetched_at"]})
        rows.append({
            "fetch_id": page["fetch_id"], "outlet_id": page["outlet_id"], "country_id": country.get(page["outlet_id"], "unknown"),
            "url": page["url"], "status": page["status"], "fetched_at": page["fetched_at"], "published": published,
            "body_sha256": page["body_sha256"],
            "v2": {"title": _title(two.record), "subtitles": _subs(two.record), "body": two.body_text_sha256,
                   "extracted": two.extracted_text_sha256, "modules": [b["index"] for b in two.record["blocks"] if b.get("module")],
                   "outcome": two.outcome},
            "v3": {"title": _title(three.record), "subtitles": _subs(three.record), "body": three.body_text_sha256,
                   "extracted": three.extracted_text_sha256, "modules": [b["index"] for b in three.record["blocks"] if b.get("module")],
                   "outcome": three.outcome, "meta_title": three.record["metadata"]["title"]["value"],
                   "meta_title_basis": three.record["metadata"]["title"]["basis"]},
            "features_v2": f2, "features_v3": f3, "ai_v2": s2, "ai_v3": s3,
            "publisher": {k: m2["publisher"][k] for k in ("sections", "breadcrumb", "authors", "organisations", "credit_text", "dateline")},
            "layers_1": m1["layers"], "layers_2": m2["layers"]})
    site2 = P.site_wide_statements([{"outlet_id": r["outlet_id"], "statements": r["ai_v2"]} for r in rows])
    site3 = P.site_wide_statements([{"outlet_id": r["outlet_id"], "statements": r["ai_v3"]} for r in rows])
    for r in rows:
        if r["fetch_id"] in records:
            two, three = records[r["fetch_id"]]
            if site2.get(r["outlet_id"]):
                r["layers_1"][P.LAYER_AI] = P.ai_disclosure(two, site_wide=site2[r["outlet_id"]])
            if site3.get(r["outlet_id"]):
                r["layers_2"][P.LAYER_AI] = P.ai_disclosure(three, site_wide=site3[r["outlet_id"]])
    by_url = {r["fetch_id"]: r["url"] for r in rows}
    t = time.perf_counter()
    reuse1 = R.relations(bodies, version=R.VERSION)
    timing["text_reuse_1"] = time.perf_counter() - t
    t = time.perf_counter()
    reuse2 = R.relations(bodies, version=R.VERSION_2)
    timing["text_reuse_2"] = time.perf_counter() - t
    # diagnostics of the second rule's relations (study only, never part of a relation): how much of the shared text is also in
    # other documents (boilerplate), and the word-level differences of the pair
    text_of = {b["document_id"]: b["body_text"] for b in bodies}
    grams_of = {d: R.shingles(R.words(t)) for d, t in text_of.items() if len(R.words(t)) >= R.MIN_WORDS}
    # boilerplate: a shingle that one outlet prints in at least three of its documents that are not copies of one another
    # (three different text-reuse clusters) is that outlet's furniture (a sign-off, a promotion, a legal note), not reused text
    cluster = R.clusters(reuse2)
    outlet_of = {b["document_id"]: b["outlet_id"] for b in bodies}
    groups_with = defaultdict(set)
    for d, grams in grams_of.items():
        for g in grams:
            groups_with[(outlet_of[d], g)].add(cluster.get(d, d))
    for relation in reuse2:
        a, b = relation["document_id"], relation["target_document_id"]
        shared = grams_of[a] & grams_of[b]
        furniture = sum(1 for g in shared if len(groups_with[(outlet_of[a], g)]) >= 3 or len(groups_with[(outlet_of[b], g)]) >= 3)
        relation["_study"] = {"shared_outlet_furniture_share": round(furniture / max(1, len(shared)), 3),
                              "same_url": _url_key(by_url[a]) == _url_key(by_url[b]), **_word_diff(text_of[a], text_of[b])}
    by1, by2 = defaultdict(list), defaultdict(list)
    for relation in reuse1:
        by1[relation["document_id"]].append(relation)
    for relation in reuse2:
        by2[relation["document_id"]].append(relation)
    with gzip.open(arguments.out, "wt", encoding="utf-8") as out:
        for r in rows:
            r["relations_1"], r["relations_2"] = by1.get(r["fetch_id"], []), by2.get(r["fetch_id"], [])
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
        out.write(json.dumps({"_meta": {"pages": len(rows), "seconds": {k: round(v, 1) for k, v in timing.items()},
                                        "site_wide_ai_statements_0_2_0": {k: sorted(v) for k, v in site2.items() if v},
                                        "site_wide_ai_statements_0_3_0": {k: sorted(v) for k, v in site3.items() if v},
                                        "section_map": section_map.pin(), "relations": [len(reuse1), len(reuse2)]}}, ensure_ascii=False) + "\n")
    print(json.dumps({"pages": len(rows), "relations": [len(reuse1), len(reuse2)], "seconds": {k: round(v, 1) for k, v in timing.items()}}))
    return 0


def _url_key(url: str) -> str:
    """The address without scheme, ``www.``, query, fragment and trailing slash: two fetches of one page (a study key only; the
    repository's document identity is ``coprepan.identity.canonical_url_key``)."""
    url = re.sub(r"^https?://(?:www\.)?", "", url.split("#")[0].split("?")[0].lower())
    return url.rstrip("/")


def _word_diff(a: str, b: str, limit: int = 6) -> dict:
    """The word-level differences of two BODY texts (difflib on their word sequences, case and punctuation kept)."""
    wa, wb = R.canonical_text(a).split(" "), R.canonical_text(b).split(" ")
    matcher = difflib.SequenceMatcher(None, wa, wb, autojunk=False)
    ops = [(tag, " ".join(wa[i1:i2]), " ".join(wb[j1:j2])) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"]
    changed = sum(max(len(x.split()) if x else 0, len(y.split()) if y else 0) for _, x, y in ops)
    return {"word_sequence_ratio": round(matcher.ratio(), 4), "differing_segments": len(ops), "words_in_differing_segments": changed,
            "first_differences": [{"op": tag, "this": x[:160], "target": y[:160]} for tag, x, y in ops[:limit]]}


# --- summarize ---------------------------------------------------------------------------------------------------------------


def _decisions(rows, key):
    pages = [{"fetch_id": r["fetch_id"], "outlet_id": r["outlet_id"], "url": r["url"], "fetched_at": r["fetched_at"] or "",
              "features": r[key], "extracted": r[key] is not None} for r in rows]
    return Q.assess_corpus(pages, ruleset=Q.RULESET_3)


def _agency_v1(layer):
    return (layer["attributes"] or {}).get("agency_use") if layer["value_state"] == "known" else f"unknown:{layer['reason']}"


def _agency_v2(layer):
    if layer["value_state"] != "known":
        return f"unknown:{layer['reason']}"
    a = layer["attributes"]
    return f"{'+'.join(a['agency_roles'])} / {a['use_declared']}"


def summarize(arguments) -> int:
    rows, meta = S3._read_rows(arguments.rows)
    n = len(rows)
    out: dict = {"schema": "coprepan-phase3-repair-study/v1", "date": "2026-11-15", "decision": "CPD-0040",
                 "population": {"pages": n, "outlets": len({r["outlet_id"] for r in rows}), "countries": len({r["country_id"] for r in rows}),
                                "what": "every stored 2xx item page of the workspace (the population of the CPD-0039 study), read from the "
                                        "local packs, offline"},
                 "derivation": meta}

    # A -- text structure
    title_changes = [r for r in rows if r["v2"]["title"] != r["v3"]["title"]]
    kind = Counter(("to_unknown" if r["v3"]["title"] is None else "other_h1", r["outlet_id"]) for r in title_changes)
    sub_change = Counter()
    sub_examples = defaultdict(list)
    lost_texts = Counter()
    for r in rows:
        a = [s["text"] for s in r["v2"]["subtitles"]]
        b = [s["text"] for s in r["v3"]["subtitles"]]
        if a == b:
            continue
        label = "removed_all" if a and not b else "added" if b and not a else "fewer" if set(b) <= set(a) else "more" if set(a) <= set(b) else "replaced"
        sub_change[(label, r["outlet_id"])] += 1
        for text in set(a) - set(b):
            lost_texts[(r["outlet_id"], text[:90])] += 1
        if len(sub_examples[label]) < 12:
            sub_examples[label].append({"outlet_id": r["outlet_id"], "url": r["url"], "fetch": r["fetch_id"][4:20],
                                        "title_0_3_0": (r["v3"]["title"] or "")[:120], "0_2_0": [t[:160] for t in a], "0_3_0": [t[:160] for t in b]})
    basis = lambda key: Counter(s["basis"] for r in rows for s in r[key]["subtitles"])  # noqa: E731
    out["text_structure"] = {
        "extractors": ["article_html/0.2.0", "article_html/0.3.0"],
        "body_same": sum(1 for r in rows if r["v2"]["body"] == r["v3"]["body"]),
        "body_changed": sum(1 for r in rows if r["v2"]["body"] != r["v3"]["body"]),
        "modules_same": sum(1 for r in rows if r["v2"]["modules"] == r["v3"]["modules"]),
        "extracted_text_changed": sum(1 for r in rows if r["v2"]["extracted"] != r["v3"]["extracted"]),
        "title_changed": len(title_changes),
        "title_changes": {f"{k}|{o}": c for (k, o), c in sorted(kind.items(), key=lambda kv: -kv[1])},
        "title_examples": [{"outlet_id": r["outlet_id"], "url": r["url"], "fetch": r["fetch_id"][4:20], "0_2_0": r["v2"]["title"],
                            "0_3_0": r["v3"]["title"], "metadata_title": r["v3"]["meta_title"], "metadata_title_basis": r["v3"]["meta_title_basis"]}
                           for r in _spread(title_changes, 3)],
        "pages_without_title_block": {"0_2_0": sum(1 for r in rows if r["v2"]["title"] is None),
                                      "0_3_0": sum(1 for r in rows if r["v3"]["title"] is None)},
        "pages_with_subtitle": {"0_2_0": sum(1 for r in rows if r["v2"]["subtitles"]), "0_3_0": sum(1 for r in rows if r["v3"]["subtitles"])},
        "subtitle_blocks_by_basis": {"0_2_0": dict(basis("v2")), "0_3_0": dict(basis("v3"))},
        "outlets_with_subtitle": {"0_2_0": len({r["outlet_id"] for r in rows if r["v2"]["subtitles"]}),
                                  "0_3_0": len({r["outlet_id"] for r in rows if r["v3"]["subtitles"]})},
        "subtitle_changes": {f"{k}|{o}": c for (k, o), c in sorted(sub_change.items(), key=lambda kv: -kv[1])},
        "subtitle_change_pages": sum(sub_change.values()),
        "subtitle_texts_removed": [{"outlet_id": o, "text": t, "pages": c} for (o, t), c in lost_texts.most_common(40)],
        "subtitle_examples": dict(sub_examples),
    }

    # quality
    d2, d3 = _decisions(rows, "features_v2"), _decisions(rows, "features_v3")
    trans = Counter(f"{d2[r['fetch_id']]['decision']}->{d3[r['fetch_id']]['decision']}" for r in rows)
    changed = [r for r in rows if d2[r["fetch_id"]] != d3[r["fetch_id"]]]
    out["quality"] = {
        "ruleset": Q.RULESET_3, "on_0_2_0": dict(Counter(d["decision"] for d in d2.values())),
        "on_0_3_0": dict(Counter(d["decision"] for d in d3.values())), "transitions": dict(trans),
        "pages_with_any_change_in_decision_or_reasons": len(changed),
        "changed": [{"fetch_id": r["fetch_id"], "outlet_id": r["outlet_id"], "url": r["url"], "on_0_2_0": d2[r["fetch_id"]]["reasons"],
                     "on_0_3_0": d3[r["fetch_id"]]["reasons"], "title_0_2_0": r["v2"]["title"], "title_0_3_0": r["v3"]["title"]} for r in changed],
        "features_equal_but_title": sum(1 for r in rows if r["features_v2"] and r["features_v3"] and
                                        {k: v for k, v in r["features_v2"].items() if k not in ("title", "title_text")} ==
                                        {k: v for k, v in r["features_v3"].items() if k not in ("title", "title_text")}),
    }

    # other layers: unchanged?
    same = {}
    for name in (M.LAYER_SECTION, M.LAYER_SCOPE, M.LAYER_PLACEMENT, M.LAYER_DECLARED, P.LAYER_AI):
        same[name] = sum(1 for r in rows if r["layers_1"][name] == r["layers_2"][name])
    out["unchanged_layers"] = {"pages_with_the_same_layer_record": same, "of": n,
                               "ai_changes": [{"fetch_id": r["fetch_id"], "outlet_id": r["outlet_id"],
                                               "1": [r["layers_1"][P.LAYER_AI]["value"], r["layers_1"][P.LAYER_AI]["attributes"]["components"]],
                                               "2": [r["layers_2"][P.LAYER_AI]["value"], r["layers_2"][P.LAYER_AI]["attributes"]["components"]]}
                                              for r in rows if r["layers_1"][P.LAYER_AI] != r["layers_2"][P.LAYER_AI]][:20]}

    # B -- agency
    a1 = {r["fetch_id"]: r["layers_1"][P.LAYER_AGENCY] for r in rows}
    a2 = {r["fetch_id"]: r["layers_2"][P.LAYER_AGENCY_2] for r in rows}
    known1 = [r for r in rows if a1[r["fetch_id"]]["value_state"] == "known"]
    known2 = [r for r in rows if a2[r["fetch_id"]]["value_state"] == "known"]
    transitions = Counter(f"{_agency_v1(a1[r['fetch_id']])} -> {_agency_v2(a2[r['fetch_id']])}" for r in rows
                          if a1[r["fetch_id"]]["value_state"] == "known" or a2[r["fetch_id"]]["value_state"] == "known")
    out["agency_credit"] = {
        "rules": [P.LAYER_AGENCY, P.LAYER_AGENCY_2],
        "pages_known": {"1": len(known1), "2": len(known2)},
        "same_agencies_where_both_known": sum(1 for r in rows if a1[r["fetch_id"]]["value"] and a1[r["fetch_id"]]["value"] == a2[r["fetch_id"]]["value"]),
        "agencies_2": dict(Counter(a for r in known2 for a in a2[r["fetch_id"]]["value"]).most_common()),
        "pages_with_several_agencies_2": sum(1 for r in known2 if len(a2[r["fetch_id"]]["value"]) > 1),
        "use_1": dict(Counter(_agency_v1(a1[r["fetch_id"]]) for r in known1)),
        "roles_2": dict(Counter("+".join(a2[r["fetch_id"]]["attributes"]["agency_roles"]) for r in known2)),
        "use_declared_2": dict(Counter(a2[r["fetch_id"]]["attributes"]["use_declared"] for r in known2)),
        "transitions_1_to_2": dict(transitions.most_common()),
        "unknown_reasons_2": dict(Counter(a2[r["fetch_id"]]["reason"] for r in rows if a2[r["fetch_id"]]["value_state"] != "known")),
        "edited_declared_1_read_again": [{"outlet_id": r["outlet_id"], "url": r["url"], "fetch": r["fetch_id"][4:20],
                                          "credit": [e["text"] for e in a2[r["fetch_id"]]["attributes"]["evidence"]],
                                          "2": _agency_v2(a2[r["fetch_id"]])}
                                         for r in known1 if a1[r["fetch_id"]]["attributes"]["agency_use"] == "edited_declared"],
        "joint_credit_1_read_again": [{"outlet_id": r["outlet_id"], "fetch": r["fetch_id"][4:20],
                                       "credit": [e["text"][:120] for e in a2[r["fetch_id"]]["attributes"]["evidence"]][:3],
                                       "credited_with": sorted({c for e in a2[r["fetch_id"]]["attributes"]["evidence"] for c in e["credited_with"]}),
                                       "2": _agency_v2(a2[r["fetch_id"]])}
                                      for r in known1 if a1[r["fetch_id"]]["attributes"]["agency_use"] == "joint_credit"],
        "quoted_only_examples": [{"outlet_id": r["outlet_id"], "fetch": r["fetch_id"][4:20],
                                  "mention": a2[r["fetch_id"]]["attributes"]["quoted_source_mentions"][0]["text"][:200]}
                                 for r in _spread([r for r in rows if a2[r["fetch_id"]]["reason"] == "agency_named_as_quoted_source_only"], 1)][:12],
        "positions_2": dict(Counter(f"{e['position']}:{e['role']}" for r in known2 for e in a2[r["fetch_id"]]["attributes"]["evidence"]).most_common()),
    }

    # C -- text reuse
    rel1 = {(x["document_id"], x["target_document_id"]): x for r in rows for x in r["relations_1"]}
    rel2 = {(x["document_id"], x["target_document_id"]): x for r in rows for x in r["relations_2"]}
    move = Counter(f"{rel1[k]['relation']}|{rel1[k]['match']} -> {rel2[k]['text_match']}" for k in rel1 if k in rel2)
    classes = Counter(f"{x['relation']}|{x['text_match']}" for x in rel2.values())
    boiler = [x for x in rel2.values() if x["_study"]["shared_outlet_furniture_share"] >= 0.5]
    near_ratio = sorted(x["_study"]["word_sequence_ratio"] for x in rel2.values() if x["text_match"] == "near_identical")
    out["text_reuse"] = {
        "rules": [R.VERSION, R.VERSION_2],
        "relations": {"1": len(rel1), "2": len(rel2), "same_pairs": len(set(rel1) & set(rel2))},
        "classes_2": dict(classes),
        "transitions_1_to_2": dict(move),
        "near_identical_word_sequence_ratio": {"min": near_ratio[0] if near_ratio else None, "median": near_ratio[len(near_ratio) // 2] if near_ratio else None,
                                               "max": near_ratio[-1] if near_ratio else None},
        "exact_but_case_or_punctuation_only_difference_impossible": "exact = equal canonical strings; any difference in case, "
                                                                    "punctuation or wording makes a pair near_identical or contained",
        "pairs_with_same_words_different_text": sum(1 for x in rel2.values() if x["text_match"] != "exact" and x["differing_words"] == [0, 0]),
        "boilerplate_check": {"rule": "share of the pair's shared 8-word shingles that one of the two outlets prints in at least three "
                                      "of its documents that are not copies of one another (three text-reuse clusters): the outlet's "
                                      "furniture, not reused text",
                              "pairs_at_or_over_half": len(boiler),
                              "pairs_over_a_tenth": sum(1 for x in rel2.values() if x["_study"]["shared_outlet_furniture_share"] > 0.1),
                              "by_class_over_a_tenth": dict(Counter(f"{x['relation']}|{x['text_match']}" for x in rel2.values()
                                                                    if x["_study"]["shared_outlet_furniture_share"] > 0.1)),
                              "examples": [_pair_view(x) for x in sorted(rel2.values(), key=lambda x: -x["_study"]["shared_outlet_furniture_share"])[:8]]},
        "same_address": {"what": "both documents of the relation are fetches of one address (study key: no scheme, www, query, "
                                 "fragment or trailing slash): a re-fetch of one page, not a relation between two documents",
                         "by_class": dict(Counter(f"{x['relation']}|{x['text_match']}|{'same_address' if x['_study']['same_url'] else 'different_address'}"
                                                  for x in rel2.values()))},
        "cross_outlet_by_class": dict(Counter(x["text_match"] for x in rel2.values() if x["relation"] == R.SYNDICATED)),
        "within_outlet_by_class": dict(Counter(x["text_match"] for x in rel2.values() if x["relation"] == R.DUPLICATE)),
        "examples": {cls: [_pair_view(x) for x in _spread_pairs([x for x in rel2.values() if x["text_match"] == cls], 4)]
                     for cls in R.TEXT_MATCHES},
        "quality_of_the_later_document": dict(Counter(f"{x['relation']}|{x['text_match']}|{d3[x['document_id']]['decision']}" for x in rel2.values())),
    }
    out["timing_seconds"] = meta.get("seconds")
    arguments.out.write_bytes((json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(json.dumps({k: out[k] for k in ("quality",)}, ensure_ascii=False)[:600])
    print(json.dumps({"title": out["text_structure"]["title_changed"], "subtitle_pages": out["text_structure"]["subtitle_change_pages"],
                      "body_changed": out["text_structure"]["body_changed"], "agency": out["agency_credit"]["transitions_1_to_2"],
                      "reuse": out["text_reuse"]["transitions_1_to_2"], "boiler": len(boiler)}, ensure_ascii=False))
    return 0


def _pair_view(x):
    return {"relation": x["relation"], "text_match": x["text_match"], "document": x["document_id"][4:20], "target": x["target_document_id"][4:20],
            "outlets": x["outlet_of"], "containment": x["containment"], "words": x["words"], "differing_words": x["differing_words"],
            "word_sequence_ratio": x["_study"]["word_sequence_ratio"], "differing_segments": x["_study"]["differing_segments"],
            "shared_outlet_furniture_share": x["_study"]["shared_outlet_furniture_share"], "first_differences": x["_study"]["first_differences"][:3]}


def _spread(items, per_outlet):
    seen, out = Counter(), []
    for r in sorted(items, key=lambda r: hashlib.sha256((SEED + r["fetch_id"]).encode()).hexdigest()):
        if seen[r["outlet_id"]] < per_outlet:
            out.append(r)
            seen[r["outlet_id"]] += 1
    return out


def _spread_pairs(items, k):
    seen, out = set(), []
    for x in sorted(items, key=lambda x: hashlib.sha256((SEED + x["document_id"] + x["target_document_id"]).encode()).hexdigest()):
        key = tuple(x["outlet_of"])
        if key not in seen:
            out.append(x)
            seen.add(key)
        if len(out) == k:
            break
    return out


# --- the blind control ---------------------------------------------------------------------------------------------------------

ANSWERS = {
    "TITLE": "a letter of the candidate that is this article's headline as the page prints it; N if none is",
    "SUBTITLE": "the number(s) of the block(s) that are the article's subtitle / standfirst (comma-separated); 0 if none",
    "BODY_COMPLETE": "complete | incomplete | not_an_article",
    "BODY_CLEAN": "clean | some_foreign_material | mostly_foreign_material",
    "CORE": "yes | no | unsure  (a complete Spanish press text of running prose, at least 150 words; not a live ticker, list, "
            "page frame, paywall or login stub, page about the publication, or paid content -- provenance does not matter)",
    "IPTC": "the IPTC Media Topics top-level code(s) the published section label names (e.g. 15000000), comma-separated; none "
            "if the label names no topic or is ambiguous",
    "AI_TEXT": "generated | assisted | translated | unclear | none  (what the page declares about AI use for the article text)",
    "AI_COMPONENT": "summary | audio | image | none  (AI-made parts beside the article the page declares; comma-separated)",
    "AGENCY_ROLE": "credited | co_credited | material_source | quoted_only | none  (comma-separated if several)",
    "AGENCY_USE": "verbatim_declared | edited_declared | material_used_declared | not_stated",
    "REUSE": "exact | near_identical | contained | partial_overlap | unrelated",
}
DEFINITIONS = {
    "credited": "the agency is named as author or source of the published text (author field, byline, wire dateline, credit)",
    "co_credited": "the agency is credited together with the outlet's newsroom or the publisher",
    "material_source": "the agency is named as the source of material the text uses ('Con información de EFE')",
    "quoted_only": "the agency is only quoted in the running text as a source ('según la agencia EFE'); nothing credits it",
    "exact": "the same text, word for word, with the same punctuation and case (paragraph breaks and spacing may differ)",
    "near_identical": "almost the same text throughout: a changed opening or close, a sentence or a few words different",
    "contained": "the shorter text stands (almost) entirely inside the longer one, which has substantial further text",
    "partial_overlap": "a substantial shared passage, but neither of the above",
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _excluded_prefixes() -> set[str]:
    prefixes = set(re.findall(r"\| `([0-9a-f]{16})` \|", REVIEW_2026_11_15.read_text(encoding="utf-8")))
    return prefixes | set(DEVELOPMENT_PREFIXES)


def _is_excluded(fetch_id: str, prefixes: set[str]) -> bool:
    return any(fetch_id[4:].startswith(p) for p in prefixes)


def _strata(rows, d3):
    a2 = lambda r: r["layers_2"][P.LAYER_AGENCY_2]  # noqa: E731
    a1 = lambda r: r["layers_1"][P.LAYER_AGENCY]  # noqa: E731
    ai = lambda r: r["layers_2"][P.LAYER_AI]  # noqa: E731
    sec = lambda r: r["layers_2"][M.LAYER_SECTION]  # noqa: E731
    acc = lambda r: d3[r["fetch_id"]]["decision"] == Q.ACCEPT  # noqa: E731
    return [  # (id, what, k, predicate) -- page strata; pair strata below
        ("T01_title_changed", "title block changed by 0.3.0 (another h1, or none)", 5, lambda r: r["v2"]["title"] != r["v3"]["title"]),
        ("T02_subtitle_removed", "a subtitle of 0.2.0 that 0.3.0 does not keep", 4,
         lambda r: {s["text"] for s in r["v2"]["subtitles"]} - {s["text"] for s in r["v3"]["subtitles"]}),
        ("T03_subtitle_stated", "a subtitle 0.3.0 takes from the page's own statement", 3,
         lambda r: any(s["basis"] == E.SUBTITLE_STATED_BY_PAGE for s in r["v3"]["subtitles"])),
        ("T04_subtitle_markup", "a subtitle 0.3.0 takes by markup alone", 3,
         lambda r: r["v3"]["subtitles"] and all(s["basis"] == E.SUBTITLE_BY_MARKUP for s in r["v3"]["subtitles"])),
        ("T05_no_subtitle_accepted", "no subtitle, CORE accepted (recall)", 3, lambda r: not r["v3"]["subtitles"] and acc(r)),
        ("T06_ai_article", "AI use declared for the article text", 4, lambda r: ai(r)["value"] in P.AI_VALUES),
        ("T07_ai_component", "AI components only", 2, lambda r: ai(r)["reason"] == "components_only"),
        ("T08_agency_reclassified", "agency-credit/1 'edited_declared' or 'joint_credit'", 4,
         lambda r: (a1(r)["attributes"] or {}).get("agency_use") in ("edited_declared", "joint_credit")),
        ("T09_agency_credited", "agency-credit/2 role 'credited' only", 2,
         lambda r: a2(r)["value_state"] == "known" and a2(r)["attributes"]["agency_roles"] == ["credited"]),
        ("T10_agency_quoted_only", "agency named only as a quoted source", 3, lambda r: a2(r)["reason"] == "agency_named_as_quoted_source_only"),
        ("T11_core_rejected", "CORE rejected by content-quality/3", 3, lambda r: d3[r["fetch_id"]]["decision"] == Q.REJECT and r["features_v3"]),
        ("T12_iptc_not_known", "a published section, IPTC unknown or undecided", 2,
         lambda r: sec(r)["value_state"] != "known" and sec(r)["attributes"].get("published")),
    ]


PAIR_STRATA = [("T13_reuse_exact", "exact", 2), ("T14_reuse_near_identical", "near_identical", 3), ("T15_reuse_contained", "contained", 3)]
RANDOM_SIZE = 24
# A targeted case asks only the questions of its feature (the machine's answer is never shown); a random case asks every
# question that applies to the page.
TARGETED_QUESTIONS = {"T01": ("TITLE", "SUBTITLE"), "T02": ("TITLE", "SUBTITLE"), "T03": ("TITLE", "SUBTITLE"), "T04": ("TITLE", "SUBTITLE"),
                      "T05": ("TITLE", "SUBTITLE"), "T06": ("AI_TEXT", "AI_COMPONENT"), "T07": ("AI_TEXT", "AI_COMPONENT"),
                      "T08": ("AGENCY_ROLE", "AGENCY_USE"), "T09": ("AGENCY_ROLE", "AGENCY_USE"), "T10": ("AGENCY_ROLE", "AGENCY_USE"),
                      "T11": ("BODY_COMPLETE", "BODY_CLEAN", "CORE"), "T12": ("IPTC",)}


def _systematic(items, n, seed):
    """A systematic sample of ``n`` with a random start over ``items`` (already in the order that spreads it): every item has
    the inclusion probability n / len(items)."""
    if not items:
        return []
    start = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % 10 ** 9 / 10 ** 9
    step = len(items) / n
    return [items[int(math.floor((start + j) * step))] for j in range(n)]


def _pick(items, k, seed, per_outlet=1):
    seen, out = Counter(), []
    for r in sorted(items, key=lambda r: hashlib.sha256((seed + r["fetch_id"]).encode()).hexdigest()):
        if seen[r["outlet_id"]] < per_outlet:
            out.append(r)
            seen[r["outlet_id"]] += 1
        if len(out) == k:
            break
    return out


def _page_view(parser, blocks):
    """The neutral evidence of one page: title candidates, the header window, metadata statements."""
    norm = A._norm
    candidates, seen = [], set()

    def add(source, text):
        if isinstance(text, str) and text.strip() and norm(text) not in seen:
            seen.add(norm(text))
            candidates.append({"source": source, "text": text.strip()[:300]})

    h1 = [i for i, item in enumerate(parser.raw) if item["tag"] == "h1"]
    for n, i in enumerate(h1[:4]):
        add(f"h1 no. {n + 1} on the page", blocks[i]["text"])
    for value in parser._json_ld_strings("headline")[:2]:
        add("JSON-LD headline", value)
    for value in parser.meta.get("og:title", [])[:1]:
        add("og:title", value)
    for value in parser.meta.get("title", [])[:1]:
        add("<title>", value)
    # the blocks after every h1 (at most four), in page order: up to 8 blocks of 20 characters or more after each, until the
    # third block of 25 words or more -- the same window whichever h1 the machine took
    picked: set[int] = set()
    for start in (h1[:4] or [-1]):
        taken = long_seen = 0
        for i in range(start + 1, len(blocks)):
            text = blocks[i]["text"]
            if parser.raw[i]["tag"] == "h1":
                break
            if len(text) < 20:
                continue
            picked.add(i)
            taken += 1
            long_seen += len(text.split()) >= 25
            if long_seen >= 3 or taken >= 8:
                break
    window = [{"block": i, "text": blocks[i]["text"][:400]} for i in sorted(picked)][:24]
    return {"title_candidates": candidates, "window": window,
            "stated_descriptions": [d[:400] for d in dict.fromkeys(
                [*parser._json_ld_strings("description")[:2], *parser.meta.get("og:description", [])[:1], *parser.meta.get("description", [])[:1]])]}


def _letters(n):
    return [chr(ord("A") + i) for i in range(n)]


def _neutral_ai(blocks):
    return [b["text"][:400] for b in blocks if len(b["text"]) <= 600 and _AI_HIT.search(b["text"])][:8]


def _neutral_agency(row, blocks):
    hits = []
    pub = row["publisher"]
    for a in pub["authors"]:
        hits.append(f"author ({a['basis']}): {a['name']}")
    for o in pub["organisations"]:
        if o["role"] in ("sourceOrganization", "copyrightHolder", "provider"):
            hits.append(f"JSON-LD {o['role']}: {o['name']}")
    hits += [f"JSON-LD creditText: {t}" for t in pub["credit_text"]] + [f"JSON-LD dateline: {t}" for t in pub["dateline"]]
    body = [b for b in blocks if b["role"] == E.ROLE_BODY]
    if body:
        hits.append(f"opening of the running text: {body[0]['text'][:140]}")
    for b in blocks:
        if _AGENCY_HIT.search(b["text"]):
            if len(b["text"]) <= 200:
                hits.append(f"block: {b['text']}")
            else:
                for m in list(_AGENCY_HIT.finditer(b["text"]))[:2]:
                    hits.append(f"…{b['text'][max(0, m.start() - 90):m.end() + 90]}…")
    return list(dict.fromkeys(hits))[:14]


def draw(arguments) -> int:
    rows, _ = S3._read_rows(arguments.rows)
    by_id = {r["fetch_id"]: r for r in rows}
    d3 = _decisions(rows, "features_v3")
    excluded = _excluded_prefixes()
    eligible = [r for r in rows if not _is_excluded(r["fetch_id"], excluded)]
    order = sorted(eligible, key=lambda r: (r["country_id"], r["outlet_id"], hashlib.sha256((SEED + r["fetch_id"]).encode()).hexdigest()))
    random_part = _systematic(order, RANDOM_SIZE, SEED + "/random")
    used = {r["fetch_id"] for r in random_part}
    cases = [{"component": "random", "stratum": "R00_random", "fetch_ids": [r["fetch_id"]],
              "inclusion_probability": round(RANDOM_SIZE / len(order), 6)} for r in random_part]
    strata_doc = [{"stratum": "R00_random", "component": "random", "population": len(order), "drawn": len(random_part),
                   "method": "systematic sample with a random start over the eligible pages ordered by country, outlet and "
                             "sha256(seed + fetch id); inclusion probability n / N for every page",
                   "inclusion_probability": round(RANDOM_SIZE / len(order), 6)}]
    for stratum, what, k, predicate in _strata(rows, d3):
        population = [r for r in eligible if predicate(r) and r["fetch_id"] not in used]
        picked = _pick(population, k, f"{SEED}/{stratum}")
        used |= {r["fetch_id"] for r in picked}
        strata_doc.append({"stratum": stratum, "component": "targeted", "what": what, "population": len(population), "drawn": len(picked),
                           "method": "the first k by sha256(seed/stratum + fetch id), at most one page per outlet",
                           "inclusion_probability": "not equal within the stratum (one page per outlet); not for population estimates"})
        cases += [{"component": "targeted", "stratum": stratum, "fetch_ids": [r["fetch_id"]]} for r in picked]
    pairs = [x for r in eligible for x in r["relations_2"] if not _is_excluded(x["target_document_id"], excluded)]
    for stratum, cls, k in PAIR_STRATA:
        population = [x for x in pairs if x["text_match"] == cls and x["document_id"] not in used and x["target_document_id"] not in used]
        seen, picked = set(), []
        for x in sorted(population, key=lambda x: hashlib.sha256((f"{SEED}/{stratum}" + x["document_id"] + x["target_document_id"]).encode()).hexdigest()):
            if x["outlet_of"][0] in seen or x["outlet_of"][1] in seen:
                continue
            picked.append(x)
            seen |= set(x["outlet_of"])
            if len(picked) == k:
                break
        used |= {d for x in picked for d in (x["document_id"], x["target_document_id"])}
        strata_doc.append({"stratum": stratum, "component": "targeted", "what": f"a text-reuse/2 pair of class {cls}", "population": len(population),
                           "drawn": len(picked), "method": "the first k pairs by sha256(seed/stratum + ids), no outlet twice",
                           "inclusion_probability": "not for population estimates"})
        cases += [{"component": "targeted", "stratum": stratum, "fetch_ids": [x["document_id"], x["target_document_id"]], "pair": x} for x in picked]
    # case ids: a neutral order (by digest), so that neither the component nor the stratum shows in the id or the position
    for case in cases:
        case["_order"] = hashlib.sha256((SEED + "/case/" + "+".join(case["fetch_ids"])).encode()).hexdigest()
    cases.sort(key=lambda c: c["_order"])
    for n, case in enumerate(cases, 1):
        case["case_id"] = f"C{n:02d}"
    need = {f for c in cases for f in c["fetch_ids"]}
    pages = {}
    for page, body in S3.stored_pages(arguments):
        if page["fetch_id"] in need:
            three = A.ARTICLE_3.run(body, body_sha256=page["body_sha256"], **page["args"])
            html, _ = E._decode(E.decode_content(body, page["args"]["content_encoding"] or "identity"), page["args"]["declared_charset"])
            parser = A._Parser3()
            parser.feed(html)
            parser.close()
            blocks = parser.blocks()
            if [b["text"] for b in blocks] != [b["text"] for b in three.record["blocks"]]:
                raise SystemExit(f"{page['fetch_id']}: the parser view differs from the extraction record")
            pages[page["fetch_id"]] = {"blocks": three.record["blocks"], "body_text": three.body_text, "view": _page_view(parser, blocks),
                                       "extracted_text_sha256": three.extracted_text_sha256}
    taxonomy = M.load_section_map().taxonomy
    tops = sorted((c["qcode"].split(":")[1], c["label_es"]) for c in taxonomy.concepts.values() if not c["broader"] and not c.get("retired"))
    form, key, sheet_cases = [], [], []
    for case in cases:
        questions, predictions, evidence = [], {}, {}
        if "pair" in case:
            x = case["pair"]
            questions.append("REUSE")
            predictions["REUSE"] = x["text_match"]
            evidence["REUSE"] = {k: x[k] for k in ("relation", "rule", "text_match", "containment", "shingles", "shared_shingles", "words",
                                                    "differing_words", "basis")}
            a, b = (pages[f] for f in case["fetch_ids"])
            sheet_cases.append({"case_id": case["case_id"], "pair": True,
                                "documents": [{"outlet": by_id[f]["outlet_id"], "url": by_id[f]["url"], "published": by_id[f]["published"],
                                               "body": pages[f]["body_text"]} for f in case["fetch_ids"]],
                                "diff": _word_diff(a["body_text"], b["body_text"], limit=40)})
        else:
            fid = case["fetch_ids"][0]
            r, page = by_id[fid], pages[fid]
            view, blocks = page["view"], page["blocks"]
            letters = _letters(len(view["title_candidates"]))
            questions += ["TITLE", "SUBTITLE", "BODY_COMPLETE", "BODY_CLEAN", "CORE"]
            title = r["v3"]["title"]
            predictions["TITLE"] = next((l for l, c in zip(letters, view["title_candidates"]) if title is not None and A._norm(c["text"]) == A._norm(title)),
                                        "N" if title is None else "?")
            numbers = {w["block"]: str(n) for n, w in enumerate(view["window"], 1)}
            sub_blocks = [s["index"] for s in r["v3"]["subtitles"]]
            predictions["SUBTITLE"] = ",".join(numbers.get(i, "?") for i in sub_blocks) or "0"
            predictions["BODY_COMPLETE"] = predictions["BODY_CLEAN"] = "(judgement of the extracted BODY shown; no prediction)"
            predictions["CORE"] = "yes" if d3[fid]["decision"] == Q.ACCEPT else "no"
            evidence["TITLE"] = {"title_0_3_0": title, "metadata_title": r["v3"]["meta_title"], "basis": r["v3"]["meta_title_basis"]}
            evidence["SUBTITLE"] = r["v3"]["subtitles"]
            evidence["CORE"] = {"ruleset": Q.RULESET_3, "reasons": d3[fid]["reasons"], "evidence": d3[fid]["evidence"]}
            sections = [s["value"] for s in r["publisher"]["sections"]][:3]
            if sections:
                questions.append("IPTC")
                layer = r["layers_2"][M.LAYER_SECTION]
                predictions["IPTC"] = ",".join(t.split(":")[1] for t in layer["attributes"].get("tops", [])) or "none"
                evidence["IPTC"] = {"state": layer["value_state"], "reason": layer["reason"], "value": layer["value"], "rule": layer["rule"]}
            ai_hits = _neutral_ai(blocks)
            if ai_hits or case["stratum"] in ("T06_ai_article", "T07_ai_component"):
                questions += ["AI_TEXT", "AI_COMPONENT"]
                layer = r["layers_2"][P.LAYER_AI]
                predictions["AI_TEXT"] = layer["value"] or "none"
                predictions["AI_COMPONENT"] = ",".join(layer["attributes"]["components"]) or "none"
                evidence["AI"] = {"state": layer["value_state"], "reason": layer["reason"], "statements": layer["attributes"]["statements"]}
            agency_hits = _neutral_agency(r, blocks)
            if any(_AGENCY_HIT.search(h) for h in agency_hits) or case["stratum"].startswith(("T08", "T09", "T10")):
                questions += ["AGENCY_ROLE", "AGENCY_USE"]
                layer = r["layers_2"][P.LAYER_AGENCY_2]
                if layer["value_state"] == "known":
                    predictions["AGENCY_ROLE"] = ",".join(layer["attributes"]["agency_roles"])
                    predictions["AGENCY_USE"] = layer["attributes"]["use_declared"]
                else:
                    predictions["AGENCY_ROLE"] = "quoted_only" if layer["reason"] == "agency_named_as_quoted_source_only" else "none"
                    predictions["AGENCY_USE"] = "not_stated"
                evidence["AGENCY"] = {"state": layer["value_state"], "reason": layer["reason"], "value": layer["value"],
                                      "attributes": layer["attributes"], "agency_credit_1": r["layers_1"][P.LAYER_AGENCY]["attributes"]}
            if case["component"] == "targeted":
                allowed = TARGETED_QUESTIONS[case["stratum"][:3]]
                questions = [q for q in questions if q in allowed]
                predictions = {q: v for q, v in predictions.items() if q in allowed}
            sheet_cases.append({"case_id": case["case_id"], "pair": False, "outlet": r["outlet_id"], "country": r["country_id"], "url": r["url"],
                                "published": r["published"], "title_candidates": list(zip(letters, view["title_candidates"])),
                                "window": [(numbers[w["block"]], w["text"]) for w in view["window"]],
                                "stated_descriptions": view["stated_descriptions"], "sections": sections,
                                "breadcrumb": r["publisher"]["breadcrumb"][:6], "body": page["body_text"], "ai_hits": ai_hits,
                                "agency_hits": agency_hits, "questions": questions})
        for question in questions:
            form.append({"case_id": case["case_id"], "question": question, "allowed": ANSWERS[question], "answer": "", "note": ""})
        key.append({"case_id": case["case_id"], "component": case["component"], "stratum": case["stratum"], "fetch_ids": case["fetch_ids"],
                    "inclusion_probability": case.get("inclusion_probability"),
                    "extracted_text_sha256": [pages[f]["extracted_text_sha256"] for f in case["fetch_ids"]],
                    "predictions": predictions, "evidence": evidence,
                    "versions": {"extractor": "article_html/0.3.0", "quality": Q.RULESET_3, "metadata": enrichment.VERSION_2,
                                 "agency": P.LAYER_AGENCY_2, "ai": P.LAYER_AI, "section": M.LAYER_SECTION, "reuse": R.VERSION_2}})
    out_dir = arguments.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["case_id", "question", "allowed", "answer", "note"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(form)
    form_bytes = buffer.getvalue().encode("utf-8")
    key_bytes = (json.dumps({"schema": "coprepan-phase3-blind-key/v1", "seed": SEED, "cases": key}, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    sheet_bytes = _sheet(sheet_cases, tops).encode("utf-8")
    (out_dir / "verdicts_form.csv").write_bytes(form_bytes)
    (out_dir / "KEY_machine_predictions_open_only_after_the_verdicts.json").write_bytes(key_bytes)
    arguments.sheet.write_bytes(sheet_bytes)
    manifest = {
        "schema": "coprepan-phase3-blind-control/v1", "date": "2026-11-15", "decision": "CPD-0040", "seed": SEED,
        "frozen_before_review": True,
        "population": {"what": "the stored 2xx item pages of the CPD-0039 / CPD-0040 study", "pages": len(rows),
                       "excluded_development_and_review_pages": len(rows) - len(eligible), "eligible": len(eligible),
                       "exclusion_rule": "every page of the 2026-11-15 review sample (109 rows) and every page this run opened one by one "
                                         "while repairing the rules (DEVELOPMENT_PREFIXES of the script)"},
        "limits": ["the rules were repaired on aggregate measurements of this same population (all pages), so the control is "
                   "independent of the cases the rules were tuned on, not of the population: it is not fresh data",
                   f"the random component (n={RANDOM_SIZE}) supports coarse statements only (e.g. 24 of 24 agreements: 95 % lower "
                   "bound about 0.86); the targeted strata find errors and do not estimate population precision",
                   "BODY questions judge the extracted text shown, so they are not blind to the extraction itself; every other "
                   "question is asked without the machine's answer"],
        "strata": strata_doc,
        "cases": [{"case_id": c["case_id"], "fetch_ids": c["fetch_ids"]} for c in cases],
        "questions": {q: ANSWERS[q] for q in ANSWERS}, "definitions": DEFINITIONS,
        "files": {"verdicts_form.csv": _sha(form_bytes), "KEY_machine_predictions_open_only_after_the_verdicts.json": _sha(key_bytes),
                  "reading_sheet (local only, publisher text)": _sha(sheet_bytes)},
        "code": {"script": "scripts/study_phase3_repair.py", "extractor": "article_html/0.3.0", "rules": [Q.RULESET_3, enrichment.VERSION_2, R.VERSION_2]},
    }
    (out_dir / "manifest.json").write_bytes((json.dumps(manifest, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(json.dumps({"cases": len(cases), "random": RANDOM_SIZE, "targeted": len(cases) - RANDOM_SIZE, "questions": len(form),
                      "strata": {s["stratum"]: [s["population"], s["drawn"]] for s in strata_doc}}))
    return 0


def _sheet(cases, tops) -> str:
    e = _html.escape
    css = (":root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6b66;--line:#d9d6cf;--card:#fff;--accent:#2f5d8a}"
           "@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe6;--muted:#a3a29b;--line:#3a3935;--card:#1f1f1d;--accent:#8db6e0}}"
           "body{background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,sans-serif;margin:0 auto;max-width:980px;padding:16px}"
           "section{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:16px;margin:18px 0}"
           "h1{font-size:22px}h2{font-size:18px;margin:0 0 8px}h3{font-size:14px;margin:14px 0 4px;color:var(--accent)}"
           ".m{color:var(--muted);font-size:13px}.body{white-space:pre-wrap;max-height:420px;overflow:auto;border:1px solid var(--line);"
           "padding:8px;font-size:14px}ol,ul{margin:4px 0;padding-left:22px}code{font-size:13px}td{vertical-align:top;padding:2px 8px}"
           ".diff del{background:#f3c6c6;color:#000}.diff ins{background:#c6efc9;color:#000;text-decoration:none}")
    out = [f"<!doctype html><html lang=\"de\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
           f"<title>Blind control Phase 3</title><style>{css}</style></head><body>",
           "<h1>Blind control — Phase 3 (frozen 2026-11-15)</h1>",
           "<p>Each case shows evidence from the stored page, never the machine's answer. Enter your answers in "
           "<code>verdicts_form.csv</code> (one row per case and question). The address is the publisher's; the live page may differ "
           "from the stored one.</p>",
           "<h3>Answers</h3><table>" + "".join(f"<tr><td><code>{q}</code></td><td>{e(a)}</td></tr>" for q, a in ANSWERS.items()) + "</table>",
           "<h3>Definitions</h3><ul>" + "".join(f"<li><b>{e(k)}</b>: {e(v)}</li>" for k, v in DEFINITIONS.items()) + "</ul>",
           "<h3>IPTC Media Topics, top level</h3><p class=\"m\">" + " · ".join(f"<code>{c}</code> {e(l)}" for c, l in tops) + "</p>"]
    for c in cases:
        out.append(f"<section id=\"{c['case_id']}\"><h2>{c['case_id']}</h2>")
        if c["pair"]:
            out.append("<p class=\"m\">Question: <code>REUSE</code> — how do the BODY texts of these two documents relate?</p>")
            for n, d in enumerate(c["documents"], 1):
                out.append(f"<h3>Document {n}: {e(d['outlet'])} · {e(d['published'] or 'date not stated')}</h3>"
                           f"<p class=\"m\"><a href=\"{e(d['url'])}\">{e(d['url'])}</a></p><div class=\"body\">{e(d['body'])}</div>")
            diff = c["diff"]
            out.append(f"<h3>Word-level differences (document 1 → document 2): {diff['differing_segments']} segments, "
                       f"{diff['words_in_differing_segments']} words; sequence ratio {diff['word_sequence_ratio']}</h3><div class=\"diff\"><ul>")
            out += [f"<li>{d['op']}: <del>{e(d['this'])}</del> → <ins>{e(d['target'])}</ins></li>" for d in diff["first_differences"]]
            out.append("</ul></div></section>")
            continue
        out.append(f"<p class=\"m\">{e(c['outlet'])} · {e(c['country'])} · {e(c['published'] or 'date not stated')} · "
                   f"<a href=\"{e(c['url'])}\">{e(c['url'])}</a></p>")
        if "TITLE" in c["questions"]:
            out.append("<h3>TITLE — headline candidates</h3><ol type=\"A\">" + "".join(
                f"<li>{e(t['text'])} <span class=\"m\">({e(t['source'])})</span></li>" for _, t in c["title_candidates"]) + "</ol>")
            out.append("<h3>SUBTITLE — the blocks after each h1, in page order</h3><ol>" + "".join(
                f"<li value=\"{n}\">{e(t)}</li>" for n, t in c["window"]) + "</ol>")
            if c["stated_descriptions"]:
                out.append("<p class=\"m\">The page's description (metadata): " + " | ".join(e(d) for d in c["stated_descriptions"]) + "</p>")
        judged = "BODY_COMPLETE" in c["questions"]
        out.append(f"<h3>BODY — the extracted running text{'' if judged else ' (for context)'}</h3><div class=\"body\">"
                   f"{e(c['body']) or '<i>(no running text extracted)</i>'}</div>")
        if "IPTC" in c["questions"]:
            out.append("<h3>IPTC — the section the page publishes</h3><p>" + " | ".join(e(s) for s in c["sections"])
                       + (f" <span class=\"m\">(breadcrumb: {e(' › '.join(map(str, c['breadcrumb'])))})</span>" if c["breadcrumb"] else "") + "</p>")
        if "AI_TEXT" in c["questions"]:
            out.append("<h3>AI — every block of the page that mentions AI or machine production</h3><ul>"
                       + "".join(f"<li>{e(h)}</li>" for h in c["ai_hits"]) + "</ul>")
        if "AGENCY_ROLE" in c["questions"]:
            out.append("<h3>AGENCY — credits and mentions of news agencies on the page</h3><ul>"
                       + "".join(f"<li>{e(h)}</li>" for h in c["agency_hits"]) + "</ul>")
        out.append("<p class=\"m\">Questions: " + ", ".join(f"<code>{q}</code>" for q in c["questions"]) + "</p></section>")
    out.append("</body></html>")
    return "\n".join(out) + "\n"


# --- merge ---------------------------------------------------------------------------------------------------------------------


def _norm_answer(question, value):
    value = (value or "").strip().lower().replace(" ", "")
    if question in ("SUBTITLE", "IPTC", "AI_COMPONENT", "AGENCY_ROLE"):
        return ",".join(sorted(v for v in value.split(",") if v))
    return value


def _wilson(k, n):
    if not n:
        return None
    z, p = 1.959964, k / n
    centre, half = (p + z * z / (2 * n)) / (1 + z * z / n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(centre - half, 3), round(centre + half, 3)]


def merge(arguments) -> int:
    manifest = json.loads((arguments.out_dir / "manifest.json").read_text(encoding="utf-8"))
    key_path = arguments.out_dir / "KEY_machine_predictions_open_only_after_the_verdicts.json"
    if _sha(key_path.read_bytes()) != manifest["files"][key_path.name]:
        raise SystemExit("the key is not the frozen key")
    key = {c["case_id"]: c for c in json.loads(key_path.read_text(encoding="utf-8"))["cases"]}
    verdicts = list(csv.DictReader(arguments.verdicts.open(encoding="utf-8-sig")))
    missing = [v for v in verdicts if not v["answer"].strip()]
    table = defaultdict(Counter)
    details = []
    for v in verdicts:
        case = key[v["case_id"]]
        predicted = case["predictions"].get(v["question"])
        if v["question"].startswith("BODY_"):
            outcome = f"answer:{_norm_answer(v['question'], v['answer'])}"
        elif not v["answer"].strip():
            outcome = "no_answer"
        elif _norm_answer(v["question"], v["answer"]) == "unsure":
            outcome = "unsure"
        else:
            outcome = "agree" if _norm_answer(v["question"], v["answer"]) == _norm_answer(v["question"], predicted) else "disagree"
        table[(case["component"], v["question"])][outcome] += 1
        table[(case["stratum"], v["question"])][outcome] += 1
        if outcome == "disagree":
            details.append({"case_id": v["case_id"], "stratum": case["stratum"], "question": v["question"], "human": v["answer"],
                            "machine": predicted, "note": v["note"], "fetch_ids": case["fetch_ids"]})
    result = {"schema": "coprepan-phase3-blind-result/v1", "manifest_sha256": _sha((arguments.out_dir / "manifest.json").read_bytes()),
              "unanswered": len(missing),
              "by_component": {f"{c}|{q}": dict(t) | ({"agreement_wilson_95": _wilson(t["agree"], t["agree"] + t["disagree"])} if c == "random" else {})
                               for (c, q), t in sorted(table.items()) if c in ("random", "targeted")},
              "by_stratum": {f"{s}|{q}": dict(t) for (s, q), t in sorted(table.items()) if s not in ("random", "targeted")},
              "disagreements": details,
              "note": "random and targeted components are reported apart; only the random component speaks to the population, and "
                      "only coarsely; a targeted stratum's agreement is not a precision"}
    arguments.out.write_bytes((json.dumps(result, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(json.dumps({"unanswered": len(missing), "disagreements": len(details)}))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("derive", "draw"):
        command = sub.add_parser(name)
        source = command.add_mutually_exclusive_group(required=True)
        source.add_argument("--runtime", type=Path)
        source.add_argument("--page-cache", type=Path)
        if name == "derive":
            command.add_argument("--out", type=Path, required=True)
        else:
            command.add_argument("--rows", type=Path, required=True)
            command.add_argument("--out-dir", type=Path, required=True)
            command.add_argument("--sheet", type=Path, required=True)
    command = sub.add_parser("summarize")
    command.add_argument("--rows", type=Path, required=True)
    command.add_argument("--out", type=Path, required=True)
    command = sub.add_parser("merge")
    command.add_argument("--out-dir", type=Path, required=True)
    command.add_argument("--verdicts", type=Path, required=True)
    command.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args(argv)
    return {"derive": derive, "summarize": summarize, "draw": draw, "merge": merge}[arguments.command](arguments)


if __name__ == "__main__":
    sys.exit(main())
