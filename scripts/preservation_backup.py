"""The BACKUP of the PRESERVATION primary (crosscorpus-storage/v1 §9; NEW_FS Phase D). Mechanics: ``coprepan.primary_backup``.

    init-root --root DIR --operator NAME          make DIR a BACKUP root (once; new or empty, another volume than the primary)
    run       [--evidence-dir DIR] [--ignore-windows]
                                                   the regular, scheduled run (INCREMENTAL, CPD-0033): one listing of each root,
                                                   new objects copied and verified, a budgeted fixity slice on both roots,
                                                   a rotating restore test, receipt; throttled, time-budgeted, yields to CO.RA.PAN
    run --full [--workers 3] [--samples 25] [--evidence-dir DIR] [--ignore-windows]
                                                   the operator-ordered FULL run: fresh baseline of the primary (every object
                                                   re-hashed) -> copy -> unbuffered verification of every object -> restore -> receipt
    status                                         the receipt's state as the contract status reads it, and the backup's health
    schedule                                       the registered task COPREPAN_PreservationBackup against the policy's calendar
                                                   (read-only; Windows)
    seed-cache [--ignore-windows]                  fill the RUNTIME manifest cache of the primary from the verified BACKUP root:
                                                   local reads only, no contact with the share (CPD-0035)

Both roots come from the workstation's ``.env`` (``COPREPAN_PRESERVATION_ROOT`` with ``COPREPAN_PRESERVATION_TARGET_ID``, checked
(T2); ``COPREPAN_BACKUP_ROOT``). With ``--holding LEGACY`` (CPD-0032) the primary is the LEGACY archive root
``COPREPAN_LEGACY_ARCHIVE_ROOT``, whose identity must be ``COPREPAN_LEGACY_ARCHIVE_TARGET_ID`` (T2, required), and the backup root
is ``COPREPAN_LEGACY_BACKUP_ROOT``; a backup root names its holding and is refused for another one. Nothing here writes to the
primary, deletes an object or touches the network beyond the two roots.

When a run runs (CPD-0033, CPD-0035, ``config/resource_policy.json``). Outcomes, recorded in ``_backup/last_run.json``:

* ``SCHEDULED_PAUSE`` (exit 0): not a day of the maintenance calendar -- Saturday and Sunday, in Europe/Berlin. Planned, not a
  failure; whatever started the process (a task that fires late after a weekday was missed) starts nothing then.
* ``DEFERRED_RESOURCE_PRIORITY`` (exit 0): a quiet window of CO.RA.PAN, CO.RA.PAN's fresh observation that the share is slow or
  recovering, the operator's ``<RUNTIME>/state/PAUSE_IO``, the BACKUP volume under its floor, or another run on the root.
* ``DEFERRED_SHARE_UNAVAILABLE`` (exit 0): the share is away -- refused, degraded in CO.RA.PAN's observation, or the share gate
  backing off after a failed contact. No logon is retried.
* ``STOPPED`` (exit 0): the time budget ended the run; resumable, no receipt.
* ``NEEDS_FULL_AUTHORIZATION`` (exit 1): there is no trustworthy basis for an incremental run (no verified receipt of this primary,
  a journal that covers less than the receipt, a mass of changed timestamps). A scheduled run never turns itself into a FULL
  run on the shared link: that is ``run --full``, on the operator's order.
* ``FAILED`` (exit 1): the run found a problem; no receipt. ``BACKUP_VERIFIED`` (exit 0): the receipt is written.

A refusal of a root or a role is exit 2. ``--ignore-windows`` is the operator's explicit order to run outside the calendar and the
quiet windows; the pause file, CO.RA.PAN's observation, the share gate and the floor still hold.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from coprepan import preservation_migration as M  # noqa: E402
from coprepan import primary_backup as B  # noqa: E402
from coprepan import resource_policy as R  # noqa: E402
from coprepan import storage_roots  # noqa: E402


#: per holding: the variable of the backup root (the PRODUCTION primary resolves through storage_roots; LEGACY below)
BACKUP_VARIABLE = {"PRODUCTION": "COPREPAN_BACKUP_ROOT", "LEGACY": "COPREPAN_LEGACY_BACKUP_ROOT"}
TASK_NAME = "COPREPAN_PreservationBackup"


def _legacy_primary(env) -> Path:
    """The LEGACY archive root (CPD-0032): set, usable, reachable, and carrying the expected identity (T1/T2) -- never guessed."""
    value = env.get("COPREPAN_LEGACY_ARCHIVE_ROOT", "").strip()
    expected = env.get("COPREPAN_LEGACY_ARCHIVE_TARGET_ID", "").strip()
    if not value or not expected:
        raise SystemExit("COPREPAN_LEGACY_ARCHIVE_ROOT and COPREPAN_LEGACY_ARCHIVE_TARGET_ID must both be set for --holding LEGACY")
    root = storage_roots.require_usable_root(value, "LEGACY archive (COPREPAN_LEGACY_ARCHIVE_ROOT)")
    identity = storage_roots.preservation_identity(root, expected=expected)
    if identity["state"] != "IDENTITY_OK":
        raise SystemExit(f"LEGACY archive root: {identity['state']} ({identity['detail']}); nothing is read or written")
    return Path(root)


def _primary(env, holding: str) -> Path:
    if holding == "LEGACY":
        return _legacy_primary(env)
    return Path(storage_roots.resolve_root("PRESERVATION", env=env, writable=False))  # T2: the identity is checked here


def _backup_root(env, holding: str, *, need: bool = True) -> Path | None:
    variable = BACKUP_VARIABLE[holding]
    value = env.get(variable, "").strip()
    if need and not value:
        raise SystemExit(f"{variable} is not set: make the root (init-root) and set it in .env")
    return Path(value) if value else None


def _roots(checkout: Path, *, need_backup: bool = True, holding: str = "PRODUCTION") -> tuple[Path, Path | None]:
    env = storage_roots.workstation_environment(checkout)
    return _primary(env, holding), _backup_root(env, holding, need=need_backup)


def _write(path: Path | None, doc) -> None:
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _runtime(env) -> Path | None:
    value = env.get("COPREPAN_WORKSPACE_ROOT", "").strip()
    return Path(value) if value and Path(value).is_dir() else None


def _policy() -> R.ResourcePolicy:
    return R.load_policy(R.default_policy_path(REPO))          # tracked configuration of this code, not workstation state


def cmd_init_root(args) -> int:
    primary, _ = _roots(args.workstation_checkout, need_backup=False, holding=args.holding)
    print(json.dumps(B.init_root(Path(args.root), primary=primary, operator=args.operator, holding=args.holding), indent=1))
    return 0


def _full(args, primary: Path, backup: Path, evidence: Path | None) -> tuple[dict, bool]:
    base = M.baseline(primary)
    print(json.dumps({k: base[k] for k in ("taken_at", "source_target_id", "files", "bytes", "tree_sha256")}), flush=True)
    copied = B.copy(primary, backup, base, workers=args.workers, progress=lambda m: print(m, flush=True), holding=args.holding)
    print(json.dumps({k: v for k, v in copied.items() if k != "problems"}), flush=True)
    verification = B.verify(backup, base, workers=args.workers)
    print(json.dumps({k: v for k, v in verification.items() if k not in ("problems",)}), flush=True)
    with tempfile.TemporaryDirectory(prefix="coprepan-restore-") as scratch:
        restore = B.restore_test(backup, base, Path(scratch) / "restore", samples=args.samples)
    print(json.dumps({k: v for k, v in restore.items() if k != "cases"}), flush=True)
    ok = copied["ok"] and verification["ok"] and restore["all_ok"]
    written = B._now()
    doc = {"written_at": written, "mode": B.MODE_FULL, "role": "BACKUP", "of": f"the PRESERVATION primary of the {args.holding} holding",
           "corpus": "coprepan", "holding": args.holding,
           "primary_target_id": base["source_target_id"], "primary_root_label": base["source_label"],
           "baseline_taken_at": base["taken_at"], "objects": base["files"], "bytes": base["bytes"], "tree_sha256": base["tree_sha256"],
           "copy_run": {k: v for k, v in copied.items() if k != "problems"}, "copy_problems": copied["problems"],
           "verification": verification, "restore_test": {k: v for k, v in restore.items() if k != "cases"},
           "produced_from_primary": copied["ok"], "verified_against_primary": verification["ok"] and copied["ok"],
           "last_full_verification_at": written,
           "independence": "different volume; further independence not determined (contract B3)",
           "not_claimed": "completeness holds for the baseline named here; objects the primary gains later are the next run's"}
    if evidence is not None:
        _write(evidence / f"backup_run_{copied['run_id']}.json", {**doc, "restore_cases": restore["cases"]})
    return doc, ok


def _incremental(args, primary: Path, backup: Path, evidence: Path | None, policy: R.ResourcePolicy, stop) -> tuple[dict, bool]:
    with tempfile.TemporaryDirectory(prefix="coprepan-restore-") as scratch:
        run = B.run_incremental(primary, backup, scratch=Path(scratch) / "restore", limits=policy.backup, stop=stop, holding=args.holding,
                                progress=lambda m: print(m, flush=True))
    print(json.dumps({k: v for k, v in run.items() if k not in ("problems", "restore_test")}), flush=True)
    doc = {"written_at": B._now(), "mode": B.MODE_INCREMENTAL, "role": "BACKUP", "of": f"the PRESERVATION primary of the {args.holding} holding",
           "corpus": "coprepan", "holding": args.holding, "primary_target_id": run["primary_target_id"], "objects": run["objects"],
           "bytes": run["bytes"], "tree_sha256": run["tree_sha256"], "run": {k: v for k, v in run.items() if k not in ("problems",)},
           "problems": run["problems"], "produced_from_primary": run["ok"], "verified_against_primary": run["ok"],
           "last_full_verification_at": run["last_full_verification_at"], "resource_policy": policy.version,
           "restore_test": {k: v for k, v in run["restore_test"].items() if k != "cases"},
           "verification_basis": ("every object of the primary's listing is on the backup root: new ones copied and re-read unbuffered against "
                                  "the digest read from the primary in this run; the others by journal evidence of such a verification, reused "
                                  "only for the same target, the same size and mtime_ns, and a backup file of that size; a budgeted slice re-hashed "
                                  "on both roots past the cache in this run (fixity); the last full re-verification of every object is named"),
           "independence": "different volume; further independence not determined (contract B3)",
           "not_claimed": "that an object outside today's fixity slice was re-read today; objects the primary gains later are the next run's"}
    if evidence is not None:
        _write(evidence / f"backup_run_{run['run_id']}.json", {**doc, "restore_cases": run["restore_test"].get("cases")})
    return doc, run["ok"]


def _incremental_basis(primary: Path, backup: Path) -> bool:
    """An incremental run builds on a verified receipt that names this primary's identity."""
    from coprepan import preservation_target

    receipt = B.read_receipt(backup)
    marker = preservation_target.read_target(primary)
    return bool(receipt and marker and receipt.get("verified_against_primary") and receipt.get("primary_target_id") == marker.get("target_id"))


