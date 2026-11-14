"""A local, rebuildable index of what one PRESERVATION target holds, and a verified local read path (decision CPD-0033).

The PRESERVATION primary is an institutional share: about 260 ms per small file from this workstation (measured
2026-10-14) and shared with CO.RA.PAN. Two regular operations used to read it far more than the bytes require:

* **the content check of every promotion** (``preservation.find_by_content``) read every manifest of the area -- for
  2,204 packs, 4,408 small reads per new pack, growing with the corpus;
* **every derived read of a pack** (identity, extraction, labels, replay, the identity rebuild of a finalizer)
  re-hashed both masters on the share past the client cache and read the pack from there, although the workspace holds
  a byte-identical sealed copy.

This module removes both without weakening a guarantee:

* :class:`ManifestCache` keeps a copy of each preservation manifest under ``<RUNTIME>/cache/preservation_manifests/
  <target_id>/<area>/<object_id>.json``. A bound manifest never changes its object id, digest, size or master path
  (``preservation.promote`` refuses any other content as an ``IdentityConflict``), so a copy of it answers those questions
  for as long as the target is the same target: the cache is keyed by the target's identity marker (contract T1), and a
  different identity is a different, empty cache. The cache is derived state: deleting it costs only reads.
  :meth:`ManifestCache.find_by_content` lists the area's manifest directory once (one enumeration, not one read per
  object), reads only the manifests it does not hold yet, and answers from the copies.
* :func:`verified_local_copy` returns the workspace's sealed pack and index **only** when their bytes hash to the
  digests the preservation manifests record -- the digests the bytes on the primary were verified against when they
  became ``RAW_PRESERVED`` (contract P2). Bytes equal to a verified master are that master's bytes; a copy that does not
  hash, or is missing, is not used and the read goes to the primary as before.

What this does **not** do: it does not verify the primary. That a master on the share is still intact is the question
of fixity, which is answered by a separate, budgeted rotation (``primary_backup`` fixity), never implied by a read of a
local copy. Nothing in a promotion relies on the cache to call an object preserved: P2's re-read of the landed bytes on
the primary is unchanged.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Mapping

from . import preservation, preservation_target
from .canonical import record_json, sha256_file, write_bytes_atomic

CACHE_DIRECTORY = "cache/preservation_manifests"
_MEMORY: dict[str, dict[str, dict[str, str]]] = {}
_LOCK = threading.Lock()


class ManifestCache:
    """The manifests of one target, copied to RUNTIME. ``directory`` is ``<RUNTIME>/cache/preservation_manifests/<target_id>``."""

    def __init__(self, directory: Path, target_id: str) -> None:
        self.directory, self.target_id = Path(directory), target_id

    @classmethod
    def for_root(cls, runtime: Path, preservation_root: Path) -> "ManifestCache | None":
        """The cache of the target at ``preservation_root``, or ``None`` when the root carries no identity (then nothing is
        cached and every caller reads the root as before)."""
        marker = preservation_target.read_target(Path(preservation_root))
        if not marker or not marker.get("target_id"):
            return None
        target_id = str(marker["target_id"])
        if not target_id.replace("-", "").replace("_", "").replace(".", "").isalnum():
            return None
        return cls(Path(runtime) / CACHE_DIRECTORY / target_id, target_id)

    # --- one manifest -------------------------------------------------------------------------------------------

    def _path(self, area: str, object_id: str) -> Path:
        return self.directory / area / f"{object_id}.json"

    def _digests(self, area: str) -> dict[str, str]:
        """``{object_id: sha256}`` of the copies held for ``area``, kept in memory per process and filled from disk once."""
        key = f"{self.directory}|{area}"
        with _LOCK:
            if key not in _MEMORY:
                table: dict[str, str] = {}
                directory = self.directory / area
                if directory.is_dir():
                    for path in directory.glob("*.json"):
                        manifest = self._read_copy(path, area, path.stem)
                        if manifest is not None:
                            table[path.stem] = manifest["sha256"]
                _MEMORY[key] = table
            return _MEMORY[key]

    @staticmethod
    def _read_copy(path: Path, area: str, object_id: str) -> dict[str, Any] | None:
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if (not isinstance(manifest, Mapping) or manifest.get("schema") != preservation.MANIFEST_SCHEMA or manifest.get("object_id") != object_id
                or manifest.get("area") != area or not isinstance(manifest.get("sha256"), str)):
            return None                                            # a damaged copy is not an answer: the root is read again
        return dict(manifest)

    def store(self, manifest: Mapping[str, Any]) -> None:
        """Keep a copy of a manifest read from (or just bound on) the root."""
        area, object_id = manifest["area"], manifest["object_id"]
        path = self._path(area, object_id)
        write_bytes_atomic(path, record_json(dict(manifest)))
        with _LOCK:
            table = _MEMORY.get(f"{self.directory}|{area}")
            if table is not None:
                table[object_id] = manifest["sha256"]

    def get(self, root: Path, area: str, object_id: str) -> dict[str, Any] | None:
        """The manifest of ``object_id``: the copy if it is held and readable, else the root's (then copied). ``None`` when
        the root has none -- an absence on the root is never cached."""
        held = self._read_copy(self._path(area, object_id), area, object_id)
        if held is not None:
            return held
        manifest = preservation.read_manifest(Path(root), area, object_id)
        if manifest is not None:
            self.store(manifest)
        return manifest

    # --- the content check of a promotion ----------------------------------------------------------------------

    def refresh(self, root: Path, area: str) -> dict[str, int]:
        """Bring the copies of ``area`` up to the root: one listing of its manifest directory, then a read of each manifest
        not held yet. Returns what it did."""
        directory = (Path(root) / preservation.manifest_relative_path(area, "x")).parent
        if not directory.is_dir():
            return {"listed": 0, "read": 0}
        with os.scandir(directory) as entries:
            names = [entry.name[:-5] for entry in entries if entry.name.endswith(".json") and entry.is_file()]
        table = self._digests(area)
        read = 0
        for object_id in sorted(set(names) - set(table)):
            manifest = preservation.read_manifest(Path(root), area, object_id)
            if manifest is not None:
                self.store(manifest)
                read += 1
        return {"listed": len(names), "read": read}

    def find_by_content(self, root: Path, area: str, sha256: str) -> dict[str, Any] | None:
        """``preservation.find_by_content`` answered from the copies, after :meth:`refresh`: the same answer (the first
        manifest in name order whose digest is ``sha256``), for a listing and the new manifests instead of every manifest."""
        self.refresh(root, area)
        table = self._digests(area)
        for object_id in sorted(name for name, digest in table.items() if digest == sha256):
            manifest = self.get(root, area, object_id)
            if manifest is not None and manifest["sha256"] == sha256:
                return manifest
        return None


def verified_local_copy(workspace_packs: Path | None, identifier: str, pack_manifest: Mapping[str, Any] | None,
                        index_manifest: Mapping[str, Any] | None) -> tuple[Path, Path] | None:
    """The workspace's sealed pack and index of ``identifier``, when both hash to the preservation manifests' digests and
    sizes; otherwise ``None``. Local reads only."""
    if workspace_packs is None or not pack_manifest or not index_manifest:
        return None
    pack_path = Path(workspace_packs) / f"{identifier}.warc.gz"
    index_path = Path(workspace_packs) / f"{identifier}.index.jsonl"
    try:
        for path, manifest in ((pack_path, pack_manifest), (index_path, index_manifest)):
            if not path.is_file() or path.stat().st_size != manifest["size_bytes"]:
                return None
            if sha256_file(path)[0] != manifest["sha256"]:
                return None
    except (OSError, KeyError):
        return None
    return pack_path, index_path


def reset_memory() -> None:
    """Forget the in-memory tables (tests; a process that replaced its cache directory)."""
    with _LOCK:
        _MEMORY.clear()


__all__ = ["CACHE_DIRECTORY", "ManifestCache", "reset_memory", "verified_local_copy"]
