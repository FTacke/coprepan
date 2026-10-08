"""Checks of the joint release contract ``crosscorpus-release/v1`` — CO.PRE.PAN's own implementation.

The contract is one byte-identical bundle that both corpora read
(``contracts/crosscorpus-release-v1/``; its canonical home is the CO.RA.PAN repository). This
module is the **second, independent implementation** of its checks: it was written from the
bundle's text, schemas, fixtures and vectors, shares no code with CO.RA.PAN's, and is held to it
only by ``conformance/VECTORS.json`` (contract §14.2). Decisions: CPD-0011, CPD-0012.

What is here: canonical values and the two digests (§4), contract paths and the tree digest
(§4.4–§4.5), the schema subset (§12), and the three checks of §13 — release, study population,
package — with their phases and the closed vocabulary of codes. **A check reads and never
repairs.** A phase that objects ends the check.

What is not here: anything that builds a release (``release_export.py``), any pipeline stage, any
storage root. The module imports nothing of the pipeline, so that a release can be checked
without it.

The bundle is used only through :func:`load_contract`, which recomputes its digest and refuses a
copy that is not the pinned one. The copy in this repository is never edited: a needed change is
made in the canonical home and re-pinned on both sides.

Words that are not the same thing (contract §3): a *release freeze* (the record that names a
manifest by its digest) is not the *acquisition baseline freeze* of ``freeze.py`` (O-12) and not
the *legacy freeze manifest* of ``legacy_freeze.py``; the test suite ``release_gate`` gates
software changes and says nothing about a corpus release.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .canonical import canonical_json, is_sha256, sha256_bytes, sha256_file

CONTRACT = "crosscorpus-release/v1"
BUNDLE_PATH = "contracts/crosscorpus-release-v1"
PINS_PATH = "config/crosscorpus/contract_pins.json"
PINS_SCHEMA = "coprepan-crosscorpus-contract-pins/v1"
_CHECKOUT = Path(__file__).resolve().parents[2]

ANALYSIS_CONTRACT = "crosscorpus-analysis/v1"
TOKEN_DENOMINATOR = "crosscorpus-token-denominator/v1"
FILTER_LANGUAGE = "crosscorpus-document-filter/v1"

MANIFEST_SCHEMA = "crosscorpus-release-manifest/v1"
MEMBER_SCHEMA = "crosscorpus-release-member/v1"
DOCUMENT_SCHEMA = "crosscorpus-release-document/v1"
COVERAGE_SCHEMA = "crosscorpus-release-coverage/v1"
FREEZE_SCHEMA = "crosscorpus-release-freeze/v1"
POINTER_SCHEMA = "crosscorpus-release-pointer/v1"
STUDY_SCHEMA = "crosscorpus-study-population/v1"
SELECTION_SCHEMA = "crosscorpus-study-selection-record/v1"
PACKAGE_SCHEMA = "crosscorpus-package-manifest/v1"
PACKAGE_FILE_SCHEMA = "crosscorpus-package-file/v1"
SCHEMA_IDS = (MANIFEST_SCHEMA, MEMBER_SCHEMA, DOCUMENT_SCHEMA, COVERAGE_SCHEMA, FREEZE_SCHEMA, POINTER_SCHEMA,
              STUDY_SCHEMA, SELECTION_SCHEMA, PACKAGE_SCHEMA, PACKAGE_FILE_SCHEMA)

RELEASE_MANIFEST, RELEASE_FREEZE = "RELEASE_MANIFEST.json", "RELEASE_FREEZE.json"
MEMBERS, DOCUMENTS, COVERAGE = "MEMBERS.jsonl", "DOCUMENTS.jsonl", "COVERAGE.jsonl"
STUDY_POPULATION, SELECTED, EXCLUDED = "STUDY_POPULATION.json", "SELECTED.jsonl", "EXCLUDED.jsonl"
PACKAGE_MANIFEST, PACKAGE_FILES = "PACKAGE_MANIFEST.json", "PACKAGE_FILES.jsonl"

# The closed vocabulary of this contract version (§13.1).
CODES = (
    "NON_CANONICAL_VALUE", "CONTRACT_VERSION_UNSUPPORTED", "SCHEMA_VIOLATION", "RELEASE_ID_INVALID",
    "REFERENCE_MISSING", "PIN_MISMATCH", "MEMBERSHIP_INCONSISTENT", "PREVIOUS_RELEASE_MISMATCH",
    "DOCUMENT_INCONSISTENT", "COVERAGE_MISMATCH", "TOTALS_MISMATCH", "EXPORT_MISSING", "PATH_INVALID",
    "EXPORT_TREE_MISMATCH", "FREEZE_MISMATCH", "RELEASE_PIN_MISMATCH", "POPULATION_NOT_RESTORABLE",
    "ANCHOR_KIND_INVALID", "POPULATION_SELECTION_MISMATCH", "PACKAGE_FORBIDDEN_CONTENT", "PACKAGE_INCOMPLETE",
)

KNOWN = "known"
STATES = (KNOWN, "unknown", "not_applicable", "undecided", "not_available")
NOT_APPLICABLE, NOT_AVAILABLE = "not_applicable", "not_available"
INTEGER_LIMIT = 2**53 - 1

# What a release of each modality may name as an anchor (§8). No kind of one is valid in the other.
ANCHORS = {
    "spoken": {"document_kind": "recording", "source_kind": "audio_master",
               "unit_kinds": ("turn", "contribution_unit"), "producer_kinds": ("speaker_occurrence", "station_speaker")},
    "written": {"document_kind": "document_version", "source_kind": "extracted_text",
                "unit_kinds": ("title", "heading", "paragraph", "list_item", "quote_block", "caption", "unstructured_text"),
                "producer_kinds": ()},
}
# Suffixes a package of this contract version refuses (§11.3).
FORBIDDEN_SUFFIXES = (".wav", ".flac", ".mp3", ".m4a", ".mp4", ".ogg", ".opus", ".aac", ".wma", ".aif", ".aiff", ".webm")
RELEASE_FILE_ROLES = {
    f"release/{RELEASE_MANIFEST}": "release_manifest", f"release/{RELEASE_FREEZE}": "release_freeze",
    f"release/{MEMBERS}": "release_members", f"release/{DOCUMENTS}": "release_documents",
    f"release/{COVERAGE}": "release_coverage",
}
_FILTER_IN = ("country_id", "outlet_id", "export_id", "cohort", "date_basis")
_FILTER_RANGE = {"date": ("from", "to"), "tokens_counted": ("min", "max"), "audio_ms": ("min", "max")}
_FILTER_STATEFUL = ("cohort", "date_basis", "date", "tokens_counted", "audio_ms")


class NonCanonical(ValueError):
    """A value, or the text of one, that has no canonical form under contract §4.1."""


class PathInvalid(ValueError):
    """A tree that holds something whose name is not a contract path (§4.4)."""


class BundleRefused(RuntimeError):
    """The contract bundle at hand is not the pinned one, or is not a bundle this code supports."""


@dataclass(frozen=True)
class Objection:
    code: str
    where: str
    detail: str

    def __post_init__(self) -> None:
        if self.code not in CODES:
            raise ValueError(f"not a code of {CONTRACT}: {self.code!r}")


@dataclass(frozen=True)
class Verdict:
    """What a check reports. Its verdict is the set of codes (§13.1)."""

    check: str
    objections: tuple[Objection, ...]
    exports_checked: bool = False   # False: only the manifest side was proved consistent (§6.3)

    @property
    def codes(self) -> list[str]:
        return sorted({objection.code for objection in self.objections})

    @property
    def conformant(self) -> bool:
        return not self.objections

    def as_record(self) -> dict[str, Any]:
        return {"check": self.check, "contract": CONTRACT, "conformant": self.conformant, "codes": self.codes,
                "exports_checked": self.exports_checked,
                "objections": [{"code": o.code, "where": o.where, "detail": o.detail} for o in self.objections]}


# --- canonical values and the two digests (§4.1, §4.2) ---------------------------------------------


def require_canonical(value: Any, where: str = "value") -> None:
    """Raise :class:`NonCanonical` unless ``value`` consists of canonical values only."""
    if value is None or value is True or value is False:
        return
    if isinstance(value, int):
        if abs(value) > INTEGER_LIMIT:
            raise NonCanonical(f"{where}: an integer outside ±(2^53 − 1)")
        return
    if isinstance(value, str):
        _require_text(value, where)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            require_canonical(item, f"{where}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise NonCanonical(f"{where}: an object key that is not a string")
            _require_text(key, f"{where} key")
            require_canonical(item, f"{where}.{key}")
        return
    raise NonCanonical(f"{where}: {type(value).__name__} is not a canonical value")  # a float, above all


def _require_text(text: str, where: str) -> None:
    if not unicodedata.is_normalized("NFC", text):
        raise NonCanonical(f"{where}: a string that is not in Normalization Form C")
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as error:
        raise NonCanonical(f"{where}: a string that is not Unicode text") from error


def _refuse_number(text: str) -> Any:
    raise NonCanonical(f"a number with a fraction or exponent has no canonical form: {text}")


def _refuse_constant(text: str) -> Any:
    raise NonCanonical(f"not a canonical value: {text}")


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise NonCanonical(f"an object key is repeated: {key!r}")
        out[key] = value
    return out


def parse_strict(data: bytes) -> Any:
    """Parse the stored text of a contract document or record. The stored whitespace and key order
    carry nothing; a fraction, a repeated key, a non-NFC string or anything that is not JSON raise
    :class:`NonCanonical`.
    """
    try:
        value = json.loads(data.decode("utf-8"), parse_float=_refuse_number, parse_constant=_refuse_constant,
                           object_pairs_hook=_object)
    except NonCanonical:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise NonCanonical(f"not UTF-8 JSON text: {error}") from error
    require_canonical(value)
    return value


def document_digest(value: Any) -> str:
    """SHA-256 over the canonical JSON of one document (§4.2)."""
    require_canonical(value)
    return sha256_bytes(canonical_json(value))


def record_set_digest(records: Iterable[Any]) -> str:
    """SHA-256 over the canonical lines of a set of records, sorted bytewise, each ended by a line
    feed (§4.2). The order in which the records are given carries nothing.
    """
    lines = []
    for record in records:
        require_canonical(record)
        lines.append(canonical_json(record) + b"\n")
    return sha256_bytes(b"".join(sorted(lines)))


def record_set_bytes(records: Iterable[Any]) -> bytes:
    """The recommended stored form of a record set: its canonical lines in digest order."""
    return b"".join(sorted(canonical_json(record) + b"\n" for record in records))


def parse_records(data: bytes) -> list[Any]:
    """The records of a stored record set (one JSON value per line; blank lines carry nothing)."""
    return [parse_strict(line) for line in data.split(b"\n") if line.strip()]


# --- contract paths and the tree digest (§4.4, §4.5) ------------------------------------------------


def is_contract_path(path: Any) -> bool:
    if not isinstance(path, str) or not path or not unicodedata.is_normalized("NFC", path):
        return False
    if "\\" in path or ":" in path or any(unicodedata.category(char) == "Cc" for char in path):
        return False
    for segment in path.split("/"):
        if segment in ("", ".", "..") or segment[0] == " " or segment[-1] in (" ", "."):
            return False
    return True


def case_collisions(paths: Iterable[str]) -> list[str]:
    """Paths that differ from another one of the same tree only by letter case."""
    seen: dict[str, str] = {}
    collisions = []
    for path in paths:
        other = seen.setdefault(path.casefold(), path)
        if other != path:
            collisions.append(path)
    return collisions


def tree_listing(root: Path) -> list[dict[str, Any]]:
    """``{path, sha256, size}`` of every regular file below ``root``, at any depth. The root's own
    name, empty directories, timestamps and listing order do not enter. Raises :class:`PathInvalid`
    for a name that is not a contract path — it is not skipped — and for a symbolic link, which is
    not a file of a tree.
    """
    listing: list[dict[str, Any]] = []

    def walk(directory: Path, prefix: str) -> None:
        with os.scandir(directory) as entries:
            for entry in sorted(entries, key=lambda item: item.name):
                relative = f"{prefix}{entry.name}"
                if not is_contract_path(relative):
                    raise PathInvalid(f"not a contract path: {relative!r}")
                if entry.is_symlink():
                    raise PathInvalid(f"a symbolic link is not a file of a tree: {relative!r}")
                if entry.is_dir(follow_symlinks=False):
                    walk(Path(entry.path), relative + "/")
                elif entry.is_file(follow_symlinks=False):
                    digest, size = sha256_file(Path(entry.path))
                    listing.append({"path": relative, "sha256": digest, "size": size})
                else:
                    raise PathInvalid(f"neither a regular file nor a directory: {relative!r}")

    walk(Path(root), "")
    collisions = case_collisions(entry["path"] for entry in listing)
    if collisions:
        raise PathInvalid(f"paths that differ only by letter case: {collisions}")
    return listing


def tree_digest(root: Path) -> str:
    """The identity of a directory tree: the record-set digest of its file listing (§4.5)."""
    return record_set_digest(tree_listing(root))


# --- the schema subset (§12) ------------------------------------------------------------------------

_SCHEMA_KEYWORDS = frozenset((
    "$schema", "$id", "$defs", "$ref", "title", "description", "type", "const", "enum", "pattern", "required",
    "properties", "additionalProperties", "items", "minItems", "minimum", "minLength",
))
_REF = re.compile(r"#/\$defs/([A-Za-z0-9_]+)")
_TYPES = {
    "object": lambda value: isinstance(value, dict),
    "array": lambda value: isinstance(value, list),
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "boolean": lambda value: isinstance(value, bool),
    "null": lambda value: value is None,
}
_PATTERNS: dict[str, re.Pattern[str]] = {}


def schema_subset_problems(schema: Any, where: str = "#") -> list[str]:
    """Why a schema is outside the subset of §12 (an implementation refuses such a schema)."""
    if not isinstance(schema, dict):
        return [f"{where}: a schema is an object"]
    problems = []
    for keyword, value in schema.items():
        if keyword not in _SCHEMA_KEYWORDS:
            problems.append(f"{where}: keyword {keyword!r} is outside the subset")
        elif keyword == "additionalProperties" and value is not False:
            problems.append(f"{where}: additionalProperties is false in this subset")
        elif keyword == "$ref" and not (isinstance(value, str) and _REF.fullmatch(value)):
            problems.append(f"{where}: a reference is local, #/$defs/<name>")
        elif keyword == "type" and not all(name in _TYPES for name in ([value] if isinstance(value, str) else value)):
            problems.append(f"{where}: type {value!r} is outside the subset")
        elif keyword in ("properties", "$defs"):
            for name, sub in value.items():
                problems += schema_subset_problems(sub, f"{where}/{keyword}/{name}")
        elif keyword == "items":
            problems += schema_subset_problems(value, f"{where}/items")
    return problems


def _pattern(text: str) -> re.Pattern[str]:
    """A schema pattern is an unanchored ECMA-262 search. In Python a final ``$`` would also match
    before a trailing line feed; ``\\Z`` restores the meaning the schema has.
    """
    compiled = _PATTERNS.get(text)
    if compiled is None:
        source = text[:-1] + r"\Z" if text.endswith("$") and not text.endswith(r"\$") else text
        compiled = _PATTERNS[text] = re.compile(source)
    return compiled


def _same(left: Any, right: Any) -> bool:
    return canonical_json(left) == canonical_json(right)  # false is not 0


def schema_problems(schema: Mapping[str, Any], value: Any, root: Mapping[str, Any] | None = None, where: str = "$") -> list[str]:
    """Why ``value`` does not satisfy ``schema`` (evaluated in the subset of §12)."""
    root = schema if root is None else root
    problems: list[str] = []
    if "$ref" in schema:
        problems += schema_problems(root["$defs"][_REF.fullmatch(schema["$ref"]).group(1)], value, root, where)
    if "type" in schema:
        names = [schema["type"]] if isinstance(schema["type"], str) else schema["type"]
        if not any(_TYPES[name](value) for name in names):
            return problems + [f"{where}: not of type {'/'.join(names)}"]
    if "const" in schema and not _same(schema["const"], value):
        problems.append(f"{where}: not {schema['const']!r}")
    if "enum" in schema and not any(_same(option, value) for option in schema["enum"]):
        problems.append(f"{where}: not one of the listed values")
    if isinstance(value, str):
        if "pattern" in schema and _pattern(schema["pattern"]).search(value) is None:
            problems.append(f"{where}: does not match {schema['pattern']}")
        if len(value) < schema.get("minLength", 0):
            problems.append(f"{where}: shorter than {schema['minLength']}")
    elif isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            problems.append(f"{where}: less than {schema['minimum']}")
    elif isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            problems.append(f"{where}: fewer than {schema['minItems']} items")
        if "items" in schema:
            for index, item in enumerate(value):
                problems += schema_problems(schema["items"], item, root, f"{where}[{index}]")
    elif isinstance(value, dict):
        properties = schema.get("properties", {})
        problems += [f"{where}: {name} is missing" for name in schema.get("required", ()) if name not in value]
        for name, item in value.items():
            if name in properties:
                problems += schema_problems(properties[name], item, root, f"{where}.{name}")
            elif schema.get("additionalProperties") is False:
                problems.append(f"{where}: unknown field {name!r}")
    return problems


# --- the bundle: identity, pin, schemas (§14) -------------------------------------------------------


@dataclass(frozen=True)
class Contract:
    """The pinned bundle, verified, with its schemas by id."""

    directory: Path
    bundle_sha256: str
    schemas: Mapping[str, Mapping[str, Any]] = field(repr=False)

    def problems(self, schema_id: str, value: Any) -> list[str]:
        return schema_problems(self.schemas[schema_id], value)


def bundle_digest(directory: Path) -> str:
    """The bundle digest: the tree digest of the bundle directory (§14.1)."""
    return tree_digest(directory)


def read_pin(pins_file: Path) -> dict[str, Any]:
    """The pin of ``crosscorpus-release/v1`` in this repository's pin file."""
    try:
        pins = parse_strict(Path(pins_file).read_bytes())
    except (OSError, NonCanonical) as error:
        raise BundleRefused(f"the pin file cannot be read: {error}") from error
    pin = pins.get("contracts", {}).get(CONTRACT) if isinstance(pins, dict) and pins.get("schema") == PINS_SCHEMA else None
    if not isinstance(pin, dict) or not is_sha256(pin.get("bundle_sha256")) or not is_contract_path(pin.get("path")):
        raise BundleRefused(f"the pin file does not pin {CONTRACT} by a path and a bundle digest")
    return pin