def cmd_run(args) -> int:
    env = storage_roots.workstation_environment(args.workstation_checkout)
    policy = _policy()
    runtime = _runtime(env)
    backup = _backup_root(env, args.holding)
    gate = R.ShareGate(runtime, policy, env=env) if runtime is not None else None

    def refusal() -> tuple[str, str] | None:
        hold = R.maintenance_hold(policy, runtime, _now(), env, calendar=not args.ignore_windows)
        if hold:
            return hold
        closed = gate.closed_because() if gate is not None else None
        if closed:
            return R.DEFERRED_SHARE_UNAVAILABLE, closed
        floor = R.free_space_refusal("BACKUP", backup, policy)
        return (R.DEFERRED_RESOURCE_PRIORITY, floor) if floor else None

    evidence = Path(args.evidence_dir) if args.evidence_dir else None
    started = B._now()
    mode = "FULL" if args.full else "INCREMENTAL"
    held = refusal()
    if held:
        B.write_last_run(backup, {"at": started, "outcome": held[0], "reason": held[1], "mode": mode})
        print(f"{held[0]}: {held[1]}")
        return 0
    try:
        primary = _primary(env, args.holding)
    except storage_roots.StorageRootUnreachable as error:
        if gate is not None:
            gate.failed(f"backup: {error}")
        B.write_last_run(backup, {"at": started, "outcome": R.DEFERRED_SHARE_UNAVAILABLE, "reason": f"primary unreachable: {error}", "mode": mode})
        print(f"{R.DEFERRED_SHARE_UNAVAILABLE}: the primary is unreachable ({error}); the share gate backs off")
        return 0
    if gate is not None:
        gate.succeeded()
    B.require_root(backup, primary=primary, holding=args.holding)
    from coprepan.exclusive import WorkspaceBusy, exclusive

    try:
        with exclusive(backup / B.STATE, "backup run"):          # one backup run per root; released when the process ends
            return _locked_run(args, env, policy, primary, backup, gate, evidence, started, refusal)
    except WorkspaceBusy:
        print(f"{R.DEFERRED_RESOURCE_PRIORITY}: another backup run holds this backup root")
        return 0


