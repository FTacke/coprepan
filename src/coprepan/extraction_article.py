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


ARTICLE = E.Extractor(NAME, VERSION, extract, E.LIFECYCLE_CANDIDATE)
E.EXTRACTORS.setdefault(ARTICLE.stage_version, ARTICLE)

__all__ = ["ARTICLE", "extract", "NAME", "VERSION"]