def bundle_problems(directory: Path, expected_sha256: str) -> list[str]:
    """Why the bundle at ``directory`` is not the pinned bundle of a supported contract. Empty: it
    is. Reads; changes nothing.
    """
    directory = Path(directory)
    if not directory.is_dir():
        return [f"no bundle directory: {directory.name}"]
    try:
        listing = tree_listing(directory)
    except (PathInvalid, OSError) as error:
        return [f"the bundle is not a tree of contract paths: {error}"]
    problems = []
    present = {entry["path"] for entry in listing}
    for required in ("CONTRACT.md", "conformance/VECTORS.json"):
        if required not in present:
            problems.append(f"{required} is missing")
    if not any(path.startswith("fixtures/") for path in present):
        problems.append("fixtures/ is missing")
    digest = record_set_digest(listing)
    if digest != expected_sha256:
        problems.append(f"bundle digest {digest} is not the pinned {expected_sha256}: the copy has drifted")
    problems += _read_schemas(directory, present)[1]
    if "conformance/VECTORS.json" in present:
        try:
            if parse_strict((directory / "conformance" / "VECTORS.json").read_bytes()).get("contract") != CONTRACT:
                problems.append(f"the vectors are not those of {CONTRACT}")
        except (NonCanonical, AttributeError) as error:
            problems.append(f"the vectors cannot be read: {error}")
    return problems


