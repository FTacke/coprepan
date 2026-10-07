"""Extraction contract and a baseline structural extractor (decision CPD-0005).

**Contract.** Extraction turns one preserved body into an *extraction record*: typed blocks in
document order plus metadata fields that each carry the basis they rest on. It is a pure function
of (body bytes, declared content type, extractor name and version): no clock, no network, no
state. The record names its input by hash and its extractor by version, so it can be re-derived
from the preserved bytes at any time and compared byte for byte.

Structural parts kept apart: ``TITLE``, ``BODY``, ``AUTHOR``, ``PUBLICATION_DATE``, ``SECTION``
(plus the modification date and the declared language). **BODY is the primary linguistic text
surface**; the title and every non-body block are kept, typed, and excluded from the body view —
never deleted. A structural role is a statement about markup, not a linguistic category.

**The extractor here is a baseline, not an adopted component.** ``baseline_html/0.1.0`` exists so
that the contract, the layer store and the replay path can be exercised end to end. It has not
been compared with any other extractor and has not been measured on a gold sample; adopting an
extractor is a Phase-3 decision (``docs/methodology/TRANSFORMATION_AND_VALIDATION_PRINCIPLES.md``).

Rules it follows, each the negation of a measured legacy defect (``docs/legacy/INDEX.md`` §3):
structural rules only — no substring test on prose, no minimum length, no lexical repair; unknown
stays unknown — no default language, no fabricated date; a metadata value is stored exactly as
published, with its basis, and is not parsed or reinterpreted here.
"""

from __future__ import annotations

import codecs
import json
import re
import zlib
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Mapping

from . import naming
from .canonical import canonical_json, record_json, require_sha256, sha256_bytes

EXTRACTION_SCHEMA = naming.schema_id("extraction", 1)
EXTRACTOR_NAME = "baseline_html"
EXTRACTOR_VERSION = "0.1.0"
STAGE = "extraction"

OUTCOME_EXTRACTED = "EXTRACTED"
OUTCOME_NOT_EXTRACTABLE = "NOT_EXTRACTABLE"
OUTCOMES = (OUTCOME_EXTRACTED, OUTCOME_NOT_EXTRACTABLE)
REASON_UNSUPPORTED_CONTENT_TYPE = "unsupported_content_type"
REASON_NOT_HTML = "content_type_unknown_and_not_html"
REASON_EMPTY_BODY = "empty_body"
REASON_UNSUPPORTED_CONTENT_ENCODING = "unsupported_content_encoding"
REASON_UNDECODABLE_CONTENT_ENCODING = "undecodable_content_encoding"
IDENTITY = "identity"
# A decompressed body larger than this is refused rather than expanded (decompression bombs).
MAX_DECODED_BYTES = 64 * 1024 * 1024
NOT_APPLICABLE = "not_applicable"
UNKNOWN = "unknown"

BLOCK_KINDS = ("title", "heading", "paragraph", "list_item", "quote_block", "caption", "unstructured_text")
ROLE_TITLE, ROLE_BODY, ROLE_NON_BODY = "title", "body", "non_body"
ROLES = (ROLE_TITLE, ROLE_BODY, ROLE_NON_BODY)
METADATA_FIELDS = ("title", "author", "publication_date", "modification_date", "section", "language")
BASES = ("json_ld", "open_graph", "html_meta", "html_title", "html_h1", "html_lang", UNKNOWN)

HTML_TYPES = ("text/html", "application/xhtml+xml")
_BLOCK_TAGS = {"p": "paragraph", "li": "list_item", "blockquote": "quote_block", "figcaption": "caption",
               "h1": "heading", "h2": "heading", "h3": "heading", "h4": "heading", "h5": "heading", "h6": "heading"}
