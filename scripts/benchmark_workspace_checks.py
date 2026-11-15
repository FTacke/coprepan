"""Benchmark of the workspace checks (CPD-0037): the full audit against the incremental check, on a copy of a real workspace and
on synthetic pack inventories. Local disk only; it writes into the directories it is given and nowhere else.

Usage:
  python scripts/benchmark_workspace_checks.py real --copy <a copy of a runtime workspace> --out <out.json>
  python scripts/benchmark_workspace_checks.py synthetic --base <empty local directory> --sizes 10000,50000,100000 --out <out.json>

``real`` (on the copy, never on the runtime workspace itself): one recovery.diagnose; the first checkpoint (no state: the full
audit and the rebase); an incremental checkpoint with nothing new; and with 100 and 1,000 request-log rows appended (chained,
well-formed), each with the number of sealed packs verified and files opened. ``synthetic``: N placeholder pack names in a
directory and a check state that holds them as verified -- what the incremental check costs per check at N packs (the listing
and the skip), and what loading the persisted state costs once per process. Nothing is projected here; the full audit's cost
at N packs is the measured per-pack cost times N, and is labelled a projection by the caller.
"""

from __future__ import annotations

import argparse
import builtins
import io
import json
import shutil
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from coprepan import incremental_check as I, pack, recovery  # noqa: E402
from coprepan.canonical import sha256_bytes  # noqa: E402
from coprepan.jsonl import CHAIN_FIELD  # noqa: E402


@contextmanager
def counting():
    counts = {"files_opened": 0, "packs_verified": 0}
    real_open, real_verify, real_io_open = builtins.open, pack.verify_sealed, io.open

    def opened(*a, **k):
        counts["files_opened"] += 1
        return real_open(*a, **k)

    def verified(*a, **k):
        counts["packs_verified"] += 1
        return real_verify(*a, **k)
    builtins.open, io.open, pack.verify_sealed = opened, opened, verified
    try:
        yield counts
    finally:
        builtins.open, io.open, pack.verify_sealed = real_open, real_io_open, real_verify


def timed(call):
    with counting() as counts:
        start = time.perf_counter()
        result = call()
        seconds = time.perf_counter() - start
    return result, {"seconds": round(seconds, 2), **counts}


def append_request_rows(root: Path, n: int) -> None:
    path = root / "requests" / "requests.jsonl"
    last = path.read_bytes().rstrip(b"\n").rsplit(b"\n", 1)[-1] + b"\n"
    template = json.loads(last)
    previous = sha256_bytes(last)
    with open(path, "ab") as handle:
        for k in range(n):
            row = {**template, "event": "PLANNED", "request_id": f"rq1:{'b' * 24}{k:08x}", "url": f"https://bench.test/{k}",
                   CHAIN_FIELD: previous}
            row.pop("result", None)
            line = json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
            handle.write(line)
            previous = sha256_bytes(line)
        # end each planned request, so that the bench leaves no intent open
    with open(path, "rb") as handle:
        pass


def real(arguments) -> dict:
    root = arguments.copy
    if not (root / "packs").is_dir():
        raise SystemExit(f"not a workspace copy: {root}")
    for leftover in (root / "checks").glob("verified-*.state") if (root / "checks").is_dir() else []:
        leftover.unlink()
    now = datetime.now(timezone.utc)
    out = {"packs_files": sum(1 for _ in (root / "packs").iterdir()), "sealed_packs": sum(1 for p in (root / "packs").glob("*.pack.json"))}
    diagnosis, out["full_audit"] = timed(lambda: recovery.diagnose(root))
    out["full_audit"]["classification"] = diagnosis["classification"]
    (d1, state), out["first_checkpoint_full_and_rebase"] = timed(lambda: I.checkpoint(root, None, now=now))
    out["first_checkpoint_full_and_rebase"]["mode"] = d1["check"]["mode"]
    _, out["state_load_once_per_process"] = timed(lambda: I.load(root))
    (d2, state), out["incremental_nothing_new"] = timed(lambda: I.checkpoint(root, state, now=now + timedelta(minutes=1)))
    out["incremental_nothing_new"].update(mode=d2["check"]["mode"], scope=d2["check"].get("scope"))
    for n in (100, 1000):
        append_request_rows(root, n)
        (dn, state), out[f"incremental_{n}_new_request_rows"] = timed(lambda: I.checkpoint(root, state, now=now + timedelta(minutes=2)))
        out[f"incremental_{n}_new_request_rows"].update(mode=dn["check"]["mode"], classification=dn["classification"])
    return out


def synthetic(arguments) -> dict:
    results = {}
    for n in [int(x) for x in arguments.sizes.split(",")]:
        root = arguments.base / f"ws-{n}"
        if root.exists():
            shutil.rmtree(root)
        (root / "packs").mkdir(parents=True)
        state = I.CheckState(valid=True, reason=None, full_at=I.format_instant(datetime.now(timezone.utc)))
        start = time.perf_counter()
        for k in range(n):
            day = (datetime(2025, 1, 1) + timedelta(days=(k // 100) % 336)).strftime("%Y%m%d")   # unique (outlet, day, seq) per k
            identifier = pack.pack_id(f"zz_bench_{k % 100:03d}", day, k // 33600)
            (root / "packs" / f"{identifier}.warc.gz").touch()
            state.packs[identifier] = {"entries": [[f"ft1:{k:064x}", "FETCHED"]], "audited_at": state.full_at}
            state.held_by[f"ft1:{k:064x}"] = identifier
        made = time.perf_counter() - start
        state.packs = dict(state.packs)
        now = datetime.now(timezone.utc)
        (d, state), check = timed(lambda: I.checkpoint(root, state, now=now, audit=I.AuditBudget(packs=0, layers=0)))
        # the persisted form: one full row holding N packs, loaded once per process
        I._persist(root, state, {"kind": "full", "at": state.full_at, "packs": state.packs})
        _, load = timed(lambda: I.load(root))
        results[str(n)] = {"placeholders_made_seconds": round(made, 1), "incremental_check": {**check, "mode": d["check"]["mode"],
                           "packs_skipped_as_verified": (d["check"].get("scope") or {}).get("packs_skipped_as_verified")},
                           "state_load": load, "state_file_bytes": sum(p.stat().st_size for p in (root / "checks").glob("*.state"))}
        shutil.rmtree(root)
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("real")
    one.add_argument("--copy", type=Path, required=True)
    one.add_argument("--out", type=Path, required=True)
    two = sub.add_parser("synthetic")
    two.add_argument("--base", type=Path, required=True)
    two.add_argument("--sizes", default="10000,50000,100000")
    two.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args(argv)
    result = real(arguments) if arguments.command == "real" else synthetic(arguments)
    arguments.out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
