"""``article_html/0.1.0``: the baseline's contract with one structural change -- the body container is the element that carries
the most running text, not the first ``article`` / ``main`` / ``body`` tag name (CPD-0005, CPD-0018; CPD-0038).

What the baseline gets wrong, measured on the weekend qualification (2026-11-14/15): it remembers the *names* of a block's
ancestors only, so a block inside **any** ``<article>`` is body. A page that lists teaser cards as ``<article>`` elements before
the article (``ar_la_nacion``, ``pa_metro_libre``, ``mx_el_universal``, ``co_elcolombiano``) yields the teasers as the body and
drops the article, whose paragraphs stand in a ``<div>`` outside every ``<article>``; a page whose article container stands
inside a page-level ``<header>`` (``pa_diaadia``) yields nothing.

This extractor keeps element identity. Every block's text without its link text counts for the element that holds it and half
for that element's parent (the usual paragraph-density rule); the element with the highest score is the container. A block is
body when it lies inside the container, no ``nav`` / ``aside`` / ``footer`` / ``form`` / ``figure`` / ``header`` stands
*between* the container and the block (what stands above the container does not matter), it is not a caption, and at most half
of its characters are link text (a list of related articles is links). The first ``h1`` is the title, as in the baseline.
Decoding, metadata, refusals and the record are the baseline's.

Structural rules only, no lexical test, no length threshold. ``CANDIDATE``: entered into the comparison of the weekend
extraction study; it is not adopted (adopting an extractor is a decision, CPD-0007 §7).
"""

from __future__ import annotations

import json as _json
import re as _re
import unicodedata as _unicodedata
from collections import Counter
from typing import Any

from . import extraction as E
from .canonical import require_sha256, sha256_bytes

NAME = "article_html"
VERSION = "0.1.0"
NON_BODY_BELOW_CONTAINER = frozenset({"nav", "aside", "footer", "form", "figure", "header"})
MAX_LINK_SHARE = 0.5
CLIMB_SHARE = 0.25          # the container's parent is taken instead when its own running text is at least this share
CLIMB_STEPS = 3
SIBLING_SHARE = 0.2         # a sibling of the container with at least this share of its score is part of the body
_SCORED = frozenset({"paragraph", "unstructured_text", "quote_block", "list_item"})
# HTML closes an open paragraph when one of these opens (the "p in button scope" rule of the HTML parsing algorithm), and an
# open list item when the next one opens. Python's HTMLParser does neither; pages with unclosed <p> would nest every
# paragraph in the one before it.
_CLOSES_P = frozenset("address article aside blockquote div dl fieldset figure footer form h1 h2 h3 h4 h5 h6 header hr main "
                      "nav ol p pre section table ul".split())


