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

**Two modes (CPD-0033).** The description above is the ``FULL`` run: every object of the primary re-hashed, every object of the
backup re-read. It is kept for an operator's explicit order (after an incident, a migration, a periodic full check). The regular,
scheduled run is ``INCREMENTAL`` (:func:`run_incremental`), because the full run re-reads the whole primary over the shared
institutional link every day (78 min for 395 MB on 2026-11-13, growing with the corpus) while CO.RA.PAN has priority on it:

* **inventory without reading.** One enumeration of the primary and one of the backup root give path, size and ``mtime_ns`` of
  every object; no file is opened for that.
* **when stored hash evidence is reused.** An object's digest is taken from the backup journal **only** when all of these hold:
  the journal row was written by a copy that re-read the landed bytes unbuffered and found them equal to the digest it had read
  from the primary (``COPIED`` / ``ALREADY_PRESENT``), or by a re-hash after a timestamp change (``RESTAMPED``); the primary
  carries the identity the previous verified receipt names (same target, T1/T2); the object's size **and** ``mtime_ns`` on the
  primary are those of the row (every object of this corpus is write-once, P8, and a rewrite changes the timestamp); and the
  backup root holds a file of that size at that path. Anything else is read: a new object is hashed on the primary and copied
  (two reads of the source, as in the full run); a changed timestamp is re-hashed and either confirmed (``RESTAMPED``) or reported
  ``SOURCE_CHANGED_SINCE_BACKUP`` (never overwritten); a missing backup copy is copied again; an object the journal knows and the
  primary no longer holds is ``MISSING_ON_PRIMARY`` -- a finding for a person, and nothing is removed.
* **full revalidation stays required** for: a primary with another identity (a migration, §11), a journal row that is torn or
  absent, any problem of a previous run, and the operator's ``--full``. And it is **spread over time**: every run re-hashes a
  budgeted slice of objects on **both** roots, past the client cache, oldest verification first (``_backup/fixity.jsonl``); the
  status reports the oldest verification and flags a cycle longer than the policy's maximum. A stored digest never stands in for
  that re-read.
* **bounded.** Sequential, throttled to the policy's bytes per second, a time budget, and a stop predicate (the operator's pause
  file, a quiet window of CO.RA.PAN, the share gate). A run that stops is resumable: what it copied is journalled, nothing is
  claimed, no receipt is written.
* **the receipt** of an incremental run says so (``mode``), names the evidence basis, the slice re-verified today, the oldest
  verification and the last full run; its ``tree_sha256`` is the digest of the full inventory, so an unchanged primary gives the
  previous receipt's digest -- checked.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from . import naming, preservation_migration as M, preservation_target, release_contract, storage_roots

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


def restore_test(root: Path, base: Mapping[str, Any], scratch: Path, *, samples: int = 25, preordered: bool = False) -> dict[str, Any]:
    """Restore a deterministic sample from the backup root into an empty ``scratch`` directory and re-hash it; the restored files
    (this test's own) are removed afterwards. ``preordered``: take the first ``samples`` objects in the order given (the
    incremental run passes an order that changes with every run)."""
    scratch = Path(scratch)
    if scratch.exists() and any(scratch.iterdir()):
        raise BackupError(f"{scratch} is not empty: the restore test writes into an empty directory of its own")
    scratch.mkdir(parents=True, exist_ok=True)
    order = list(base["objects"]) if preordered else sorted(
        base["objects"], key=lambda e: hashlib.sha256(("restore-test/v1:" + e["path"]).encode("utf-8")).hexdigest())
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
            "receipt": {k: doc.get(k) for k in ("written_at", "primary_target_id", "objects", "bytes", "tree_sha256", "mode",
                                                 "last_full_verification_at")}}


_LEVELS = ("OK", "WARNING", "FAILURE")


def _worse(level: str, other: str) -> str:
    return max(level, other, key=_LEVELS.index)


