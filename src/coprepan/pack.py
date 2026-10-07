"""Sealed WARC packs: the raw container (``docs/storage/INDEX.md`` §3, decision CPD-0005).

A pack is a WARC/1.1 file with one gzip member per record:

* one ``warcinfo`` record first;
* per fetch that returned a response: a ``response`` record whose payload is **the exact body
  bytes**, followed by a ``metadata`` record holding the fetch record;
* per fetch that returned nothing: the ``metadata`` record alone.

A fetch is in the pack once its ``metadata`` record is — the two records of a fetch are written
in one append. A pack is appended to while it is open (``<pack_id>.warc.gz.open``), then
**sealed**: every record is re-read and checked, the file is renamed to ``<pack_id>.warc.gz``, an
index and a manifest are written. A sealed pack is never modified.

"An index must be proven to fit the stream it addresses": the index is never written while
appending. It is derived at seal time by scanning the bytes that were actually written, the
manifest binds it to the pack's SHA-256, and every read through the index re-checks the record it
lands on.

The HTTP status line and header block inside a ``response`` record are rendered from the fetch
record; they are not wire bytes. What is identified by a digest is the body.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import zlib
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any, Iterator, Mapping

from . import acquisition, naming
from .canonical import canonical_json, line_json, record_json, sha256_bytes, sha256_file, write_bytes_atomic
from .identity import format_instant

PACK_MANIFEST_SCHEMA = naming.schema_id("pack", 1)
PACK_INDEX_SCHEMA = naming.schema_id("pack-index", 1)
PACK_WRITER_VERSION = "pack-writer/1"
WARC_VERSION = "WARC/1.1"
PACK_ID_PREFIX = "pk1"

_PACK_ID = re.compile(rf"{PACK_ID_PREFIX}-(?P<outlet>[a-z]{{2}}_[a-z0-9]+(?:_[a-z0-9]+)*)-(?P<day>\d{{8}})-(?P<seq>\d{{3}})")
_CHUNK = 256 * 1024
_CRLF = b"\r\n"


class PackError(RuntimeError):
    """The pack cannot be written, or what it holds does not verify."""


class PackTornTail(PackError):
    """The open pack ends in bytes that are not a complete fetch: a write was interrupted."""

    def __init__(self, message: str, offset: int) -> None:
        super().__init__(message)
        self.offset = offset


class DuplicateFetch(PackError):
    """The pack already holds this fetch."""


@dataclass(frozen=True)
class PackEntry:
    """Where one fetch lives in a pack. Offsets and lengths address gzip members."""

    fetch_id: str
    requested_url: str
    outcome: str
    body_sha256: str | None
    body_size_bytes: int | None
    response_offset: int | None
    response_length: int | None
    metadata_offset: int
    metadata_length: int

    def as_row(self, pack_id: str) -> dict[str, Any]:
        return {
            "schema": PACK_INDEX_SCHEMA,
            "pack_id": pack_id,
            "fetch_id": self.fetch_id,
            "requested_url": self.requested_url,
            "outcome": self.outcome,
            "body_sha256": self.body_sha256,
            "body_size_bytes": self.body_size_bytes,
            "response_offset": self.response_offset,
            "response_length": self.response_length,
            "metadata_offset": self.metadata_offset,
            "metadata_length": self.metadata_length,
        }


def pack_id(outlet_id: str, utc_day: str, sequence: int = 0) -> str:
    """``pk1-<outlet_id>-<YYYYMMDD>-<nnn>``: one pack per outlet and UTC day, plus a rollover number."""
    value = f"{PACK_ID_PREFIX}-{outlet_id}-{utc_day}-{sequence:03d}"
    if not naming.is_outlet_id(outlet_id) or _PACK_ID.fullmatch(value) is None:
        raise PackError(f"not a pack id: {value!r}")
    return value


def is_pack_id(value: object) -> bool:
    return isinstance(value, str) and _PACK_ID.fullmatch(value) is not None


def pack_outlet(value: str) -> str:
    match = _PACK_ID.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise PackError(f"not a pack id: {value!r}")
    return match.group("outlet")


def utc_day_of(instant: str) -> str:
    """``YYYYMMDD`` of a canonical UTC instant string."""
    return instant[:10].replace("-", "")


# --- record rendering -----------------------------------------------------------------------------


def _record(warc_type: str, record_id: str, date: str, block: bytes, content_type: str,
            extra: Mapping[str, str] | None = None) -> bytes:
    headers = [
        ("WARC-Type", warc_type),
        ("WARC-Record-ID", f"<{record_id}>"),
        ("WARC-Date", date),
        *(extra or {}).items(),
        ("Content-Type", content_type),
        ("WARC-Block-Digest", f"sha256:{sha256_bytes(block)}"),
        ("Content-Length", str(len(block))),
    ]
    head = WARC_VERSION.encode("ascii") + _CRLF + b"".join(
        f"{name}: {value}".encode("utf-8") + _CRLF for name, value in headers
    )
    # mtime=0: the member bytes depend on the content only, not on when they were written.
    return gzip.compress(head + _CRLF + block + _CRLF + _CRLF, compresslevel=6, mtime=0)


def _record_id(fetch_id: str, part: str) -> str:
    return f"urn:coprepan:{fetch_id}:{part}"


def _response_block(record: Mapping[str, Any], body: bytes) -> bytes:
    status = record["response"]["status"]
    try:
        phrase = HTTPStatus(status).phrase
    except ValueError:
        phrase = ""
    lines = [f"HTTP/1.1 {status} {phrase}".rstrip()]
    lines += [f"{name}: {value}" for name, value in record["response"]["headers"]]
    return "\r\n".join(lines).encode("utf-8") + _CRLF + _CRLF + body


def render_fetch(record: Mapping[str, Any], body: bytes | None) -> bytes:
    """The gzip members of one fetch: ``response`` (when there is a body) then ``metadata``."""
    acquisition.validate_fetch_record(record)
    fetch_id, date = record["fetch_id"], record["fetch_started_at"]
    fetched = record["outcome"] == acquisition.OUTCOME_FETCHED
    if fetched != (body is not None):
        raise PackError(f"{fetch_id}: outcome {record['outcome']} does not fit the presence of a body")
    members = b""
    extra = {"WARC-Target-URI": record["request"]["requested_url"]}
    if fetched:
        if sha256_bytes(body) != record["body_sha256"] or len(body) != record["body_size_bytes"]:
            raise PackError(f"{fetch_id}: the body offered is not the body the fetch record identifies")
        members += _record(
            "response", _record_id(fetch_id, "response"), date, _response_block(record, body),
            "application/http;msgtype=response",
            {**extra, "WARC-Payload-Digest": f"sha256:{record['body_sha256']}"},
        )
        extra["WARC-Concurrent-To"] = f"<{_record_id(fetch_id, 'response')}>"
    return members + _record(
        "metadata", _record_id(fetch_id, "metadata"), date, canonical_json(dict(record)), "application/json", extra
    )


# --- reading --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Member:
    offset: int
    length: int
    headers: Mapping[str, str]
    block: bytes


def _members(path: Path) -> Iterator[_Member]:
    """Every complete gzip member, in order. Raises :class:`PackTornTail` at the first byte that
    does not start a complete, well-formed record.
    """
    with open(path, "rb") as handle:
        offset, buffer = 0, b""
        while True:
            decompressor, parts, consumed = zlib.decompressobj(wbits=31), [], 0
            try:
                while not decompressor.eof:
                    if not buffer:
                        buffer = handle.read(_CHUNK)
                        if not buffer:
                            break
                    parts.append(decompressor.decompress(buffer))
                    consumed += len(buffer) - len(decompressor.unused_data)
                    buffer = decompressor.unused_data
            except zlib.error as error:
                raise PackTornTail(f"{path.name}: unreadable bytes at offset {offset}: {error}", offset) from error
            if not decompressor.eof:
                if consumed:
                    raise PackTornTail(f"{path.name}: incomplete record at offset {offset}", offset)
                return
            try:
                headers, block = _parse(b"".join(parts))
            except PackError as error:
                raise PackTornTail(f"{path.name}: malformed record at offset {offset}: {error}", offset) from error
            yield _Member(offset, consumed, headers, block)
            offset += consumed


def _parse(data: bytes) -> tuple[dict[str, str], bytes]:
    head, separator, rest = data.partition(_CRLF + _CRLF)
    lines = head.split(_CRLF)
    if not separator or lines[0] != WARC_VERSION.encode("ascii"):
        raise PackError("not a WARC/1.1 record")
    headers = {}
    for line in lines[1:]:
        name, colon, value = line.decode("utf-8").partition(": ")
        if not colon:
            raise PackError(f"malformed WARC header line {line!r}")
        headers[name] = value
    try:
        length = int(headers["Content-Length"])
    except (KeyError, ValueError) as error:
        raise PackError("no usable Content-Length") from error
    block = rest[:length]
    if len(block) != length or rest[length:] != _CRLF + _CRLF:
        raise PackError("record block does not have its declared length")
    if headers.get("WARC-Block-Digest") != f"sha256:{sha256_bytes(block)}":
        raise PackError("record block does not match its digest")
    return headers, block


def _body_of(block: bytes) -> bytes:
    head, separator, body = block.partition(_CRLF + _CRLF)
    if not separator or not head.startswith(b"HTTP/"):
        raise PackError("response record holds no HTTP message")
    return body


def scan(path: Path, expected_pack_id: str) -> list[PackEntry]:
    """Read a pack end to end and return its fetches, checking everything that can be checked:
    the leading ``warcinfo``, every block digest, every fetch record, every body against the
    digest its fetch record states. An incomplete trailing fetch raises :class:`PackTornTail`.
    """
    entries: list[PackEntry] = []
    seen: set[str] = set()
    pending: _Member | None = None
    first = True
    members = _members(path)
    while True:
        try:
            member = next(members)
        except StopIteration:
            break
        except PackTornTail as torn:
            # A fetch is whole or absent: a response whose fetch record is torn goes with the tail.
            if pending is not None:
                raise PackTornTail(str(torn), pending.offset) from torn
            raise
        warc_type = member.headers.get("WARC-Type")
        if first:
            if warc_type != "warcinfo" or f"pack-id: {expected_pack_id}" not in member.block.decode("utf-8").split("\r\n"):
                raise PackError(f"{path.name}: does not start with the warcinfo record of {expected_pack_id}")
            first = False
            continue
        if warc_type == "response":
            if pending is not None:
                raise PackTornTail(f"{path.name}: response without its fetch record", pending.offset)
            pending = member
            continue
        if warc_type != "metadata":
            raise PackError(f"{path.name}: unexpected record type {warc_type!r} at offset {member.offset}")
        try:
            record = acquisition.validate_fetch_record(json.loads(member.block.decode("utf-8")))
        except (ValueError, acquisition.AcquisitionError) as error:
            raise PackError(f"{path.name}: unreadable fetch record at offset {member.offset}: {error}") from error
        fetch_id = record["fetch_id"]
        if fetch_id in seen:
            raise PackError(f"{path.name}: fetch {fetch_id} occurs twice")
        if member.headers.get("WARC-Record-ID") != f"<{_record_id(fetch_id, 'metadata')}>":
            raise PackError(f"{path.name}: record id does not name the fetch it holds ({fetch_id})")
        fetched = record["outcome"] == acquisition.OUTCOME_FETCHED
        if fetched != (pending is not None):
            raise PackError(f"{path.name}: fetch {fetch_id} and its response record do not fit together")
        if fetched:
            body = _body_of(pending.block)
            if (
                pending.headers.get("WARC-Record-ID") != f"<{_record_id(fetch_id, 'response')}>"
                or pending.headers.get("WARC-Payload-Digest") != f"sha256:{record['body_sha256']}"
                or sha256_bytes(body) != record["body_sha256"]
            ):
                raise PackError(f"{path.name}: the body stored for {fetch_id} is not the body it identifies")
        entries.append(
            PackEntry(
                fetch_id, record["request"]["requested_url"], record["outcome"],
                record["body_sha256"] if fetched else None,
                record["body_size_bytes"] if fetched else None,
                pending.offset if fetched else None, pending.length if fetched else None,
                member.offset, member.length,
            )
        )
        seen.add(fetch_id)
        pending = None
    if first:
        raise PackError(f"{path.name}: empty file, not a pack")
    if pending is not None:
        raise PackTornTail(f"{path.name}: the last fetch has no fetch record", pending.offset)
    return entries


def _read_member(path: Path, offset: int, length: int) -> _Member:
    with open(path, "rb") as handle:
        handle.seek(offset)
        data = handle.read(length)
    try:
        headers, block = _parse(gzip.decompress(data))
    except (OSError, EOFError, zlib.error, PackError) as error:
        raise PackError(f"{path.name}: no readable record at offset {offset}: {error}") from error
    return _Member(offset, length, headers, block)


def read_fetch_record(path: Path, entry: PackEntry) -> dict[str, Any]:
    """The fetch record an index entry points at — refused unless it is that fetch."""
    member = _read_member(path, entry.metadata_offset, entry.metadata_length)
    record = acquisition.validate_fetch_record(json.loads(member.block.decode("utf-8")))
    if member.headers.get("WARC-Type") != "metadata" or record["fetch_id"] != entry.fetch_id:
        raise PackError(f"{path.name}: the index entry of {entry.fetch_id} points at another record")
    return record


def read_body(path: Path, entry: PackEntry) -> bytes:
    """The exact body bytes of a fetch — refused unless they hash to the indexed digest."""
    if entry.response_offset is None:
        raise PackError(f"{entry.fetch_id} has no body ({entry.outcome})")
    member = _read_member(path, entry.response_offset, entry.response_length)
    body = _body_of(member.block)
    if (
        member.headers.get("WARC-Record-ID") != f"<{_record_id(entry.fetch_id, 'response')}>"
        or sha256_bytes(body) != entry.body_sha256
    ):
        raise PackError(f"{path.name}: the index entry of {entry.fetch_id} does not fit the bytes it addresses")
    return body


# --- writing --------------------------------------------------------------------------------------


def _paths(directory: Path, identifier: str) -> dict[str, Path]:
    if not is_pack_id(identifier):
        raise PackError(f"not a pack id: {identifier!r}")
    directory = Path(directory)
    return {
        "open": directory / f"{identifier}.warc.gz.open",
        "sealed": directory / f"{identifier}.warc.gz",
        "index": directory / f"{identifier}.index.jsonl",
        "manifest": directory / f"{identifier}.pack.json",
    }


class OpenPack:
    """A pack that is being appended to in the runtime workspace."""

    def __init__(self, directory: Path, identifier: str, *, opened_at: datetime) -> None:
        self.pack_id = identifier
        self.paths = _paths(directory, identifier)
        if self.paths["manifest"].exists() or self.paths["sealed"].exists():
            raise PackError(f"{identifier} is sealed; a sealed pack is never appended to")
        self.path = self.paths["open"]
        if self.path.exists():
            self._fetch_ids = {entry.fetch_id for entry in scan(self.path, identifier)}
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            match = _PACK_ID.fullmatch(identifier)
            info = "\r\n".join(
                [
                    f"software: coprepan {PACK_WRITER_VERSION}",
                    "format: WARC File Format 1.1",
                    f"pack-id: {identifier}",
                    f"outlet-id: {match.group('outlet')}",
                    f"utc-day: {match.group('day')}",
                    "",
                ]
            ).encode("utf-8")
            with open(self.path, "xb") as handle:
                handle.write(
                    _record("warcinfo", f"urn:coprepan:{identifier}:warcinfo", format_instant(opened_at), info,
                            "application/warc-fields")
                )
                handle.flush()
                os.fsync(handle.fileno())
            self._fetch_ids = set()

    def __contains__(self, fetch_id: str) -> bool:
        return fetch_id in self._fetch_ids

    def append(self, record: Mapping[str, Any], body: bytes | None) -> None:
        """Append one fetch — its records in a single write, flushed to disk before returning."""
        if record["fetch_id"] in self._fetch_ids:
            raise DuplicateFetch(f"{self.pack_id} already holds {record['fetch_id']}")
        if record["outlet_id"] != pack_outlet(self.pack_id):
            raise PackError(f"{record['fetch_id']} belongs to {record['outlet_id']}, not to {self.pack_id}")
        if utc_day_of(record["fetch_started_at"]) != _PACK_ID.fullmatch(self.pack_id).group("day"):
            raise PackError(f"{record['fetch_id']} did not start on the UTC day of {self.pack_id}")
        data = render_fetch(record, body)
        descriptor = os.open(self.path, os.O_WRONLY | os.O_APPEND | getattr(os, "O_BINARY", 0))
        try:
            os.write(descriptor, data)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self._fetch_ids.add(record["fetch_id"])


def quarantine_torn_tail(directory: Path, identifier: str) -> Path | None:
    """Recover an open pack whose last append was interrupted.

    The bytes from the first incomplete fetch onwards are moved to ``<name>.torn-<n>`` and the
    pack is cut back to its last complete fetch. Nothing is discarded. Runtime workspace only: a
    sealed pack is never touched. Returns the sidecar, or ``None`` when the pack was intact.
    """
    path = _paths(directory, identifier)["open"]
    try:
        scan(path, identifier)
        return None
    except PackTornTail as torn:
        offset = torn.offset
    data = path.read_bytes()
    number = 0
    while (sidecar := path.with_name(f"{path.name}.torn-{number}")).exists():
        number += 1
    with open(sidecar, "xb") as handle:
        handle.write(data[offset:])
        handle.flush()
        os.fsync(handle.fileno())
    with open(path, "r+b") as handle:
        handle.truncate(offset)
        handle.flush()
        os.fsync(handle.fileno())
    return sidecar


def seal(directory: Path, identifier: str, *, sealed_at: datetime) -> dict[str, Any]:
    """Seal a pack: verify every record, fix its name, derive the index, write the manifest.

    Idempotent: sealing a sealed pack re-verifies it against its manifest and returns the manifest.
    A crash between the steps is completed by calling ``seal`` again.
    """
    paths = _paths(directory, identifier)
    if paths["manifest"].exists():
        return verify_sealed(directory, identifier)
    if paths["open"].exists():
        if paths["sealed"].exists():
            raise PackError(f"{identifier}: both an open and a sealed file exist")
        entries = scan(paths["open"], identifier)
        os.replace(paths["open"], paths["sealed"])
    elif paths["sealed"].exists():
        entries = scan(paths["sealed"], identifier)
    else:
        raise PackError(f"{identifier}: no pack to seal")

    index = b"".join(line_json(entry.as_row(identifier)) for entry in entries)
    write_bytes_atomic(paths["index"], index)
    sha256, size = sha256_file(paths["sealed"])
    match = _PACK_ID.fullmatch(identifier)
    manifest = {
        "schema": PACK_MANIFEST_SCHEMA,
        "pack_id": identifier,
        "outlet_id": match.group("outlet"),
        "utc_day": match.group("day"),
        "container": "WARC/1.1, one gzip member per record",
        "writer": PACK_WRITER_VERSION,
        "pack_sha256": sha256,
        "pack_size_bytes": size,
        "index_sha256": sha256_bytes(index),
        "fetch_count": len(entries),
        "fetched_count": sum(1 for entry in entries if entry.body_sha256 is not None),
        "sealed_at": format_instant(sealed_at),
    }
    write_bytes_atomic(paths["manifest"], record_json(manifest))
    return manifest


def read_index(directory: Path, identifier: str) -> list[PackEntry]:
    """The stored index of a sealed pack — refused unless the manifest binds it to the pack."""
    paths = _paths(directory, identifier)
    manifest = _manifest(paths, identifier)
    data = paths["index"].read_bytes()
    if sha256_bytes(data) != manifest["index_sha256"]:
        raise PackError(f"{identifier}: the index is not the one its manifest names")
    entries = []
    for line in data.split(b"\n")[:-1]:
        row = json.loads(line.decode("utf-8"))
        if row.pop("schema") != PACK_INDEX_SCHEMA or row.pop("pack_id") != identifier:
            raise PackError(f"{identifier}: foreign row in the index")
        entries.append(PackEntry(**row))
    return entries


def _manifest(paths: Mapping[str, Path], identifier: str) -> dict[str, Any]:
    try:
        manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
        if manifest["schema"] != PACK_MANIFEST_SCHEMA or manifest["pack_id"] != identifier:
            raise ValueError("schema or pack id")
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise PackError(f"{identifier}: no readable pack manifest: {error}") from error
    return manifest


def verify_sealed(directory: Path, identifier: str) -> dict[str, Any]:
    """Fixity check of a sealed pack: pack hash, index hash, and the index against a fresh scan."""
    paths = _paths(directory, identifier)
    manifest = _manifest(paths, identifier)
    sha256, size = sha256_file(paths["sealed"])
    if (sha256, size) != (manifest["pack_sha256"], manifest["pack_size_bytes"]):
        raise PackError(f"{identifier}: the sealed pack does not match its manifest")
    if read_index(directory, identifier) != scan(paths["sealed"], identifier):
        raise PackError(f"{identifier}: the index does not fit the pack")
    return manifest
