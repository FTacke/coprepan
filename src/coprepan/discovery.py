"""Discovery: from a channel document to candidates (decision CPD-0006 §2).

Discovery answers one question — *which URLs did this channel list, when, where in which
document?* — and records the answer as evidence. It fetches nothing, preserves nothing and
creates no document: a channel document reaches it as bytes with an identity (it is itself a
preserved fetch of kind ``channel_document``), and what leaves it are

* **inputs** — one row per channel document read (or not readable), with its parse outcome;
* **discovery events** — one row per listed URL: channel, input document, position, the URL as
  written and as resolved, optional hints (title, dates, guid);
* **candidates** — one row per canonical URL key of the outlet that has been listed at least once.

A candidate is a URL worth planning a fetch for. It is not an article and not a document.

Formats: RSS (0.9x, 1.0, 2.0), Atom, XML sitemap ``urlset``, XML sitemap index, HTML listing.
Expansion (sitemap index → sitemaps, ``rel=next`` pagination) is bounded by an explicit budget on
depth, documents, candidates and bytes; there is no unbounded recursion and a cycle is recorded,
not followed.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urldefrag, urljoin, urlsplit

from . import naming
from .canonical import canonical_json, require_sha256, sha256_bytes
from .extraction import ContentDecodingError, decode_content
from .identity import IdentityError, OffOriginError, OutletUrlRules, canonical_url_key, format_instant, is_channel_id
from .jsonl import append_row, keyed, read_rows

PARSER_VERSION = "channel-parser/1"
INPUT_SCHEMA = naming.schema_id("discovery-input", 1)
EVENT_SCHEMA = naming.schema_id("discovery-event", 1)
CANDIDATE_SCHEMA = naming.schema_id("discovery-candidate", 1)
EVENT_ID_PREFIX = "de1"

FORMATS = ("rss", "atom", "sitemap_urlset", "sitemap_index", "html_listing")
OUTCOME_PARSED = "PARSED"
OUTCOME_UNPARSEABLE = "UNPARSEABLE"
OUTCOME_UNAVAILABLE = "UNAVAILABLE"
RELATION_ITEM = "item"
RELATION_CHILD_DOCUMENT = "child_document"   # a sitemap named by a sitemap index
RELATION_NEXT_PAGE = "next_page"             # pagination declared by the document

# Reserved discovery source: sitemaps named by an origin's robots file (CPD-0007 §6). Events from
# them are recorded under ``{outlet_id}:ch:robots_sitemaps``; the registry refuses to assign this
# slug to a channel.
ROBOTS_SITEMAP_SLUG = "robots_sitemaps"

_XML_DECLARATION = re.compile(rb"\s*<\?xml[^>]*\?>", re.IGNORECASE)
_HTML_START = re.compile(rb"\s*(?:<!--.*?-->\s*)*<(?:!doctype\s+html|html[\s>])", re.IGNORECASE | re.DOTALL)
_FORBIDDEN_XML = re.compile(rb"<!(?:DOCTYPE|ENTITY)", re.IGNORECASE)
_SCHEMES = ("http", "https")


class DiscoveryError(RuntimeError):
    """Discovery was asked something it cannot do (not: a channel document was bad)."""


@dataclass(frozen=True)
class ChannelEntry:
    """One thing a channel document lists, in document order."""

    position: int
    relation: str
    url_raw: str | None
    url: str | None
    hints: Mapping[str, str]
    problem: str | None = None


@dataclass(frozen=True)
class ParsedChannelDocument:
    outcome: str
    format: str | None
    entries: tuple[ChannelEntry, ...]
    problems: tuple[str, ...]
    base_url: str


# --- parsing --------------------------------------------------------------------------------------


def _local(tag: Any) -> str:
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def _namespace(tag: Any) -> str:
    return tag[1:].split("}", 1)[0] if isinstance(tag, str) and tag.startswith("{") else ""


def _text(element: ET.Element | None) -> str:
    return re.sub(r"\s+", " ", "".join(element.itertext())).strip() if element is not None else ""


def _child(element: ET.Element, *names: str) -> ET.Element | None:
    """The first direct child with one of these local names, in the parent's own namespace or none."""
    for child in element:
        if _local(child.tag) in names and _namespace(child.tag) in ("", _namespace(element.tag)):
            return child
    return None


