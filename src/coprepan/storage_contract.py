"""``crosscorpus-storage/v1`` — CO.PRE.PAN's implementation of the joint storage-management contract (CPD-0015).

Normative source: ``contracts/crosscorpus-storage-v1/CONTRACT.md``, a verbatim copy of the bundle whose
canonical home is CO.RA.PAN, pinned by digest in ``config/crosscorpus/contract_pins.json``. This module
is CO.PRE.PAN's own code: it shares the reference cases (``conformance/CASES.json``) with CO.RA.PAN's
implementation and nothing else.

The decision functions are pure — no I/O. They are *used* by the code that acts:
:func:`coprepan.storage_roots.validate_role_separation` (separation), the outage path of
:func:`coprepan.core_pipeline.preserve_pack` (what a step may claim, and when a spool copy may be
released), and ``scripts/storage_contract.py`` (status).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import release_contract

CONTRACT = "crosscorpus-storage/v1"
BUNDLE_PATH = "contracts/crosscorpus-storage-v1"
PINS_PATH = "config/crosscorpus/contract_pins.json"
_CHECKOUT = Path(__file__).resolve().parents[2]

# The contract's role names and this repository's (CPD-0014 §2). Only REPO differs.
CONTRACT_ROLE = {"REPOSITORY": "REPO", "RUNTIME": "RUNTIME", "SPOOL": "SPOOL", "PRESERVATION": "PRESERVATION",
                 "BACKUP": "BACKUP", "DISTRIBUTION": "DISTRIBUTION", "EXCHANGE": "EXCHANGE"}
HOLDINGS = ("PRODUCTION", "HISTORIC")
_NAMESPACE = ("projects", "panhispanic_media_corpora")
_NEVER_CO_LOCATED = frozenset(("PRESERVATION", "BACKUP", "SPOOL"))

STATE_NOT_DECLARED = "NOT_DECLARED"
STATE_NOT_CONFIGURED = "NOT_CONFIGURED"
STATE_DEFAULTED = "DEFAULTED"
STATE_UNUSABLE = "UNUSABLE"
STATE_UNREACHABLE = "UNREACHABLE"
STATE_READ_ONLY = "READ_ONLY"
STATE_AVAILABLE = "AVAILABLE"
CONFIGURATION_STATES = (STATE_NOT_DECLARED, STATE_NOT_CONFIGURED, STATE_DEFAULTED, STATE_UNUSABLE, STATE_UNREACHABLE,
                        STATE_READ_ONLY, STATE_AVAILABLE)

OBJECT_PRESERVED, OBJECT_PENDING, OBJECT_REFUSED = "PRESERVED", "PENDING", "REFUSED"
PENDING_IN_SPOOL, PENDING_IN_WORKSPACE = "SPOOL", "WORKSPACE"
CLEANUP_PROTECTED, CLEANUP_REMOVABLE = "PROTECTED", "REMOVABLE"

SEPARATION_CODES = ("ROLE_SHARED", "ROLE_NESTED", "BACKUP_NOT_INDEPENDENT", "VOLUME_UNKNOWN", "FOREIGN_CORPUS_OVERLAP")
BACKUP_STATES = ("NOT_CONFIGURED", "CONFIGURED_NO_COPY", "COPY_UNVERIFIED", "NOT_INDEPENDENT", "INDEPENDENCE_UNKNOWN",
                 "BACKUP_VERIFIED")


class BundleRefused(RuntimeError):
    """The local copy of the storage contract is not the pinned bundle."""


# --- §5.1 separation ------------------------------------------------------------------------------


def path_segments(path: Any) -> tuple[str, ...]:
    """A path as the contract compares it (§5.1): its segments, case-folded. Lexical only."""
    return tuple(segment.casefold() for segment in str(path).replace("\\", "/").split("/") if segment)


def _overlap(first: tuple[str, ...], second: tuple[str, ...]) -> str | None:
    """``ROLE_SHARED`` for the same root, ``ROLE_NESTED`` when one contains the other, else ``None``."""
    if first == second:
        return "ROLE_SHARED"
    short, long = sorted((first, second), key=len)
    return "ROLE_NESTED" if long[: len(short)] == short else None


def role_separation(
    roots: Mapping[str, Any],
    *,
    volumes: Mapping[str, Any] | None = None,
    co_located: Iterable[Sequence[str]] = (),
    foreign_roots: Iterable[Any] = (),
) -> list[str]:
    """The separation codes of the configured role roots of one holding (S1–S4): sorted, each once.

    ``roots`` is keyed by the contract's role names. ``volumes`` gives a volume identity per role
    (anything comparable; ``None`` or a missing key is "unknown"). An empty result means separated.
    """
    declared = set()
    for pair in co_located:
        members = frozenset(pair)
        if len(members) == 2 and not members & _NEVER_CO_LOCATED:
            declared.add(members)
    split = {role: path_segments(root) for role, root in roots.items()}
    found = set()
    names = sorted(split)
    for position, first in enumerate(names):
        for second in names[position + 1:]:
            code = _overlap(split[first], split[second])
            if code is not None and frozenset((first, second)) not in declared:
                found.add(code)
    if "PRESERVATION" in split and "BACKUP" in split:
        known = volumes or {}
        primary, backup = known.get("PRESERVATION"), known.get("BACKUP")
        if primary is None or backup is None:
            found.add("VOLUME_UNKNOWN")
        elif primary == backup:
            found.add("BACKUP_NOT_INDEPENDENT")
    for foreign in foreign_roots:
        other = path_segments(foreign)
        if any(_overlap(own, other) is not None for own in split.values()):
            found.add("FOREIGN_CORPUS_OVERLAP")
    return sorted(found)


# --- §5.2 namespace ---------------------------------------------------------------------------------


def namespace(provided_root: Sequence[str], corpus: str, holding: str = "PRODUCTION") -> list[str]:
    """The segments of a corpus root below an administratively provided root: the institutional
    namespace joined without repeating what the provided root already ends with (§5.2)."""
    if holding not in HOLDINGS:
        raise ValueError(f"not a holding: {holding!r}")
    tail = list(_NAMESPACE) + (["historic"] if holding == "HISTORIC" else []) + [corpus]
    head = list(provided_root)
    shared = 0
    for length in range(1, min(len(head), len(tail)) + 1):
        if [segment.casefold() for segment in head[-length:]] == [segment.casefold() for segment in tail[:length]]:
            shared = length
    return head + tail[shared:]


# --- §4.2 configuration state -------------------------------------------------------------------------


def configuration_state(
    *,
    declared: bool,
    value: str | None,
    default: str | None = None,
    usable: bool = False,
    reachable: bool = False,
    writable: bool = False,
    need_write: bool = True,
) -> str:
    """The one state a role resolves to. A set value that cannot be used never falls back (I1)."""
    if not declared:
        return STATE_NOT_DECLARED
    if value is None or not value.strip():
        return STATE_DEFAULTED if default else STATE_NOT_CONFIGURED
    if not usable:
        return STATE_UNUSABLE
    if not reachable:
        return STATE_UNREACHABLE
    if need_write and not writable:
        return STATE_READ_ONLY
    return STATE_AVAILABLE


# --- §7 preservation outcome ----------------------------------------------------------------------------


def preservation_outcome(
    *,
    content_ok: bool,
    primary: str,
    primary_copy_verified: bool,
    record_written: bool,
    spool: str = STATE_NOT_CONFIGURED,
    spool_has_capacity: bool = False,
    spool_copy_verified: bool = False,
) -> dict[str, Any]:
    """What one preservation step may claim (P1–P7).

    ``PRESERVED`` only with the primary available, its bytes re-read and verified, and the record
    written. A content refusal is ``REFUSED`` and is never pending anywhere. Everything else is
    ``PENDING`` — in the spool exactly when a verified copy is there, otherwise in the workspace.
    """
    if not content_ok:
        return {"state": OBJECT_REFUSED, "pending_location": None, "spool_copy_releasable": False, "local_copy_protected": True}
    if primary == STATE_AVAILABLE and primary_copy_verified and record_written:
        return {"state": OBJECT_PRESERVED, "pending_location": None, "spool_copy_releasable": True, "local_copy_protected": False}
    spooled = spool == STATE_AVAILABLE and spool_has_capacity and spool_copy_verified
    return {"state": OBJECT_PENDING, "pending_location": PENDING_IN_SPOOL if spooled else PENDING_IN_WORKSPACE,
            "spool_copy_releasable": False, "local_copy_protected": True}


# --- §8 cleanup ------------------------------------------------------------------------------------


def cleanup(
    *,
    pending: bool,
    on_primary: bool,
    regenerable: bool | None,
    verified_copy_on_primary: bool | None,
    named_by_frozen_release: bool = False,
    deletion_decision_recorded: bool = False,
) -> str:
    """Whether bytes may be removed (R1–R4). Unknown is protected; a storage class decides nothing."""
    if pending:
        return CLEANUP_PROTECTED
    if on_primary:
        return CLEANUP_REMOVABLE if deletion_decision_recorded and not named_by_frozen_release else CLEANUP_PROTECTED
    if regenerable is True or verified_copy_on_primary is True:
        return CLEANUP_REMOVABLE
    return CLEANUP_PROTECTED


# --- §9 backup ---------------------------------------------------------------------------------------


def backup_status(
    *,
    configured: bool,
    copy_exists: bool,
    produced_from_primary: bool,
    verified_against_primary: bool,
    primary_volume: Any,
    backup_volume: Any,
    **_unused: Any,
) -> str:
    """The backup state of a holding (B1, B2, B6): only a copy that exists, was produced from the
    primary and verified against it, on another volume, is a backup."""
    if not configured:
        return "NOT_CONFIGURED"
    if primary_volume is None or backup_volume is None:
        return "INDEPENDENCE_UNKNOWN"
    if primary_volume == backup_volume:
        return "NOT_INDEPENDENT"
    if not copy_exists:
        return "CONFIGURED_NO_COPY"
    if not produced_from_primary or not verified_against_primary:
        return "COPY_UNVERIFIED"
    return "BACKUP_VERIFIED"


# --- the bundle and its pin (§12) -------------------------------------------------------------------------


def read_pin(checkout: Path = _CHECKOUT) -> dict[str, Any]:
    pins = json.loads((Path(checkout) / PINS_PATH).read_text(encoding="utf-8"))
    pin = pins.get("contracts", {}).get(CONTRACT)
    if not isinstance(pin, dict) or not release_contract.is_sha256(pin.get("bundle_sha256")):
        raise BundleRefused(f"the pin file does not pin {CONTRACT} by a bundle digest")
    return pin


def bundle_problems(checkout: Path = _CHECKOUT) -> list[str]:
    """Why the local copy is not the pinned bundle. Empty: it is. Reads; changes nothing."""
    directory = Path(checkout) / BUNDLE_PATH
    if not directory.is_dir():
        return [f"no bundle directory: {BUNDLE_PATH}"]
    try:
        pin = read_pin(checkout)
        listing = release_contract.tree_listing(directory)
    except (BundleRefused, OSError, ValueError) as error:
        return [str(error)]
    problems = []
    if sorted(entry["path"] for entry in listing) != ["CONTRACT.md", "conformance/CASES.json"]:
        problems.append("the bundle is not exactly CONTRACT.md and conformance/CASES.json")
    digest = release_contract.record_set_digest(listing)
    if digest != pin["bundle_sha256"]:
        problems.append(f"bundle digest {digest} is not the pinned {pin['bundle_sha256']}: the copy has drifted")
    return problems


def load_cases(checkout: Path = _CHECKOUT) -> dict[str, Any]:
    """The reference cases of the pinned bundle. Refuses a copy that is not the pinned one."""
    problems = bundle_problems(checkout)
    if problems:
        raise BundleRefused("; ".join(problems))
    return json.loads((Path(checkout) / BUNDLE_PATH / "conformance" / "CASES.json").read_text(encoding="utf-8"))
