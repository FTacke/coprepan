"""Bounded outage spool for the preservation target (``docs/storage/INDEX.md`` §6).

When the preservation root is unavailable, a verified local copy is spooled and the object is
``PRESERVATION_PENDING`` — not preserved. When the target returns, :func:`drain` runs the same
promotion function. The spool answers *unavailability only*: a refusal about content (hash
mismatch, identity conflict) is never rerouted into it.

The spool is not a second archive. Its copy of an object is released only after the promoted
master has been re-read and verified; that release lives here, not in the preservation module,
which has no deletion path at all.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

from . import naming, preservation
from .canonical import _discard_staging, record_json, sha256_file, staging_path, write_bytes_atomic
from .identity import format_instant
from .storage_roots import StorageRefusal, probe

SPOOL_RECORD_SCHEMA = naming.schema_id("preservation-spool", 1)
SPOOL_POLICY_VERSION = "preservation-outage-spool/v1"

ROUTE_DIRECT = "direct"
ROUTE_SPOOLED = "spooled"

DRAIN_PRESERVED = "preserved"
DRAIN_TARGET_UNAVAILABLE = "target_unavailable"
DRAIN_REFUSED = "refused"


class SpoolCapacityExceeded(StorageRefusal):
    """Spooling this object would break a bound of the spool policy."""


@dataclass(frozen=True)
class SpoolPolicy:
    """Both bounds are required: there is no built-in default size for somebody else's disk.

    ``min_free_bytes``: free space that must remain on the spool volume after the write.
    ``max_spool_bytes``: ceiling on the bytes held in the spool after the write.
    """

    min_free_bytes: int
    max_spool_bytes: int

    def __post_init__(self) -> None:
        for name in ("min_free_bytes", "max_spool_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer: {value!r}")


@dataclass(frozen=True)
class PreserveOutcome:
    route: str
    state: str
    object_id: str
    promotion: preservation.PromotionResult | None = None
    reason: str | None = None


@dataclass(frozen=True)
class DrainResult:
    object_id: str
    action: str
    detail: str | None = None


def spooled_bytes(spool_root: Path) -> int:
    pending = spool_root / "preservation" / "pending"
    if not pending.is_dir():
        return 0
    return sum(path.stat().st_size for path in pending.rglob("*") if path.is_file())


def pending_records(spool_root: Path) -> list[dict[str, Any]]:
    """Pending records, oldest first (then by object id, so the order is deterministic)."""
    directory = spool_root / "state" / "pending"
    if not directory.is_dir():
        return []
    records = [json.loads(path.read_text(encoding="utf-8")) for path in directory.glob("*.json")]
    for record in records:
        if record.get("schema") != SPOOL_RECORD_SCHEMA:
            raise preservation.PreservationError(f"not a spool record: {record.get('object_id')!r}")
    return sorted(records, key=lambda record: (record["spooled_at"], record["object_id"]))


def record_name(area: str, object_id: str) -> str:
    """The file name of a pending record. One record per *(area, object)*: a pack and its index are
    two objects of two areas under one object id, and both can be pending at once."""
    return f"{area}--{object_id}.json"


def _record_path(spool_root: Path, area: str, object_id: str) -> Path:
    """Where the pending record of an object lies. A record written before records were named per
    area (``<object_id>.json``) is still found, if it is the record of this area."""
    directory = spool_root / "state" / "pending"
    legacy = directory / f"{object_id}.json"
    if legacy.is_file():
        try:
            if json.loads(legacy.read_text(encoding="utf-8")).get("area") == area:
                return legacy
        except (OSError, ValueError):
            pass
    return directory / record_name(area, object_id)


def spool_object(
    source: Path,
    *,
    spool_root: Path,
    policy: SpoolPolicy,
    reason: str,
    area: str,
    object_id: str,
    relative_path: str,
    declared_sha256: str,
    details: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    free_bytes: Callable[[Path], int | None] | None = None,
) -> None:
    """Spool one object whose promotion failed for unavailability: a verified copy and its pending
    record, within the bounds of ``policy``. Idempotent. The caller has established that the
    refusal was about availability; a content refusal is never brought here.
    """
    _spool(source, spool_root, policy, reason, free_bytes or _free_bytes, area=area, object_id=object_id,
           relative_path=relative_path, declared_sha256=declared_sha256, details=details, now=now)


def preserve_or_spool(
    source: Path,
    *,
    preservation_root: Callable[[], Path],
    spool_root: Path | None,
    policy: SpoolPolicy | None,
    area: str,
    object_id: str,
    relative_path: str,
    declared_sha256: str,
    details: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    free_bytes: Callable[[Path], int | None] | None = None,
) -> PreserveOutcome:
    """Promote directly, or spool when — and only when — the target is unavailable.

    ``preservation_root`` resolves the root at call time and raises a ``StorageRefusal`` when the
    target cannot be used. Without a spool (``spool_root`` is ``None``) unavailability propagates.
    """
    arguments = dict(
        area=area, object_id=object_id, relative_path=relative_path, declared_sha256=declared_sha256,
        details=details, now=now,
    )
    try:
        result = preservation.promote(source, root=preservation_root(), **arguments)
        return PreserveOutcome(ROUTE_DIRECT, result.state, result.object_id, promotion=result)
    except preservation.ContentRefusal:
        raise
    except preservation.PreservationError as error:
        if not isinstance(error.__cause__, OSError):
            raise
        reason = f"io_error: {type(error.__cause__).__name__}"
    except StorageRefusal as error:
        reason = f"target_unavailable: {type(error).__name__}"
    if spool_root is None:
        raise StorageRefusal(f"{object_id}: preservation target unavailable and no spool configured ({reason})")
    if policy is None:
        raise StorageRefusal(f"{object_id}: a spool needs an explicit SpoolPolicy")

    _spool(source, spool_root, policy, reason, free_bytes or _free_bytes, **arguments)
    return PreserveOutcome(ROUTE_SPOOLED, preservation.STATE_PENDING, object_id, reason=reason)


def _free_bytes(root: Path) -> int | None:
    return probe(root).free_bytes


def _spool(source, spool_root, policy, reason, free_bytes, *, area, object_id, relative_path,
           declared_sha256, details, now) -> None:
    target_relative = preservation.master_relative_path(area, relative_path)
    preservation.manifest_relative_path(area, object_id)   # validates the area and the object id
    record_path = _record_path(spool_root, area, object_id)
    actual, size = sha256_file(source)
    if actual != declared_sha256:
        raise preservation.HashMismatch(f"{object_id}: source bytes hash to {actual}, declared {declared_sha256}")

    spool_relative = str(PurePosixPath("preservation", "pending", *PurePosixPath(target_relative).parts[1:]))
    destination = spool_root / spool_relative
    if record_path.exists():
        held = json.loads(record_path.read_text(encoding="utf-8"))
        if held["sha256"] != declared_sha256:
            raise preservation.IdentityConflict(f"{object_id}: already spooled with sha256 {held['sha256']}")
        if destination.is_file() and sha256_file(destination) == (actual, size):
            return

    free = free_bytes(spool_root)
    if free is None:
        raise SpoolCapacityExceeded(f"{object_id}: free space of the spool volume is unknown")
    if free - size < policy.min_free_bytes:
        raise SpoolCapacityExceeded(f"{object_id}: spooling would leave less than the required free space")
    if spooled_bytes(spool_root) + size > policy.max_spool_bytes:
        raise SpoolCapacityExceeded(f"{object_id}: spooling would exceed the spool ceiling")

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = staging_path(destination)
    try:
        with open(source, "rb") as reader, open(staging, "xb") as writer:
            shutil.copyfileobj(reader, writer, 1024 * 1024)
            writer.flush()
            os.fsync(writer.fileno())
        if sha256_file(staging) != (actual, size):
            raise preservation.HashMismatch(f"{object_id}: spooled bytes differ from the source")
        os.replace(staging, destination)
    finally:
        _discard_staging(staging)
    write_bytes_atomic(
        record_path,
        record_json(
            {
                "schema": SPOOL_RECORD_SCHEMA,
                "policy_version": SPOOL_POLICY_VERSION,
                "object_id": object_id,
                "state": preservation.STATE_PENDING,
                "area": area,
                "relative_path": relative_path,
                "spool_relative_path": spool_relative,
                "target_relative_path": target_relative,
                "sha256": actual,
                "size_bytes": size,
                "spooled_at": format_instant(now if now is not None else datetime.now(timezone.utc)),
                "reason": reason,
                "details": dict(details or {}),
            }
        ),
    )


def drain(
    spool_root: Path,
    *,
    preservation_root: Callable[[], Path],
    now: datetime | None = None,
) -> list[DrainResult]:
    """Promote pending objects, oldest first. Stops at the first sign that the target is still
    unavailable. A content refusal is reported and the object stays in the spool for the operator.
    """
    results = []
    for record in pending_records(spool_root):
        object_id = record["object_id"]
        spooled = spool_root / record["spool_relative_path"]
        try:
            root = preservation_root()
            preservation.promote(
                spooled, root=root, area=record["area"], object_id=object_id,
                relative_path=record["relative_path"], declared_sha256=record["sha256"],
                details=record["details"], now=now,
            )
            verified = preservation.verify_master(root, record["area"], object_id)
        except preservation.ContentRefusal as error:
            results.append(DrainResult(object_id, DRAIN_REFUSED, str(error)))
            continue
        except (StorageRefusal, preservation.PreservationError, OSError) as error:
            results.append(DrainResult(object_id, DRAIN_TARGET_UNAVAILABLE, type(error).__name__))
            break
        if not verified:
            results.append(DrainResult(object_id, DRAIN_REFUSED, "promoted master did not verify"))
            continue
        _release(spool_root, record)
        results.append(DrainResult(object_id, DRAIN_PRESERVED))
    return results


def _release(spool_root: Path, record: Mapping[str, Any]) -> None:
    """Free the spool copy of an object whose master has just been verified on the target."""
    (spool_root / record["spool_relative_path"]).unlink()
    _record_path(spool_root, record["area"], record["object_id"]).unlink()
