"""Human gold for BODY and CORE (CPD-0044): build gold packages, serve the reviewer, freeze the gold, and only then predict and
score. Offline; no publisher request; no model.

Usage:
  python scripts/gold_review.py prepare-practice (--runtime <ws> | --page-cache <cache>) --out-dir <dir> [--n 5] [--seed 7]
  python scripts/gold_review.py prepare-holdout  --runtime <ws> --out-dir <dir> --development <development_population.json>
                                                 [--per-outlet 2] --seed <int>
  python scripts/gold_review.py serve    --package <dir> [--port 8766] [--no-browser]
  python scripts/gold_review.py status   --package <dir>
  python scripts/gold_review.py snapshot --package <dir> --out <events copy .jsonl>
  python scripts/gold_review.py freeze   --package <dir> --out <gold .json in the repository> --by "<who>"
  python scripts/gold_review.py predict  --package <dir> --gold <gold .json> (--runtime <ws> | --page-cache <cache>)
  python scripts/gold_review.py score    --package <dir> --gold <gold .json> --predictions <file> --out <result .json>

``prepare-practice`` draws development pages that are in no control or package (a ``PRACTICE`` package, never scored).
``prepare-holdout`` builds the ``HOLDOUT`` package from the runs of ``config/validation/holdout_runs.json`` alone: their 2xx item
pages minus every development document (by fetch id and by address), ``--per-outlet`` drawn at random per outlet. No extractor,
gate or status runs in either. ``predict`` refuses unless the package is frozen and the gold file is the frozen one, tracked by
git and unchanged against ``HEAD`` (committed before any prediction). Package directories are refused inside the repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import webbrowser
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))
sys.path.insert(0, str(REPOSITORY / "scripts"))

from coprepan import core_pipeline, extraction as E, gold_review as G, gold_score as GS, pack  # noqa: E402
from coprepan.validation_holdout import holdout_runs  # noqa: E402
import study_phase3_metadata as S3  # noqa: E402

CONTROL_MANIFESTS = ("docs/intake/quality/phase3_blind_control_2026-11-15/manifest.json",
                     "docs/intake/quality/body_quality_control_2026-11-15/manifest.json",
                     "docs/intake/quality/body_final_review_2026-11-16/manifest.json")


def _country() -> dict[str, str]:
    registry = json.loads((REPOSITORY / "config" / "outlet_registry.json").read_text(encoding="utf-8"))
    return {o["outlet_id"]: o["country_id"] for o in registry["outlets"]}


def _decoded(page, body) -> str:
    try:
        html, _ = E._decode(E.decode_content(body, page["args"]["content_encoding"] or "identity"), page["args"]["declared_charset"])
    except E.ContentDecodingError:
        html = ""
    return html


def _url_key(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()[:16]


def prepare_practice(arguments) -> int:
    used = set()
    for relative in CONTROL_MANIFESTS:
        path = REPOSITORY / relative
        if path.is_file():
            for c in json.loads(path.read_text(encoding="utf-8")).get("cases", []):
                used |= set(c.get("fetch_ids") or [c["fetch_id"]])      # the phase-3 control names several fetches per case
    import random

    rng = random.Random(arguments.seed)
    chosen, seen = [], 0                       # reservoir sample: n pages held, never the whole population
    for page, body in S3.stored_pages(arguments):
        if page["fetch_id"] in used:
            continue
        seen += 1
        if len(chosen) < arguments.n:
            chosen.append((page, body))
        else:
            k = rng.randrange(seen)
            if k < arguments.n:
                chosen[k] = (page, body)
    chosen.sort(key=lambda pb: pb[0]["fetch_id"])
    rng.shuffle(chosen)
    country = _country()
    cases, materials = [], {}
    for k, (page, body) in enumerate(chosen, 1):
        cid = f"U{k:02d}"
        case, source = G.case_material(cid, page, _decoded(page, body), country_id=country.get(page["outlet_id"], "unknown"))
        materials[page["fetch_id"]] = (case, source)
        cases.append({"case_id": cid, "fetch_id": page["fetch_id"], "component": "practice"})
    manifest = G.write_package(arguments.out_dir, kind="PRACTICE", cases=cases, materials=materials,
                               design={"design": "practice: development pages in no control or package, drawn at random", "seed": arguments.seed},
                               meta={"label": "practice -- to learn the reviewer; never gold"}, repository=REPOSITORY)
    print(json.dumps({"package_id": manifest["package_id"], "kind": "PRACTICE", "cases": len(cases),
                      "segments": [c["segments"] for c in manifest["cases"]], "out": str(arguments.out_dir)}))
    return 0


def prepare_holdout(arguments) -> int:
    runs = holdout_runs()
    if not runs:
        raise G.GoldError("config/validation/holdout_runs.json lists no run: no holdout has been acquired")
    development = json.loads(arguments.development.read_text(encoding="utf-8"))
    dev_ids, dev_urls = set(development["fetch_ids"]), set(development["url_sha256_16"])
    arguments.include_holdout = True
    frame, pages = [], {}
    import study_content_quality as S

    workspace = core_pipeline.Workspace(arguments.runtime)
    excluded = {"development_fetch": 0, "development_address": 0}
    for record, path, entry in S.pages(workspace, include_holdout=True):
        if record["run_id"] not in runs:
            continue
        url = record["request"]["requested_url"]
        if record["fetch_id"] in dev_ids:
            excluded["development_fetch"] += 1
            continue
        if _url_key(url) in dev_urls:
            excluded["development_address"] += 1
            continue
        frame.append({"fetch_id": record["fetch_id"], "outlet_id": record["outlet_id"]})
        pages[record["fetch_id"]] = (record, path, entry)
    cases = G.draw_per_outlet(frame, per_outlet=arguments.per_outlet, seed=arguments.seed)
    country = _country()
    materials = {}
    for c in cases:
        record, path, entry = pages[c["fetch_id"]]
        stored = pack.read_fetch_record(path, entry)
        page = {"fetch_id": record["fetch_id"], "outlet_id": record["outlet_id"], "url": record["request"]["requested_url"],
                "fetched_at": record["fetch_started_at"], "body_sha256": stored["body_sha256"],
                "args": core_pipeline._extraction_arguments(stored)}
        body = pack.read_body(path, entry)
        materials[c["fetch_id"]] = G.case_material(c["case_id"], page, _decoded(page, body), country_id=country.get(record["outlet_id"], "unknown"))
        c["cluster"] = c["case_id"]
    design = {"design": "every outlet of the frame a stratum taken with certainty; documents drawn at random without replacement "
                        "within it", "seed": arguments.seed, "per_outlet": arguments.per_outlet, "runs": sorted(runs),
              "frame": {"documents": len(frame), "outlets": len({r['outlet_id'] for r in frame}), "excluded": excluded},
              "development_population_sha256": hashlib.sha256(arguments.development.read_bytes()).hexdigest()}
    manifest = G.write_package(arguments.out_dir, kind="HOLDOUT", cases=cases, materials=materials, design=design,
                               meta={"label": arguments.label}, repository=REPOSITORY)
    print(json.dumps({"package_id": manifest["package_id"], "cases": len(cases), "frame": design["frame"], "out": str(arguments.out_dir)}))
    return 0


def development_population(arguments) -> int:
    """Every stored 2xx item page outside the holdout register: the development population -- what development has seen. Ids,
    address digests and counts only."""
    import study_content_quality as S
    from collections import Counter, defaultdict

    workspace = core_pipeline.Workspace(arguments.runtime)
    ids, urls, per_outlet, runs = [], set(), Counter(), defaultdict(set)
    first, last = {}, {}
    for record, _, _ in S.pages(workspace):
        o, t = record["outlet_id"], record["fetch_started_at"]
        ids.append(record["fetch_id"])
        urls.add(_url_key(record["request"]["requested_url"]))
        per_outlet[o] += 1
        runs[o].add(record["run_id"])
        first[o], last[o] = min(first.get(o, t), t), max(last.get(o, t), t)
    country = _country()
    doc = {"schema": "coprepan-development-population/v1", "decision": "CPD-0044", "date": arguments.date,
           "definition": "every stored 2xx item page of the runtime workspace outside config/validation/holdout_runs.json -- the "
                         "population every BODY/CORE development study (CPD-0038..0043) read in full",
           "pages": len(ids), "outlets": len(per_outlet), "runs": len({r for v in runs.values() for r in v}),
           "fetched_from": min(first.values()) if first else None, "fetched_to": max(last.values()) if last else None,
           "by_outlet": {o: {"country_id": country.get(o, "unknown"), "pages": n, "runs": len(runs[o]), "first": first[o], "last": last[o]}
                         for o, n in sorted(per_outlet.items())},
           "fetch_ids_sha256": hashlib.sha256("\n".join(sorted(ids)).encode("ascii")).hexdigest(),
           "fetch_ids": sorted(ids), "url_sha256_16": sorted(urls),
           "url_key": "sha256 of the requested URL as recorded, first 16 hex"}
    arguments.out.write_bytes((json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(json.dumps({k: doc[k] for k in ("pages", "outlets", "runs", "fetched_from", "fetched_to", "fetch_ids_sha256")}))
    return 0


def serve(arguments) -> int:
    package = G.Package(arguments.package)
    server = G.make_server(package, port=arguments.port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Gold review of package {package.package_id} ({package.kind}, {len(package.case_ids)} cases) at {url}\n"
          "Answers are saved as you go; stop with Ctrl+C.", flush=True)
    if not arguments.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def status(arguments) -> int:
    package = G.Package(arguments.package)
    journal = G.Journal(package)
    closed = [c for c in package.case_ids if journal.state[c]["finalized"]]
    print(json.dumps({"package_id": package.package_id, "kind": package.kind, "cases": len(package.case_ids), "closed": len(closed),
                      "started": sum(1 for c in package.case_ids if journal.state[c]["events"]), "events": len(journal.events),
                      "torn_lines_left_out": journal.torn, "frozen": package.frozen}, indent=1))
    return 0


def snapshot(arguments) -> int:
    package = G.Package(arguments.package)
    data = (package.directory / "judgments" / "events.jsonl").read_bytes()
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_bytes(data)
    print(json.dumps({"events_sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "out": str(arguments.out)}))
    return 0


def freeze(arguments) -> int:
    package = G.Package(arguments.package)
    case_ids, scope = None, "all cases"
    if arguments.replicate is not None:
        case_ids = [c["case_id"] for c in package.design()["cases"] if c.get("replicate") is not None and c["replicate"] <= arguments.replicate]
        scope = f"replicates 1..{arguments.replicate}"
    marker = G.freeze(package, G.Journal(package), arguments.out, by=arguments.by, case_ids=case_ids, scope=scope)
    print(json.dumps(marker, indent=1))
    print("Commit the gold file now (explicit pathspec), before any prediction is made.")
    return 0


def _committed(path: Path) -> None:
    relative = path.resolve().relative_to(REPOSITORY.resolve()).as_posix()
    tracked = subprocess.run(["git", "-C", str(REPOSITORY), "ls-files", "--error-unmatch", relative], capture_output=True)
    unchanged = subprocess.run(["git", "-C", str(REPOSITORY), "diff", "--quiet", "HEAD", "--", relative], capture_output=True)
    if tracked.returncode != 0 or unchanged.returncode != 0:
        raise G.GoldError(f"{relative}: the gold must be committed and unchanged before any prediction is made")


def predict(arguments) -> int:
    package = G.Package(arguments.package)
    G.load_gold(package, arguments.gold)
    _committed(arguments.gold)
    wanted = {package.cases[c]["fetch_id"]: c for c in package.case_ids}
    arguments.include_holdout = True
    out = {}
    for page, body in S3.stored_pages(arguments):
        cid = wanted.get(page["fetch_id"])
        if cid is None:
            continue
        if hashlib.sha256(body).hexdigest() != package.cases[cid]["body_sha256"]:
            raise G.GoldError(f"{cid}: the stored body is not the one the package was built from")
        out[cid] = GS.predict_page(page, body)
    missing = sorted(set(package.case_ids) - set(out))
    if missing:
        raise G.GoldError(f"no stored page for {len(missing)} case(s): {missing[:5]}")
    doc = {"schema": GS.PREDICTIONS_SCHEMA, "package_id": package.package_id, "gold_sha256": package.frozen["gold_sha256"],
           "systems": {k: {"extractor": v["extractor"].stage_version, "quality": v["quality"], "status": v["status"]}
                       for k, v in GS.SYSTEMS.items()}, "cases": out}
    data = (json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    target = package.directory / "predictions" / f"predictions_{package.frozen['gold_sha256'][:12]}.json"
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        raise G.GoldError(f"{target}: exists -- predictions are written once")
    target.write_bytes(data)
    print(json.dumps({"predictions": str(target), "sha256": hashlib.sha256(data).hexdigest(), "cases": len(out)}))
    return 0


def score(arguments) -> int:
    package = G.Package(arguments.package)
    gold = G.load_gold(package, arguments.gold)
    data = arguments.predictions.read_bytes()
    predictions = json.loads(data)
    predictions["sha256"] = hashlib.sha256(data).hexdigest()
    result = GS.score(package, gold, predictions)
    arguments.out.write_bytes((json.dumps(result, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(json.dumps({k: result[k] for k in ("cases", "probability_cases", "counts")}, ensure_ascii=False)[:3000])
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare-practice")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--runtime", type=Path)
    src.add_argument("--page-cache", type=Path)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--n", type=int, default=5)
    p.add_argument("--seed", type=int, default=7)
    p = sub.add_parser("prepare-holdout")
    p.add_argument("--runtime", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--development", type=Path, required=True)
    p.add_argument("--per-outlet", type=int, default=2)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--label", default="independent BODY/CORE validation holdout")
    p = sub.add_parser("development-population")
    p.add_argument("--runtime", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--date", required=True)
    p = sub.add_parser("serve")
    p.add_argument("--package", type=Path, required=True)
    p.add_argument("--port", type=int, default=8766)
    p.add_argument("--no-browser", action="store_true")
    for name in ("status",):
        p = sub.add_parser(name)
        p.add_argument("--package", type=Path, required=True)
    p = sub.add_parser("snapshot")
    p.add_argument("--package", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("freeze")
    p.add_argument("--package", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--by", required=True)
    p.add_argument("--replicate", type=int, help="freeze replicates 1..N only (decided on effort, before any prediction)")
    p = sub.add_parser("predict")
    p.add_argument("--package", type=Path, required=True)
    p.add_argument("--gold", type=Path, required=True)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--runtime", type=Path)
    src.add_argument("--page-cache", type=Path)
    p = sub.add_parser("score")
    p.add_argument("--package", type=Path, required=True)
    p.add_argument("--gold", type=Path, required=True)
    p.add_argument("--predictions", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args(argv)
    commands = {"prepare-practice": prepare_practice, "prepare-holdout": prepare_holdout,
                "development-population": development_population, "serve": serve, "status": status,
                "snapshot": snapshot, "freeze": freeze, "predict": predict, "score": score}
    try:
        return commands[arguments.command](arguments)
    except G.GoldError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
