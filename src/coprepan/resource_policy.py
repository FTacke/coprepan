"""How much shared I/O CO.PRE.PAN may use, and when it yields (decision CPD-0033).

CO.PRE.PAN shares three things with the far more data-intensive CO.RA.PAN on this workstation: the institutional
share (one server, one namespace, in practice one Windows account), the external ``D:`` device that holds both
projects' backups, and the ``C:`` umbrella of workspaces and spools. CO.RA.PAN has priority on all three. This module
is the one place where CO.PRE.PAN's side of that is decided in code; it builds no orchestration platform.

* **The policy** (``config/resource_policy.json``): limits for backup and fixity, free-space floors per role, the
  bounds of honest pending preservation, the share back-off, and quiet windows in which no CO.PRE.PAN maintenance
  starts or continues. Tracked, versioned, no path.
* **The share gate** (:class:`ShareGate`): a persisted back-off in front of every resolution of the PRESERVATION root.
  After a failed contact nothing in CO.PRE.PAN touches the share again before the back-off ends -- no logon attempt, no
  probe, no retry per pack. A process restart reads the same state (``<RUNTIME>/state/share_gate.json``).
* **The sibling advisory** (:func:`sibling_advisory`): CO.RA.PAN's own observation of the share, read from a file the
  workstation names in ``COPREPAN_SIBLING_PRESERVATION_STATE`` (``.env``). The file is **not** a declared interface of
  CO.RA.PAN, so it is used in one direction only: a fresh observation that the share is degraded or slow makes
  CO.PRE.PAN wait or yield; **no observation, a stale one, an unreadable one or a normal one never permits anything**
  that the policy does not permit by itself. Missing information is never read as idle.
* **The pause file** ``<RUNTIME>/state/PAUSE_IO``: an operator (or a later tool) can make every CO.PRE.PAN process
  stop new shared I/O at its next decision point, without killing anything; deleting the file resumes.
* **Free-space floors**: a role root whose volume has less free space than its floor gets no new CO.PRE.PAN bytes;
  CO.RA.PAN stops its own production when such a volume runs low, so CO.PRE.PAN stops first.

Nothing here touches the share: every decision is made from local files and the clock.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, time as dtime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import naming
from .canonical import record_json, write_bytes_atomic
from .storage_roots import StorageRootReadOnly, StorageRootUnreachable

SCHEMA = naming.schema_id("resource-policy", 1)
SHARE_STATE_SCHEMA = naming.schema_id("share-gate-state", 1)
STATE_DIRECTORY = "state"
SHARE_STATE_FILE = "share_gate.json"
PAUSE_FILE = "PAUSE_IO"
SIBLING_SIGNAL_VARIABLE = "COPREPAN_SIBLING_PRESERVATION_STATE"
SIBLING_SCHEMA = "corapan-preservation-mode/v1"
GIB = 1024 ** 3
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# sibling advisory states
NO_SIGNAL, STALE, UNREADABLE, UNRECOGNISED = "NO_SIGNAL", "STALE", "UNREADABLE", "UNRECOGNISED"
SHARE_DEGRADED, SHARE_SLOW, SHARE_NORMAL = "SHARE_DEGRADED", "SHARE_SLOW", "SHARE_NORMAL"
CAUTION = (SHARE_DEGRADED, SHARE_SLOW)


class ResourcePolicyError(ValueError):
    """The resource policy file is not a policy this code understands."""


@dataclass(frozen=True)
class QuietWindow:
    days: tuple[str, ...]
    start: dtime
    end: dtime
    why: str

    def covers(self, local: datetime) -> bool:
        day = DAYS[local.weekday()]
        moment = local.time().replace(tzinfo=None)
        if self.start <= self.end:
            return day in self.days and self.start <= moment < self.end
        # a window across midnight belongs to the day it starts on
        previous = DAYS[(local.weekday() - 1) % 7]
        return (day in self.days and moment >= self.start) or (previous in self.days and moment < self.end)


@dataclass(frozen=True)
class ResourcePolicy:
    version: str
    backoff_initial_seconds: int
    backoff_factor: int
    backoff_max_seconds: int
    sibling_signal_max_age_seconds: int
    free_space_floor_bytes: Mapping[str, int]
    pending_max_packs: int
    pending_max_bytes: int
    pending_max_age_hours: int
    backup: Mapping[str, int]
    windows: tuple[QuietWindow, ...] = field(default_factory=tuple)

    def quiet_window(self, now: datetime) -> str | None:
        """Why no maintenance may run now (the first covering window), or ``None``. Windows are in local time."""
        local = now.astimezone()
        for window in self.windows:
            if window.covers(local):
                return f"quiet window {','.join(window.days)} {window.start:%H:%M}-{window.end:%H:%M}: {window.why}"
        return None

    def as_record(self) -> dict[str, Any]:
        return {"version": self.version, "backoff_initial_seconds": self.backoff_initial_seconds, "backoff_factor": self.backoff_factor,
                "backoff_max_seconds": self.backoff_max_seconds, "sibling_signal_max_age_seconds": self.sibling_signal_max_age_seconds,
                "free_space_floor_bytes": dict(self.free_space_floor_bytes), "pending": {"max_packs": self.pending_max_packs,
                "max_bytes": self.pending_max_bytes, "max_age_hours": self.pending_max_age_hours}, "backup": dict(self.backup),
                "windows": [{"days": list(w.days), "from": f"{w.start:%H:%M}", "to": f"{w.end:%H:%M}", "why": w.why} for w in self.windows]}


_BACKUP_KEYS = ("workers", "max_bytes_per_second", "max_minutes", "fixity_objects_per_run", "fixity_bytes_per_run", "fixity_cycle_max_days",
                "restore_samples", "receipt_warning_hours", "receipt_failure_hours")


def _count(value: Any, what: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ResourcePolicyError(f"{what} must be an integer >= {minimum}: {value!r}")
    return value


def _clock(text: Any, what: str) -> dtime:
    try:
        return datetime.strptime(str(text), "%H:%M").time()
    except ValueError as error:
        raise ResourcePolicyError(f"{what} is HH:MM: {text!r}") from error


def parse_policy(doc: Mapping[str, Any]) -> ResourcePolicy:
    """A policy document as this code reads it; anything else is refused, never defaulted."""
    if not isinstance(doc, Mapping) or doc.get("schema") != SCHEMA or doc.get("status") != "DECIDED":
        raise ResourcePolicyError(f"not a DECIDED {SCHEMA}")
    share, floors, pending, backup = (doc.get(k) for k in ("share", "free_space_floor_gib", "pending", "backup"))
    if not all(isinstance(x, Mapping) for x in (share, floors, pending, backup)):
        raise ResourcePolicyError("share, free_space_floor_gib, pending and backup are objects")
    if set(backup) != set(_BACKUP_KEYS):
        raise ResourcePolicyError(f"backup has exactly the keys {list(_BACKUP_KEYS)}")
    if set(floors) - {"RUNTIME", "SPOOL", "BACKUP"} or not floors:
        raise ResourcePolicyError("free-space floors are given for RUNTIME, SPOOL and BACKUP only")
    windows = []
    for number, w in enumerate(doc.get("maintenance_quiet_windows") or ()):
        days = tuple(w.get("days") or ())
        if not days or set(days) - set(DAYS):
            raise ResourcePolicyError(f"window {number}: days are {DAYS}")
        windows.append(QuietWindow(days, _clock(w.get("from"), f"window {number} from"), _clock(w.get("to"), f"window {number} to"), str(w.get("why") or "")))
    policy = ResourcePolicy(
        version=str(doc.get("version")),
        backoff_initial_seconds=_count(share.get("backoff_initial_seconds"), "share.backoff_initial_seconds", minimum=1),
        backoff_factor=_count(share.get("backoff_factor"), "share.backoff_factor", minimum=1),
        backoff_max_seconds=_count(share.get("backoff_max_seconds"), "share.backoff_max_seconds", minimum=1),
        sibling_signal_max_age_seconds=_count(share.get("sibling_signal_max_age_seconds"), "share.sibling_signal_max_age_seconds", minimum=1),
        free_space_floor_bytes={role: _count(value, f"floor {role}") * GIB for role, value in floors.items()},
        pending_max_packs=_count(pending.get("max_packs"), "pending.max_packs"),
        pending_max_bytes=_count(pending.get("max_bytes"), "pending.max_bytes"),
        pending_max_age_hours=_count(pending.get("max_age_hours"), "pending.max_age_hours"),
        backup={key: _count(backup[key], f"backup.{key}", minimum=0 if key.startswith("fixity") else 1) for key in _BACKUP_KEYS},
        windows=tuple(windows))
    if policy.backoff_max_seconds < policy.backoff_initial_seconds:
        raise ResourcePolicyError("the back-off maximum is at least its initial value")
    return policy


def load_policy(path: Path) -> ResourcePolicy:
    try:
        return parse_policy(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        if isinstance(error, ResourcePolicyError):
            raise
        raise ResourcePolicyError(f"{path}: {error}") from error


def default_policy_path(checkout: Path) -> Path:
    return Path(checkout) / "config" / "resource_policy.json"


# --- the pause file and free space ---------------------------------------------------------------------------


def pause_path(runtime: Path) -> Path:
    return Path(runtime) / STATE_DIRECTORY / PAUSE_FILE


def paused(runtime: Path | None) -> str | None:
    """Why CO.PRE.PAN must not start new shared I/O now (the operator's pause file), or ``None``."""
    if runtime is None:
        return None
    path = pause_path(runtime)
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8").strip()[:200]
    except OSError:
        text = ""
    return f"paused by {PAUSE_FILE}" + (f": {text}" if text else "")


def free_space_refusal(role: str, root: Path | None, policy: ResourcePolicy, *, usage: Callable[[Path], Any] | None = None) -> str | None:
    """Why no new CO.PRE.PAN bytes may go to ``root`` (its volume is under the role's floor), or ``None``.
    A volume whose free space cannot be read is a refusal too: never guessed."""
    floor = policy.free_space_floor_bytes.get(role)
    if floor is None or root is None:
        return None
    try:
        free = (usage or shutil.disk_usage)(Path(root)).free
    except OSError as error:
        return f"{role}: free space of the volume cannot be read ({type(error).__name__})"
    if free < floor:
        return f"{role}: {free / GIB:.1f} GiB free on the volume, the floor is {floor / GIB:.0f} GiB (CO.RA.PAN stops its own production when such a volume runs low)"
    return None


# --- the sibling advisory --------------------------------------------------------------------------------------


def _instant(text: Any) -> datetime | None:
    if not isinstance(text, str) or not text:
        return None
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def sibling_advisory(env: Mapping[str, str], now: datetime, *, max_age_seconds: int) -> dict[str, Any]:
    """CO.RA.PAN's latest observation of the share, as advice that can only make CO.PRE.PAN more careful.

    ``state``: ``NO_SIGNAL`` (not configured, or no file) · ``UNREADABLE`` · ``UNRECOGNISED`` (another schema) · ``STALE``
    (older than ``max_age_seconds``) · ``SHARE_DEGRADED`` (fresh: not reachable, or a degraded mode) · ``SHARE_SLOW`` ·
    ``SHARE_NORMAL``. Only the two of :data:`CAUTION` change behaviour; ``hold_until`` is the sibling's own next probe.
    """
    value = (env.get(SIBLING_SIGNAL_VARIABLE) or "").strip()
    if not value:
        return {"state": NO_SIGNAL, "detail": f"{SIBLING_SIGNAL_VARIABLE} is not set"}
    path = Path(value)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"state": NO_SIGNAL, "detail": "the sibling's state file does not exist"}
    except (OSError, ValueError) as error:
        return {"state": UNREADABLE, "detail": f"{type(error).__name__}"}
    if not isinstance(doc, Mapping) or doc.get("schema") != SIBLING_SCHEMA:
        return {"state": UNRECOGNISED, "detail": f"not a {SIBLING_SCHEMA} document"}
    verdict = doc.get("verdict") if isinstance(doc.get("verdict"), Mapping) else {}
    seen = [t for t in (_instant(doc.get("last_probe_utc")), _instant(verdict.get("at"))) if t is not None]
    if not seen:
        return {"state": UNREADABLE, "detail": "the document carries no time of observation"}
    observed = max(seen)
    age = (now - observed).total_seconds()
    base = {"observed_at": observed.isoformat(timespec="seconds"), "age_seconds": int(age), "mode": doc.get("mode"),
            "error_class": doc.get("last_error_class")}
    if age > max_age_seconds:
        return {"state": STALE, **base, "detail": f"observed {int(age)} s ago, more than {max_age_seconds} s"}
    if doc.get("reachable") is False or str(doc.get("mode") or "").startswith("DEGRADED"):
        hold = _instant(doc.get("next_probe_after_utc"))
        return {"state": SHARE_DEGRADED, **base, "hold_until": hold.isoformat(timespec="seconds") if hold else None,
                "detail": f"CO.RA.PAN observes the share as {doc.get('mode')} ({doc.get('last_error_class')})"}
    if doc.get("share_slow") is True:
        return {"state": SHARE_SLOW, **base, "detail": "CO.RA.PAN observes the share as slow"}
    return {"state": SHARE_NORMAL, **base, "detail": "CO.RA.PAN observes the share as normal (this permits nothing by itself)"}


