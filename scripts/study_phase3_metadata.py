"""Phase-3 metadata study (CPD-0039): text structure, IPTC section mapping, scope, genre, AI and agency provenance, text reuse and
the quality gate before/after -- on every stored 2xx item page, offline and read-only.

Usage:
  python scripts/study_phase3_metadata.py cache   --runtime <workspace> --out <pages.jsonl.gz>          (optional, local only)
  python scripts/study_phase3_metadata.py derive  (--runtime <workspace> | --page-cache <pages.jsonl.gz>) --out <rows.jsonl.gz>
                                                  [--legacy-section-map <legacy section_map_v1.yml>]
  python scripts/study_phase3_metadata.py summarize --rows <rows.jsonl.gz> --out <study.json> --review <review.md>
  python scripts/study_phase3_metadata.py show    (--runtime <workspace> | --page-cache <pages.jsonl.gz>) --fetch <fetch id prefix>

``derive`` writes one row per page to a local file outside the repository: identifiers, both extractions' digests and block
structure (kinds, roles, subtitle texts), the content-quality features under ``article_html/0.1.0`` and ``/0.2.0``, the six
metadata layers, the AI and agency statements (short publisher notes, verbatim), and the text-reuse relations. Body text is not
written. ``summarize`` turns the rows into the versioned evidence record and the human review package. ``cache`` keeps the
stored bodies in a local file so that repeated runs do not reread the packs; it holds publisher bytes and stays outside the
repository and outside any shared root (delete it after the study).
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))
sys.path.insert(0, str(REPOSITORY / "scripts"))

from coprepan import content_quality as Q, core_pipeline, editorial_metadata as M, enrichment, extraction as E  # noqa: E402
from coprepan import extraction_article as A, pack, provenance as P, publisher_metadata as H, text_reuse as R  # noqa: E402

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")
# an agency named in the running text (a quoted source, never a credit): kept as a short snippet for the review of the rule
# that such a mention yields no label
AGENCY_MENTION = re.compile(r"(?:agencia|agencias)\s+(?:de\s+noticias\s+)?(?:EFE|AFP|Reuters|AP|Europa Press|Xinhua|ANSA|Bloomberg|Sputnik)\b",
                            re.I)


def agency_mentions(body_text: str) -> list[str]:
    out = []
    for match in AGENCY_MENTION.finditer(body_text):
        start = max(0, match.start() - 70)
        out.append(body_text[start:match.end() + 70].replace("\n", " "))
        if len(out) == 2:
            break
    return out


def stored_pages(arguments):
    """``(row, body bytes)`` of every stored 2xx item page, from the workspace packs or from a page cache. The validation
    holdout's runs are left out (CPD-0044) unless ``arguments.include_holdout``; a page cache is refused when it holds one."""
    from coprepan.validation_holdout import holdout_runs  # noqa: PLC0415

    include = bool(getattr(arguments, "include_holdout", False))
    if getattr(arguments, "page_cache", None):
        excluded = frozenset() if include else holdout_runs()
        for line in gzip.open(arguments.page_cache, "rt", encoding="utf-8"):
            row = json.loads(line)
            if row.get("run_id") in excluded:
                raise SystemExit(f"the page cache holds a validation holdout run ({row['run_id']}): development never reads it")
            yield row, base64.b64decode(row.pop("body_b64"))
        return
    import study_content_quality as S

    workspace = core_pipeline.Workspace(arguments.runtime)
    for record, path, entry in S.pages(workspace, include_holdout=include):
        stored = pack.read_fetch_record(path, entry)
        row = {"fetch_id": record["fetch_id"], "run_id": record["run_id"], "outlet_id": record["outlet_id"],
               "url": record["request"]["requested_url"], "status": record["response"]["status"], "fetched_at": record["fetch_started_at"],
               "body_sha256": stored["body_sha256"], "pack": path.name, "args": core_pipeline._extraction_arguments(stored)}
        yield row, pack.read_body(path, entry)


def cache(arguments) -> int:
    with gzip.open(arguments.out, "wt", encoding="utf-8") as out:
        n = 0
        for row, body in stored_pages(arguments):
            out.write(json.dumps({**row, "body_b64": base64.b64encode(body).decode("ascii")}) + "\n")
            n += 1
    print(json.dumps({"pages": n, "out": str(arguments.out)}))
    return 0


# --- the legacy section mapping, for comparison only (section-map-v1 of the frozen legacy system) ----------------------------


