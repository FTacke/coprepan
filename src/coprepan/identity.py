"""Id serialisation and the canonical URL key (frozen by decision CPD-0003).

Normative sources: ``docs/architecture/TERMINOLOGY_AND_NAMING.md`` §5.4 (the forms),
``docs/architecture/TARGET_ARCHITECTURE.md`` §6 (the URL key), ``docs/identity/INDEX.md`` (the
byte-level rules implemented here).

This module *computes and checks* ids. It mints nothing: an id belongs to production material only
when a stage has recorded it, and no such stage exists yet (``docs/STATUS.md``).

Hash function everywhere: SHA-256, lower-case hexadecimal. A truncated digest is a prefix of it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence
from urllib.parse import urlsplit

from . import naming
from .canonical import canonical_json, require_sha256, sha256_bytes

# --- serialisation versions -----------------------------------------------------------------------

FETCH_ID_PREFIX = "ft1"
FETCH_ID_SCHEMA = naming.schema_id("fetch-id", 1)
URL_KEY_RULESET = naming.schema_id("url-key", 1)

DOCUMENT_HASH_LENGTH = 16
VERSION_HASH_LENGTH = 12
TOKEN_INDEX_WIDTH = 8
TOKEN_INDEX_LIMIT = 10**TOKEN_INDEX_WIDTH

_OUTLET = r"[a-z]{2}_[a-z0-9]+(?:_[a-z0-9]+)*"
_FETCH_ID = re.compile(rf"{FETCH_ID_PREFIX}:[0-9a-f]{{64}}")
_DOCUMENT_ID = re.compile(rf"(?P<outlet>{_OUTLET}):doc:(?P<hash>[0-9a-f]{{{DOCUMENT_HASH_LENGTH}}})")
_VERSION_ID = re.compile(
    rf"(?P<document>{_OUTLET}:doc:[0-9a-f]{{{DOCUMENT_HASH_LENGTH}}})"
    rf":v:(?P<hash>[0-9a-f]{{{VERSION_HASH_LENGTH}}})"
)
_CHILD_ID = re.compile(
    rf"(?P<version>{_OUTLET}:doc:[0-9a-f]{{{DOCUMENT_HASH_LENGTH}}}:v:[0-9a-f]{{{VERSION_HASH_LENGTH}}})"
    r":(?P<kind>UNIT|SENT|TOKEN):(?P<index>\d+)"
)
_CHANNEL_SLUG = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*")

# Characters that never belong in a URL as transmitted: C0 controls, space, DEL.
_FORBIDDEN_IN_URL = re.compile(r"[\x00-\x20\x7f]")


class IdentityError(ValueError):
    """An input cannot be turned into an id, or a value is not an id of the stated kind."""


class OffOriginError(IdentityError):
    """No candidate URL lies on a registered web origin of the outlet."""


# --- instants -------------------------------------------------------------------------------------


def format_instant(value: datetime) -> str:
    """UTC, microsecond precision, ``Z`` suffix: ``2026-10-07T18:42:17.249461Z``.

    A naive datetime is refused: an instant without an offset does not name a moment.
    """
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise IdentityError(f"not an offset-aware instant: {value!r}")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# --- fetch ----------------------------------------------------------------------------------------


def fetch_id(requested_url: str, fetch_started_at: datetime, body_sha256: str) -> str:
    """``ft1:`` + SHA-256 over (requested URL, fetch-start instant, body hash).

    The URL is the string that was requested, byte for byte: it is not normalised, because two
    requests are two events even when a rule would later fold their URLs into one document.
    """
    _require_url_text(requested_url, "requested_url")
    preimage = canonical_json(
        {
            "schema": FETCH_ID_SCHEMA,
            "requested_url": requested_url,
            "fetch_started_at": format_instant(fetch_started_at),
            "body_sha256": require_sha256(body_sha256, "body_sha256"),
        }
    )
    return f"{FETCH_ID_PREFIX}:{sha256_bytes(preimage)}"


def is_fetch_id(value: object) -> bool:
    return isinstance(value, str) and _FETCH_ID.fullmatch(value) is not None


# --- channel --------------------------------------------------------------------------------------


def channel_id(outlet_id: str, slug: str) -> str:
    """``{outlet_id}:ch:{slug}``. Form only; assignment is the registry's."""
    if not naming.is_outlet_id(outlet_id):
        raise IdentityError(f"not an outlet_id: {outlet_id!r}")
    if not isinstance(slug, str) or _CHANNEL_SLUG.fullmatch(slug) is None:
        raise IdentityError(f"not a channel slug: {slug!r}")
    return f"{outlet_id}:ch:{slug}"