def _locked_run(args, env, policy, primary, backup, gate, evidence, started, refusal) -> int:
    seen: list[tuple[str, str]] = []

    def stop() -> str | None:
        hold = refusal()
        if hold:
            seen.append(hold)
        return hold[1] if hold else None

    if not args.full and not _incremental_basis(primary, backup):
        return _needs_full(backup, started, "no verified receipt produced from this primary to build on")
    try:
        doc, ok = (_full(args, primary, backup, evidence) if args.full else _incremental(args, primary, backup, evidence, policy, stop))
    except B.NeedsFullAuthorization as error:
        return _needs_full(backup, started, str(error))
    run = doc.get("run") or {}
    stop_reason = str(run.get("stop_reason") or "")
    if stop_reason.startswith("SHARE_FAILED") and gate is not None:
        gate.failed(f"backup: {stop_reason}")
    if ok:
        receipt = B.write_receipt(backup, doc)
        outcome = R.BACKUP_VERIFIED
        print(f"{R.BACKUP_VERIFIED} -> {receipt}")
    elif run.get("stopped") and not run.get("problem_count"):
        outcome = (R.DEFERRED_SHARE_UNAVAILABLE if stop_reason.startswith("SHARE_FAILED") else
                   R.STOPPED if stop_reason.startswith("TIME_BUDGET") else (seen[-1][0] if seen else R.STOPPED))
        print(f"{outcome}: {stop_reason}; resumable, no receipt written")
    else:
        outcome = R.FAILED
        print(f"{R.FAILED} (not verified): no receipt written")
    problems = doc.get("problems") or doc.get("copy_problems") or []
    B.write_last_run(backup, {"at": started, "finished_at": B._now(), "outcome": outcome, "mode": doc["mode"], "objects": doc.get("objects"),
                              "stop_reason": run.get("stop_reason"), "problem_count": run.get("problem_count", len(problems)),
                              "first_problems": problems[:5], "fixity": {k: v for k, v in (run.get("fixity") or {}).items() if k != "problems"},
                              "seconds": run.get("seconds"), "counts": run.get("counts")})
    return 1 if outcome == R.FAILED else 0


