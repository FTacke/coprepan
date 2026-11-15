"""The revised 24-hour wave as a draft plan of intake-controller/3 (CPD-0037). No request; not written to config/intake/plans/.

Usage: python scripts/build_24h_revision_plan.py --runtime <workspace> --out <plan.json> --summary <summary.json>

Outlets: those of the intake-readiness file that the weekend matrix rates QUALIFIED or QUALIFIED_WITH_LIMITS. Allowance per outlet
from the 24-hour intake of 2026-10-10/11 (new articles = new and dated in the window + new and undated at a later poll):
items per cycle = min(30, max(3, ceil(1.5 x new per hour))); per hour the same; in all min(900, max(80, ceil(1.5 x new in 24 h))).
An outlet without an October measurement keeps 3 / 3 / 80. Validated against the registry, the policy and every hold derived from
the stored evidence. The expected load is a projection from October and is labelled so.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from coprepan import canary_driver as D, core_pipeline, intake, policy, registry  # noqa: E402
from coprepan.canonical import record_json, sha256_bytes  # noqa: E402

BUDGET = intake.IntakeBudget(duration_seconds=86400, cycle_seconds=3600, item_requests_per_outlet=900, item_requests_per_outlet_hour=30,
                             item_requests_per_origin=1000, total_requests=8000, items_per_outlet_cycle=30, backlog_items_per_outlet_cycle=0,
                             drain_seconds=1800)
READINESS = REPOSITORY / "config" / "intake" / "intake_readiness_2026-10-10.1.json"
MATRIX = REPOSITORY / "docs" / "intake" / "qualification" / "weekend_qualification_2026-11-15.json"
OCTOBER = REPOSITORY / "docs" / "intake" / "reports" / "in1-20261010-24h" / "measurement.json"


def allowance(new_24h: int | None) -> dict[str, int]:
    if not new_24h:
        return intake.default_allowance(intake.IntakeBudget(**{**BUDGET.as_record(), "items_per_outlet_cycle": 3,
                                                                "item_requests_per_outlet_hour": 3, "item_requests_per_outlet": 80}))
    per_cycle = min(30, max(3, math.ceil(1.5 * new_24h / 24)))
    return {"items_per_cycle": per_cycle, "item_requests_per_hour": per_cycle, "item_requests": min(900, max(80, math.ceil(1.5 * new_24h)))}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    arguments = parser.parse_args(argv)
    readiness_bytes = READINESS.read_bytes()
    readiness = json.loads(readiness_bytes.decode("utf-8"))
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))["outlets"]
    october = json.loads(OCTOBER.read_text(encoding="utf-8"))["outlets"]
    wanted = {o for o, row in matrix.items() if row["QUALIFIED_FOR_NEXT_INTAKE"] in ("QUALIFIED", "QUALIFIED_WITH_LIMITS")}
    in_readiness = {e["outlet_id"] for e in readiness["outlets"]}
    volumes = {}
    for oid in sorted(wanted & in_readiness):
        first = (october.get(oid) or {}).get("candidates_first_listed_in_the_intake") or {}
        volumes[oid] = first.get("new_dated_in_window", 0) + first.get("new_undated_later_poll", 0) if oid in october else None
    acquisition_policy = policy.load_policy(REPOSITORY / "config" / "acquisition_policy.json")
    holds = D.access_holds_from_evidence(core_pipeline.Workspace(arguments.runtime), reclassify=True)
    # every hold the stored evidence gives (the weekend's included) is left out when the plan is made, not only refused after
    readiness = dict(readiness)
    readiness["held_origins"] = {**(readiness.get("held_origins") or {}), **{k: v for k, v in holds.items() if k.count("/") <= 2}}
    readiness["held_urls"] = {**(readiness.get("held_urls") or {}), **{k: v for k, v in holds.items() if k.count("/") > 2}}
    plan = intake.build_plan(readiness, intake_id="in3-24h-wave-draft", budget=BUDGET, policy=acquisition_policy,
                             registry_sha256=sha256_bytes((REPOSITORY / "config" / "outlet_registry.json").read_bytes()),
                             readiness_sha256=sha256_bytes(readiness_bytes), outlets=sorted(volumes),
                             allowances={oid: allowance(v) for oid, v in volumes.items()})
    registry_ = registry.load_registry(REPOSITORY / "config" / "outlet_registry.json")
    valid = "PASS"
    try:
        intake.validate_plan(plan, registry_, acquisition_policy, holds)
    except intake.IntakeStopped as error:
        valid = f"FAIL: {error}"
    arguments.out.write_bytes(record_json(plan))
    items_cap = sum(o["allowance"]["item_requests"] for o in plan["outlets"])
    expected_items = sum(min(v or 0, a["allowance"]["item_requests"]) for v, a in zip((volumes[o["outlet_id"]] for o in plan["outlets"]), plan["outlets"]))
    polls_per_outlet_day = 2566 / 87                                  # October: channel polls per outlet and day
    summary = {
        "plan": arguments.out.name, "plan_sha256": sha256_bytes(record_json(plan)), "controller": plan["controller"], "validate_plan": valid,
        "holds_considered": len(holds), "outlets": plan["totals"]["outlets"], "channels": plan["totals"]["channels"],
        "countries": len(plan["totals"]["countries"]), "left_out_by_the_plan": plan["left_out"],
        "qualified_by_the_weekend_but_not_in_the_readiness_file": sorted(wanted - in_readiness),
        "budget": plan["budget"],
        "allowance_classes": {f"{k} per cycle": sum(1 for o in plan["outlets"] if o["allowance"]["items_per_cycle"] == k)
                              for k in sorted({o["allowance"]["items_per_cycle"] for o in plan["outlets"]})},
        "projection": {"label": "PROJECTION from the October 24-hour intake, not a measurement",
                       "new_articles_october_in_these_outlets": sum(v or 0 for v in volumes.values()),
                       "item_requests_if_october_repeats": expected_items, "item_request_ceiling_sum": items_cap,
                       "channel_polls": round(polls_per_outlet_day * plan["totals"]["outlets"]),
                       "total_requests": expected_items + round(polls_per_outlet_day * plan["totals"]["outlets"])},
    }
    arguments.summary.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
