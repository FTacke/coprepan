"""BODY quality study (CPD-0041): ``article_html/0.4.0`` against ``0.3.0`` on every stored 2xx item page, offline and read-only;
the template table; the contamination status; text reuse on both BODY versions; and the frozen human control.

Usage:
  python scripts/study_body_quality.py templates (--runtime <workspace> | --page-cache <pages.jsonl.gz>) --out <table.json>
                                                 [--review <local review .tsv>]
  python scripts/study_body_quality.py derive    (--runtime <workspace> | --page-cache <pages.jsonl.gz>) --out <rows.jsonl.gz>
                                                 [--templates <table.json>]
  python scripts/study_body_quality.py summarize --rows <rows.jsonl.gz> --out <study.json>
  python scripts/study_body_quality.py show      (--runtime <workspace> | --page-cache <pages.jsonl.gz>) --fetch <prefix> [--all]
  python scripts/study_body_quality.py draw      --rows <rows.jsonl.gz> (--runtime … | --page-cache …) --out-dir <evidence dir>
                                                 --sheet <local reading sheet .html>
  python scripts/study_body_quality.py merge     --out-dir <evidence dir> --verdicts <filled form .csv> --out <result.json>
                                                 [--sheet <local reading sheet .html>]
  python scripts/study_body_quality.py repair    (--runtime … | --page-cache …) --out <repairs.json> [--review <local .tsv>]
                                                 [--control-dir <evidence dir> --verdicts <filled form .csv>]

The page cache is ``study_phase3_metadata.py cache``'s (publisher bytes: local only, outside the repository, deleted after the
study). ``templates`` builds the pinned table from the BODY blocks of ``0.4.0`` *without* templates: a block is a template
when one outlet prints it in at least ``MIN_GROUPS`` unrelated articles (``MIN_GROUPS_RECURRING`` to 4: recurring, kept and
reported); articles that share more than ``SAME_STORY_JACCARD`` of their other 8-word shingles are one story and count once. The table holds digests only; ``--review`` writes the texts to a local file for reading. ``derive``
writes one row per page outside the repository (no body text but the changed blocks, verbatim, up to 300 characters).
"""

from __future__ import annotations

import argparse
import csv
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

from coprepan import body_quality as BQ, content_quality as Q, editorial_metadata as M, enrichment  # noqa: E402
from coprepan import extraction as E, extraction_article as A, extraction_body as B, provenance as P, text_reuse as R  # noqa: E402
import study_phase3_metadata as S3  # noqa: E402
import study_phase3_repair as P3  # noqa: E402

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")
MIN_GROUPS, MIN_GROUPS_RECURRING, SAME_STORY_JACCARD = 5, 3, 0.2