def _parse_instant(text: Any) -> datetime | None:
    try:
        value = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def backup_health(root: Path | None, *, now: datetime, calendar: Any, failure_hours: int) -> dict[str, Any]:
    """How current the backup is, from local files of the BACKUP root only (CPD-0033, CPD-0035). Four facts, kept apart:
    the **last verified backup** (the receipt) and its real age; the **last attempt** (``_backup/last_run.json``: also a
    planned pause, a deferral or a stop) and the recent attempts; the **fixity** rotation's oldest verification; the
    **restore** evidence of the receipt.

    The level counts **missed weekday slots**: scheduled starts of the maintenance calendar (Monday to Friday) that passed,
    plus the run's grace, without a newer verified receipt. A weekend has no slot, so Friday's backup is not late on Monday
    morning; two weekdays without a backup are, whatever the reason -- a deferral for CO.RA.PAN is visible as such, but the
    risk of an old backup is real either way. ``OK`` · ``WARNING`` (``warning_missed_slots`` missed, or the fixity cycle overdue) ·
    ``FAILURE`` (``failure_missed_slots`` missed, a receipt older than ``failure_hours`` whatever the calendar says, no receipt,
    a last run that failed, or one that needs the operator's FULL order). Never reports a backup the receipt does not establish."""
    receipt = read_receipt(root) if root is not None else None
    last = read_last_run(root)
    out: dict[str, Any] = {"last_verified_at": receipt.get("written_at") if receipt else None,
                           "last_verified_mode": receipt.get("mode") if receipt else None, "last_attempt": last,
                           "next_scheduled_start": None, "operator_action": []}
    nxt = calendar.next_slot(now)
    out["next_scheduled_start"] = nxt.strftime("%Y-%m-%dT%H:%M:%SZ") if nxt else None
    reasons: list[str] = []
    level = "OK"
    written = _parse_instant(receipt.get("written_at")) if receipt else None
    if receipt is None:
        level, reasons = "FAILURE", ["no backup receipt"]
        out["operator_action"].append("no verified backup exists: the first one is a FULL run on the operator's order (run --full)")
    else:
        age = (now - written).total_seconds() / 3600 if written else float("inf")
        out["last_verified_age_hours"] = round(age, 1)
        missed = calendar.missed(written, now) if written else []
        out["missed_weekday_slots"] = len(missed)
        out["missed_slot_starts"] = [m.strftime("%Y-%m-%dT%H:%M:%SZ") for m in missed[-5:]]
        if len(missed) >= calendar.failure_missed_slots:
            level = "FAILURE"
            reasons.append(f"{len(missed)} weekday slots passed without a verified backup (failure from {calendar.failure_missed_slots})")
        elif len(missed) >= calendar.warning_missed_slots:
            level = "WARNING"
            reasons.append(f"{len(missed)} weekday slots passed without a verified backup (warning from {calendar.warning_missed_slots})")
        if age > failure_hours:
            level = "FAILURE"
            reasons.append(f"the last verified backup is {age:.0f} h old (failure above {failure_hours} h, whatever the calendar)")
        fixity = (last or {}).get("fixity") or ((receipt.get("run") or {}).get("fixity") or {})
        out["fixity"] = {k: fixity.get(k) for k in ("oldest_verification_at", "oldest_verification_age_days", "cycle_max_days", "cycle_overdue", "checked")}
        if fixity.get("cycle_overdue"):
            level = _worse(level, "WARNING")
            reasons.append(f"the oldest fixity verification is {fixity.get('oldest_verification_age_days')} days old")
        restore = receipt.get("restore_test") or (receipt.get("run") or {}).get("restore_test") or {}
        out["restore_evidence"] = {k: restore.get(k) for k in ("tested_at", "samples", "ok_count", "all_ok")}
    recent = [r for r in (last or {}).get("recent") or [] if isinstance(r, Mapping)]
    since = [r for r in recent if written is None or (_parse_instant(r.get("at")) or now) > written]
    out["attempts_since_verified"] = dict(Counter(str(r.get("outcome")) for r in since))
    outcome = (last or {}).get("outcome")
    if outcome in ("FAILED", "NOT_VERIFIED"):
        level = "FAILURE"
        reasons.append(f"the last run found {last.get('problem_count')} problem(s): {last.get('first_problems')}")
        out["operator_action"].append("the last backup run found problems: read _backup/last_run.json and the run evidence")
    elif outcome == "NEEDS_FULL_AUTHORIZATION":
        level = "FAILURE"
        reasons.append(f"the incremental basis is not trustworthy: {last.get('reason')}")
        out["operator_action"].append("an incremental run has no trustworthy basis: a FULL run (run --full) is the operator's order")
    elif level != "OK" and outcome:
        reasons.append(f"the last attempt was {outcome}: {last.get('reason') or last.get('stop_reason')}")
    if level == "FAILURE" and not out["operator_action"]:
        out["operator_action"].append("the backup is overdue: read the attempts since the last verified backup")
    out.update(level=level, reasons=reasons)
    return out


