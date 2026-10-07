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

from .canonical import append_lock, line_json


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
    if not line.endswith(b"\n") or line.count(b"\n") != 1:
        raise JsonlError("an appended line is exactly one line")
    path = Path(path)
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
            os.write(descriptor, line)
            os.fsync(descriptor)
            os.lseek(descriptor, before, os.SEEK_SET)
            if os.fstat(descriptor).st_size != before + len(line) or os.read(descriptor, len(line)) != line:
                raise ConcurrentAppend(f"{path.name}: the appended line is not what the file holds; another writer is active")
    finally:
        os.close(descriptor)


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
