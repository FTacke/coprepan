"""What the publisher states about an article, as stated (``publisher-metadata/1``, CPD-0039).

The first of four kinds of evidence that are never mixed (CPD-0039 §10):

1. **publisher statement** -- this module: values copied from the page's own markup, with the place they came from;
2. deterministic derivation from those statements (``coprepan.editorial_metadata``, ``coprepan.provenance``);
3. document relations from a text comparison (``coprepan.text_reuse``);
4. a later scientific classification of the content (not built).

Nothing here is interpreted, normalised or completed. A value is kept verbatim (whitespace collapsed, cut at
``MAX_CHARACTERS``) with its ``basis``; a field the page does not state is an empty list, never a default. The harvest is a
pure function of the decoded page and its address, so it can be re-derived from the preserved bytes at any time.

Sources read (each a ``basis``): the JSON-LD object(s) that describe the article (a ``@type`` naming an Article or Posting) --
``@type``, ``articleSection``, ``genre``, ``author``, ``creator``, ``sourceOrganization``, ``copyrightHolder``, ``publisher``,
``provider``, ``creditText``, ``dateline``; a JSON-LD ``BreadcrumbList``; the ``meta`` tags ``article:section``,
``parsely-section``, ``section``, ``author``, ``article:author``, ``og:type``; and the path of the article's address.
"""

from __future__ import annotations

import html as _html
import json
import re
from typing import Any
from urllib.parse import unquote, urlsplit

VERSION = "publisher-metadata/1"
MAX_CHARACTERS = 300
ARTICLE_TYPE = re.compile(r"(Article|Posting|Report)$")
_LD = re.compile(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", re.S | re.I)
_META = re.compile(r"<meta\s[^>]*>", re.I)
_ATTRIBUTE = re.compile(r"""([a-zA-Z_:.-]+)\s*=\s*("([^"]*)"|'([^']*)')""")
_SPACE = re.compile(r"\s+")
META_SECTIONS = {"article:section": "meta_article_section", "parsely-section": "meta_parsely_section", "section": "meta_section"}
META_AUTHORS = {"author": "meta_author", "article:author": "meta_article_author"}
ORGANISATION_ROLES = ("sourceOrganization", "copyrightHolder", "publisher", "provider")


def _text(value: Any) -> str:
    return _SPACE.sub(" ", _html.unescape(str(value))).strip()[:MAX_CHARACTERS]


def _types(node: dict[str, Any]) -> list[str]:
    value = node.get("@type")
    return [t for t in (value if isinstance(value, list) else [value]) if isinstance(t, str)]


def _nodes(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _nodes(item)
    elif isinstance(value, list):
        for item in value:
            yield from _nodes(item)


def _parties(value: Any) -> list[tuple[str, str]]:
    """``(name, type)`` of a JSON-LD person / organisation value (a string, an object, or a list of them)."""
    out = []
    for item in value if isinstance(value, list) else [value]:
        if isinstance(item, str) and item.strip():
            out.append((_text(item), ""))
        elif isinstance(item, dict) and isinstance(item.get("name"), (str, list)):
            names = item["name"] if isinstance(item["name"], list) else [item["name"]]
            for name in names:
                if isinstance(name, str) and name.strip():
                    out.append((_text(name), ",".join(_types(item))))
    return out


def harvest(html: str, *, url: str) -> dict[str, Any]:
    """The publisher's statements about the article on one page."""
    documents = []
    for block in _LD.findall(html):
        try:
            documents.append(json.loads(block.strip()))
        except ValueError:
            continue
    out: dict[str, Any] = {"version": VERSION, "article_types": [], "genre": [], "sections": [], "breadcrumb": [],
                           "authors": [], "organisations": [], "credit_text": [], "dateline": [], "og_type": [], "url_path": []}

    def add(field: str, value: Any) -> None:
        if value not in out[field]:
            out[field].append(value)

    for node in (n for document in documents for n in _nodes(document)):
        types = _types(node)
        if any(ARTICLE_TYPE.search(t) for t in types):
            for t in types:
                add("article_types", t)
            for key, field in (("genre", "genre"), ("dateline", "dateline"), ("creditText", "credit_text")):
                for value in node.get(key) if isinstance(node.get(key), list) else [node.get(key)]:
                    if isinstance(value, str) and value.strip():
                        add(field, _text(value))
            for value in node.get("articleSection") if isinstance(node.get("articleSection"), list) else [node.get("articleSection")]:
                if isinstance(value, str) and value.strip():
                    add("sections", {"value": _text(value), "basis": "json_ld_articleSection"})
            for key in ("author", "creator"):
                for name, kind in _parties(node.get(key)):
                    add("authors", {"name": name, "type": kind, "basis": f"json_ld_{key}"})
            for role in ORGANISATION_ROLES:
                for name, kind in _parties(node.get(role)):
                    add("organisations", {"name": name, "type": kind, "role": role})
        if "BreadcrumbList" in types and not out["breadcrumb"]:
            items = [item for item in node.get("itemListElement") or [] if isinstance(item, dict)]
            items.sort(key=lambda item: int(item["position"]) if str(item.get("position", "")).isdigit() else 0)
            for item in items:
                name = item.get("name")
                if name is None and isinstance(item.get("item"), dict):
                    name = item["item"].get("name")
                if isinstance(name, str) and name.strip():
                    out["breadcrumb"].append(_text(name))
    for tag in _META.findall(html):
        attributes = {m.group(1).lower(): (m.group(3) if m.group(3) is not None else m.group(4)) for m in _ATTRIBUTE.finditer(tag)}
        key = (attributes.get("property") or attributes.get("name") or "").strip().lower()
        content = attributes.get("content")
        if not key or content is None or not content.strip():
            continue
        if key in META_SECTIONS:
            add("sections", {"value": _text(content), "basis": META_SECTIONS[key]})
        elif key in META_AUTHORS:
            add("authors", {"name": _text(content), "type": "", "basis": META_AUTHORS[key]})
        elif key == "og:type":
            add("og_type", _text(content))
    out["url_path"] = [unquote(part) for part in urlsplit(url).path.split("/") if part][:6]
    return out


__all__ = ["harvest", "VERSION"]
