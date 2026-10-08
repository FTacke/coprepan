"""Storage roles and fail-closed root resolution (``docs/storage/INDEX.md`` §5).

A storage root is resolved from the environment through the logical targets declared in
``config/storage_targets.yml``. There is no default and no fallback: an unset, unusable,
unreachable or read-only root is a refusal raised *before any byte moves*. A root inside the
checkout is refused as well — the checkout is the ``REPOSITORY`` role and never holds corpus data
or runtime state.

No concrete path lives in this module or in tracked configuration.
"""

from __future__ import annotations

import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from . import naming

STORAGE_TARGETS_SCHEMA = naming.schema_id("storage-targets", 1)

# One role per function. REPOSITORY is the checkout and has no root to resolve; BACKUP is named by
# the storage contract but has no configured target yet.
ROLES = ("REPOSITORY", "RUNTIME", "PRESERVATION", "SPOOL", "DISTRIBUTION", "EXCHANGE", "BACKUP")

CHECKOUT = Path(__file__).resolve().parents[2]
DEFAULT_TARGETS_FILE = CHECKOUT / "config" / "storage_targets.yml"

_ENV_REFERENCE = re.compile(r"\$\{(COPREPAN_[A-Z0-9]+(?:_[A-Z0-9]+)*_ROOT)\}")
_TOP_KEY = re.compile(r"([a-z_]+):(?: (.*))?")
_ROLE_KEY = re.compile(r"  ([A-Z]+):")
_FIELD = re.compile(r"    ([a-z_]+): (.+)")
_ENV_LINE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)")


class StorageRefusal(RuntimeError):
    """A storage root may not be used. Never caught to fall back to another location."""


class StorageConfigError(StorageRefusal):
    """The tracked storage configuration is not what the contract allows."""


class StorageRootNotConfigured(StorageRefusal):
    """The role has no target, or its environment variable is unset or empty."""


class StorageRootUnusable(StorageRefusal):
    """The configured value is not an acceptable root (relative, a filesystem root, in the checkout)."""


class StorageRootUnreachable(StorageRefusal):
    """The configured root is not a reachable directory. Its content is unknown, not empty."""


class StorageRootReadOnly(StorageRefusal):
    """The configured root is reachable but cannot be written to."""


@dataclass(frozen=True)
class StorageTarget:
    role: str
    variable: str
    purpose: str
    authoritative: bool


@dataclass(frozen=True)
class RootProbe:
    """What is known about a root. ``free_bytes`` is ``None`` when it could not be measured."""

    reachable: bool
    free_bytes: int | None
    total_bytes: int | None


def load_storage_targets(path: Path | None = None) -> dict[str, StorageTarget]:
    """Read the logical targets. The file format is the small fixed shape of the tracked file:
    a ``schema`` line and, under ``targets:``, one block per role with ``root``, ``purpose`` and
    ``authoritative``. Anything else is a configuration error, not something to interpret.
    """
    path = Path(path) if path is not None else DEFAULT_TARGETS_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise StorageConfigError(f"storage targets file is not readable: {error}") from error

    schema = None
    blocks: dict[str, dict[str, str]] = {}
    section = None
    role = None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        where = f"{path.name}:{number}"
        if match := _TOP_KEY.fullmatch(line):
            section, role = match.group(1), None
            if section == "schema" and match.group(2):
                schema = match.group(2).strip()
            elif section != "targets" or match.group(2):
                raise StorageConfigError(f"{where}: unexpected top-level entry {line!r}")
        elif section == "targets" and (match := _ROLE_KEY.fullmatch(line)):
            role = match.group(1)
            if role in blocks:
                raise StorageConfigError(f"{where}: role {role} is declared twice")
            blocks[role] = {}
        elif section == "targets" and role and (match := _FIELD.fullmatch(line)):
            if match.group(1) in blocks[role]:
                raise StorageConfigError(f"{where}: {role}.{match.group(1)} is given twice")
            blocks[role][match.group(1)] = match.group(2).strip()
        else:
            raise StorageConfigError(f"{where}: line does not fit the storage-targets format: {line!r}")

    if schema != STORAGE_TARGETS_SCHEMA:
        raise StorageConfigError(f"{path.name}: schema is {schema!r}, expected {STORAGE_TARGETS_SCHEMA!r}")
    targets = {}
    for name, fields in blocks.items():
        if name not in ROLES or name == "REPOSITORY":
            raise StorageConfigError(f"{path.name}: {name} is not a storage role with a root")
        if set(fields) != {"root", "purpose", "authoritative"}:
            raise StorageConfigError(f"{path.name}: {name} must have exactly root, purpose, authoritative")
        reference = _ENV_REFERENCE.fullmatch(fields["root"])
        if reference is None:
            raise StorageConfigError(f"{path.name}: {name}.root must be an ${{COPREPAN_*_ROOT}} reference")
        if fields["authoritative"] not in ("true", "false"):
            raise StorageConfigError(f"{path.name}: {name}.authoritative must be true or false")
        targets[name] = StorageTarget(name, reference.group(1), fields["purpose"], fields["authoritative"] == "true")
    if not targets:
        raise StorageConfigError(f"{path.name}: no storage target declared")
    variables = [target.variable for target in targets.values()]
    if len(set(variables)) != len(variables):
        raise StorageConfigError(f"{path.name}: two roles share one environment variable")
    return targets


