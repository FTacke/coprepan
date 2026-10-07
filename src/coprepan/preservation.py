"""Promotion of a sealed object to the preservation root (``docs/storage/INDEX.md`` §6).

```text
sealed object → validate → stable identity → sha256 → manifest → verified immutable master
```

The promotion unit is "a file with a stable identity and a manifest" — for COPREPAN 3.0 a sealed
pack. What a pack is and how it is named belongs to Phase 2; this module promotes any sealed file
under the same on-disk contract CO.RA.PAN 3.0 uses for its raw masters (staging name, hashing of
the landed bytes, atomic rename, manifest rendering), so a later consolidation moves no data.

**This module has no deletion path.** The only file it ever removes is its own ``.part-`` staging
file after a failed write; ``tests/test_preservation.py`` asserts that structurally.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from . import naming
from .canonical import (
    _discard_staging,
    publish_exclusive,
    record_json,
    require_sha256,
    sha256_file,
    staging_path,
    write_bytes_atomic,
    write_bytes_exclusive,
)
from .identity import format_instant

MANIFEST_SCHEMA = naming.schema_id("preservation-manifest", 1)
POLICY_VERSION = "preservation/v1"
DATA_CLASS = "acquisition_source"
STATE_PRESERVED = "RAW_PRESERVED"
STATE_PENDING = "PRESERVATION_PENDING"

ACTION_PROMOTED = "promoted"
ACTION_ALREADY_PRESERVED = "already_preserved"
ACTION_REPAIRED = "repaired"
ACTION_DUPLICATE_RECORDED = "duplicate_recorded"
ACTIONS = (ACTION_PROMOTED, ACTION_ALREADY_PRESERVED, ACTION_REPAIRED, ACTION_DUPLICATE_RECORDED)

_OBJECT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_AREA = re.compile(r"[a-z][a-z0-9_]*")
_COPY_CHUNK = 1024 * 1024


class PreservationError(RuntimeError):
    """A promotion could not be completed. An I/O cause is kept as ``__cause__``."""


class ContentRefusal(PreservationError):
    """A refusal about the content itself. Never rerouted into the outage spool."""


class HashMismatch(ContentRefusal):
    """Declared and actual bytes differ, or the landed bytes differ from the source."""


class IdentityConflict(ContentRefusal):
    """The identity is already bound to different content. Never resolved automatically."""


@dataclass(frozen=True)
class PromotionResult:
    object_id: str
    state: str
    action: str
    relative_path: str
    sha256: str
    size_bytes: int
    manifest_path: Path
    duplicate_of: str | None = None


def master_relative_path(area: str, relative_path: str) -> str:
    """``preservation/<area>/<relative_path>`` below the preservation root, POSIX separators."""
    return str(PurePosixPath("preservation", _area(area), *_relative_parts(relative_path)))


def manifest_relative_path(area: str, object_id: str) -> str:
    """``preservation/manifests/<area>/<object_id>.json`` below the preservation root."""
    return str(PurePosixPath("preservation", "manifests", _area(area), f"{_object_id(object_id)}.json"))


def read_manifest(root: Path, area: str, object_id: str) -> dict[str, Any] | None:
    path = root / manifest_relative_path(area, object_id)
    if not path.exists():
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest["schema"] != MANIFEST_SCHEMA or manifest["object_id"] != object_id:
            raise ValueError("schema or object_id does not match")
        require_sha256(manifest["sha256"], "manifest sha256")
        if _relative_parts(manifest["relative_path"])[:2] != ("preservation", manifest["area"]):
            raise ValueError("relative_path leaves its preservation area")
        if not isinstance(manifest["size_bytes"], int):
            raise ValueError("size_bytes is not an integer")
    except (ValueError, KeyError, TypeError, OSError, PreservationError) as error:
        raise PreservationError(f"manifest of {object_id} is unreadable: {error}") from error
    return manifest


def verify_master(root: Path, area: str, object_id: str) -> bool:
    """Whether the manifest's master exists and its bytes hash to the manifest's digest."""
    manifest = read_manifest(root, area, object_id)
    if manifest is None:
        return False
    return _holds(root / manifest["relative_path"], manifest["sha256"], manifest["size_bytes"])


def promote(
    source: Path,
    *,
    root: Path,
    area: str,
    object_id: str,
    relative_path: str,
    declared_sha256: str,
    details: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> PromotionResult:
    """Promote one sealed file. ``root`` is an already resolved, writable preservation root.

    Outcomes: ``promoted``; ``already_preserved`` (a completed promotion re-verifies and writes
    nothing); ``repaired`` (an interrupted or damaged promotion is completed and reported);
    ``duplicate_recorded`` (the same bytes are already held under another identity: a manifest is
    written that points at the existing master, and nothing is copied).

    Refusals: :class:`HashMismatch`, :class:`IdentityConflict` — and any I/O failure as a
    :class:`PreservationError` whose ``__cause__`` is the ``OSError``.
    """
    object_id = _object_id(object_id)
    declared = require_sha256(declared_sha256, "declared_sha256")
    target_relative = master_relative_path(area, relative_path)
    manifest_path = root / manifest_relative_path(area, object_id)
    try:
        actual, size = sha256_file(source)
    except OSError as error:
        raise PreservationError(f"{object_id}: source is not readable") from error
    if actual != declared:
        raise HashMismatch(f"{object_id}: source bytes hash to {actual}, declared {declared}")

    try:
        existing = read_manifest(root, area, object_id)
        if existing is not None:
            if existing["sha256"] != declared:
                raise IdentityConflict(
                    f"{object_id}: already preserved with sha256 {existing['sha256']}, offered {declared}"
                )
            if _holds(root / existing["relative_path"], declared, size):
                return _result(existing, manifest_path, ACTION_ALREADY_PRESERVED)
            if existing.get("duplicate_of"):
                raise PreservationError(
                    f"{object_id}: recorded as a duplicate of {existing['duplicate_of']}, whose master does not verify"
                )
            if existing["relative_path"] != target_relative:
                raise IdentityConflict(
                    f"{object_id}: preserved at {existing['relative_path']}, offered for {target_relative}"
                )
            action = ACTION_REPAIRED
        else:
            holder = find_by_content(root, area, declared)
            if holder is not None and _holds(root / holder["relative_path"], declared, size):
                manifest = _manifest(object_id, area, holder["relative_path"], declared, size, details, now)
                manifest["duplicate_of"] = holder.get("duplicate_of") or holder["object_id"]
                return _bind(root, area, object_id, manifest_path, manifest, ACTION_DUPLICATE_RECORDED, new=True)
            action = ACTION_PROMOTED

        destination = root / target_relative
        if destination.exists():
            if _holds(destination, declared, size):
                action = ACTION_REPAIRED
            elif existing is None:
                raise IdentityConflict(f"{object_id}: {target_relative} already holds different bytes")
            else:
                # the manifest says these bytes belong here and the master does not hold them:
                # the one case in which a master is replaced
                _land(source, destination, declared, size, object_id, replace=True)
        else:
            _land(source, destination, declared, size, object_id, replace=False)

        manifest = _manifest(object_id, area, target_relative, declared, size, details, now)
        return _bind(root, area, object_id, manifest_path, manifest, action, new=existing is None)
    except OSError as error:
        raise PreservationError(f"{object_id}: promotion failed on I/O") from error


def _bind(root: Path, area: str, object_id: str, manifest_path: Path, manifest: dict[str, Any], action: str, *, new: bool) -> PromotionResult:
    """Write the manifest that binds an identity to its bytes. For an identity that had none, the
    manifest is created exclusively: if another process bound the identity in the meantime, its
    manifest stands — the same content is the same promotion, other content is a conflict.
    """
    if not new:
        write_bytes_atomic(manifest_path, record_json(manifest))
        return _result(manifest, manifest_path, action)
    try:
        write_bytes_exclusive(manifest_path, record_json(manifest))
    except FileExistsError:
        standing = read_manifest(root, area, object_id)
        if standing is None or standing["sha256"] != manifest["sha256"]:
            raise IdentityConflict(
                f"{object_id}: bound to sha256 {standing and standing['sha256']} by another process while this promotion ran"
            ) from None
        return _result(standing, manifest_path, ACTION_ALREADY_PRESERVED)
    return _result(manifest, manifest_path, action)


def find_by_content(root: Path, area: str, sha256: str) -> dict[str, Any] | None:
    """The manifest of an object in ``area`` that already holds these bytes, if any.

    A linear scan of the area's manifests, in name order so the answer is deterministic.
    """
    directory = (root / manifest_relative_path(area, "x")).parent
    if not directory.is_dir():
        return None
    for path in sorted(directory.glob("*.json")):
        manifest = read_manifest(root, area, path.stem)
        if manifest is not None and manifest["sha256"] == sha256:
            return manifest
    return None


# --- internals --------------------------------------------------------------------------------


def _land(source: Path, destination: Path, sha256: str, size: int, object_id: str, *, replace: bool) -> None:
    """Copy to a ``.part-`` name beside the destination, hash the landed bytes, then give them
    the master's name — exclusively, unless a damaged master is being replaced. Two processes that
    land at once cannot overwrite each other: the second finds the name taken and either sees its
    own bytes there (the same promotion) or has a conflict.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = staging_path(destination)
    try:
        with open(source, "rb") as reader, open(staging, "xb") as writer:
            shutil.copyfileobj(reader, writer, _COPY_CHUNK)
            writer.flush()
            os.fsync(writer.fileno())
        landed, landed_size = sha256_file(staging)
        if landed != sha256 or landed_size != size:
            raise HashMismatch(f"{object_id}: landed bytes hash to {landed}, expected {sha256}")
        if replace:
            os.replace(staging, destination)
        else:
            try:
                publish_exclusive(staging, destination)
            except FileExistsError:
                if not _holds(destination, sha256, size):
                    raise IdentityConflict(f"{object_id}: {destination.name} was taken by other bytes while this promotion ran") from None
    finally:
        _discard_staging(staging)


