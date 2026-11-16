"""The local BODY review (CPD-0043): prepare a frozen package from the stored pages, serve the browser reviewer on a loopback
address, export, validate and score the operator's judgments. Offline; no publisher request; no model.

Usage:
  python scripts/body_review.py prepare  (--runtime <workspace> | --page-cache <pages.jsonl.gz>) --out-dir <package dir>
                                         [--random 80] [--per-stratum 5] [--seed 20261116] [--label <name>]
  python scripts/body_review.py serve    --package <package dir> [--port 8765] [--diagnostic] [--no-browser]
  python scripts/body_review.py export   --package <package dir> --out <judgments.json>
  python scripts/body_review.py validate --package <package dir> --judgments <judgments.json>
  python scripts/body_review.py score    --package <package dir> --judgments <judgments.json> --out <result.json> [--include-not-blind]

The package holds publisher text and is written outside the repository (a directory inside it is refused). ``prepare`` runs the
preferred candidates (``article_html/0.4.2`` with ``body-templates/1``, ``content-features/2``, ``content-quality/4``,
``body-quality/2``) on every stored page and, for the targeted strata, ``0.4.0``/``0.4.1`` and ``content-quality/3`` as the
earlier baselines. The random component is a stratified random sample by country (proportional allocation, exact inclusion
probabilities); the targeted component draws ``--per-stratum`` pages from each error-class stratum (``STRATA``), counted apart.
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))
sys.path.insert(0, str(REPOSITORY / "scripts"))

from coprepan import body_quality as BQ, body_review as R, content_quality as Q, extraction as E, extraction_body as B  # noqa: E402
import study_phase3_metadata as S3  # noqa: E402
import study_body_quality as SB  # noqa: E402

# The targeted strata, in the order a page is assigned (the first it meets). Each names an error class of the BODY/CORE study.
STRATA = {
    "changed_by_0_4_2": lambda r: r["changed_by_0_4_2"],
    "core_changed_since_cpd_0041": lambda r: r["core_now"] != r["core_0_4_0_cq3"],
    "live_or_preview": lambda r: r["live"],
    "near_threshold_120_180_words": lambda r: 120 <= (r["words"] or 0) < 180,
    "structured_list_or_table": lambda r: r["structured"],
    "stated_body_shortfall": lambda r: r["shortfall"],
    "residual_suspect": lambda r: r["body_quality"] == "residual_suspect",
    "rejected_not_too_short": lambda r: r["core_now"] == "REJECT" and r["first_reason"] not in (None, "too_short"),
}


def prepare(arguments) -> int:
    registry = json.loads((REPOSITORY / "config" / "outlet_registry.json").read_text(encoding="utf-8"))
    country = {o["outlet_id"]: o["country_id"] for o in registry["outlets"]}
    rows, feats = [], {"now": [], "old": []}
    for page, body in S3.stored_pages(arguments):
        new = B.PREFERRED.run(body, body_sha256=page["body_sha256"], **page["args"])
        if new.outcome != E.OUTCOME_EXTRACTED:
            continue
        old = B.ARTICLE_4.run(body, body_sha256=page["body_sha256"], **page["args"])
        mid = B.ARTICLE_4_1.run(body, body_sha256=page["body_sha256"], **page["args"])
        html = SB._decoded(page, body)
        f = Q.features(new.record, http_status=page["status"], html=html)
        f_old = Q.features(old.record, http_status=page["status"], html=html) if old.outcome == E.OUTCOME_EXTRACTED else None
        stated = f["stated_body_text_characters"] or 0
        row = {"fetch_id": page["fetch_id"], "outlet_id": page["outlet_id"], "country_id": country.get(page["outlet_id"], "unknown"),
               "url": page["url"], "fetched_at": page["fetched_at"] or "", "words": f["words"],
               "changed_by_0_4_2": new.body_text_sha256 != mid.body_text_sha256,
               "live": bool(f["declares_live_blog"]) or f["timestamp_led_share"] > 0.1 or bool(Q.LIVE_URL.search(page["url"]))
                       or bool(Q.LIVE_TITLE.search(f["title_text"] or "")),
               "structured": f["words"] >= 100 and (f["list_item_share"] >= 0.3 or f["function_word_share"] < 0.35),
               "shortfall": stated >= 1000 and f["body_characters"] < 0.8 * stated,
               "body_quality": BQ.assess(new.record, html=html, version=BQ.VERSION_2)["state"]}
        rows.append(row)
        for key, x in (("now", f), ("old", f_old)):
            feats[key].append({"fetch_id": row["fetch_id"], "outlet_id": row["outlet_id"], "url": row["url"],
                               "fetched_at": row["fetched_at"], "features": x, "extracted": x is not None})
    now = Q.assess_corpus(feats["now"], ruleset=Q.RULESET_4)
    then = Q.assess_corpus(feats["old"], ruleset=Q.RULESET_3)
    for r in rows:
        r["core_now"], r["core_0_4_0_cq3"] = now[r["fetch_id"]]["decision"], then[r["fetch_id"]]["decision"]
        r["first_reason"] = (now[r["fetch_id"]]["reasons"] or [None])[0]
    plan = {name: arguments.per_stratum for name in STRATA}
    cases = R.draw(rows, random_n=arguments.random, targeted=plan, strata=STRATA, seed=arguments.seed)
    wanted = {c["fetch_id"] for c in cases}
    by_id = {r["fetch_id"]: r for r in rows}
    materials = {}
    for page, body in S3.stored_pages(arguments):
        if page["fetch_id"] not in wanted:
            continue
        x = B.PREFERRED.run(body, body_sha256=page["body_sha256"], **page["args"])
        html = SB._decoded(page, body)
        case, machine = R.case_material("", page, x.record, country_id=by_id[page["fetch_id"]]["country_id"],
                                        extractor=f"{x.record['extractor']['name']}/{x.record['extractor']['version']}")
        decision = now[page["fetch_id"]]
        machine.update({"core": {"ruleset": Q.RULESET_4, "decision": decision["decision"], "reasons": decision["reasons"]},
                        "body_quality": by_id[page["fetch_id"]]["body_quality"], "words": by_id[page["fetch_id"]]["words"]})
        materials[page["fetch_id"]] = (case, machine, R.sanitize(html))
    strata_sizes = {name: sum(1 for r in rows if next((s for s in STRATA if STRATA[s](r)), None) == name) for name in STRATA}
    meta = {"label": arguments.label,
            "versions": {"extractor": f"article_html/{B.PREFERRED.version}", "templates_sha256": B.body_templates_sha256(),
                         "features": Q.FEATURES_VERSION, "quality": Q.RULESET_4, "body_quality": BQ.VERSION_2},
            "sampling": {"seed": arguments.seed, "random": {"n": arguments.random, "design": "stratified by country, proportional "
                                                                                            "allocation (largest remainder)"},
                         "targeted": {"per_stratum": arguments.per_stratum, "order": list(STRATA),
                                      "stratum_sizes_after_the_random_draw_excluded": strata_sizes}},
            "population": {"pages": len(rows), "countries": len({r["country_id"] for r in rows}),
                           "outlets": len({r["outlet_id"] for r in rows})}}
    manifest = R.write_package(arguments.out_dir, cases=cases, materials=materials, meta=meta, repository=REPOSITORY)
    shown = [c["shown_blocks"] for c in manifest["cases"]]
    print(json.dumps({"package_id": manifest["package_id"], "cases": len(manifest["cases"]),
                      "random": sum(1 for c in cases if c["component"] == "random"),
                      "targeted": sum(1 for c in cases if c["component"] == "targeted"),
                      "shown_blocks": {"total": sum(shown), "mean": round(sum(shown) / max(1, len(shown)), 1), "max": max(shown, default=0)},
                      "out": str(arguments.out_dir)}, ensure_ascii=False))
    return 0


def serve(arguments) -> int:
    package = R.Package(arguments.package)
    server = R.make_server(package, port=arguments.port, diagnostic=arguments.diagnostic)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"BODY review of package {package.package_id} ({len(package.case_ids)} cases) at {url}"
          + ("  -- DIAGNOSTIC MODE: machine labels visible, judgments not blind" if arguments.diagnostic else "")
          + "\nAnswers are saved as you go; stop with Ctrl+C.", flush=True)
    if not arguments.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def export(arguments) -> int:
    package = R.Package(arguments.package)
    data = R.export(package, R.Journal(package))
    arguments.out.write_bytes((json.dumps(data, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(json.dumps({"cases_closed": data["cases_closed"], "cases_total": data["cases_total"], "events": data["events"],
                      "out": str(arguments.out)}))
    return 0


def validate(arguments) -> int:
    package = R.Package(arguments.package)
    R.validate_export(package, json.loads(arguments.judgments.read_text(encoding="utf-8")))
    print("valid")
    return 0


def score(arguments) -> int:
    package = R.Package(arguments.package)
    result = R.score(package, json.loads(arguments.judgments.read_text(encoding="utf-8")), include_not_blind=arguments.include_not_blind)
    arguments.out.write_bytes((json.dumps(result, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(json.dumps(result["components"], ensure_ascii=False)[:3000])
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--runtime", type=Path)
    source.add_argument("--page-cache", type=Path)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--random", type=int, default=80)
    p.add_argument("--per-stratum", type=int, default=5)
    p.add_argument("--seed", type=int, default=20261116)
    p.add_argument("--label", default="final BODY/CORE validation")
    p = sub.add_parser("serve")
    p.add_argument("--package", type=Path, required=True)
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--diagnostic", action="store_true", help="show the machine labels at once; judgments are marked, never gold")
    p.add_argument("--no-browser", action="store_true")
    p = sub.add_parser("export")
    p.add_argument("--package", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("validate")
    p.add_argument("--package", type=Path, required=True)
    p.add_argument("--judgments", type=Path, required=True)
    p = sub.add_parser("score")
    p.add_argument("--package", type=Path, required=True)
    p.add_argument("--judgments", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--include-not-blind", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        return {"prepare": prepare, "serve": serve, "export": export, "validate": validate, "score": score}[arguments.command](arguments)
    except R.ReviewError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
