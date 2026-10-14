"""Pre-copy the PRESERVATION primary to the root that becomes the primary at cutover (CPD-0030; crosscorpus-storage/v1 §11.2).

    init-target --root DIR --target-id ID --operator NAME [--create]     give a NEW root its identity marker (once)
    plan        --source DIR --out FILE                                   step 1: the source's objects with their digests
    copy        --plan FILE --source DIR --dest DIR --migration-id ID [--workers 3] [--max-mib-s X] [--stop-file PATH]
    verify      --plan FILE --dest DIR --out FILE                         step 6: unbuffered re-read of every object
    receipt     --plan FILE --dest DIR --migration-id ID --verification FILE
    sweep-temp  --dest DIR --migration-id ID                              this tool's own leftover temporary files only

Every command that writes refuses the PRESERVATION root the workstation uses today (read from the ``.env`` of
``--workstation-checkout``, default this checkout; COPREPAN_* names only) and refuses when that root is unknown. Nothing here
changes ``.env``, the tracked configuration, the old primary or an acquisition switch. Nothing touches the network or an outlet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from coprepan import preservation_migration as M  # noqa: E402
from coprepan import preservation_target, storage_roots  # noqa: E402


def _active_root(checkout: Path) -> Path:
    environment = storage_roots.workstation_environment(checkout)
    value = environment.get("COPREPAN_PRESERVATION_ROOT", "").strip()
    if not value:
        raise SystemExit("REFUSED: the PRESERVATION root in use today is not known (COPREPAN_PRESERVATION_ROOT unset); "
                         "pass --workstation-checkout with the checkout whose .env configures it")
    return Path(value)


def _write(path: Path, payload) -> str:
    data = (json.dumps(payload, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--workstation-checkout", type=Path, default=REPO)
    commands = parser.add_subparsers(dest="command", required=True)
    c = commands.add_parser("init-target")
    c.add_argument("--root", type=Path, required=True)
    c.add_argument("--target-id", required=True)
    c.add_argument("--operator", required=True)
    c.add_argument("--create", action="store_true")
    c = commands.add_parser("plan")
    c.add_argument("--source", type=Path, required=True)
    c.add_argument("--out", type=Path, required=True)
    for name in ("copy", "verify", "receipt"):
        c = commands.add_parser(name)
        c.add_argument("--plan", type=Path, required=True)
        c.add_argument("--dest", type=Path, required=True)
        if name in ("copy", "receipt"):
            c.add_argument("--migration-id", required=True)
        if name == "copy":
            c.add_argument("--source", type=Path, required=True, help="the root the plan was taken from (a plan names it by label only)")
            c.add_argument("--workers", type=int, default=3)
            c.add_argument("--max-mib-s", type=float, default=None)
            c.add_argument("--stop-file", type=Path, default=None)
        if name == "verify":
            c.add_argument("--out", type=Path, required=True)
        if name == "receipt":
            c.add_argument("--verification", type=Path, required=True)
    c = commands.add_parser("sweep-temp")
    c.add_argument("--dest", type=Path, required=True)
    c.add_argument("--migration-id", required=True)
    args = parser.parse_args(argv)

    try:
        if args.command == "plan":
            payload = M.baseline(args.source)
            digest = _write(args.out, payload)
            print(json.dumps({k: payload[k] for k in ("files", "bytes", "tree_sha256", "source_target_id")} | {"plan_sha256": digest}))
            return 0
        active = _active_root(args.workstation_checkout)
        if args.command == "init-target":
            if str(args.root).casefold().rstrip("\\/") == str(active).casefold().rstrip("\\/"):
                print("REFUSED: this is the PRESERVATION root in use today")
                return 2
            if args.create and not args.root.is_dir():
                if not args.root.parent.is_dir():
                    print(f"REFUSED: the parent {args.root.parent} does not exist")
                    return 2
                args.root.mkdir()
            marker = preservation_target.initialise_target(args.root, args.target_id, operator=args.operator,
                                                           now=datetime.now(timezone.utc))
            print(json.dumps(marker, indent=1))
            return 0
        if args.command == "sweep-temp":
            print(json.dumps({"removed_own_temporary_files": M.sweep_temporary(args.dest, migration_id=args.migration_id, active_root=active)}, indent=1))
            return 0
        raw = args.plan.read_bytes()
        plan, plan_sha = json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()
        if args.command == "copy":
            result = M.copy(args.source, args.dest, plan["objects"],
                            migration_id=args.migration_id, active_root=active, workers=args.workers,
                            max_bytes_per_second=args.max_mib_s * 2**20 if args.max_mib_s else None, stop_file=args.stop_file,
                            progress=lambda message: print(message, flush=True))
            result["plan_sha256"] = plan_sha
            state = Path(M._long(args.dest / M.STATE_DIRECTORY / args.migration_id))
            with open(state / f"run_{result['run_id']}.json", "xb") as handle:
                handle.write((json.dumps(result, indent=1) + "\n").encode("utf-8"))
            kept = state / f"plan_{plan_sha[:16]}.json"
            if not kept.exists():
                with open(kept, "xb") as handle:
                    handle.write(raw)
            print(json.dumps({k: v for k, v in result.items() if k != "problems"}))
            for problem in result["problems"][:20]:
                print("PROBLEM", json.dumps(problem))
            return 3 if result["stopped"] else (1 if result["problems"] else 0)
        if args.command == "verify":
            result = M.verify(args.dest, plan["objects"]) | {"plan_sha256": plan_sha}
            _write(args.out, result)
            print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in result.items()}))
            return 0 if result["equal"] else 1
        verification_raw = args.verification.read_bytes()
        verification = json.loads(verification_raw.decode("utf-8"))
        receipt = {"schema": M.SCHEMA, "kind": "receipt", "written_at": M._now(), "state": "PRE_COPY_NOT_PRIMARY",
                   "destination_target_id": (preservation_target.read_target(args.dest) or {}).get("target_id"),
                   "source_target_id": plan.get("source_target_id"), "plan_sha256": plan_sha, "tree_sha256": plan["tree_sha256"],
                   "objects": plan["files"], "bytes": plan["bytes"],
                   "verification": {k: (v if not isinstance(v, list) else len(v)) for k, v in verification.items()},
                   "verification_sha256": hashlib.sha256(verification_raw).hexdigest(),
                   "journal_audit": M.journal_audit(args.dest, args.migration_id),
                   "not_claimed": "not the primary and not a backup: the destination becomes the primary only by the cutover (the "
                                  "workstation's COPREPAN_PRESERVATION_ROOT and COPREPAN_PRESERVATION_TARGET_ID), never by this receipt"}
        path = Path(M._long(args.dest / M.STATE_DIRECTORY / args.migration_id / "migration_receipt.json"))
        with open(path, "xb") as handle:
            handle.write((json.dumps(receipt, indent=1) + "\n").encode("utf-8"))
        print(f"receipt -> {path}")
        return 0
    except (M.MigrationError, preservation_target.TargetError, storage_roots.StorageRefusal) as error:
        print(f"REFUSED: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