def read_env_file(path: Path) -> dict[str, str]:
    """Parse a workstation ``.env`` (``NAME=value`` lines, ``#`` comments). Reads, never exports."""
    values = {}
    for number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _ENV_LINE.fullmatch(line)
        if match is None:
            raise StorageConfigError(f"{Path(path).name}:{number}: not a NAME=value line")
        value = match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[match.group(1)] = value
    return values


def workstation_environment(checkout: Path = CHECKOUT, process_env: Mapping[str, str] | None = None) -> dict[str, str]:
    """The process environment over the workstation ``.env`` of the checkout (the process wins).

    Only ``COPREPAN_*`` names are taken from the file, so that a workstation file cannot reconfigure
    anything else. A missing ``.env`` is legal and means that nothing is configured from it.
    """
    values: dict[str, str] = {}
    path = Path(checkout) / ".env"
    if path.is_file():
        values = {name: value for name, value in read_env_file(path).items() if name.startswith("COPREPAN_")}
    values.update(os.environ if process_env is None else process_env)
    return values


def volume_of(root: Path) -> int:
    """An identifier of the physical or logical volume holding ``root`` (the device number). Refuses
    when it cannot be determined: whether two roots share a volume is never guessed.
    """
    try:
        device = os.stat(root).st_dev
    except OSError as error:
        raise StorageRootUnreachable(f"{root.name}: the volume cannot be determined: {type(error).__name__}") from error
    if not device:
        raise StorageRootUnusable(f"{root.name}: this platform reports no volume identity")
    return device


def separation_codes(roots: Mapping[str, Path], *, checkout: Path = CHECKOUT, foreign_roots: Sequence[Path | str] = ()) -> list[str]:
    """The separation codes of the joint storage contract (``crosscorpus-storage/v1`` §5.1, S1–S4)
    for a set of configured roots; empty when the roles are apart.

    The decision is the contract's (:func:`coprepan.storage_contract.role_separation`); this
    function supplies the facts: the checkout as the ``REPO`` role and, when both ``BACKUP`` and
    ``PRESERVATION`` are configured, their volumes. A volume that cannot be determined raises — it
    is never guessed. ``foreign_roots`` are roots of the sister corpus (S4).
    """
    from . import storage_contract

    named = {"REPO": Path(checkout), **{storage_contract.CONTRACT_ROLE[role]: Path(root) for role, root in roots.items()}}
    volumes = {}
    if "BACKUP" in roots and "PRESERVATION" in roots:
        volumes = {role: volume_of(Path(roots[role])) for role in ("BACKUP", "PRESERVATION")}
    return storage_contract.role_separation(named, volumes=volumes, foreign_roots=foreign_roots)


def validate_role_separation(roots: Mapping[str, Path], *, checkout: Path = CHECKOUT, foreign_roots: Sequence[Path | str] = ()) -> None:
    """Refuse a set of configured roots that does not keep the roles apart (CPD-0014, CPD-0015).

    * no two roles share a root, and no role lies inside another (the checkout is the
      ``REPOSITORY`` role and takes part);
    * ``BACKUP`` is on another volume than ``PRESERVATION``: a second copy on the same physical
      volume is not a backup, whatever it is called;
    * no root equals, contains or lies inside a root of the sister corpus.

    Lexical for the nesting rules (no I/O); the volume rule reads the volumes and fails closed.
    """
    codes = separation_codes(roots, checkout=checkout, foreign_roots=foreign_roots)
    if not codes:
        return
    reasons = {
        "ROLE_SHARED": "two roles overlap: they share one root (one role per function, never nested or shared)",
        "ROLE_NESTED": "two roles overlap: one root lies inside another (one role per function, never nested or shared)",
        "BACKUP_NOT_INDEPENDENT": "BACKUP is on the same volume as PRESERVATION: that is not an independent copy",
        "VOLUME_UNKNOWN": "the volume of BACKUP or PRESERVATION is unknown: independence is never guessed",
        "FOREIGN_CORPUS_OVERLAP": "a root overlaps a root of the sister corpus: one corpus is never stored under the other",
    }
    raise StorageRootUnusable("; ".join(f"{code}: {reasons[code]}" for code in codes))


