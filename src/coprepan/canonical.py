"""Canonical bytes for hashing, and the two JSON renderings this repository writes.

One rule for every hashed structure (decision CPD-0003 §1): the preimage is the UTF-8 encoding of
the JSON text with sorted keys, no insignificant whitespace and non-ASCII characters written
literally. The same serialisation is the one CO.RA.PAN 3.0 uses for its layer-store fingerprints,
so a fingerprint means the same thing in both repositories.

Human-readable records (manifests) are a different rendering and are never hashed for identity.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
_CHUNK = 1024 * 1024


def canonical_json(value: Any) -> bytes:
    """The bytes a hash of ``value`` is taken over. Refuses NaN, infinities and non-JSON types."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def record_json(value: Any) -> bytes:
    """A stored, human-readable record: indented, sorted, one trailing newline, LF only."""
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return (text + "\n").encode("utf-8")


def line_json(value: Any) -> bytes:
    """One line of a line-oriented ledger or index."""
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return (text + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    """``(sha256, size)`` of a file, read in chunks."""
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def is_sha256(value: object) -> bool:
    """A full SHA-256 digest in lower-case hexadecimal."""
    return isinstance(value, str) and _SHA256_HEX.fullmatch(value) is not None


def require_sha256(value: object, what: str) -> str:
    if not is_sha256(value):
        raise ValueError(f"{what} is not a lower-case sha256 hex digest: {value!r}")
    return value  # type: ignore[return-value]


_APPEND_LOCK_OFFSET = 1 << 40  # a byte no file of this project reaches: locking it never blocks a reader


@contextmanager
def append_lock(descriptor: int) -> Iterator[None]:
    """Serialise appends to one file between processes for the length of one append.

    Appending is not atomic between processes on every platform (on Windows two appenders
    overwrite each other). Whoever appends holds this lock from before it looks at the end of the
    file until after it has checked what it wrote. It is an operating-system lock on the open
    descriptor: it waits a few seconds for another appender, and it ends with the process.
    """
    if os.name == "nt":
        import msvcrt
        os.lseek(descriptor, _APPEND_LOCK_OFFSET, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)   # retries for about ten seconds, then OSError
        try:
            yield
        finally:
            os.lseek(descriptor, _APPEND_LOCK_OFFSET, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)


def staging_path(final: Path) -> Path:
    """A sibling ``<name>.part-<hex>``: never a master, never read as one."""
    return final.with_name(f"{final.name}.part-{uuid.uuid4().hex[:8]}")


def write_bytes_atomic(final: Path, data: bytes) -> None:
    """Write ``data`` beside ``final`` under a ``.part-`` name, flush to disk, then rename.

    Used for small records (manifests, markers) that may legitimately be rewritten. The file is
    complete or absent; a reader never sees half of it.
    """
    final.parent.mkdir(parents=True, exist_ok=True)
    staging = staging_path(final)
    try:
        with open(staging, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(staging, final)
    finally:
        _discard_staging(staging)


def publish_exclusive(staging: Path, final: Path) -> None:
    """Give a finished staging file its final name **only if that name is free**; raise
    ``FileExistsError`` otherwise. Atomic: never a half-written file under the final name, and
    never a replaced one. (``os.replace`` would silently overwrite what another process put there.)
    """
    if os.name == "nt":
        os.rename(staging, final)      # refuses an existing target on this platform
    else:
        os.link(staging, final)        # refuses an existing target; the caller drops the staging name


def write_bytes_exclusive(final: Path, data: bytes) -> None:
    """Like :func:`write_bytes_atomic`, for a file that must not exist yet: whole or absent, and
    ``FileExistsError`` — nothing written — when somebody else's file already has the name.
    """
    final.parent.mkdir(parents=True, exist_ok=True)
    staging = staging_path(final)
    try:
        with open(staging, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        publish_exclusive(staging, final)
    finally:
        _discard_staging(staging)


def _discard_staging(staging: Path) -> None:
    """Drop a ``.part-`` file left by a failed write. Refuses any other name."""
    if ".part-" not in staging.name:
        raise ValueError(f"not a staging file: {staging.name!r}")
    staging.unlink(missing_ok=True)