def read_receipt(root: Path) -> dict[str, Any] | None:
    path = Path(root) / STATE / RECEIPT
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except (OSError, ValueError):
        return None


# --- the incremental run (CPD-0033) ------------------------------------------------------------------------------

MODE_FULL, MODE_INCREMENTAL = "FULL", "INCREMENTAL"
RESTAMPED = "RESTAMPED"
EVIDENCE = (M.COPIED, M.PRESENT, RESTAMPED)
FIXITY_LOG = "fixity.jsonl"
LAST_RUN = "last_run.json"
RECENT_ATTEMPTS = 20


class NeedsFullAuthorization(BackupError):
    """An incremental run has no trustworthy basis (CPD-0035): no verified receipt of this primary, a journal that covers
    fewer objects than the receipt verified, or more changed timestamps than one run's fixity slice. Reading the whole
    primary to rebuild the basis is a FULL run, and a FULL run on the shared link is the operator's order -- never a
    surprise of a scheduled run. Raised before any object of the primary is read."""
_PROBE_PREFIX = ".coprepan_write_probe-"          # storage_roots' transient writability probe in the root: not an object


def _primary_excluded(path: str) -> bool:
    return M._excluded(path) or path.rsplit("/", 1)[-1].startswith(_PROBE_PREFIX)


def load_evidence(root: Path) -> dict[str, dict[str, Any]]:
    """The newest evidence row per path of the backup journal (``COPIED``, ``ALREADY_PRESENT``, ``RESTAMPED``). A torn row is no
    evidence: its object is treated as unknown and read again."""
    path = Path(root) / STATE / JOURNAL
    out: dict[str, dict[str, Any]] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.lstrip("\x00")
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("status") in EVIDENCE and isinstance(row.get("sha256"), str) and isinstance(row.get("size"), int):
                out[row["path"]] = row
    return out


def list_tree(root: Path, excluded: Callable[[str], bool]) -> tuple[dict[str, tuple[int, int]], list[str]]:
    """``({path: (size, mtime_ns)}, temporary files)`` from one enumeration of ``root``; no file is opened."""
    base = M._long(Path(root))
    objects: dict[str, tuple[int, int]] = {}
    temporaries: list[str] = []
    stack = [base]
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                relative = Path(os.path.relpath(entry.path, base)).as_posix()
                if entry.is_dir(follow_symlinks=False):
                    if not excluded(relative + "/"):
                        stack.append(entry.path)
                    continue
                if excluded(relative):
                    continue
                if M.TEMP_TAG in entry.name:
                    temporaries.append(relative)
                    continue
                stat = entry.stat(follow_symlinks=False)
                objects[relative] = (stat.st_size, stat.st_mtime_ns)
    return objects, sorted(temporaries)


def _hash_source(path: Path, rate: "M._Rate") -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with open(M._long(path), "rb") as handle:
        for block in iter(lambda: handle.read(M.CHUNK), b""):
            rate.take(len(block))
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def load_fixity(root: Path) -> dict[str, str]:
    """``{path: newest time both copies were re-hashed past the cache and found equal}`` from ``_backup/fixity.jsonl``."""
    path = Path(root) / STATE / FIXITY_LOG
    out: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line.lstrip("\x00"))
            except json.JSONDecodeError:
                continue
            if row.get("ok") is True and isinstance(row.get("at"), str):
                out[row["path"]] = max(out.get(row["path"], ""), row["at"])
    return out