_CONTAINERS = ("article", "main", "body")
_NON_BODY_ANCESTORS = {"nav", "aside", "footer", "header", "form", "figure"}
_SKIPPED = {"script", "style", "noscript", "template", "svg", "iframe"}
_TEXT_RUN = "#text"  # text that stands in no block element: kept as `unstructured_text`, never dropped
_INLINE = {"a", "abbr", "b", "bdi", "bdo", "cite", "code", "data", "dfn", "em", "font", "i", "kbd", "mark", "q",
           "s", "samp", "small", "span", "strong", "sub", "sup", "time", "u", "var"}
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
_WHITESPACE = re.compile(r"[ \t\n\r\f\v]+")
_META_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([A-Za-z0-9_\-:.]+)""", re.IGNORECASE)
_HTML_START = re.compile(rb"\s*(?:<!--.*?-->\s*)*<(?:!doctype\s+html|html[\s>])", re.IGNORECASE | re.DOTALL)

# (basis, source key) per field, in the order candidates are listed. The first is the value.
_META_SOURCES = {
    "title": (("json_ld", "headline"), ("open_graph", "og:title"), ("html_h1", "h1"), ("html_title", "title")),
    "author": (("json_ld", "author"), ("html_meta", "author"), ("open_graph", "article:author")),
    "publication_date": (("json_ld", "datePublished"), ("open_graph", "article:published_time"),
                         ("html_meta", "date")),
    "modification_date": (("json_ld", "dateModified"), ("open_graph", "article:modified_time")),
    "section": (("json_ld", "articleSection"), ("open_graph", "article:section")),
    "language": (("html_lang", "lang"),),
}


class ExtractionError(ValueError):
    """The input cannot be given to the extractor at all (not: the page has no article)."""


@dataclass(frozen=True)
class Extraction:
    """An extraction record with the digests later stages key on."""

    record: Mapping[str, Any]

    @property
    def outcome(self) -> str:
        return self.record["outcome"]

    @property
    def payload(self) -> bytes:
        """The stored bytes of the record. Contains no timestamp and no location."""
        return record_json(dict(self.record))

    @property
    def extracted_text_sha256(self) -> str:
        return self.record["extracted_text_sha256"]

    @property
    def body_text_sha256(self) -> str:
        return self.record["body_text_sha256"]

    @property
    def body_text(self) -> str:
        return body_text(self.record["blocks"])


def extracted_text_bytes(blocks: list[Mapping[str, Any]]) -> bytes:
    """The bytes a document version's digest covers: every block's kind, role and text, in order,
    as canonical JSON. Any change in what was extracted — title, body or a non-body block — is a
    new textual state.
    """
    return canonical_json([[block["kind"], block["role"], block["text"]] for block in blocks])


def body_text(blocks: list[Mapping[str, Any]]) -> str:
    """The BODY view: the texts of the body blocks, joined by a blank line."""
    return "\n\n".join(block["text"] for block in blocks if block["role"] == ROLE_BODY)


class ContentDecodingError(ValueError):
    """The stored body cannot be turned back into the representation it encodes."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def decode_content(body: bytes, content_encoding: str) -> bytes:
    """Undo the HTTP content coding of a stored body (``identity``, ``gzip``, ``deflate``).

    The stored bytes are never changed; this is a step of reading them. An unknown coding or
    bytes that do not decode raise — the caller labels the fetch, it does not guess.
    """
    data = body
    for coding in reversed([part for part in content_encoding.split(",") if part]):
        if coding == IDENTITY:
            continue
        if coding not in ("gzip", "x-gzip", "deflate"):
            raise ContentDecodingError(REASON_UNSUPPORTED_CONTENT_ENCODING, f"unsupported content coding {coding!r}")
        try:
            # gzip: wbits 31. deflate: zlib-wrapped (15), and raw (-15) as sent by some servers.
            for wbits in ((31,) if coding != "deflate" else (15, -15)):
                decompressor = zlib.decompressobj(wbits)
                try:
                    out = decompressor.decompress(data, MAX_DECODED_BYTES + 1)
                except zlib.error:
                    if wbits == 15:
                        continue
                    raise
                if len(out) > MAX_DECODED_BYTES:
                    raise ContentDecodingError(REASON_UNDECODABLE_CONTENT_ENCODING, "decoded body exceeds the size limit")
                if not decompressor.eof:
                    raise zlib.error("incomplete stream")
                data = out
                break
        except zlib.error as error:
            raise ContentDecodingError(REASON_UNDECODABLE_CONTENT_ENCODING, f"{coding}: {error}") from error
    return data


