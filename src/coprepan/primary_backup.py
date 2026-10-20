"""The BACKUP of the PRESERVATION primary (``crosscorpus-storage/v1`` §9, B1-B6; NEW_FS Phase D, 2026-10-18).

A backup is a copy that exists, was produced FROM the primary and was verified AGAINST it, on another volume (B1, B2). This module
makes one with the qualified mechanics of the pre-copy (:mod:`coprepan.preservation_migration`):

* **from the primary.** Every run takes a fresh baseline of the configured primary (path, size, SHA-256 of every object, the
  primary's identity marker); the copy is checked against those digests, never against an older list.
* **write-once.** Each object is read once, its digest must be the baseline's (else ``SOURCE_CHANGED``), written to a temporary file,
  re-read unbuffered, and published with ``os.rename``, which never replaces a name; an existing object with the same digest is
  ``ALREADY_PRESENT``, with another digest ``CONFLICT`` (nothing in this corpus is rewritten). A rerun skips what its journal confirms.
* **verified against the primary.** Every baseline object re-read unbuffered from the backup root and compared with the baseline
  digest; objects on the backup root that the primary does not hold are reported (``only_in_backup``), never removed.
* **restorable.** A deterministic sample is restored from the backup root into an empty scratch directory and re-hashed.
* **its own root.** The root carries ``BACKUP_ROOT.json`` (role BACKUP, corpus coprepan). A root with that marker is refused as a
  PRESERVATION root by :mod:`coprepan.storage_roots` (T2); a backup root on the primary's volume is refused here.

The receipt (``_backup/backup_receipt.json``) is what the contract status reports from. Nothing is deleted except this tool's own
unpublished temporary files and the restore test's own restored files.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from . import naming, preservation_migration as M, preservation_target, storage_roots

SCHEMA = naming.schema_id("primary-backup", 1)
MARKER = "BACKUP_ROOT.json"
STATE = "_backup"
RECEIPT = "backup_receipt.json"
JOURNAL = "journal.jsonl"
#: the holdings whose primary this tool backs up (contract §2.2): PRODUCTION, and LEGACY since CPD-0032. A backup root names its
#: holding in its marker and is never used for another holding's primary (role isolation).
HOLDINGS = ("PRODUCTION", "LEGACY")


class BackupError(RuntimeError):
    """The backup cannot be made or trusted without risking a role, an identity or an object."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _excluded(path: str) -> bool:
    return path == MARKER or path.split("/", 1)[0] == STATE