def resolve_configured_roles(
    *,
    env: Mapping[str, str] | None = None,
    targets: Mapping[str, StorageTarget] | None = None,
) -> dict[str, Path | None]:
    """Every declared role: its resolved root, or ``None`` when it is not configured.

    ``None`` is a statement, never a default: a caller that needs the role calls
    :func:`resolve_root`, which refuses. A role that is configured but unusable raises. The
    configured roles are checked against each other (:func:`validate_role_separation`).
    """
    targets = load_storage_targets() if targets is None else targets
    env = workstation_environment() if env is None else env
    resolved: dict[str, Path | None] = {}
    for role, target in sorted(targets.items()):
        if not env.get(target.variable, "").strip():
            resolved[role] = None
        else:
            resolved[role] = resolve_root(role, env=env, targets=targets)
    validate_role_separation({role: root for role, root in resolved.items() if root is not None})
    return resolved


def probe(root: Path) -> RootProbe:
    """Reachability and free space. Never raises; an unreachable root reports unknown, not zero."""
    try:
        if not root.is_dir():
            return RootProbe(False, None, None)
        usage = shutil.disk_usage(root)
    except OSError:
        return RootProbe(False, None, None)
    return RootProbe(True, usage.free, usage.total)


def resolve_root(
    role: str,
    *,
    env: Mapping[str, str] | None = None,
    targets: Mapping[str, StorageTarget] | None = None,
    writable: bool = True,
) -> Path:
    """The root directory of a storage role, or a :class:`StorageRefusal`.

    ``env`` defaults to the process environment. The root must already exist: resolution never
    creates a root, because a missing directory on a network share means the share is not mounted.
    """
    if role not in ROLES:
        raise StorageConfigError(f"not a storage role: {role!r}")
    targets = load_storage_targets() if targets is None else targets
    target = targets.get(role)
    if target is None:
        raise StorageRootNotConfigured(f"{role}: no storage target is declared for this role")
    env = os.environ if env is None else env
    value = env.get(target.variable, "")
    if not value.strip():
        raise StorageRootNotConfigured(f"{role}: {target.variable} is not set")

    root = require_usable_root(value, f"{role} ({target.variable})")
    if not probe(root).reachable:
        raise StorageRootUnreachable(f"{role}: {target.variable} does not name a reachable directory")
    if writable and not _writable(root):
        raise StorageRootReadOnly(f"{role}: {target.variable} is not writable")
    return root


def require_usable_root(value: str, what: str) -> Path:
    """Lexical checks only (no I/O): absolute, not a filesystem root, not inside the checkout.

    ``normpath`` rather than ``resolve``: resolving blocks on an offline network share.
    """
    if not os.path.isabs(value):
        raise StorageRootUnusable(f"{what}: a storage root is an absolute path")
    root = Path(os.path.normpath(value))
    if root == Path(root.anchor):
        raise StorageRootUnusable(f"{what}: a filesystem root is not a storage root")
    if is_inside(root, CHECKOUT):
        raise StorageRootUnusable(f"{what}: a storage root may not lie inside the checkout")
    return root


def is_inside(path: Path, parent: Path) -> bool:
    """Whether ``path`` is ``parent`` or below it, compared lexically and case-normalised."""
    child = os.path.normcase(os.path.normpath(os.path.abspath(path)))
    base = os.path.normcase(os.path.normpath(os.path.abspath(parent)))
    return child == base or child.startswith(base.rstrip("\\/") + os.sep)


def _writable(root: Path) -> bool:
    """Create and remove an empty, uniquely named probe file directly in the root."""
    marker = root / f".coprepan_write_probe-{uuid.uuid4().hex[:12]}"
    try:
        with open(marker, "xb"):
            pass
    except OSError:
        return False
    try:
        marker.unlink()
    except OSError:
        pass
    return True
