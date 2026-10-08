"""Append-only line-oriented tables (one JSON object per line).

Used for identity tables and other append-only records. A row is appended and flushed to disk
before the call returns; nothing is ever rewritten. A file that ends in an incomplete line is
refused, not silently repaired (``recovery.repair`` moves a torn tail aside, on request).

**One writer at a time.** Appending is not atomic between processes: on this project's
workstation platform two processes appending to one file overwrite each other's lines (measured
2026-10-08: 900 appends reported, 597 rows on disk). The single writer is enforced one level up,
by :func:`coprepan.exclusive.exclusive` around every operation that writes a workspace. As a
tripwire, every append re-reads what it wrote and refuses to report success if the file does not
end in exactly that line.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Hashable, Iterable, Mapping

from .canonical import append_lock, line_json, sha256_bytes


class JsonlError(RuntimeError):
    """The table cannot be trusted or cannot be appended to."""


class TornTail(JsonlError):
    """The file ends in an incomplete line: a write was interrupted."""


class ConcurrentAppend(JsonlError):
    """What was appended is not what the file now holds there: somebody else wrote at the same time."""


def append_line(path: Path, line: bytes, *, expected_size: int | None = None) -> None:
    """Append one complete line durably, and verify that it is the line now standing at the end.

    Appends to one file are serialised between processes by an operating-system lock held for
    the length of the append. ``expected_size``: the size the caller last saw; a file of another
    size was written by somebody else in between and is refused — for a writer whose record
    depends on what came before (the ledger's sequence).

    Raises :class:`TornTail` when the file ends in an incomplete line (nothing is written), and
    :class:`ConcurrentAppend` when the file is not as expected before, or not as written after.
    """
    _append(Path(path), lambda previous: line, expected_size)


def _last_line(descriptor: int, size: int) -> bytes:
    """The last complete line of a file of ``size`` bytes that ends in a newline, with its newline."""
    end, window = size, 4096
    while True:
        start = max(0, end - window)
        os.lseek(descriptor, start, os.SEEK_SET)
        block = os.read(descriptor, end - start)
        cut = block.rfind(b"\n", 0, len(block) - 1 if end == size else len(block))
        if cut >= 0:
            os.lseek(descriptor, start + cut + 1, os.SEEK_SET)
            return os.read(descriptor, size - (start + cut + 1))
        if start == 0:
            os.lseek(descriptor, 0, os.SEEK_SET)
            return os.read(descriptor, size)
        window *= 2


def _append(path: Path, build: Callable[[bytes | None], bytes], expected_size: int | None) -> bytes:
    """Append what ``build(last_line)`` returns — ``last_line`` being the line the file ends in
    (``None`` for an empty file), read under the append lock, so that two appenders can never
    both build on the same predecessor.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0))
    try:
        with append_lock(descriptor):
            before = os.fstat(descriptor).st_size
            if expected_size is not None and before != expected_size and before:
                os.lseek(descriptor, before - 1, os.SEEK_SET)
                if os.read(descriptor, 1) == b"\n":   # a torn tail is reported as that, below
                    raise ConcurrentAppend(f"{path.name}: the file changed since it was read; another writer is active")
            if before:
                os.lseek(descriptor, before - 1, os.SEEK_SET)
                if os.read(descriptor, 1) != b"\n":
                    raise TornTail(f"{path.name}: refusing to append after an incomplete line")
            line = build(_last_line(descriptor, before) if before else None)
            if not line.endswith(b"\n") or line.count(b"\n") != 1:
                raise JsonlError("an appended line is exactly one line")
            os.write(descriptor, line)
            os.fsync(descriptor)
            os.lseek(descriptor, before, os.SEEK_SET)
            if os.fstat(descriptor).st_size != before + len(line) or os.read(descriptor, len(line)) != line:
                raise ConcurrentAppend(f"{path.name}: the appended line is not what the file holds; another writer is active")
            return line
    finally:
        os.close(descriptor)


# --- chained tables ---------------------------------------------------------------------------------
#
# Primary evidence that nothing else can re-derive is chained like the ledger (CPD-0009 §5, CPD-0010):
# every row carries ``previous_row_sha256``, the SHA-256 of the line before it (``null`` for the
# first). A changed, removed, inserted, duplicated or moved row breaks the chain at the row after
# it. A torn tail is not a break: it is an incomplete line, reported as such, and the complete rows
# before it still authenticate each other. The last complete row has no successor to vouch for it.

CHAIN_FIELD = "previous_row_sha256"


class ChainBroken(JsonlError):
    """A row does not name the row before it: earlier evidence was changed, removed, inserted or moved."""


def read_chained(path: Path, schema: str) -> list[dict[str, Any]]:
    """Every row of a chained table, each checked against the line before it."""
    path = Path(path)
    if not path.exists():
        return []
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        raise TornTail(f"{path.name}: ends in an incomplete line")
    rows, previous = [], None
    for number, line in enumerate(data.split(b"\n")[:-1], 1):
        try:
            row = json.loads(line.decode("utf-8"))
            if row["schema"] != schema:
                raise ValueError(f"schema {row['schema']!r}")
            claimed = row[CHAIN_FIELD]
        except (ValueError, KeyError, TypeError) as error:
            raise JsonlError(f"{path.name}: line {number} is not a {schema} row: {error}") from error
        if claimed != previous:
            raise ChainBroken(f"{path.name}: line {number} does not follow the row before it: "
                              "an earlier row was changed, removed, inserted or moved")
        rows.append(row)
        previous = sha256_bytes(line + b"\n")
    return rows


def append_chained(path: Path, schema: str, row: Mapping[str, Any]) -> dict[str, Any]:
    """Append one row that names the row before it, and return it as written."""
    if CHAIN_FIELD in row:
        raise JsonlError(f"{CHAIN_FIELD} is set by the table, not by the caller")
    written: dict[str, Any] = {}

    def build(last: bytes | None) -> bytes:
        written.update(row, schema=schema, **{CHAIN_FIELD: sha256_bytes(last) if last is not None else None})
        return line_json(written)
    _append(Path(path), build, None)
    return written


def read_rows(path: Path, schema: str) -> list[dict[str, Any]]:
    """Every row of the table, in order. An absent file is an empty table."""
    path = Path(path)
    if not path.exists():
        return []
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        raise TornTail(f"{path.name}: ends in an incomplete line")
    rows = []
    for number, line in enumerate(data.split(b"\n")[:-1], 1):
        try:
            row = json.loads(line.decode("utf-8"))
            if row["schema"] != schema:
                raise ValueError(f"schema {row['schema']!r}")
        except (ValueError, KeyError, TypeError) as error:
            raise JsonlError(f"{path.name}: line {number} is not a {schema} row: {error}") from error
        rows.append(row)
    return rows


def append_row(path: Path, schema: str, row: Mapping[str, Any]) -> dict[str, Any]:
    """Append one row durably and return it as written."""
    written = {**row, "schema": schema}
    append_line(Path(path), line_json(written))
    return written


def keyed(rows: Iterable[Mapping[str, Any]], key: Callable[[Mapping[str, Any]], Hashable], table: str) -> dict[Any, Any]:
    """Rows by their key. The same row twice is one row (an append that was repeated); **two
    different rows under one key are refused** — a table never answers with whichever came last.
    """
    out: dict[Any, Any] = {}
    for row in rows:
        identifier = key(row)
        if identifier in out and out[identifier] != row:
            raise JsonlError(f"{table}: two different rows for {identifier!r}")
        out.setdefault(identifier, row)
    return out