def _read_schemas(directory: Path, present: set[str]) -> tuple[dict[str, Any], list[str]]:
    schemas: dict[str, Any] = {}
    problems = []
    for path in sorted(path for path in present if path.startswith("schemas/") and path.endswith(".schema.json")):
        try:
            schema = parse_strict((directory / path).read_bytes())
        except NonCanonical as error:
            problems.append(f"{path}: {error}")
            continue
        trouble = schema_subset_problems(schema)
        if trouble or not isinstance(schema.get("$id"), str):
            problems += [f"{path}: {item}" for item in trouble] or [f"{path}: no $id"]
            continue
        schemas[schema["$id"]] = schema
    for schema_id in SCHEMA_IDS:
        if schema_id not in schemas:
            problems.append(f"schema {schema_id} is missing: not a bundle of a supported contract version")
    return schemas, problems


def load_contract(directory: Path | None = None, pins_file: Path | None = None) -> Contract:
    """The bundle this repository pins — or a refusal. Fail closed: a copy whose digest is not the
    pinned one is never used, whatever it contains.
    """
    pin = read_pin(pins_file or _CHECKOUT / PINS_PATH)
    directory = Path(directory) if directory is not None else _CHECKOUT / pin["path"]
    problems = bundle_problems(directory, pin["bundle_sha256"])
    if problems:
        raise BundleRefused("; ".join(problems))
    schemas, _ = _read_schemas(directory, {entry["path"] for entry in tree_listing(directory)})
    return Contract(directory, pin["bundle_sha256"], schemas)