def extract(
    body: bytes, *, body_sha256: str, content_type: str, declared_charset: str = UNKNOWN,
    content_encoding: str = IDENTITY,
) -> Extraction:
    """Extract one body. ``content_type``, ``declared_charset`` and ``content_encoding`` are what
    the server declared, ``unknown`` (or ``identity`` for the coding) when it declared nothing.
    """
    if not isinstance(body, bytes):
        raise ExtractionError("a body is bytes")
    if sha256_bytes(body) != require_sha256(body_sha256, "body_sha256"):
        raise ExtractionError("the body offered is not the body the digest names")
    if not isinstance(content_type, str) or not content_type:
        raise ExtractionError("content_type is the declared media type or 'unknown'")

    record: dict[str, Any] = {
        "schema": EXTRACTION_SCHEMA,
        "extractor": {"name": EXTRACTOR_NAME, "version": EXTRACTOR_VERSION},
        "input": {"body_sha256": body_sha256, "body_size_bytes": len(body), "declared_content_type": content_type,
                  "declared_charset": declared_charset, "content_encoding": content_encoding},
        "outcome": OUTCOME_EXTRACTED,
        "reason": NOT_APPLICABLE,
        "decoding": {"charset": NOT_APPLICABLE, "basis": NOT_APPLICABLE, "replaced_characters": 0},
        "metadata": {name: {"value": UNKNOWN, "basis": UNKNOWN, "candidates": []} for name in METADATA_FIELDS},
        "blocks": [],
    }
    try:
        body = decode_content(body, content_encoding) if body else body
        reason = _refusal(body, content_type)
    except ContentDecodingError as error:
        reason = error.reason
    if reason is None:
        text, record["decoding"] = _decode(body, declared_charset)
        parser = _Parser()
        parser.feed(text)
        parser.close()
        record["blocks"] = parser.blocks()
        record["metadata"] = _metadata(parser)
    else:
        record["outcome"], record["reason"] = OUTCOME_NOT_EXTRACTABLE, reason
    record["extracted_text_sha256"] = sha256_bytes(extracted_text_bytes(record["blocks"]))
    record["body_text_sha256"] = sha256_bytes(body_text(record["blocks"]).encode("utf-8"))
    return Extraction(record)


def fingerprint_inputs(
    body_sha256: str, content_type: str, declared_charset: str = UNKNOWN, content_encoding: str = IDENTITY
) -> tuple[dict[str, str], dict[str, str]]:
    """``(inputs, parameters)`` of the layer-store fingerprint of an extraction."""
    return (
        {"body": require_sha256(body_sha256, "body_sha256")},
        {"declared_content_type": content_type, "declared_charset": declared_charset,
         "content_encoding": content_encoding},
    )


def declared_charset_of(response_headers: list[list[str]]) -> str:
    """The ``charset`` parameter of the ``Content-Type`` header, lower-cased; ``unknown`` if none."""
    for name, value in response_headers:
        if name.lower() == "content-type":
            match = re.search(r"""charset\s*=\s*["']?([A-Za-z0-9_\-:.]+)""", value, re.IGNORECASE)
            return match.group(1).lower() if match else UNKNOWN
    return UNKNOWN