def resolve_url(raw: str | None, base_url: str) -> tuple[str | None, str | None]:
    """``(absolute URL without fragment, problem)``. Only ``http(s)`` URLs are candidates."""
    if raw is None or not raw.strip():
        return None, "no_link"
    text = raw.strip()
    if re.search(r"[\x00-\x20\x7f]", text):
        return None, "invalid_url"
    try:
        absolute = urldefrag(urljoin(base_url, text)).url
        parts = urlsplit(absolute)
    except ValueError:
        return None, "invalid_url"
    if parts.scheme not in _SCHEMES:
        return None, "not_http"
    if not parts.hostname:
        return None, "invalid_url"
    return absolute, None


def parse_channel_document(body: bytes, *, document_url: str, declared_content_type: str = "unknown") -> ParsedChannelDocument:
    """Parse one channel document. Never raises on bad content: an unparseable document is an
    outcome with its reason, and a listed thing without a usable URL is an entry with a problem.
    """
    if not isinstance(body, bytes):
        raise DiscoveryError("a channel document is bytes")
    if not body.strip():
        return ParsedChannelDocument(OUTCOME_UNPARSEABLE, None, (), ("empty_document",), document_url)
    # The bytes decide, not the header: feeds are often served as text/html and listings as
    # text/xml. The declared type only breaks the tie for something that is not XML at all.
    declared_html = declared_content_type in ("text/html", "application/xhtml+xml")
    if _HTML_START.match(_XML_DECLARATION.sub(b"", body[:4096], count=1)):
        return _parse_html(body, document_url)
    if _FORBIDDEN_XML.search(body):
        # No DTD, no entity declarations: nothing a feed or sitemap needs, and the classic way to
        # make an XML parser expand or fetch something.
        return ParsedChannelDocument(OUTCOME_UNPARSEABLE, None, (), ("dtd_or_entity_declaration_refused",), document_url)
    try:
        root = ET.fromstring(body)
    except ET.ParseError as error:
        if declared_html:
            return _parse_html(body, document_url)
        return ParsedChannelDocument(OUTCOME_UNPARSEABLE, None, (), (f"invalid_xml: {error}",), document_url)
    name = _local(root.tag)
    if name in ("rss", "rdf"):
        return _parse_rss(root, document_url)
    if name == "feed":
        return _parse_atom(root, document_url)
    if name == "urlset":
        return _parse_sitemap(root, document_url, "url", "sitemap_urlset", RELATION_ITEM)
    if name == "sitemapindex":
        return _parse_sitemap(root, document_url, "sitemap", "sitemap_index", RELATION_CHILD_DOCUMENT)
    if name == "html":
        return _parse_html(body, document_url)
    return ParsedChannelDocument(OUTCOME_UNPARSEABLE, None, (), (f"unknown_root_element: {name}",), document_url)


def _entries(raw: list[tuple[str, str | None, dict[str, str]]], base_url: str) -> tuple[ChannelEntry, ...]:
    out = []
    for position, (relation, url_raw, hints) in enumerate(raw):
        url, problem = resolve_url(url_raw, base_url)
        out.append(ChannelEntry(position, relation, url_raw, url, {k: v for k, v in hints.items() if v}, problem))
    return tuple(out)


def _next_links(element: ET.Element) -> list[tuple[str, str | None, dict[str, str]]]:
    """Atom-style ``<link rel="next" href>`` children: pagination the document itself declares."""
    return [
        (RELATION_NEXT_PAGE, child.get("href"), {})
        for child in element
        if _local(child.tag) == "link" and (child.get("rel") or "").lower() == "next" and child.get("href")
    ]


def _parse_rss(root: ET.Element, base_url: str) -> ParsedChannelDocument:
    channel = next((child for child in root if _local(child.tag) == "channel"), root)
    items = [e for parent in {id(root): root, id(channel): channel}.values() for e in parent if _local(e.tag) == "item"]
    raw = []
    for item in items:
        link, guid = _child(item, "link"), _child(item, "guid")
        url_raw = _text(link) or (link.get("href") if link is not None else None)
        if not url_raw and guid is not None and (guid.get("isPermaLink") or "true").lower() != "false":
            url_raw = _text(guid)  # RSS 2.0: a guid is a permalink unless it says otherwise
        raw.append((RELATION_ITEM, url_raw or None,
                    {"title": _text(_child(item, "title")),
                     "published": _text(_child(item, "pubdate")) or _text(next((c for c in item if _local(c.tag) == "date"), None)),
                     "guid": _text(guid)}))
    return ParsedChannelDocument(OUTCOME_PARSED, "rss", _entries(raw + _next_links(channel), base_url), (), base_url)