def is_channel_id(value: object) -> bool:
    if not isinstance(value, str):
        return False
    outlet, separator, slug = value.partition(":ch:")
    return bool(separator) and naming.is_outlet_id(outlet) and _CHANNEL_SLUG.fullmatch(slug) is not None


# --- document, version, unit, sentence, token -----------------------------------------------------


def document_id(outlet_id: str, url_key: str) -> str:
    """``{outlet_id}:doc:{hash16}``, the hash taken over the UTF-8 bytes of the canonical URL key."""
    if not naming.is_outlet_id(outlet_id):
        raise IdentityError(f"not an outlet_id: {outlet_id!r}")
    _require_url_text(url_key, "url_key")
    digest = sha256_bytes(url_key.encode("utf-8"))
    return f"{outlet_id}:doc:{digest[:DOCUMENT_HASH_LENGTH]}"


def document_version_id(document: str, extracted_text_sha256: str) -> str:
    """``{document_id}:v:{hash12}``, a prefix of the SHA-256 of the extracted text.

    The caller passes the full digest. Which bytes are "the extracted text" is defined by the
    extraction layer schema (Phase 3), not here; the name of the parameter says what it must cover.
    """
    if not is_document_id(document):
        raise IdentityError(f"not a document_id: {document!r}")
    digest = require_sha256(extracted_text_sha256, "extracted_text_sha256")
    return f"{document}:v:{digest[:VERSION_HASH_LENGTH]}"


def unit_id(document_version: str, index: int) -> str:
    return _child_id(document_version, "UNIT", index)


def sentence_id(document_version: str, index: int) -> str:
    return _child_id(document_version, "SENT", index)


def token_id(document_version: str, index: int) -> str:
    return _child_id(document_version, "TOKEN", index)


def _child_id(document_version: str, kind: str, index: int) -> str:
    """Zero-based position in the document version. Token indexes are padded to eight digits."""
    if not is_document_version_id(document_version):
        raise IdentityError(f"not a document_version_id: {document_version!r}")
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise IdentityError(f"{kind} index must be a non-negative integer: {index!r}")
    if kind == "TOKEN":
        if index >= TOKEN_INDEX_LIMIT:
            raise IdentityError(f"token index does not fit {TOKEN_INDEX_WIDTH} digits: {index}")
        return f"{document_version}:TOKEN:{index:0{TOKEN_INDEX_WIDTH}d}"
    return f"{document_version}:{kind}:{index}"


def is_document_id(value: object) -> bool:
    return isinstance(value, str) and _DOCUMENT_ID.fullmatch(value) is not None


def is_document_version_id(value: object) -> bool:
    return isinstance(value, str) and _VERSION_ID.fullmatch(value) is not None


@dataclass(frozen=True)
class ChildId:
    """A parsed unit, sentence or token id."""

    document_version_id: str
    kind: str
    index: int


def parse_child_id(value: str) -> ChildId:
    """Split a unit, sentence or token id; refuse anything that is not in canonical form."""
    match = _CHILD_ID.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise IdentityError(f"not a unit, sentence or token id: {value!r}")
    kind, digits = match.group("kind"), match.group("index")
    index = int(digits)
    builder = {"UNIT": unit_id, "SENT": sentence_id, "TOKEN": token_id}[kind]
    if builder(match.group("version"), index) != value:
        raise IdentityError(f"not in canonical form: {value!r}")
    return ChildId(match.group("version"), kind, index)


def parent_document_id(value: str) -> str:
    """The ``document_id`` a version, unit, sentence or token id hangs on."""
    for pattern, group in ((_CHILD_ID, "version"), (_VERSION_ID, "document")):
        match = pattern.fullmatch(value) if isinstance(value, str) else None
        if match is not None:
            inner = match.group(group)
            return inner if group == "document" else _VERSION_ID.fullmatch(inner).group("document")
    raise IdentityError(f"not a version, unit, sentence or token id: {value!r}")


# --- canonical URL key ----------------------------------------------------------------------------

_DEFAULT_PORTS = {"http": 80, "https": 443}
_UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
_HEX = frozenset("0123456789abcdefABCDEF")

