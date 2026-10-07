"""After an interruption: say what is on disk, and repair what can be repaired without judgement
(decision CPD-0009 §4).

Two functions, deliberately unequal:

* :func:`diagnose` reads and **classifies**. It never raises on damaged content and never
  changes anything: every state a workspace can be left in has a name here, and a state that has
  none is reported as ``unclassified`` — which is a defect of this module, not a state to live with.
* :func:`repair` does exactly one thing: it moves the **torn tail** of an append-only file (the
  incomplete last line of the ledger or of a table, the incomplete last fetch of an open pack)
  into a sidecar beside it. Nothing is discarded, no record is rewritten, no state is invented.

Everything else is either completed by simply running the interrupted step again (each step
recognises its own finished work), or needs a person: lost evidence, a master that no longer
verifies, two rows that contradict each other. Those are reported and left exactly as found.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from . import acquisition, document_identity, extraction, identity, layer_store, ledger as ledger_module, naming, pack, preservation
from .core_pipeline import AREA_INDEXES, AREA_PACKS, Workspace
from .exclusive import exclusive
from .jsonl import JsonlError, TornTail

DIAGNOSIS_SCHEMA = naming.schema_id("workspace-diagnosis", 1)
CLEAN, RESUMABLE, NEEDS_REPAIR, DAMAGED = "CLEAN", "INCOMPLETE_RESUMABLE", "NEEDS_REPAIR", "DAMAGED"
_HELD = ("FETCHED", "RAW_VERIFIED", "PRESERVATION_PENDING", "RAW_PRESERVED")


def _tables(root: Path) -> list[Path]:
    """Every append-only line file of a workspace (pack indexes are written whole, not appended)."""
    return sorted(path for path in root.rglob("*.jsonl")
                  if not {"packs", "layers"} & set(path.relative_to(root).parts) and ".torn-" not in path.name)


def _torn(path: Path) -> bool:
    data = path.read_bytes()
    return bool(data) and not data.endswith(b"\n")


def _pack_ids(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    return sorted({path.name.split(".")[0] for path in directory.iterdir() if pack.is_pack_id(path.name.split(".")[0])})


def diagnose(workspace_root: Path, preservation_root: Path | None = None) -> dict[str, Any]:
    """What an interrupted (or healthy) workspace holds. Read-only; takes no lock."""
    workspace = Workspace(Path(workspace_root))
    root = workspace.root
    needs_repair: list[str] = []      # repair() handles these
    resumable: list[str] = []         # running the step again completes these
    damaged: list[str] = []           # a person has to look
    out: dict[str, Any] = {"schema": DIAGNOSIS_SCHEMA}

    # --- append-only files ---
    torn, unreadable = [], {}
    for path in _tables(root):
        name = path.relative_to(root).as_posix()
        if _torn(path):
            torn.append(name)
    out["torn_tails"] = torn
    needs_repair += [f"torn tail: {name}" for name in torn]

    # --- ledger ---
    book = None
    try:
        book = workspace.ledger()
        out["ledger"] = dict(sorted(Counter(book.states().values()).items()))
    except ledger_module.LedgerTornTail:
        out["ledger"] = "TORN_TAIL"
    except ledger_module.LedgerError as error:
        out["ledger"] = "UNREADABLE"
        unreadable["ledgers/preservation.jsonl"] = str(error)
        damaged.append(f"ledger is not a consistent record: {error}")

    # --- packs ---
    packs: dict[str, dict[str, Any]] = {}
    in_pack: dict[str, tuple[str, str]] = {}
    for identifier in _pack_ids(workspace.packs):
        paths = pack._paths(workspace.packs, identifier)
        info: dict[str, Any] = {}
        try:
            if paths["manifest"].exists():
                pack.verify_sealed(workspace.packs, identifier)
                info["state"], entries = "SEALED", pack.read_index(workspace.packs, identifier)
            elif paths["sealed"].exists():
                info["state"], entries = "SEALED_WITHOUT_MANIFEST", pack.scan(paths["sealed"], identifier)
                resumable.append(f"{identifier}: sealing was interrupted after the rename; seal again")
            elif paths["open"].exists() and paths["open"].stat().st_size == 0:
                info["state"], entries = "OPEN_EMPTY", []
            else:
                info["state"], entries = "OPEN", pack.scan(paths["open"], identifier)
            info["fetches"] = len(entries)
            in_pack.update({entry.fetch_id: (identifier, entry.outcome) for entry in entries})
        except pack.PackTornTail as tail:
            info.update(state="OPEN_TORN_TAIL" if not paths["sealed"].exists() else "SEALED_DAMAGED", offset=tail.offset)
            (needs_repair if info["state"] == "OPEN_TORN_TAIL" else damaged).append(f"{identifier}: incomplete fetch at offset {tail.offset}")
        except (pack.PackError, OSError, ValueError, KeyError) as error:
            info.update(state="DAMAGED", error=str(error))
            damaged.append(f"{identifier}: {error}")
        packs[identifier] = info
    out["packs"] = packs

    # --- ledger against packs and against the preservation root ---
    relation: dict[str, list[str]] = {"in_pack_ledger_planned": [], "ledger_claims_bytes_no_pack_has": [],
                                      "planned_without_bytes": [], "pending_and_master_verifies": [],
                                      "preserved_but_master_does_not_verify": []}
    if book is not None:
        torn_packs = any(info["state"] in ("OPEN_TORN_TAIL", "DAMAGED", "SEALED_DAMAGED") for info in packs.values())
        verified: dict[str, bool] = {}

        def master_ok(identifier: str) -> bool:
            if identifier not in verified:
                try:
                    verified[identifier] = preservation_root is not None and all(
                        preservation.verify_master(preservation_root, area, identifier) for area in (AREA_PACKS, AREA_INDEXES))
                except preservation.PreservationError:
                    verified[identifier] = False
            return verified[identifier]

        for fetch_id, state in sorted(book.states().items()):
            held = in_pack.get(fetch_id)
            if state == "FETCH_PLANNED":
                relation["in_pack_ledger_planned" if held else "planned_without_bytes"].append(fetch_id)
            elif state in _HELD and held is None and not torn_packs:
                relation["ledger_claims_bytes_no_pack_has"].append(fetch_id)
            elif state == "PRESERVATION_PENDING" and held and master_ok(held[0]):
                relation["pending_and_master_verifies"].append(fetch_id)
            elif state == "RAW_PRESERVED" and preservation_root is not None and held and not master_ok(held[0]):
                relation["preserved_but_master_does_not_verify"].append(fetch_id)
        if relation["in_pack_ledger_planned"]:
            resumable.append("fetches are in a pack while the ledger says FETCH_PLANNED; sealing reconciles them")
        if relation["planned_without_bytes"]:
            resumable.append("fetches were planned and nothing was recorded: interrupted before any bytes; they can be planned again")
        if relation["pending_and_master_verifies"]:
            resumable.append("promotion finished and the last transition is missing; preserve again")
        if relation["ledger_claims_bytes_no_pack_has"]:
            damaged.append("EVIDENCE LOST: the ledger records fetched bytes that no pack holds")
        if relation["preserved_but_master_does_not_verify"]:
            damaged.append("RAW_PRESERVED fetches whose preserved master does not verify")
    out["ledger_and_packs"] = {key: len(value) for key, value in relation.items()}
    out["fetch_ids"] = {key: value[:20] for key, value in relation.items() if value}

    # --- runs and requests ---
    try:
        out["unfinished_runs"] = acquisition.unfinished_runs(root)
        runs = root / "runs"
        out["runs_without_record"] = sorted(p.name for p in runs.iterdir() if p.is_dir() and not (p / "run.json").exists()) if runs.is_dir() else []
        if out["unfinished_runs"]:
            resumable.append("runs without a result: interrupted or still running")
        if out["runs_without_record"]:
            resumable.append("a run directory without a run record: the start itself was interrupted; start the run again")
        altered = []
        for directory in sorted(p for p in runs.iterdir() if (p / "run.json").exists()) if runs.is_dir() else []:
            try:
                record = json.loads((directory / "run.json").read_text(encoding="utf-8"))
                if record.get("run_id") != directory.name or not acquisition.verify_run_record(record):
                    altered.append(directory.name)
                acquisition.read_run_result(root, directory.name)
            except (OSError, ValueError, AttributeError, acquisition.AcquisitionError, acquisition.RunStateError):
                altered.append(directory.name)
        out["run_records_that_do_not_verify"] = sorted(set(altered))
        if altered:
            damaged.append("run records or results that are not the records their run id names")
    except OSError as error:
        unreadable["runs"] = str(error)
    requests = root / "requests" / "requests.jsonl"
    if requests.exists() and "requests/requests.jsonl" not in torn:
        try:
            from .http_acquisition import request_rows, unfinished_requests
            rows = request_rows(workspace)
            position = {id(row): number for number, row in enumerate(rows)}
            ended = [(row["url"], row["fetch_kind"], position[id(row)]) for row in rows if row["event"] == "FINISHED"]
            # An intent without an end stays on record for good: the request may or may not have
            # been sent. Once the same URL has been asked again and that request has ended, the
            # old intent is history, not an open task.
            pending = [row for row in unfinished_requests(workspace)
                       if row not in rows or not any(url == row["url"] and kind == row["fetch_kind"] and at > rows.index(row)
                                                     for url, kind, at in ended)]
            out["requests_planned_without_end"] = len(pending)
            out["interrupted_requests_repeated_later"] = len(unfinished_requests(workspace)) - len(pending)
            if pending:
                resumable.append("requests were planned and have no end on record: the request may or may not have been sent")
        except JsonlError as error:
            unreadable["requests/requests.jsonl"] = str(error)

    # --- identity tables and the layers they point at ---
    identity_torn = any(name.startswith("identity/") for name in torn)
    if workspace.identity.is_dir() and not identity_torn:
        try:
            tables = document_identity.IdentityTables(workspace.identity)
            missing = []
            store = workspace.layer_store() if workspace.layers.is_dir() else None
            wrong_ids = []   # an id is derived from what it identifies: a row whose id no longer fits was changed
            for document, row in sorted(tables.documents.items()):
                if identity.document_id(row["outlet_id"], row["url_key"]) != document:
                    wrong_ids.append(document)
            for version, row in sorted(tables.versions.items()):
                try:
                    if identity.document_version_id(row["document_id"], row["extracted_text_sha256"]) != version:
                        wrong_ids.append(version)
                    if store is None or store.get(extraction.STAGE, row["extraction_fingerprint"]) is None:
                        missing.append(version)
                    else:
                        stored = json.loads(store.read(extraction.STAGE, row["extraction_fingerprint"]).decode("utf-8"))
                        if (stored.get("extracted_text_sha256"), stored.get("body_text_sha256")) != (row["extracted_text_sha256"], row["body_text_sha256"]):
                            missing.append(version)   # the layer verifies, but it is not the text this version names
                except (layer_store.LayerStoreError, ValueError, TypeError):
                    missing.append(version)
            not_preserved = sorted(fetch for (_, fetch) in tables.version_observations
                                   if book is not None and book.state(fetch) != "RAW_PRESERVED")
            unknown = sorted({row["document_id"] for row in tables.observations.values() if row["document_id"] not in tables.documents}
                             | {row["document_id"] for row in tables.versions.values() if row["document_id"] not in tables.documents})
            out["identity"] = {"documents": len(tables.documents), "versions": len(tables.versions),
                               "versions_without_verifying_extraction": missing, "versions_of_unpreserved_fetches": not_preserved,
                               "ids_that_do_not_fit_their_rows": wrong_ids, "rows_naming_unknown_documents": unknown}
            if missing:
                damaged.append("document versions whose extraction layer is missing or does not verify")
            if not_preserved:
                damaged.append("document versions rest on fetches that are not RAW_PRESERVED")
            if wrong_ids or unknown:
                damaged.append("identity rows whose ids do not fit their content, or that name documents the tables do not hold")
        except (JsonlError, ValueError, TypeError, KeyError) as error:
            unreadable["identity"] = str(error)
            damaged.append(f"identity tables contradict themselves: {error}")

    # --- every other table must at least be readable as lines ---
    for path in _tables(root):
        name = path.relative_to(root).as_posix()
        if name in torn or name in unreadable:
            continue
        try:
            for number, line in enumerate(path.read_bytes().split(b"\n")[:-1], 1):
                if not line.startswith(b"{") or not line.endswith(b"}"):
                    raise JsonlError(f"line {number} is not a record")
        except JsonlError as error:
            unreadable[name] = str(error)
            damaged.append(f"{name}: {error}")
    out["unreadable"] = unreadable

    # --- layers ---
    conflicts, unverifiable, staging = [], [], 0
    if workspace.layers.is_dir():
        store = workspace.layer_store()
        staging = len(list((workspace.layers / ".staging").glob("*"))) if (workspace.layers / ".staging").is_dir() else 0
        for slot in sorted(path for path in workspace.layers.glob("*/*/*") if path.is_dir() and path.parent.parent.name != ".staging"):
            if sum(1 for answer in slot.iterdir() if (answer / layer_store.MARKER_NAME).is_file()) > 1:
                conflicts.append(slot.name[:16])
                continue
            try:   # every stored answer is re-read and hashed, whether or not anything points at it
                if store.get(slot.parent.parent.name, slot.name) is not None:
                    store.read(slot.parent.parent.name, slot.name)
                elif any(slot.iterdir()):
                    unverifiable.append(slot.name[:16])   # a directory in the slot that is not an answer
            except (layer_store.LayerStoreError, ValueError):
                unverifiable.append(slot.name[:16])
    if conflicts:
        damaged.append("layer slots holding more than one answer")
    if unverifiable:
        damaged.append("stored layer answers that do not verify")
    out["layers"] = {"slots_with_several_answers": conflicts, "answers_that_do_not_verify": unverifiable, "abandoned_writes": staging}

    # --- leftovers that are never read as data ---
    bases = [root] + ([Path(preservation_root)] if preservation_root is not None else [])
    out["leftovers"] = {"staging_files": sum(len(list(base.rglob("*.part-*"))) for base in bases),
                        "torn_sidecars": sorted(path.name for base in bases for path in base.rglob("*.torn-*"))}

    out["needs_repair"], out["resumable"], out["damaged"] = needs_repair, resumable, damaged
    out["classification"] = DAMAGED if damaged else NEEDS_REPAIR if needs_repair else RESUMABLE if resumable else CLEAN
    return out


def repair(workspace_root: Path) -> dict[str, Any]:
    """Move torn tails aside. Holds the writer lock; idempotent; changes nothing else."""
    workspace = Workspace(Path(workspace_root))
    moved: list[str] = []
    with exclusive(workspace.root, "repair torn tails"):
        for path in _tables(workspace.root):
            sidecar = ledger_module.quarantine_torn_tail(path)
            if sidecar is not None:
                moved.append(sidecar.relative_to(workspace.root).as_posix())
        for identifier in _pack_ids(workspace.packs):
            paths = pack._paths(workspace.packs, identifier)
            if paths["open"].exists() and paths["open"].stat().st_size and not paths["sealed"].exists():
                try:
                    sidecar = pack.quarantine_torn_tail(workspace.packs, identifier)
                except pack.PackError:
                    continue  # not a torn tail: damage of another kind, left for diagnose() to name
                if sidecar is not None:
                    moved.append(sidecar.relative_to(workspace.root).as_posix())
    return {"moved_aside": moved, "nothing_else_changed": True}


__all__ = ["diagnose", "repair", "CLEAN", "RESUMABLE", "NEEDS_REPAIR", "DAMAGED", "TornTail"]