def _parse_atom(root: ET.Element, base_url: str) -> ParsedChannelDocument:
    raw = []
    for entry in (child for child in root if _local(child.tag) == "entry"):
        links = [c for c in entry if _local(c.tag) == "link" and c.get("href")]
        chosen = next((c for c in links if (c.get("rel") or "alternate").lower() == "alternate"), None)
        raw.append((RELATION_ITEM, chosen.get("href") if chosen is not None else None,
                    {"title": _text(_child(entry, "title")), "published": _text(_child(entry, "published")),
                     "updated": _text(_child(entry, "updated")), "guid": _text(_child(entry, "id"))}))
    return ParsedChannelDocument(OUTCOME_PARSED, "atom", _entries(raw + _next_links(root), base_url), (), base_url)


def _parse_sitemap(root: ET.Element, base_url: str, element: str, name: str, relation: str) -> ParsedChannelDocument:
    """Only ``<loc>`` directly under ``<url>`` / ``<sitemap>`` in the sitemap's own namespace:
    image, video and other extension locations are not candidates.
    """
    raw = []
    for node in (child for child in root if _local(child.tag) == element and _namespace(child.tag) == _namespace(root.tag)):
        news = next((c for c in node if _local(c.tag) == "news"), None)
        hints = {"lastmod": _text(_child(node, "lastmod"))}
        if news is not None:
            hints["title"] = _text(next((c for c in news if _local(c.tag) == "title"), None))
            hints["published"] = _text(next((c for c in news if _local(c.tag) == "publication_date"), None))
        raw.append((relation, _text(_child(node, "loc")) or None, hints))
    return ParsedChannelDocument(OUTCOME_PARSED, name, _entries(raw, base_url), (), base_url)