def _holds(path: Path, sha256: str, size: int) -> bool:
    if not path.is_file() or path.stat().st_size != size:
        return False
    return sha256_file(path)[0] == sha256


def _manifest(object_id, area, relative_path, sha256, size, details, now) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "policy_version": POLICY_VERSION,
        "object_id": object_id,
        "area": area,
        "state": STATE_PRESERVED,
        "relative_path": relative_path,
        "sha256": sha256,
        "size_bytes": size,
        "data_class": DATA_CLASS,
        "preserved_at": format_instant(now if now is not None else datetime.now(timezone.utc)),
        "duplicate_of": None,
        "details": dict(details or {}),
    }


def _result(manifest: Mapping[str, Any], manifest_path: Path, action: str) -> PromotionResult:
    return PromotionResult(
        manifest["object_id"],
        manifest["state"],
        action,
        manifest["relative_path"],
        manifest["sha256"],
        manifest["size_bytes"],
        manifest_path,
        manifest.get("duplicate_of"),
    )


def _object_id(value: str) -> str:
    if not isinstance(value, str) or _OBJECT_ID.fullmatch(value) is None or ".part-" in value:
        raise PreservationError(f"not a usable object id (letters, digits, '.', '_', '-'): {value!r}")
    return value


def _area(value: str) -> str:
    if not isinstance(value, str) or _AREA.fullmatch(value) is None or value == "manifests":
        raise PreservationError(f"not a preservation area name: {value!r}")
    return value


def _relative_parts(relative_path: str) -> tuple[str, ...]:
    """A relative POSIX path of safe components: no drive, no root, no ``..``, no staging name."""
    if not isinstance(relative_path, str) or not relative_path or "\\" in relative_path:
        raise PreservationError(f"not a relative POSIX path: {relative_path!r}")
    parts = relative_path.split("/")
    for part in parts:
        if _OBJECT_ID.fullmatch(part) is None or ".part-" in part:
            raise PreservationError(f"unsafe path component {part!r} in {relative_path!r}")
    return tuple(parts)
