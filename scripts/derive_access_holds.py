"""The access holds in force, derived from every preserved answer of the runtime workspace (read-only; CPD-0027).

    python scripts/derive_access_holds.py --out <file>

For every preserved answer that the classifier of its day or the classifier in force reads as an access
control: what was asked, what answered, the class recorded then, the class now, and what it holds
under the scope table in force — the origin, that URL, or nothing. The file is a dated snapshot of a
derivation the driver repeats at every start; it decides nothing by being written.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from coprepan import access_control, acquisition, canary_driver, pack, policy, storage_roots  # noqa: E402
from coprepan.canonical import record_json  # noqa: E402
from coprepan.core_pipeline import Workspace  # noqa: E402

SCHEMA = "coprepan-access-holds/v1"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prepared-on", required=True)
    arguments = parser.parse_args(argv)
    if arguments.out.exists():
        raise SystemExit(f"{arguments.out.name} exists: a snapshot is written once")
    workspace = Workspace(storage_roots.resolve_configured_roles(env=storage_roots.workstation_environment())["RUNTIME"])
    rows = []
    for identifier in canary_driver.pack_ids(workspace):
        sealed = workspace.packs / f"{identifier}.warc.gz"
        path = sealed if sealed.exists() else workspace.packs / f"{identifier}.warc.gz.open"
        for entry in pack.scan(path, identifier):
            record = pack.read_fetch_record(path, entry)
            if record["outcome"] != acquisition.OUTCOME_FETCHED:
                continue
            stored = record["policy"]["access_class_observed"]
            response = record["response"]
            now = stored
            if stored not in (access_control.LOGIN_REDIRECT, access_control.PAYWALL_REDIRECT):
                now = access_control.classify_response(response["status"], [(h[0], h[1]) for h in response["headers"]], pack.read_body(path, entry))
            before = "origin" if stored in ("auth_required", "forbidden", "unavailable_for_legal_reasons", "rate_limited", "captcha", "bot_challenge") else None
            scope = access_control.hold_scope(record["fetch_kind"], now)
            if before is None and scope is None and now == access_control.NONE_OBSERVED:
                continue
            origin = policy._origin(response["final_url"])
            rows.append({"outlet_id": record["outlet_id"], "run_id": record["run_id"], "fetch_id": record["fetch_id"], "fetch_kind": record["fetch_kind"],
                         "url": response["final_url"], "status": response["status"], "class_recorded": stored, "class_now": now,
                         "held_until_2026_10_09": origin if before else None, "scope_now": scope,
                         "held_now": origin if scope == access_control.SCOPE_ORIGIN else response["final_url"] if scope == access_control.SCOPE_URL else None})
    rows.sort(key=lambda row: (row["outlet_id"], row["run_id"], row["fetch_id"]))
    holds = canary_driver.access_holds_from_evidence(workspace, reclassify=True)
    origins = sorted(key for key in holds if "/" not in key.split("://", 1)[-1])
    urls = sorted(key for key in holds if key not in origins)
    document = {"schema": SCHEMA, "prepared_on": arguments.prepared_on,
                "what_this_is": "a snapshot of what the driver derives at every start from the preserved answers; no hold is set or lifted by this file",
                "classifier": access_control.CLASSIFIER_VERSION, "hold_scope": access_control.HOLD_SCOPE_VERSION,
                "robots_decision_semantics": policy.ROBOTS_DECISION_SEMANTICS,
                "held_origins": {key: holds[key] for key in origins}, "held_urls": {key: holds[key] for key in urls},
                "origins_held_under_the_rule_until_2026_10_09": sorted({row["held_until_2026_10_09"] for row in rows if row["held_until_2026_10_09"]}),
                "answers": rows}
    arguments.out.write_bytes(record_json(document))
    print(json.dumps({"held_origins": len(origins), "held_urls": len(urls), "answers": len(rows),
                      "origins_before": len(document["origins_held_under_the_rule_until_2026_10_09"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