class _Listing(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.base: str | None = None
        self.raw: list[tuple[str, str | None, dict[str, str]]] = []
        self.open: tuple[str, list[str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "base" and self.base is None and attributes.get("href"):
            self.base = attributes["href"].strip()  # only the first <base> counts (HTML)
        elif tag == "link" and "next" in (attributes.get("rel") or "").lower().split() and attributes.get("href"):
            self.raw.append((RELATION_NEXT_PAGE, attributes["href"], {}))
        elif tag == "a" and attributes.get("href") is not None:
            self._close()
            self.open = (attributes["href"], [])

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._close()

    def handle_data(self, data: str) -> None:
        if self.open is not None:
            self.open[1].append(data)

    def _close(self) -> None:
        if self.open is not None:
            href, parts = self.open
            self.raw.append((RELATION_ITEM, href, {"title": re.sub(r"\s+", " ", "".join(parts)).strip()}))
            self.open = None


def _parse_html(body: bytes, document_url: str) -> ParsedChannelDocument:
    parser = _Listing()
    parser.feed(body.decode("utf-8", errors="replace"))
    parser.close()
    parser._close()
    base_url = document_url
    if parser.base:
        resolved, problem = resolve_url(parser.base, document_url)
        base_url = resolved if problem is None else document_url
    # An anchor that only names a place in the page (`#top`) lists nothing.
    raw = [entry for entry in parser.raw if not (entry[1] or "").strip().startswith("#")]
    return ParsedChannelDocument(OUTCOME_PARSED, "html_listing", _entries(raw, base_url), (), base_url)


# --- tables ---------------------------------------------------------------------------------------


def event_id(channel: str, input_fetch_id: str, position: int, observed_url: str | None) -> str:
    """``de1:`` + 32 hex over (channel, input document, position, URL as written)."""
    preimage = canonical_json({"schema": EVENT_SCHEMA, "channel_id": channel, "input_fetch_id": input_fetch_id,
                               "position": position, "observed_url": observed_url})
    return f"{EVENT_ID_PREFIX}:{sha256_bytes(preimage)[:32]}"


def candidate_id(outlet_id: str, url_key: str) -> str:
    """``{outlet_id}:cand:{hash16}`` over the canonical URL key — the key a fetch would be planned for."""
    return f"{outlet_id}:cand:{sha256_bytes(url_key.encode('utf-8'))[:16]}"


class DiscoveryTables:
    """Append-only discovery evidence of one workspace."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self._inputs, self._events, self._candidates = (self.directory / f"{name}.jsonl" for name in ("inputs", "events", "candidates"))
        self.inputs = read_rows(self._inputs, INPUT_SCHEMA)
        self.events = keyed(read_rows(self._events, EVENT_SCHEMA), lambda row: row["event_id"], "discovery events")
        self.candidates = keyed(read_rows(self._candidates, CANDIDATE_SCHEMA), lambda row: row["candidate_id"], "candidates")
        self._seen_inputs = {(row["channel_id"], row["input_fetch_id"]) for row in self.inputs}

    def add_input(self, row: Mapping[str, Any]) -> bool:
        key = (row["channel_id"], row["input_fetch_id"])
        if key in self._seen_inputs:
            return False
        self.inputs.append(append_row(self._inputs, INPUT_SCHEMA, row))
        self._seen_inputs.add(key)
        return True

    def add_event(self, row: Mapping[str, Any]) -> bool:
        if row["event_id"] in self.events:
            return False
        self.events[row["event_id"]] = append_row(self._events, EVENT_SCHEMA, row)
        return True

    def add_candidate(self, row: Mapping[str, Any]) -> bool:
        if row["candidate_id"] in self.candidates:
            return False
        self.candidates[row["candidate_id"]] = append_row(self._candidates, CANDIDATE_SCHEMA, row)
        return True


# --- a discovery pass over one channel --------------------------------------------------------------


@dataclass(frozen=True)
class DiscoveryBudget:
    """Hard limits of one discovery pass. All four are required: there is no unbounded default."""

    max_depth: int
    max_documents: int
    max_candidates: int
    max_bytes: int

    def __post_init__(self) -> None:
        for name in ("max_depth", "max_documents", "max_candidates", "max_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise DiscoveryError(f"{name} must be a non-negative integer: {value!r}")


@dataclass(frozen=True)
class ChannelDocument:
    """A channel document as handed to discovery: bytes plus the identity of the fetch that got them."""

    requested_url: str
    final_url: str
    fetch_id: str
    body: bytes
    content_type: str = "unknown"
    content_encoding: str = "identity"


@dataclass(frozen=True)
class DocumentUnavailable:
    """The provider could not supply a channel document (denied, failed, error status)."""

    requested_url: str
    reason: str
    fetch_id: str | None = None


@dataclass
class DiscoveryResult:
    channel_id: str
    documents_read: int = 0
    bytes_read: int = 0
    events_new: int = 0
    events_seen: int = 0
    candidates_new: list[str] = field(default_factory=list)
    candidates_listed: list[str] = field(default_factory=list)
    stopped_by: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


Provider = Callable[[str, int], "ChannelDocument | DocumentUnavailable"]


def discover_channel(
    tables: DiscoveryTables,
    rules: OutletUrlRules,
    *,
    channel_id: str,
    start_url: str,
    provider: Provider,
    budget: DiscoveryBudget,
    run_id: str,
    discovered_at: datetime,
) -> DiscoveryResult:
    """Read a channel and everything it names within the budget; record inputs, events, candidates.

    ``provider(url, depth)`` supplies each channel document (in production: the fetcher behind the
    policy gate; in tests: recorded bytes). Breadth-first and in document order, so the same
    documents always give the same rows in the same order. Idempotent: an input, an event or a
    candidate that is already recorded is not recorded again.
    """
    if not is_channel_id(channel_id) or not channel_id.startswith(f"{rules.outlet_id}:ch:"):
        raise DiscoveryError(f"{channel_id!r} is not a channel of {rules.outlet_id}")
    at = format_instant(discovered_at)
    result = DiscoveryResult(channel_id)
    queue: deque[tuple[str, int, str | None]] = deque([(start_url, 0, None)])
    visited_urls: set[str] = set()
    visited_bodies: set[str] = set()

    def stop(reason: str) -> None:
        if reason not in result.stopped_by:
            result.stopped_by.append(reason)

    while queue:
        url, depth, parent = queue.popleft()
        if url in visited_urls:
            result.notes.append(f"cycle_or_repeat_not_followed: {url}")
            continue
        if result.documents_read >= budget.max_documents:
            stop("max_documents")
            break
        visited_urls.add(url)
        document = provider(url, depth)
        base_row = {"run_id": run_id, "channel_id": channel_id, "document_url": url, "depth": depth,
                    "parent_fetch_id": parent, "read_at": at, "parser": PARSER_VERSION}
        if isinstance(document, DocumentUnavailable):
            # No fetch record exists for a request the gate refused: the row is keyed by run and URL,
            # so that the same refusal in a later run is a later observation, not a repeat.
            unfetched = f"unavailable:{run_id}:{sha256_bytes(url.encode('utf-8'))[:16]}"
            tables.add_input({**base_row, "input_fetch_id": document.fetch_id or unfetched,
                              "outcome": OUTCOME_UNAVAILABLE, "format": None, "problems": [document.reason],
                              "body_sha256": None, "entries": 0})
            result.notes.append(f"unavailable: {url}: {document.reason}")
            continue
        body_sha256 = sha256_bytes(document.body)
        if result.bytes_read + len(document.body) > budget.max_bytes:
            stop("max_bytes")
            break
        result.documents_read += 1
        result.bytes_read += len(document.body)
        if body_sha256 in visited_bodies:
            result.notes.append(f"same_bytes_as_an_earlier_document_not_reparsed: {url}")
            continue
        visited_bodies.add(body_sha256)
        try:
            parsed = parse_channel_document(decode_content(document.body, document.content_encoding),
                                            document_url=document.final_url, declared_content_type=document.content_type)
        except ContentDecodingError as error:
            parsed = ParsedChannelDocument(OUTCOME_UNPARSEABLE, None, (), (error.reason,), document.final_url)
        tables.add_input({**base_row, "input_fetch_id": document.fetch_id, "final_url": document.final_url,
                          "outcome": parsed.outcome, "format": parsed.format, "problems": list(parsed.problems),
                          "body_sha256": require_sha256(body_sha256, "body_sha256"), "entries": len(parsed.entries)})
        if parsed.outcome != OUTCOME_PARSED:
            result.notes.append(f"unparseable: {url}: {'; '.join(parsed.problems)}")
            continue

        for entry in parsed.entries:
            identifier = event_id(channel_id, document.fetch_id, entry.position, entry.url_raw)
            row = {"event_id": identifier, "run_id": run_id, "channel_id": channel_id, "outlet_id": rules.outlet_id,
                   "input_fetch_id": document.fetch_id, "position": entry.position, "relation": entry.relation,
                   "observed_url": entry.url_raw, "resolved_url": entry.url, "hints": dict(entry.hints),
                   "problem": entry.problem, "url_key": None, "candidate_id": None, "discovered_at": at,
                   "parser": PARSER_VERSION}
            if entry.url is not None and entry.relation == RELATION_ITEM:
                try:
                    row["url_key"] = canonical_url_key(rules, requested_url=entry.url).key
                    row["candidate_id"] = candidate_id(rules.outlet_id, row["url_key"])
                except OffOriginError:
                    row["problem"] = "off_origin"
                except IdentityError:
                    row["problem"] = "invalid_url"
            is_new_candidate = row["candidate_id"] is not None and row["candidate_id"] not in tables.candidates
            if is_new_candidate and len(result.candidates_new) >= budget.max_candidates:
                stop("max_candidates")
                row["candidate_id"], row["problem"] = None, "candidate_budget_exhausted"
                is_new_candidate = False
            if tables.add_event(row):
                result.events_new += 1
            else:
                result.events_seen += 1
            if row["candidate_id"] is not None:
                if is_new_candidate:
                    tables.add_candidate({"candidate_id": row["candidate_id"], "outlet_id": rules.outlet_id,
                                          "url_key": row["url_key"], "fetch_url": entry.url,
                                          "first_event_id": identifier, "first_channel_id": channel_id,
                                          "first_listed_at": at})
                    result.candidates_new.append(row["candidate_id"])
                if row["candidate_id"] not in result.candidates_listed:
                    result.candidates_listed.append(row["candidate_id"])
            if entry.url is not None and entry.relation in (RELATION_CHILD_DOCUMENT, RELATION_NEXT_PAGE):
                if depth + 1 > budget.max_depth:
                    stop("max_depth")
                elif entry.url in visited_urls or any(entry.url == queued for queued, _, _ in queue):
                    result.notes.append(f"cycle_or_repeat_not_followed: {entry.url}")
                else:
                    queue.append((entry.url, depth + 1, document.fetch_id))
    return result