BASIS_REL_CANONICAL = "rel_canonical"
BASIS_FINAL_URL = "final_url"
BASIS_REQUESTED_URL = "requested_url"
URL_KEY_BASES = (BASIS_REL_CANONICAL, BASIS_FINAL_URL, BASIS_REQUESTED_URL)


@dataclass(frozen=True)
class OutletUrlRules:
    """What the registry declares about one outlet's URLs.

    ``web_origins``: every origin the outlet publishes under (``scheme://host[:port]``); the first
    is the canonical one that all others fold to. ``significant_query_params``: the parameters
    that select a document; every other parameter is dropped. ``strip_path_prefixes`` /
    ``strip_path_suffixes``: variant markers (``/amp``, ``/print``) removed at a segment boundary.
    ``version`` names this rule set; a change of rules is a new version.
    """

    outlet_id: str
    web_origins: tuple[str, ...]
    version: str
    significant_query_params: tuple[str, ...] = ()
    strip_path_prefixes: tuple[str, ...] = ()
    strip_path_suffixes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not naming.is_outlet_id(self.outlet_id):
            raise IdentityError(f"not an outlet_id: {self.outlet_id!r}")
        if not self.web_origins:
            raise IdentityError(f"{self.outlet_id}: no web origin registered")
        if not isinstance(self.version, str) or not self.version:
            raise IdentityError(f"{self.outlet_id}: URL rules carry no version")
        normalised = tuple(normalise_origin(origin) for origin in self.web_origins)
        if normalised != tuple(self.web_origins):
            raise IdentityError(f"{self.outlet_id}: web origins are not in normal form: {self.web_origins}")
        if len(set(normalised)) != len(normalised):
            raise IdentityError(f"{self.outlet_id}: a web origin is registered twice")
        for marker in (*self.strip_path_prefixes, *self.strip_path_suffixes):
            if not marker.startswith("/") or marker.endswith("/") or len(marker) < 2:
                raise IdentityError(f"{self.outlet_id}: path marker must look like '/amp': {marker!r}")


@dataclass(frozen=True)
class UrlKey:
    """A canonical URL key with everything needed to recompute it."""

    key: str
    basis: str
    input_url: str
    ruleset: str
    outlet_rules_version: str

    def as_record(self) -> dict[str, str]:
        return {
            "url_key": self.key,
            "url_key_basis": self.basis,
            "url_key_input": self.input_url,
            "url_key_ruleset": self.ruleset,
            "outlet_url_rules_version": self.outlet_rules_version,
        }


def normalise_origin(origin: str) -> str:
    """``scheme://host[:port]``: lower case, no default port, no trailing dot, nothing else."""
    _require_url_text(origin, "origin")
    parts = _split(origin)
    if parts.scheme not in _DEFAULT_PORTS or not parts.hostname:
        raise IdentityError(f"not an http(s) origin: {origin!r}")
    if parts.path not in ("", "/") or parts.query or parts.fragment or parts.username or parts.password:
        raise IdentityError(f"an origin has no path, query, fragment or credentials: {origin!r}")
    return _origin_of(parts, origin)


def _split(url: str):
    try:
        return urlsplit(url)
    except ValueError as error:
        raise IdentityError(f"unparseable URL {url!r}: {error}") from error


def _origin_of(parts, original: str) -> str:
    host = parts.hostname.rstrip(".").lower()
    try:
        host = host.encode("idna").decode("ascii")
        port = parts.port
    except (UnicodeError, ValueError) as error:
        raise IdentityError(f"unusable host or port in {original!r}: {error}") from error
    if not host:
        raise IdentityError(f"no host in {original!r}")
    if port is None or port == _DEFAULT_PORTS[parts.scheme]:
        return f"{parts.scheme}://{host}"
    return f"{parts.scheme}://{host}:{port}"


def canonical_url_key(
    rules: OutletUrlRules,
    *,
    requested_url: str,
    final_url: str | None = None,
    rel_canonical: str | None = None,
) -> UrlKey:
    """The canonical URL key of a fetch under one outlet's rules.

    Candidates in order: ``rel=canonical``, the final URL after redirects, the requested URL. The
    first one that lies on a registered web origin of the outlet is used; a candidate that is
    malformed or off-origin is skipped. If none qualifies the fetch has no key under this outlet
    and :class:`OffOriginError` is raised — an off-origin redirect is recorded, not folded in.
    """
    candidates = (
        (BASIS_REL_CANONICAL, rel_canonical),
        (BASIS_FINAL_URL, final_url),
        (BASIS_REQUESTED_URL, requested_url),
    )
    for basis, url in candidates:
        if url is None:
            continue
        try:
            key = _key_of(rules, url)
        except OffOriginError:
            continue
        except IdentityError:
            if basis == BASIS_REQUESTED_URL:
                raise
            continue
        return UrlKey(key, basis, url, URL_KEY_RULESET, rules.version)
    raise OffOriginError(
        f"{rules.outlet_id}: no candidate URL lies on a registered web origin {rules.web_origins}"
    )