@dataclass(frozen=True)
class Extractor:
    """A named, versioned extractor. The version is part of every fingerprint it answers."""

    name: str
    version: str
    function: Any

    @property
    def stage_version(self) -> str:
        return f"{self.name}/{self.version}"

    def run(self, body: bytes, *, body_sha256: str, content_type: str, declared_charset: str = UNKNOWN,
            content_encoding: str = IDENTITY) -> Extraction:
        result = self.function(body, body_sha256=body_sha256, content_type=content_type,
                               declared_charset=declared_charset, content_encoding=content_encoding)
        if result.record["extractor"] != {"name": self.name, "version": self.version}:
            raise ExtractionError(f"{self.stage_version} returned a record signed {result.record['extractor']}")
        return result


BASELINE = Extractor(EXTRACTOR_NAME, EXTRACTOR_VERSION, extract)


# --- content type and decoding --------------------------------------------------------------------


def _refusal(body: bytes, content_type: str) -> str | None:
    """Why this body is not given to the HTML extractor, or ``None``. A label, never a deletion."""
    if not body:
        return REASON_EMPTY_BODY
    if content_type in HTML_TYPES:
        return None
    if content_type == UNKNOWN:
        return None if _HTML_START.match(body.lstrip(codecs.BOM_UTF8)[:2048]) else REASON_NOT_HTML
    return REASON_UNSUPPORTED_CONTENT_TYPE


def _decode(body: bytes, declared_charset: str) -> tuple[str, dict[str, Any]]:
    """Decode by, in order: a UTF-8 byte-order mark, the charset of the HTTP header, the charset
    the markup declares, UTF-8. Undecodable bytes become U+FFFD and are counted — the count is
    part of the record, not a silent repair.
    """
    if body.startswith(codecs.BOM_UTF8):
        charset, basis, data = "utf-8", "byte_order_mark", body[len(codecs.BOM_UTF8):]
    else:
        data = body
        in_markup = _META_CHARSET.search(body[:4096])
        charset, basis = "utf-8", "default_utf8"
        for name, source in ((declared_charset, "http_header"),
                             (in_markup.group(1).decode("ascii") if in_markup else UNKNOWN, "html_meta")):
            if name == UNKNOWN:
                continue
            try:
                charset, basis = codecs.lookup(name).name, source
                break
            except LookupError:
                basis = "default_utf8_after_unknown_declared_charset"
    text = data.decode(charset, errors="replace")
    return text, {"charset": charset, "basis": basis, "replaced_characters": text.count("�") - _literal_fffd(data, charset)}


def _literal_fffd(data: bytes, charset: str) -> int:
    try:
        return data.count("�".encode(charset))
    except UnicodeEncodeError:
        return 0


# --- parsing --------------------------------------------------------------------------------------


