"""The identity tables are derived state: rebuild them from preserved evidence and compare
(decision CPD-0010 §3).

```text
preserved packs (verified masters) + ledger (RAW_PRESERVED) + outlet URL rules + extraction
    ──► documents, observations, versions, relations
```

Nothing else enters. In particular the existing identity tables are not an input: they are what is
being checked. The rebuild reads no network, writes no preserved byte and no layer (a stored
extraction that verifies is used; any other is derived again in memory).

**Canonical order.** Packs by pack id, fetches in index order. The tables are defined as the
derivation in that order. It is also the order in which the pipeline derives them when packs are
identified day by day. A store built in another order can differ in exactly two things that
depend on order: ``first_fetch_id`` of a document (compared as "one of the fetches that observed it") and the existence
and direction of relations (compared exactly — a differing relation is reported, because it
cannot be told from a wrong one).

Statuses:

``CORRECT``
    the existing tables hold exactly the rows the evidence gives (``exact`` when the bytes are
    equal too).
``REBUILDABLE``
    the existing tables are absent, unreadable or a strict subset of what the evidence gives:
    nothing in them contradicts it.
``CONFLICTING``
    the existing tables hold a row the evidence does not support, or a different row where it
    gives one. Not adopted without an explicit decision.
``SOURCE_EVIDENCE_DAMAGED``
    the preserved evidence needed for the rebuild does not verify. Nothing is rebuilt and nothing
    is claimed.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from . import core_pipeline, extraction, ledger as ledger_module, naming, pack, preservation
from .canonical import canonical_json
from .core_pipeline import AREA_PACKS, Workspace
from .exclusive import exclusive
from .identity import IdentityError
from .jsonl import JsonlError, read_rows
from .registry import Registry

REPORT_SCHEMA = naming.schema_id("identity-verification", 1)
CORRECT, REBUILDABLE, CONFLICTING, SOURCE_EVIDENCE_DAMAGED = "CORRECT", "REBUILDABLE", "CONFLICTING", "SOURCE_EVIDENCE_DAMAGED"
TABLES = {"documents": "coprepan-document-identity/v1", "observations": "coprepan-document-observation/v1",
          "versions": "coprepan-document-version/v1", "relations": "coprepan-document-relation/v1"}


class RebuildRefused(RuntimeError):
    """The rebuild was not adopted: the evidence is damaged, or the existing tables conflict with it."""


def preserved_packs(preservation_root: Path) -> list[str]:
    """Every pack on the preservation root with its pack **and** its index manifest, in canonical
    order. A pack whose promotion was interrupted between the two is not preserved yet.
    """
    root = Path(preservation_root)
    held = {}
    for area in (AREA_PACKS, core_pipeline.AREA_INDEXES):
        directory = (root / preservation.manifest_relative_path(area, "x")).parent
        held[area] = {path.stem for path in directory.glob("*.json")} if directory.is_dir() else set()
    return sorted(held[AREA_PACKS] & held[core_pipeline.AREA_INDEXES])


def derive(workspace: Workspace, registry: Registry, *, preservation_root: Path, target: Path,
           extractor: extraction.Extractor = extraction.BASELINE) -> int:
    """Derive the tables into ``target`` (a directory that does not hold tables yet). Returns the
    number of fetches assigned. Raises when the evidence cannot be read or does not verify.
    """
    target = Path(target)
    if any(target.glob("*.jsonl")):
        raise RebuildRefused(f"{target.name} already holds tables: a rebuild writes a new store")
    packs = preserved_packs(preservation_root)
    # Every fetch the ledger records as preserved must lie in a pack this rebuild can read: a
    # pack that vanished from the root is damaged evidence, not a smaller input.
    claimed = {record.details.get("pack_id") for record in workspace.ledger().records() if record.new_state == "RAW_PRESERVED"}
    if claimed - set(packs):
        raise RebuildRefused(f"the ledger records fetches as RAW_PRESERVED in {sorted(claimed - set(packs))}, "
                             "which are not (completely) on the preservation root")
    assigned = 0
    for identifier in packs:
        results = core_pipeline.identify_and_extract(
            workspace, registry, preservation_root=preservation_root, identifier=identifier, extractor=extractor,
            identity_directory=target, read_only_layers=True, skip_unpreserved=True)
        assigned += sum(1 for result in results if result.get("identity") == "assigned")
    return assigned


def _rows(directory: Path) -> dict[str, list[dict[str, Any]]]:
    return {name: read_rows(Path(directory) / f"{name}.jsonl", schema) for name, schema in TABLES.items()}


def _canonical(rows: dict[str, list[dict[str, Any]]], observers: dict[str, set[str]]) -> dict[str, set[str]]:
    """Rows as comparable text: no schema field, no row order. ``first_fetch_id`` depends on the
    order the fetches were identified in, so it is compared as a statement — "this is one of the
    fetches that observed the document" — not as a value: another order passes, a damaged value
    does not.
    """
    out = {}
    for name, table in rows.items():
        keep = []
        for row in table:
            row = {k: v for k, v in row.items() if k != "schema"}
            if name == "documents":
                row["first_fetch_id"] = row.get("first_fetch_id") in observers.get(row.get("document_id"), set())
            keep.append(canonical_json(row).decode("utf-8"))
        out[name] = set(keep)
    return out


def _bytes(directory: Path) -> dict[str, bytes]:
    return {name: (Path(directory) / f"{name}.jsonl").read_bytes() if (Path(directory) / f"{name}.jsonl").exists() else b""
            for name in TABLES}


def verify(workspace: Workspace, registry: Registry, *, preservation_root: Path,
           extractor: extraction.Extractor = extraction.BASELINE) -> dict[str, Any]:
    """Compare the existing identity tables with a rebuild from the evidence. Reads only; the
    rebuild is made in a temporary directory that removes itself.
    """
    report: dict[str, Any] = {"schema": REPORT_SCHEMA, "status": None, "exact": False, "detail": None, "differences": {}}
    with tempfile.TemporaryDirectory(prefix="identity-rebuild-") as scratch:
        try:
            report["fetches_assigned"] = derive(workspace, registry, preservation_root=preservation_root,
                                                target=Path(scratch), extractor=extractor)
        except (core_pipeline.NotPreserved, preservation.PreservationError, pack.PackError, ledger_module.LedgerError,
                IdentityError, JsonlError, OSError, ValueError, KeyError, RebuildRefused) as error:
            report.update(status=SOURCE_EVIDENCE_DAMAGED, detail=f"{type(error).__name__}: {str(error)[:200]}")
            return report
        rebuilt = _rows(Path(scratch))
        rebuilt_bytes = _bytes(Path(scratch))
    try:
        existing = _rows(workspace.identity)
    except (JsonlError, ValueError, OSError) as error:
        report.update(status=REBUILDABLE, detail=f"existing tables unreadable: {type(error).__name__}: {str(error)[:160]}")
        return report
    observers: dict[str, set[str]] = {}
    for row in rebuilt["observations"]:
        observers.setdefault(row["document_id"], set()).add(row["fetch_id"])
    wanted, held = _canonical(rebuilt, observers), _canonical(existing, observers)
    missing = {name: len(wanted[name] - held[name]) for name in TABLES if wanted[name] - held[name]}
    extra = {name: len(held[name] - wanted[name]) for name in TABLES if held[name] - wanted[name]}
    report["differences"] = {"missing_from_existing": missing, "not_supported_by_evidence": extra}
    if extra:
        report.update(status=CONFLICTING, detail="the existing tables hold rows the evidence does not support")
    elif missing:
        report.update(status=REBUILDABLE, detail="the existing tables lack rows the evidence gives")
    else:
        report.update(status=CORRECT, exact=_bytes(workspace.identity) == rebuilt_bytes,
                      detail=None if _bytes(workspace.identity) == rebuilt_bytes else "equal but for order-dependent fields or row order")
    return report


def adopt(workspace: Workspace, registry: Registry, *, preservation_root: Path,
          extractor: extraction.Extractor = extraction.BASELINE, replace_conflicting: bool = False) -> dict[str, Any]:
    """Make the identity tables the rebuild. The existing directory is **moved aside**
    (``identity.replaced-<n>``), never deleted. Refused when the evidence is damaged, and — unless
    asked for explicitly — when the existing tables conflict with it. Holds the writer lock.
    """
    with exclusive(workspace.root, "adopt a rebuild of the identity tables"):
        report = verify(workspace, registry, preservation_root=preservation_root, extractor=extractor)
        if report["status"] == SOURCE_EVIDENCE_DAMAGED:
            raise RebuildRefused(f"the preserved evidence does not verify: {report['detail']}")
        if report["status"] == CONFLICTING and not replace_conflicting:
            raise RebuildRefused("the existing identity tables conflict with the evidence: a person decides "
                                 f"(replace_conflicting=True): {report['differences']}")
        if report["status"] == CORRECT:
            return {**report, "adopted": False}
        staging = workspace.root / f"identity.rebuild-{uuid.uuid4().hex[:8]}"
        staging.mkdir()
        derive(workspace, registry, preservation_root=preservation_root, target=staging, extractor=extractor)
        moved = None
        if workspace.identity.exists():
            number = 0
            while (moved := workspace.root / f"identity.replaced-{number}").exists():
                number += 1
            os.rename(workspace.identity, moved)
        os.rename(staging, workspace.identity)
        return {**report, "adopted": True, "moved_aside": moved.name if moved else None}
