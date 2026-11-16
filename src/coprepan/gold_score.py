"""The machine against frozen human gold (CPD-0044): predictions made **after** the freeze, aligned word by word to the
model-independent text view, scored by design-based estimators, candidate against the realistic baseline.

**Systems** (pre-registered; versions pinned, never the moving ``PREFERRED``): ``candidate`` = ``article_html/0.4.2`` with
``body-templates/1``, ``content-quality/4`` on ``content-features/2``, ``body-quality/2``; ``baseline`` = ``article_html/0.3.0``
with ``content-quality/3`` (the container-only extractor before the BODY selection -- the feasible alternative); ``predecessor``
= ``article_html/0.4.1`` with ``content-quality/4`` (diagnostic). The CORE gate is applied page by page (``content_quality.assess``
with the address); its corpus rules (template bodies, duplicates of earlier pages) need the corpus and are reported apart.

**Alignment.** The text view's word tokens (``\\w+``, NFC, lower case) carry the gold label of their first character. Each
machine BODY block, in order, is sought as a contiguous token run in the view -- after the previous match first, then anywhere --
and else aligned locally (matching runs of at least ``MIN_LOCAL_RUN`` tokens). Matched view tokens are *included*; machine tokens
that match nothing are *unaligned* (reported, never counted as gold).

**Per case**: gold BODY words, included BODY words, missed BODY words and *missed spans* (runs of at least ``MIN_MISSED_RUN``
consecutive missed BODY tokens -- single-token misses are alignment noise more often than text), included words by gold label
(title, standfirst, caption, embed, foreign, foreign_implicit: contamination; unsure: doubt), unaligned words; the CORE decision.

**Estimates** (``survey_stats``): for the probability component, word recall and precision as ratio estimators and case-level
proportions (a missed span; any contamination; CORE false accept among machine accepts; CORE false reject among gold yes), each
with its design-based interval; the paired difference candidate - baseline. Two estimands when the design gives both weights:
``documents`` (each fetched document counts once: weights ``N_h / n_h``) and ``outlets`` (each outlet counts once: ``1 / n_h``).
A non-probability component is counted, never weighted. Every number is ``DIAGNOSTIC`` here; no threshold is applied.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from collections import Counter
from typing import Any, Mapping

from . import body_quality as BQ
from . import content_quality as Q
from . import extraction as E
from . import extraction_article as A
from . import extraction_body as B
from . import gold_review as G
from . import survey_stats as SS

RESULT_SCHEMA = "gold-body-result/v1"
PREDICTIONS_SCHEMA = "gold-body-predictions/v1"
SYSTEMS = {
    "candidate": {"extractor": B.ARTICLE_4_2, "quality": Q.RULESET_4, "status": BQ.VERSION_2},
    "baseline": {"extractor": A.ARTICLE_3, "quality": Q.RULESET_3, "status": None},
    "predecessor": {"extractor": B.ARTICLE_4_1, "quality": Q.RULESET_4, "status": None},
}
MIN_LOCAL_RUN = 2
MIN_MISSED_RUN = 3
CONTAMINATION = ("title", "standfirst", "caption", "embed", "foreign", G.IMPLICIT)
_TOKEN = re.compile(r"\w+", re.UNICODE)


def _norm(token: str) -> str:
    return unicodedata.normalize("NFC", token).lower()


def view_tokens(case: Mapping[str, Any], labels: list[list[str]]) -> tuple[list[str], list[str]]:
    tokens, token_labels = [], []
    for seg, row in zip(case["view"]["segments"], labels):
        for m in _TOKEN.finditer(seg["text"]):
            tokens.append(_norm(m.group()))
            token_labels.append(row[m.start()] if m.start() < len(row) else G.IMPLICIT)
    return tokens, token_labels


def _find(hay: list[str], needle: list[str], start: int) -> int:
    if not needle:
        return -1
    first, n = needle[0], len(needle)
    i = start
    while True:
        try:
            i = hay.index(first, i)
        except ValueError:
            return -1
        if hay[i:i + n] == needle:
            return i
        i += 1


def align(view: list[str], blocks: list[str]) -> tuple[list[bool], int]:
    """Which view tokens the machine BODY blocks cover, and how many machine tokens cover nothing."""
    covered = [False] * len(view)
    unaligned, cursor = 0, 0
    for text in blocks:
        tokens = [_norm(t) for t in _TOKEN.findall(text)]
        if not tokens:
            continue
        at = _find(view, tokens, cursor)
        if at < 0:
            at = _find(view, tokens, 0)
        if at >= 0:
            for k in range(at, at + len(tokens)):
                covered[k] = True
            cursor = at + len(tokens)
            continue
        matcher = difflib.SequenceMatcher(None, view, tokens, autojunk=False)
        hit = 0
        for block in matcher.get_matching_blocks():
            if block.size >= MIN_LOCAL_RUN:
                for k in range(block.a, block.a + block.size):
                    covered[k] = True
                hit += block.size
        unaligned += len(tokens) - hit
    return covered, unaligned


def case_metrics(case: Mapping[str, Any], gold_case: Mapping[str, Any], blocks: list[str]) -> dict[str, Any]:
    labels = G.char_labels(case, gold_case["resolved"])
    tokens, token_labels = view_tokens(case, labels)
    covered, unaligned = align(tokens, blocks)
    gold_body = sum(1 for lab in token_labels if lab == "body")
    tp = sum(1 for lab, c in zip(token_labels, covered) if lab == "body" and c)
    runs, run, missed_span_words = 0, 0, 0
    for lab, c in [*zip(token_labels, covered), ("end", True)]:
        if lab == "body" and not c:                   # a maximal run of consecutive missed BODY tokens; any other token ends it
            run += 1
            continue
        if run >= MIN_MISSED_RUN:
            runs += 1
            missed_span_words += run
        run = 0
    included = Counter(lab for lab, c in zip(token_labels, covered) if c and lab != "body")
    contamination = sum(included[k] for k in CONTAMINATION)
    return {"gold_body_words": gold_body, "included_body_words": tp, "missed_body_words": gold_body - tp,
            "missed_spans": runs, "missed_span_words": missed_span_words, "included_by_label": dict(included),
            "contamination_words": contamination, "unsure_included_words": included.get("unsure", 0),
            "unaligned_machine_words": unaligned, "machine_words": sum(len(_TOKEN.findall(b)) for b in blocks)}


# --- predictions (after the freeze) ----------------------------------------------------------------------------------------


def predict_page(page: Mapping[str, Any], body: bytes) -> dict[str, Any]:
    """Every pre-registered system on one stored page."""
    out = {}
    try:
        html, _ = E._decode(E.decode_content(body, page["args"]["content_encoding"] or "identity"), page["args"]["declared_charset"])
    except E.ContentDecodingError:
        html = ""
    for name, system in SYSTEMS.items():
        x = system["extractor"].run(body, body_sha256=page["body_sha256"], **page["args"])
        entry: dict[str, Any] = {"extractor": system["extractor"].stage_version, "outcome": x.outcome, "quality": system["quality"]}
        if x.outcome == E.OUTCOME_EXTRACTED:
            blocks = [b["text"] for b in x.record["blocks"] if b["role"] == E.ROLE_BODY]
            f = Q.features(x.record, http_status=page.get("status"), html=html)
            decision = Q.assess(f, url=page["url"], ruleset=system["quality"])
            entry.update({"body_blocks": blocks, "body_text_sha256": x.body_text_sha256, "core": decision["decision"],
                          "core_reasons": decision["reasons"]})
            if system["status"]:
                entry["body_quality"] = BQ.assess(x.record, html=html, version=system["status"])["state"]
        else:
            entry.update({"body_blocks": [], "core": Q.REJECT, "core_reasons": ["not_extracted"]})
        out[name] = entry
    return out


# --- scoring -------------------------------------------------------------------------------------------------------------


def score(package: G.Package, gold: Mapping[str, Any], predictions: Mapping[str, Any]) -> dict[str, Any]:
    """The result: per case and per system the metrics; for the probability component the design-based estimates."""
    if predictions.get("gold_sha256") != package.frozen["gold_sha256"]:
        raise G.GoldError("the predictions were not made against this frozen gold")
    design = {c["case_id"]: c for c in package.design()["cases"]}
    rows = []
    for gc in gold["cases"]:
        cid = gc["case_id"]
        case = package.cases[cid]
        pred = predictions["cases"][cid]
        row = {"case_id": cid, "outlet_id": case["outlet_id"], "country_id": case["country_id"], "design": design[cid],
               "gold": {"core": gc["core"]["value"], "source_state": gc["source_state"]}, "systems": {}}
        for name in SYSTEMS:
            m = case_metrics(case, gc, pred[name]["body_blocks"])
            m["core"] = pred[name]["core"]
            m["core_reasons"] = pred[name]["core_reasons"]
            row["systems"][name] = m
        rows.append(row)
    probability = [r for r in rows if r["design"].get("component") == "probability"]
    _realised_design(probability)
    out = {"schema": RESULT_SCHEMA, "package_id": package.package_id, "gold_sha256": package.frozen["gold_sha256"],
           "predictions_sha256": predictions.get("sha256"), "systems": {k: {"extractor": v["extractor"].stage_version,
                                                                            "quality": v["quality"], "status": v["status"]}
                                                                        for k, v in SYSTEMS.items()},
           "cases": len(rows), "probability_cases": len(probability),
           "estimates": {}, "counts": {}, "per_case": [{"case_id": r["case_id"], "outlet_id": r["outlet_id"],
                                                        "component": r["design"].get("component"), "gold": r["gold"],
                                                        **{n: {k: v for k, v in m.items()} for n, m in r["systems"].items()}}
                                                       for r in rows]}
    for part in sorted({r["design"].get("component", "unknown") for r in rows}):
        sel = [r for r in rows if r["design"].get("component", "unknown") == part]
        out["counts"][part] = _counts(sel)
    if probability:
        for estimand in ("documents", "outlets"):
            key = "weight_documents" if estimand == "documents" else "weight_outlets"
            if not all(r["design"].get(key) for r in probability):
                continue
            out["estimates"][estimand] = _estimates(probability, key)
    return out


def _realised_design(rows: list[dict[str, Any]]) -> None:
    """The weights of the cases the gold holds (``n_h`` counted in the gold, so a freeze of replicate 1 alone is weighted as
    one document per outlet) and the variance design: outlets as strata with documents as units when every outlet has at least
    two gold cases; otherwise **collapsed strata** -- the country as variance stratum, the outlet as unit (conservative: it adds
    the between-outlet variance), countries with one outlet pooled together."""
    n_h: dict[str, int] = {}
    for r in rows:
        n_h[r["design"]["stratum"]] = n_h.get(r["design"]["stratum"], 0) + 1
    collapsed = any(v < 2 for v in n_h.values())
    outlets_in_country: dict[str, set] = {}
    for r in rows:
        outlets_in_country.setdefault(r["country_id"], set()).add(r["design"]["stratum"])
    for r in rows:
        d = r["design"]
        n = n_h[d["stratum"]]
        d["weight_documents"] = d["frame_size"] / n
        d["weight_outlets"] = 1.0 / n
        if collapsed:
            d["variance_stratum"] = r["country_id"] if len(outlets_in_country[r["country_id"]]) >= 2 else "pooled"
            d["variance_unit"] = d["stratum"]
        else:
            d["variance_stratum"], d["variance_unit"] = d["stratum"], r["case_id"]
        d["variance_design"] = "collapsed strata (country / outlet)" if collapsed else "outlet strata / documents"


def _counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"cases": len(rows)}
    for name in SYSTEMS:
        c = Counter()
        for r in rows:
            m, g = r["systems"][name], r["gold"]["core"]
            for k in ("gold_body_words", "included_body_words", "missed_body_words", "missed_span_words", "contamination_words",
                      "unsure_included_words", "unaligned_machine_words"):
                c[k] += m[k]
            c["cases_with_missed_span"] += int(m["missed_spans"] > 0)
            c["cases_with_contamination"] += int(m["contamination_words"] > 0)
            if g == "unsure":
                c["core_gold_unsure"] += 1
            elif g in ("yes", "no"):
                c[f"core_gold_{g}_machine_{m['core'].lower()}"] += 1
        out[name] = dict(c)
    return out


def _estimates(rows: list[dict[str, Any]], weight_key: str) -> dict[str, Any]:
    w = [r["design"][weight_key] for r in rows]
    strata = [r["design"]["variance_stratum"] for r in rows]
    clusters = [r["design"]["variance_unit"] for r in rows]
    est: dict[str, Any] = {"weights": weight_key, "n": len(rows), "variance_design": rows[0]["design"]["variance_design"],
                           "variance_strata": len(set(strata)), "variance_units": len(set(zip(strata, clusters)))}

    def col(name, key):
        return [r["systems"][name][key] for r in rows]

    for name in SYSTEMS:
        e: dict[str, Any] = {}
        tp, gb = col(name, "included_body_words"), col(name, "gold_body_words")
        cont = col(name, "contamination_words")
        e["word_recall"] = SS.ratio(tp, gb, weights=w, strata=strata, clusters=clusters)
        e["word_precision"] = SS.ratio(tp, [a + b for a, b in zip(tp, cont)], weights=w, strata=strata, clusters=clusters)
        has_body = [1.0 if g > 0 else 0.0 for g in gb]
        if any(has_body):
            sub = [i for i, h in enumerate(has_body) if h]
            e["cases_with_missed_span"] = SS.proportion([1.0 if rows[i]["systems"][name]["missed_spans"] > 0 else 0.0 for i in sub],
                                                        weights=[w[i] for i in sub], strata=[strata[i] for i in sub],
                                                        clusters=[clusters[i] for i in sub])
        e["cases_with_contamination"] = SS.proportion([1.0 if c > 0 else 0.0 for c in cont], weights=w, strata=strata, clusters=clusters)
        acc = [i for i, r in enumerate(rows) if r["systems"][name]["core"] == Q.ACCEPT and r["gold"]["core"] in ("yes", "no")]
        if acc:
            e["core_false_accept_among_accepted"] = SS.proportion([1.0 if rows[i]["gold"]["core"] == "no" else 0.0 for i in acc],
                                                                  weights=[w[i] for i in acc], strata=[strata[i] for i in acc],
                                                                  clusters=[clusters[i] for i in acc])
        yes = [i for i, r in enumerate(rows) if r["gold"]["core"] == "yes"]
        if yes:
            e["core_false_reject_among_gold_yes"] = SS.proportion(
                [1.0 if rows[i]["systems"][name]["core"] == Q.REJECT else 0.0 for i in yes], weights=[w[i] for i in yes],
                strata=[strata[i] for i in yes], clusters=[clusters[i] for i in yes])
        est[name] = e
    est["gold_core_unsure_share"] = SS.proportion([1.0 if r["gold"]["core"] == "unsure" else 0.0 for r in rows], weights=w,
                                                  strata=strata, clusters=clusters)
    c, b = "candidate", "baseline"
    est["candidate_minus_baseline"] = {
        "word_recall": SS.ratio_difference(col(c, "included_body_words"), col(c, "gold_body_words"), col(b, "included_body_words"),
                                           col(b, "gold_body_words"), weights=w, strata=strata, clusters=clusters),
        "word_contamination_share": SS.ratio_difference(
            col(c, "contamination_words"), [a + d for a, d in zip(col(c, "included_body_words"), col(c, "contamination_words"))],
            col(b, "contamination_words"), [a + d for a, d in zip(col(b, "included_body_words"), col(b, "contamination_words"))],
            weights=w, strata=strata, clusters=clusters)}
    return est


__all__ = ["SYSTEMS", "align", "case_metrics", "predict_page", "score", "view_tokens", "RESULT_SCHEMA", "PREDICTIONS_SCHEMA"]