class _Parser(E._Parser):
    """The baseline's parser, with the identity of every open element and the link text of every block."""

    def __init__(self) -> None:
        super().__init__()
        self.ids: list[int] = []
        self.tag_of: dict[int, str] = {}
        self.parent_of: dict[int, int | None] = {}
        self._next = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _CLOSES_P and "p" in self.stack and not E._SKIPPED.intersection(self.stack):
            self._implicit_end("p")
        elif tag == "li" and "li" in self.stack:
            nearest_list = max((i for i, t in enumerate(self.stack) if t in ("ul", "ol")), default=-1)
            if max(i for i, t in enumerate(self.stack) if t == "li") > nearest_list:    # an open item of the same list
                self._implicit_end("li")
        before, current = len(self.stack), self.current
        super().handle_starttag(tag, attrs)
        if len(self.stack) > before:                      # an element was opened (void tags are not)
            self._next += 1
            self.parent_of[self._next] = self.ids[-1] if self.ids else None
            self.ids.append(self._next)
            self.tag_of[self._next] = tag
        if self.current is not None and self.current is not current and "ids" not in self.current:
            self.current["ids"] = tuple(self.ids[:-1])    # a block element: its ancestors, without itself

    def handle_endtag(self, tag: str) -> None:
        super().handle_endtag(tag)
        del self.ids[len(self.stack):]

    def _implicit_end(self, tag: str) -> None:
        """Close the innermost open ``tag`` -- but only if no element that ``tag`` cannot span is open inside it."""
        position = max(i for i, t in enumerate(self.stack) if t == tag)
        if not {"table", "td", "th", "button"} & set(self.stack[position + 1:]):
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        current = self.current
        super().handle_data(data)
        if self.current is not None and self.current is not current and "ids" not in self.current:
            self.current["ids"] = tuple(self.ids)          # a text run: it stands in the innermost open element
        if self.current is not None and "a" in self.stack and self.capture is None:
            self.current["link"] = self.current.get("link", 0) + len(E._WHITESPACE.sub(" ", data).strip())

    def _close_block(self) -> None:
        current, count = self.current, len(self.raw)
        super()._close_block()
        if current is not None and len(self.raw) > count:
            self.raw[-1]["ids"] = current.get("ids", ())
            self.raw[-1]["link"] = min(current.get("link", 0), len(self.raw[-1]["text"]))

    def container(self) -> int | None:
        return (self.containers_chosen() or [None])[0]

    def containers_chosen(self) -> list[int]:
        """The container and the siblings that carry a real share of its running text (an article whose paragraphs stand in
        several sibling elements between embeds); the container first."""
        best = self._best()
        if best is None:
            return []
        parent = self.parent_of.get(best)
        siblings = sorted(element for element, parent_of in self.parent_of.items()
                          if parent is not None and parent_of == parent and element != best
                          and self._score[element] >= SIBLING_SHARE * self._score[best])
        return [best, *siblings]

    def _best(self) -> int | None:
        score: Counter[int] = Counter()
        direct: Counter[int] = Counter()
        for item in self.raw:
            kind = E._BLOCK_TAGS.get(item["tag"], "unstructured_text")
            ids = item.get("ids") or ()
            weight = len(item["text"]) - item.get("link", 0)
            if kind not in _SCORED or weight <= 0 or not ids:
                continue
            score[ids[-1]] += weight
            direct[ids[-1]] += weight
            if len(ids) > 1:
                score[ids[-2]] += weight / 2
        self._score = score
        if not score:
            return None
        top = max(score.values())
        best = min(element for element, value in score.items() if value == top)   # the first opened among equals
        # An article whose running text is split between an element and its parent (a lead in the parent, the rest in a
        # wrapper; text around an embedded block): the parent is the container when it carries a real share of its own.
        for _ in range(CLIMB_STEPS):
            parent = self.parent_of.get(best)
            if parent is None or self.tag_of.get(parent) in ("body", "html") or direct[parent] < CLIMB_SHARE * max(1, direct[best]):
                break
            best = parent
        return best

    def blocks(self) -> list[dict[str, Any]]:
        chosen = self.containers_chosen()
        blocks, title_taken = [], False
        for item in self.raw:
            ids = item.get("ids") or ()
            if item["tag"] == "h1" and not title_taken:
                kind, role, title_taken = "title", E.ROLE_TITLE, True
            else:
                kind = E._BLOCK_TAGS.get(item["tag"], "unstructured_text")
                role = E.ROLE_NON_BODY
                container = next((c for c in chosen if c in ids), None)
                if container is not None and kind != "caption":
                    below = {self.tag_of[i] for i in ids[ids.index(container) + 1:]}
                    linked = item.get("link", 0) > MAX_LINK_SHARE * len(item["text"])
                    if not NON_BODY_BELOW_CONTAINER & below and not linked:
                        role = E.ROLE_BODY
            blocks.append({"index": len(blocks), "kind": kind, "role": role, "text": item["text"]})
        return blocks


def extract(body: bytes, *, body_sha256: str, content_type: str, declared_charset: str = E.UNKNOWN,
            content_encoding: str = E.IDENTITY) -> E.Extraction:
    """As :func:`coprepan.extraction.extract`, with the container chosen by text density."""
    if not isinstance(body, bytes):
        raise E.ExtractionError("a body is bytes")
    if sha256_bytes(body) != require_sha256(body_sha256, "body_sha256"):
        raise E.ExtractionError("the body offered is not the body the digest names")
    if not isinstance(content_type, str) or not content_type:
        raise E.ExtractionError("content_type is the declared media type or 'unknown'")
    record: dict[str, Any] = {
        "schema": E.EXTRACTION_SCHEMA,
        "extractor": {"name": NAME, "version": VERSION},
        "input": {"body_sha256": body_sha256, "body_size_bytes": len(body), "declared_content_type": content_type,
                  "declared_charset": declared_charset, "content_encoding": content_encoding},
        "outcome": E.OUTCOME_EXTRACTED,
        "reason": E.NOT_APPLICABLE,
        "decoding": {"charset": E.NOT_APPLICABLE, "basis": E.NOT_APPLICABLE, "replaced_characters": 0},
        "metadata": {name: {"value": E.UNKNOWN, "basis": E.UNKNOWN, "candidates": []} for name in E.METADATA_FIELDS},
        "blocks": [],
    }
    try:
        body = E.decode_content(body, content_encoding) if body else body
        reason = E._refusal(body, content_type)
    except E.ContentDecodingError as error:
        reason = error.reason
    if reason is None:
        text, record["decoding"] = E._decode(body, declared_charset)
        parser = _Parser()
        parser.feed(text)
        parser.close()
        record["blocks"] = parser.blocks()
        record["metadata"] = E._metadata(parser)
    else:
        record["outcome"], record["reason"] = E.OUTCOME_NOT_EXTRACTABLE, reason
    record["extracted_text_sha256"] = sha256_bytes(E.extracted_text_bytes(record["blocks"]))
    record["body_text_sha256"] = sha256_bytes(E.body_text(record["blocks"]).encode("utf-8"))
    return E.Extraction(record)


# Not entered into extraction.EXTRACTORS (the registry of record of the package's adopted pipeline): a candidate of a comparison
# carries its lifecycle itself, and importing it changes nothing elsewhere.
ARTICLE = E.Extractor(NAME, VERSION, extract, E.LIFECYCLE_CANDIDATE)


