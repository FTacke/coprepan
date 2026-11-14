"""The whole-root audit of the workspace against the PRESERVATION primary (CPD-0033). Operator-ordered; never scheduled.

    python scripts/preservation_audit.py [--ignore-windows] [--out FILE]

``recovery.diagnose`` with the preservation root and the registry: every master the ledger relates is re-hashed **on the
primary** past the client cache, and the identity tables are rebuilt from every preserved pack read from the primary and
compared (CPD-0010). This is the full read of the share that the regular paths no longer make: an intake's finalizer re-hashes
its own packs only, and the backup's fixity rotation re-reads a budgeted slice per run. Use it after an incident, before a
release, or when the fixity rotation reports a cycle overdue.

It yields like every CO.PRE.PAN maintenance on shared storage (``config/resource_policy.json``): not in a quiet window of
CO.RA.PAN, not while ``<RUNTIME>/state/PAUSE_IO`` exists, not while the share gate backs off or CO.RA.PAN's fresh observation says
the share is degraded or slow -- unless the operator passes ``--ignore-windows``. Read-only; takes no lock; writes only ``--out``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from coprepan import recovery, registry, resource_policy as R, storage_roots  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ignore-windows", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    env = storage_roots.workstation_environment()
    policy = R.load_policy(R.default_policy_path(REPO))
    try:
        runtime = storage_roots.resolve_root("RUNTIME", env=env)
    except storage_roots.StorageRefusal as error:
        print(f"REFUSED: RUNTIME: {error}")
        return 2
    gate = R.ShareGate(runtime, policy, env=env)
    held = None if args.ignore_windows else (R.maintenance_refusal(policy, runtime, datetime.now(timezone.utc), env) or gate.closed_because())
    if held:
        print(f"DEFERRED: {held}")
        return 0
    try:
        root = gate.guard(lambda: storage_roots.resolve_root("PRESERVATION", env=env, writable=False))()
    except storage_roots.StorageRefusal as error:
        print(f"REFUSED: PRESERVATION: {error}")
        return 2
    diagnosis = recovery.diagnose(runtime, root, registry.load_registry(REPO / "config" / "outlet_registry.json"))
    text = json.dumps(diagnosis, indent=1, sort_keys=True, default=str)
    if args.out is not None:
        args.out.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: diagnosis.get(k) for k in ("classification", "masters_checked_on_root", "ledger_and_packs")}, default=str))
    print(json.dumps({"identity_rebuild": (diagnosis.get("identity_rebuild") or {}).get("status")}))
    return 0 if diagnosis.get("classification") == recovery.CLEAN else 1


if __name__ == "__main__":
    raise SystemExit(main())
