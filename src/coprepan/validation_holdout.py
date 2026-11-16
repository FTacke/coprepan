"""The validation holdout's separation from development (CPD-0044).

Acquisition runs made for an independent validation are listed in ``config/validation/holdout_runs.json``
(``coprepan-holdout-runs/v1``). Every development study iterates stored pages through ``scripts/study_content_quality.pages``,
which leaves these runs out unless it is told to include them -- only the gold tooling does, and only after the gold of their
package is frozen. A run is added to the register **before** anything reads its pages; it is never removed (a holdout once
seen by development is no longer one, and the register records the fact instead of hiding it).
"""

from __future__ import annotations

import json
from pathlib import Path

SCHEMA = "coprepan-holdout-runs/v1"
PATH = "config/validation/holdout_runs.json"
_REPOSITORY = Path(__file__).resolve().parents[2]


class HoldoutError(ValueError):
    """The register is missing or not this schema -- a refusal, never an empty register."""


def holdout_runs(root: Path = _REPOSITORY) -> frozenset[str]:
    """The run ids of the validation holdout (an empty register is a valid answer; a missing or foreign file is not)."""
    path = root / PATH
    if not path.is_file():
        raise HoldoutError(f"{PATH}: missing -- the holdout register is required")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA or not isinstance(data.get("runs"), list):
        raise HoldoutError(f"{PATH}: not a {SCHEMA} register")
    return frozenset(r["run_id"] for r in data["runs"])


__all__ = ["holdout_runs", "HoldoutError", "SCHEMA", "PATH"]
