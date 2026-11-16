"""``docview/1``: a model-independent text view of a stored page, for human gold (CPD-0044).

The view splits the page's body text at the HTML block boundaries and nothing else. It shares **no** rule with any extractor
under test: no container choice, no scoring, no module vocabulary, no template table, no selection. Every text of the body is in
it -- navigation, captions, embeds, footers, hidden text -- so that a reviewer can find article text wherever it stands, and the
machine output can later be aligned to it word by word, independent of the extractor's block boundaries.

A **segment** is the text between two block boundaries (an opening or closing block element or a ``<br>``), white space folded,
the characters otherwise as published. Each carries the innermost block tag and *markup facts* -- inside ``nav``, ``header``,
``footer``, ``aside``, ``figure``, ``form``, a table cell, a list, a heading, a quote; hidden by ``hidden``, ``aria-hidden`` or an
inline ``display:none`` / ``visibility:hidden``; the share of its characters inside links. These are presentation facts a reader
sees, not machine decisions. ``script``, ``style``, ``template``, ``noscript``, ``svg`` and ``math`` carry no reader-visible text and
are left out; a ``select`` becomes one segment of its options. The ``<head>`` is left out.

Decoding (charset, content encoding) is the stored page's own, through ``extraction``'s decoder: what bytes mean is not a
BODY decision.
"""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from typing import Any

VERSION = "docview/1"
BLOCKS = frozenset({"address", "article", "aside", "blockquote", "body", "caption", "center", "dd", "details", "dialog", "div", "dl",
                    "dt", "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hgroup",
                    "hr", "html", "li", "main", "menu", "nav", "ol", "p", "pre", "section", "summary", "table", "tbody", "td", "tfoot",
                    "th", "thead", "tr", "ul", "button", "select", "label", "legend", "iframe", "video", "audio", "picture", "time"})
SKIP = frozenset({"script", "style", "template", "noscript", "svg", "math", "head", "title"})
VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr", "keygen"})
CONTEXT = {"nav": "nav", "header": "header", "footer": "footer", "aside": "aside", "figure": "figure", "figcaption": "figure",
           "form": "form", "td": "table", "th": "table", "li": "list", "dd": "list", "dt": "list", "blockquote": "quote",
           "h1": "heading", "h2": "heading", "h3": "heading", "h4": "heading", "h5": "heading", "h6": "heading"}
_HIDDEN_STYLE = re.compile(r"(display\s*:\s*none|visibility\s*:\s*hidden)", re.I)
_SPACE = re.compile(r"\s+")


class _View(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool]] = []        # (tag, hidden)
        self.skip = 0
        self.skip_tag: list[str] = []
        self.parts: list[str] = []
        self.link = 0
        self.segments: list[dict[str, Any]] = []
        self.in_select = 0
        self.options: list[str] = []

    # -- the current segment ------------------------------------------------------------------------------------------------

    def _flush(self) -> None:
        text = _SPACE.sub(" ", "".join(self.parts)).strip()
        if text:
            tags = [t for t, _ in self.stack]
            block = next((t for t in reversed(tags) if t in BLOCKS), "body")
            flags = sorted({CONTEXT[t] for t in tags if t in CONTEXT} | ({"hidden"} if any(h for _, h in self.stack) else set()))
            self.segments.append({"i": len(self.segments), "text": text, "tag": block, "flags": flags,
                                  "link_share": round(min(1.0, self.link / max(1, len(text))), 3),
                                  "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})
        self.parts, self.link = [], 0

    # -- parser events ------------------------------------------------------------------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self.skip and self.skip_tag[-1] == "head" and tag == "body":
            self.skip, self.skip_tag = 0, []                     # a head never closed ends where the body begins
        if self.skip:
            if tag == self.skip_tag[-1] and tag not in VOID:
                self.skip += 1
            return
        if tag in SKIP:
            if tag not in VOID:
                self.skip, self.skip_tag = 1, [tag]
            return
        if tag == "br":
            self._flush()
            return
        if tag in BLOCKS:
            self._flush()
        if tag == "select":
            self.in_select += 1
        if tag in VOID:
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        hidden = "hidden" in a or a.get("aria-hidden", "").lower() == "true" or bool(_HIDDEN_STYLE.search(a.get("style", "")))
        self.stack.append((tag, hidden))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self.skip or tag in SKIP:
            return
        if tag == "br":
            self._flush()
            return
        if tag in BLOCKS:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.skip:
            if tag == self.skip_tag[-1]:
                self.skip -= 1
            return
        if tag in VOID or not any(t == tag for t, _ in self.stack):
            return
        if tag in BLOCKS:
            self._flush()
        if tag == "select" and self.in_select:
            self.in_select -= 1
            if self.options:
                self.parts.append(" | ".join(self.options))
                self.options = []
            self._flush()
        while self.stack:
            t, _ = self.stack.pop()
            if t == tag:
                break

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        if self.in_select:
            text = _SPACE.sub(" ", data).strip()
            if text:
                self.options.append(text)
            return
        self.parts.append(data)
        if any(t == "a" for t, _ in self.stack):
            self.link += len(_SPACE.sub(" ", data).strip())

    def close(self) -> None:
        super().close()
        self._flush()


def segments(html: str) -> list[dict[str, Any]]:
    """The page's body text as ``docview/1`` segments, in document order."""
    view = _View()
    view.feed(html or "")
    view.close()
    return view.segments


def view_sha256(segs: list[dict[str, Any]]) -> str:
    """One digest over the whole view: the segment digests in order."""
    return hashlib.sha256("\n".join(s["sha256"] for s in segs).encode("ascii")).hexdigest()


__all__ = ["VERSION", "segments", "view_sha256"]