class _Parser(HTMLParser):
    """Collects blocks and metadata in one pass over the markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.raw: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None
        self.capture: tuple[str, list[str]] | None = None
        self.meta: dict[str, list[str]] = {}
        self.json_ld: list[str] = []
        self.containers: set[str] = set()

    def _add_meta(self, key: str, value: str | None) -> None:
        value = _WHITESPACE.sub(" ", value or "").strip()
        if value:
            self.meta.setdefault(key, []).append(value)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "html":
            self._add_meta("lang", attributes.get("lang"))
        elif tag == "meta":
            key = attributes.get("property") or attributes.get("name")
            if key:
                self._add_meta(key.strip().lower(), attributes.get("content"))
        if tag in _VOID:
            if tag == "br" and self.current is not None:
                self.current["parts"].append(" ")
            return
        if self.current is not None and self.current["tag"] == _TEXT_RUN and tag not in _INLINE:
            self._close_block()
        self.stack.append(tag)
        if tag in _CONTAINERS:
            self.containers.add(tag)
        if tag == "title" and "body" not in self.stack:
            self.capture = ("title", [])
        elif tag == "script" and (attributes.get("type") or "").strip().lower() == "application/ld+json":
            self.capture = ("json_ld", [])
        elif tag in _BLOCK_TAGS and not _SKIPPED.intersection(self.stack):
            self._close_block()
            self.current = {"tag": tag, "parts": [], "ancestors": tuple(self.stack[:-1])}

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID or tag not in self.stack:
            return
        while self.stack:
            closed = self.stack.pop()
            if self.capture and closed in ("title", "script"):
                kind, parts = self.capture
                self.capture = None
                if kind == "title":
                    self._add_meta("title", "".join(parts))
                else:
                    self.json_ld.append("".join(parts))
            if self.current is not None and (
                closed == self.current["tag"] or (self.current["tag"] == _TEXT_RUN and closed not in _INLINE)
            ):
                self._close_block()
            if closed == tag:
                break

    def handle_data(self, data: str) -> None:
        if self.capture is not None:
            self.capture[1].append(data)
        elif _SKIPPED.intersection(self.stack):
            return
        elif self.current is not None:
            self.current["parts"].append(data)
        elif "body" in self.stack and data.strip():
            self.current = {"tag": _TEXT_RUN, "parts": [data], "ancestors": tuple(self.stack)}

    def _close_block(self) -> None:
        if self.current is None:
            return
        text = _WHITESPACE.sub(" ", "".join(self.current["parts"])).strip()
        if text:
            self.raw.append({"tag": self.current["tag"], "ancestors": self.current["ancestors"], "text": text})
        self.current = None

    def close(self) -> None:
        super().close()
        self._close_block()

    def blocks(self) -> list[dict[str, Any]]:
        """Typed blocks in document order. The body container is the first of ``article``,
        ``main``, ``body`` that the page has; a block inside it and outside navigation, asides,
        footers, headers, forms and figures is body text. The first ``h1`` is the title.
        """
        container = next((name for name in _CONTAINERS if name in self.containers), None)
        blocks, title_taken = [], False
        for item in self.raw:
            ancestors = item["ancestors"]
            if item["tag"] == "h1" and not title_taken:
                kind, role, title_taken = "title", ROLE_TITLE, True
            else:
                kind = _BLOCK_TAGS.get(item["tag"], "unstructured_text")
                inside = container is not None and container in ancestors
                role = ROLE_BODY if inside and not _NON_BODY_ANCESTORS.intersection(ancestors) else ROLE_NON_BODY
                if kind == "caption":
                    role = ROLE_NON_BODY
            blocks.append({"index": len(blocks), "kind": kind, "role": role, "text": item["text"]})
        return blocks


def _json_ld_values(documents: list[str]) -> dict[str, list[str]]:
    """Values of the article-describing keys in the page's JSON-LD, in document order. A script
    that is not valid JSON contributes nothing and breaks nothing.
    """
    found: dict[str, list[str]] = {}

    def text_of(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return text_of(value.get("name"))
        if isinstance(value, list):
            return [text for item in value for text in text_of(item)]
        return []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for key in ("headline", "author", "datePublished", "dateModified", "articleSection"):
                for text in text_of(node.get(key)):
                    text = _WHITESPACE.sub(" ", text).strip()
                    if text and text not in found.setdefault(key, []):
                        found[key].append(text)
            walk(node.get("@graph"))

    for document in documents:
        try:
            walk(json.loads(document))
        except ValueError:
            continue
    return found


def _metadata(parser: _Parser) -> dict[str, dict[str, Any]]:
    json_ld = _json_ld_values(parser.json_ld)
    h1 = [block["text"] for block in parser.blocks() if block["role"] == ROLE_TITLE]
    metadata = {}
    for name, sources in _META_SOURCES.items():
        candidates = []
        for basis, key in sources:
            values = json_ld.get(key, []) if basis == "json_ld" else h1 if basis == "html_h1" else parser.meta.get(key, [])
            candidates += [{"value": value, "basis": basis} for value in values]
        first = candidates[0] if candidates else {"value": UNKNOWN, "basis": UNKNOWN}
        metadata[name] = {"value": first["value"], "basis": first["basis"], "candidates": candidates}
    return metadata
