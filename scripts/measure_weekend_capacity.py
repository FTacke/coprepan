"""Capacity of the weekend qualification (2026-11-14/15), measured from its own fetch records (no request, read-only).

Usage: python scripts/measure_weekend_capacity.py --runtime <workspace> --out <out.json> [--evidence <dir>] [--authorization-id ID ...]

Why this exists: a fetch record's ``fetch_started_at`` is taken *before* the fetcher's origin pacing (``Fetcher._pace`` waits inside
``_request``), so ``fetch_finished_at - fetch_started_at`` -- the ``request_seconds`` of a canary measurement -- is the pacing wait
plus the transport, not a latency. What the records do allow:

* **exact transport** for the first request to an origin in a run (nothing to wait for);
* an **upper bound** for every later one: the pacing ends no earlier than the previous request to that origin started plus the
  policy's minimum interval (10 s; a Crawl-delay only lengthens it), so ``transport <= finished - max(started, previous_start + 10)``.

From these, per run: the wall time, the share of it the one executor spent on transport at most, and a **projection** (labelled as
such) of what interleaving origins -- still one request at a time, but the next origin while one waits -- would allow.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from coprepan import canary_driver as D, core_pipeline  # noqa: E402

SCHEMA = "coprepan-weekend-capacity/v1"
MIN_INTERVAL_SECONDS = 10.0  # config/acquisition_policy.json min_interval_seconds_per_origin
AUTHORIZATIONS = ("DOA-2026-11-14-2", "DOA-2026-11-15-1")


def _t(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


def _summary(values):
    if not values:
        return None
    ordered = sorted(values)
    return {"n": len(ordered), "median": round(statistics.median(ordered), 3),
            "p90": round(ordered[min(len(ordered) - 1, int(0.9 * len(ordered)))], 3), "max": round(ordered[-1], 3),
            "sum": round(sum(ordered), 1)}


def transport_times(records):
    """(exact first-request transports, upper bounds of the later ones), seconds, for one run's records."""
    by_origin = defaultdict(list)
    for record in records:
        by_origin[_origin(record["request"]["requested_url"])].append(record)
    exact, bounded = [], []
    for rows in by_origin.values():
        rows.sort(key=lambda r: r["fetch_started_at"])
        paced = None  # a lower bound of the instant the previous request to this origin left its pacing
        for row in rows:
            started, finished = _t(row["fetch_started_at"]).timestamp(), _t(row["fetch_finished_at"]).timestamp()
            if paced is None:
                exact.append(finished - started)
                paced = started
            else:
                paced = max(started, paced + MIN_INTERVAL_SECONDS)
                bounded.append(max(0.0, finished - paced))
    return exact, bounded, len(by_origin)


def between_records(records):
    """Seconds between one record's end and the next record's start, over the run: the driver's own work (parsing, packing, the
    ledger, the stages), when no request and no pacing wait is under way."""
    rows = sorted(records, key=lambda r: r["fetch_started_at"])
    gaps = [(_t(b["fetch_started_at"]) - _t(a["fetch_finished_at"])).total_seconds() for a, b in zip(rows, rows[1:])]
    return [g for g in gaps if g > 0]


def run_capacity(records):
    starts = [_t(r["fetch_started_at"]) for r in records]
    ends = [_t(r["fetch_finished_at"]) for r in records]
    wall = (max(ends) - min(starts)).total_seconds()
    exact, bounded, origins = transport_times(records)
    transport_at_most = sum(exact) + sum(bounded)
    body_bytes = sum(r["body_size_bytes"] for r in records if isinstance(r.get("body_size_bytes"), int))  # "not_applicable": no body
    return {
        "requests": len(records), "origins": origins, "wall_seconds": round(wall, 1),
        "requests_per_minute": round(60 * len(records) / wall, 2) if wall else None,
        "received_body_bytes": body_bytes,
        "transport_exact_first_request_per_origin": _summary(exact),
        "transport_upper_bound_later_requests": _summary(bounded),
        "executor_busy_share_at_most": round(transport_at_most / wall, 3) if wall else None,
        "inside_records_seconds": round(sum((_t(r["fetch_finished_at"]) - _t(r["fetch_started_at"])).total_seconds() for r in records), 1),
        "between_records": _summary(between_records(records)),
    }


def projection(runs):
    """What interleaving would allow, from the measured transports (a projection, not a measurement)."""
    exact = [x for r in runs.values() for x in r["_exact"]]
    if not exact:
        return None
    median = statistics.median(exact)
    return {
        "label": "PROJECTION",
        "basis": "median exact transport of a first request to an origin over every run; one request at a time; each origin at most "
                 "one request per 10 s",
        "median_transport_seconds": round(median, 3),
        "one_executor_ceiling_requests_per_hour": int(3600 / median),
        "sequential_by_origin_requests_per_hour_one_origin": int(3600 / (MIN_INTERVAL_SECONDS + median)),
        "origins_needed_to_fill_one_executor": round((MIN_INTERVAL_SECONDS + median) / median, 1),
        "note": "transport only; parsing, packing and the ledger add time per request; a publisher's Crawl-delay lowers its own share",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, default=REPOSITORY / "docs" / "canary" / "evidence")
    parser.add_argument("--authorization-id", action="append", default=None)
    arguments = parser.parse_args(argv)
    wanted = tuple(arguments.authorization_id or AUTHORIZATIONS)
    receipts = []
    for path in sorted(arguments.evidence.glob("*/canary-receipt-*.json")):
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if (receipt.get("operator_authorization") or {}).get("authorization_id") in wanted:
            receipts.append(receipt)
    workspace = core_pipeline.Workspace(arguments.runtime)
    by_run = defaultdict(list)
    run_ids = {r["run_id"] for r in receipts}
    for record in D.fetch_records(workspace):
        if record["run_id"] in run_ids:
            by_run[record["run_id"]].append(record)
    runs = {}
    for receipt in sorted(receipts, key=lambda r: r["started_at"]):
        records = by_run.get(receipt["run_id"], [])
        if not records:
            continue
        entry = run_capacity(records)
        exact, _, _ = transport_times(records)
        entry["wave"] = (receipt.get("operator_authorization") or {}).get("wave")
        entry["authorization_id"] = (receipt.get("operator_authorization") or {}).get("authorization_id")
        entry["_exact"] = exact
        runs[receipt["run_id"]] = entry
    result = {"schema": SCHEMA, "min_interval_seconds": MIN_INTERVAL_SECONDS, "authorizations": list(wanted),
              "projection": projection(runs),
              "runs": {k: {kk: vv for kk, vv in v.items() if kk != "_exact"} for k, v in runs.items()}}
    arguments.out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"runs": len(runs), "projection": result["projection"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
