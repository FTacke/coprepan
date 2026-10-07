"""State-machine and ledger primitives.

Rules implemented (``docs/architecture/TARGET_ARCHITECTURE.md`` §2, ``docs/storage/INDEX.md`` §4):

* states are named tokens of a declared machine, never free text;
* an illegal transition raises;
* **ledger before state**: the only way to change a subject's state is to append a transition
  record, and the state is what replaying the ledger yields. There is no second copy of the state
  that could run ahead of the ledger.

The ledger is a line-oriented file (one JSON object per line, appended and flushed to disk before
the call returns). It has one writer at a time; cross-process locking is not provided here.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

from . import naming
from .canonical import line_json, sha256_bytes
from .identity import format_instant
from .jsonl import ConcurrentAppend, TornTail, append_line

# v2 (2026-10-08, CPD-0009 §5): every record names the SHA-256 of the record before it. No v1
# ledger of corpus material exists; a v1 file is refused, not read as v2.
LEDGER_RECORD_SCHEMA = naming.schema_id("ledger-record", 2)

_STATE_TOKEN = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*")


class StateMachineError(ValueError):
    """A machine is declared inconsistently, or a state is not one of its tokens."""


class IllegalTransition(RuntimeError):
    """The requested transition is not declared by the machine."""


class LedgerError(RuntimeError):
    """The ledger file cannot be trusted or cannot be appended to."""


class LedgerTornTail(LedgerError):
    """The file ends in an incomplete line: a write was interrupted."""


@dataclass(frozen=True)
class StateMachine:
    """A closed vocabulary of states and the transitions between them."""

    name: str
    initial: str
    transitions: Mapping[str, frozenset[str]]

    def __post_init__(self) -> None:
        states = set(self.transitions)
        for state in states | {target for targets in self.transitions.values() for target in targets}:
            if not isinstance(state, str) or _STATE_TOKEN.fullmatch(state) is None:
                raise StateMachineError(f"{self.name}: not an upper-case state token: {state!r}")
        undeclared = {t for targets in self.transitions.values() for t in targets} - states
        if undeclared:
            raise StateMachineError(f"{self.name}: transition into undeclared state(s) {sorted(undeclared)}")
        if self.initial not in states:
            raise StateMachineError(f"{self.name}: initial state {self.initial!r} is not declared")

    @property
    def states(self) -> tuple[str, ...]:
        return tuple(self.transitions)

    def is_terminal(self, state: str) -> bool:
        self.require_state(state)
        return not self.transitions[state]

    def require_state(self, state: str) -> None:
        if state not in self.transitions:
            raise StateMachineError(f"{self.name}: unknown state {state!r}")

    def check(self, current: str | None, target: str) -> None:
        """Raise unless ``current → target`` is declared. ``None`` means "no record yet"."""
        self.require_state(target)
        if current is None:
            if target != self.initial:
                raise IllegalTransition(f"{self.name}: a subject starts in {self.initial}, not {target}")
            return
        self.require_state(current)
        if target not in self.transitions[current]:
            raise IllegalTransition(f"{self.name}: {current} → {target} is not a declared transition")


def machine(name: str, initial: str, transitions: Mapping[str, tuple[str, ...]]) -> StateMachine:
    return StateMachine(name, initial, {state: frozenset(targets) for state, targets in transitions.items()})


# The preservation state machine of docs/storage/INDEX.md §4. The three side states branch off
# FETCH_PLANNED as drawn there. FETCH_FAILED → FETCH_PLANNED is the retry that `retry_at` and "a
# failed fetch is never a permanent blacklist" imply; it is the one edge not drawn in the diagram.
PRESERVATION = machine(
    "preservation",
    "DISCOVERED",
    {
        "DISCOVERED": ("FETCH_PLANNED",),
        "FETCH_PLANNED": ("FETCHED", "FETCH_FAILED", "REFUSED_BY_POLICY", "QUARANTINED"),
        "FETCHED": ("RAW_VERIFIED",),
        "RAW_VERIFIED": ("PRESERVATION_PENDING",),
        "PRESERVATION_PENDING": ("RAW_PRESERVED",),
        "RAW_PRESERVED": (),
        "FETCH_FAILED": ("FETCH_PLANNED",),
        "REFUSED_BY_POLICY": (),
        "QUARANTINED": (),
    },
)


@dataclass(frozen=True)
class LedgerRecord:
    seq: int
    subject: str
    previous_state: str | None
    new_state: str
    at: str
    details: Mapping[str, Any]
    previous_record_sha256: str | None = None

    def as_row(self, machine_name: str) -> dict[str, Any]:
        return {
            "schema": LEDGER_RECORD_SCHEMA,
            "machine": machine_name,
            "seq": self.seq,
            "subject": self.subject,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "at": self.at,
            "details": dict(self.details),
            "previous_record_sha256": self.previous_record_sha256,
        }


class Ledger:
    """An append-only transition ledger for one state machine.

    Opening replays the file and checks every record against the machine, so a ledger that was
    edited, reordered or truncated in the middle is refused rather than believed.
    """

    def __init__(self, path: Path, state_machine: StateMachine) -> None:
        self.path = Path(path)
        self.machine = state_machine
        self._states: dict[str, str] = {}
        self._next_seq = 0
        self._size = 0
        self._chain: str | None = None   # SHA-256 of the last record's line; what the next record must name
        for record in self._read():
            self._apply(record)

    # -- reading -------------------------------------------------------------------------------

    def _read(self) -> Iterator[LedgerRecord]:
        if not self.path.exists():
            self._size = 0
            return
        data = self.path.read_bytes()
        self._size = len(data)
        if data and not data.endswith(b"\n"):
            complete = data.rfind(b"\n") + 1
            raise LedgerTornTail(
                f"{self.path.name}: {len(data) - complete} byte(s) after the last complete record; "
                "call quarantine_torn_tail() before appending"
            )
        chain: str | None = None
        for number, line in enumerate(data.split(b"\n")[:-1], 1):
            try:
                row = json.loads(line.decode("utf-8"))
                if row["schema"] != LEDGER_RECORD_SCHEMA or row["machine"] != self.machine.name:
                    raise ValueError(f"schema/machine {row['schema']!r}/{row['machine']!r}")
                # The chain: a record that was changed, removed or moved no longer has the hash
                # the record after it names. (The last record has no successor to vouch for it.)
                if row["previous_record_sha256"] != chain:
                    raise ValueError("it does not follow the record before it: an earlier record was changed, removed or moved")
                yield LedgerRecord(
                    row["seq"], row["subject"], row["previous_state"], row["new_state"], row["at"], row["details"], chain
                )
            except (ValueError, KeyError, TypeError) as error:
                raise LedgerError(f"{self.path.name}: line {number} is not a ledger record: {error}") from error
            chain = sha256_bytes(line + b"\n")
            self._chain = chain

    def _apply(self, record: LedgerRecord) -> None:
        if record.seq != self._next_seq:
            raise LedgerError(f"{self.path.name}: expected seq {self._next_seq}, found {record.seq}")
        current = self._states.get(record.subject)
        if record.previous_state != current:
            raise LedgerError(
                f"{self.path.name}: seq {record.seq} claims {record.subject} was "
                f"{record.previous_state}, the ledger says {current}"
            )
        try:
            self.machine.check(current, record.new_state)
        except (IllegalTransition, StateMachineError) as error:
            raise LedgerError(f"{self.path.name}: seq {record.seq} records an illegal transition: {error}") from error
        self._states[record.subject] = record.new_state
        self._next_seq += 1

    def state(self, subject: str) -> str | None:
        """The current state of a subject, or ``None`` if the ledger has never seen it."""
        return self._states.get(subject)

    def states(self) -> dict[str, str]:
        return dict(self._states)

    def records(self) -> list[LedgerRecord]:
        size, chain = self._size, self._chain
        try:
            return list(self._read())
        finally:
            self._size, self._chain = size, chain  # reading again does not move where this ledger appends

    def __len__(self) -> int:
        return self._next_seq

    # -- writing -------------------------------------------------------------------------------

    def transition(
        self,
        subject: str,
        new_state: str,
        *,
        at: datetime | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> LedgerRecord:
        """Check the transition, append its record durably, and only then change the state."""
        if not isinstance(subject, str) or not subject:
            raise LedgerError(f"a ledger subject is a non-empty string: {subject!r}")
        current = self._states.get(subject)
        self.machine.check(current, new_state)
        record = LedgerRecord(
            self._next_seq,
            subject,
            current,
            new_state,
            format_instant(at if at is not None else datetime.now(timezone.utc)),
            dict(details or {}),
            self._chain,
        )
        line = line_json(record.as_row(self.machine.name))
        self._append(line)
        self._chain = sha256_bytes(line)
        self._apply(record)
        return record

    def _append(self, line: bytes) -> None:
        """Append durably. The record must stand exactly where this ledger expects the file to end:
        a ledger that grew behind this object's back has another writer, and is refused.
        """
        try:
            append_line(self.path, line, expected_size=self._size)
        except TornTail as error:
            raise LedgerTornTail(str(error)) from error
        except ConcurrentAppend as error:
            raise LedgerError(str(error)) from error
        self._size += len(line)


def quarantine_torn_tail(path: Path) -> Path | None:
    """Recover a ledger whose last write was interrupted.

    The bytes after the last complete record are moved to a sibling ``<name>.torn-<n>`` file and
    the ledger is cut back to its last complete record. Nothing is discarded: the torn bytes stay
    on disk as evidence. Returns the sidecar path, or ``None`` when the ledger was intact.
    """
    path = Path(path)
    data = path.read_bytes()
    if not data or data.endswith(b"\n"):
        return None
    complete = data.rfind(b"\n") + 1
    number = 0
    while (sidecar := path.with_name(f"{path.name}.torn-{number}")).exists():
        number += 1
    with open(sidecar, "xb") as handle:
        handle.write(data[complete:])
        handle.flush()
        os.fsync(handle.fileno())
    with open(path, "r+b") as handle:
        handle.truncate(complete)
        handle.flush()
        os.fsync(handle.fileno())
    return sidecar
