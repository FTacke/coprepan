"""The joint storage contract ``crosscorpus-storage/v1`` on this workstation (CPD-0015): the pinned bundle,
the roles in the contract's terms, the joint check with the sister checkout, and the read-only half of a
root migration.

    check                                   the local bundle copy is the pinned one
    status                                  every role: its configuration state; separation; pending; backup
    compare-sister [--sister DIR]           both pins, both bundle copies, and S4 over both machines' roots
    migration-inventory --root DIR --out FILE
    migration-verify --inventory FILE --root DIR

Everything here READS. ``status`` probes reachability and creates nothing; ``migration-inventory`` hashes
every file below a root and writes one JSON file where the caller says; ``migration-verify`` re-reads a root
and compares it with an inventory. No command copies, moves, deletes, configures or initialises anything:
the mutating half of a migration (contract §11.2, steps 3, 4, 5, 8, 9) is an operator-ordered act and is
not in this tool. Nothing here touches the network or an outlet.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from coprepan import outage_spool, release_contract, storage_contract, storage_roots  # noqa: E402

SISTER_NAME = "corapan"                     # the local sibling layout of contract §5.2: <umbrella>/<corpus>
INVENTORY_SCHEMA = "crosscorpus-storage-migration-inventory/v1"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _state(role: str, environment: dict[str, str], targets) -> tuple[str, Path | None]:
    """The contract's configuration state of one role, from the real resolver's refusals."""
    target = targets.get(role)
    value = environment.get(target.variable, "") if target is not None else None
    try:
        root = storage_roots.resolve_root(role, env=environment, targets=targets)
        return storage_contract.STATE_AVAILABLE, root
    except storage_roots.StorageRootNotConfigured:
        return storage_contract.configuration_state(declared=target is not None, value=value), None
    except storage_roots.StorageRootUnusable:
        return storage_contract.STATE_UNUSABLE, None
    except storage_roots.StorageRootUnreachable:
        return storage_contract.STATE_UNREACHABLE, None
    except storage_roots.StorageRootReadOnly:
        return storage_contract.STATE_READ_ONLY, None


def _sister_roots(sister: Path) -> list[str]:
    """The sister's configured root values, read from ITS machine file: ``CORAPAN_*_ROOT`` names only."""
    path = sister / ".env"
    if not path.is_file():
        return []
    values = []
    for line in path.read_text(encoding="utf-8").splitlines():
        name, _, value = line.strip().partition("=")
        if name.startswith("CORAPAN_") and name.endswith("_ROOT") and value.strip():
            values.append(value.strip().strip("'\""))
    return sorted(values)


def status(sister: Path | None = None) -> dict[str, Any]:
    environment = storage_roots.workstation_environment()
    targets = storage_roots.load_storage_targets()
    states, roots = {"REPOSITORY": storage_contract.STATE_AVAILABLE}, {}
    for role in sorted(targets):
        states[role], root = _state(role, environment, targets)
        if root is not None:
            roots[role] = root
    foreign = (_sister_roots(sister) + [str(sister)]) if sister is not None and sister.is_dir() else []
    try:
        separation: Any = storage_roots.separation_codes(roots, foreign_roots=foreign) or "SEPARATED"
    except storage_roots.StorageRefusal as refusal:
        separation = [f"VOLUME_UNKNOWN ({type(refusal).__name__})"]
    pending = None
    if "SPOOL" in roots:
        records = outage_spool.pending_records(roots["SPOOL"])
        pending = {"pending_records": len(records), "spooled_bytes": outage_spool.spooled_bytes(roots["SPOOL"]),
                   "oldest_pending_at": records[0]["spooled_at"] if records else None}

    def volume(role: str):
        try:
            return storage_roots.volume_of(roots[role]) if role in roots else None
        except storage_roots.StorageRefusal:
            return None
    backup = storage_contract.backup_status(
        configured="BACKUP" in roots, copy_exists=False, produced_from_primary=False, verified_against_primary=False,
        primary_volume=volume("PRESERVATION"), backup_volume=volume("BACKUP"))
    return {"contract": storage_contract.CONTRACT, "bundle_sha256": storage_contract.read_pin()["bundle_sha256"],
            "pin_status": storage_contract.read_pin()["status"], "bundle_problems": storage_contract.bundle_problems(),
            "corpus": "coprepan", "holding": "PRODUCTION",
            "roles": {role: {"state": state, "contract_role": storage_contract.CONTRACT_ROLE[role]} for role, state in sorted(states.items())},
            "separation": separation, "pending_in_the_spool": pending,
            "backup_of_the_preservation_primary": backup,
            "note": "a copy counts as a backup only when produced from the primary and verified against it; this command verifies no copy",
            "historic_holding": "no root is configured or present for the HISTORIC holding; planned, see docs/storage/INDEX.md",
            "checked_at": _now()}


