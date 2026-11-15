"""Offline diagnostic of the weekend qualification (2026-11-14/15): body characters per extraction variant, measured on the
local bytes of the waves of DOA-2026-11-14-2 and its confirmation record DOA-2026-11-15-1. Numbers only; no text is printed or written. No variant is chosen here (CPD-0018).

Usage: python scripts/diagnose_extraction_variants.py <checkout> <evidence dir> <runtime workspace> <out.json>

Variants: baseline (extraction.BASELINE); rule A / rule B (the two measured ancestor-rule repairs); jsonld (the longest schema.org
articleBody in the page's JSON-LD, a publisher-stated field); paragraphs (every <p> outside script/style: an upper bound with
boilerplate); first / largest <article> element; densest_p_parent (the element whose direct <p> children carry the most text,
outside nav/aside/footer/form); the ratios of baseline and densest_p_parent to jsonld where jsonld exists.
"""
import importlib.util
import json
import re
import statistics
import sys
from collections import defaultdict
from html import unescape
from pathlib import Path

repo, evidence, runtime, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
sys.path.insert(0, str(repo / "src"))
spec = importlib.util.spec_from_file_location("q", repo / "scripts" / "build_weekend_qualification.py")
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
from coprepan import canary_driver as D, core_pipeline, extraction as E, pack  # noqa: E402

LD = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)
P = re.compile(r"<p\b[^>]*>(.*?)</p>", re.S | re.I)
TAG = re.compile(r"<[^>]+>")
SCRIPT = re.compile(r"<(script|style|noscript)\b.*?</\1>", re.S | re.I)


from html.parser import HTMLParser

VOID = {"br", "img", "hr", "meta", "link", "input", "source", "wbr", "area", "base", "col", "embed", "param", "track"}
SKIP = {"script", "style", "noscript", "template", "svg"}


class Shape(HTMLParser):
    """Per <article> instance: its text characters (outside script/style, nav/aside/footer/form inside it); and the parent tags
    that carry text anywhere in the page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.articles, self.count, self.by_parent = [], [], 0, defaultdict(int)
        self.p_parent, self.serial = defaultdict(int), 0

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        self.serial += 1
        if tag == "p":
            self.stack.append(("p", ("p", self._parent_id())))
            return
        if tag == "article":
            self.articles.append(0)
            self.stack.append(("article", len(self.articles) - 1))
        else:
            self.stack.append((tag, ("el", self.serial)))

    def _parent_id(self):
        for t, ident in reversed(self.stack):
            if t != "p":
                return (t, ident)
        return ("-", None)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        n = len(" ".join(data.split()))
        if not n or any(t in SKIP for t, _ in self.stack):
            return
        self.by_parent[self.stack[-1][0] if self.stack else "-"] += n
        if any(t in ("nav", "aside", "footer", "form") for t, _ in self.stack):
            return
        for t, index in self.stack:
            if t == "article":
                self.articles[index] += n
        for t, ident in reversed(self.stack):
            if t == "p":
                self.p_parent[ident[1]] += n
                break


def bodies_ld(obj, found):
    if isinstance(obj, dict):
        if isinstance(obj.get("articleBody"), str):
            found.append(len(obj["articleBody"].strip()))
        for v in obj.values():
            bodies_ld(v, found)
    elif isinstance(obj, list):
        for v in obj:
            bodies_ld(v, found)


receipts = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(evidence.glob("*/canary-receipt-*.json"))]
receipts = [r for r in receipts if (r.get("operator_authorization") or {}).get("authorization_id") in ("DOA-2026-11-14-2", "DOA-2026-11-15-1")]
ws = core_pipeline.Workspace(runtime)
runs = {r["run_id"] for r in receipts}
records = [r for r in D.fetch_records(ws) if r["run_id"] in runs and r["fetch_kind"] == "item" and r["outcome"] == "FETCHED"
           and 200 <= int(r["response"]["status"]) < 300]
locate = {}
for ident in {p for r in receipts for p in r["packs"]}:
    path = ws.packs / f"{ident}.warc.gz"
    for entry in pack.scan(path, ident):
        locate[entry.fetch_id] = (path, entry)
per = defaultdict(lambda: defaultdict(list))
containers = defaultdict(lambda: defaultdict(int))
parents = defaultdict(lambda: defaultdict(int))
for r in records:
    if r["fetch_id"] not in locate:
        continue
    path, entry = locate[r["fetch_id"]]
    stored = pack.read_fetch_record(path, entry)
    body = pack.read_body(path, entry)
    res = E.BASELINE.run(body, body_sha256=stored["body_sha256"], **core_pipeline._extraction_arguments(stored))
    o = r["outlet_id"]
    per[o]["baseline"].append(len(res.body_text) if res.outcome == E.OUTCOME_EXTRACTED else 0)
    try:
        raw = E.decode_content(body, stored["response"].get("content_encoding") or "identity")
        text, _ = E._decode(raw, E.declared_charset_of(stored["response"]["headers"]))
    except Exception:
        continue
    x, a, b = q._rule_chars(text)
    per[o]["rule_a"].append(a)
    per[o]["rule_b"].append(b)
    found = []
    for block in LD.findall(text):
        try:
            bodies_ld(json.loads(block.strip()), found)
        except ValueError:
            pass
    per[o]["jsonld"].append(max(found) if found else 0)
    clean = SCRIPT.sub(" ", text)
    per[o]["paragraphs"].append(sum(len(re.sub(r"\s+", " ", unescape(TAG.sub("", p))).strip()) for p in P.findall(clean)))
    parser = E._Parser()
    parser.feed(text)
    parser.close()
    containers[o][next((n for n in E._CONTAINERS if n in parser.containers), "none")] += 1
    shape = Shape()
    try:
        shape.feed(text)
        shape.close()
    except Exception:
        pass
    per[o]["articles_count"].append(len(shape.articles))
    per[o]["first_article"].append(shape.articles[0] if shape.articles else 0)
    per[o]["largest_article"].append(max(shape.articles) if shape.articles else 0)
    per[o]["densest_p_parent"].append(max(shape.p_parent.values()) if shape.p_parent else 0)
    ld = max(found) if found else 0
    if ld:
        per[o]["baseline_over_jsonld"].append(round(per[o]["baseline"][-1] / ld, 2))
        per[o]["densest_over_jsonld"].append(round(per[o]["densest_p_parent"][-1] / ld, 2))
    for tag, n in shape.by_parent.items():
        parents[o][tag] += n
parents_total = {o: sum(v.values()) for o, v in parents.items()}
result = {o: {"pages": len(v["baseline"]), **{k: statistics.median(vals) for k, vals in v.items() if vals},
              "jsonld_pages": sum(1 for x in v["jsonld"] if x), "container": dict(containers[o]),
              "text_parents_share": {t: round(n / parents_total[o], 2) for t, n in sorted(parents[o].items(), key=lambda kv: -kv[1])[:5]}}
          for o, v in sorted(per.items())}
out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
for o, v in result.items():
    print(o, v)
