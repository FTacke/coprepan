"""Readiness of a preservation target (master plan O-3; decision CPD-0006 §7).

Choosing the target is an institutional decision and is not made here. What is here is the
contract a chosen target must meet and a check that says, property by property, whether it does:

* it is a usable root: absolute, not a filesystem root, not inside the checkout, reachable;
* it has an **identity**: a marker file written once when the operator takes the target into
  service, so that "the preservation root" is a named thing and not whatever a path points at;
* it is writable, and promotion as this repository does it works there: write under a ``.part-``
  name, flush, hash the landed bytes, rename atomically, re-read; an existing name is not
  overwritten by an exclusive create;
* its free space is known and at least what the operator requires;
* what it already holds verifies against its manifests (a fixity pass, bounded).

The check writes a few hundred bytes into a directory of its own (``_readiness_probe/``) and
removes exactly what it wrote. It never touches ``preservation/``.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from . import naming, preservation
from .canonical import record_json, sha256_bytes, sha256_file
from .identity import format_instant
from .storage_roots import StorageRefusal, probe, require_usable_root

TARGET_SCHEMA = naming.schema_id("preservation-target", 1)
READINESS_SCHEMA = naming.schema_id("preservation-readiness", 1)
MARKER_NAME = "coprepan_preservation_target.json"
PROBE_DIRECTORY = "_readiness_probe"

PASS, FAIL, INFO = "PASS", "FAIL", "INFO"
READY, NOT_READY = "READY", "NOT_READY"


class TargetError(RuntimeError):
    """The target cannot be taken into service as asked."""


def initialise_target(root: Path, target_id: str, *, operator: str, now: datetime) -> dict[str, Any]:
    """Give a target its identity, once. An operator action: it is the statement "this directory
    is preservation target ``target_id``". A target that already has an identity keeps it.
    """
    root = require_usable_root(str(root), "preservation target")
    if not isinstance(target_id, str) or not target_id or not target_id.replace("-", "").replace("_", "").isalnum():
        raise TargetError(f"a target id is letters, digits, '-' and '_': {target_id!r}")
    if not probe(root).reachable:
        raise TargetError("the target is not a reachable directory")
    marker = {"schema": TARGET_SCHEMA, "target_id": target_id, "taken_into_service_at": format_instant(now),
              "operator": operator}
    try:
        with open(root / MARKER_NAME, "xb") as handle:
            handle.write(record_json(marker))
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise TargetError("the target already has an identity; it is never re-initialised") from error
    return marker


def read_target(root: Path) -> dict[str, Any] | None:
    """The identity of a target, ``None`` when it has none. An unreadable marker raises."""
    path = Path(root) / MARKER_NAME
    if not path.exists():
        return None
    try:
        marker = json.loads(path.read_text(encoding="utf-8"))
        if marker["schema"] != TARGET_SCHEMA or not marker["target_id"]:
            raise ValueError("schema or target_id")
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise TargetError(f"the target's identity marker is unreadable: {error}") from error
    return marker


def check_readiness(root: Path | str, *, required_free_bytes: int, now: datetime, max_fixity_objects: int = 50) -> dict[str, Any]:
    """Check a target against the contract. Returns a report; never raises for a failing target."""
    checks: list[dict[str, str]] = []

    def add(name: str, status: str, detail: str) -> bool:
        checks.append({"check": name, "status": status, "detail": detail})
        return status == PASS

    report: dict[str, Any] = {"schema": READINESS_SCHEMA, "checked_at": format_instant(now), "target_id": "unknown",
                              "required_free_bytes": required_free_bytes, "free_bytes": "unknown", "total_bytes": "unknown",
                              "checks": checks}
    try:
        path = require_usable_root(str(root), "preservation target")
        usable = add("usable_root", PASS, "absolute, not a filesystem root, not inside the checkout")
    except StorageRefusal as refusal:
        usable = add("usable_root", FAIL, str(refusal))
    measured = probe(path) if usable else None
    reachable = usable and add("reachable", PASS if measured.reachable else FAIL,
                               "is a directory" if measured.reachable else "not a reachable directory; its content is unknown, not empty")
    if reachable:
        report["free_bytes"], report["total_bytes"] = measured.free_bytes, measured.total_bytes
        try:
            marker = read_target(path)
            if marker is None:
                add("target_identity", FAIL, f"no {MARKER_NAME}: the target was never taken into service")
            else:
                report["target_id"] = marker["target_id"]
                add("target_identity", PASS, marker["target_id"])
        except TargetError as error:
            add("target_identity", FAIL, str(error))
        add("free_space", PASS if measured.free_bytes is not None and measured.free_bytes >= required_free_bytes else FAIL,
            f"{measured.free_bytes} bytes free, {required_free_bytes} required")
        _promotion_probe(path, add)
        _fixity(path, add, max_fixity_objects)
    report["status"] = READY if checks and all(check["status"] != FAIL for check in checks) else NOT_READY
    return report


def _promotion_probe(root: Path, add) -> None:
    """Exercise exactly what promotion needs, on files of this probe's own making."""
    directory = root / PROBE_DIRECTORY / uuid.uuid4().hex
    payload = b"coprepan readiness probe\n" * 8
    final, staging = directory / "probe.bin", directory / "probe.bin.part-00000000"
    created: list[Path] = []
    try:
        directory.mkdir(parents=True)
        with open(staging, "xb") as handle:
            created.append(staging)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        landed = sha256_file(staging)[0] == sha256_bytes(payload)
        os.replace(staging, final)
        created[:] = [final]
        add("writable", PASS, "a file was created and flushed")
        add("atomic_promotion", PASS if landed and sha256_file(final)[0] == sha256_bytes(payload) and not staging.exists() else FAIL,
            "staged, hashed, renamed and re-read with the same digest")
        try:
            with open(final, "xb"):
                pass
            add("no_silent_overwrite", FAIL, "an exclusive create replaced an existing file")
        except FileExistsError:
            add("no_silent_overwrite", PASS, "an exclusive create refuses an existing name")
        upper = directory / "CASE.probe"
        with open(upper, "xb"):
            created.append(upper)
        add("case_sensitivity", INFO, "case-insensitive names" if (directory / "case.probe").exists() else "case-sensitive names")
        long_name = directory / ("pk1-" + "x" * 180 + ".warc.gz")
        try:
            with open(long_name, "xb"):
                created.append(long_name)
            add("long_names", PASS, "a 190-character file name can be created")
        except OSError as error:
            add("long_names", FAIL, f"a 190-character file name cannot be created: {type(error).__name__}")
    except OSError as error:
        add("writable", FAIL, f"{type(error).__name__}: the probe could not write")
    finally:
        _remove_probe(directory, created)


def _remove_probe(directory: Path, created: list[Path]) -> None:
    """Remove the probe's own files and its own directory — nothing else, and only inside
    ``_readiness_probe/``.
    """
    if PROBE_DIRECTORY not in directory.parts:
        raise TargetError("refusing to clean up outside the readiness probe directory")
    for path in created:
        try:
            path.unlink()
        except OSError:
            pass
    for path in (directory, directory.parent):
        try:
            path.rmdir()
        except OSError:
            pass


def _fixity(root: Path, add, limit: int) -> None:
    """Verify up to ``limit`` held objects per area against their manifests."""
    manifests = root / "preservation" / "manifests"
    if not manifests.is_dir():
        add("fixity", INFO, "nothing is held yet")
        return
    verified, failed = 0, []
    for area in sorted(path.name for path in manifests.iterdir() if path.is_dir()):
        for manifest in sorted((manifests / area).glob("*.json"))[:limit]:
            try:
                ok = preservation.verify_master(root, area, manifest.stem)
            except preservation.PreservationError:
                ok = False
            verified += ok
            if not ok:
                failed.append(f"{area}/{manifest.stem}")
    add("fixity", FAIL if failed else PASS, f"{verified} object(s) verified" + (f"; do not verify: {failed}" if failed else ""))
