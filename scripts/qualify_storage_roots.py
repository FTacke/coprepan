"""Qualify the configured storage roots on their real file systems (2026-10-08, O-3 interim; CPD-0014).

Reads the roots from the workstation environment (``.env``) and reports. Commands:

    roles                                  every declared role: configured or NOT_CONFIGURED; the separation rules checked
    init-preservation --target-id ID --operator NAME
                                           give the PRESERVATION root its identity, once (an operator act)
    readiness --required-free-bytes N      the readiness check of the preservation target, on the real root
    spool-failover                         preservation unavailable -> spooled -> target returns -> drained -> verified -> spool empty

The failover test never writes an object into the real preservation root (preservation has no deletion
path): it runs against a probe target made for the purpose beside it, on the same file system, with the real
spool root's file system as spool, and removes exactly the directories it created. Nothing here touches the
network or an outlet.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from coprepan import outage_spool, preservation, preservation_target, storage_roots  # noqa: E402
from coprepan.canonical import sha256_bytes  # noqa: E402

QUALIFICATION = "_qualification"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def roles() -> dict:
    environment = storage_roots.workstation_environment()
    resolved = storage_roots.resolve_configured_roles(env=environment)
    targets = storage_roots.load_storage_targets()
    return {"roles": {role: ("NOT_CONFIGURED" if root is None else "CONFIGURED") for role, root in resolved.items()},
            "variables": {role: target.variable for role, target in targets.items()},
            "separation": "checked: no role shares or contains another; BACKUP, if configured, is on another volume than PRESERVATION",
            "checked_at": _now().strftime("%Y-%m-%dT%H:%M:%SZ")}


def init_preservation(target_id: str, operator: str) -> dict:
    root = storage_roots.resolve_root("PRESERVATION", env=storage_roots.workstation_environment())
    marker = preservation_target.initialise_target(root, target_id, operator=operator, now=_now())
    return {"initialised": marker}


def readiness(required_free_bytes: int) -> dict:
    root = storage_roots.resolve_root("PRESERVATION", env=storage_roots.workstation_environment())
    report = preservation_target.check_readiness(root, required_free_bytes=required_free_bytes, now=_now())
    leftovers = sorted(path.name for path in (root / preservation_target.PROBE_DIRECTORY).glob("*")) if (root / preservation_target.PROBE_DIRECTORY).exists() else []
    return {**report, "probe_artefacts_left": leftovers}


def _remove_own(directory: Path) -> None:
    if QUALIFICATION not in directory.parts or not directory.name.startswith("qualification-"):
        raise SystemExit(f"refusing to remove a directory this script did not create: {directory.name}")
    shutil.rmtree(directory)


def spool_failover() -> dict:
    environment = storage_roots.workstation_environment()
    preservation_root = storage_roots.resolve_root("PRESERVATION", env=environment)
    spool_root = storage_roots.resolve_root("SPOOL", env=environment)
    stamp = _now().strftime("%Y%m%dT%H%M%SZ")
    area = preservation_root.parent / QUALIFICATION / f"qualification-{stamp}"       # beside the real root, same file system
    spool = spool_root / QUALIFICATION / f"qualification-{stamp}"                    # on the real spool root's file system
    target = area / "preservation_probe"
    steps = []
    try:
        area.mkdir(parents=True)
        spool.mkdir(parents=True)
        payload = b"coprepan spool failover probe\n" * 4096
        source = area / "source.bin"
        source.write_bytes(payload)
        digest = sha256_bytes(payload)
        policy = outage_spool.SpoolPolicy(min_free_bytes=1 << 20, max_spool_bytes=1 << 30)

        def resolve() -> Path:
            if not storage_roots.probe(target).reachable:
                raise storage_roots.StorageRootUnreachable("PRESERVATION: the probe target is not reachable")
            return target

        arguments = dict(preservation_root=resolve, spool_root=spool, policy=policy, area="qualification", object_id="qualification-probe-1",
                         relative_path="qualification/probe-1.bin", declared_sha256=digest, now=_now())
        first = outage_spool.preserve_or_spool(source, **arguments)
        steps.append({"step": "target unavailable", "route": first.route, "state": first.state, "reason": first.reason})
        pending = outage_spool.pending_records(spool)
        steps.append({"step": "spool holds it", "pending_records": len(pending), "spooled_bytes": outage_spool.spooled_bytes(spool)})
        target.mkdir()
        preservation_target.initialise_target(target, "qualification-probe", operator="qualification", now=_now())
        drained = outage_spool.drain(spool, preservation_root=resolve, now=_now())
        steps.append({"step": "target returned, drained", "results": [{"object": d.object_id, "action": d.action} for d in drained]})
        verified = preservation.verify_master(target, "qualification", "qualification-probe-1")
        master = target / preservation.master_relative_path("qualification", "qualification/probe-1.bin")
        steps.append({"step": "destination verified", "verify_master": verified, "bytes_equal_source": master.read_bytes() == payload})
        steps.append({"step": "spool retired", "pending_records": len(outage_spool.pending_records(spool)), "spooled_bytes": outage_spool.spooled_bytes(spool)})
        ok = (first.route == "spooled" and len(pending) == 1 and [d.action for d in drained] == ["preserved"] and verified
              and master.read_bytes() == payload and not outage_spool.pending_records(spool) and outage_spool.spooled_bytes(spool) == 0)
    finally:
        for directory in (area, spool):
            if directory.exists():
                _remove_own(directory)
        for parent in (area.parent, spool.parent):
            try:
                parent.rmdir()
            except OSError:
                pass
    return {"status": "PASS" if ok else "FAIL", "steps": steps, "cleaned_up": not area.exists() and not spool.exists()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("roles")
    init = commands.add_parser("init-preservation")
    init.add_argument("--target-id", required=True)
    init.add_argument("--operator", required=True)
    ready = commands.add_parser("readiness")
    ready.add_argument("--required-free-bytes", type=int, required=True)
    commands.add_parser("spool-failover")
    arguments = parser.parse_args(argv)
    if arguments.command == "roles":
        result = roles()
    elif arguments.command == "init-preservation":
        result = init_preservation(arguments.target_id, arguments.operator)
    elif arguments.command == "readiness":
        result = readiness(arguments.required_free_bytes)
    else:
        result = spool_failover()
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") in (None, "PASS", "READY") else 1


if __name__ == "__main__":
    raise SystemExit(main())
