"""The pre-copy of the PRESERVATION primary to the root that becomes the primary at cutover (``crosscorpus-storage/v1``
§11.2 steps 1, 3, 4, 6, 7; CPD-0030). Not a cutover: nothing here changes a configured root.

* **Baseline (step 1).** The source's contract inventory (``release_contract.tree_listing``: path, size, SHA-256 of every
  file), without the source's identity marker and without probe or migration evidence directories.
* **Copy (step 3).** Every object of a CO.PRE.PAN primary is write-once (sealed WARC packs, their indexes, manifests). Each
  file is read once; its digest must be the baseline's (else ``SOURCE_CHANGED``, not copied); the bytes go to a temporary
  file beside the destination, its timestamp is set to the source's, it is re-read UNBUFFERED from the file server and must
  have the same digest; only then it is published with ``os.rename``, which never replaces an existing name. A destination
  that already holds the object with the same digest is ``ALREADY_PRESENT``; with another digest it is ``CONFLICT`` and is
  left as it is.
* **Identity (step 4).** The destination must carry its own marker (``preservation_target.initialise_target``) and must not
  be the root the workstation uses today.
* **Verification (step 6).** Every baseline object re-read unbuffered from the destination; what the destination holds beyond
  the baseline; leftover temporary files.
* **Resumable.** A journal under ``_migration/<migration id>/`` on the destination, appended per object; a rerun skips what
  the journal and the published file's size and timestamp confirm.

Nothing is deleted except this tool's own unpublished temporary files. The source is opened read-only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from . import naming, preservation_target, release_contract

SCHEMA = naming.schema_id("preservation-migration", 1)
STATE_DIRECTORY = "_migration"
EXCLUDED_DIRECTORIES = (STATE_DIRECTORY, preservation_target.PROBE_DIRECTORY)
TEMP_TAG = ".coprepan-migrate-part-"
_OWN_TEMP = re.compile(r".+" + re.escape(TEMP_TAG) + r"[0-9a-f]{8}$")
CHUNK = 4 * 1024 * 1024

COPIED, SKIPPED, PRESENT = "COPIED", "SKIPPED_JOURNALLED", "ALREADY_PRESENT"
CONFLICT, SOURCE_CHANGED, FAILED = "CONFLICT", "SOURCE_CHANGED", "FAILED"
DONE = (COPIED, PRESENT)
PROBLEMS = (CONFLICT, SOURCE_CHANGED, FAILED)


class MigrationError(RuntimeError):
    """The migration cannot proceed without risking integrity or the identity of a primary."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _long(path: Path | str) -> str:
    text = os.path.abspath(str(path))
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    return "\\\\?\\UNC\\" + text[2:] if text.startswith("\\\\") else "\\\\?\\" + text