def legacy_matcher(path: Path | None):
    """The legacy rule: exact match on the lower-cased label, then 'contains'; opinion markers only flag. Read-only."""
    if path is None:
        return None
    import yaml  # noqa: PLC0415  (the legacy file is YAML; only this comparison needs it)

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    sections = data["standard_sections"]

    def match(label: str) -> str:
        value = unicodedata.normalize("NFKC", label).strip().lower()
        for name, rules in sections.items():
            if value in [str(x).lower() for x in rules.get("exact") or []]:
                return name
        for name, rules in sections.items():
            if any(str(x).lower() in value for x in rules.get("contains") or []):
                return name
        return "other_unclear"

    return match


def _record_summary(extraction):
    blocks = extraction.record["blocks"]
    return {"outcome": extraction.outcome, "extracted_text_sha256": extraction.extracted_text_sha256,
            "body_text_sha256": extraction.body_text_sha256, "body_characters": len(extraction.body_text),
            "body_blocks": sum(1 for b in blocks if b["role"] == E.ROLE_BODY)}


def derive(arguments) -> int:
    registry = json.loads((REPOSITORY / "config" / "outlet_registry.json").read_text(encoding="utf-8"))
    country = {o["outlet_id"]: o["country_id"] for o in registry["outlets"]}
    section_map = M.load_section_map()
    legacy = legacy_matcher(arguments.legacy_section_map)
    rows, bodies, statement_records = [], [], {}
    timing = Counter()
    for page, body in stored_pages(arguments):
        t = time.perf_counter()
        one = A.ARTICLE.run(body, body_sha256=page["body_sha256"], **page["args"])
        timing["extract_0_1_0"] += time.perf_counter() - t
        t = time.perf_counter()
        two = A.ARTICLE_2.run(body, body_sha256=page["body_sha256"], **page["args"])
        timing["extract_0_2_0"] += time.perf_counter() - t
        try:
            html, _ = E._decode(E.decode_content(body, page["args"]["content_encoding"] or "identity"), page["args"]["declared_charset"])
        except E.ContentDecodingError:
            html = ""
        t = time.perf_counter()
        metadata = enrichment.derive(html=html, url=page["url"], record=two.record, outlet_id=page["outlet_id"],
                                     country_id=country.get(page["outlet_id"], "unknown"), section_map=section_map)
        timing["metadata"] += time.perf_counter() - t
        t = time.perf_counter()
        f1 = Q.features(one.record, http_status=page["status"], html=html) if one.outcome == E.OUTCOME_EXTRACTED else None
        f2 = Q.features(two.record, http_status=page["status"], html=html) if two.outcome == E.OUTCOME_EXTRACTED else None
        timing["features_both"] += time.perf_counter() - t
        statements = P.ai_statements(two.record)
        if statements:
            statement_records[page["fetch_id"]] = two.record
        published = two.record["metadata"]["publication_date"]["value"]
        published = published[:19] if DATE.match(published or "") else None
        if two.outcome == E.OUTCOME_EXTRACTED:
            bodies.append({"document_id": page["fetch_id"], "outlet_id": page["outlet_id"], "body_text": two.body_text,
                           "published": published, "fetched_at": page["fetched_at"]})
        first_section = next((s["value"] for s in metadata["publisher"]["sections"]
                              if s["basis"] in ("json_ld_articleSection", "meta_article_section")), None)
        rows.append({
            "fetch_id": page["fetch_id"], "outlet_id": page["outlet_id"], "country_id": country.get(page["outlet_id"], "unknown"),
            "url": page["url"], "status": page["status"], "fetched_at": page["fetched_at"], "published": published,
            "v1": _record_summary(one), "v2": _record_summary(two),
            "title": next((b["text"] for b in two.record["blocks"] if b["kind"] == "title"), None),
            "subtitles": [{"index": b["index"], "basis": b["basis"], "text": b["text"][:300]} for b in two.record["blocks"]
                          if b["kind"] == E.KIND_SUBTITLE],
            "modules": [{"index": b["index"], "module": b["module"], "role_in_0_1_0": one.record["blocks"][b["index"]]["role"]}
                        for b in two.record["blocks"] if b.get("module")],
            "features_v1": f1, "features_v2": f2,
            "publisher": {k: metadata["publisher"][k] for k in ("article_types", "genre", "sections", "breadcrumb", "authors",
                                                                "organisations", "credit_text", "dateline")},
            "layers": metadata["layers"], "ai_statements": statements,
            "agency_mentions_in_body": agency_mentions(two.body_text) if two.outcome == E.OUTCOME_EXTRACTED else [],
            "legacy_section": legacy(first_section) if legacy and first_section else None, "first_section": first_section})
    # corpus-level: site-wide AI notices, then the AI layer again without them
    site = P.site_wide_statements([{"outlet_id": r["outlet_id"], "statements": r["ai_statements"]} for r in rows])
    for r in rows:
        if r["fetch_id"] in statement_records and site.get(r["outlet_id"]):
            r["layers"][P.LAYER_AI] = P.ai_disclosure(statement_records[r["fetch_id"]], site_wide=site[r["outlet_id"]])
    t = time.perf_counter()
    reuse = R.relations(bodies)
    timing["text_reuse"] = time.perf_counter() - t
    by_doc = defaultdict(list)
    for relation in reuse:
        by_doc[relation["document_id"]].append(relation)
    with gzip.open(arguments.out, "wt", encoding="utf-8") as out:
        for r in rows:
            r["relations"] = by_doc.get(r["fetch_id"], [])
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
        out.write(json.dumps({"_meta": {"pages": len(rows), "seconds": {k: round(v, 1) for k, v in timing.items()},
                                        "site_wide_ai_statements": {k: sorted(v) for k, v in site.items() if v},
                                        "section_map": section_map.pin(), "relations": len(reuse)}}, ensure_ascii=False) + "\n")
    print(json.dumps({"pages": len(rows), "relations": len(reuse), "seconds": {k: round(v, 1) for k, v in timing.items()}}))
    return 0


