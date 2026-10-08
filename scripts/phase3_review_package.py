"""Phase 3: a blinded review package from preserved item fetches (2026-10-08; CPD-0018).

Reads the preserved packs of one acquisition run from the preservation root (masters verified), draws
the sample by the design (``docs/extraction/GOLD_SAMPLE_DESIGN.md`` §3), runs the baseline and the
pinned classical candidates on the same preserved bytes — each twice, a different answer stops the
run — and writes a review package with the candidates under blinded labels.

**No request is made**: the socket guard of the canary verification is on for the whole run, and no
tool is given an address. No reference is created: every decision form is empty.

What it writes, under ``--out`` (a directory that must not exist, outside the checkout)::

    reviewer/             what a reviewer gets: index, cases (blinded), the codebook
    operator_only/        NOT for a reviewer before every case is decided:
                          the blinding key, the evaluation record, every arm's full output per case, the environment
    package_manifest.json every file with its digest; the key's digest; names no arm against a label

and, with ``--evidence-dir``, the compact evidence for the repository: the sample manifest and the
package manifest (no page text, no arm output).

Run it in the environment of the candidates (extra ``phase3``), from the checkout::

    PYTHONPATH=src python scripts/phase3_review_package.py --receipt <canary receipt> --sample-id <id> --seed <seed> \
        --per-stratum <n> --out <RUNTIME root>/phase3/<id> --evidence-dir docs/extraction/phase3/<id>
"""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

from coprepan import acquisition, canary_evidence, core_pipeline, extraction, extraction_eval, extractor_candidates, naming, registry, storage_roots
from coprepan.canonical import canonical_json, record_json, sha256_bytes, sha256_file, write_bytes_exclusive
from coprepan.pack import utc_day_of
from coprepan.storage_roots import CHECKOUT

STRATA = ("outlet", "country", "outlet_type", "channel_kind", "response_class", "time_slice")
CODEBOOK = CHECKOUT / "docs" / "extraction" / "REVIEW_CODEBOOK_v1.md"
CODEBOOK_VERSION = 1
# Strings that would tell a reviewer which candidate is which. None may occur in a reviewer file.
ARM_MARKS = ("trafilatura", "readability", "justext", "baseline_html")


def response_class(record: dict) -> str:
    status, content_type = record["response"]["status"], record["response"]["content_type"]
    if not 200 <= status < 300:
        return "error_status"
    return "2xx_html" if content_type in extraction.HTML_TYPES else "non_html"