def _sweep_own_temporaries(root: Path, temporaries: list[str]) -> list[str]:
    """Remove this tool's own unpublished temporary files on the BACKUP root (a killed copy leaves them); any other name stays."""
    removed = []
    for relative in temporaries:
        name = relative.rsplit("/", 1)[-1]
        if M._OWN_TEMP.fullmatch(name):
            M._discard_own_temporary(Path(M._long(Path(root).joinpath(*relative.split("/")))))
            removed.append(relative)
    return removed


def write_last_run(root: Path, doc: Mapping[str, Any]) -> None:
    """What the last scheduled attempt did -- also a deferral or a stop -- so a missed or deferred backup is visible."""
    from .canonical import record_json, write_bytes_atomic

    if root is None or not (Path(root) / MARKER).is_file():
        return                                    # only into a root that was made a BACKUP root: never creates state elsewhere
    previous = read_last_run(root) or {}
    recent = [r for r in previous.get("recent") or [] if isinstance(r, Mapping)][-(RECENT_ATTEMPTS - 1):]
    recent.append({"at": doc.get("at"), "outcome": doc.get("outcome")})
    try:
        write_bytes_atomic(Path(root) / STATE / LAST_RUN, record_json({"schema": SCHEMA + "/last-run", **dict(doc), "recent": recent}))
    except OSError:
        pass                                      # a record of an attempt; its absence shows as an old last run in the status