def show(arguments) -> int:
    for page, body in stored_pages(arguments):
        if not page["fetch_id"].startswith(arguments.fetch) and arguments.fetch not in page["fetch_id"]:
            continue
        two = A.ARTICLE_2.run(body, body_sha256=page["body_sha256"], **page["args"])
        print(f"== {page['outlet_id']} {page['url']}")
        for block in two.record["blocks"]:
            if block["role"] != E.ROLE_NON_BODY or block.get("module") or arguments.all:
                print(f"[{block['index']:3} {block['role'][:5]:5} {block['kind'][:9]:9}{' ' + block['module'] if block.get('module') else ''}] "
                      f"{block['text'][:arguments.chars]}")
        return 0
    print("not found")
    return 1


# --- summary and review --------------------------------------------------------------------------------------------------


def _read_rows(path: Path):
    rows, meta = [], {}
    for line in gzip.open(path, "rt", encoding="utf-8"):
        item = json.loads(line)
        if "_meta" in item:
            meta = item["_meta"]
        else:
            rows.append(item)
    return rows, meta


def _decisions(rows, ruleset, key):
    pages = [{"fetch_id": r["fetch_id"], "outlet_id": r["outlet_id"], "url": r["url"], "fetched_at": r["fetched_at"] or "",
              "features": r[key], "extracted": r[key] is not None} for r in rows]
    return Q.assess_corpus(pages, ruleset=ruleset)


def _share(counter: Counter, total: int) -> dict:
    return {k: {"pages": v, "share": round(v / total, 3) if total else None} for k, v in counter.most_common()}


