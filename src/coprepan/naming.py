"""Machine-facing naming contract of COPREPAN 3.0.

Normative source: ``docs/architecture/TERMINOLOGY_AND_NAMING.md`` (decision CPD-0002). This module
holds only the parts of that contract that are frozen: the corpus and generation tokens, the
provenance classes, and the lexical form of ``country_id``, ``outlet_id``, ``release_id`` and
schema ids. The serialisation of fetch, document, document-version, sentence and token ids is
frozen by the Phase-1 identity run and is deliberately absent here.

A validator checks the *form* of an id. Whether an id is *registered* is a registry question.
"""

from __future__ import annotations

import re

CORPUS_ID = "coprepan"
SIBLING_CORPUS_ID = "corapan"
CORPUS_IDS = (SIBLING_CORPUS_ID, CORPUS_ID)

# The generation is an attribute of material and of a pipeline; it is never part of a corpus id,
# a release id or a schema id.
GENERATION = "v3"
GENERATIONS = ("legacy", GENERATION)

PROVENANCE_CLASSES = (
    "native_v3",
    "legacy_refetched",
    "legacy_text_reannotated",
    "legacy_frozen",
)

# The frozen state of the legacy corpus (planned release; see docs/legacy/INDEX.md).
LEGACY_RELEASE_ID = "coprepan-legacy-2026-06"

# Namespace of schema and contract ids minted by this repository.
SCHEMA_NAMESPACE = "coprepan"

_COUNTRY_ID = re.compile(r"[a-z]{2}")
_OUTLET_ID = re.compile(r"[a-z]{2}_[a-z0-9]+(?:_[a-z0-9]+)*")
_RELEASE_ID = re.compile(r"(?P<corpus>[a-z]+)-(?:(?P<year>\d{4})\.(?P<seq>[1-9]\d*)|legacy-\d{4}-\d{2})")
_SCHEMA_ID = re.compile(r"(?P<namespace>[a-z]+)-(?P<thing>[a-z0-9]+(?:-[a-z0-9]+)*)/v(?P<version>[1-9]\d*)")


def is_country_id(value: str) -> bool:
    """ISO 3166-1 alpha-2, lower case. Form only: membership is decided by the registry."""
    return isinstance(value, str) and _COUNTRY_ID.fullmatch(value) is not None


def is_outlet_id(value: str) -> bool:
    """``{country_id}_{outlet}``: ASCII, lower case, underscore-separated (``uy_el_pais``)."""
    return isinstance(value, str) and _OUTLET_ID.fullmatch(value) is not None


def outlet_country(outlet_id: str) -> str:
    """The ``country_id`` an ``outlet_id`` is registered under."""
    if not is_outlet_id(outlet_id):
        raise ValueError(f"not an outlet_id: {outlet_id!r}")
    return outlet_id[:2]


def is_release_id(value: str, corpus_id: str = CORPUS_ID) -> bool:
    """``<corpus_id>-<YYYY>.<n>`` or the frozen legacy form ``<corpus_id>-legacy-<YYYY>-<MM>``."""
    if not isinstance(value, str):
        return False
    match = _RELEASE_ID.fullmatch(value)
    return match is not None and match.group("corpus") == corpus_id


def is_schema_id(value: str, namespace: str = SCHEMA_NAMESPACE) -> bool:
    """``<namespace>-<thing>/v<n>``; the ``v<n>`` is the version of the schema and nothing else."""
    if not isinstance(value, str):
        return False
    match = _SCHEMA_ID.fullmatch(value)
    return match is not None and match.group("namespace") == namespace


def schema_id(thing: str, version: int, namespace: str = SCHEMA_NAMESPACE) -> str:
    """Build a schema id and refuse a malformed one."""
    value = f"{namespace}-{thing}/v{version}"
    if not is_schema_id(value, namespace):
        raise ValueError(f"not a schema id: {value!r}")
    return value