def build_frame(run_id: str, pack_identifiers: list[str], workspace: core_pipeline.Workspace, preservation_root: Path,
                registered: registry.Registry) -> tuple[list[dict], dict]:
    """Every item fetch of the run that is RAW_PRESERVED, with strata from the registry and the fetch record only."""
    states = workspace.ledger().states()
    frame, held_packs = [], {}
    for identifier in pack_identifiers:
        held = core_pipeline.open_preserved_pack(preservation_root, identifier)   # masters verified, or it raises
        held_packs[identifier] = held
        for fetch_id in held.entries:
            record = held.fetch_record(fetch_id)
            if (record["run_id"] != run_id or record["fetch_kind"] != acquisition.FETCH_KIND_ITEM
                    or record["outcome"] != acquisition.OUTCOME_FETCHED or states.get(fetch_id) != "RAW_PRESERVED"):
                continue
            outlet = registered.resolve(record["outlet_id"])
            channel_id = (record.get("discovery") or {}).get("channel_id")
            channel_kind = next((c["kind"] for c in outlet["channels"] if c["channel_id"] == channel_id), extraction.UNKNOWN)
            frame.append({
                "case_id": f"case-{record['body_sha256'][:16]}", "fetch_id": fetch_id, "body_sha256": record["body_sha256"],
                "pack_id": identifier, "outlet_id": record["outlet_id"],
                "declared_content_type": record["response"]["content_type"],
                "declared_charset": extraction.declared_charset_of(record["response"]["headers"]),
                "content_encoding": record["response"]["content_encoding"],
                "strata": {"outlet": record["outlet_id"], "country": outlet["country_id"], "outlet_type": outlet.get("outlet_type", extraction.UNKNOWN),
                           "channel_kind": channel_kind, "response_class": response_class(record),
                           "time_slice": utc_day_of(record["fetch_started_at"]), "part": "stratified"},
            })
    return frame, held_packs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a blinded extraction review package from preserved item fetches. No request.")
    parser.add_argument("--receipt", type=Path, required=True, help="the receipt of the acquisition run whose preserved items are the frame")
    parser.add_argument("--sample-id", required=True)
    parser.add_argument("--seed", required=True, help="the seed of the draw (recorded)")
    parser.add_argument("--per-stratum", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True, help="package directory; must not exist; not inside the checkout")
    parser.add_argument("--evidence-dir", type=Path, help="where the sample and package manifests are written for the repository")
    arguments = parser.parse_args(argv)

    out = arguments.out.resolve()
    if out.exists() or CHECKOUT in out.parents or out == CHECKOUT:
        raise SystemExit("--out must be a new directory outside the checkout: a review package holds page text")
    receipt = json.loads(arguments.receipt.read_text(encoding="utf-8"))
    roles = storage_roots.resolve_configured_roles(env=storage_roots.workstation_environment())
    workspace = core_pipeline.Workspace(roles["RUNTIME"])
    registered = registry.load_registry(CHECKOUT / "config" / "outlet_registry.json")

    with canary_evidence.network_unavailable():
        frame, held_packs = build_frame(receipt["run_id"], receipt["packs"], workspace, roles["PRESERVATION"], registered)
        if not frame:
            raise SystemExit("the frame is empty: no preserved item fetch of this run")
        chosen = extraction_eval.draw_sample(frame, strata=STRATA, per_stratum=arguments.per_stratum, seed=arguments.seed)
        cells = Counter(tuple(case["strata"][name] for name in STRATA) for case in frame)
        description = (f"item fetches of run {receipt['run_id']} that are RAW_PRESERVED, read from the preservation root; packs "
                       f"{', '.join(receipt['packs'])}; {len(frame)} cases in {len(cells)} cell(s) of the strata; "
                       f"baseline {receipt['baseline_id']}")
        manifest = extraction_eval.sample_manifest(chosen, sample_id=arguments.sample_id, strata=STRATA, seed=arguments.seed,
                                                   per_stratum=arguments.per_stratum, frame_description=description)

        def body_of(case):
            return held_packs[case["pack_id"]].body(case["fetch_id"])

        arms = [extraction.BASELINE, *extractor_candidates.CANDIDATES.values()]
        result = extraction_eval.evaluate(manifest, arms, body_of)     # every arm twice per case; a difference raises
        blind_seed = secrets.token_hex(32)                             # known to the key file only
        staging = out / "reviewer"
        out.mkdir(parents=True)
        extraction_eval.review_package(manifest, result, body_of, staging, blind_seed=blind_seed)

    hidden = out / "operator_only"
    hidden.mkdir()
    shutil.move(str(staging / "blinding_key.json"), str(hidden / "blinding_key.json"))
    write_bytes_exclusive(staging / CODEBOOK.name, CODEBOOK.read_bytes())
    write_bytes_exclusive(hidden / "evaluation.json", record_json(extraction_eval.public_record(result)))
    for case_id, outputs in result["_outputs"].items():
        (hidden / "arm_outputs" / case_id).mkdir(parents=True)
        for arm_name, record in outputs.items():
            write_bytes_exclusive(hidden / "arm_outputs" / case_id / (arm_name.replace("/", "@") + ".json"), record_json(record))
    freeze = subprocess.run([sys.executable, "-m", "pip", "freeze", "--disable-pip-version-check"], capture_output=True, text=True, check=True).stdout
    write_bytes_exclusive(hidden / "environment.txt", ("python " + sys.version.split()[0] + "\n" + freeze.replace("\r\n", "\n")).encode("utf-8"))

    # A reviewer file names no arm. Checked on what was written, not assumed.
    leaks = [path.relative_to(out).as_posix() for path in sorted(staging.rglob("*")) if path.is_file() and path.name != CODEBOOK.name
             and any(mark in path.read_bytes().lower() for mark in (m.encode("ascii") for m in ARM_MARKS))]
    if leaks or (staging / "blinding_key.json").exists():
        raise SystemExit(f"blinding failed: {leaks or 'the key is in the reviewer directory'}")
    undecided = [path.name for path in sorted((staging / "cases").glob("*.json"))
                 if json.loads(path.read_text(encoding="utf-8"))["decision"]["state"] is not None]
    if undecided:
        raise SystemExit(f"a decision form is not empty: {undecided}")

    def listing(directory: Path) -> list[dict]:
        rows = []
        for path in sorted(p for p in directory.rglob("*") if p.is_file()):
            digest, size = sha256_file(path)
            rows.append({"path": path.relative_to(out).as_posix(), "sha256": digest, "size_bytes": size})
        return rows

    key_digest, _ = sha256_file(hidden / "blinding_key.json")
    package = {
        "schema": naming.schema_id("extraction-review-package", 1), "sample_id": manifest["sample_id"], "sample_sha256": manifest["sample_sha256"],
        "evaluation_sha256": result["evaluation_sha256"], "harness": extraction_eval.HARNESS_VERSION,
        "codebook": {"file": CODEBOOK.name, "version": CODEBOOK_VERSION, "sha256": sha256_bytes(CODEBOOK.read_bytes())},
        "arms": sorted(arm.stage_version for arm in arms),
        "candidate_tools": {extractor_candidates.DISTRIBUTION_OF[name]: extractor_candidates.PINS[extractor_candidates.DISTRIBUTION_OF[name]]
                            for name in extractor_candidates.CANDIDATES},
        "cases": len(manifest["cases"]), "labels_per_case": len(arms),
        "blinding": {"labels": "A.. per case, order from a seed generated at build time and stored in the key only",
                     "key_file": "operator_only/blinding_key.json", "key_sha256": key_digest,
                     "reviewer_files_name_no_arm": True},
        "decision_forms_empty": True, "source_run": receipt["run_id"], "source_baseline": receipt["baseline_id"],
        "reviewer_files": listing(staging), "operator_only_files": listing(hidden),
    }
    package["package_sha256"] = sha256_bytes(canonical_json(package))
    write_bytes_exclusive(out / "package_manifest.json", record_json(package))
    if arguments.evidence_dir:
        arguments.evidence_dir.mkdir(parents=True, exist_ok=True)
        write_bytes_exclusive(arguments.evidence_dir / "sample_manifest.json", record_json(manifest))
        write_bytes_exclusive(arguments.evidence_dir / "package_manifest.json", record_json(package))
    states = Counter(arm["state"] for case in result["cases"] for arm in case["arms"].values())
    print(json.dumps({"frame": len(frame), "cells": len(cells), "sample": len(manifest["cases"]), "sample_sha256": manifest["sample_sha256"],
                      "arms": len(arms), "arm_states": dict(states), "evaluation_sha256": result["evaluation_sha256"],
                      "key_sha256": key_digest, "package_sha256": package["package_sha256"], "out": out.name}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