# --- reading documents and record sets --------------------------------------------------------------


def _document(path: Path, schema_id: str, contract: Contract, where: str) -> tuple[Any, list[Objection]]:
    """One contract document: present, strictly parsed, of this contract and schema, schema-valid."""
    if not path.is_file():
        return None, [Objection("REFERENCE_MISSING", where, "the document does not exist")]
    try:
        value = parse_strict(path.read_bytes())
    except NonCanonical as error:
        return None, [Objection("NON_CANONICAL_VALUE", where, str(error))]
    if isinstance(value, dict):
        named = [(name, value[name], expected) for name, expected in (("contract", CONTRACT), ("schema", schema_id))
                 if name in value and value[name] != expected]
        if named:
            return None, [Objection("CONTRACT_VERSION_UNSUPPORTED", where, f"{name} is {found!r}, not {expected!r}")
                          for name, found, expected in named]
    problems = contract.problems(schema_id, value)
    if problems:
        return None, [Objection("SCHEMA_VIOLATION", where, problem) for problem in problems]
    return value, []


def _record_set(path: Path, pin: Mapping[str, Any], schema_id: str, contract: Contract, where: str) -> tuple[list[Any] | None, list[Objection]]:
    """One pinned record set: present, strictly parsed, schema-valid, and exactly the pinned set."""
    if not path.is_file():
        return None, [Objection("REFERENCE_MISSING", where, "the pinned record set does not exist")]
    try:
        records = parse_records(path.read_bytes())
    except NonCanonical as error:
        return None, [Objection("NON_CANONICAL_VALUE", where, str(error))]
    objections = [Objection("SCHEMA_VIOLATION", f"{where}[{index}]", problem)
                  for index, record in enumerate(records) for problem in contract.problems(schema_id, record)]
    if len(records) != pin["records"] or record_set_digest(records) != pin["sha256"]:
        objections.append(Objection("PIN_MISMATCH", where, "the records are not the set the manifest pins"))
    return (None if objections else records), objections


def _pin_schema(pin: Mapping[str, Any], schema_id: str, where: str) -> list[Objection]:
    if pin["schema"] != schema_id:
        return [Objection("CONTRACT_VERSION_UNSUPPORTED", where, f"record schema {pin['schema']!r}, not {schema_id!r}")]
    return []


def _state_problems(value: Any, where: str) -> list[str]:
    """§5.1: a stateful value is null exactly when its state is not ``known`` — for ``<field>`` /
    ``<field>_state`` pairs and for the pin shapes ``{state, …}``.
    """
    problems: list[str] = []
    if isinstance(value, list):
        for index, item in enumerate(value):
            problems += _state_problems(item, f"{where}[{index}]")
    elif isinstance(value, dict):
        for name, item in value.items():
            if name.endswith("_state") and name[:-6] in value and (value[name[:-6]] is None) == (item == KNOWN):
                problems.append(f"{where}.{name[:-6]}: null exactly when its state is not known")
            problems += _state_problems(item, f"{where}.{name}")
        if value.get("state") in STATES:
            for name, item in value.items():
                if name != "state" and (item is None) == (value["state"] == KNOWN):
                    problems.append(f"{where}.{name}: null exactly when the state is not known")
    return problems


def _duplicates(values: Iterable[Any]) -> list[Any]:
    seen: set[Any] = set()
    return sorted({value for value in values if value in seen or seen.add(value)})  # type: ignore[func-returns-value]


def stateful_sum(rows: Sequence[Mapping[str, Any]], name: str) -> tuple[int | None, str]:
    """The sum of a stateful count over documents (§7.3): known with the sum if every value is
    known; otherwise null with the documents' common state, or ``not_available`` if they share none.
    A partial sum is never a total.
    """
    states = {row[f"{name}_state"] for row in rows}
    if states <= {KNOWN}:
        return sum(row[name] for row in rows), KNOWN
    return None, states.pop() if len(states) == 1 else NOT_AVAILABLE


