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

Both roots come from the workstation's ``.env`` (``COPREPAN_PRESERVATION_ROOT`` with ``COPREPAN_PRESERVATION_TARGET_ID``, checked
(T2); ``COPREPAN_BACKUP_ROOT``). With ``--holding LEGACY`` (CPD-0032) the primary is the LEGACY archive root
``COPREPAN_LEGACY_ARCHIVE_ROOT``, whose identity must be ``COPREPAN_LEGACY_ARCHIVE_TARGET_ID`` (T2, required), and the backup root
is ``COPREPAN_LEGACY_BACKUP_ROOT``; a backup root names its holding and is refused for another one. Nothing here writes to the
primary, deletes an object or touches the network beyond the two roots.

Yielding (CPD-0033, ``config/resource_policy.json``): a run does not start, and a running one stops at its next object, in a quiet
window of CO.RA.PAN, while the operator's ``<RUNTIME>/state/PAUSE_IO`` exists, while CO.RA.PAN's fresh observation says the share
is degraded or slow, while the share gate is backing off, or when the BACKUP volume is under its floor. Such a run ends
``DEFERRED`` or ``STOPPED`` (exit 0: an expected state; ``_backup/last_run.json`` records it and the status shows the receipt's
age). A run that finds a problem ends ``NOT_VERIFIED`` (exit 1). A refusal of a root or a role is exit 2.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
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
    """An incremental run builds on a verified receipt that names this primary's identity; without one the run is FULL."""
    from coprepan import preservation_target

    receipt = B.read_receipt(backup)
    marker = preservation_target.read_target(primary)
    return bool(receipt and marker and receipt.get("verified_against_primary") and receipt.get("primary_target_id") == marker.get("target_id"))


def cmd_run(args) -> int:
    env = storage_roots.workstation_environment(args.workstation_checkout)
    policy = R.load_policy(R.default_policy_path(REPO))          # tracked configuration of this code, not workstation state
    runtime = _runtime(env)
    backup = _backup_root(env, args.holding)
    gate = R.ShareGate(runtime, policy, env=env) if runtime is not None else None

    def refusal() -> str | None:
        reason = None if args.ignore_windows else R.maintenance_refusal(policy, runtime, _now(), env)
        reason = reason or (gate.closed_because() if gate is not None else None)
        return reason or R.free_space_refusal("BACKUP", backup, policy)

    evidence = Path(args.evidence_dir) if args.evidence_dir else None
    started = B._now()
    held = refusal()
    if held:
        B.write_last_run(backup, {"at": started, "outcome": "DEFERRED", "reason": held, "mode": "FULL" if args.full else "INCREMENTAL"})
        print(f"DEFERRED: {held}")
        return 0
    try:
        primary = _primary(env, args.holding)
    except storage_roots.StorageRootUnreachable as error:
        if gate is not None:
            gate.failed(f"backup: {error}")
        B.write_last_run(backup, {"at": started, "outcome": "DEFERRED", "reason": f"primary unreachable: {error}"})
        print(f"DEFERRED: the primary is unreachable ({error}); the share gate backs off")
        return 0
    if gate is not None:
        gate.succeeded()
    B.require_root(backup, primary=primary, holding=args.holding)
    from coprepan.exclusive import WorkspaceBusy, exclusive

    try:
        with exclusive(backup / B.STATE, "backup run"):          # one backup run per root; released when the process ends
            return _locked_run(args, env, policy, primary, backup, gate, evidence, started, refusal)
    except WorkspaceBusy:
        print("DEFERRED: another backup run holds this backup root")
        return 0


def _locked_run(args, env, policy, primary, backup, gate, evidence, started, refusal) -> int:
    full = args.full or not _incremental_basis(primary, backup)
    if full and not args.full:
        print("FULL: no verified receipt produced from this primary to build on; this run re-hashes every object (once)", flush=True)
    doc, ok = (_full(args, primary, backup, evidence) if full else _incremental(args, primary, backup, evidence, policy, refusal))
    run = doc.get("run") or {}
    if run.get("stop_reason", "") and str(run.get("stop_reason")).startswith("SHARE_FAILED") and gate is not None:
        gate.failed(f"backup: {run['stop_reason']}")
    if ok:
        receipt = B.write_receipt(backup, doc)
        outcome = "BACKUP_VERIFIED"
        print(f"BACKUP_VERIFIED -> {receipt}")
    elif run.get("stopped") and not run.get("problem_count"):
        outcome = "STOPPED"
        print(f"STOPPED: {run.get('stop_reason')}; resumable, no receipt written")
    else:
        outcome = "NOT_VERIFIED"
        print("NOT VERIFIED: no receipt written")
    problems = doc.get("problems") or doc.get("copy_problems") or []
    B.write_last_run(backup, {"at": started, "finished_at": B._now(), "outcome": outcome, "mode": doc["mode"], "objects": doc.get("objects"),
                              "stop_reason": run.get("stop_reason"), "problem_count": run.get("problem_count", len(problems)),
                              "first_problems": problems[:5], "fixity": {k: v for k, v in (run.get("fixity") or {}).items() if k != "problems"},
                              "seconds": run.get("seconds")})
    return 0 if outcome in ("BACKUP_VERIFIED", "STOPPED") else 1


def cmd_status(args) -> int:
    env = storage_roots.workstation_environment(args.workstation_checkout)
    backup = _backup_root(env, args.holding, need=False)
    try:
        primary = _primary(env, args.holding)
    except storage_roots.StorageRefusal:
        primary = None
    policy = R.load_policy(R.default_policy_path(REPO))
    print(json.dumps({**B.receipt_status(backup, primary),
                      "health": B.backup_health(backup, now=_now(), warning_hours=policy.backup["receipt_warning_hours"],
                                                failure_hours=policy.backup["receipt_failure_hours"])}, indent=1, default=str))
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
    c.add_argument("--ignore-windows", action="store_true", help="an operator's explicit order: run inside a quiet window or a pause")
    sub.add_parser("status")
    args = parser.parse_args(argv)
    try:
        return {"init-root": cmd_init_root, "run": cmd_run, "status": cmd_status}[args.command](args)
    except (B.BackupError, storage_roots.StorageRefusal, R.ResourcePolicyError) as error:
        print(f"REFUSED: {type(error).__name__}: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