def summarize(arguments) -> int:
    rows, meta = _read_rows(arguments.rows)
    n = len(rows)
    by_outlet = defaultdict(list)
    for r in rows:
        by_outlet[r["outlet_id"]].append(r)
    out: dict = {"schema": "coprepan-phase3-metadata-study/v1", "date": "2026-11-15", "decision": "CPD-0039",
                 "population": {"pages": n, "outlets": len(by_outlet), "countries": len({r["country_id"] for r in rows}),
                                "what": "every stored 2xx item page of the workspace (October pilot and 24-hour intake, weekend waves of "
                                        "2026-11-14/15), read from the local packs, offline"},
                 "derivation": meta}

    # text structure
    v1_v2 = Counter("body_same" if r["v1"]["body_text_sha256"] == r["v2"]["body_text_sha256"] else "body_changed" for r in rows)
    ver = Counter("version_same" if r["v1"]["extracted_text_sha256"] == r["v2"]["extracted_text_sha256"] else "version_changed" for r in rows)
    sub_basis = Counter(b["basis"] for r in rows for b in r["subtitles"])
    pages_sub = sum(1 for r in rows if r["subtitles"])
    modules = Counter((r["outlet_id"], m["role_in_0_1_0"]) for r in rows for m in r["modules"])
    out["text_structure"] = {
        "extractors": ["article_html/0.1.0", "article_html/0.2.0"], **dict(v1_v2), **dict(ver),
        "pages_with_subtitle": pages_sub, "subtitle_blocks_by_basis": dict(sub_basis),
        "outlets_with_subtitle": sum(1 for o, rs in by_outlet.items() if any(r["subtitles"] for r in rs)),
        "subtitle_pages_by_outlet": {o: sum(1 for r in rs if r["subtitles"]) for o, rs in sorted(by_outlet.items())},
        "ai_summary_module_blocks": {f"{o}|{role}": c for (o, role), c in sorted(modules.items())},
        "pages_whose_body_lost_an_ai_summary": sum(1 for r in rows if any(m["role_in_0_1_0"] == E.ROLE_BODY for m in r["modules"])),
    }

    # sections, scope, genre
    def layer_table(name):
        states = Counter((r["layers"][name]["value_state"], r["layers"][name]["reason"]) for r in rows)
        per_country = defaultdict(Counter)
        for r in rows:
            per_country[r["country_id"]][r["layers"][name]["value_state"]] += 1
        per_outlet = {o: dict(Counter(r["layers"][name]["value_state"] for r in rs)) for o, rs in sorted(by_outlet.items())}
        return {"states": {f"{s}|{why}": c for (s, why), c in states.most_common()},
                "known_share": round(sum(c for (s, _), c in states.items() if s == "known") / n, 3),
                "by_country": {c: dict(v) for c, v in sorted(per_country.items())}, "by_outlet": per_outlet}

    tops = Counter(top for r in rows if r["layers"][M.LAYER_SECTION]["value_state"] == "known"
                   for top in r["layers"][M.LAYER_SECTION]["attributes"]["tops"])
    out["section_iptc"] = {**layer_table(M.LAYER_SECTION), "top_concepts": dict(tops.most_common()),
                           "bases": dict(Counter(r["layers"][M.LAYER_SECTION]["basis"][0]["basis"] for r in rows
                                                 if r["layers"][M.LAYER_SECTION]["value_state"] == "known"))}
    unmapped = Counter()
    for r in rows:
        if r["layers"][M.LAYER_SECTION]["reason"] == "unmapped_label":
            for item in r["layers"][M.LAYER_SECTION]["attributes"]["published"][:1]:
                unmapped[(r["outlet_id"], item["value"][:60])] += 1
    out["section_iptc"]["unmapped_labels_top"] = [{"outlet_id": o, "label": l, "pages": c} for (o, l), c in unmapped.most_common(40)]
    constant = []
    for o, rs in sorted(by_outlet.items()):
        labels = [r["first_section"] for r in rs if r["first_section"]]
        if len(labels) >= 10:
            top, k = Counter(labels).most_common(1)[0]
            paths = Counter((r["url"].split("/")[3] if len(r["url"].split("/")) > 3 else "") for r in rs if r["first_section"] == top)
            if k / len(labels) >= 0.9:
                constant.append({"outlet_id": o, "label": top, "pages": k, "of": len(labels), "distinct_first_url_segments": len(paths),
                                 "verdict": "template_suspect" if len(paths) >= 3 and paths.most_common(1)[0][1] < 0.5 * k else "channel_constant"})
    out["section_iptc"]["outlet_constant_labels"] = constant
    if any(r["legacy_section"] for r in rows):
        cross = Counter((r["legacy_section"], ",".join(r["layers"][M.LAYER_SECTION]["attributes"].get("tops", [])) or r["layers"][M.LAYER_SECTION]["value_state"],
                         r["layers"][M.LAYER_SCOPE]["value"] or r["layers"][M.LAYER_SCOPE]["value_state"]) for r in rows if r["legacy_section"])
        out["legacy_comparison"] = [{"legacy": a, "iptc_tops": b, "scope": c, "pages": k} for (a, b, c), k in cross.most_common(60)]
    out["editorial_scope"] = {**layer_table(M.LAYER_SCOPE), "values": dict(Counter(r["layers"][M.LAYER_SCOPE]["value"] for r in rows
                                                                                       if r["layers"][M.LAYER_SCOPE]["value"]))}
    out["genre_placement"] = {**layer_table(M.LAYER_PLACEMENT), "values": dict(Counter(v for r in rows for v in r["layers"][M.LAYER_PLACEMENT]["value"] or []))}
    declared_by_outlet = defaultdict(Counter)
    for r in rows:
        for v in r["layers"][M.LAYER_DECLARED]["value"] or []:
            declared_by_outlet[v][r["outlet_id"]] += 1
    out["genre_declared"] = {**layer_table(M.LAYER_DECLARED),
                             "values": {v: {"pages": sum(c.values()), "outlets": dict(c.most_common())} for v, c in declared_by_outlet.items()},
                             "placement_vs_declared": dict(Counter(
                                 f"{','.join(r['layers'][M.LAYER_PLACEMENT]['value'] or ['-'])} / {','.join(r['layers'][M.LAYER_DECLARED]['value'] or ['-'])}"
                                 for r in rows if r["layers"][M.LAYER_PLACEMENT]["value"] or r["layers"][M.LAYER_DECLARED]["value"]).most_common(30))}
    types = defaultdict(Counter)
    for r in rows:
        for t in r["publisher"]["article_types"]:
            types[t][r["outlet_id"]] += 1
    out["genre_declared"]["json_ld_types_by_outlet"] = {t: {"pages": sum(c.values()), "top_outlets": dict(c.most_common(5)),
                                                            "outlet_share": {o: round(k / len(by_outlet[o]), 2) for o, k in c.most_common(5)}}
                                                        for t, c in sorted(types.items(), key=lambda kv: -sum(kv[1].values()))}

    # AI provenance
    ai_values = Counter((r["layers"][P.LAYER_AI]["value_state"], r["layers"][P.LAYER_AI]["value"] or r["layers"][P.LAYER_AI]["reason"]) for r in rows)
    statements = defaultdict(lambda: {"pages": 0, "outlets": Counter(), "value": None, "form": None, "roles": Counter(), "tools": set(),
                                      "human_review": None})
    for r in rows:
        for s in r["ai_statements"]:
            key = re.sub(r"\s+", " ", s["text"]).strip()[:300]
            item = statements[key]
            item["pages"] += 1
            item["outlets"][r["outlet_id"]] += 1
            item["value"], item["form"], item["human_review"] = s["value"], s["form"], s["human_review_stated"]
            item["roles"][f"{s['block_role']}/{s['block_kind']}{'/' + s['module'] if s['module'] else ''}"] += 1
            item["tools"] |= set(s["tools_named"])
    out["ai_disclosure"] = {
        "layer_states": {f"{s}|{v}": c for (s, v), c in ai_values.most_common()},
        "pages_with_any_statement": sum(1 for r in rows if r["ai_statements"]),
        "article_level_by_outlet": {o: dict(Counter(r["layers"][P.LAYER_AI]["value"] for r in rs if r["layers"][P.LAYER_AI]["value"]))
                                    for o, rs in sorted(by_outlet.items()) if any(r["layers"][P.LAYER_AI]["value"] for r in rs)},
        "components_by_outlet": {o: dict(Counter(c for r in rs for c in r["layers"][P.LAYER_AI]["attributes"]["components"]))
                                 for o, rs in sorted(by_outlet.items()) if any(r["layers"][P.LAYER_AI]["attributes"]["components"] for r in rs)},
        "distinct_statements": sorted([{"text": k, "pages": v["pages"], "outlets": dict(v["outlets"]), "value": v["value"], "form": v["form"],
                                        "positions": dict(v["roles"]), "tools_named": sorted(v["tools"]), "human_review_stated": v["human_review"]}
                                       for k, v in statements.items()], key=lambda d: -d["pages"]),
        "weekend_machine_text_pages_v1": [r["fetch_id"] for r in rows if (r["features_v1"] or {}).get("machine_text_hits")],
        "site_wide": meta.get("site_wide_ai_statements", {}),
    }
    mt = set(out["ai_disclosure"]["weekend_machine_text_pages_v1"])
    out["ai_disclosure"]["machine_text_pages_v1_read_again"] = dict(Counter(
        f"{r['outlet_id']}: {r['layers'][P.LAYER_AI]['value'] or r['layers'][P.LAYER_AI]['reason']}"
        f"{' + ' + ','.join(r['layers'][P.LAYER_AI]['attributes']['components']) if r['layers'][P.LAYER_AI]['attributes']['components'] else ''}"
        for r in rows if r["fetch_id"] in mt).most_common())

    # agency
    ag = [r for r in rows if r["layers"][P.LAYER_AGENCY]["value_state"] == "known"]
    out["agency_credit"] = {
        "pages_with_credit": len(ag), "share": round(len(ag) / n, 3),
        "agencies": dict(Counter(a for r in ag for a in r["layers"][P.LAYER_AGENCY]["value"]).most_common()),
        "agency_use": dict(Counter(r["layers"][P.LAYER_AGENCY]["attributes"]["agency_use"] for r in ag).most_common()),
        "positions": dict(Counter(e["position"] for r in ag for e in r["layers"][P.LAYER_AGENCY]["attributes"]["evidence"]).most_common()),
        "by_outlet": {o: {"pages": sum(1 for r in rs if r["layers"][P.LAYER_AGENCY]["value_state"] == "known"), "of": len(rs)}
                      for o, rs in sorted(by_outlet.items()) if any(r["layers"][P.LAYER_AGENCY]["value_state"] == "known" for r in rs)},
    }

    # text reuse
    rel = [x for r in rows for x in r["relations"]]
    cross = [x for x in rel if x["relation"] == R.SYNDICATED]
    credited = {r["fetch_id"]: r["layers"][P.LAYER_AGENCY]["value"] for r in rows}
    out["text_reuse"] = {
        "relations": dict(Counter(f"{x['relation']}|{x['match']}" for x in rel)),
        "cross_outlet_pairs_with_agency_credit_on_either_side": sum(1 for x in cross if credited.get(x["document_id"]) or credited.get(x["target_document_id"])),
        "cross_outlet_pairs": len(cross),
        "outlet_pairs": dict(Counter(" + ".join(x["outlets"]) for x in cross).most_common(30)),
        "clusters": len(set(R.clusters(cross).values())) if cross else 0,
    }

    # quality before / after
    d2 = _decisions(rows, Q.RULESET, "features_v1")
    d3 = _decisions(rows, Q.RULESET_3, "features_v2")
    trans = Counter(f"{d2[r['fetch_id']]['decision']}->{d3[r['fetch_id']]['decision']}" for r in rows)
    changed = [r for r in rows if d2[r["fetch_id"]]["decision"] != d3[r["fetch_id"]]["decision"]]
    out["quality"] = {
        "before": {"ruleset": Q.RULESET, "extractor": "article_html/0.1.0", **dict(Counter(d["decision"] for d in d2.values()))},
        "after": {"ruleset": Q.RULESET_3, "extractor": "article_html/0.2.0", **dict(Counter(d["decision"] for d in d3.values()))},
        "transitions": dict(trans),
        "changed": [{"fetch_id": r["fetch_id"], "outlet_id": r["outlet_id"], "url": r["url"], "before": d2[r["fetch_id"]]["reasons"],
                     "after": d3[r["fetch_id"]]["reasons"], "ai": r["layers"][P.LAYER_AI]["value"] or r["layers"][P.LAYER_AI]["reason"],
                     "ai_components": r["layers"][P.LAYER_AI]["attributes"]["components"],
                     "words_v1": (r["features_v1"] or {}).get("words"), "words_v2": (r["features_v2"] or {}).get("words")} for r in changed],
        "first_reasons_after": dict(Counter(d["reasons"][0] for d in d3.values() if d["reasons"]).most_common()),
        "accepted_by_ai_value": dict(Counter(r["layers"][P.LAYER_AI]["value"] or "unknown" for r in rows if d3[r["fetch_id"]]["decision"] == Q.ACCEPT)),
        "accepted_by_agency": dict(Counter("credited" if r["layers"][P.LAYER_AGENCY]["value"] else "unknown" for r in rows
                                           if d3[r["fetch_id"]]["decision"] == Q.ACCEPT)),
    }
    core = [r for r in rows if d3[r["fetch_id"]]["decision"] == Q.ACCEPT]
    out["core_candidate_coverage"] = {
        "pages": len(core),
        "metadata_known_share": {name: round(sum(1 for r in core if r["layers"][name]["value_state"] == "known") / max(1, len(core)), 3)
                                 for name in enrichment.LAYERS},
        "by_country": {c: {name: round(sum(1 for r in rs if r["layers"][name]["value_state"] == "known") / len(rs), 3) for name in enrichment.LAYERS}
                       | {"pages": len(rs)}
                       for c, rs in sorted(_group(core, "country_id").items())},
    }
    arguments.out.write_bytes((json.dumps(out, ensure_ascii=False, indent=1, sort_keys=False) + "\n").encode("utf-8"))   # LF
    if arguments.review:
        review(rows, d2, d3, arguments.review)
    print(json.dumps({"pages": n, "quality": out["quality"]["transitions"], "ai_pages": out["ai_disclosure"]["pages_with_any_statement"],
                      "agency_pages": len(ag), "relations": out["text_reuse"]["relations"]}))
    return 0