# --- article_html/0.2.0 (CPD-0039): the text structure -- title, subtitle, BODY -- and machine-summary modules ----------------
#
# 0.1.0's body rule unchanged, plus two structural rules, both read from the markup and the page's own statements, never from the
# wording of the text:
#
# 1. **Subtitle.** A block between the title and the first body block becomes ``subtitle`` (role ``title``) when the publisher
#    sets it apart: its text is the one the page states as the article's secondary headline or description (JSON-LD
#    ``alternativeHeadline`` / ``description`` of the article, ``og:description`` / ``description`` / ``twitter:description``),
#    or its element (or the element directly around it) carries a subtitle mark of the closed list ``SUBTITLE_MARKS``. Only a
#    block that 0.1.0 does not take as body is moved -- a body paragraph that repeats the description is the *entradilla*, the
#    first paragraph of the running text, and stays BODY -- with one exception: the leading body blocks whose own element
#    carries a subtitle mark (an explicitly marked standfirst inside the article container). Nothing uncertain is separated.
# 2. **Machine-summary module.** A block inside an element marked as an AI summary (``AI_SUMMARY_MARK``: a class / id / itemprop
#    token that pairs ``ai``/``ia`` with ``summary``/``resumen``) is never body; it is kept with ``module: ai_summary``. A page
#    summary written by a machine must not stand in, or beside, the newspaper's running text (CPD-0039 §7).

VERSION_2 = "0.2.0"
SUBTITLE_MARKS = frozenset({"subtitle", "subtitulo", "subheadline", "subhead", "bajada", "copete", "standfirst", "sumario", "deck",
                            "dek", "entradilla", "excerpt", "epigraph"})
# a subtitle mark beside one of these is a caption, a credit or a byline, not a subtitle
NOT_SUBTITLE_MARKS = frozenset({"caption", "credit", "credits", "foto", "photo", "image", "img", "media", "figure", "figcaption",
                                "author", "autor", "byline", "firma", "date", "fecha", "time", "related", "relacionadas", "tag", "tags"})
SUBTITLE_KINDS = frozenset({"heading", "paragraph", "unstructured_text", "list_item"})
LEADING_BODY_MARKS = SUBTITLE_MARKS - {"entradilla", "excerpt", "epigraph"}   # inside the body only an explicit subtitle element
MIN_SUBTITLE_CHARACTERS = 20
MIN_MARKED_SUBTITLE_CHARACTERS = 40   # a subtitle by markup alone is at least this long (shorter marked blocks: labels, dates)
MIN_PREFIX_CHARACTERS = 60       # a stated description that the page shortens ("…") matches a block on its first characters

_MARK_PARTS = _re.compile(r"[a-z0-9]+")
_CAMEL = _re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
AI_SUMMARY_MARK = _re.compile(r"(?:^|[-_ ])(?:ai|ia)[-_ ]*(?:summary|summaries|resumen|resumenes)(?:$|[-_ ])|"
                              r"(?:^|[-_ ])(?:summary|summaries|resumen|resumenes)[-_ ]*(?:ai|ia)(?:$|[-_ ])|"
                              r"(?:^|[-_ ])resumen[-_ ]generado(?:$|[-_ ])")
_ELLIPSIS = _re.compile(r"\s*(?:\.\.\.|…)\s*$")


def _mark_parts(value: str) -> set[str]:
    """The tokens of a class / id / itemprop value: split at spaces, hyphens, underscores and camel case, lower-cased."""
    return set(_MARK_PARTS.findall(_CAMEL.sub(" ", value).lower()))


def _norm(text: str) -> str:
    return _unicodedata.normalize("NFC", E._WHITESPACE.sub(" ", text.replace("\xa0", " "))).strip().lower()