def derive_coverage(documents: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The coverage of a release: fully determined by its document records (§7.3)."""
    cells: dict[tuple, list[Mapping[str, Any]]] = {}
    for document in documents:
        key = (document["country_id"], document["outlet_id"], document["cohort"], document["cohort_state"],
               document["date_basis"], document["date_basis_state"])
        cells.setdefault(key, []).append(document)
    coverage = []
    for (country, outlet, cohort, cohort_state, basis, basis_state), rows in cells.items():
        tokens, tokens_state = stateful_sum(rows, "tokens_counted")
        audio, audio_state = stateful_sum(rows, "audio_ms")
        coverage.append({"country_id": country, "outlet_id": outlet, "cohort": cohort, "cohort_state": cohort_state,
                         "date_basis": basis, "date_basis_state": basis_state, "documents": len(rows),
                         "tokens_counted": tokens, "tokens_counted_state": tokens_state,
                         "audio_ms": audio, "audio_ms_state": audio_state})
    return coverage


def cohort_of(date: str) -> str:
    """The calendar quarter of a date, ``YYYY-Qn`` (§7.2). Raises for a date that does not exist."""
    day = _datetime.date.fromisoformat(date)
    return f"{day.year:04d}-Q{(day.month - 1) // 3 + 1}"


# --- release (§13.1) --------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Release:
    manifest: Mapping[str, Any]
    manifest_sha256: str
    members: Sequence[Mapping[str, Any]]
    documents: Sequence[Mapping[str, Any]]


def _manifest_rules(manifest: Mapping[str, Any]) -> list[Objection]:
    """§5.2 and §5.4: what the schema subset cannot state about a release manifest."""
    where = RELEASE_MANIFEST
    objections = [o for name, schema_id in (("members", MEMBER_SCHEMA), ("documents", DOCUMENT_SCHEMA), ("coverage", COVERAGE_SCHEMA))
                  for o in _pin_schema(manifest[name], schema_id, f"{where}.{name}")]
    problems = _state_problems(manifest, "$")
    kind, modality, anchors = manifest["release_kind"], manifest["modality"], manifest["anchors"]
    if manifest["fixture"] != (kind == "fixture"):
        problems.append("$.fixture: true exactly for release_kind fixture")
    if kind == "release" and manifest["selection_policy"]["state"] != KNOWN:
        problems.append("$.selection_policy: a release pins its selection policy")
    denominator_known = manifest["token_denominator_state"] == KNOWN
    if denominator_known and manifest["token_denominator"] != TOKEN_DENOMINATOR:
        problems.append(f"$.token_denominator: a count is a count under {TOKEN_DENOMINATOR} and nothing else")
    if manifest["totals"]["tokens_counted_state"] == KNOWN and not denominator_known:
        problems.append("$.totals.tokens_counted: a token count names its denominator")
    allowed = ANCHORS[modality]
    for name in ("document_kind", "source_kind"):
        if anchors[name] != allowed[name]:
            problems.append(f"$.anchors.{name}: {anchors[name]!r} is not a kind of a {modality} release")
    for name in ("unit_kinds", "producer_kinds"):
        foreign = [kind_ for kind_ in anchors[name] if kind_ not in allowed[name]]
        if foreign or _duplicates(anchors[name]):
            problems.append(f"$.anchors.{name}: {foreign or _duplicates(anchors[name])} not valid for a {modality} release")
    if (anchors["time_reference_state"] != NOT_APPLICABLE) != (modality == "spoken"):
        problems.append("$.anchors.time_reference: exactly a spoken release has a time reference")
    layer = manifest["analysis_layer"]
    if layer["state"] == KNOWN and layer["contract"] != ANALYSIS_CONTRACT:
        problems.append(f"$.analysis_layer: known exactly when it names {ANALYSIS_CONTRACT} and a digest")
    for name in ("date_basis", "export_schema"):
        if _duplicates(manifest["vocabularies"][name]):
            problems.append(f"$.vocabularies.{name}: a value is listed twice")
    objections += [Objection("SCHEMA_VIOLATION", where, problem) for problem in problems]

    release_id, prefix = manifest["release_id"], manifest["corpus_id"] + "-"
    trouble = []
    if not release_id.startswith(prefix):
        trouble.append("a release id begins with its corpus id")
    elif release_id[len(prefix):].startswith("0000") != (kind == "fixture"):
        trouble.append("a suffix beginning with 0000 marks a fixture, and only a fixture")
    previous = manifest["previous_release"]["release_id"]
    if previous is not None and (not previous.startswith(prefix) or previous == release_id):
        trouble.append("the predecessor is another release of the same corpus")
    return objections + [Objection("RELEASE_ID_INVALID", where, problem) for problem in trouble]


def _membership(manifest: Mapping[str, Any], members: Sequence[Mapping[str, Any]], documents: Sequence[Mapping[str, Any]],
                previous: _Release | None) -> list[Objection]:
    """§6.1 and §9.3."""
    problems = []
    ids = [member["export_id"] for member in members]
    if _duplicates(ids):
        problems.append(f"an export is a member twice: {_duplicates(ids)}")
    delivered: dict[str, int] = {}
    for document in documents:
        delivered[document["export_id"]] = delivered.get(document["export_id"], 0) + 1
    for member in members:
        if member["export_schema"] not in manifest["vocabularies"]["export_schema"]:
            problems.append(f"{member['export_id']}: export schema {member['export_schema']!r} is not declared by the release")
        if member["documents"] != delivered.get(member["export_id"], 0):
            problems.append(f"{member['export_id']}: states {member['documents']} documents, the document index has "
                            f"{delivered.get(member['export_id'], 0)}")
    changes, now = manifest["changes"], set(ids)
    added, removed = list(changes["added"]), [item["export_id"] for item in changes["removed"]]
    old, new = [item["old"] for item in changes["replaced"]], [item["new"] for item in changes["replaced"]]
    if _duplicates(added + new) or _duplicates(removed + old) or set(added + new) & set(removed + old):
        problems.append("changes: an export is accounted for more than once")
    if not set(added + new) <= now:
        problems.append(f"changes: added or replacing exports that are not members: {sorted(set(added + new) - now)}")
    if set(removed + old) & now:
        problems.append(f"changes: removed or replaced exports that are still members: {sorted(set(removed + old) & now)}")
    if manifest["previous_release"]["state"] != KNOWN:
        if set(added) != now or new or removed:
            problems.append("changes: a first release adds exactly its members")
    elif previous is not None:
        before = {member["export_id"]: member for member in previous.members}
        if not set(removed + old) <= set(before) or set(added + new) & set(before):
            problems.append("changes: do not fit the members of the previous release")
        if (set(before) - set(removed + old)) | set(added + new) != now:
            problems.append("changes: a difference of membership to the previous release is not accounted for")
        for member in members:
            if member["export_id"] in before and canonical_json(before[member["export_id"]]) != canonical_json(member):
                problems.append(f"{member['export_id']}: is not the export the previous release names by this id")
    return [Objection("MEMBERSHIP_INCONSISTENT", MEMBERS, problem) for problem in problems]


def _document_rules(manifest: Mapping[str, Any], members: Sequence[Mapping[str, Any]], documents: Sequence[Mapping[str, Any]]) -> list[Objection]:
    """§7.1 and §7.2."""
    problems = []
    if _duplicates(document["document_id"] for document in documents):
        problems.append(f"a document id is repeated: {_duplicates(d['document_id'] for d in documents)}")
    exports = {member["export_id"] for member in members}
    bases, written = manifest["vocabularies"]["date_basis"], manifest["modality"] == "written"
    for document in documents:
        name = document["document_id"]
        problems += [f"{name}: {problem}" for problem in _state_problems(document, "$")]
        if document["export_id"] not in exports:
            problems.append(f"{name}: delivered by {document['export_id']!r}, which is not a member")
        if not document["outlet_id"].startswith(document["country_id"] + "_"):
            problems.append(f"{name}: the outlet is not registered under the country")
        dated = document["date_state"] == KNOWN
        if dated != (document["date_basis_state"] == KNOWN):
            problems.append(f"{name}: a date and its basis are known together or not at all")
        if document["date_basis"] is not None and document["date_basis"] not in bases:
            problems.append(f"{name}: date basis {document['date_basis']!r} is not in the release's vocabulary")
        quarter = None
        if document["date"] is not None:
            try:
                quarter = cohort_of(document["date"])
            except ValueError:
                problems.append(f"{name}: {document['date']!r} is not a calendar date")
        if document["cohort_state"] == KNOWN and (not dated or document["cohort"] != quarter):
            problems.append(f"{name}: a cohort is known only with its date and contains it")
        if (document["audio_ms_state"] == NOT_APPLICABLE) != written:
            problems.append(f"{name}: audio_ms is not_applicable for a written document, and only for one")
        if document["tokens_counted_state"] == KNOWN and manifest["token_denominator_state"] != KNOWN:
            problems.append(f"{name}: a token count names its denominator")
    return [Objection("DOCUMENT_INCONSISTENT", DOCUMENTS, problem) for problem in problems]


def _totals(manifest: Mapping[str, Any], members: Sequence[Any], documents: Sequence[Mapping[str, Any]]) -> list[Objection]:
    tokens, tokens_state = stateful_sum(documents, "tokens_counted")
    audio, audio_state = stateful_sum(documents, "audio_ms")
    derived = {"exports": len(members), "documents": len(documents), "tokens_counted": tokens,
               "tokens_counted_state": tokens_state, "audio_ms": audio, "audio_ms_state": audio_state}
    if not _same(derived, manifest["totals"]):
        return [Objection("TOTALS_MISMATCH", RELEASE_MANIFEST, f"the records give {derived}")]
    return []


def _exports(members: Sequence[Mapping[str, Any]], exports_root: Path) -> list[Objection]:
    objections = []
    for member in members:
        where, directory = f"exports/{member['export_id']}", Path(exports_root) / member["export_id"]
        if not directory.is_dir():
            objections.append(Objection("EXPORT_MISSING", where, "the release names an export that is not available"))
            continue
        try:
            listing = tree_listing(directory)
        except PathInvalid as error:
            objections.append(Objection("PATH_INVALID", where, str(error)))
            continue
        found = (record_set_digest(listing), len(listing), sum(entry["size"] for entry in listing))
        if found != (member["tree_sha256"], member["files"], member["bytes"]):
            objections.append(Objection("EXPORT_TREE_MISMATCH", where, "the export is not the tree the member record names"))
    return objections


def _freeze(directory: Path, manifest: Mapping[str, Any], digest: str, contract: Contract) -> list[Objection]:
    record, objections = _document(directory / RELEASE_FREEZE, FREEZE_SCHEMA, contract, RELEASE_FREEZE)
    if objections:
        return objections
    named = (record["corpus_id"], record["release_id"], record["release_manifest_sha256"])
    if named != (manifest["corpus_id"], manifest["release_id"], digest):
        return [Objection("FREEZE_MISMATCH", RELEASE_FREEZE, "the freeze record does not name this manifest")]
    return []


def _check_release(directory: Path, contract: Contract, *, exports_root: Path | None, require_exports: bool,
                   previous_directory: Path | None) -> tuple[_Release | None, list[Objection]]:
    directory = Path(directory)
    manifest, objections = _document(directory / RELEASE_MANIFEST, MANIFEST_SCHEMA, contract, RELEASE_MANIFEST)  # phase 1
    objections = objections or _manifest_rules(manifest)
    if objections:
        return None, objections
    sets: dict[str, Any] = {}                                                                          # phase 2
    for name, file_name, schema_id in (("members", MEMBERS, MEMBER_SCHEMA), ("documents", DOCUMENTS, DOCUMENT_SCHEMA),
                                       ("coverage", COVERAGE, COVERAGE_SCHEMA)):
        sets[name], trouble = _record_set(directory / file_name, manifest[name], schema_id, contract, file_name)
        objections += trouble
    if objections:
        return None, objections
    release = _Release(manifest, document_digest(manifest), sets["members"], sets["documents"])

    previous = None                                                                                    # phase 3
    if previous_directory is not None:
        previous, trouble = _check_release(Path(previous_directory), contract, exports_root=None, require_exports=False,
                                           previous_directory=None)
        named = manifest["previous_release"]
        if previous is None and any(o.code == "REFERENCE_MISSING" and o.where == RELEASE_MANIFEST for o in trouble):
            objections.append(Objection("REFERENCE_MISSING", "previous release", "the previous release is not available"))
        elif previous is None or (previous.manifest["release_id"], previous.manifest_sha256) != (
                named["release_id"], named["release_manifest_sha256"]):
            objections.append(Objection("PREVIOUS_RELEASE_MISMATCH", "previous release",
                                        "the release at hand is not the predecessor the manifest names"))
            previous = None
    objections += _membership(manifest, release.members, release.documents, previous)
    objections += _document_rules(manifest, release.members, release.documents)
    if not objections:
        derived, stored = derive_coverage(release.documents), sets["coverage"]
        if sorted(map(canonical_json, derived)) != sorted(map(canonical_json, stored)):
            objections.append(Objection("COVERAGE_MISMATCH", COVERAGE, "the coverage is not what the document index implies"))
        objections += _totals(manifest, release.members, release.documents)
    if objections:
        return None, objections

    if require_exports and exports_root is None:                                                       # phase 4
        raise ValueError("exports are required: name the exports root")
    if exports_root is not None:
        objections = _exports(release.members, Path(exports_root))
        if objections:
            return None, objections

    if manifest["release_kind"] != "provisional_export":                                               # phase 5
        objections = _freeze(directory, manifest, release.manifest_sha256, contract)
        if objections:
            return None, objections
    return release, []


def verify_release(directory: Path, *, exports_root: Path | None = None, require_exports: bool = False,
                   previous_directory: Path | None = None, contract: Contract | None = None) -> Verdict:
    """Check a release directory (§13.1). With ``exports_root`` every member export is re-hashed;
    without it the verdict proves only that the manifest side is consistent, and says so.
    """
    _, objections = _check_release(Path(directory), contract or load_contract(), exports_root=exports_root,
                                   require_exports=require_exports, previous_directory=previous_directory)
    return Verdict("release", tuple(objections), exports_checked=exports_root is not None)


def release_manifest_digest(directory: Path) -> str:
    """The document digest of the manifest in a release directory — what a referrer records."""
    return document_digest(parse_strict((Path(directory) / RELEASE_MANIFEST).read_bytes()))


def _pinned_release(directory: Path | None, release_id: str, digest: str, contract: Contract, *, exports_root: Path | None,
                    where: str) -> tuple[_Release | None, list[Objection]]:
    """A release a study or a package names by id and manifest digest: available, the named one,
    and conformant. A release that is not the named one is reported as that and not examined
    further: its own state is not the subject of the check.
    """
    if directory is None or not (Path(directory) / RELEASE_MANIFEST).is_file():
        return None, [Objection("REFERENCE_MISSING", where, f"release {release_id} is not available")]
    try:
        manifest = parse_strict((Path(directory) / RELEASE_MANIFEST).read_bytes())
        found = (manifest.get("release_id") if isinstance(manifest, dict) else None, document_digest(manifest))
    except NonCanonical:
        found = (None, "")
    if found != (release_id, digest):
        return None, [Objection("RELEASE_PIN_MISMATCH", where, f"the release at hand is not {release_id} with the pinned manifest digest")]
    return _check_release(Path(directory), contract, exports_root=exports_root, require_exports=exports_root is not None,
                          previous_directory=None)


# --- study population (§10, §13.1) ------------------------------------------------------------------


def _study_rules(study: Mapping[str, Any]) -> list[Objection]:
    where = STUDY_POPULATION
    objections = [o for name in ("selected", "excluded") for o in _pin_schema(study[name], SELECTION_SCHEMA, f"{where}.{name}")]
    problems = _state_problems(study, "$")
    corpora = [entry["corpus_id"] for entry in study["inputs"]]
    if _duplicates(corpora):
        problems.append("$.inputs: one entry per corpus")
    for entry in study["inputs"]:
        if not entry["release_id"].startswith(entry["corpus_id"] + "-"):
            problems.append(f"$.inputs: {entry['release_id']} is not a release of {entry['corpus_id']}")
        if entry["analysis_layer"]["state"] == KNOWN and entry["analysis_layer"]["contract"] != ANALYSIS_CONTRACT:
            problems.append(f"$.inputs: an analysis layer is known exactly when it names {ANALYSIS_CONTRACT} and a digest")
    if sorted(entry["corpus_id"] for entry in study["totals"]) != sorted(corpora):
        problems.append("$.totals: one entry per corpus of the inputs")
    if _duplicates(study["exclusion_reasons"]):
        problems.append("$.exclusion_reasons: a reason is listed twice")
    selection = study["selection"]
    if selection["kind"] == "declarative_filter":
        if selection["filter_language"] != FILTER_LANGUAGE:
            problems.append(f"$.selection: a declarative selection is written in {FILTER_LANGUAGE}")
        if _duplicates(entry["corpus_id"] for entry in selection["filters"]) or not {e["corpus_id"] for e in selection["filters"]} <= set(corpora):
            problems.append("$.selection.filters: at most one filter per corpus of the inputs")
        for entry in selection["filters"]:
            for clause in entry["all"]:
                operators = sorted(name for name in clause if name != "field")
                name = clause["field"]
                fits = operators == ["in"] if name in _FILTER_IN else (
                    bool(operators) and set(operators) <= set(_FILTER_RANGE[name]) if name in _FILTER_RANGE else False)
                if not fits:
                    problems.append(f"$.selection.filters: {name!r} with {operators} is not a clause of {FILTER_LANGUAGE}")
    return objections + [Objection("SCHEMA_VIOLATION", where, problem) for problem in problems]


def _satisfies(document: Mapping[str, Any], clause: Mapping[str, Any]) -> bool:
    name = clause["field"]
    if name in _FILTER_STATEFUL and document[f"{name}_state"] != KNOWN:
        return False  # a clause on a stateful field is not satisfied by a value that is not known
    value = document[name]
    if "in" in clause:
        return value in clause["in"]
    low, high = _FILTER_RANGE[name]
    return (low not in clause or value >= clause[low]) and (high not in clause or value <= clause[high])


def filter_documents(documents: Sequence[Mapping[str, Any]], clauses: Sequence[Mapping[str, Any]]) -> list[str]:
    """The document ids a conjunction of ``crosscorpus-document-filter/v1`` clauses selects (§10.3)."""
    return sorted(document["document_id"] for document in documents if all(_satisfies(document, clause) for clause in clauses))


def study_totals(corpus_id: str, selected: Sequence[Mapping[str, Any]], documents: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The totals of one corpus in a study population, re-derived (§10.3)."""
    own = [record for record in selected if record["corpus_id"] == corpus_id]
    ids = {record["document_id"] for record in own}
    if all(record["level"] == "document" for record in own):
        rows = [document for document in documents if document["document_id"] in ids]
        tokens, tokens_state = stateful_sum(rows, "tokens_counted")
        audio, audio_state = stateful_sum(rows, "audio_ms")
    else:  # below the document the document records cannot give a count
        tokens = audio = None
        tokens_state = audio_state = NOT_AVAILABLE
    return {"corpus_id": corpus_id, "selected_records": len(own), "documents": len(ids), "tokens_counted": tokens,
            "tokens_counted_state": tokens_state, "audio_ms": audio, "audio_ms_state": audio_state}


def verify_study(directory: Path, releases: Mapping[str, Path], *, contract: Contract | None = None) -> Verdict:
    """Check a study population (§13.1). ``releases`` maps a ``release_id`` to the release directory
    at hand. The population is restored by resolving its frozen ids against the pinned releases.
    """
    contract, directory = contract or load_contract(), Path(directory)

    def verdict(objections: list[Objection]) -> Verdict:
        return Verdict("study", tuple(objections))

    study, objections = _document(directory / STUDY_POPULATION, STUDY_SCHEMA, contract, STUDY_POPULATION)   # phase 1
    objections = objections or _study_rules(study)
    if objections:
        return verdict(objections)

    pinned: dict[str, _Release] = {}                                                                      # phase 2
    for entry in study["inputs"]:
        release, trouble = _pinned_release(releases.get(entry["release_id"]), entry["release_id"], entry["release_manifest_sha256"],
                                           contract, exports_root=None, where=f"inputs.{entry['corpus_id']}")
        objections += trouble
        if release is not None:
            if release.manifest["corpus_id"] != entry["corpus_id"]:
                objections.append(Objection("RELEASE_PIN_MISMATCH", f"inputs.{entry['corpus_id']}", "the release is of another corpus"))
            pinned[entry["corpus_id"]] = release
    sets = {}
    for name, file_name in (("selected", SELECTED), ("excluded", EXCLUDED)):
        sets[name], trouble = _record_set(directory / file_name, study[name], SELECTION_SCHEMA, contract, file_name)
        objections += trouble
    if objections:
        return verdict(objections)
    selected, excluded = sets["selected"], sets["excluded"]

    release_of = {entry["corpus_id"]: entry["release_id"] for entry in study["inputs"]}                   # phase 3
    seen: set[tuple[str, str, str, str]] = set()
    for file_name, records in ((SELECTED, selected), (EXCLUDED, excluded)):
        for record in records:
            where = f"{file_name}: {record['id']}"
            if release_of.get(record["corpus_id"]) != record["release_id"]:
                objections.append(Objection("POPULATION_NOT_RESTORABLE", where, "names a release the study does not pin"))
                continue
            release = pinned[record["corpus_id"]]
            anchors = release.manifest["anchors"]
            kinds = {"document": [anchors["document_kind"]], "unit": anchors["unit_kinds"], "producer": anchors["producer_kinds"]}
            if record["id_kind"] not in kinds[record["level"]]:
                objections.append(Objection("ANCHOR_KIND_INVALID", where,
                                            f"{record['id_kind']!r} is not a {record['level']} anchor the pinned release declares"))
            if record["document_id"] not in {document["document_id"] for document in release.documents}:
                objections.append(Objection("POPULATION_NOT_RESTORABLE", where, "its document is not in the pinned release"))
            elif record["level"] == "document" and record["id"] != record["document_id"]:
                objections.append(Objection("POPULATION_NOT_RESTORABLE", where, "at document level the id is the document id"))
            is_excluded = file_name == EXCLUDED
            if (record["reason"] is not None) != is_excluded or (is_excluded and record["reason"] not in study["exclusion_reasons"]):
                objections.append(Objection("POPULATION_SELECTION_MISMATCH", where,
                                            "exactly an excluded record states a reason, from the population's vocabulary"))
            key = (record["corpus_id"], record["level"], record["id_kind"], record["id"])
            if key in seen:
                objections.append(Objection("POPULATION_SELECTION_MISMATCH", where, "an id is selected or excluded, never both, never twice"))
            seen.add(key)
    if objections:
        return verdict(objections)

    if study["selection"]["kind"] == "declarative_filter":                                                # phase 4
        clauses = {entry["corpus_id"]: entry["all"] for entry in study["selection"]["filters"]}
        for corpus_id, release in pinned.items():
            frozen = [record for record in selected + excluded if record["corpus_id"] == corpus_id]
            expected = filter_documents(release.documents, clauses[corpus_id]) if corpus_id in clauses else []
            if any(record["level"] != "document" for record in frozen) or sorted(record["id"] for record in frozen) != expected:
                objections.append(Objection("POPULATION_SELECTION_MISMATCH", f"selection.{corpus_id}",
                                            "the declared filter, re-run on the pinned documents, does not give the frozen ids"))
    for stated in study["totals"]:
        derived = study_totals(stated["corpus_id"], selected, pinned[stated["corpus_id"]].documents)
        if not _same(derived, stated):
            objections.append(Objection("TOTALS_MISMATCH", f"totals.{stated['corpus_id']}", f"the records give {derived}"))
    return verdict(objections)


# --- package (§11, §13.1) ---------------------------------------------------------------------------


def _package_rules(package: Mapping[str, Any]) -> list[Objection]:
    where = PACKAGE_MANIFEST
    objections = _pin_schema(package["files"], PACKAGE_FILE_SCHEMA, f"{where}.files")
    problems = _state_problems(package, "$")
    release = package["release"]
    if not release["release_id"].startswith(release["corpus_id"] + "-"):
        problems.append("$.release: the release id begins with its corpus id")
    if package["package_kind"] == "archive" and package["exports"] != "included":
        problems.append("$.exports: an archive package is self-contained")
    if package["metadata"]["version"] != release["release_id"]:
        problems.append("$.metadata.version: the version of a package is the release id")
    return objections + [Objection("SCHEMA_VIOLATION", where, problem) for problem in problems]


def _listed_files(package: Mapping[str, Any], files: Sequence[Mapping[str, Any]]) -> list[Objection]:
    """Phase 3 of the package check: paths, forbidden content, roles."""
    objections = []
    paths = [entry["path"] for entry in files]
    for path in paths:
        if not is_contract_path(path):
            objections.append(Objection("PATH_INVALID", PACKAGE_FILES, f"not a contract path: {path!r}"))
    for path in case_collisions(path for path in dict.fromkeys(paths)):
        objections.append(Objection("PATH_INVALID", PACKAGE_FILES, f"differs from another path only by letter case: {path!r}"))
    for path in paths:
        if path.casefold().endswith(FORBIDDEN_SUFFIXES):
            objections.append(Objection("PACKAGE_FORBIDDEN_CONTENT", PACKAGE_FILES, f"source media are not part of a package: {path!r}"))
    problems = [f"listed twice: {path!r}" for path in _duplicates(paths)]
    for entry in files:
        path, role = entry["path"], entry["role"]
        if path in (PACKAGE_MANIFEST, PACKAGE_FILES):
            problems.append(f"{path} describes the package and is not listed")
        elif path.startswith("release/") or role in RELEASE_FILE_ROLES.values():
            if RELEASE_FILE_ROLES.get(path) != role:
                problems.append(f"{path!r} with role {role!r}: release/ holds exactly the five release files, each under its role")
        elif path.startswith("exports/") != (role == "export_payload"):
            problems.append(f"{path!r} with role {role!r}: exports/ holds the export payload and nothing else does")
    problems += [f"{path} is not listed" for path in RELEASE_FILE_ROLES if path not in paths]
    if package["exports"] == "by_reference" and any(entry["role"] == "export_payload" for entry in files):
        problems.append("exports are by reference, yet export payload is listed")
    return objections + [Objection("PACKAGE_INCOMPLETE", PACKAGE_FILES, problem) for problem in problems]


def verify_package(directory: Path, *, exports_root: Path | None = None, contract: Contract | None = None) -> Verdict:
    """Check a distribution or archive package (§13.1). When the exports are included they are
    re-hashed as part of the release inside; ``exports_root`` supplies them for a package that
    names them by reference.
    """
    contract, directory = contract or load_contract(), Path(directory)

    def verdict(objections: list[Objection], exports_checked: bool = False) -> Verdict:
        return Verdict("package", tuple(objections), exports_checked=exports_checked)

    package, objections = _document(directory / PACKAGE_MANIFEST, PACKAGE_SCHEMA, contract, PACKAGE_MANIFEST)   # phase 1
    objections = objections or _package_rules(package)
    if objections:
        return verdict(objections)
    files, objections = _record_set(directory / PACKAGE_FILES, package["files"], PACKAGE_FILE_SCHEMA, contract, PACKAGE_FILES)  # 2
    objections = objections or _listed_files(package, files)                                                # phase 3
    if objections:
        return verdict(objections)

    try:                                                                                                    # phase 4
        on_disk = [entry for entry in tree_listing(directory) if entry["path"] not in (PACKAGE_MANIFEST, PACKAGE_FILES)]
    except PathInvalid as error:
        return verdict([Objection("PATH_INVALID", "package", str(error))])
    listed = {entry["path"]: (entry["sha256"], entry["size"]) for entry in files}
    found = {entry["path"]: (entry["sha256"], entry["size"]) for entry in on_disk}
    for path in sorted(set(listed) | set(found)):
        if listed.get(path) != found.get(path):
            state = "is missing" if path not in found else "is not listed" if path not in listed else "is not the listed file"
            objections.append(Objection("PACKAGE_INCOMPLETE", path, state))
    if objections:
        return verdict(objections)

    included = package["exports"] == "included"                                                             # phase 5
    root = directory / "exports" if included else exports_root
    _, objections = _pinned_release(directory / "release", package["release"]["release_id"], package["release"]["release_manifest_sha256"],
                                    contract, exports_root=root, where="release")
    return verdict(objections, exports_checked=root is not None)


# --- command line -----------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"Checks of {CONTRACT}. Reads; never repairs.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bundle", help="is the contract bundle of this checkout the pinned one")
    release = commands.add_parser("verify-release")
    release.add_argument("directory", type=Path)
    release.add_argument("--exports", type=Path, default=None, help="exports root; without it only the manifest side is checked")
    release.add_argument("--previous", type=Path, default=None)
    package = commands.add_parser("verify-package")
    package.add_argument("directory", type=Path)
    package.add_argument("--exports", type=Path, default=None)
    study = commands.add_parser("verify-study")
    study.add_argument("directory", type=Path)
    study.add_argument("--release", action="append", default=[], metavar="RELEASE_ID=DIRECTORY")
    arguments = parser.parse_args(argv)
    try:
        contract = load_contract()
    except BundleRefused as refusal:
        print(json.dumps({"bundle": "REFUSED", "reason": str(refusal)}, indent=2))
        return 2
    if arguments.command == "bundle":
        print(json.dumps({"bundle": "PINNED", "contract": CONTRACT, "bundle_sha256": contract.bundle_sha256}, indent=2))
        return 0
    if arguments.command == "verify-release":
        verdict = verify_release(arguments.directory, exports_root=arguments.exports, previous_directory=arguments.previous, contract=contract)
    elif arguments.command == "verify-package":
        verdict = verify_package(arguments.directory, exports_root=arguments.exports, contract=contract)
    else:
        verdict = verify_study(arguments.directory, {name: Path(place) for name, _, place in (item.partition("=") for item in arguments.release)},
                               contract=contract)
    print(json.dumps(verdict.as_record(), indent=2, ensure_ascii=False))
    return 0 if verdict.conformant else 1


if __name__ == "__main__":
    raise SystemExit(main())
