"""The BACKUP of the PRESERVATION primary (crosscorpus-storage/v1 §9; NEW_FS Phase D). Mechanics: ``coprepan.primary_backup``.

    init-root --root DIR --operator NAME          make DIR a BACKUP root (once; new or empty, another volume than the primary)
    run       [--workers 3] [--samples 25] [--evidence-dir DIR]
                                                   fresh baseline of the primary -> copy -> unbuffered verification -> restore test -> receipt
    status                                         the receipt's state as the contract status reads it

Both roots come from the workstation's ``.env`` (``COPREPAN_PRESERVATION_ROOT`` with ``COPREPAN_PRESERVATION_TARGET_ID``, checked
(T2); ``COPREPAN_BACKUP_ROOT``). Nothing here writes to the primary, deletes an object or touches the network beyond the two roots.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from coprepan import preservation_migration as M  # noqa: E402
from coprepan import primary_backup as B  # noqa: E402
from coprepan import storage_roots  # noqa: E402


def _roots(checkout: Path, *, need_backup: bool = True) -> tuple[Path, Path | None]:
    env = storage_roots.workstation_environment(checkout)
    primary = storage_roots.resolve_root("PRESERVATION", env=env, writable=False)      # T2: the identity is checked here
    value = env.get("COPREPAN_BACKUP_ROOT", "").strip()
    if need_backup and not value:
        raise SystemExit("COPREPAN_BACKUP_ROOT is not set: make the root (init-root) and set it in .env")
    return Path(primary), (Path(value) if value else None)


def _write(path: Path | None, doc) -> None:
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def cmd_init_root(args) -> int:
    primary, _ = _roots(args.workstation_checkout, need_backup=False)
    print(json.dumps(B.init_root(Path(args.root), primary=primary, operator=args.operator), indent=1))
    return 0


def cmd_run(args) -> int:
    primary, backup = _roots(args.workstation_checkout)
    B.require_root(backup, primary=primary)
    evidence = Path(args.evidence_dir) if args.evidence_dir else None
    base = M.baseline(primary)
    print(json.dumps({k: base[k] for k in ("taken_at", "source_target_id", "files", "bytes", "tree_sha256")}), flush=True)
    copied = B.copy(primary, backup, base, workers=args.workers, progress=lambda m: print(m, flush=True))
    print(json.dumps({k: v for k, v in copied.items() if k != "problems"}), flush=True)
    verification = B.verify(backup, base, workers=args.workers)
    print(json.dumps({k: v for k, v in verification.items() if k not in ("problems",)}), flush=True)
    with tempfile.TemporaryDirectory(prefix="coprepan-restore-") as scratch:
        restore = B.restore_test(backup, base, Path(scratch) / "restore", samples=args.samples)
    print(json.dumps({k: v for k, v in restore.items() if k != "cases"}), flush=True)
    ok = copied["ok"] and verification["ok"] and restore["all_ok"]
    doc = {"written_at": B._now(), "role": "BACKUP", "of": "the PRESERVATION primary", "corpus": "coprepan", "holding": "PRODUCTION",
           "primary_target_id": base["source_target_id"], "primary_root_label": base["source_label"],
           "baseline_taken_at": base["taken_at"], "objects": base["files"], "bytes": base["bytes"], "tree_sha256": base["tree_sha256"],
           "copy_run": {k: v for k, v in copied.items() if k != "problems"}, "copy_problems": copied["problems"],
           "verification": verification, "restore_test": {k: v for k, v in restore.items() if k != "cases"},
           "produced_from_primary": copied["ok"], "verified_against_primary": verification["ok"] and copied["ok"],
           "independence": "different volume; further independence not determined (contract B3)",
           "not_claimed": "completeness holds for the baseline named here; objects the primary gains later are the next run's"}
    if ok:
        receipt = B.write_receipt(backup, doc)
        print(f"BACKUP_VERIFIED -> {receipt}")
    else:
        print("NOT VERIFIED: no receipt written")
    if evidence is not None:
        _write(evidence / f"backup_run_{copied['run_id']}.json", {**doc, "restore_cases": restore["cases"]})
    return 0 if ok else 1


def cmd_status(args) -> int:
    primary, backup = _roots(args.workstation_checkout, need_backup=False)
    print(json.dumps(B.receipt_status(backup, primary), indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workstation-checkout", type=Path, default=REPO)
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("init-root")
    c.add_argument("--root", required=True)
    c.add_argument("--operator", required=True)
    c = sub.add_parser("run")
    c.add_argument("--workers", type=int, default=3)
    c.add_argument("--samples", type=int, default=25)
    c.add_argument("--evidence-dir", default=None)
    sub.add_parser("status")
    args = parser.parse_args(argv)
    try:
        return {"init-root": cmd_init_root, "run": cmd_run, "status": cmd_status}[args.command](args)
    except (B.BackupError, storage_roots.StorageRefusal) as error:
        print(f"REFUSED: {type(error).__name__}: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