class _Parser2(_Parser):
    """0.1.0's parser, with the markup marks of every element and the element of every block."""

    def __init__(self) -> None:
        super().__init__()
        self.marks_of: dict[int, set[str]] = {}
        self.raw_marks_of: dict[int, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        before, current = self._next, self.current
        super().handle_starttag(tag, attrs)
        if self._next > before:
            attributes = dict(attrs)
            raw = " ".join(v for v in (attributes.get("class"), attributes.get("id"), attributes.get("itemprop")) if v)
            if raw:
                self.raw_marks_of[self._next] = raw.lower()
                self.marks_of[self._next] = _mark_parts(raw)
            if self.current is not None and self.current is not current:
                self.current["own"] = self._next

    def _close_block(self) -> None:
        current, count = self.current, len(self.raw)
        super()._close_block()
        if current is not None and len(self.raw) > count:
            self.raw[-1]["own"] = current.get("own")

    def _in_ai_summary(self, item: dict[str, Any]) -> bool:
        elements = [*(item.get("ids") or ()), *([item["own"]] if item.get("own") else [])]
        return any(AI_SUMMARY_MARK.search(" " + self.raw_marks_of.get(element, "") + " ") for element in elements)

    def _subtitle_marks(self, item: dict[str, Any], allowed: frozenset[str]) -> bool:
        ids = item.get("ids") or ()
        elements = [item["own"]] if item.get("own") else []
        if ids and allowed is SUBTITLE_MARKS:
            elements.append(ids[-1])
        marks = set().union(*(self.marks_of.get(element, set()) for element in elements)) if elements else set()
        return bool(marks & allowed) and not marks & NOT_SUBTITLE_MARKS

    def stated_subtitles(self) -> list[str]:
        """What the page itself states as the article's secondary headline or description, normalised."""
        stated = []

        def walk(node: Any) -> None:
            if isinstance(node, list):
                for item in node:
                    walk(item)
            elif isinstance(node, dict):
                if node.get("headline") is not None or node.get("alternativeHeadline") is not None:
                    for key in ("alternativeHeadline", "description"):
                        if isinstance(node.get(key), str):
                            stated.append(node[key])
                walk(node.get("@graph"))
                walk(node.get("mainEntity"))

        for document in self.json_ld:
            try:
                walk(_json.loads(document))
            except ValueError:
                continue
        for key in ("og:description", "description", "twitter:description"):
            stated += self.meta.get(key, [])
        return [text for text in dict.fromkeys(_norm(value) for value in stated) if len(text) >= MIN_SUBTITLE_CHARACTERS]

    @staticmethod
    def _states(text: str, stated: list[str]) -> bool:
        block = _norm(text)
        for value in stated:
            core = _ELLIPSIS.sub("", value)
            if block == value or block == core:
                return True
            if len(core) >= MIN_PREFIX_CHARACTERS and len(block) >= MIN_PREFIX_CHARACTERS and (
                    block.startswith(core) or core.startswith(block) or block[:MIN_PREFIX_CHARACTERS] == core[:MIN_PREFIX_CHARACTERS]):
                return True
        return False

    def stated_headlines(self) -> list[str]:
        """The article's headline as the page states it (JSON-LD ``headline``, ``og:title``, ``twitter:title``), normalised."""
        stated = list(self.meta.get("og:title", [])) + list(self.meta.get("twitter:title", []))
        for document in self.json_ld:
            try:
                nodes = [_json.loads(document)]
            except ValueError:
                continue
            while nodes:
                node = nodes.pop()
                if isinstance(node, list):
                    nodes += node
                elif isinstance(node, dict):
                    if isinstance(node.get("headline"), str):
                        stated.append(node["headline"])
                    nodes += [node.get("@graph"), node.get("mainEntity")]
        return [text for text in dict.fromkeys(_norm(value) for value in stated) if text]

    def _title_is_the_headline(self, title: str) -> bool:
        """Whether the title block is the article's headline. A page whose ``h1`` is the site's name has no reliable header
        region; where the page states no headline at all, the title is taken as it is."""
        stated, title = self.stated_headlines(), _norm(title)
        return not stated or any(title == value or (len(title) >= 15 and (title in value or value in title)) for value in stated)

    def blocks(self) -> list[dict[str, Any]]:
        if getattr(self, "_blocks", None) is not None:
            return [dict(block) for block in self._blocks]
        blocks = super().blocks()
        for block, item in zip(blocks, self.raw):
            if self._in_ai_summary(item):
                block["role"], block["module"] = E.ROLE_NON_BODY, E.MODULE_AI_SUMMARY
        self._blocks = blocks
        title = next((i for i, block in enumerate(blocks) if block["kind"] == "title"), None)
        first_body = next((i for i, block in enumerate(blocks) if block["role"] == E.ROLE_BODY), None)
        if title is None or first_body is None or first_body < title or not self._title_is_the_headline(blocks[title]["text"]):
            return [dict(block) for block in blocks]
        stated, title_text = self.stated_subtitles(), _norm(blocks[title]["text"])
        # the leading body blocks that are an explicitly marked subtitle element, or a heading (never a paragraph: that is the
        # entradilla) whose text the page states as its secondary headline or description
        position = first_body
        while position < len(blocks) and blocks[position]["role"] == E.ROLE_BODY and blocks[position]["kind"] in SUBTITLE_KINDS:
            block = blocks[position]
            if self._subtitle_marks(self.raw[position], LEADING_BODY_MARKS):
                block.update(kind=E.KIND_SUBTITLE, role=E.ROLE_TITLE, basis=E.SUBTITLE_BY_MARKUP)
            elif block["kind"] == "heading" and len(block["text"]) >= MIN_SUBTITLE_CHARACTERS and self._states(block["text"], stated):
                block.update(kind=E.KIND_SUBTITLE, role=E.ROLE_TITLE, basis=E.SUBTITLE_STATED_BY_PAGE)
            else:
                break
            position += 1
        marked = False
        for i in range(title + 1, first_body):
            block, item = blocks[i], self.raw[i]
            if block["role"] != E.ROLE_NON_BODY or "module" in block or block["kind"] not in SUBTITLE_KINDS \
                    or len(block["text"]) < MIN_SUBTITLE_CHARACTERS or _norm(block["text"]) == title_text \
                    or item.get("link", 0) > MAX_LINK_SHARE * len(block["text"]):      # a link to another article
                continue
            if self._states(block["text"], stated):
                block.update(kind=E.KIND_SUBTITLE, role=E.ROLE_TITLE, basis=E.SUBTITLE_STATED_BY_PAGE)
            elif not marked and len(block["text"]) >= MIN_MARKED_SUBTITLE_CHARACTERS and self._subtitle_marks(item, SUBTITLE_MARKS):
                # by markup alone: the first marked block of the header only -- labels, dialogs and dates under the same class
                # names follow it (measured: kicker labels, login dialogs, event dates)
                block.update(kind=E.KIND_SUBTITLE, role=E.ROLE_TITLE, basis=E.SUBTITLE_BY_MARKUP)
                marked = True
        return [dict(block) for block in blocks]


def extract_v2(body: bytes, *, body_sha256: str, content_type: str, declared_charset: str = E.UNKNOWN,
               content_encoding: str = E.IDENTITY) -> E.Extraction:
    """``article_html/0.2.0``: 0.1.0 with subtitles and machine-summary modules kept apart (``extraction/2``)."""
    if not isinstance(body, bytes):
        raise E.ExtractionError("a body is bytes")
    if sha256_bytes(body) != require_sha256(body_sha256, "body_sha256"):
        raise E.ExtractionError("the body offered is not the body the digest names")
    if not isinstance(content_type, str) or not content_type:
        raise E.ExtractionError("content_type is the declared media type or 'unknown'")
    record: dict[str, Any] = {
        "schema": E.EXTRACTION_SCHEMA_2,
        "extractor": {"name": NAME, "version": VERSION_2},
        "input": {"body_sha256": body_sha256, "body_size_bytes": len(body), "declared_content_type": content_type,
                  "declared_charset": declared_charset, "content_encoding": content_encoding},
        "outcome": E.OUTCOME_EXTRACTED,
        "reason": E.NOT_APPLICABLE,
        "decoding": {"charset": E.NOT_APPLICABLE, "basis": E.NOT_APPLICABLE, "replaced_characters": 0},
        "metadata": {name: {"value": E.UNKNOWN, "basis": E.UNKNOWN, "candidates": []} for name in E.METADATA_FIELDS},
        "blocks": [],
    }
    try:
        body = E.decode_content(body, content_encoding) if body else body
        reason = E._refusal(body, content_type)
    except E.ContentDecodingError as error:
        reason = error.reason
    if reason is None:
        text, record["decoding"] = E._decode(body, declared_charset)
        parser = _Parser2()
        parser.feed(text)
        parser.close()
        record["blocks"] = parser.blocks()
        record["metadata"] = E._metadata(parser)
    else:
        record["outcome"], record["reason"] = E.OUTCOME_NOT_EXTRACTABLE, reason
    record["extracted_text_sha256"] = sha256_bytes(E.extracted_text_bytes(record["blocks"]))
    record["body_text_sha256"] = sha256_bytes(E.body_text(record["blocks"]).encode("utf-8"))
    return E.Extraction(record)


ARTICLE_2 = E.Extractor(NAME, VERSION_2, extract_v2, E.LIFECYCLE_CANDIDATE, record_schema=E.EXTRACTION_SCHEMA_2)


# --- article_html/0.3.0 (CPD-0040): the title surface repaired -- 0.2.0 with the title chosen, not assumed -------------------
#
# The operator's review of the 0.2.0 sample (2026-11-15) found three wrong title surfaces; the study of the 4,759 stored pages
# found their general form (CPD-0040 §2). 0.3.0 keeps 0.2.0's body rule, machine-summary modules and record schema
# (``extraction/2``) and changes only which blocks stand on the title surface:
#
# 1. **Title.** 0.1.0 and 0.2.0 take the first ``h1``. 0.3.0 takes the first ``h1`` that is the headline the page states
#    (JSON-LD ``headline``, ``og:title``, ``twitter:title``, ``<title>``; equal, or one contains the other, or equal to one part
#    of a stated title split at `` | `` / `` - `` / `` / ``); a page whose ``h1`` is its logo or edition label before the article's
#    own ``h1`` (``py_la_nacion``, ``ec_primicias``) gets the article's. Where no ``h1`` is a stated headline, the first ``h1``
#    stays the title -- the printed headline often differs from the search title (``ar_clarin``, ``mx_el_universal``) --
#    unless it is the page's branding or a section label: the site name the page states (``og:site_name``,
#    ``application-name``, the JSON-LD publisher), what remains of a stated title once a stated headline is taken out of it
#    (``La Nación / <headline>``), or a section the page states (``articleSection``, ``article:section``, a breadcrumb item
#    but the last). Then the page has **no title block**: the title is unknown on the text surface (the record's
#    ``metadata.title`` keeps what the page states, with its basis) -- never the newspaper's name, never a reconstruction.
#    An ``h1`` that is not the title is a ``heading`` and never BODY (as the first ``h1`` never was).
# 2. **Subtitle.** 0.2.0's two paths, and only where the chosen title is the stated headline (or the page states none), with
#    five exclusions found on the stored pages:
#    a. a block inside a newsletter, subscription or promotion module (``PROMO_MARKS`` on any enclosing element) --
#       "Lo bueno que es estar informado ... desde tu correo electrónico" (``co_el_espectador``);
#    b. a field of a data sheet: a block that opens with a short label and a colon and stands next to another such block
#       ("Lugar: …", "Fecha de inicio: …", "Horario: …" of an event listing, ``cu_14ymedio``);
#    c. a caption, a credit or a gallery element (``NOT_SUBTITLE_MARKS_3``), on the page-statement path too (0.2.0 checked
#       it on the markup path only);
#    d. one subtitle per stated text: the same description repeated further down (a gallery's captions, a share box, the
#       paywalled copy) is not a second subtitle, and a stated "description" that is the headline itself is not a subtitle
#       source;
#    e. by markup alone, only in the header: at most ``MAX_MARKED_GAP`` blocks after the title (measured on 0.2.0: every
#       marked subtitle within 9 blocks; the 13 beyond 30 were newsletter boxes and teasers of other articles).
#
# BODY is 0.2.0's, except where the chosen title was a body block under 0.1.0's rule (it is the headline; measured and named in
# CPD-0040). Structural and markup rules only; the one textual form read is the field label of (b). ``CANDIDATE``.

VERSION_3 = "0.3.0"
MAX_MARKED_GAP = 12
PROMO_MARKS = frozenset({"newsletter", "newsletters", "boletin", "boletines", "suscripcion", "suscripciones", "suscribete",
                         "subscribe", "subscription", "subscriptions", "promo", "promocion", "signup", "registro"})
NOT_SUBTITLE_MARKS_3 = NOT_SUBTITLE_MARKS | {"gallery", "galeria", "slider", "carousel", "slide", "slideshow", "epigraphe"}
_FIELD = _re.compile(r"^\s*[A-ZÁÉÍÓÚÑ][\wáéíóúñü]*(?:\s+[\wáéíóúñü]+){0,2}\s*:\s+\S")
_TITLE_PARTS = _re.compile(r"\s+(?:\||/|-|–|—|·|::)\s+")
_SEPARATOR_EDGE = _re.compile(r"^\s*(?:\||/|-|–|—|·|::)\s+|\s+(?:\||/|-|–|—|·|::)\s*$")


class _Parser3(_Parser2):
    """0.2.0's parser; the title is chosen among the ``h1`` blocks and the subtitle paths are bounded (``article_html/0.3.0``)."""

    def site_names(self) -> set[str]:
        names = [*self.meta.get("og:site_name", []), *self.meta.get("application-name", [])]
        for document in self.json_ld:
            try:
                nodes = [_json.loads(document)]
            except ValueError:
                continue
            while nodes:
                node = nodes.pop()
                if isinstance(node, list):
                    nodes += node
                elif isinstance(node, dict):
                    publisher = node.get("publisher")
                    for item in publisher if isinstance(publisher, list) else [publisher]:
                        if isinstance(item, dict) and isinstance(item.get("name"), str):
                            names.append(item["name"])
                    if node.get("@type") in ("WebSite", "Organization", "NewsMediaOrganization") and isinstance(node.get("name"), str):
                        names.append(node["name"])
                    nodes += [node.get("@graph"), node.get("mainEntity")]
        headlines = {_norm(v) for v in [*self._json_ld_strings("headline"), *self.meta.get("og:title", []), *self.meta.get("twitter:title", [])]}
        # what a stated title keeps besides a stated headline: "La Nación / <headline>" -> "la nación",
        # "<headline> - Juventud Rebelde - Diario de la juventud cubana" -> "juventud rebelde - diario de la juventud cubana"
        for title in {_norm(t) for t in [*self.meta.get("title", []), *self.meta.get("og:title", [])]}:
            for headline in headlines - {title}:
                if not headline or headline == title:
                    continue
                for rest in (title[len(headline):] if title.startswith(headline) else None,
                             title[:-len(headline)] if title.endswith(headline) else None):
                    if rest is None:
                        continue
                    stripped = _SEPARATOR_EDGE.sub("", rest)
                    if stripped and stripped != rest.strip():        # the headline was set off by a separator
                        names += [stripped, *_TITLE_PARTS.split(stripped)]
        return {_norm(name) for name in names if name and _norm(name)}

    def _json_ld_strings(self, key: str) -> list[str]:
        out = []
        for document in self.json_ld:
            try:
                nodes = [_json.loads(document)]
            except ValueError:
                continue
            while nodes:
                node = nodes.pop()
                if isinstance(node, list):
                    nodes += node
                elif isinstance(node, dict):
                    value = node.get(key)
                    out += [value] if isinstance(value, str) else [v for v in value if isinstance(v, str)] if isinstance(value, list) else []
                    nodes += [node.get("@graph"), node.get("mainEntity")]
        return out

    def section_labels(self) -> set[str]:
        labels = [*self._json_ld_strings("articleSection"), *self.meta.get("article:section", [])]
        for document in self.json_ld:
            try:
                nodes = [_json.loads(document)]
            except ValueError:
                continue
            while nodes:
                node = nodes.pop()
                if isinstance(node, list):
                    nodes += node
                elif isinstance(node, dict):
                    if node.get("@type") == "BreadcrumbList" and isinstance(node.get("itemListElement"), list):
                        items = [i for i in node["itemListElement"] if isinstance(i, dict)]
                        for item in items[:-1]:
                            name = item.get("name")
                            if not isinstance(name, str) and isinstance(item.get("item"), dict):
                                name = item["item"].get("name")
                            if isinstance(name, str):
                                labels.append(name)
                    nodes += [node.get("@graph"), node.get("mainEntity")]
        return {_norm(label) for label in labels if isinstance(label, str) and _norm(label)}

    def _is_stated_headline(self, text: str) -> bool:
        stated, text = self.stated_headlines() + [_norm(t) for t in self.meta.get("title", [])], _norm(text)
        for value in stated:
            if text == value or (len(text) >= 15 and (text in value or value in text)):
                return True
            if len(text) >= 15 and text in _TITLE_PARTS.split(value):
                return True
        return False

    def choose_title(self, blocks: list[dict[str, Any]]) -> int | None:
        """The index of the title block among the ``h1`` blocks, or ``None`` (no ``h1`` is the article's headline)."""
        h1 = [i for i, item in enumerate(self.raw) if item["tag"] == "h1"]
        if not h1:
            return None
        names = self.site_names() | self.section_labels()      # branding and section labels are never the headline
        if self.stated_headlines():
            for i in h1:
                if _norm(blocks[i]["text"]) not in names and self._is_stated_headline(blocks[i]["text"]):
                    return i
        return None if _norm(blocks[h1[0]]["text"]) in names else h1[0]

    def _field_like(self, blocks: list[dict[str, Any]], i: int) -> bool:
        """A field of a data sheet: label and colon, beside another such block of the same element kind (same tag, same marks)."""
        if not _FIELD.match(blocks[i]["text"]):
            return False

        def shape(j: int) -> tuple[str, frozenset[str]]:
            return self.raw[j]["tag"], frozenset(self.marks_of.get(self.raw[j].get("own"), set()))

        return any(0 <= j < len(blocks) and _FIELD.match(blocks[j]["text"]) and shape(j) == shape(i) for j in (i - 1, i + 1))

    def _excluded(self, blocks: list[dict[str, Any]], i: int, title: int) -> bool:
        item = self.raw[i]
        ids = item.get("ids") or ()
        # a module of its own: marked as a newsletter / subscription / promotion box, and not the element around the title too
        around_title = set(self.raw[title].get("ids") or ())
        enclosing = [element for element in [*ids, *([item["own"]] if item.get("own") else [])] if element not in around_title]
        if any(self.marks_of.get(element, set()) & PROMO_MARKS for element in enclosing):
            return True
        near = [item["own"]] if item.get("own") else []
        near += [ids[-1]] if ids else []
        if any(self.marks_of.get(element, set()) & NOT_SUBTITLE_MARKS_3 for element in near):
            return True
        return self._field_like(blocks, i)

    def blocks(self) -> list[dict[str, Any]]:
        if getattr(self, "_blocks", None) is not None:
            return [dict(block) for block in self._blocks]
        blocks = _Parser.blocks(self)
        for block, item in zip(blocks, self.raw):
            if self._in_ai_summary(item):
                block["role"], block["module"] = E.ROLE_NON_BODY, E.MODULE_AI_SUMMARY
        chosen = self.choose_title(blocks)
        for i, block in enumerate(blocks):
            if block["kind"] == "title" and i != chosen:
                block["kind"], block["role"] = "heading", E.ROLE_NON_BODY        # an h1 that is not the headline: never body
            elif i == chosen:
                block["kind"], block["role"] = "title", E.ROLE_TITLE
        self._blocks = blocks
        first_body = next((i for i, block in enumerate(blocks) if block["role"] == E.ROLE_BODY), None)
        if chosen is None or first_body is None or first_body < chosen or not self._title_is_the_headline(blocks[chosen]["text"]):
            return [dict(block) for block in blocks]
        title_text = _norm(blocks[chosen]["text"])
        headlines = set(self.stated_headlines()) | {title_text}
        # a stated "description" that is the headline itself is no subtitle source
        stated = [v for v in self.stated_subtitles() if not self._states(v, list(headlines)) and not any(
            self._states(h, [v]) for h in headlines)]
        used: set[str] = set()

        def stated_value(text: str) -> str | None:
            return next((v for v in stated if self._states(text, [v])), None)

        marked = False
        for i in range(chosen + 1, first_body):          # the header, in page order (it comes before the body)
            block, item = blocks[i], self.raw[i]
            if block["role"] != E.ROLE_NON_BODY or "module" in block or block["kind"] not in SUBTITLE_KINDS \
                    or len(block["text"]) < MIN_SUBTITLE_CHARACTERS or _norm(block["text"]) in headlines \
                    or item.get("link", 0) > MAX_LINK_SHARE * len(block["text"]) or self._excluded(blocks, i, chosen):
                continue
            value = stated_value(block["text"])
            if value is not None:
                if value not in used:
                    block.update(kind=E.KIND_SUBTITLE, role=E.ROLE_TITLE, basis=E.SUBTITLE_STATED_BY_PAGE)
                    used.add(value)
            elif not marked and i - chosen <= MAX_MARKED_GAP and len(block["text"]) >= MIN_MARKED_SUBTITLE_CHARACTERS \
                    and self._subtitle_marks(item, SUBTITLE_MARKS):
                block.update(kind=E.KIND_SUBTITLE, role=E.ROLE_TITLE, basis=E.SUBTITLE_BY_MARKUP)
                marked = True
        # the leading body blocks that are an explicitly marked subtitle element, or a stated heading (0.2.0's rule)
        position = first_body
        while position < len(blocks) and blocks[position]["role"] == E.ROLE_BODY and blocks[position]["kind"] in SUBTITLE_KINDS:
            block = blocks[position]
            if self._excluded(blocks, position, chosen):
                break
            value = stated_value(block["text"]) if block["kind"] == "heading" and len(block["text"]) >= MIN_SUBTITLE_CHARACTERS else None
            if self._subtitle_marks(self.raw[position], LEADING_BODY_MARKS):
                block.update(kind=E.KIND_SUBTITLE, role=E.ROLE_TITLE, basis=E.SUBTITLE_BY_MARKUP)
            elif value is not None and value not in used:
                block.update(kind=E.KIND_SUBTITLE, role=E.ROLE_TITLE, basis=E.SUBTITLE_STATED_BY_PAGE)
                used.add(value)
            else:
                break
            position += 1
        return [dict(block) for block in blocks]


def extract_v3(body: bytes, *, body_sha256: str, content_type: str, declared_charset: str = E.UNKNOWN,
               content_encoding: str = E.IDENTITY) -> E.Extraction:
    """``article_html/0.3.0``: 0.2.0 with the title chosen among the ``h1`` blocks and bounded subtitle paths (``extraction/2``)."""
    if not isinstance(body, bytes):
        raise E.ExtractionError("a body is bytes")
    if sha256_bytes(body) != require_sha256(body_sha256, "body_sha256"):
        raise E.ExtractionError("the body offered is not the body the digest names")
    if not isinstance(content_type, str) or not content_type:
        raise E.ExtractionError("content_type is the declared media type or 'unknown'")
    record: dict[str, Any] = {
        "schema": E.EXTRACTION_SCHEMA_2,
        "extractor": {"name": NAME, "version": VERSION_3},
        "input": {"body_sha256": body_sha256, "body_size_bytes": len(body), "declared_content_type": content_type,
                  "declared_charset": declared_charset, "content_encoding": content_encoding},
        "outcome": E.OUTCOME_EXTRACTED,
        "reason": E.NOT_APPLICABLE,
        "decoding": {"charset": E.NOT_APPLICABLE, "basis": E.NOT_APPLICABLE, "replaced_characters": 0},
        "metadata": {name: {"value": E.UNKNOWN, "basis": E.UNKNOWN, "candidates": []} for name in E.METADATA_FIELDS},
        "blocks": [],
    }
    try:
        body = E.decode_content(body, content_encoding) if body else body
        reason = E._refusal(body, content_type)
    except E.ContentDecodingError as error:
        reason = error.reason
    if reason is None:
        text, record["decoding"] = E._decode(body, declared_charset)
        parser = _Parser3()
        parser.feed(text)
        parser.close()
        record["blocks"] = parser.blocks()
        record["metadata"] = E._metadata(parser)
    else:
        record["outcome"], record["reason"] = E.OUTCOME_NOT_EXTRACTABLE, reason
    record["extracted_text_sha256"] = sha256_bytes(E.extracted_text_bytes(record["blocks"]))
    record["body_text_sha256"] = sha256_bytes(E.body_text(record["blocks"]).encode("utf-8"))
    return E.Extraction(record)


ARTICLE_3 = E.Extractor(NAME, VERSION_3, extract_v3, E.LIFECYCLE_CANDIDATE, record_schema=E.EXTRACTION_SCHEMA_2)
PREFERRED = ARTICLE_3      # CPD-0040's preferred candidate of this module; the preferred extractor is now extraction_body.ARTICLE_4 (CPD-0041)


def subtitles(record: Any) -> list[str]:
    """The subtitle texts of an extraction record, in order (none under ``extraction/1``)."""
    return [block["text"] for block in record["blocks"] if block["kind"] == E.KIND_SUBTITLE]


__all__ = ["ARTICLE", "ARTICLE_2", "ARTICLE_3", "PREFERRED", "extract", "extract_v2", "extract_v3", "subtitles", "NAME", "VERSION",
           "VERSION_2", "VERSION_3"]
