"""Append-only line-oriented tables (one JSON object per line).

Used for identity tables and other append-only records. A row is appended and flushed to disk
before the call returns; nothing is ever rewritten. A file that ends in an incomplete line is
refused, not silently repaired. One writer at a time.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from .canonical import line_json


class JsonlError(RuntimeError):
    """The table cannot be trusted or cannot be appended to."""


def read_rows(path: Path, schema: str) -> list[dict[str, Any]]:
    """Every row of the table, in order. An absent file is an empty table."""
    path = Path(path)
    if not path.exists():
        return []
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        raise JsonlError(f"{path.name}: ends in an incomplete line")
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
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size:
        with open(path, "rb") as handle:
            handle.seek(-1, os.SEEK_END)
            if handle.read(1) != b"\n":
                raise JsonlError(f"{path.name}: refusing to append after an incomplete line")
    written = {**row, "schema": schema}
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0))
    try:
        os.write(descriptor, line_json(written))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return written