# --- the share gate --------------------------------------------------------------------------------------------


class ShareBackingOff(StorageRootUnreachable):
    """The share is in its back-off: it is not contacted now. A refusal of the root like any unreachable one (contract I2:
    unreachable is not empty), so the pipeline's outage path (pending, spool) takes it as it is."""


class ShareGate:
    """A persisted back-off in front of the PRESERVATION root (and any other root on the shared server).

    ``guard(resolve)`` returns a callable that resolves the root only when the gate is open; otherwise it raises the
    refusal ``refuse(reason)`` (by default :class:`ShareBackingOff`) **without any contact**. A failed resolution, and an
    I/O failure the caller reports with :meth:`failed`, close the gate for ``initial * factor**(n-1)`` seconds (capped).
    A success opens it. The state survives a restart; it is written only when it changes.
    """

    def __init__(self, runtime: Path, policy: ResourcePolicy, *, env: Mapping[str, str] | None = None,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self.path = Path(runtime) / STATE_DIRECTORY / SHARE_STATE_FILE
        self.policy, self.env, self.clock = policy, dict(env or {}), clock

    # state
    def state(self) -> dict[str, Any]:
        try:
            doc = json.loads(self.path.read_text(encoding="utf-8"))
            if doc.get("schema") == SHARE_STATE_SCHEMA:
                return doc
        except (OSError, ValueError):
            pass
        return {"schema": SHARE_STATE_SCHEMA, "failures": 0, "next_contact_after": None, "last_failure": None, "last_success_at": None}

    def _write(self, doc: Mapping[str, Any]) -> None:
        write_bytes_atomic(self.path, record_json(dict(doc)))

    def closed_because(self) -> str | None:
        """Why the share must not be contacted now, or ``None``. Reads local files only."""
        now = self.clock()
        state = self.state()
        until = _instant(state.get("next_contact_after"))
        if until is not None and now < until:
            return f"share back-off until {until.isoformat(timespec='seconds')} after {state.get('failures')} failed contact(s): {state.get('last_failure')}"
        advice = sibling_advisory(self.env, now, max_age_seconds=self.policy.sibling_signal_max_age_seconds)
        if advice["state"] == SHARE_DEGRADED:
            hold = _instant(advice.get("hold_until"))
            if hold is None or now < hold:
                return f"sibling advisory: {advice['detail']}" + (f"; its next probe after {advice['hold_until']}" if hold else "")
        return None

    def failed(self, reason: str) -> None:
        now = self.clock()
        state = self.state()
        failures = int(state.get("failures") or 0) + 1
        delay = min(self.policy.backoff_max_seconds, self.policy.backoff_initial_seconds * self.policy.backoff_factor ** (failures - 1))
        self._write({**state, "failures": failures, "last_failure": f"{reason}"[:300], "last_failure_at": now.isoformat(timespec="seconds"),
                     "next_contact_after": (now + timedelta(seconds=delay)).isoformat(timespec="seconds")})

    def succeeded(self) -> None:
        state = self.state()
        if state.get("failures") or state.get("next_contact_after"):
            self._write({**state, "failures": 0, "next_contact_after": None, "last_success_at": self.clock().isoformat(timespec="seconds"),
                         "recovered_from": state.get("last_failure")})

    def guard(self, resolve: Callable[[], Path], *, refuse: Callable[[str], Exception] | None = None) -> "GuardedRoot":
        return GuardedRoot(self, resolve, refuse or ShareBackingOff)

    def status(self) -> dict[str, Any]:
        state = self.state()
        return {**{k: state.get(k) for k in ("failures", "next_contact_after", "last_failure", "last_failure_at", "last_success_at")},
                "closed_because": self.closed_because()}


class GuardedRoot:
    """The callable a pipeline takes as ``preservation_root``: resolves through the gate. ``report_failure`` lets the caller
    close the gate after an I/O failure that happened after a successful resolution (a promotion that broke off)."""

    def __init__(self, gate: ShareGate, resolve: Callable[[], Path], refuse: Callable[[str], Exception]) -> None:
        self.gate, self.resolve, self.refuse = gate, resolve, refuse

    def __call__(self) -> Path:
        reason = self.gate.closed_because()
        if reason is not None:
            raise self.refuse(reason)
        try:
            root = self.resolve()
        except Exception as error:
            if _is_availability_failure(error):
                self.gate.failed(f"{type(error).__name__}: {error}")
            raise
        self.gate.succeeded()
        return root

    def report_failure(self, reason: str) -> None:
        self.gate.failed(reason)


def _is_availability_failure(error: BaseException) -> bool:
    """A failure of availability closes the gate; a configuration or identity refusal does not (it is not cured by waiting)."""
    return isinstance(error, (StorageRootUnreachable, StorageRootReadOnly, OSError)) and not isinstance(error, ShareBackingOff)


def report_failure(preservation_root: Any, reason: str) -> None:
    """Tell a guarded root (if it is one) that the share failed during a step; a plain callable is left alone."""
    hook = getattr(preservation_root, "report_failure", None)
    if callable(hook):
        hook(reason)


def maintenance_refusal(policy: ResourcePolicy, runtime: Path | None, now: datetime, env: Mapping[str, str]) -> str | None:
    """Why CO.PRE.PAN maintenance on shared storage (backup, fixity) must not start or continue now, or ``None``:
    the pause file, a quiet window, a fresh sibling observation that the share is degraded or slow."""
    reason = paused(runtime) or policy.quiet_window(now)
    if reason:
        return reason
    advice = sibling_advisory(env, now, max_age_seconds=policy.sibling_signal_max_age_seconds)
    if advice["state"] in CAUTION:
        return f"sibling advisory: {advice['detail']}"
    return None


__all__ = ["CAUTION", "GuardedRoot", "PAUSE_FILE", "QuietWindow", "ResourcePolicy", "ResourcePolicyError", "SCHEMA", "SHARE_DEGRADED", "SHARE_NORMAL",
           "SHARE_SLOW", "SIBLING_SIGNAL_VARIABLE", "ShareBackingOff", "ShareGate", "default_policy_path", "free_space_refusal", "load_policy",
           "maintenance_refusal", "parse_policy", "pause_path", "paused", "report_failure", "sibling_advisory"]
