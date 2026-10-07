"""Acquisition contracts: the acquisition run and the fetch record (decision CPD-0005).

This module defines *what is recorded* about a run and about one retrieval. It contains no
network code. The only kind of run that exists is ``recorded_replay``: exchanges that were
recorded elsewhere (today: test fixtures) are turned into fetch records. A live fetcher is a
Phase-2 deliverable behind the open acquisition gates (``docs/STATUS.md`` §5).

Fetch record: ``docs/storage/INDEX.md`` §2. The body is identified by the SHA-256 of the stored
payload bytes; the record never contains the body itself.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import naming
from .canonical import canonical_json, record_json, require_sha256, sha256_bytes
from .identity import IdentityError, _require_url_text, fetch_id, format_instant, is_channel_id

RUN_SCHEMA = naming.schema_id("acquisition-run", 1)
RUN_RESULT_SCHEMA = naming.schema_id("acquisition-run-result", 1)
FETCH_RECORD_SCHEMA = naming.schema_id("fetch-record", 1)
RUN_ID_PREFIX = "acq1"

RUN_KIND_RECORDED_REPLAY = "recorded_replay"
RUN_KIND_HTTP_FETCH = "http_fetch"
RUN_KINDS = (RUN_KIND_RECORDED_REPLAY, RUN_KIND_HTTP_FETCH)
RUN_STATUSES = ("COMPLETED", "FAILED")

OUTCOME_FETCHED = "FETCHED"
OUTCOME_FETCH_FAILED = "FETCH_FAILED"
OUTCOMES = (OUTCOME_FETCHED, OUTCOME_FETCH_FAILED)
FAILURE_REASONS = (
    "timeout", "connection_error", "incomplete_response", "malformed_response",
    "body_limit_exceeded", "redirect_limit_exceeded", "unknown",
)

# What a fetch was for (CPD-0006 §1). Only an `item` can become a document; a channel document is
# the evidence of discovery and a robots file the evidence of a policy decision.
FETCH_KIND_ITEM = "item"
FETCH_KIND_CHANNEL_DOCUMENT = "channel_document"
FETCH_KIND_ROBOTS = "robots_txt"
FETCH_KINDS = (FETCH_KIND_ITEM, FETCH_KIND_CHANNEL_DOCUMENT, FETCH_KIND_ROBOTS)
POLICY_FIELDS = (
    "policy_decision", "policy_version", "robots_decision", "robots_txt_sha256",
    "access_class_observed", "crawler_version", "user_agent",
)

NOT_APPLICABLE = "not_applicable"
UNKNOWN = "unknown"

_RUN_ID = re.compile(rf"{RUN_ID_PREFIX}-\d{{8}}T\d{{12}}Z-[0-9a-f]{{12}}")
_HEADER_NAME = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
_METHOD = re.compile(r"[A-Z]+")


class AcquisitionError(ValueError):
    """An acquisition record cannot be built from what was given."""


class RunStateError(RuntimeError):
    """A run record exists in a state that forbids the requested step."""


# --- run ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class AcquisitionRun:
    """The identity and the declared context of one acquisition run.

    Identity covers what was *asked*: kind, start instant, outlets, discovery method, software
    version and configuration. What *happened* is the run result, written when the run ends.
    """

    kind: str
    started_at: datetime
    outlet_ids: tuple[str, ...]
    discovery_method: str
    software_version: str
    component_versions: Mapping[str, str]
    configuration: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.kind not in RUN_KINDS:
            raise AcquisitionError(f"not a run kind: {self.kind!r} (known: {RUN_KINDS})")
        if not self.outlet_ids or list(self.outlet_ids) != sorted(set(self.outlet_ids)):
            raise AcquisitionError("outlet_ids is a non-empty, sorted tuple of distinct ids")
        for outlet in self.outlet_ids:
            if not naming.is_outlet_id(outlet):
                raise AcquisitionError(f"not an outlet_id: {outlet!r}")
        for name in ("discovery_method", "software_version"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise AcquisitionError(f"{name} is a non-empty string")
        format_instant(self.started_at)
        try:
            canonical_json(dict(self.configuration))
            canonical_json(dict(self.component_versions))
        except (TypeError, ValueError) as error:
            raise AcquisitionError(f"configuration is not canonical JSON: {error}") from error

    @property
    def configuration_sha256(self) -> str:
        return sha256_bytes(canonical_json(dict(self.configuration)))

    @property
    def run_id(self) -> str:
        """``acq1-<UTC start, compact>-<hash12>``: sortable by time, usable as a file name."""
        preimage = canonical_json(
            {
                "schema": RUN_SCHEMA,
                "kind": self.kind,
                "started_at": format_instant(self.started_at),
                "outlet_ids": list(self.outlet_ids),
                "discovery_method": self.discovery_method,
                "software_version": self.software_version,
                "component_versions": dict(self.component_versions),
                "configuration_sha256": self.configuration_sha256,
            }
        )
        stamp = format_instant(self.started_at).replace("-", "").replace(":", "").replace(".", "")
        return f"{RUN_ID_PREFIX}-{stamp}-{sha256_bytes(preimage)[:12]}"

    def as_record(self) -> dict[str, Any]:
        return {
            "schema": RUN_SCHEMA,
            "run_id": self.run_id,
            "kind": self.kind,
            "started_at": format_instant(self.started_at),
            "outlet_ids": list(self.outlet_ids),
            "discovery_method": self.discovery_method,
            "software_version": self.software_version,
            "component_versions": dict(self.component_versions),
            "configuration": dict(self.configuration),
            "configuration_sha256": self.configuration_sha256,
        }


def is_run_id(value: object) -> bool:
    return isinstance(value, str) and _RUN_ID.fullmatch(value) is not None


def run_directory(workspace: Path, run_id: str) -> Path:
    if not is_run_id(run_id):
        raise AcquisitionError(f"not a run id: {run_id!r}")
    return Path(workspace) / "runs" / run_id


def open_run(workspace: Path, run: AcquisitionRun) -> bool:
    """Record that a run has started. Returns ``False`` when it was already open (a resume).

    A run that already has a result is finished and cannot be opened again.
    """
    directory = run_directory(workspace, run.run_id)
    if (directory / "result.json").exists():
        raise RunStateError(f"{run.run_id} is finished; a new run needs a new start instant")
    record = record_json(run.as_record())
    path = directory / "run.json"
    if path.exists():
        if path.read_bytes() != record:
            raise RunStateError(f"{run.run_id}: the stored run record differs from the one offered")
        return False
    directory.mkdir(parents=True, exist_ok=True)
    with open(path, "xb") as handle:
        handle.write(record)
    return True


def close_run(
    workspace: Path,
    run: AcquisitionRun,
    *,
    finished_at: datetime,
    status: str,
    counts: Mapping[str, int],
    pack_ids: Sequence[str],
    errors: Sequence[str] = (),
) -> dict[str, Any]:
    """Write the result of a run, once."""
    if status not in RUN_STATUSES:
        raise AcquisitionError(f"not a run status: {status!r}")
    directory = run_directory(workspace, run.run_id)
    if not (directory / "run.json").exists():
        raise RunStateError(f"{run.run_id} was never opened")
    result = {
        "schema": RUN_RESULT_SCHEMA,
        "run_id": run.run_id,
        "finished_at": format_instant(finished_at),
        "status": status,
        "counts": dict(counts),
        "pack_ids": list(pack_ids),
        "errors": list(errors),
    }
    try:
        with open(directory / "result.json", "xb") as handle:
            handle.write(record_json(result))
    except FileExistsError as error:
        raise RunStateError(f"{run.run_id} already has a result") from error
    return result


def unfinished_runs(workspace: Path) -> list[str]:
    """Runs that were opened and have no result: interrupted, or still running."""
    runs = Path(workspace) / "runs"
    if not runs.is_dir():
        return []
    return sorted(
        path.name for path in runs.iterdir() if (path / "run.json").exists() and not (path / "result.json").exists()
    )


def read_run_result(workspace: Path, run_id: str) -> dict[str, Any] | None:
    path = run_directory(workspace, run_id) / "result.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


# --- fetch record ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class RecordedExchange:
    """One request and what came back, as recorded. ``body`` is ``None`` when nothing came back."""

    requested_url: str
    fetch_started_at: datetime
    fetch_finished_at: datetime
    status: int | None = None
    response_headers: tuple[tuple[str, str], ...] = ()
    body: bytes | None = None
    final_url: str | None = None
    redirect_chain: tuple[str, ...] = ()
    method: str = "GET"
    request_headers: tuple[tuple[str, str], ...] = ()
    channel_id: str | None = None
    failure_reason: str | None = None
    policy: Mapping[str, str] = field(default_factory=dict)
    fetch_kind: str = FETCH_KIND_ITEM
    request_id: str | None = None
    attempt_number: int = 1
    failure_detail: str | None = None
    redirect_not_followed: str | None = None


def build_fetch_record(run: AcquisitionRun, outlet_id: str, exchange: RecordedExchange) -> dict[str, Any]:
    """The fetch record of one exchange. Refuses an exchange that is not internally consistent."""
    if outlet_id not in run.outlet_ids:
        raise AcquisitionError(f"{outlet_id} is not an outlet of run {run.run_id}")
    if not isinstance(exchange.method, str) or _METHOD.fullmatch(exchange.method) is None:
        raise AcquisitionError(f"not an HTTP method: {exchange.method!r}")
    started = format_instant(exchange.fetch_started_at)
    finished = format_instant(exchange.fetch_finished_at)
    if exchange.fetch_finished_at < exchange.fetch_started_at:
        raise AcquisitionError("a fetch cannot finish before it starts")
    if exchange.channel_id is not None and not is_channel_id(exchange.channel_id):
        raise AcquisitionError(f"not a channel_id: {exchange.channel_id!r}")
    if exchange.fetch_kind not in FETCH_KINDS:
        raise AcquisitionError(f"not a fetch kind: {exchange.fetch_kind!r} (known: {FETCH_KINDS})")
    if isinstance(exchange.attempt_number, bool) or not isinstance(exchange.attempt_number, int) or exchange.attempt_number < 1:
        raise AcquisitionError(f"attempt_number is a positive integer: {exchange.attempt_number!r}")
    try:
        _require_url_text(exchange.requested_url, "requested_url")
        for url in (*exchange.redirect_chain, *([exchange.final_url] if exchange.final_url else [])):
            _require_url_text(url, "redirect or final URL")
    except IdentityError as error:
        raise AcquisitionError(str(error)) from error

    fetched = exchange.body is not None
    if fetched:
        if not isinstance(exchange.body, bytes):
            raise AcquisitionError("a body is bytes")
        if isinstance(exchange.status, bool) or not isinstance(exchange.status, int) or not 100 <= exchange.status <= 599:
            raise AcquisitionError(f"a response has an HTTP status: {exchange.status!r}")
        if exchange.failure_reason is not None:
            raise AcquisitionError("an exchange with a body has no failure reason")
        body_sha256 = sha256_bytes(exchange.body)
    else:
        if exchange.failure_reason not in FAILURE_REASONS:
            raise AcquisitionError(f"an exchange without a body names a failure reason of {FAILURE_REASONS}")
        if exchange.status is not None or exchange.response_headers:
            raise AcquisitionError("an exchange without a body carries no status and no response headers")
        # No bytes came back: the event is identified over the hash of the empty byte string.
        body_sha256 = sha256_bytes(b"")

    record = {
        "schema": FETCH_RECORD_SCHEMA,
        "fetch_id": fetch_id(exchange.requested_url, exchange.fetch_started_at, body_sha256),
        "run_id": run.run_id,
        "outlet_id": outlet_id,
        "fetch_kind": exchange.fetch_kind,
        "request_id": exchange.request_id or NOT_APPLICABLE,
        "attempt_number": exchange.attempt_number,
        "outcome": OUTCOME_FETCHED if fetched else OUTCOME_FETCH_FAILED,
        "failure_reason": exchange.failure_reason if not fetched else NOT_APPLICABLE,
        "failure_detail": (exchange.failure_detail or UNKNOWN) if not fetched else NOT_APPLICABLE,
        "request": {
            "method": exchange.method,
            "requested_url": exchange.requested_url,
            "headers": _headers(exchange.request_headers),
        },
        "response": {
            "status": exchange.status if fetched else NOT_APPLICABLE,
            "final_url": (exchange.final_url or exchange.requested_url) if fetched else NOT_APPLICABLE,
            "redirect_chain": list(exchange.redirect_chain),
            "redirect_not_followed": exchange.redirect_not_followed or NOT_APPLICABLE,
            "headers": _headers(exchange.response_headers),
            "content_type": _content_type(exchange.response_headers) if fetched else NOT_APPLICABLE,
            "content_encoding": content_encoding_of(exchange.response_headers) if fetched else NOT_APPLICABLE,
        },
        "fetch_started_at": started,
        "fetch_finished_at": finished,
        "body_sha256": body_sha256 if fetched else NOT_APPLICABLE,
        "body_size_bytes": len(exchange.body) if fetched else NOT_APPLICABLE,
        "discovery": {"channel_id": exchange.channel_id or UNKNOWN},
        "policy": _policy(run, exchange.policy),
    }
    canonical_json(record)
    return record


def validate_fetch_record(record: Any) -> dict[str, Any]:
    """Check the shape of a stored fetch record and that its id covers what it claims."""
    try:
        if record["schema"] != FETCH_RECORD_SCHEMA or record["outcome"] not in OUTCOMES:
            raise ValueError("schema or outcome")
        fetched = record["outcome"] == OUTCOME_FETCHED
        body_sha256 = require_sha256(record["body_sha256"], "body_sha256") if fetched else sha256_bytes(b"")
        started = datetime.strptime(record["fetch_started_at"], "%Y-%m-%dT%H:%M:%S.%f%z")
        if fetch_id(record["request"]["requested_url"], started, body_sha256) != record["fetch_id"]:
            raise ValueError("fetch_id does not cover the record's URL, start instant and body hash")
        if not naming.is_outlet_id(record["outlet_id"]) or not is_run_id(record["run_id"]):
            raise ValueError("outlet_id or run_id")
        if record["fetch_kind"] not in FETCH_KINDS:
            raise ValueError("fetch_kind")
    except (KeyError, TypeError, ValueError) as error:
        raise AcquisitionError(f"not a valid fetch record: {error}") from error
    return record


def _headers(headers: Sequence[tuple[str, str]]) -> list[list[str]]:
    """Headers as an ordered list of pairs: order and repetition are part of what was received."""
    out = []
    for pair in headers:
        if len(pair) != 2:
            raise AcquisitionError(f"a header is a (name, value) pair: {pair!r}")
        name, value = pair
        if not isinstance(name, str) or _HEADER_NAME.fullmatch(name) is None:
            raise AcquisitionError(f"not a header name: {name!r}")
        if not isinstance(value, str) or "\r" in value or "\n" in value:
            raise AcquisitionError(f"header {name}: value contains a line break")
        out.append([name, value])
    return out


def _content_type(headers: Sequence[tuple[str, str]]) -> str:
    """The media type as sent, lower-cased, without parameters; ``unknown`` when not sent."""
    for name, value in headers:
        if name.lower() == "content-type":
            return value.split(";", 1)[0].strip().lower() or UNKNOWN
    return UNKNOWN


def content_encoding_of(headers: Sequence[tuple[str, str]]) -> str:
    """The content coding the server declared, lower-cased; ``identity`` when it declared none.

    The stored body is the HTTP payload **with its content coding intact** (and any transfer
    coding removed): what ``body_sha256`` covers is what the server sent as the representation.
    Decoding is a recorded step of the stages that read the body (CPD-0006 §1).
    """
    for name, value in headers:
        if name.lower() == "content-encoding":
            return ",".join(part.strip().lower() for part in value.split(",") if part.strip()) or "identity"
    return "identity"


def _policy(run: AcquisitionRun, policy: Mapping[str, str]) -> dict[str, str]:
    """The policy context of a fetch. A replay consulted no robots.txt and applied no policy: the
    fields say so explicitly instead of being absent. An HTTP fetch must state every field: a
    request that went out without a recorded policy decision is a defect, not a default.
    """
    unknown = set(policy) - set(POLICY_FIELDS)
    if unknown:
        raise AcquisitionError(f"unknown policy field(s): {sorted(unknown)}")
    if run.kind == RUN_KIND_RECORDED_REPLAY:
        return {name: policy.get(name, NOT_APPLICABLE) for name in POLICY_FIELDS}
    missing = [name for name in POLICY_FIELDS if not policy.get(name)]
    if missing:
        raise AcquisitionError(f"an HTTP fetch records its policy context; missing: {missing}")
    if policy["policy_decision"] != "ALLOW":
        raise AcquisitionError("a fetch record exists only for a request the policy allowed")
    return {name: policy[name] for name in POLICY_FIELDS}