def sha256_uncached(path: Path | str) -> tuple[str, int]:
    """SHA-256 and size read past the local client cache (Windows ``FILE_FLAG_NO_BUFFERING``): a re-read straight after a
    write over SMB is otherwise served by the local cache and proves nothing about the server (measured 2026-10-14)."""
    if os.name != "nt":
        digest, size = hashlib.sha256(), 0
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(CHUNK), b""):
                digest.update(block)
                size += len(block)
        return digest.hexdigest(), size
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.HANDLE]
    kernel.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel.VirtualAlloc.restype = wintypes.LPVOID
    kernel.VirtualAlloc.argtypes = [wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    kernel.VirtualFree.argtypes = [wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(_long(path), 0x80000000, 0x7, None, 3, 0x20000000 | 0x08000000, None)
    if handle in (None, wintypes.HANDLE(-1).value):
        raise OSError(ctypes.get_last_error(), "cannot open unbuffered", str(path))
    buffer = kernel.VirtualAlloc(None, CHUNK, 0x3000, 0x04)
    try:
        digest, size, got = hashlib.sha256(), 0, wintypes.DWORD(0)
        view = (ctypes.c_char * CHUNK).from_address(buffer)
        while True:
            if not kernel.ReadFile(handle, buffer, CHUNK, ctypes.byref(got), None):
                raise OSError(ctypes.get_last_error(), "unbuffered read failed", str(path))
            if not got.value:
                return digest.hexdigest(), size
            digest.update(memoryview(view)[:got.value])
            size += got.value
    finally:
        kernel.VirtualFree(buffer, 0, 0x8000)
        kernel.CloseHandle(handle)


def _excluded(path: str) -> bool:
    return path == preservation_target.MARKER_NAME or path.split("/", 1)[0] in EXCLUDED_DIRECTORIES


def baseline(source: Path) -> dict[str, Any]:
    """Step 1: the source's objects with the digest each must keep. The marker and evidence directories are not objects."""
    listing = [entry for entry in release_contract.tree_listing(Path(source)) if not _excluded(entry["path"])]
    for entry in listing:
        entry["mtime_ns"] = os.stat(Path(source).joinpath(*entry["path"].split("/"))).st_mtime_ns
    marker = preservation_target.read_target(Path(source))
    return {"schema": SCHEMA, "kind": "baseline", "taken_at": _now(), "source_label": Path(source).name,
            "source_target_id": marker["target_id"] if marker else None, "files": len(listing),
            "bytes": sum(entry["size"] for entry in listing),
            "tree_sha256": release_contract.record_set_digest([{k: e[k] for k in ("path", "sha256", "size")} for e in listing]),
            "objects": listing}


def journal_path(dest: Path, migration_id: str) -> Path:
    return Path(dest) / STATE_DIRECTORY / migration_id / "journal.jsonl"


def load_journal(dest: Path, migration_id: str) -> dict[str, dict[str, Any]]:
    path = Path(_long(journal_path(dest, migration_id)))
    out: dict[str, dict[str, Any]] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue                          # a row torn by a broken handle: the object is re-recognised by digest
                if row.get("status") in DONE:
                    out[row["path"]] = row
    return out


class _Journal:
    """Append rows robustly: after an I/O error (a reset SMB session invalidates an open handle -- measured 2026-10-14) the handle
    is reopened and the row written again, with a growing pause. One ``write`` per row."""

    def __init__(self, path: Path, *, attempts: int = 8, pause: float = 5.0, sleep: Callable[[float], None] = time.sleep):
        self.path, self.attempts, self.pause, self.sleep, self.handle, self.reopened = path, attempts, pause, sleep, None, 0

    def write(self, text: str) -> None:
        for attempt in range(self.attempts):
            try:
                if self.handle is None:
                    self.handle = open(self.path, "a", encoding="utf-8", newline="\n")
                self.handle.write(text)
                self.handle.flush()
                return
            except OSError:
                self.close()
                if attempt == self.attempts - 1:
                    raise
                self.reopened += 1
                self.sleep(min(300.0, self.pause * 2 ** attempt))

    def close(self) -> None:
        if self.handle is not None:
            try:
                self.handle.close()
            except OSError:
                pass
            self.handle = None


def _transient(result: Mapping[str, Any]) -> bool:
    return result.get("status") == FAILED and str(result.get("error", "")).split(":", 1)[0] in (
        "OSError", "PermissionError", "ConnectionError", "TimeoutError", "BrokenPipeError", "FileNotFoundError")


def require_destination(dest: Path, *, active_root: Path | str | None) -> dict[str, Any]:
    """The destination is an existing directory with its own identity marker and is not the root in use today."""
    dest = Path(dest)
    if not Path(_long(dest)).is_dir():
        raise MigrationError(f"{dest} is not an existing directory; a migration never creates the destination root")
    marker = preservation_target.read_target(dest)
    if marker is None:
        raise MigrationError(f"{dest} carries no {preservation_target.MARKER_NAME}; it was never set up as a preservation target")
    if active_root is not None and os.path.normcase(os.path.normpath(str(active_root))) == os.path.normcase(os.path.normpath(str(dest))):
        raise MigrationError(f"{dest} is the PRESERVATION root in use today; a pre-copy never writes into a live primary")
    return marker


def _discard_own_temporary(path: Path | str) -> None:
    """The ONLY removal in this module: an unpublished temporary file of this tool (``<name>.coprepan-migrate-part-<8 hex>``).
    Refuses any other name."""
    if not _OWN_TEMP.fullmatch(Path(path).name):
        raise ValueError(f"not a temporary file of the migration: {Path(path).name!r}")
    Path(path).unlink(missing_ok=True)


def _publish(temporary: Path, final: Path, digest: str) -> str:
    try:
        os.rename(temporary, final)
        return COPIED
    except (FileExistsError, PermissionError):
        same = final.is_file() and sha256_uncached(final)[0] == digest
        _discard_own_temporary(temporary)
        return PRESENT if same else CONFLICT


class _Rate:
    def __init__(self, per_second: float | None):
        self.rate, self.lock, self.allowance, self.last = per_second, threading.Lock(), 0.0, time.monotonic()

    def take(self, amount: int) -> None:
        while self.rate:
            with self.lock:
                now = time.monotonic()
                self.allowance = min(self.rate, self.allowance + (now - self.last) * self.rate)
                self.last = now
                if self.allowance >= amount or self.allowance >= self.rate:
                    self.allowance -= amount
                    return
                wait = (amount - self.allowance) / self.rate
            time.sleep(min(wait, 1.0))


def migrate_one(source: Path, dest: Path, entry: Mapping[str, Any], known: Mapping[str, Any] | None, *, run_id: str,
                rate: _Rate) -> dict[str, Any]:
    path = entry["path"]
    src = Path(_long(Path(source).joinpath(*path.split("/"))))
    dst = Path(_long(Path(dest).joinpath(*path.split("/"))))
    row: dict[str, Any] = {"path": path, "size": entry["size"], "sha256": entry["sha256"], "mtime_ns": entry.get("mtime_ns"), "run_id": run_id}
    try:
        if known and known.get("sha256") == entry["sha256"] and dst.is_file():
            stat = dst.stat()
            if stat.st_size == entry["size"] and (entry.get("mtime_ns") is None or stat.st_mtime_ns == entry["mtime_ns"]):
                return {**row, "status": SKIPPED}
        if dst.is_file():
            return {**row, "status": PRESENT if sha256_uncached(dst)[0] == entry["sha256"] else CONFLICT}
        dst.parent.mkdir(parents=True, exist_ok=True)
        temporary = dst.with_name(f"{dst.name}{TEMP_TAG}{uuid.uuid4().hex[:8]}")
        try:
            digest = hashlib.sha256()
            with open(src, "rb") as reader, open(temporary, "xb") as writer:
                for block in iter(lambda: reader.read(CHUNK), b""):
                    rate.take(len(block))
                    digest.update(block)
                    writer.write(block)
                writer.flush()
                os.fsync(writer.fileno())
            if digest.hexdigest() != entry["sha256"]:
                return {**row, "status": SOURCE_CHANGED, "source_sha256": digest.hexdigest()}
            if entry.get("mtime_ns") is not None:
                os.utime(temporary, ns=(entry["mtime_ns"], entry["mtime_ns"]))
            landed, size = sha256_uncached(temporary)
            if landed != entry["sha256"] or size != entry["size"]:
                return {**row, "status": FAILED, "error": "the bytes on the destination differ from the source"}
            status = _publish(temporary, dst, entry["sha256"])
            return {**row, "status": status, "reread": "uncached",
                    "mtime_kept": entry.get("mtime_ns") is None or dst.stat().st_mtime_ns == entry["mtime_ns"]}
        finally:
            if temporary.exists():
                _discard_own_temporary(temporary)                 # only this run's own unpublished temporary file
    except OSError as error:
        return {**row, "status": FAILED, "error": f"{type(error).__name__}: {error}"}


def copy(source: Path, dest: Path, entries: Iterable[Mapping[str, Any]], *, migration_id: str, active_root: Path | str | None,
         workers: int = 3, max_bytes_per_second: float | None = None, stop_file: Path | None = None,
         progress: Callable[[str], None] | None = None, retries: int = 3, retry_pause: float = 20.0,
         network_failure_limit: int = 12, sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    """Step 3. An object interrupted by the transport is retried with a growing pause; ``network_failure_limit`` such failures in a
    row stop the run cleanly (``stop_reason NETWORK_UNAVAILABLE``), resumable from the journal."""
    require_destination(dest, active_root=active_root)
    if os.path.normcase(os.path.abspath(source)) == os.path.normcase(os.path.abspath(dest)):
        raise MigrationError("source and destination are the same root")
    run_id = "mig" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + os.urandom(3).hex()
    known = load_journal(dest, migration_id)
    journal = Path(_long(journal_path(dest, migration_id)))
    journal.parent.mkdir(parents=True, exist_ok=True)
    rate, lock = _Rate(max_bytes_per_second), threading.Lock()
    counts: dict[str, int] = {}
    problems: list[dict[str, Any]] = []
    state = {"done": 0, "bytes": 0, "stopped": False}
    entries = list(entries)
    started = time.monotonic()
    handle = _Journal(journal)
    state["stop_reason"], in_a_row = None, [0]
    try:
        def work(entry):
            if state["stopped"] or (stop_file is not None and Path(stop_file).exists()):
                state["stopped"] = True
                state["stop_reason"] = state["stop_reason"] or "STOP_FILE"
                return
            for attempt in range(retries + 1):
                result = migrate_one(source, dest, entry, known.get(entry["path"]), run_id=run_id, rate=rate)
                if not _transient(result) or state["stopped"]:
                    break
                with lock:
                    in_a_row[0] += 1
                    if in_a_row[0] >= network_failure_limit:
                        state["stopped"], state["stop_reason"] = True, "NETWORK_UNAVAILABLE"
                if attempt < retries and not state["stopped"]:
                    sleep(retry_pause * 2 ** attempt)
            with lock:
                if not _transient(result):
                    in_a_row[0] = 0
                counts[result["status"]] = counts.get(result["status"], 0) + 1
                state["done"] += 1
                if result["status"] != SKIPPED:
                    handle.write(json.dumps({**result, "at": _now()}, sort_keys=True) + "\n")
                if result["status"] == COPIED:
                    state["bytes"] += result["size"]
                if result["status"] in PROBLEMS or result.get("mtime_kept") is False:
                    problems.append(result)
                if progress and state["done"] % 500 == 0:
                    progress(f"{state['done']}/{len(entries)} objects, {state['bytes'] / 2**20:.1f} MiB written, {counts}")

        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            list(pool.map(work, entries))
    finally:
        handle.close()
    return {"schema": SCHEMA, "kind": "run", "migration_id": migration_id, "run_id": run_id, "objects": len(entries), "processed": state["done"],
            "counts": counts, "copied_bytes": state["bytes"], "seconds": round(time.monotonic() - started, 1),
            "stopped": state["stopped"], "stop_reason": state["stop_reason"], "journal_reopened": handle.reopened, "problems": problems}


def verify(dest: Path, entries: Iterable[Mapping[str, Any]], *, workers: int = 4) -> dict[str, Any]:
    """Step 6: every baseline object re-read unbuffered from the destination; extras; leftover temporary files."""
    dest = Path(dest)
    wanted = {entry["path"]: entry for entry in entries}
    present, temporaries = {}, []
    for directory, _subdirs, files in os.walk(_long(dest)):
        for name in files:
            relative = Path(os.path.relpath(os.path.join(directory, name), _long(dest))).as_posix()
            if _excluded(relative):
                continue
            (temporaries.append(relative) if TEMP_TAG in name else present.__setitem__(relative, None))

    def one(item):
        path, entry = item
        if path not in present:
            return {"path": path, "problem": "MISSING"}
        try:
            digest, size = sha256_uncached(dest.joinpath(*path.split("/")))
        except OSError as error:
            return {"path": path, "problem": f"UNREADABLE: {error}"}
        if size != entry["size"] or digest != entry["sha256"]:
            return {"path": path, "problem": "DIFFERENT"}
        return None

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        problems = [p for p in pool.map(one, sorted(wanted.items())) if p]
    extra = sorted(path for path in present if path not in wanted)
    return {"schema": SCHEMA, "kind": "verification", "verified_at": _now(), "reread": "uncached", "objects": len(wanted),
            "bytes": sum(entry["size"] for entry in wanted.values()), "problems": problems, "extra": extra,
            "temporary_files": temporaries, "equal": not problems and not extra}


def sweep_temporary(dest: Path, *, migration_id: str, active_root: Path | str | None) -> list[str]:
    """Remove this tool's OWN leftover temporary files of a killed run (``<name>.coprepan-migrate-part-<8 hex>``); journalled."""
    require_destination(dest, active_root=active_root)
    removed = []
    journal = Path(_long(journal_path(dest, migration_id)))
    journal.parent.mkdir(parents=True, exist_ok=True)
    with open(journal, "a", encoding="utf-8", newline="\n") as handle:
        for directory, _subdirs, files in os.walk(_long(dest)):
            for name in files:
                relative = Path(os.path.relpath(os.path.join(directory, name), _long(dest))).as_posix()
                if _excluded(relative) or not _OWN_TEMP.fullmatch(name):
                    continue
                _discard_own_temporary(os.path.join(directory, name))
                removed.append(relative)
                handle.write(json.dumps({"path": relative, "status": "OWN_TEMP_REMOVED", "at": _now()}, sort_keys=True) + "\n")
    return removed
