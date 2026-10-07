"""Write-once layer store (``docs/architecture/TARGET_ARCHITECTURE.md`` §2).

Three different things, kept apart:

* the **fingerprint** says what was asked: stage, stage version, input hashes, parameters;
* the **artifact id** says which answer was produced: fingerprint plus payload hash;
* **execution provenance** (when, where, by which run) is recorded in the manifest and is part of
  neither.

One answer per fingerprint: storing the same answer again is a no-op, storing a *different* answer
under the same fingerprint is an error, never a new version. Nothing is overwritten.

The store works on whatever directory it is given. Which storage role holds the durable,
non-released layer store is still open (``docs/storage/INDEX.md`` §11).
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import naming
from .canonical import canonical_json, record_json, require_sha256, sha256_bytes
from .identity import format_instant

FINGERPRINT_SCHEMA = naming.schema_id("layer-fingerprint", 1)
MANIFEST_SCHEMA = naming.schema_id("layer-manifest", 1)
ARTIFACT_ID_PREFIX = "ar1"
ARTIFACT_HASH_LENGTH = 32

STATUS_STORED = "STORED"
STATUS_ALREADY_STORED = "ALREADY_STORED"

PAYLOAD_NAME = "payload"
MANIFEST_NAME = "manifest.json"
MARKER_NAME = "PROMOTED"

_STAGE = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*")
_ARTIFACT_ID = re.compile(rf"{ARTIFACT_ID_PREFIX}-[0-9a-f]{{{ARTIFACT_HASH_LENGTH}}}")


class LayerStoreError(RuntimeError):
    """The store cannot answer, or what it holds does not verify."""


class FingerprintConflict(LayerStoreError):
    """A different answer was offered for a fingerprint that already has one."""


@dataclass(frozen=True)
class StoredArtifact:
    status: str
    stage: str
    fingerprint: str
    artifact_id: str
    payload_sha256: str
    directory: Path


def fingerprint(
    stage: str,
    stage_version: str,
    inputs: Mapping[str, str],
    parameters: Mapping[str, Any] | None = None,
) -> str:
    """SHA-256 over the canonical JSON of what was asked. ``inputs`` maps a role name to the
    SHA-256 of that input; ``parameters`` is any JSON value that changes the answer.
    """
    _stage(stage)
    if not isinstance(stage_version, str) or not stage_version:
        raise LayerStoreError(f"a stage version is a non-empty string: {stage_version!r}")
    for name, digest in inputs.items():
        if not isinstance(name, str) or not name:
            raise LayerStoreError(f"an input needs a name: {name!r}")
        require_sha256(digest, f"input {name!r}")
    try:
        preimage = canonical_json(
            {
                "schema": FINGERPRINT_SCHEMA,
                "stage": stage,
                "stage_version": stage_version,
                "inputs": dict(inputs),
                "parameters": dict(parameters or {}),
            }
        )
    except (TypeError, ValueError) as error:
        raise LayerStoreError(f"parameters are not canonical JSON: {error}") from error
    return sha256_bytes(preimage)


def artifact_id(fingerprint_value: str, payload_sha256: str) -> str:
    """``ar1-`` + 32 hex digits of SHA-256 over ``<fingerprint>:<payload sha256>``."""
    require_sha256(fingerprint_value, "fingerprint")
    require_sha256(payload_sha256, "payload_sha256")
    digest = sha256_bytes(f"{fingerprint_value}:{payload_sha256}".encode("ascii"))
    return f"{ARTIFACT_ID_PREFIX}-{digest[:ARTIFACT_HASH_LENGTH]}"


class LayerStore:
    """``<root>/<stage>/<fp[:2]>/<fp>/<artifact_id>/{payload, manifest.json, PROMOTED}``.

    An artifact exists once its ``PROMOTED`` marker does; the marker holds the SHA-256 of the
    manifest bytes. A directory without a marker is an abandoned write and is never an answer.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        if not self.root.is_dir():
            raise LayerStoreError("the layer store root is not an existing directory")

    def _slot(self, stage: str, fingerprint_value: str) -> Path:
        require_sha256(fingerprint_value, "fingerprint")
        return self.root / _stage(stage) / fingerprint_value[:2] / fingerprint_value

    def put(
        self,
        stage: str,
        fingerprint_value: str,
        payload: bytes,
        *,
        provenance: Mapping[str, Any] | None = None,
        now: datetime | None = None,
    ) -> StoredArtifact:
        """Store the answer for a fingerprint, or confirm that this very answer is stored."""
        if not isinstance(payload, bytes):
            raise LayerStoreError("a payload is bytes")
        slot = self._slot(stage, fingerprint_value)
        payload_sha256 = sha256_bytes(payload)
        identifier = artifact_id(fingerprint_value, payload_sha256)

        existing = self.get(stage, fingerprint_value)
        if existing is not None:
            if existing.artifact_id != identifier:
                raise FingerprintConflict(
                    f"{stage}: fingerprint {fingerprint_value[:16]}… already answered by "
                    f"{existing.artifact_id}; refusing a different answer {identifier}"
                )
            return StoredArtifact(STATUS_ALREADY_STORED, stage, fingerprint_value, identifier, payload_sha256, existing.directory)

        manifest = record_json(
            {
                "schema": MANIFEST_SCHEMA,
                "stage": stage,
                "fingerprint": fingerprint_value,
                "artifact_id": identifier,
                "payload_sha256": payload_sha256,
                "payload_bytes": len(payload),
                "stored_at": format_instant(now if now is not None else datetime.now(timezone.utc)),
                "execution_provenance": dict(provenance or {}),
            }
        )
        staging = self.root / ".staging" / uuid.uuid4().hex
        staging.mkdir(parents=True)
        for name, data in (
            (PAYLOAD_NAME, payload),
            (MANIFEST_NAME, manifest),
            (MARKER_NAME, (sha256_bytes(manifest) + "\n").encode("ascii")),
        ):
            with open(staging / name, "xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        slot.mkdir(parents=True, exist_ok=True)
        final = slot / identifier
        try:
            os.rename(staging, final)
        except OSError as error:
            raise LayerStoreError(f"{stage}: could not publish {identifier}; staged copy kept") from error
        return StoredArtifact(STATUS_STORED, stage, fingerprint_value, identifier, payload_sha256, final)

    def get(self, stage: str, fingerprint_value: str) -> StoredArtifact | None:
        """The verified artifact for a fingerprint, ``None`` if there is none.

        More than one promoted artifact under one fingerprint is a corrupted store and raises.
        """
        slot = self._slot(stage, fingerprint_value)
        if not slot.is_dir():
            return None
        promoted = sorted(path for path in slot.iterdir() if (path / MARKER_NAME).is_file())
        if not promoted:
            return None
        if len(promoted) > 1:
            raise FingerprintConflict(
                f"{stage}: fingerprint {fingerprint_value[:16]}… holds {len(promoted)} answers"
            )
        directory = promoted[0]
        manifest = self._verified_manifest(directory, stage, fingerprint_value)
        return StoredArtifact(
            STATUS_ALREADY_STORED, stage, fingerprint_value, manifest["artifact_id"], manifest["payload_sha256"], directory
        )

    def read(self, stage: str, fingerprint_value: str) -> bytes:
        """The payload for a fingerprint, re-hashed before it is returned."""
        artifact = self.get(stage, fingerprint_value)
        if artifact is None:
            raise LayerStoreError(f"{stage}: no artifact for fingerprint {fingerprint_value[:16]}…")
        payload = (artifact.directory / PAYLOAD_NAME).read_bytes()
        if sha256_bytes(payload) != artifact.payload_sha256:
            raise LayerStoreError(f"{stage}: payload of {artifact.artifact_id} does not match its manifest")
        return payload

    def manifest(self, stage: str, fingerprint_value: str) -> dict[str, Any]:
        artifact = self.get(stage, fingerprint_value)
        if artifact is None:
            raise LayerStoreError(f"{stage}: no artifact for fingerprint {fingerprint_value[:16]}…")
        return self._verified_manifest(artifact.directory, stage, fingerprint_value)

    def _verified_manifest(self, directory: Path, stage: str, fingerprint_value: str) -> dict[str, Any]:
        try:
            manifest_bytes = (directory / MANIFEST_NAME).read_bytes()
            marker = (directory / MARKER_NAME).read_text(encoding="ascii").strip()
            manifest = json.loads(manifest_bytes.decode("utf-8"))
            consistent = (
                marker == sha256_bytes(manifest_bytes)
                and manifest["schema"] == MANIFEST_SCHEMA
                and manifest["stage"] == stage
                and manifest["fingerprint"] == fingerprint_value
                and manifest["artifact_id"] == directory.name
                and manifest["artifact_id"] == artifact_id(fingerprint_value, manifest["payload_sha256"])
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise LayerStoreError(f"{stage}: artifact {directory.name} is unreadable: {error}") from error
        if not consistent:
            raise LayerStoreError(f"{stage}: artifact {directory.name} does not match its marker or manifest")
        return manifest


def is_artifact_id(value: object) -> bool:
    return isinstance(value, str) and _ARTIFACT_ID.fullmatch(value) is not None


def _stage(value: str) -> str:
    if not isinstance(value, str) or _STAGE.fullmatch(value) is None:
        raise LayerStoreError(f"not a stage name: {value!r}")
    return value