def _needs_full(backup: Path, started: str, reason: str) -> int:
    B.write_last_run(backup, {"at": started, "outcome": R.NEEDS_FULL_AUTHORIZATION, "reason": reason, "mode": "INCREMENTAL"})
    print(f"{R.NEEDS_FULL_AUTHORIZATION}: {reason}. Nothing of the primary was read beyond its listing; a FULL run (run --full) is the operator's order.")
    return 1


def cmd_status(args) -> int:
    env = storage_roots.workstation_environment(args.workstation_checkout)
    backup = _backup_root(env, args.holding, need=False)
    try:
        primary = _primary(env, args.holding)
    except storage_roots.StorageRefusal:
        primary = None
    policy = _policy()
    print(json.dumps({**B.receipt_status(backup, primary),
                      "health": B.backup_health(backup, now=_now(), calendar=policy.calendar,
                                                failure_hours=policy.backup["receipt_failure_hours"])}, indent=1, default=str))
    return 0


# --- the scheduled task against the calendar (read-only) ----------------------------------------------------------

_TASK_NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
_TASK_DAYS = {"Monday": "mon", "Tuesday": "tue", "Wednesday": "wed", "Thursday": "thu", "Friday": "fri", "Saturday": "sat", "Sunday": "sun"}


def task_triggers(xml_text: str) -> list[dict]:
    """The triggers of a task definition (``schtasks /query /xml``): kind, days, local start time, enabled."""
    root = ET.fromstring(xml_text)
    out = []
    found = root.find("t:Triggers", _TASK_NS)
    for trigger in (list(found) if found is not None else []):
        kind = trigger.tag.split("}", 1)[-1]
        start = (trigger.findtext("t:StartBoundary", default="", namespaces=_TASK_NS) or "")[11:16]
        enabled = (trigger.findtext("t:Enabled", default="true", namespaces=_TASK_NS) or "true").lower() == "true"
        days: list[str] = []
        if trigger.find("t:ScheduleByDay", _TASK_NS) is not None:
            days = list(R.DAYS)
        week = trigger.find("t:ScheduleByWeek/t:DaysOfWeek", _TASK_NS)
        if week is not None:
            days = [_TASK_DAYS[d.tag.split("}", 1)[-1]] for d in week]
        out.append({"kind": kind, "days": days, "start_local": start, "enabled": enabled})
    return out


