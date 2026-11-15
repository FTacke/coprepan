"""Content-quality study (CPD-0038): features of every stored 2xx item page under two extractors, offline and read-only.

Usage:
  python scripts/study_content_quality.py features --runtime <workspace> --out <features.jsonl>
  python scripts/study_content_quality.py show --runtime <workspace> --fetch <fetch_id> [--extractor article_html/0.1.0] [--chars 1200]

``features`` writes one row per page: identifiers, the HTTP facts, the body characters of ``baseline_html/0.1.0``,
``article_html/0.1.0`` and of the longest JSON-LD ``articleBody`` (a publisher-stated comparison value), and the features of
``coprepan.content_quality`` on the article extractor's body. No text of a page is written. ``show`` prints one page's
extracted body for a person (or the study's own reading) -- to the terminal only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from coprepan import canary_driver as D, content_quality as Q, core_pipeline, extraction as E, extraction_article as A, pack  # noqa: E402

LD = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)


def _ld_bodies(node, found):
    if isinstance(node, dict):
        body = node.get("articleBody")
        if isinstance(body, str):
            found.append(len(re.sub(r"\s+", " ", body).strip()))
        for value in node.values():
            _ld_bodies(value, found)
    elif isinstance(node, list):
        for value in node:
            _ld_bodies(value, found)


def jsonld_chars(text: str) -> int:
    found: list[int] = []
    for block in LD.findall(text):
        try:
            _ld_bodies(json.loads(block.strip()), found)
        except ValueError:
            continue
    return max(found) if found else 0


def pages(workspace: core_pipeline.Workspace):
    """Every stored 2xx item fetch with its pack entry, newest packs last."""
    records = {r["fetch_id"]: r for r in D.fetch_records(workspace)
               if r["fetch_kind"] == "item" and r["outcome"] == "FETCHED" and 200 <= int(r["response"]["status"]) < 300}
    for path in sorted(workspace.packs.glob("*.warc.gz*")):
        if path.name.endswith((".pack.json", ".index.jsonl")) or ".torn-" in path.name:
            continue
        identifier = path.name.split(".")[0]
        try:
            entries = pack.scan(path, identifier)
        except (pack.PackError, OSError):   # an open pack sealed (renamed) while the study reads: its sealed name follows
            continue
        for entry in entries:
            if entry.fetch_id in records and entry.body_sha256 is not None:
                yield records[entry.fetch_id], path, entry


def run_both(stored: dict, body: bytes):
    arguments = core_pipeline._extraction_arguments(stored)
    return (E.BASELINE.run(body, body_sha256=stored["body_sha256"], **arguments),
            A.ARTICLE.run(body, body_sha256=stored["body_sha256"], **arguments))


def features(arguments) -> int:
    workspace = core_pipeline.Workspace(arguments.runtime)
    out = open(arguments.out, "w", encoding="utf-8")
    count = 0
    for record, path, entry in pages(workspace):
        stored = pack.read_fetch_record(path, entry)
        body = pack.read_body(path, entry)
        base, art = run_both(stored, body)
        try:
            decoded, _ = E._decode(E.decode_content(body, stored["response"].get("content_encoding") or "identity"),
                                   E.declared_charset_of(stored["response"]["headers"]))
            ld = jsonld_chars(decoded)
        except E.ContentDecodingError:
            decoded, ld = None, 0
        row = {"fetch_id": record["fetch_id"], "run_id": record["run_id"], "outlet_id": record["outlet_id"],
               "url": record["request"]["requested_url"], "final_url": record["response"].get("final_url"),
               "status": record["response"]["status"], "content_type": record["response"].get("content_type"),
               "body_bytes": len(body), "body_sha256": stored["body_sha256"],
               "baseline_chars": len(base.body_text) if base.outcome == E.OUTCOME_EXTRACTED else 0,
               "article_chars": len(art.body_text) if art.outcome == E.OUTCOME_EXTRACTED else 0,
               "jsonld_chars": ld, "outcome": art.outcome, "fetched_at": record["fetch_started_at"],
               "features": Q.features(art.record, http_status=record["response"]["status"], html=decoded) if art.outcome == E.OUTCOME_EXTRACTED else None}
        out.write(json.dumps(row, ensure_ascii=False) + "\n")
        count += 1
    out.close()
    print(json.dumps({"pages": count, "out": str(arguments.out)}))
    return 0


def show(arguments) -> int:
    workspace = core_pipeline.Workspace(arguments.runtime)
    for record, path, entry in pages(workspace):
        if record["fetch_id"] != arguments.fetch and not record["fetch_id"].startswith(arguments.fetch):
            continue
        stored = pack.read_fetch_record(path, entry)
        base, art = run_both(stored, pack.read_body(path, entry))
        chosen = base if arguments.extractor.startswith("baseline") else art
        text = chosen.body_text
        title = next((b["text"] for b in chosen.record["blocks"] if b["role"] == E.ROLE_TITLE), "")
        print(f"== {record['outlet_id']} {record['request']['requested_url']}\n== title: {title}\n== body chars {len(text)}")
        cut = arguments.chars
        print(text[:cut] + ("\n[...]\n" + text[-cut // 3:] if len(text) > cut else ""))
        return 0
    print("not found")
    return 1


def decide(arguments) -> int:
    """Decisions of content-quality/1 for every page of a features file (corpus rules included), and their summary."""
    rows = [json.loads(line) for line in open(arguments.features, encoding="utf-8")]
    pages = [{"fetch_id": r["fetch_id"], "outlet_id": r["outlet_id"], "url": r["url"], "fetched_at": r.get("fetched_at") or "",
              "features": r["features"], "extracted": r["outcome"] == E.OUTCOME_EXTRACTED} for r in rows]
    decisions = Q.assess_corpus(pages)
    with open(arguments.out, "w", encoding="utf-8") as out:
        for r in rows:
            out.write(json.dumps({"fetch_id": r["fetch_id"], "outlet_id": r["outlet_id"], **decisions[r["fetch_id"]]}) + "\n")
    from collections import Counter
    print(json.dumps({"ruleset": Q.RULESET, "pages": len(rows), "decisions": dict(Counter(d["decision"] for d in decisions.values())),
                      "first_reasons": dict(Counter(d["reasons"][0] for d in decisions.values() if d["reasons"]))}, indent=1))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("features")
    one.add_argument("--runtime", type=Path, required=True)
    one.add_argument("--out", type=Path, required=True)
    two = sub.add_parser("show")
    two.add_argument("--runtime", type=Path, required=True)
    two.add_argument("--fetch", required=True)
    two.add_argument("--extractor", default=A.ARTICLE.stage_version)
    two.add_argument("--chars", type=int, default=1200)
    three = sub.add_parser("decide")
    three.add_argument("--features", type=Path, required=True)
    three.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args(argv)
    return {"features": features, "show": show, "decide": decide}[arguments.command](arguments)


if __name__ == "__main__":
    sys.exit(main())