def read_last_run(root: Path | None) -> dict[str, Any] | None:
    if root is None:
        return None
    try:
        return json.loads((Path(root) / STATE / LAST_RUN).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def run_incremental(primary: Path, root: Path, *, scratch: Path, limits: Mapping[str, int], stop: Callable[[], str | None] | None = None,
                    holding: str = "PRODUCTION", clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                    monotonic: Callable[[], float] = time.monotonic, progress: Callable[[str], None] | None = None) -> dict[str, Any]:
    """One incremental backup run (see the module's documentation). Returns the run document; ``doc["ok"]`` says whether a
    receipt may be written from it. Writes only to the BACKUP root (objects, journal, fixity log) and ``scratch``."""
    primary, root = Path(primary), Path(root)
    require_root(root, primary=primary, holding=holding)
    marker = preservation_target.read_target(primary)
    target_id = marker.get("target_id") if marker else None
    previous = read_receipt(root)
    if not target_id:
        raise BackupError("the primary carries no identity marker: no evidence of an earlier run can be its evidence")
    if previous is None or previous.get("primary_target_id") != target_id or not previous.get("verified_against_primary"):
        raise NeedsFullAuthorization("no verified receipt produced from this primary: an incremental run builds on one; run --full first")
    started, begun = clock(), monotonic()
    run_id = "bi" + started.strftime("%Y%m%dT%H%M%SZ") + "-" + os.urandom(3).hex()
    rate = M._Rate(float(limits["max_bytes_per_second"]) or None)
    deadline = begun + 60 * limits["max_minutes"]
    stop_reason: list[str] = []

    def halted() -> bool:
        if not stop_reason:
            reason = (stop() if stop is not None else None) or ("TIME_BUDGET: the run's time budget is spent" if monotonic() >= deadline else None)
            if reason:
                stop_reason.append(reason)
        return bool(stop_reason)

    evidence = load_evidence(root)
    if len(evidence) < int(previous.get("objects") or 0):
        raise NeedsFullAuthorization(f"the backup journal holds evidence for {len(evidence)} objects, the verified receipt for "
                                     f"{previous.get('objects')}: the basis is damaged; run --full on the operator's order")
    listed, primary_temporaries = list_tree(primary, _primary_excluded)
    on_backup, backup_temporaries = list_tree(root, _excluded)
    swept = _sweep_own_temporaries(root, backup_temporaries)
    counts: Counter[str] = Counter()
    problems: list[dict[str, Any]] = []
    inventory: dict[str, tuple[str, int]] = {}
    new, changed, recopy = [], [], []
    for path, (size, mtime_ns) in sorted(listed.items()):
        if not release_contract.is_contract_path(path):
            problems.append({"path": path, "problem": "PATH_INVALID"})
            continue
        row = evidence.get(path)
        if row is None:
            new.append(path)
        elif row["size"] != size or row.get("mtime_ns") != mtime_ns:
            changed.append(path)
        elif path not in on_backup:
            recopy.append(path)
        elif on_backup[path][0] != size:
            problems.append({"path": path, "problem": "DIFFERENT_ON_BACKUP", "detail": f"{on_backup[path][0]} bytes on the backup, {size} on the primary"})
        else:
            inventory[path] = (row["sha256"], size)
            counts["REUSED_EVIDENCE"] += 1
    if len(changed) > limits["fixity_objects_per_run"]:
        raise NeedsFullAuthorization(f"{len(changed)} objects of a write-once primary show another size or timestamp than their "
                                     "evidence: a systemic change (a copy, a migration, a restore by others), not a day's work; "
                                     "re-hashing them is a FULL run on the operator's order")
    for path in sorted(set(evidence) - set(listed)):
        problems.append({"path": path, "problem": "MISSING_ON_PRIMARY", "detail": "the journal holds it, the primary's listing does not; nothing is removed"})
    journal = M._Journal(root / STATE / JOURNAL)
    copied_bytes = 0
    try:
        for path in changed:
            if halted():
                break
            row = evidence[path]
            try:
                digest, size = _hash_source(primary.joinpath(*path.split("/")), rate)
            except OSError as error:
                stop_reason.append(f"SHARE_FAILED: {type(error).__name__} while reading the primary")
                break
            if (digest, size) == (row["sha256"], row["size"]):
                mtime_ns = listed[path][1]
                journal.write(json.dumps({"path": path, "status": RESTAMPED, "sha256": digest, "size": size, "mtime_ns": mtime_ns,
                                          "previous_mtime_ns": row.get("mtime_ns"), "primary_target_id": target_id, "run_id": run_id,
                                          "at": _now()}, sort_keys=True) + "\n")
                counts[RESTAMPED] += 1
                if path in on_backup and on_backup[path][0] == size:
                    inventory[path] = (digest, size)
                else:
                    recopy.append(path)
                    evidence[path] = {**row, "mtime_ns": mtime_ns}
            else:
                problems.append({"path": path, "problem": "SOURCE_CHANGED_SINCE_BACKUP",
                                 "detail": "a write-once object has other bytes than when it was copied; the backup copy is kept"})
        for path in new + recopy:
            if halted():
                break
            size, mtime_ns = listed[path]
            if path in evidence:
                digest = evidence[path]["sha256"]
            else:
                try:
                    digest, hashed = _hash_source(primary.joinpath(*path.split("/")), rate)
                except OSError as error:
                    stop_reason.append(f"SHARE_FAILED: {type(error).__name__} while reading the primary")
                    break
                if hashed != size:
                    problems.append({"path": path, "problem": "SOURCE_CHANGED", "detail": "the size changed while the run read it"})
                    continue
            entry = {"path": path, "size": size, "sha256": digest, "mtime_ns": mtime_ns}
            result = M.migrate_one(primary, root, entry, None, run_id=run_id, rate=rate)
            if M._transient(result):
                stop_reason.append(f"SHARE_FAILED: {result.get('error')}")
                break
            journal.write(json.dumps({**result, "primary_target_id": target_id, "at": _now()}, sort_keys=True) + "\n")
            counts[result["status"]] += 1
            if result["status"] in M.DONE:
                inventory[path] = (digest, size)
                copied_bytes += size if result["status"] == M.COPIED else 0
            else:
                problems.append(result)
            if progress and sum(counts.values()) % 500 == 0:
                progress(f"{dict(counts)}")
    finally:
        journal.close()
    fixity = _fixity_rotation(primary, root, inventory, previous, limits, halted, rate, run_id)
    problems += fixity.pop("problems")
    restore = _restore_rotation(root, inventory, scratch, samples=limits["restore_samples"], salt=run_id)
    complete = not stop_reason and len(inventory) == len(listed) and not problems
    tree = release_contract.record_set_digest([{"path": p, "sha256": s, "size": z} for p, (s, z) in sorted(inventory.items())]) if complete else None
    unchanged = not new and not changed and not recopy
    if complete and unchanged and previous.get("tree_sha256") and tree != previous["tree_sha256"]:
        problems.append({"problem": "TREE_DIGEST_DIVERGES", "detail": f"nothing new and the inventory digest {tree} is not the previous receipt's"})
        complete = False
    ok = complete and restore["all_ok"] and not problems
    return {"run_id": run_id, "mode": MODE_INCREMENTAL, "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"), "finished_at": _now(),
            "seconds": round(monotonic() - begun, 1), "primary_target_id": target_id, "objects": len(listed),
            "bytes": sum(size for size, _ in listed.values()), "tree_sha256": tree, "counts": dict(counts), "new": len(new),
            "changed_timestamp": len(changed), "recopied": len(recopy), "copied_bytes": copied_bytes,
            "stopped": bool(stop_reason), "stop_reason": stop_reason[0] if stop_reason else None,
            "primary_temporary_files": primary_temporaries[:20], "own_temporaries_swept": swept, "fixity": fixity, "restore_test": restore,
            "problems": problems[:50], "problem_count": len(problems), "previous_receipt_written_at": previous.get("written_at"),
            "last_full_verification_at": previous.get("last_full_verification_at") or previous.get("written_at"),
            "ok": ok}