def schedule_check(triggers: list[dict], policy: R.ResourcePolicy) -> dict:
    """Whether the task starts on the calendar's days at its scheduled time, and on no other day."""
    active = [t for t in triggers if t["enabled"]]
    days = sorted({d for t in active for d in t["days"]}, key=R.DAYS.index)
    starts = sorted({t["start_local"] for t in active})
    problems = []
    if set(days) != set(policy.calendar.days):
        problems.append(f"the task starts on {days}, the calendar's days are {list(policy.calendar.days)}")
    if starts != [f"{policy.calendar.start:%H:%M}"]:
        problems.append(f"the task starts at {starts}, the calendar's scheduled start is {policy.calendar.start:%H:%M}")
    return {"triggers": triggers, "consistent": not problems, "problems": problems,
            "note": "the code refuses maintenance outside the calendar whatever the task does; a mismatch only wastes starts or misses slots"}


def cmd_schedule(args) -> int:
    policy = _policy()
    try:
        raw = subprocess.run(["schtasks", "/query", "/tn", TASK_NAME, "/xml"], capture_output=True, check=True).stdout
        # schtasks declares UTF-16 but writes the console code page when its output is piped: decode by what is there
        text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8", errors="replace")
    except (OSError, subprocess.CalledProcessError) as error:
        print(json.dumps({"task": TASK_NAME, "registered": False, "detail": f"{type(error).__name__}"}, indent=1))
        return 1
    if text.startswith("﻿"):
        text = text[1:]
    text = text.replace('encoding="UTF-16"', "")
    report = {"task": TASK_NAME, "registered": True, **schedule_check(task_triggers(text), policy),
              "calendar": {"days": list(policy.calendar.days), "scheduled_start": f"{policy.calendar.start:%H:%M}", "timezone": R.TIMEZONE}}
    print(json.dumps(report, indent=1))
    return 0 if report["consistent"] else 1


def cmd_seed_cache(args) -> int:
    from coprepan import preserved_index

    env = storage_roots.workstation_environment(args.workstation_checkout)
    policy = _policy()
    runtime = _runtime(env)
    backup = _backup_root(env, "PRODUCTION")
    target_id = env.get("COPREPAN_PRESERVATION_TARGET_ID", "").strip()
    if runtime is None or not target_id:
        raise SystemExit("COPREPAN_WORKSPACE_ROOT and COPREPAN_PRESERVATION_TARGET_ID must be set: the cache belongs to a workspace and a target")

    def stop() -> str | None:
        hold = R.maintenance_hold(policy, runtime, _now(), env, calendar=not args.ignore_windows)
        return hold[1] if hold else (R.free_space_refusal("RUNTIME", runtime, policy))

    held = stop()
    if held:
        print(f"DEFERRED: {held}")
        return 0
    cache = preserved_index.ManifestCache(Path(runtime) / preserved_index.CACHE_DIRECTORY / target_id, target_id)
    print(json.dumps(B.seed_manifest_cache(backup, cache, stop=stop), indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workstation-checkout", type=Path, default=REPO)
    parser.add_argument("--holding", choices=B.HOLDINGS, default="PRODUCTION",
                        help="PRODUCTION (default): the PRESERVATION primary; LEGACY: the LEGACY archive root (CPD-0032)")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("init-root")
    c.add_argument("--root", required=True)
    c.add_argument("--operator", required=True)
    c = sub.add_parser("run")
    c.add_argument("--full", action="store_true", help="the operator-ordered full run (every object re-hashed on both roots)")
    c.add_argument("--workers", type=int, default=3, help="full run only")
    c.add_argument("--samples", type=int, default=25, help="full run only")
    c.add_argument("--evidence-dir", default=None)
    c.add_argument("--ignore-windows", action="store_true",
                   help="an operator's explicit order: run outside the calendar and the quiet windows (the pause file, CO.RA.PAN's observation and the share gate still hold)")
    sub.add_parser("status")
    sub.add_parser("schedule")
    c = sub.add_parser("seed-cache")
    c.add_argument("--ignore-windows", action="store_true", help="an operator's explicit order: outside the calendar and the quiet windows")
    args = parser.parse_args(argv)
    try:
        return {"init-root": cmd_init_root, "run": cmd_run, "status": cmd_status, "schedule": cmd_schedule,
                "seed-cache": cmd_seed_cache}[args.command](args)
    except (B.BackupError, storage_roots.StorageRefusal, R.ResourcePolicyError) as error:
        print(f"REFUSED: {type(error).__name__}: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