def _key_of(rules: OutletUrlRules, url: str) -> str:
    _require_url_text(url, "url")
    parts = _split(url)
    if parts.scheme not in _DEFAULT_PORTS or not parts.hostname:
        raise IdentityError(f"not an absolute http(s) URL: {url!r}")
    if parts.username is not None or parts.password is not None:
        raise IdentityError(f"a URL with credentials is not keyed: {url!r}")
    if _origin_of(parts, url) not in rules.web_origins:
        raise OffOriginError(f"{rules.outlet_id}: off-origin URL {url!r}")

    path = _remove_dot_segments(_normalise_escapes(parts.path)) or "/"
    path = _strip_variant_markers(path, rules)
    key = rules.web_origins[0] + path
    query = _significant_query(parts.query, rules.significant_query_params)
    return f"{key}?{query}" if query else key


def _strip_variant_markers(path: str, rules: OutletUrlRules) -> str:
    """Remove declared markers at a segment boundary until none is left, so that the key of a key
    is the key. The case is kept; a path that is nothing but a marker is left alone.
    """
    while True:
        before = path
        for prefix in rules.strip_path_prefixes:
            if path.startswith(prefix + "/"):
                path = path[len(prefix) :]
        for suffix in rules.strip_path_suffixes:
            if path.endswith(suffix) and len(path) > len(suffix):
                path = path[: -len(suffix)] or "/"
            elif path.endswith(suffix + "/") and len(path) > len(suffix) + 1:
                path = path[: -len(suffix) - 1] + "/"
        if path == before:
            return path


def _significant_query(query: str, significant: Sequence[str]) -> str:
    """Keep the declared parameters only, each normalised, in a fixed order."""
    if not query or not significant:
        return ""
    wanted = set(significant)
    kept = []
    for pair in query.split("&"):
        if not pair:
            continue
        name, separator, value = pair.partition("=")
        name = _normalise_escapes(name)
        if name in wanted:
            kept.append((name, separator, _normalise_escapes(value)))
    return "&".join(f"{name}{separator}{value}" for name, separator, value in sorted(kept))


def _normalise_escapes(text: str) -> str:
    """RFC 3986 §6.2.2 on one component: escapes upper-cased, unreserved characters unescaped,
    non-ASCII characters escaped as UTF-8, a stray ``%`` escaped. Idempotent; letters keep their case.
    """
    out = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "%":
            pair = text[index + 1 : index + 3]
            if len(pair) == 2 and pair[0] in _HEX and pair[1] in _HEX:
                decoded = chr(int(pair, 16))
                out.append(decoded if decoded in _UNRESERVED else "%" + pair.upper())
                index += 3
                continue
            out.append("%25")
        elif ord(char) > 0x7F:
            out.append("".join(f"%{byte:02X}" for byte in char.encode("utf-8")))
        else:
            out.append(char)
        index += 1
    return "".join(out)


def _remove_dot_segments(path: str) -> str:
    """RFC 3986 §5.2.4. Empty segments (``//``) are kept: folding them is an outlet rule."""
    if not path:
        return path
    segments = path.split("/")
    out: list[str] = []
    for position, segment in enumerate(segments):
        last = position == len(segments) - 1
        if segment == ".":
            if last:
                out.append("")
        elif segment == "..":
            if len(out) > 1:
                out.pop()
            if last:
                out.append("")
        else:
            out.append(segment)
    return "/".join(out)


def _require_url_text(value: object, what: str) -> None:
    if not isinstance(value, str) or not value:
        raise IdentityError(f"{what} must be a non-empty string: {value!r}")
    if _FORBIDDEN_IN_URL.search(value):
        raise IdentityError(f"{what} contains whitespace or a control character: {value!r}")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise IdentityError(f"{what} is not encodable as UTF-8: {error}") from error