_LD = re.compile(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", re.S | re.I)


def _stated_body(html: str) -> str:
    """The page's JSON-LD ``articleBody`` texts, folded as the extractor folds block texts ('' when none)."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("articleBody"), str):
                found.append(node["articleBody"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for block in _LD.findall(html or ""):
        try:
            walk(json.loads(block.strip()))
        except ValueError:
            continue
    return A._norm(" ".join(found)) if found else ""


def _decoded(page, body):
    try:
        html, _ = E._decode(E.decode_content(body, page["args"]["content_encoding"] or "identity"), page["args"]["declared_charset"])
    except E.ContentDecodingError:
        html = ""
    return html


# --- templates ---------------------------------------------------------------------------------------------------------------


def templates(arguments) -> int:
    pages = []
    for page, body in S3.stored_pages(arguments):
        x = B.ARTICLE_4.function(body, body_sha256=page["body_sha256"], templates=frozenset(), **page["args"])
        blocks = [b for b in x.record["blocks"] if b["role"] == E.ROLE_BODY]
        pages.append({"outlet": page["outlet_id"], "fetch": page["fetch_id"], "body": x.body_text_sha256,
                      "blocks": [(B.template_digest(b["text"]), len(b["text"].split()), b["kind"], b["text"]) for b in blocks]})
    gram_cache: dict[str, dict[str, set[int]]] = {}

    def grams_of(p):
        if p["fetch"] not in gram_cache:
            gram_cache[p["fetch"]] = {d: R.shingles(R.words(text)) for d, _, _, text in p["blocks"]}
        return gram_cache[p["fetch"]]
    by_outlet = defaultdict(list)
    for p in pages:
        by_outlet[p["outlet"]].append(p)
    digests, recurring, review, stats = {}, {}, [], Counter()
    for outlet, ps in sorted(by_outlet.items()):
        where = defaultdict(dict)                        # digest -> {body digest: page}
        info = {}
        for p in ps:
            for d, words, kind, text in p["blocks"]:
                where[d].setdefault(p["body"], p)
                info[d] = (words, kind, text)
        for d, bodies in where.items():
            if len(bodies) < MIN_GROUPS_RECURRING:
                continue
            words, kind, text = info[d]
            members = list(bodies.values())
            rest = [set().union(*(g for dd, g in grams_of(m).items() if dd != d)) for m in members]
            parent = list(range(len(members)))

            def root(i):
                while parent[i] != i:
                    i = parent[i]
                return i

            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    a, b = rest[i], rest[j]
                    if a and b and len(a & b) / len(a | b) > SAME_STORY_JACCARD:
                        parent[root(j)] = root(i)
            groups = len({root(i) for i in range(len(members))})
            decision = groups >= MIN_GROUPS
            stats[f"{'short' if words < 12 else 'long'}|{'template' if decision else ('recurring' if groups >= MIN_GROUPS_RECURRING else 'one_story')}"] += 1
            review.append((outlet, groups, len(bodies), words, kind, "template" if decision else "kept", text[:300]))
            if decision:
                digests[d] = max(digests.get(d, 0), groups)
            elif groups >= MIN_GROUPS_RECURRING:
                recurring[d] = max(recurring.get(d, 0), groups)
    table = {"schema": B.TEMPLATES_SCHEMA, "rule": B.TEMPLATE_RULE,
             "built_from": {"population": "the stored 2xx item pages of the CPD-0039/0040/0041 study", "pages": len(pages),
                            "outlets": len(by_outlet), "extractor": "article_html/0.4.0 without templates", "date": "2026-11-15"},
             "parameters": {"min_unrelated_articles": MIN_GROUPS, "min_unrelated_articles_recurring": MIN_GROUPS_RECURRING,
                            "same_story_jaccard": SAME_STORY_JACCARD, "digest": "sha256 of the NFC, invisible-free, white-space-folded, "
                                                                                 "lower-cased block text, first 24 hex"},
             "candidates": dict(stats), "digests": sorted(digests),
             "recurring_kept": sorted(set(recurring) - set(digests)),
             "note": "digests: removed from the BODY by article_html/0.4.0 (outlet_template): one outlet prints the block in at least "
                     "5 unrelated articles. recurring_kept: in 3-4 unrelated articles -- not removed (a recipe heading, a poll's "
                     "technical sheet, a background paragraph can recur that often), reported by body-quality/1 as residual_suspect"}
    arguments.out.write_bytes((json.dumps(table, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    if arguments.review:
        with arguments.review.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("outlet\tgroups\tbodies\twords\tkind\tdecision\ttext\n")
            for row in sorted(review, key=lambda r: (r[5], -r[1])):
                handle.write("\t".join(str(v).replace("\t", " ").replace("\n", " ") for v in row) + "\n")
    print(json.dumps({"pages": len(pages), "templates": len(digests), "candidates": dict(stats)}))
    return 0


# --- derive ------------------------------------------------------------------------------------------------------------------


def _view(x):
    blocks = x.record["blocks"]
    return {"outcome": x.outcome, "body": x.body_text_sha256, "extracted": x.extracted_text_sha256,
            "body_words": len(x.body_text.split()), "body_blocks": sum(1 for b in blocks if b["role"] == E.ROLE_BODY),
            "title": next((b["text"] for b in blocks if b["kind"] == "title"), None),
            "subtitles": [b["text"][:200] for b in blocks if b["kind"] == E.KIND_SUBTITLE]}


def derive(arguments) -> int:
    table = B.body_templates() if arguments.templates is None else frozenset(json.loads(arguments.templates.read_text(encoding="utf-8"))["digests"])
    registry = json.loads((REPOSITORY / "config" / "outlet_registry.json").read_text(encoding="utf-8"))
    country = {o["outlet_id"]: o["country_id"] for o in registry["outlets"]}
    section_map = M.load_section_map()
    rows, bodies3, bodies4, records = [], [], [], {}
    timing = Counter()
    for page, body in S3.stored_pages(arguments):
        t = time.perf_counter()
        three = A.ARTICLE_3.run(body, body_sha256=page["body_sha256"], **page["args"])
        timing["extract_0_3_0"] += time.perf_counter() - t
        t = time.perf_counter()
        four = B.ARTICLE_4.function(body, body_sha256=page["body_sha256"], templates=table, **page["args"])
        problems = E.record_problems(four.record, E.EXTRACTION_SCHEMA_3)
        timing["extract_0_4_0"] += time.perf_counter() - t
        html = _decoded(page, body)
        f3 = Q.features(three.record, http_status=page["status"], html=html) if three.outcome == E.OUTCOME_EXTRACTED else None
        f4 = Q.features(four.record, http_status=page["status"], html=html) if four.outcome == E.OUTCOME_EXTRACTED else None
        t = time.perf_counter()
        status = BQ.assess(four.record, html=html) if four.outcome == E.OUTCOME_EXTRACTED else None
        timing["body_quality"] += time.perf_counter() - t
        common = dict(html=html, url=page["url"], outlet_id=page["outlet_id"], country_id=country.get(page["outlet_id"], "unknown"),
                      section_map=section_map)
        m3 = enrichment.derive(record=three.record, version=enrichment.VERSION_2, **common)
        m4 = enrichment.derive(record=four.record, version=enrichment.VERSION_3, **common)
        if P.ai_statements(three.record) or P.ai_statements(four.record):
            records[page["fetch_id"]] = (three.record, four.record)
        published = four.record["metadata"]["publication_date"]["value"]
        published = published[:19] if DATE.match(published or "") else None
        for target, x in ((bodies3, three), (bodies4, four)):
            if x.outcome == E.OUTCOME_EXTRACTED:
                target.append({"document_id": page["fetch_id"], "outlet_id": page["outlet_id"], "body_text": x.body_text,
                               "published": published, "fetched_at": page["fetched_at"]})
        # the publisher's own statement of the article body, where there is one: an excluded block it contains (and the kept
        # BODY does not repeat), an included block it contains -- evidence, not gold (a page puts promotions into it too)
        stated = _stated_body(html)
        kept = {A._norm(b["text"]) for b in four.record["blocks"] if b["role"] == E.ROLE_BODY}
        changed = [{"index": b["index"], "kind": b["kind"], **b["selection"], "words": len(b["text"].split()), "text": b["text"][:300],
                    "in_stated_body": (len(A._norm(b["text"])) >= 30 and A._norm(b["text"]) in stated
                                       and (b["selection"]["decision"] == E.SELECTION_INCLUDED or A._norm(b["text"]) not in kept))
                    if stated else None}
                   for b in four.record["blocks"] if b.get("selection")]
        rows.append({"fetch_id": page["fetch_id"], "outlet_id": page["outlet_id"], "country_id": country.get(page["outlet_id"], "unknown"),
                     "url": page["url"], "status": page["status"], "fetched_at": page["fetched_at"], "published": published,
                     "v3": _view(three), "v4": _view(four), "schema_problems": problems, "selection": changed,
                     "before_selection_equals_0_3_0_body": B.body_before_selection(four.record) == three.body_text,
                     "features_v3": f3, "features_v4": f4, "body_quality": status,
                     "layers_3": m3["layers"], "layers_4": m4["layers"]})
    site3 = P.site_wide_statements([{"outlet_id": r["outlet_id"], "statements": P.ai_statements(records[r["fetch_id"]][0])}
                                    for r in rows if r["fetch_id"] in records] + [{"outlet_id": r["outlet_id"], "statements": []}
                                                                                  for r in rows if r["fetch_id"] not in records])
    site4 = P.site_wide_statements([{"outlet_id": r["outlet_id"], "statements": P.ai_statements(records[r["fetch_id"]][1])}
                                    for r in rows if r["fetch_id"] in records] + [{"outlet_id": r["outlet_id"], "statements": []}
                                                                                  for r in rows if r["fetch_id"] not in records])
    for r in rows:
        if r["fetch_id"] in records:
            three, four = records[r["fetch_id"]]
            if site3.get(r["outlet_id"]):
                r["layers_3"][P.LAYER_AI] = P.ai_disclosure(three, site_wide=site3[r["outlet_id"]])
            if site4.get(r["outlet_id"]):
                r["layers_4"][P.LAYER_AI] = P.ai_disclosure(four, site_wide=site4[r["outlet_id"]])
    t = time.perf_counter()
    reuse3 = R.relations(bodies3, version=R.VERSION_2)
    reuse4 = R.relations(bodies4, version=R.VERSION_2)
    timing["text_reuse_both"] = time.perf_counter() - t
    by3, by4 = defaultdict(list), defaultdict(list)
    for x in reuse3:
        by3[x["document_id"]].append(x)
    for x in reuse4:
        by4[x["document_id"]].append(x)
    with gzip.open(arguments.out, "wt", encoding="utf-8") as out:
        for r in rows:
            r["relations_3"], r["relations_4"] = by3.get(r["fetch_id"], []), by4.get(r["fetch_id"], [])
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
        out.write(json.dumps({"_meta": {"pages": len(rows), "seconds": {k: round(v, 1) for k, v in timing.items()},
                                        "templates": len(table), "relations": [len(reuse3), len(reuse4)]}}) + "\n")
    print(json.dumps({"pages": len(rows), "relations": [len(reuse3), len(reuse4)], "seconds": {k: round(v, 1) for k, v in timing.items()}}))
    return 0


# --- show ----------------------------------------------------------------------------------------------------------------------


def show(arguments) -> int:
    for page, body in S3.stored_pages(arguments):
        if not page["fetch_id"][4:].startswith(arguments.fetch):
            continue
        four = B.ARTICLE_4.run(body, body_sha256=page["body_sha256"], **page["args"])
        print(f"== {page['outlet_id']} {page['url']}")
        for block in four.record["blocks"]:
            if block["role"] == E.ROLE_BODY or block.get("selection") or arguments.all:
                mark = (block.get("selection") or {}).get("reason", "")
                print(f"[{block['index']:3} {block['role'][:5]:5} {block['kind'][:9]:9} {mark[:22]:22}] {block['text'][:arguments.chars]}")
        print(json.dumps(BQ.assess(four.record, html=_decoded(page, body)), ensure_ascii=False))
        return 0
    print("not found")
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("templates", "derive", "show", "draw", "repair"):
        command = sub.add_parser(name)
        source = command.add_mutually_exclusive_group(required=True)
        source.add_argument("--runtime", type=Path)
        source.add_argument("--page-cache", type=Path)
        if name in ("templates", "repair"):
            command.add_argument("--out", type=Path, required=True)
            command.add_argument("--review", type=Path)
            if name == "repair":
                command.add_argument("--control-dir", type=Path, help="the frozen control, to score the candidate on it (not blind)")
                command.add_argument("--verdicts", type=Path, help="the filled form of the control")
        elif name == "derive":
            command.add_argument("--out", type=Path, required=True)
            command.add_argument("--templates", type=Path)
        elif name == "show":
            command.add_argument("--fetch", required=True)
            command.add_argument("--chars", type=int, default=150)
            command.add_argument("--all", action="store_true")
        else:
            command.add_argument("--rows", type=Path, required=True)
            command.add_argument("--out-dir", type=Path, required=True)
            command.add_argument("--sheet", type=Path, required=True)
    command = sub.add_parser("compare")
    source = command.add_mutually_exclusive_group(required=True)
    source.add_argument("--runtime", type=Path)
    source.add_argument("--page-cache", type=Path)
    command.add_argument("--old", choices=sorted(EXTRACTORS), required=True)
    command.add_argument("--new", choices=sorted(EXTRACTORS), required=True)
    command.add_argument("--date", required=True, help="the run date, recorded in the result")
    command.add_argument("--out", type=Path, required=True)
    command.add_argument("--review", type=Path)
    command.add_argument("--control-dir", type=Path, help="the frozen control, to score the new version on it (not blind)")
    command.add_argument("--verdicts", type=Path, help="the filled form of the control")
    command = sub.add_parser("summarize")
    command.add_argument("--rows", type=Path, required=True)
    command.add_argument("--out", type=Path, required=True)
    command = sub.add_parser("merge")
    command.add_argument("--out-dir", type=Path, required=True)
    command.add_argument("--verdicts", type=Path, required=True)
    command.add_argument("--out", type=Path, required=True)
    command.add_argument("--sheet", type=Path, help="the local reading sheet, for word counts (numbers only reach the result)")
    arguments = parser.parse_args(argv)
    return {"templates": templates, "derive": derive, "summarize": summarize, "show": show, "draw": draw,
            "merge": merge, "repair": repair, "compare": compare}[arguments.command](arguments)


# --- the repairs of the BODY control (CPD-0042) ------------------------------------------------------------------------------


def repair(arguments) -> int:
    """``article_html/0.4.1`` against ``0.4.0``, ``content-quality/4`` against ``/3`` (each change apart and together),
    ``body-quality/2`` against ``/1``, the metadata layers and text reuse where the BODY changed -- on every stored page. The
    result holds numbers, outlets and fetch-id prefixes; ``--review`` writes the changed pages with their text, locally."""
    registry = json.loads((REPOSITORY / "config" / "outlet_registry.json").read_text(encoding="utf-8"))
    country = {o["outlet_id"]: o["country_id"] for o in registry["outlets"]}
    section_map = M.load_section_map()
    rows, bodies = [], {"0_4_0": [], "0_4_1": []}
    timing = Counter()
    for page, body in S3.stored_pages(arguments):
        four = B.ARTICLE_4.run(body, body_sha256=page["body_sha256"], **page["args"])
        t = time.perf_counter()
        new = B.ARTICLE_4_1.run(body, body_sha256=page["body_sha256"], **page["args"])
        timing["extract_0_4_1"] += time.perf_counter() - t
        html = _decoded(page, body)
        ok = four.outcome == E.OUTCOME_EXTRACTED
        f4 = Q.features(four.record, http_status=page["status"], html=html) if ok else None
        f41 = Q.features(new.record, http_status=page["status"], html=html) if new.outcome == E.OUTCOME_EXTRACTED else None
        row = {"fetch_id": page["fetch_id"], "outlet_id": page["outlet_id"], "url": page["url"], "fetched_at": page["fetched_at"],
               "f4": f4, "f41": f41, "body_changed": four.body_text_sha256 != new.body_text_sha256,
               "bq1": BQ.assess(four.record, html=html)["state"] if ok else None,
               "bq2": BQ.assess(new.record, html=html, version=BQ.VERSION_2)["state"] if ok else None}
        if row["body_changed"]:
            b4 = {b["index"] for b in four.record["blocks"] if b["role"] == E.ROLE_BODY}
            b41 = {b["index"] for b in new.record["blocks"] if b["role"] == E.ROLE_BODY}
            gone = [b for b in four.record["blocks"] if b["index"] in b4 - b41]
            row["gone"] = [{"index": b["index"], "reason": (b.get("selection") or {}).get("reason"), "words": len(b["text"].split()),
                            "text": b["text"][:300]} for b in gone]
            row["added"] = [{"index": b["index"], "reason": (b.get("selection") or {}).get("reason"), "words": len(b["text"].split()),
                             "text": b["text"][:300]} for b in new.record["blocks"] if b["index"] in b41 - b4]
            common = dict(html=html, url=page["url"], outlet_id=page["outlet_id"], country_id=country.get(page["outlet_id"], "unknown"),
                          section_map=section_map)
            l4 = enrichment.derive(record=four.record, version=enrichment.VERSION_3, **common)["layers"]
            l41 = enrichment.derive(record=new.record, version=enrichment.VERSION_3, **common)["layers"]
            row["layers_changed"] = sorted(n for n in l4 if (l4[n]["value"], l4[n]["value_state"]) != (l41[n]["value"], l41[n]["value_state"]))
        if f4 and f4["declares_live_blog"]:
            row["title"] = (f4["title_text"] or "")[:160]
        published = new.record["metadata"]["publication_date"]["value"]
        published = published[:19] if DATE.match(published or "") else None
        for key, x in (("0_4_0", four), ("0_4_1", new)):
            if x.outcome == E.OUTCOME_EXTRACTED:
                bodies[key].append({"document_id": page["fetch_id"], "outlet_id": page["outlet_id"], "body_text": x.body_text,
                                    "published": published, "fetched_at": page["fetched_at"]})
        rows.append(row)

    def decide(key, ruleset):
        return Q.assess_corpus([{"fetch_id": r["fetch_id"], "outlet_id": r["outlet_id"], "url": r["url"], "fetched_at": r["fetched_at"] or "",
                                 "features": r[key], "extracted": r[key] is not None} for r in rows], ruleset=ruleset)

    runs = {"3_on_0_4_0": decide("f4", Q.RULESET_3), "4_on_0_4_0": decide("f4", Q.RULESET_4), "3_on_0_4_1": decide("f41", Q.RULESET_3),
            "4_on_0_4_1": decide("f41", Q.RULESET_4)}
    base, cand = runs["3_on_0_4_0"], runs["4_on_0_4_1"]
    t = time.perf_counter()
    reuse = {k: R.relations(v, version=R.VERSION_2) for k, v in bodies.items()}
    timing["text_reuse_both"] = time.perf_counter() - t
    pairs = {k: {(x["document_id"], x["target_document_id"]) for x in v} for k, v in reuse.items()}
    flips = [r for r in rows if base[r["fetch_id"]]["decision"] != cand[r["fetch_id"]]["decision"]]

    def cause(r):
        fid = r["fetch_id"]
        out = []
        if runs["3_on_0_4_1"][fid]["decision"] != base[fid]["decision"]:
            out.append("extractor_0_4_1")
        if runs["4_on_0_4_0"][fid]["decision"] != base[fid]["decision"]:
            out.append("gate_4")
        return "+".join(out) or "both_together"

    live = [r for r in rows if r["f4"] and r["f4"]["declares_live_blog"]]
    markup = [r for r in rows if r["f4"] and (r["f4"]["stated_body_characters"] or 0) != (r["f4"]["stated_body_text_characters"] or 0)]
    out = {
        "schema": "coprepan-body-control-repairs/v1", "decision": "CPD-0042", "date": "2026-11-15",
        "population": {"pages": len(rows), "extracted": sum(1 for r in rows if r["f4"])},
        "versions": {"extractor": ["article_html/0.4.0", "article_html/0.4.1"], "quality": [Q.RULESET_3, Q.RULESET_4],
                     "features": Q.FEATURES_VERSION, "body_quality": [BQ.VERSION, BQ.VERSION_2], "metadata": enrichment.VERSION_3,
                     "text_reuse": R.VERSION_2, "templates_sha256": B.body_templates_sha256()},
        "extractor_0_4_1": {
            "body_changed": sum(1 for r in rows if r["body_changed"]),
            "blocks_left_out": sum(len(r.get("gone", [])) for r in rows), "blocks_added": sum(len(r.get("added", [])) for r in rows),
            "words_left_out": sum(b["words"] for r in rows for b in r.get("gone", [])),
            "words_added": sum(b["words"] for r in rows for b in r.get("added", [])),
            "left_out_by_former_reason": dict(Counter(b["reason"] for r in rows for b in r.get("gone", []))),
            "added_by_reason": dict(Counter(b["reason"] for r in rows for b in r.get("added", []))),
            "pages_left_out": sum(1 for r in rows if r.get("gone")), "pages_added": sum(1 for r in rows if r.get("added")),
            "by_outlet": dict(Counter(r["outlet_id"] for r in rows if r["body_changed"]).most_common()),
            "pages_with_a_layer_changed": sum(1 for r in rows if r.get("layers_changed")),
            "layers_changed": dict(Counter(n for r in rows for n in r.get("layers_changed", []))),
            "fetch_prefixes": sorted(r["fetch_id"][4:14] for r in rows if r["body_changed"])},
        "core": {
            "accepted": {k: sum(1 for d in v.values() if d["decision"] == Q.ACCEPT) for k, v in runs.items()},
            "flips_3_on_0_4_0_to_4_on_0_4_1": {
                "accepted_to_rejected": sum(1 for r in flips if cand[r["fetch_id"]]["decision"] == Q.REJECT),
                "rejected_to_accepted": sum(1 for r in flips if cand[r["fetch_id"]]["decision"] == Q.ACCEPT),
                "by_cause": dict(Counter(cause(r) for r in flips)),
                "pages": [{"fetch": r["fetch_id"][4:14], "outlet": r["outlet_id"], "from": base[r["fetch_id"]]["reasons"],
                           "to": cand[r["fetch_id"]]["reasons"], "cause": cause(r)} for r in flips]}},
        "live_blog_declared": {
            "pages": len(live), "by_outlet": dict(Counter(r["outlet_id"] for r in live).most_common()),
            "accepted_by_3_on_0_4_0": sum(1 for r in live if base[r["fetch_id"]]["decision"] == Q.ACCEPT),
            "already_live_coverage_under_3": sum(1 for r in live if "live_coverage" in base[r["fetch_id"]]["reasons"])},
        "stated_body_markup": {
            "pages_whose_stated_body_carries_markup": len(markup), "by_outlet": dict(Counter(r["outlet_id"] for r in markup).most_common()),
            "incomplete_under_3_on_0_4_0": sum(1 for r in markup if "incomplete_against_stated_body" in base[r["fetch_id"]]["reasons"]),
            "incomplete_under_4_on_0_4_1": sum(1 for r in markup if "incomplete_against_stated_body" in cand[r["fetch_id"]]["reasons"])},
        "body_quality": {"states_1_on_0_4_0": dict(Counter(r["bq1"] for r in rows if r["bq1"])),
                         "states_2_on_0_4_1": dict(Counter(r["bq2"] for r in rows if r["bq2"])),
                         "transitions": dict(Counter(f"{r['bq1']}->{r['bq2']}" for r in rows if r["bq1"] != r["bq2"]))},
        "text_reuse": {"relations": {k: len(v) for k, v in reuse.items()}, "kept": len(pairs["0_4_0"] & pairs["0_4_1"]),
                       "lost": len(pairs["0_4_0"] - pairs["0_4_1"]), "new": len(pairs["0_4_1"] - pairs["0_4_0"])},
        "cost": {"seconds": {k: round(v, 1) for k, v in timing.items()},
                 "ms_per_page_extract_0_4_1": round(1000 * timing["extract_0_4_1"] / max(1, len(rows)), 2)},
    }
    if arguments.control_dir is not None:
        out["control_rescored"] = _rescore_control(arguments, cand, {r["fetch_id"]: r for r in rows})
    arguments.out.write_bytes((json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    if arguments.review:
        with arguments.review.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("kind\tfetch\toutlet\turl\tdetail\n")
            for r in rows:
                for b in r.get("gone", []):
                    handle.write(f"gone\t{r['fetch_id'][4:14]}\t{r['outlet_id']}\t{r['url']}\t[{b['reason']}] {b['text']}\n".replace("\r", " "))
                for b in r.get("added", []):
                    handle.write(f"added\t{r['fetch_id'][4:14]}\t{r['outlet_id']}\t{r['url']}\t[{b['reason']}] {b['text']}\n".replace("\r", " "))
            for r in live:
                handle.write(f"live\t{r['fetch_id'][4:14]}\t{r['outlet_id']}\t{r['url']}\t{base[r['fetch_id']]['decision']} "
                             f"{base[r['fetch_id']]['reasons']} | {r.get('title', '')}\n")
            for r in flips:
                handle.write(f"flip\t{r['fetch_id'][4:14]}\t{r['outlet_id']}\t{r['url']}\t{base[r['fetch_id']]['reasons']} -> "
                             f"{cand[r['fetch_id']]['reasons']} ({cause(r)})\n")
    print(json.dumps({k: out[k] for k in ("extractor_0_4_1", "core", "live_blog_declared", "stated_body_markup")}, ensure_ascii=False)[:1500])
    return 0


EXTRACTORS = {"0.4.0": B.ARTICLE_4, "0.4.1": B.ARTICLE_4_1, "0.4.2": B.ARTICLE_4_2}


def compare(arguments) -> int:
    """Two ``article_html`` versions on every stored page under ``content-quality/4`` and ``body-quality/2``: the BODY changes
    block by block, CORE flips, body-quality transitions, the metadata layers where the BODY changed and text reuse. The result
    holds numbers, outlets and fetch-id prefixes; ``--review`` writes the changed blocks with their text, locally."""
    old_x, new_x = EXTRACTORS[arguments.old], EXTRACTORS[arguments.new]
    registry = json.loads((REPOSITORY / "config" / "outlet_registry.json").read_text(encoding="utf-8"))
    country = {o["outlet_id"]: o["country_id"] for o in registry["outlets"]}
    section_map = M.load_section_map()
    rows, bodies, timing = [], {"old": [], "new": []}, Counter()
    for page, body in S3.stored_pages(arguments):
        old = old_x.run(body, body_sha256=page["body_sha256"], **page["args"])
        t = time.perf_counter()
        new = new_x.run(body, body_sha256=page["body_sha256"], **page["args"])
        timing["extract_new"] += time.perf_counter() - t
        html = _decoded(page, body)
        ok = old.outcome == E.OUTCOME_EXTRACTED and new.outcome == E.OUTCOME_EXTRACTED
        row = {"fetch_id": page["fetch_id"], "outlet_id": page["outlet_id"], "url": page["url"], "fetched_at": page["fetched_at"],
               "f_old": Q.features(old.record, http_status=page["status"], html=html) if ok else None,
               "f_new": Q.features(new.record, http_status=page["status"], html=html) if ok else None,
               "body_changed": old.body_text_sha256 != new.body_text_sha256,
               "bq_old": BQ.assess(old.record, html=html, version=BQ.VERSION_2)["state"] if ok else None,
               "bq_new": BQ.assess(new.record, html=html, version=BQ.VERSION_2)["state"] if ok else None}
        if row["body_changed"]:
            b_old = {b["index"] for b in old.record["blocks"] if b["role"] == E.ROLE_BODY}
            b_new = {b["index"] for b in new.record["blocks"] if b["role"] == E.ROLE_BODY}
            row["gone"] = [{"index": b["index"], "kind": b["kind"], "reason": (b.get("selection") or {}).get("reason"),
                            "words": len(b["text"].split()), "text": b["text"][:300]}
                           for b in new.record["blocks"] if b["index"] in b_old - b_new]
            row["added"] = [{"index": b["index"], "kind": b["kind"], "reason": (b.get("selection") or {}).get("reason"),
                             "words": len(b["text"].split()), "text": b["text"][:300]}
                            for b in new.record["blocks"] if b["index"] in b_new - b_old]
            common = dict(html=html, url=page["url"], outlet_id=page["outlet_id"], country_id=country.get(page["outlet_id"], "unknown"),
                          section_map=section_map)
            l_old = enrichment.derive(record=old.record, version=enrichment.VERSION_3, **common)["layers"]
            l_new = enrichment.derive(record=new.record, version=enrichment.VERSION_3, **common)["layers"]
            row["layers_changed"] = sorted(n for n in l_old if (l_old[n]["value"], l_old[n]["value_state"])
                                           != (l_new[n]["value"], l_new[n]["value_state"]))
        published = new.record["metadata"]["publication_date"]["value"]
        published = published[:19] if DATE.match(published or "") else None
        for key, x in (("old", old), ("new", new)):
            if x.outcome == E.OUTCOME_EXTRACTED:
                bodies[key].append({"document_id": page["fetch_id"], "outlet_id": page["outlet_id"], "body_text": x.body_text,
                                    "published": published, "fetched_at": page["fetched_at"]})
        rows.append(row)

    def decide(key):
        return Q.assess_corpus([{"fetch_id": r["fetch_id"], "outlet_id": r["outlet_id"], "url": r["url"], "fetched_at": r["fetched_at"] or "",
                                 "features": r[key], "extracted": r[key] is not None} for r in rows], ruleset=Q.RULESET_4)

    d_old, d_new = decide("f_old"), decide("f_new")
    flips = [r for r in rows if d_old[r["fetch_id"]]["decision"] != d_new[r["fetch_id"]]["decision"]]
    reuse = {k: R.relations(v, version=R.VERSION_2) for k, v in bodies.items()}
    pairs = {k: {(x["document_id"], x["target_document_id"]) for x in v} for k, v in reuse.items()}
    changed = [r for r in rows if r["body_changed"]]
    out = {
        "schema": "coprepan-body-extractor-comparison/v1", "date": arguments.date,
        "versions": {"old": f"article_html/{arguments.old}", "new": f"article_html/{arguments.new}", "quality": Q.RULESET_4,
                     "features": Q.FEATURES_VERSION, "body_quality": BQ.VERSION_2, "metadata": enrichment.VERSION_3,
                     "text_reuse": R.VERSION_2, "templates_sha256": B.body_templates_sha256()},
        "population": {"pages": len(rows), "extracted": sum(1 for r in rows if r["f_new"])},
        "body": {"changed": len(changed), "pages_with_blocks_added": sum(1 for r in changed if r["added"]),
                 "pages_with_blocks_gone": sum(1 for r in changed if r["gone"]),
                 "blocks_added": sum(len(r["added"]) for r in changed), "blocks_gone": sum(len(r["gone"]) for r in changed),
                 "words_added": sum(b["words"] for r in changed for b in r["added"]),
                 "words_gone": sum(b["words"] for r in changed for b in r["gone"]),
                 "added_by_reason_and_kind": dict(Counter(f"{b['reason']}|{b['kind']}" for r in changed for b in r["added"])),
                 "gone_by_reason_and_kind": dict(Counter(f"{b['reason']}|{b['kind']}" for r in changed for b in r["gone"])),
                 "by_outlet": dict(Counter(r["outlet_id"] for r in changed).most_common()),
                 "pages_with_a_layer_changed": sum(1 for r in changed if r["layers_changed"]),
                 "layers_changed": dict(Counter(n for r in changed for n in r["layers_changed"])),
                 "fetch_prefixes": sorted(r["fetch_id"][4:14] for r in changed)},
        "core": {"accepted": {"old": sum(1 for d in d_old.values() if d["decision"] == Q.ACCEPT),
                              "new": sum(1 for d in d_new.values() if d["decision"] == Q.ACCEPT)},
                 "flips": [{"fetch": r["fetch_id"][4:14], "outlet": r["outlet_id"], "from": d_old[r["fetch_id"]]["reasons"],
                            "to": d_new[r["fetch_id"]]["reasons"],
                            "words": [(r["f_old"] or {}).get("words"), (r["f_new"] or {}).get("words")]} for r in flips]},
        "body_quality": {"transitions": dict(Counter(f"{r['bq_old']}->{r['bq_new']}" for r in rows if r["bq_old"] != r["bq_new"]))},
        "text_reuse": {"relations": {k: len(v) for k, v in reuse.items()}, "kept": len(pairs["old"] & pairs["new"]),
                       "lost": len(pairs["old"] - pairs["new"]), "new": len(pairs["new"] - pairs["old"])},
        "cost": {"ms_per_page_extract_new": round(1000 * timing["extract_new"] / max(1, len(rows)), 2)},
    }
    if arguments.control_dir is not None:
        out["control_rescored"] = _rescore_control(arguments, d_new, {r["fetch_id"]: r for r in rows}, extractor=new_x,
                                                   state_key="bq_new", label=arguments.new.replace(".", "_"))
    arguments.out.write_bytes((json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    if arguments.review:
        with arguments.review.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("kind\tfetch\toutlet\turl\tdetail\n")
            for r in changed:
                for tag in ("gone", "added"):
                    for b in r[tag]:
                        handle.write(f"{tag}\t{r['fetch_id'][4:14]}\t{r['outlet_id']}\t{r['url']}\t[{b['reason']}|{b['kind']}|{b['words']}] "
                                     f"{b['text']}\n".replace("\r", " "))
            for r in flips:
                handle.write(f"flip\t{r['fetch_id'][4:14]}\t{r['outlet_id']}\t{r['url']}\t{d_old[r['fetch_id']]['reasons']} -> "
                             f"{d_new[r['fetch_id']]['reasons']}\n")
    print(json.dumps({k: out[k] for k in ("body", "core", "body_quality", "text_reuse")}, ensure_ascii=False)[:2500])
    return 0


def _rescore_control(arguments, decisions, rows_by_id, extractor=None, state_key="bq2", label="0_4_1"):
    """The candidate (0.4.1 unless ``extractor``, content-quality/4, body-quality/2) on the 45 control cases, in the sheet's
    numbering, scored with the filled form like the frozen key. NOT blind: the repairs were written after the key was opened
    (CPD-0042)."""
    extractor = extractor or B.ARTICLE_4_1
    manifest = json.loads((arguments.control_dir / "manifest.json").read_text(encoding="utf-8"))
    key_path = arguments.control_dir / "KEY_machine_predictions_open_only_after_the_verdicts.json"
    if P3._sha(key_path.read_bytes()) != manifest["files"][key_path.name]:
        raise SystemExit("the key is not the frozen key")
    frozen = {c["case_id"]: c for c in json.loads(key_path.read_text(encoding="utf-8"))["cases"]}
    by_fetch = {c["fetch_id"]: c["case_id"] for c in manifest["cases"]}
    key, outside = {}, {}
    for page, body in S3.stored_pages(arguments):
        cid = by_fetch.get(page["fetch_id"])
        if cid is None:
            continue
        three = A.ARTICLE_3.run(body, body_sha256=page["body_sha256"], **page["args"])
        four = B.ARTICLE_4.run(body, body_sha256=page["body_sha256"], **page["args"])
        new = extractor.run(body, body_sha256=page["body_sha256"], **page["args"])
        union, _, _ = _union_blocks(three, four)
        b41 = {b["index"] for b in new.record["blocks"] if b["role"] == E.ROLE_BODY}
        shown = {i for _, i, _ in union}
        if b41 - shown:              # a block neither 0.3.0 nor 0.4.0 has: the sheet cannot show it; judged against MISSING
            outside[cid] = [{"block_index": b["index"], "reason": (b.get("selection") or {}).get("reason"),
                             "words": len(b["text"].split())} for b in new.record["blocks"] if b["index"] in b41 - shown]
        state = rows_by_id[page["fetch_id"]][state_key]
        key[cid] = {**frozen[cid], f"predictions_{label}": {
            "FOREIGN": ",".join(str(n) for n, i, _ in union if i not in b41) or "0",
            "MISSING": {"not_article": "not_an_article", "incomplete": "middle_missing"}.get(state, "complete"),
            "CORE": "yes" if decisions[page["fetch_id"]]["decision"] == Q.ACCEPT else "no"}}
    verdicts = list(csv.DictReader(arguments.verdicts.open(encoding="utf-8-sig")))
    gold, every = {}, {}
    for v in verdicts:
        answer = v["answer"].strip().lower()
        if answer and v.get("basis") != "UNRESOLVED":
            every[(v["case_id"], v["question"])] = (answer, set())
        operator, opened = (v.get("operator_answer") or "").strip().lower(), _set(v.get("operator_open") or "")
        if v["question"] == "FOREIGN" and (operator or opened):
            gold[(v["case_id"], v["question"])] = (operator or "0", opened)
        elif operator and v["question"] != "FOREIGN":
            gold[(v["case_id"], v["question"])] = (operator, set())
    versions = (label, "0_4_0")
    gold_table, _ = _score(key, gold, versions=versions)
    every_table, cases = _score(key, every, versions=versions)
    return {"not_blind": "the repairs were written after the key was opened; these counts check the repairs, they do not "
                         "validate them", "verdicts_sha256": P3._sha(arguments.verdicts.read_bytes()),
            "operator_confirmed_only": gold_table, "all_answers": every_table,
            "blocks_outside_the_sheet": {c: {"blocks": v, "missing_label": next((x["answer"] for x in verdicts if x["case_id"] == c
                                                                                  and x["question"] == "MISSING"), None)}
                                         for c, v in sorted(outside.items())},
            "cases": {c: d for c, d in cases.items() if len(d) > 2}}


def _decisions(rows, key):
    return Q.assess_corpus([{"fetch_id": r["fetch_id"], "outlet_id": r["outlet_id"], "url": r["url"], "fetched_at": r["fetched_at"] or "",
                             "features": r[key], "extracted": r[key] is not None} for r in rows], ruleset=Q.RULESET_3)


PHASE3_KEY = REPOSITORY / "docs" / "intake" / "quality" / "phase3_blind_control_2026-11-15" / "KEY_machine_predictions_open_only_after_the_verdicts.json"
# the blind-control cases the operator's reading named (brief of 2026-11-15, §3)
NAMED_CASES = ("C01", "C04", "C05", "C14", "C18", "C24", "C28", "C30", "C31", "C32", "C33", "C39", "C42", "C48", "C49", "C51", "C53",
               "C54", "C55", "C62", "C64", "C66", "C69", "C70")


def summarize(arguments) -> int:
    rows, meta = S3._read_rows(arguments.rows)
    by_id = {r["fetch_id"]: r for r in rows}
    n = len(rows)
    d3, d4 = _decisions(rows, "features_v3"), _decisions(rows, "features_v4")
    out: dict = {"schema": "coprepan-body-quality-study/v1", "date": "2026-11-15", "decision": "CPD-0041",
                 "population": {"pages": n, "outlets": len({r["outlet_id"] for r in rows}),
                                "what": "every stored 2xx item page of the CPD-0039/0040 study, read from the local packs, offline"},
                 "versions": {"before": "article_html/0.3.0 + editorial-metadata/2", "after": "article_html/0.4.0 + editorial-metadata/3",
                              "quality": Q.RULESET_3, "body_quality": BQ.VERSION, "text_reuse": R.VERSION_2,
                              "templates": {"path": B.TEMPLATES_PATH, "sha256": B.body_templates_sha256(), "digests": len(B.body_templates())}},
                 "derivation": meta}
    reasons, pages, words, stated = Counter(), Counter(), Counter(), Counter()
    for r in rows:
        seen = set()
        for s in r["selection"]:
            key = f"{s['decision']}:{s['reason']}"
            reasons[key] += 1
            words[key] += s["words"]
            seen.add(key)
            if s["in_stated_body"] is not None:
                stated[f"{key}|checkable"] += 1
                stated[f"{key}|in_stated_body"] += bool(s["in_stated_body"])
        for key in seen:
            pages[key] += 1
    w3 = sum(r["v3"]["body_words"] for r in rows)
    w4 = sum(r["v4"]["body_words"] for r in rows)
    out["body"] = {
        "body_changed": sum(1 for r in rows if r["v3"]["body"] != r["v4"]["body"]),
        "body_same": sum(1 for r in rows if r["v3"]["body"] == r["v4"]["body"]),
        "container_changed_pages": sum(1 for r in rows if not r["before_selection_equals_0_3_0_body"]),
        "schema_problems": sum(1 for r in rows if r["schema_problems"]),
        "title_changed": sum(1 for r in rows if r["v3"]["title"] != r["v4"]["title"]),
        "subtitles_changed": sum(1 for r in rows if r["v3"]["subtitles"] != r["v4"]["subtitles"]),
        "words": {"0_3_0": w3, "0_4_0": w4},
        "selection": {k: {"blocks": reasons[k], "pages": pages[k], "words": words[k]} for k, _ in reasons.most_common()},
        "checked_against_stated_article_body": {k: v for k, v in sorted(stated.items())},
    }
    trans = Counter(f"{d3[r['fetch_id']]['decision']}->{d4[r['fetch_id']]['decision']}" for r in rows)
    changed = [r for r in rows if d3[r["fetch_id"]]["decision"] != d4[r["fetch_id"]]["decision"]]
    out["quality"] = {
        "ruleset": Q.RULESET_3, "on_0_3_0": dict(Counter(d["decision"] for d in d3.values())),
        "on_0_4_0": dict(Counter(d["decision"] for d in d4.values())), "transitions": dict(trans),
        "changed": [{"fetch": r["fetch_id"][4:20], "outlet_id": r["outlet_id"], "url": r["url"], "on_0_3_0": d3[r["fetch_id"]]["reasons"],
                     "on_0_4_0": d4[r["fetch_id"]]["reasons"], "words": [r["v3"]["body_words"], r["v4"]["body_words"]],
                     "body_quality": (r["body_quality"] or {}).get("state"),
                     "excluded": dict(Counter(s["reason"] for s in r["selection"] if s["decision"] == E.SELECTION_EXCLUDED)),
                     "included": dict(Counter(s["reason"] for s in r["selection"] if s["decision"] == E.SELECTION_INCLUDED))} for r in changed],
    }
    states = Counter((r["body_quality"] or {}).get("state", "not_extracted") for r in rows)
    signals = Counter(s["signal"] for r in rows for s in ((r["body_quality"] or {}).get("evidence") or {}).get("signals", []))
    out["body_quality"] = {"states": dict(states), "states_by_core": dict(Counter(
        f"{(r['body_quality'] or {}).get('state', 'not_extracted')}|{d4[r['fetch_id']]['decision']}" for r in rows)),
        "signals": dict(signals), "residual_pages_by_outlet": dict(Counter(r["outlet_id"] for r in rows
                                                                          if (r["body_quality"] or {}).get("state") == "residual_suspect").most_common(20))}
    layers = {}
    for name in rows[0]["layers_3"]:
        name4 = name.replace(P.LAYER_AGENCY_2, P.LAYER_AGENCY_3)
        layers[f"{name} -> {name4}"] = sum(1 for r in rows if (r["layers_3"][name]["value"], r["layers_3"][name]["value_state"])
                                           == (r["layers_4"][name4]["value"], r["layers_4"][name4]["value_state"]))
    out["layers_same_value"] = {"pages": layers, "of": n}
    rel3 = {(x["document_id"], x["target_document_id"]): x for r in rows for x in r["relations_3"]}
    rel4 = {(x["document_id"], x["target_document_id"]): x for r in rows for x in r["relations_4"]}
    lost = [k for k in rel3 if k not in rel4]
    why = Counter()
    for a, b in lost:
        ra, rb = by_id[a], by_id[b]
        short = min(ra["v4"]["body_words"], rb["v4"]["body_words"]) < R.MIN_WORDS
        why[f"{rel3[(a, b)]['relation']}|{rel3[(a, b)]['text_match']}|{ra['outlet_id']}|{'a body now under 50 words' if short else 'bodies now differ'}"] += 1
    out["text_reuse"] = {"rule": R.VERSION_2, "relations": {"0_3_0": len(rel3), "0_4_0": len(rel4), "kept": len(set(rel3) & set(rel4))},
                         "classes_0_3_0": dict(Counter(f"{x['relation']}|{x['text_match']}" for x in rel3.values())),
                         "classes_0_4_0": dict(Counter(f"{x['relation']}|{x['text_match']}" for x in rel4.values())),
                         "lost": dict(why.most_common()),
                         "new": dict(Counter(f"{rel4[k]['relation']}|{rel4[k]['text_match']}" for k in rel4 if k not in rel3)),
                         "kept_class_moves": dict(Counter(f"{rel3[k]['relation']}|{rel3[k]['text_match']}->{rel4[k]['text_match']}"
                                                          for k in set(rel3) & set(rel4)))}
    key = {c["case_id"]: c for c in json.loads(PHASE3_KEY.read_text(encoding="utf-8"))["cases"]}
    out["named_blind_cases"] = []
    for case_id in NAMED_CASES:
        for fid in key[case_id]["fetch_ids"]:
            r = by_id[fid]
            out["named_blind_cases"].append({
                "case": case_id, "outlet_id": r["outlet_id"], "fetch": fid[4:20], "words": [r["v3"]["body_words"], r["v4"]["body_words"]],
                "core": [d3[fid]["decision"], d4[fid]["decision"]], "body_quality": (r["body_quality"] or {}).get("state"),
                "excluded": dict(Counter(s["reason"] for s in r["selection"] if s["decision"] == E.SELECTION_EXCLUDED)),
                "included": dict(Counter(s["reason"] for s in r["selection"] if s["decision"] == E.SELECTION_INCLUDED)),
                "relations": [len(r["relations_3"]), len(r["relations_4"])]})
    seconds = meta.get("seconds", {})
    out["cost"] = {"seconds": seconds, "ms_per_page": {k: round(1000 * v / n, 2) for k, v in seconds.items() if k != "text_reuse_both"}}
    arguments.out.write_bytes((json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(json.dumps({"body_changed": out["body"]["body_changed"], "quality": out["quality"]["transitions"], "states": out["body_quality"]["states"],
                      "relations": out["text_reuse"]["relations"]}))
    return 0


# --- the blind control of the BODY selection ---------------------------------------------------------------------------------

SEED = "body-quality-control-2026-11-15"
RANDOM_SIZE = 16
# Pages this run opened one by one while it developed the rules (fetch id prefixes after "ft1:"); never drawn.
DEVELOPMENT_PREFIXES = (
    "96e45708bf", "2160f8214d", "313c715733", "4ab3e4fd3d", "c5f5cf5998", "bbb3896922", "21157fd112", "df1719ad69", "c92644b044",
    "203add0271", "c8ce9bf1a4", "f7d5269ede", "9defe72c66", "163dbd55e2", "2e616ac5a0", "051832def1", "88ed062f1d", "27b0c343f5",
    "03640df7f9", "94bba5946c", "f56c5e276b", "44729e03cf", "14607df116", "a3d7c8838b", "465c80c1d9", "f125df5c92", "9e16178ac4",
    "4b27718743", "60d71bd423", "88fc16174a", "042a7627b0", "e66d9f0c3b", "88d145d39a", "3f12edcd78", "ec11db4a05", "c70b378f47",
    "f11cc8e4dc", "d0a897a892", "2912549e39", "d5b352f2b5", "e4ea74baf5", "a350b755a1", "5bc78faab5", "863eed8141", "4456038e7b",
    "b3fbf6b99d", "787736f002", "e18f74b49c", "87df5797e9", "c16173dbdc", "c64132e5dc", "ec7d8da235", "42754651ad", "626fe82cfc",
    "7b10b4fcf4", "12b3e3b64b", "0dcd70faaa", "b0ff1ca41b", "5af36c0b5a", "66774694f3", "fac70bf026")
QUESTIONS = {
    "FOREIGN": "the number(s) of the blocks that are NOT text of this article (navigation, teasers, promotion, credits, embeds, "
               "repeated copies ...), comma-separated; 0 if every block is article text",
    "MISSING": "complete | beginning_missing | end_missing | middle_missing | not_an_article  (is article text missing from the "
               "blocks shown, compared with the page?)",
    "CORE": "yes | no | unsure  (a complete Spanish press text of running prose, at least 150 words; not a live ticker, list, "
            "page frame, paywall stub, page about the publication or paid content -- provenance does not matter)",
}


def _strata(rows, d3, d4):
    st = lambda r: (r["body_quality"] or {}).get("state")  # noqa: E731
    removed = lambda r: r["v3"]["body_words"] - r["v4"]["body_words"]  # noqa: E731
    reasons = lambda r: {s["reason"] for s in r["selection"]}  # noqa: E731
    return [
        ("T01_large_removal", "0.4.0 removed at least 30 % of 0.3.0's BODY words", 4,
         lambda r: r["v3"]["body_words"] >= 100 and removed(r) >= 0.3 * r["v3"]["body_words"]),
        ("T02_inclusion", "0.4.0 included a lead or a stated-body paragraph", 4, lambda r: reasons(r) & {"lead_paragraph", "stated_article_body"}),
        ("T03_template", "a block removed as an outlet template", 3, lambda r: "outlet_template" in reasons(r)),
        ("T04_module", "a block removed as a byline, caption, date, embed or related module", 3,
         lambda r: reasons(r) & {"module_byline", "module_caption", "module_date", "module_social_embed", "module_related"}),
        ("T05_core_newly_rejected", "CORE accepted on 0.3.0, rejected on 0.4.0", 3,
         lambda r: d3[r["fetch_id"]]["decision"] == Q.ACCEPT and d4[r["fetch_id"]]["decision"] == Q.REJECT),
        ("T06_core_newly_accepted", "CORE rejected on 0.3.0, accepted on 0.4.0", 3,
         lambda r: d3[r["fetch_id"]]["decision"] == Q.REJECT and d4[r["fetch_id"]]["decision"] == Q.ACCEPT),
        ("T07_residual", "body-quality/1 residual_suspect", 4, lambda r: st(r) == "residual_suspect"),
        ("T08_unchanged_clean", "BODY unchanged and clean (what the rules may miss)", 3,
         lambda r: st(r) == "clean" and r["v3"]["body"] == r["v4"]["body"] and r["v4"]["body_words"] >= 150),
        ("T09_not_article_or_incomplete", "body-quality/1 not_article or incomplete", 2, lambda r: st(r) in ("not_article", "incomplete")),
    ]


def _union_blocks(three, four):
    """The blocks either version has in its BODY, in page order: (number, block index, text). The same block indexes in both
    records (0.4.0 keeps 0.3.0's block segmentation); the selection is not shown."""
    b3 = {b["index"] for b in three.record["blocks"] if b["role"] == E.ROLE_BODY}
    b4 = {b["index"] for b in four.record["blocks"] if b["role"] == E.ROLE_BODY}
    texts = {b["index"]: b["text"] for b in four.record["blocks"]}
    return [(n, i, texts[i]) for n, i in enumerate(sorted(b3 | b4), 1)], b3, b4


def draw(arguments) -> int:
    rows, _ = S3._read_rows(arguments.rows)
    by_id = {r["fetch_id"]: r for r in rows}
    d3, d4 = _decisions(rows, "features_v3"), _decisions(rows, "features_v4")
    excluded = P3._excluded_prefixes() | set(DEVELOPMENT_PREFIXES) | {f[4:20] for c in json.loads(PHASE3_KEY.read_text(encoding="utf-8"))["cases"]
                                                                       for f in c["fetch_ids"]}
    eligible = [r for r in rows if not P3._is_excluded(r["fetch_id"], excluded) and r["v4"]["outcome"] == E.OUTCOME_EXTRACTED]
    order = sorted(eligible, key=lambda r: (r["country_id"], r["outlet_id"], hashlib.sha256((SEED + r["fetch_id"]).encode()).hexdigest()))
    random_part = P3._systematic(order, RANDOM_SIZE, SEED + "/random")
    used = {r["fetch_id"] for r in random_part}
    cases = [{"component": "random", "stratum": "R00_random", "fetch_id": r["fetch_id"], "inclusion_probability": round(RANDOM_SIZE / len(order), 6)}
             for r in random_part]
    strata_doc = [{"stratum": "R00_random", "component": "random", "population": len(order), "drawn": len(random_part),
                   "method": "systematic sample with a random start over the eligible pages ordered by country, outlet and "
                             "sha256(seed + fetch id); inclusion probability n / N for every page",
                   "inclusion_probability": round(RANDOM_SIZE / len(order), 6)}]
    for stratum, what, k, predicate in _strata(rows, d3, d4):
        population = [r for r in eligible if predicate(r) and r["fetch_id"] not in used]
        picked = P3._pick(population, k, f"{SEED}/{stratum}")
        used |= {r["fetch_id"] for r in picked}
        strata_doc.append({"stratum": stratum, "component": "targeted", "what": what, "population": len(population), "drawn": len(picked),
                           "method": "the first k by sha256(seed/stratum + fetch id), at most one page per outlet",
                           "inclusion_probability": "not equal within the stratum; not for population estimates"})
        cases += [{"component": "targeted", "stratum": stratum, "fetch_id": r["fetch_id"]} for r in picked]
    for case in cases:
        case["_order"] = hashlib.sha256((SEED + "/case/" + case["fetch_id"]).encode()).hexdigest()
    cases.sort(key=lambda c: c["_order"])
    for n, case in enumerate(cases, 1):
        case["case_id"] = f"B{n:02d}"
    need = {c["fetch_id"] for c in cases}
    pages = {}
    for page, body in S3.stored_pages(arguments):
        if page["fetch_id"] in need:
            three = A.ARTICLE_3.run(body, body_sha256=page["body_sha256"], **page["args"])
            four = B.ARTICLE_4.run(body, body_sha256=page["body_sha256"], **page["args"])
            pages[page["fetch_id"]] = (three, four)
    form, key, sheet = [], [], []
    for case in cases:
        fid = case["fetch_id"]
        r, (three, four) = by_id[fid], pages[fid]
        union, b3, b4 = _union_blocks(three, four)
        number = {i: n for n, i, _ in union}
        questions = ["FOREIGN", "MISSING", "CORE"]
        predictions = {
            "FOREIGN": ",".join(str(number[i]) for i in sorted(b3 | b4) if i not in b4) or "0",
            "MISSING": {"not_article": "not_an_article", "incomplete": "middle_missing"}.get((r["body_quality"] or {}).get("state"), "complete"),
            "CORE": "yes" if d4[fid]["decision"] == Q.ACCEPT else "no"}
        before = {"FOREIGN": ",".join(str(number[i]) for i in sorted(b3 | b4) if i not in b3) or "0",
                  "CORE": "yes" if d3[fid]["decision"] == Q.ACCEPT else "no"}
        selection = {number[s["index"]]: f"{s['decision']}:{s['reason']}" for s in r["selection"] if s["index"] in number}
        for q in questions:
            form.append({"case_id": case["case_id"], "question": q, "allowed": QUESTIONS[q], "answer": "", "note": ""})
        key.append({"case_id": case["case_id"], "component": case["component"], "stratum": case["stratum"], "fetch_id": fid,
                    "inclusion_probability": case.get("inclusion_probability"), "predictions_0_4_0": predictions,
                    "predictions_0_3_0": before, "selection_by_number": selection, "body_quality": r["body_quality"],
                    "core_reasons": {"0_3_0": d3[fid]["reasons"], "0_4_0": d4[fid]["reasons"]},
                    "extracted_text_sha256": {"0_3_0": three.extracted_text_sha256, "0_4_0": four.extracted_text_sha256},
                    "versions": {"extractor": "article_html/0.4.0 (against 0.3.0)", "quality": Q.RULESET_3, "body_quality": BQ.VERSION,
                                 "templates_sha256": B.body_templates_sha256()}})
        title = next((b["text"] for b in four.record["blocks"] if b["kind"] == "title"), None)
        sheet.append({"case_id": case["case_id"], "outlet": r["outlet_id"], "country": r["country_id"], "url": r["url"],
                      "published": r["published"], "title": title, "blocks": [(n, t) for n, _, t in union]})
    out_dir = arguments.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["case_id", "question", "allowed", "answer", "note"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(form)
    form_bytes = buffer.getvalue().encode("utf-8")
    key_bytes = (json.dumps({"schema": "coprepan-body-quality-key/v1", "seed": SEED, "cases": key}, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    sheet_bytes = _sheet(sheet).encode("utf-8")
    (out_dir / "verdicts_form.csv").write_bytes(form_bytes)
    (out_dir / "KEY_machine_predictions_open_only_after_the_verdicts.json").write_bytes(key_bytes)
    arguments.sheet.write_bytes(sheet_bytes)
    manifest = {
        "schema": "coprepan-body-quality-control/v1", "date": "2026-11-15", "decision": "CPD-0041", "seed": SEED, "frozen_before_review": True,
        "population": {"what": "the stored 2xx item pages of the CPD-0039/0040/0041 study, extracted", "pages": len(rows),
                       "eligible": len(eligible),
                       "excluded": "the 109 pages of the 2026-11-15 review, the pages of the phase-3 blind control (now development "
                                   "material), and every page this run opened one by one (DEVELOPMENT_PREFIXES of the script)"},
        "limits": ["a holdout within the known population, not fresh data: the rules were developed on aggregate measurements and on "
                   "listings of removed blocks across all pages",
                   f"the random component (n={RANDOM_SIZE}) supports coarse statements only; the targeted strata find errors and do "
                   "not estimate population precision",
                   "the sheet shows the blocks either version has in its BODY, without saying which version keeps which: the FOREIGN "
                   "answer measures the selection's false deletions (a kept-out block that is article text) and residual "
                   "contamination (a kept block that is not) of both versions; text neither version has can only be reported "
                   "through MISSING"],
        "strata": strata_doc, "cases": [{"case_id": c["case_id"], "fetch_id": c["fetch_id"]} for c in cases],
        "questions": QUESTIONS,
        "files": {"verdicts_form.csv": P3._sha(form_bytes), "KEY_machine_predictions_open_only_after_the_verdicts.json": P3._sha(key_bytes),
                  "reading_sheet (local only, publisher text)": P3._sha(sheet_bytes)},
        "code": {"script": "scripts/study_body_quality.py", "extractor": "article_html/0.4.0", "templates_sha256": B.body_templates_sha256()},
    }
    (out_dir / "manifest.json").write_bytes((json.dumps(manifest, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(json.dumps({"cases": len(cases), "questions": len(form), "strata": {s["stratum"]: [s["population"], s["drawn"]] for s in strata_doc}}))
    return 0


def _sheet(cases) -> str:
    e = _html.escape
    css = (":root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6b66;--line:#d9d6cf;--card:#fff;--accent:#2f5d8a}"
           "@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe6;--muted:#a3a29b;--line:#3a3935;--card:#1f1f1d;--accent:#8db6e0}}"
           "body{background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,sans-serif;margin:0 auto;max-width:980px;padding:16px}"
           "section{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:16px;margin:18px 0}"
           "h1{font-size:22px}h2{font-size:18px;margin:0 0 8px}.m{color:var(--muted);font-size:13px}"
           "ol{padding-left:34px}li{margin:4px 0}td{vertical-align:top;padding:2px 8px}code{font-size:13px}")
    out = [f"<!doctype html><html lang=\"de\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
           f"<title>BODY control</title><style>{css}</style></head><body><h1>BODY control (frozen 2026-11-15)</h1>",
           "<p>Each case lists, in page order, every block that one of two extractor versions takes as the article's running text. "
           "Which version keeps which block is not shown. Mark in <code>verdicts_form.csv</code> the numbers of the blocks that are "
           "<b>not</b> text of this article, whether article text is missing (compare with the page at its address; the live page may "
           "differ from the stored one), and the CORE judgement.</p>",
           "<table>" + "".join(f"<tr><td><code>{q}</code></td><td>{e(a)}</td></tr>" for q, a in QUESTIONS.items()) + "</table>"]
    for c in cases:
        out.append(f"<section id=\"{c['case_id']}\"><h2>{c['case_id']}</h2><p class=\"m\">{e(c['outlet'])} · {e(c['country'])} · "
                   f"{e(c['published'] or 'date not stated')} · <a href=\"{e(c['url'])}\">{e(c['url'])}</a></p>"
                   f"<p><b>{e(c['title'] or '(no title block)')}</b></p><ol>"
                   + "".join(f"<li value=\"{n}\">{e(t)}</li>" for n, t in c["blocks"]) + "</ol>"
                   "<p class=\"m\">Questions: <code>FOREIGN</code>, <code>MISSING</code>, <code>CORE</code></p></section>")
    out.append("</body></html>")
    return "\n".join(out) + "\n"


def _set(value: str) -> set[str]:
    """Block numbers from a FOREIGN answer: '3,9-12' (a hyphen or an en dash makes a range); '0' and '' are the empty set."""
    out: set[str] = set()
    for v in (value or "").replace(" ", "").replace("–", "-").split(","):
        if not v or v == "0":
            continue
        a, _, b = v.partition("-")
        out |= {str(n) for n in range(int(a), int(b or a) + 1)}
    return out


# The bases a filled form may give an answer (CPD-0042): only OPERATOR_CONFIRMED is human gold.
BASES = ("OPERATOR_CONFIRMED", "TECHNICALLY_VERIFIED", "AGENT_ASSESSED", "UNRESOLVED")


def _coarse_missing(value: str) -> str:
    return value if value in ("complete", "not_an_article") else ("text_missing" if value.endswith("_missing") else value)


def _score(key, labels, words=None, versions=("0_4_0", "0_3_0")):
    """``labels``: {(case, question): (answer, block numbers left out)}. Counts per component and version, and the cases."""
    table, cases = defaultdict(Counter), {}
    for (cid, q), (answer, excluded) in sorted(labels.items()):
        case = key[cid]
        detail = cases.setdefault(cid, {"component": case["component"], "stratum": case["stratum"]})
        for version in versions:
            predicted = case[f"predictions_{version}"].get(q)
            if predicted is None:
                continue
            t = table[(case["component"], f"{q}|{version}")]
            if q == "FOREIGN":
                human, machine = _set(answer) - excluded, _set(predicted) - excluded
                # machine "foreign" = kept out of the BODY by that version; human "foreign" = not article text
                parts = {"kept_out_and_foreign": human & machine, "false_deletion": machine - human, "residual": human - machine}
                for name, blocks in parts.items():
                    t[f"blocks_{name}"] += len(blocks)
                    if words is not None:
                        t[f"words_{name}"] += sum(words[cid].get(int(b), 0) for b in blocks)
                    if blocks and name != "kept_out_and_foreign":
                        detail[f"{name}|{version}"] = sorted(int(b) for b in blocks)
                t["cases_with_false_deletion"] += bool(parts["false_deletion"])
                t["cases_with_residual"] += bool(parts["residual"])
            elif q == "MISSING":
                t["agree" if answer == predicted else "disagree"] += 1
                t["agree_coarse" if _coarse_missing(answer) == _coarse_missing(predicted) else "disagree_coarse"] += 1
                if _coarse_missing(answer) != _coarse_missing(predicted):
                    detail[f"MISSING|{version}"] = {"label": answer, "predicted": predicted}
            else:
                outcome = "unsure" if answer == "unsure" else ("agree" if answer == predicted else "disagree")
                t[outcome] += 1
                t[f"label_{answer}|predicted_{predicted}"] += 1
                if outcome == "disagree":
                    detail[f"CORE|{version}"] = {"label": answer, "predicted": predicted}
    return {f"{c}|{q}": dict(t) for (c, q), t in sorted(table.items())}, cases


def merge(arguments) -> int:
    """Score a filled form against the frozen key. A form with a ``basis`` column (CPD-0042) is scored twice: on the operator's
    confirmed verdicts alone (human gold; blocks the operator left open are left out of that question) and on every answer
    (gold plus what the run verified or assessed, the basis counted); a form without it as before, every answer alike."""
    manifest = json.loads((arguments.out_dir / "manifest.json").read_text(encoding="utf-8"))
    key_path = arguments.out_dir / "KEY_machine_predictions_open_only_after_the_verdicts.json"
    if P3._sha(key_path.read_bytes()) != manifest["files"][key_path.name]:
        raise SystemExit("the key is not the frozen key")
    form_path = arguments.out_dir / "verdicts_form.csv"
    if P3._sha(form_path.read_bytes()) != manifest["files"][form_path.name]:
        raise SystemExit("the blank form is not the frozen form")
    key = {c["case_id"]: c for c in json.loads(key_path.read_text(encoding="utf-8"))["cases"]}
    verdicts = list(csv.DictReader(arguments.verdicts.open(encoding="utf-8-sig")))
    if {(v["case_id"], v["question"]) for v in verdicts} != {(r["case_id"], r["question"]) for r in csv.DictReader(form_path.open(encoding="utf-8"))}:
        raise SystemExit("the filled form does not hold the frozen form's cases and questions")
    words = None
    if arguments.sheet is not None:
        if P3._sha(arguments.sheet.read_bytes()) != manifest["files"]["reading_sheet (local only, publisher text)"]:
            raise SystemExit("the reading sheet is not the frozen sheet")
        src = arguments.sheet.read_text(encoding="utf-8")
        words = {cid: {int(n): len(_html.unescape(t).split()) for n, t in re.findall(r'<li value="(\d+)">(.*?)</li>', body, re.S)}
                 for cid, body in re.findall(r'<section id="(B\d\d)">(.*?)</section>', src, re.S)}
    with_basis = "basis" in (verdicts[0] if verdicts else {})
    all_labels, gold, bases, unanswered = {}, {}, Counter(), Counter()
    for v in verdicts:
        cid, q, answer = v["case_id"], v["question"], v["answer"].strip().lower()
        basis = (v.get("basis") or "").strip() if with_basis else "OPERATOR_CONFIRMED"
        if with_basis and basis not in BASES:
            raise SystemExit(f"{cid} {q}: basis {basis!r} is not one of {BASES}")
        bases[f"{q}|{basis}"] += 1
        if not answer or basis == "UNRESOLVED":
            unanswered[f"{key[cid]['component']}|{q}"] += 1
        else:
            all_labels[(cid, q)] = (answer, set())
        operator = (v.get("operator_answer") or "").strip().lower() if with_basis else answer
        opened = _set(v.get("operator_open") or "") if with_basis else set()
        if q == "FOREIGN" and with_basis and (operator or opened):
            gold[(cid, q)] = (operator or "0", opened)
        elif operator and (q != "FOREIGN" or not with_basis):
            gold[(cid, q)] = (operator, set())
    every, every_cases = _score(key, all_labels, words)
    result = {"schema": "coprepan-body-quality-result/v2", "manifest_sha256": P3._sha((arguments.out_dir / "manifest.json").read_bytes()),
              "verdicts_sha256": P3._sha(arguments.verdicts.read_bytes()), "bases": dict(sorted(bases.items())),
              "unanswered": dict(unanswered)}
    if with_basis:
        result["operator_confirmed_only"], _ = _score(key, gold, words)
    result["all_answers"] = every
    result["cases"] = every_cases
    result["note"] = ("random (16) and targeted (29) components apart; only the random component speaks to the population, and "
                      "only coarsely; the targeted strata look for errors and estimate no precision. 'operator_confirmed_only' is the "
                      "human gold (blocks the operator left open are left out); 'all_answers' adds the answers the run established "
                      "from the stored pages (the basis column says which)")
    arguments.out.write_bytes((json.dumps(result, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(json.dumps({k: result[k] for k in ("bases", "unanswered")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