def init_root(root: Path, *, primary: Path, operator: str, holding: str = "PRODUCTION") -> dict[str, Any]:
    """Make ``root`` a BACKUP root of ``holding``'s primary (once): it must be new or empty, and on another volume than the
    primary (B2)."""
    if holding not in HOLDINGS:
        raise BackupError(f"not a holding this tool backs up: {holding!r}")
    root = Path(root)
    marker = root / MARKER
    if marker.is_file():
        return json.loads(marker.read_text(encoding="utf-8"))
    if root.exists() and any(root.iterdir()):
        raise BackupError(f"{root} exists, is not empty and carries no {MARKER}: a directory is never adopted as a backup (B6)")
    root.mkdir(parents=True, exist_ok=True)
    if storage_roots.volume_of(root) == storage_roots.volume_of(Path(primary)):
        raise BackupError(f"{root} is on the primary's volume: two directories of one volume are one copy (B2)")
    doc = {"schema": SCHEMA + "/root", "role": "BACKUP", "corpus": "coprepan", "holding": holding,
           "contract": "crosscorpus-storage/v1 §9", "created_at": _now(), "operator": operator,
           "statement": f"a secondary copy produced from the PRESERVATION primary of the {holding} holding and verified against it; "
                        "never a primary, never a pipeline dependency; nothing in it is deleted by a tool",
           "independence": "different volume; further independence not determined (contract B3)"}
    with open(marker, "x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    return doc


def require_root(root: Path, *, primary: Path, holding: str = "PRODUCTION") -> dict[str, Any]:
    marker = Path(root) / MARKER
    if not marker.is_file():
        raise BackupError(f"{root} carries no {MARKER}: it was not made a backup root (init-root); refusing to write into it")
    doc = json.loads(marker.read_text(encoding="utf-8"))
    if doc.get("role") != "BACKUP" or doc.get("corpus") != "coprepan":
        raise BackupError(f"{marker} is not a CO.PRE.PAN BACKUP root marker")
    if doc.get("holding", "PRODUCTION") != holding:
        raise BackupError(f"{marker} is the backup of the {doc.get('holding')} holding, not of {holding} (role isolation)")
    if storage_roots.volume_of(Path(root)) == storage_roots.volume_of(Path(primary)):
        raise BackupError(f"{root} is on the primary's volume (B2)")
    if preservation_target.read_target(Path(root)) is not None:
        raise BackupError(f"{root} carries a PRESERVATION identity marker: a primary is never a backup (B6)")
    return doc


def load_journal(root: Path) -> dict[str, dict[str, Any]]:
    path = Path(root) / STATE / JOURNAL
    out: dict[str, dict[str, Any]] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.lstrip("\x00")
            if line.strip():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("status") in M.DONE:
                    out[row["path"]] = row
    return out


def copy(primary: Path, root: Path, base: Mapping[str, Any], *, workers: int = 3,
         progress: Callable[[str], None] | None = None, holding: str = "PRODUCTION") -> dict[str, Any]:
    """Copy the baseline objects of ``primary`` to the backup ``root`` (write-once, journalled, resumable)."""
    require_root(root, primary=primary, holding=holding)
    from concurrent.futures import ThreadPoolExecutor
    import threading

    run_id = "bk" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + os.urandom(3).hex()
    known = load_journal(root)
    state = Path(root) / STATE
    state.mkdir(parents=True, exist_ok=True)
    journal = M._Journal(state / JOURNAL)
    rate, lock = M._Rate(None), threading.Lock()
    counts: dict[str, int] = {}
    problems: list[dict[str, Any]] = []
    done = [0]

    def work(entry):
        result = M.migrate_one(Path(primary), Path(root), entry, known.get(entry["path"]), run_id=run_id, rate=rate)
        with lock:
            counts[result["status"]] = counts.get(result["status"], 0) + 1
            done[0] += 1
            if result["status"] != M.SKIPPED:
                journal.write(json.dumps({**result, "at": _now()}, sort_keys=True) + "\n")
            if result["status"] in M.PROBLEMS or result.get("mtime_kept") is False:
                problems.append(result)
            if progress and done[0] % 1000 == 0:
                progress(f"{done[0]}/{len(base['objects'])} objects, {counts}")

    try:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            list(pool.map(work, base["objects"]))
    finally:
        journal.close()
    return {"run_id": run_id, "objects": len(base["objects"]), "counts": counts, "problems": problems[:50],
            "problem_count": len(problems), "ok": not problems}


def verify(root: Path, base: Mapping[str, Any], *, workers: int = 4) -> dict[str, Any]:
    """Every baseline object re-read unbuffered from the backup root against the baseline digest; what the root holds beyond it."""
    from concurrent.futures import ThreadPoolExecutor

    root = Path(root)
    wanted = {e["path"]: e for e in base["objects"]}
    present, temporaries = set(), []
    for directory, _subdirs, files in os.walk(M._long(root)):
        for name in files:
            relative = Path(os.path.relpath(os.path.join(directory, name), M._long(root))).as_posix()
            if _excluded(relative):
                continue
            (temporaries.append(relative) if M.TEMP_TAG in name else present.add(relative))

    def one(item):
        path, entry = item
        if path not in present:
            return {"path": path, "problem": "MISSING"}
        try:
            digest, size = M.sha256_uncached(root.joinpath(*path.split("/")))
        except OSError as error:
            return {"path": path, "problem": f"UNREADABLE: {error}"}
        return None if (digest, size) == (entry["sha256"], entry["size"]) else {"path": path, "problem": "DIFFERENT"}

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        problems = [p for p in pool.map(one, sorted(wanted.items())) if p]
    extra = sorted(p for p in present if p not in wanted)
    return {"verified_at": _now(), "reread": "uncached", "objects": len(wanted), "bytes": sum(e["size"] for e in wanted.values()),
            "problems": problems[:50], "problem_count": len(problems), "only_in_backup": extra[:50], "only_in_backup_count": len(extra),
            "temporary_files": temporaries, "ok": not problems and not temporaries}


def _discard_restored(scratch: Path, path: Path) -> None:
    """The ONLY removal in this module: a file the restore test itself restored into its own scratch directory. Refuses any path
    outside that directory."""
    scratch, path = Path(scratch).resolve(), Path(path).resolve()
    if scratch not in path.parents:
        raise ValueError(f"{path} is not inside the restore scratch directory {scratch}")
    path.unlink(missing_ok=True)


def restore_test(root: Path, base: Mapping[str, Any], scratch: Path, *, samples: int = 25) -> dict[str, Any]:
    """Restore a deterministic sample from the backup root into an empty ``scratch`` directory and re-hash it; the restored files
    (this test's own) are removed afterwards."""
    scratch = Path(scratch)
    if scratch.exists() and any(scratch.iterdir()):
        raise BackupError(f"{scratch} is not empty: the restore test writes into an empty directory of its own")
    scratch.mkdir(parents=True, exist_ok=True)
    order = sorted(base["objects"], key=lambda e: hashlib.sha256(("restore-test/v1:" + e["path"]).encode("utf-8")).hexdigest())
    cases = []
    for entry in order[:samples]:
        dst = scratch / Path(*entry["path"].split("/"))
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(M._long(Path(root).joinpath(*entry["path"].split("/"))), dst)
        got = hashlib.sha256(dst.read_bytes()).hexdigest()
        cases.append({"path": entry["path"], "bytes": dst.stat().st_size, "ok": got == entry["sha256"]})
    for entry in order[:samples]:
        _discard_restored(scratch, scratch / Path(*entry["path"].split("/")))
    return {"tested_at": _now(), "read_from": "BACKUP root", "samples": len(cases), "ok_count": sum(c["ok"] for c in cases),
            "bytes": sum(c["bytes"] for c in cases), "all_ok": bool(cases) and all(c["ok"] for c in cases), "cases": cases}


def write_receipt(root: Path, doc: Mapping[str, Any]) -> Path:
    state = Path(root) / STATE
    state.mkdir(parents=True, exist_ok=True)
    path = state / RECEIPT
    if path.is_file():
        os.rename(path, state / f"backup_receipt.superseded_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json")
    with open(path, "x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({"schema": SCHEMA + "/receipt", **doc}, indent=1, sort_keys=True) + "\n")
    return path


def receipt_status(root: Path | None, primary: Path | None) -> dict[str, Any]:
    """The inputs of ``storage_contract.backup_status`` from the receipt: a copy exists, it was produced from THIS primary (the
    receipt names the primary's identity, which the primary still carries) and it was verified against it."""
    if root is None:
        return {"copy_exists": False, "produced_from_primary": False, "verified_against_primary": False, "receipt": None}
    path = Path(root) / STATE / RECEIPT
    if not path.is_file():
        return {"copy_exists": (Path(root) / MARKER).is_file(), "produced_from_primary": False, "verified_against_primary": False,
                "receipt": None}
    doc = json.loads(path.read_text(encoding="utf-8"))
    marker = preservation_target.read_target(Path(primary)) if primary is not None else None
    same = bool(marker) and marker.get("target_id") == doc.get("primary_target_id")
    return {"copy_exists": True, "produced_from_primary": same and doc.get("produced_from_primary") is True,
            "verified_against_primary": same and doc.get("verified_against_primary") is True,
            "receipt": {k: doc.get(k) for k in ("written_at", "primary_target_id", "objects", "bytes", "tree_sha256")}}


__all__ = ["BackupError", "HOLDINGS", "MARKER", "RECEIPT", "SCHEMA", "STATE", "copy", "init_root", "load_journal", "receipt_status", "require_root",
           "restore_test", "verify", "write_receipt"]