def _fixity_rotation(primary: Path, root: Path, inventory: Mapping[str, tuple[str, int]], previous: Mapping[str, Any],
                     limits: Mapping[str, int], halted: Callable[[], bool], rate: "M._Rate", run_id: str) -> dict[str, Any]:
    """Re-hash a budgeted slice of objects on both roots, past the client cache, oldest verification first. An object never
    re-hashed since the last full run counts as verified at that run (the full run re-hashed every object on both roots)."""
    baseline_at = previous.get("last_full_verification_at") or previous.get("written_at") or ""
    log = load_fixity(root)
    order = sorted(inventory, key=lambda p: (log.get(p, baseline_at), p))
    checked, checked_bytes, problems = 0, 0, []
    journal = M._Journal(root / STATE / FIXITY_LOG)
    try:
        for path in order:
            sha, size = inventory[path]
            if checked >= limits["fixity_objects_per_run"] or (checked and checked_bytes + size > limits["fixity_bytes_per_run"]) or halted():
                break
            rate.take(size)
            try:
                on_primary = M.sha256_uncached(primary.joinpath(*path.split("/")))
            except OSError as error:
                problems.append({"path": path, "problem": f"FIXITY_UNREADABLE_PRIMARY: {type(error).__name__}"})
                break                                         # the share is in trouble: no more reads of it now
            try:
                on_backup = M.sha256_uncached(root.joinpath(*path.split("/")))
            except OSError as error:
                on_backup = (f"unreadable: {type(error).__name__}", -1)
            ok = on_primary == (sha, size) and on_backup == (sha, size)
            if on_primary != (sha, size):
                problems.append({"path": path, "problem": "FIXITY_MISMATCH_PRIMARY"})
            if on_backup != (sha, size):
                problems.append({"path": path, "problem": "FIXITY_MISMATCH_BACKUP"})
            journal.write(json.dumps({"path": path, "ok": ok, "at": _now(), "run_id": run_id, "reread": "uncached"}, sort_keys=True) + "\n")
            checked, checked_bytes = checked + 1, checked_bytes + size
            if ok:
                log[path] = _now()
    finally:
        journal.close()
    oldest = min((log.get(p, baseline_at) for p in inventory), default=None)
    age_days = None
    if oldest:
        try:
            age_days = round((datetime.now(timezone.utc) - datetime.fromisoformat(oldest.replace("Z", "+00:00"))).total_seconds() / 86400, 1)
        except ValueError:
            age_days = None
    return {"checked": checked, "checked_bytes": checked_bytes, "reread": "uncached, both roots", "oldest_verification_at": oldest,
            "oldest_verification_age_days": age_days, "cycle_max_days": limits["fixity_cycle_max_days"],
            "cycle_overdue": age_days is not None and age_days > limits["fixity_cycle_max_days"], "problems": problems}