def _group(rows, key):
    out = defaultdict(list)
    for r in rows:
        out[r[key]].append(r)
    return out


def _pick(rows, predicate, k, seed="phase3-review-2026-11-15", per_outlet=1):
    """``k`` pages that satisfy ``predicate``, drawn deterministically, at most ``per_outlet`` per outlet."""
    chosen, seen = [], Counter()
    for r in sorted((r for r in rows if predicate(r)), key=lambda r: hashlib.sha256((seed + r["fetch_id"]).encode()).hexdigest()):
        if seen[r["outlet_id"]] < per_outlet:
            chosen.append(r)
            seen[r["outlet_id"]] += 1
        if len(chosen) == k:
            break
    return chosen


def review(rows, d2, d3, path: Path) -> None:
    """The compact human review package: real cases of every kind the operator is asked to judge."""
    ai, ag, sec = P.LAYER_AI, P.LAYER_AGENCY, M.LAYER_SECTION

    def line(r, note):
        return (f"| `{r['outlet_id']}` | {r['url']} | {note} | {d3[r['fetch_id']]['decision']} "
                f"{('(' + ', '.join(d3[r['fetch_id']]['reasons']) + ')') if d3[r['fetch_id']]['reasons'] else ''} | `{r['fetch_id'][4:20]}` | |")

    groups = [
        ("Subtitle from the page's own statement (alternativeHeadline / description)",
         lambda r: any(s["basis"] == E.SUBTITLE_STATED_BY_PAGE for s in r["subtitles"]), 8,
         lambda r: "T: " + (r["title"] or "")[:70] + " — S: " + next(s["text"] for s in r["subtitles"])[:110]),
        ("Subtitle by markup alone (the weaker path)", lambda r: r["subtitles"] and all(s["basis"] == E.SUBTITLE_BY_MARKUP for s in r["subtitles"]), 8,
         lambda r: "S: " + r["subtitles"][0]["text"][:140]),
        ("No subtitle found (recall check: is there one the rules missed?)",
         lambda r: not r["subtitles"] and (r["features_v2"] or {}).get("words", 0) > 150, 6, lambda r: "T: " + (r["title"] or "")[:100]),
        ("IPTC mapping known", lambda r: r["layers"][sec]["value_state"] == "known", 8,
         lambda r: f"{r['layers'][sec]['basis'][0]['value'][:40]} → " + ", ".join(
             f"{c['qcode']} {c['label_es']} ({c['relation']})" for c in r["layers"][sec]["attributes"]["concepts"][:2])),
        ("IPTC mapping not decided: ambiguous section", lambda r: r["layers"][sec]["value_state"] == "undecided", 5,
         lambda r: "; ".join(p["value"][:40] for p in r["layers"][sec]["attributes"]["published"][:2])),
        ("IPTC mapping unknown: section unmapped", lambda r: r["layers"][sec]["reason"] == "unmapped_label", 5,
         lambda r: "; ".join(p["value"][:40] for p in r["layers"][sec]["attributes"]["published"][:2])),
        ("AI: article declared generated", lambda r: r["layers"][ai]["value"] == "generated", 4,
         lambda r: next(s["text"] for s in r["ai_statements"] if s["value"] == "generated")[:160]),
        ("AI: article declared assisted", lambda r: r["layers"][ai]["value"] == "assisted", 6,
         lambda r: next(s["text"] for s in r["ai_statements"] if s["value"] == "assisted")[:160]),
        ("AI: article declared machine-translated", lambda r: r["layers"][ai]["value"] == "translated", 4,
         lambda r: next(s["text"] for s in r["ai_statements"] if s["value"] == "translated")[:160]),
        ("AI: machine summary beside the article (component)", lambda r: "summary" in r["layers"][ai]["attributes"]["components"], 4,
         lambda r: next(s["text"] for s in r["ai_statements"] if s["value"] == "summary")[:160]),
        ("AI: audio or image only (component, article text unknown)",
         lambda r: r["layers"][ai]["reason"] == "components_only" and "summary" not in r["layers"][ai]["attributes"]["components"], 4,
         lambda r: next(s["text"] for s in r["ai_statements"])[:160]),
        ("AI mentioned in the text, no disclosure (must stay unknown)",
         lambda r: r["layers"][ai]["reason"] == "no_disclosure_observed" and "inteligencia artificial" in (r["title"] or "").lower(), 4,
         lambda r: "T: " + (r["title"] or "")[:120]),
        ("Agency: edited material declared", lambda r: (r["layers"][ag]["attributes"] or {}).get("agency_use") == "edited_declared", 5,
         lambda r: next(e["text"] for e in r["layers"][ag]["attributes"]["evidence"] if e["position"] == "edited_note")[:140]),
        ("Agency: credited (author / dateline), take-over not stated", lambda r: (r["layers"][ag]["attributes"] or {}).get("agency_use") == "credit_only", 6,
         lambda r: "; ".join(f"{e['position']}: {e['text'][:60]}" for e in r["layers"][ag]["attributes"]["evidence"][:2])),
        ("Agency and newsroom credited together", lambda r: (r["layers"][ag]["attributes"] or {}).get("agency_use") == "joint_credit", 4,
         lambda r: "; ".join(f"{e['position']}: {e['text'][:60]}" for e in r["layers"][ag]["attributes"]["evidence"][:2])),
        ("Agency named only as a quoted source in the text (must stay unknown)",
         lambda r: r["layers"][ag]["value_state"] != "known" and r.get("agency_mentions_in_body"), 5,
         lambda r: "…" + r["agency_mentions_in_body"][0][:150] + "…"),
        ("Text reuse across outlets (syndication evidence)", lambda r: any(x["relation"] == R.SYNDICATED for x in r["relations"]), 6,
         lambda r: "; ".join(f"{x['match']} {x['containment']} with `{x['target_document_id'][4:20]}` ({' + '.join(x['outlets'])})" for x in r["relations"][:1])),
        ("Newly accepted by content-quality/3 (rejected by /2)", lambda r: d2[r["fetch_id"]]["decision"] == Q.REJECT and d3[r["fetch_id"]]["decision"] == Q.ACCEPT, 8,
         lambda r: "before: " + ", ".join(d2[r["fetch_id"]]["reasons"])),
        ("Newly rejected by content-quality/3", lambda r: d2[r["fetch_id"]]["decision"] == Q.ACCEPT and d3[r["fetch_id"]]["decision"] == Q.REJECT, 6,
         lambda r: "after: " + ", ".join(d3[r["fetch_id"]]["reasons"])),
        ("Accepted CORE text (control)", lambda r: d3[r["fetch_id"]]["decision"] == Q.ACCEPT, 10, lambda r: "T: " + (r["title"] or "")[:110]),
        ("Rejected, borderline (150-220 words or one reason only)",
         lambda r: d3[r["fetch_id"]]["decision"] == Q.REJECT and len(d3[r["fetch_id"]]["reasons"]) == 1 and d3[r["fetch_id"]]["reasons"][0] in
         ("too_short", "incomplete_against_stated_body", "not_running_prose"), 6, lambda r: "reason: " + d3[r["fetch_id"]]["reasons"][0]),
    ]
    lines = ["# Phase-3 review sample — text structure, section mapping, provenance, quality gate (2026-11-15)", "",
             "**For the operator's scientific acceptance (CPD-0039 § 14).** Real pages, drawn deterministically from the stored",
             "item pages (seed `phase3-review-2026-11-15/<group name>`, one page per outlet in a group). Each row: the outlet, the address, what the",
             "new rules found (verbatim where it is a publisher's note), the content-quality/3 decision, and a fetch id prefix to open",
             "the page locally (`python scripts/study_phase3_metadata.py show --page-cache <cache> --fetch <prefix>`). Enter your",
             "judgement in the last column: `ok`, or what is wrong. The agent's own reading of these groups is in the run report and is",
             "**not** a human gold standard. Nothing here is binding until you decide (CPD-0039 *Not decided here*).", ""]
    for name, predicate, k, note in groups:
        picked = _pick(rows, predicate, k, seed=f"phase3-review-2026-11-15/{name}")
        total = sum(1 for r in rows if predicate(r))
        lines += [f"## {name} — {total} pages, {len(picked)} drawn", "",
                  "| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |", "|---|---|---|---|---|---|"]
        lines += [line(r, note(r).replace("|", "/")) for r in picked]
        lines.append("")
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))   # LF


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("cache", "derive", "show"):
        command = sub.add_parser(name)
        source = command.add_mutually_exclusive_group(required=True)
        source.add_argument("--runtime", type=Path)
        if name != "cache":
            source.add_argument("--page-cache", type=Path)
        if name != "show":
            command.add_argument("--out", type=Path, required=True)
        if name == "derive":
            command.add_argument("--legacy-section-map", type=Path)
        if name == "show":
            command.add_argument("--fetch", required=True)
            command.add_argument("--chars", type=int, default=160)
            command.add_argument("--all", action="store_true")
    command = sub.add_parser("summarize")
    command.add_argument("--rows", type=Path, required=True)
    command.add_argument("--out", type=Path, required=True)
    command.add_argument("--review", type=Path)
    arguments = parser.parse_args(argv)
    return {"cache": cache, "derive": derive, "summarize": summarize, "show": show}[arguments.command](arguments)


if __name__ == "__main__":
    sys.exit(main())