def compare_sister(sister: Path) -> list[str]:
    """Why the two repositories do not agree on the storage contract. Empty: both pins are equal, both
    bundle copies are byte-identical, and no root of one corpus overlaps a root of the other (S4).
    """
    theirs = sister / storage_contract.BUNDLE_PATH
    if not theirs.is_dir():
        return [f"SISTER_NOT_AVAILABLE: no {storage_contract.CONTRACT} bundle in the sister checkout; nothing was compared"]
    problems = []
    mine_listing, their_listing = release_contract.tree_listing(REPO / storage_contract.BUNDLE_PATH), release_contract.tree_listing(theirs)
    if mine_listing != their_listing:
        problems.append("the two bundle copies differ")
    their_pin = json.loads((sister / storage_contract.PINS_PATH).read_text(encoding="utf-8")).get("contracts", {}).get(storage_contract.CONTRACT) or {}
    pin = storage_contract.read_pin()
    if their_pin.get("bundle_sha256") != pin["bundle_sha256"]:
        problems.append(f"pins differ: here {pin['bundle_sha256']}, sister {their_pin.get('bundle_sha256')}")
    if their_pin.get("status") != pin.get("status"):
        problems.append(f"pin status differs: here {pin.get('status')}, sister {their_pin.get('status')}")
    report = status(sister)
    if isinstance(report["separation"], list) and "FOREIGN_CORPUS_OVERLAP" in report["separation"]:
        problems.append("a storage root of one corpus lies inside, contains or equals a root of the other (S4)")
    return problems


def inventory(root: Path) -> dict[str, Any]:
    """Step 1 (and 7) of contract §11.2: every file below ``root`` with relative path, size and SHA-256.
    Reads ``root``; writes nothing there. The root is named by its last segment only.
    """
    started = _now()
    listing = release_contract.tree_listing(root)
    return {"schema": INVENTORY_SCHEMA, "contract": storage_contract.CONTRACT, "taken_at": started, "finished_at": _now(),
            "root_label": Path(root).name, "files": len(listing), "bytes": sum(entry["size"] for entry in listing),
            "tree_sha256": release_contract.record_set_digest(listing), "listing": listing,
            "note": "an inventory is a statement about one moment; it does not protect against a writer (contract §11.3)"}


def compare(stated: dict[str, Any], root: Path) -> dict[str, Any]:
    """Steps 6 and 7: a root re-read in full against an inventory — paths, sizes, digests, nothing extra."""
    wanted = {entry["path"]: (entry["sha256"], entry["size"]) for entry in stated["listing"]}
    found = {entry["path"]: (entry["sha256"], entry["size"]) for entry in release_contract.tree_listing(root)}
    missing, extra = sorted(set(wanted) - set(found)), sorted(set(found) - set(wanted))
    different = sorted(path for path in set(wanted) & set(found) if wanted[path] != found[path])
    return {"equal": not (missing or extra or different), "missing": missing, "extra": extra, "different": different}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    command = commands.add_parser("status")
    command.add_argument("--sister", type=Path, default=None)
    command = commands.add_parser("compare-sister")
    command.add_argument("--sister", type=Path, default=None)
    command = commands.add_parser("migration-inventory")
    command.add_argument("--root", type=Path, required=True)
    command.add_argument("--out", type=Path, required=True)
    command = commands.add_parser("migration-verify")
    command.add_argument("--inventory", type=Path, required=True)
    command.add_argument("--root", type=Path, required=True)
    arguments = parser.parse_args(argv)
    default_sister = REPO.parent / SISTER_NAME
    if arguments.command == "check":
        problems = storage_contract.bundle_problems()
        print(json.dumps({"contract": storage_contract.CONTRACT, "pinned": storage_contract.read_pin()["bundle_sha256"], "problems": problems}, indent=1))
        return 1 if problems else 0
    if arguments.command == "status":
        sister = arguments.sister or (default_sister if default_sister.is_dir() else None)
        report = status(sister)
        print(json.dumps(report, indent=1))
        return 0 if report["separation"] == "SEPARATED" and not report["bundle_problems"] else 1
    if arguments.command == "compare-sister":
        problems = compare_sister(arguments.sister or default_sister)
        print(json.dumps({"joint_check": "OK" if not problems else "NOT OK", "problems": problems}, indent=1))
        return 2 if problems and problems[0].startswith("SISTER_NOT_AVAILABLE") else 1 if problems else 0
    if arguments.command == "migration-inventory":
        payload = inventory(arguments.root)
        arguments.out.parent.mkdir(parents=True, exist_ok=True)
        with open(arguments.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
        print(json.dumps({key: payload[key] for key in ("files", "bytes", "tree_sha256", "root_label")}, indent=1))
        return 0
    result = compare(json.loads(arguments.inventory.read_text(encoding="utf-8")), arguments.root)
    print(json.dumps({**{key: value[:20] if isinstance(value, list) else value for key, value in result.items()},
                      "counts": {key: len(result[key]) for key in ("missing", "extra", "different")}}, indent=1))
    return 0 if result["equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