def _restore_rotation(root: Path, inventory: Mapping[str, tuple[str, int]], scratch: Path, *, samples: int, salt: str) -> dict[str, Any]:
    """Restore a sample that changes with every run from the BACKUP root into an empty scratch directory and re-hash it."""
    base = {"objects": [{"path": p, "sha256": s, "size": z} for p, (s, z) in inventory.items()]}
    ordered = sorted(base["objects"], key=lambda e: hashlib.sha256(f"restore-test/v2:{salt}:{e['path']}".encode("utf-8")).hexdigest())
    return restore_test(root, {"objects": ordered}, scratch, samples=samples, preordered=True) if inventory else {
        "tested_at": _now(), "read_from": "BACKUP root", "samples": 0, "ok_count": 0, "bytes": 0, "all_ok": False, "cases": []}


_MANIFEST_PREFIX = "preservation/manifests/"


def seed_manifest_cache(root: Path, cache: Any, *, stop: Callable[[], str | None] | None = None) -> dict[str, Any]:
    """Fill the RUNTIME manifest cache of the primary (``preserved_index.ManifestCache``, CPD-0033) from the BACKUP root,
    without any contact with the share (CPD-0035 §4).

    A copy is taken only from a backup whose verified receipt names the cache's target, and only when the backup file's bytes
    hash to the journal's digest -- the digest the bytes on the primary were read with when they were copied and re-read
    unbuffered. A bound manifest never changes (``preservation.promote`` refuses any other content), so such a copy is the
    primary's manifest. Copies the cache holds are not read again; a promotion still lists the area on the root and reads
    whatever is newer, and still verifies on the root any master it binds to. Local reads only; resumable."""
    from . import preservation

    receipt = read_receipt(root)
    if not receipt or not receipt.get("verified_against_primary") or receipt.get("primary_target_id") != cache.target_id:
        raise BackupError(f"no verified receipt of target {cache.target_id!r} on {root}: the cache is not seeded from it")
    counts: Counter[str] = Counter()
    halted = None
    for path, row in sorted(load_evidence(root).items()):
        if not path.startswith(_MANIFEST_PREFIX) or not path.endswith(".json"):
            continue
        area, _, name = path[len(_MANIFEST_PREFIX):].rpartition("/")
        object_id = name[:-5]
        if not area or "/" in area or cache._read_copy(cache._path(area, object_id), area, object_id) is not None:
            counts["HELD"] += 1
            continue
        if stop is not None and counts["SEEDED"] % 100 == 0:          # asked every hundred copies: local files, but not per file
            halted = stop()
            if halted:
                break
        try:
            data = Path(M._long(Path(root).joinpath(*path.split("/")))).read_bytes()
        except OSError:
            counts["UNREADABLE"] += 1
            continue
        if (hashlib.sha256(data).hexdigest(), len(data)) != (row["sha256"], row["size"]):
            counts["DIFFERS_FROM_EVIDENCE"] += 1
            continue
        try:
            manifest = json.loads(data.decode("utf-8"))
        except ValueError:
            counts["NOT_A_MANIFEST"] += 1
            continue
        if (not isinstance(manifest, Mapping) or manifest.get("schema") != preservation.MANIFEST_SCHEMA
                or manifest.get("area") != area or manifest.get("object_id") != object_id):
            counts["NOT_A_MANIFEST"] += 1
            continue
        cache.store(manifest)
        counts["SEEDED"] += 1
    return {"target_id": cache.target_id, "from_receipt": receipt.get("written_at"), "counts": dict(counts), "stopped": halted}


__all__ = ["BackupError", "EVIDENCE", "NeedsFullAuthorization", "seed_manifest_cache", "HOLDINGS", "backup_health", "MARKER", "MODE_FULL", "MODE_INCREMENTAL", "RECEIPT", "SCHEMA", "STATE", "copy", "init_root",
           "list_tree", "load_evidence", "load_fixity", "load_journal", "read_last_run", "read_receipt", "receipt_status", "require_root",
           "restore_test", "run_incremental", "verify", "write_last_run", "write_receipt"]
