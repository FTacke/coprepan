"""The chained evidence tables of a workspace, and the heads that anchor them (decision CPD-0010).

A chain authenticates every row by the row after it. The newest row has no successor, so
until the next append it is vouched for by nothing. When a run closes, the **head** of every
chained table — how many rows it held and the hash of the last line — is written into the run's
result. A later reader can then check that the row at that position is still the row that was
there: from a clean close on, every row of every chained table is covered.

Not covered, and said so: rows appended after the last closed run, until the next append or close.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .canonical import sha256_bytes

LEDGER = "ledgers/preservation.jsonl"


def chained_tables() -> dict[str, str]:
    """The chained primary-evidence tables, by path in the workspace, with the schema of each.
    (The ledger is chained too, in its own record format.)
    """
    from . import admission, candidate_filter, discovery, http_acquisition
    return {"requests/requests.jsonl": http_acquisition.REQUEST_LOG_SCHEMA, "discovery/inputs.jsonl": discovery.INPUT_SCHEMA,
            "discovery/events.jsonl": discovery.EVENT_SCHEMA, "discovery/qualifications.jsonl": candidate_filter.QUALIFICATION_SCHEMA,
            "admission/labels.jsonl": admission.LABEL_SCHEMA}


def _lines(path: Path) -> list[bytes]:
    data = path.read_bytes()
    return data.split(b"\n")[:-1] if data.endswith(b"\n") else data.split(b"\n")[:-1]


def heads(workspace_root: Path) -> dict[str, dict[str, Any]]:
    """``{path: {"rows": n, "head_sha256": hash of the last complete line}}`` of every chained
    table that exists and is not empty. Reads the files; verifies nothing.
    """
    out = {}
    for relative in (*chained_tables(), LEDGER):
        path = Path(workspace_root) / relative
        if path.exists():
            lines = _lines(path)
            if lines:
                out[relative] = {"rows": len(lines), "head_sha256": sha256_bytes(lines[-1] + b"\n")}
    return out


def mismatches(workspace_root: Path, recorded: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """Where the tables no longer hold what was recorded at a close: a table shorter than it was,
    or whose row at the recorded position is another row.
    """
    problems = []
    for relative, head in sorted(recorded.items()):
        path = Path(workspace_root) / relative
        lines = _lines(path) if path.exists() else []
        if len(lines) < head["rows"]:
            problems.append(f"{relative}: {len(lines)} rows, {head['rows']} were recorded")
        elif sha256_bytes(lines[head["rows"] - 1] + b"\n") != head["head_sha256"]:
            problems.append(f"{relative}: row {head['rows']} is not the row that was recorded")
    return problems
