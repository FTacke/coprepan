"""``article_html/0.4.0`` (CPD-0041): the BODY selected block by block, every decision recorded in the record (``extraction/3``).

0.3.0's title and subtitle surface and its container rule (``coprepan.extraction_article``, unchanged), with the BODY decided
block by block. Every block whose membership differs from what the container rule alone gives carries ``selection``
(``{"rule", "decision", "reason"}``); its text and position stay as they are, so the BODY before the selection is the record's
blocks with the selection undone (:func:`body_before_selection`).

**Container choice.** Text inside a form control (``select`` / ``option`` / ``textarea`` / ``button`` …) is never scored and
never BODY -- an author filter of several hundred names was chosen as the article on 30 stored pages (``gt_prensa_libre``,
``pr_el_nuevo_dia``). Nothing else changes in the container choice: module marks decide block by block, never the container
(a "cuerpo ad" class stands on the element around the whole article at ``cl_cooperativa``; hiding marked text from the
scoring was measured and dropped -- it moved the container away from the article on 253 pages).

**Excluded** from the BODY (reason in ``extraction.SELECTION_EXCLUDING``), in this order:

1. ``form_control``; ``no_text`` (no letter or digit: ad-slot placeholders of zero-width characters);
2. ``module_*``: the block's own element, or an element between the container and the block, carries a mark of
   ``MODULE_MARKS`` (advertising, share bars, related-article lists, newsletter boxes, breadcrumbs, tag lists, bylines, captions
   and photo credits, date lines, social-media embeds, audio / player controls, page buttons, channel promotions) -- and that
   element holds less than ``MODULE_MAX_SHARE`` of the container's text, so a mark on the article itself (a WordPress
   ``tag-…`` class on the post) never removes the article;
3. ``provenance_ai_note`` / ``provenance_agency_note``: a block that is a production note in a form of ``ai-disclosure/1`` or
   an agency material note ("Con información de EFE"); it stays in the record and in the provenance layers;
4. ``duplicate_block``: the same text (at least ``MIN_DUPLICATE_WORDS`` words) as an earlier BODY block -- a pull quote, a
   lazy-load copy; a repeated short line (a refrain, a list label) stays;
5. ``outlet_template``: a block whose text is in the pinned template table (``TEMPLATES_PATH``: digests -- never texts -- of
   blocks that one outlet prints in several unrelated articles of the reference population: labels such as "Publicidad",
   "Escuchar", promotions, submission notes; built by ``scripts/study_body_quality.py templates``), unless it is a heading
   followed by a BODY paragraph that is not a template (a recurring sub-heading of real text);
6. ``trailing_heading``: label headings (at most ``MAX_TRAILING_HEADING_WORDS`` words) that end the BODY with no running text
   after them ("Temas relacionados", "VER MÁS"); a sentence-length heading there leads into an embed and stays;
7. ``repeated_label``: a short label (at most ``MAX_LABEL_WORDS`` words, no digit, no colon, no sentence end, not a heading)
   that the BODY prints ``MIN_LABEL_REPEATS`` times or more -- the kicker of every card of a teaser list ("Puedes ver",
   "Música"); a rating, a date or a data field that repeats in a real list ("Fase: Primer Hexagonal") stays.

A byline mark (2) counts at the BODY's edges only: between paragraphs an "author" element holds a pull quote or the profile
line of a person the article quotes (``es_el_mundo``). Templates need ``5`` unrelated articles of one outlet; at 3-4 a block is
listed as recurring and reported, not removed (a recipe heading, a poll's technical sheet recur that often).

**Included** in the BODY (reason in ``extraction.SELECTION_INCLUDING``), never a title, subtitle, caption, module or link list:
a paragraph of at least ``MIN_INCLUDED_WORDS`` words whose text the page states as part of its JSON-LD ``articleBody``
(``stated_article_body``); and the lead -- the nearest block with text before the first BODY block -- when it is a paragraph of
at least ``MIN_LEAD_WORDS`` words in the same ``<article>`` element as the container, with no navigation / aside / footer /
form / figure / header and no module mark in between, and not the page's stated description (``lead_paragraph``: the first
paragraph outside the body component, ``cr_la_nacion``). A wider rule -- every paragraph of the article element -- was measured
and dropped: a third of what it added on pages with a stated articleBody was not in it (captions, author biographies).

No block is split, shortened or rewritten; foreign material *inside* a block stays and is reported by
``coprepan.body_quality``. Structural rules and digest matches only; no outlet rule, no lexical deletion. ``CANDIDATE``.

``article_html/0.4.1`` (CPD-0042) is 0.4.0 with two corrections of the inclusions, both found by the BODY control of
2026-11-15 and checked on every stored page:

* **no copy**: a paragraph is never included when its text, a trailing ellipsis set aside, is the *beginning* of a block the
  BODY already holds -- the hidden teaser a paywall prints before the full text, cut off with "…" (``co_el_espectador``'s
  ``ee-gated-content__teaser``), was taken as the lead and the BODY began twice (case B37). Only the beginning: a text that
  merely stands somewhere inside a BODY block may stand there in an embed the rules do not see, and then the article's own
  paragraph is the one to keep;
* **teaser cards are not a list**: 0.4.0 took an ``<article>`` that holds other ``<article>`` elements for a list and gave up
  the lead; 0.4.1 does so only when those nested articles hold at least ``MODULE_MAX_SHARE`` of its text. A "Noticia
  relacionada" card inside the article (``es_abc``) no longer costs the article its opening paragraph (case B03).

Every other rule is 0.4.0's; 0.4.0 is unchanged.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from . import extraction as E
from . import extraction_article as A
from .canonical import require_sha256, sha256_bytes, sha256_file

VERSION_4 = "0.4.0"
VERSION_4_1 = "0.4.1"
SELECTION_RULE = "body-select/1"
TEMPLATE_RULE = "body-templates/1"
FORM_CONTROLS = frozenset({"select", "option", "optgroup", "datalist", "textarea", "button"})
MODULE_MARKS: dict[str, frozenset[str]] = {
    "module_advertising": frozenset({"ad", "ads", "advert", "adverts", "advertisement", "advertising", "publicidad", "dfp", "adslot",
                                     "adunit", "banner", "banners"}),
    "module_share": frozenset({"share", "sharing", "sharebar", "compartir", "social", "socials"}),
    "module_related": frozenset({"related", "relacionadas", "relacionados", "relacionada", "relacionado",
                                 "recommended", "recomendados", "recomendadas", "recomendado", "outbrain", "taboola"}),
    "module_newsletter": frozenset({"newsletter", "newsletters", "boletin", "boletines", "suscripcion", "suscribete", "subscribe",
                                    "subscription"}),
    "module_breadcrumb": frozenset({"breadcrumb", "breadcrumbs", "crumb", "crumbs", "migas"}),
    "module_tags": frozenset({"tags", "etiquetas", "keywords"}),
    "module_byline": frozenset({"byline", "bylines", "author", "authors", "autor", "autores", "firma"}),
    "module_caption": frozenset({"caption", "captions", "credit", "credits", "credito", "creditos", "figcaption", "gallery", "galeria",
                                 "slider", "carousel", "slideshow"}),
    "module_date": frozenset({"date", "fecha", "timestamp", "datetime"}),
    "module_social_embed": frozenset({"tweet", "twitter", "instagram", "tiktok"}),
    "module_media_controls": frozenset({"audio", "player", "listen", "escuchar", "podcast", "texttoaudio", "tts"}),
    "module_page_controls": frozenset({"btn", "button", "buttons", "comments", "comentarios", "toolbar", "tools"}),
    "module_channel_promo": frozenset({"whatsapp", "telegram"}),
}
_GOOGLE_PROMO = frozenset({"source", "preferred", "preferida", "fuente", "discover", "follow"})   # with "google": a promotion
MODULE_MAX_SHARE = 0.3
MIN_DUPLICATE_WORDS = 12
MIN_INCLUDED_WORDS = 12
MIN_LEAD_WORDS = 25
MIN_SUBHEADING_FOLLOW_WORDS = 12
MAX_TRAILING_HEADING_WORDS = 4
MAX_LABEL_WORDS, MIN_LABEL_REPEATS = 3, 3
MIN_COPY_CHARACTERS = 40             # 0.4.1: a shorter text at the beginning of a BODY block is not taken for a copy of it
_TRAILING_ELLIPSIS = re.compile(r"\s*(?:…|\.\.\.)\s*$")
_SENTENCE_END = re.compile(r"[.!?…:;»”\")]\s*$")
_NOT_LABEL = re.compile(r"[\d:]")
TEMPLATES_PATH = "config/extraction/body-templates_1.json"
TEMPLATES_SCHEMA = "coprepan-body-templates/v1"
_ALNUM = re.compile(r"[^\W_]", re.UNICODE)
_INVISIBLE = dict.fromkeys(map(ord, "­​‌‍⁠﻿"))
_REPOSITORY = Path(__file__).resolve().parents[2]


def template_digest(text: str) -> str:
    """The digest a block's text is looked up by: NFC, invisible characters removed, white space folded, lower case."""
    folded = unicodedata.normalize("NFC", E._WHITESPACE.sub(" ", text.translate(_INVISIBLE).replace("\xa0", " "))).strip().lower()
    return hashlib.sha256(folded.encode("utf-8")).hexdigest()[:24]


_TEMPLATES: dict[str, tuple[str, frozenset[str]]] = {}


def body_templates(path: str = TEMPLATES_PATH, *, root: Path = _REPOSITORY) -> frozenset[str]:
    """The pinned template digests, read once. A missing or foreign table is an error, never an empty table."""
    key = str(root / path)
    if key not in _TEMPLATES:
        file = root / path
        data = json.loads(file.read_text(encoding="utf-8"))
        if data.get("schema") != TEMPLATES_SCHEMA or not isinstance(data.get("digests"), list):
            raise E.ExtractionError(f"{path}: not a {TEMPLATES_SCHEMA} table")
        _TEMPLATES[key] = (sha256_file(file)[0], frozenset(data["digests"]))
    return _TEMPLATES[key][1]


def body_templates_sha256(path: str = TEMPLATES_PATH, *, root: Path = _REPOSITORY) -> str:
    body_templates(path, root=root)
    return _TEMPLATES[str(root / path)][0]


def _provenance_note(block: dict[str, Any]) -> str | None:
    """A production note standing as a block of its own: an AI disclosure in one of ``ai-disclosure/1``'s forms (at most
    ``provenance.MAX_STATEMENT_CHARACTERS``), or a note of agency material ("Con información de EFE", "La información es de
    AFP"). The note stays in the record and in the provenance layers; it is not running text of the article."""
    from . import provenance as P      # noqa: PLC0415  (provenance reads extraction records; imported when first needed)

    text = block["text"]
    # only the forms anchored at the block's start (a note about the text, a summary or an audio version); an image credit
    # matches anywhere in a block and is often the tail of a running paragraph ("... Foto: Imagen creada con IA")
    statements = P.ai_statements({"blocks": [dict(block)]}) if len(text) <= P.MAX_STATEMENT_CHARACTERS else []
    if any(s["form"] not in ("image", "image_caption") for s in statements):
        return "provenance_ai_note"
    note = P._EDITED.match(text) or P._CREDIT_NOTE.match(text)
    if len(text) <= 200 and note and P.agencies_in(note.group(1))[0]:
        return "provenance_agency_note"
    return None


class _Parser4(A._Parser3):
    """0.3.0's parser with the BODY selected block by block (``article_html/0.4.0``)."""

    def __init__(self, templates: frozenset[str] = frozenset(), *, revision: int = 0) -> None:
        super().__init__()
        self.templates = templates
        self.revision = revision              # 0: article_html/0.4.0; 1: 0.4.1 (no copy, teaser cards are not a list)

    @staticmethod
    def _copy_of(text: str, body_keys: set[str]) -> bool:
        """0.4.1: ``text``, a trailing ellipsis set aside, is the beginning of a BODY block -- a cut-off teaser or an echo of
        the paragraph's opening, not more article text."""
        key = _TRAILING_ELLIPSIS.sub("", A._norm(text))
        return len(key) >= MIN_COPY_CHARACTERS and any(body.startswith(key) for body in body_keys)

    def _a_list(self, article: int) -> bool:
        """The ``<article>`` element holds other articles: a list -- under 0.4.1 only when those nested articles hold at least
        ``MODULE_MAX_SHARE`` of its text (teaser cards inside an article are not a list)."""
        nested = [e for e, t in self.tag_of.items() if t == "article" and e != article and article in self._ancestors(e)]
        if not nested:
            return False
        if self.revision < 1:
            return True
        outer = [e for e in nested if not any(n in self._ancestors(e) for n in nested)]
        under = self._text_under()
        return sum(under.get(e, 0) for e in outer) >= MODULE_MAX_SHARE * under.get(article, 0)

    # -- what an element is ------------------------------------------------------------------------------------------------

    def _in_form_control(self, item: dict[str, Any]) -> bool:
        return any(self.tag_of.get(e) in FORM_CONTROLS for e in (item.get("ids") or ()))

    @staticmethod
    def _module_of_marks(marks: set[str]) -> str | None:
        for reason, vocabulary in MODULE_MARKS.items():
            if marks & vocabulary:
                return reason
        if "google" in marks and marks & _GOOGLE_PROMO:
            return "module_channel_promo"
        return None

    def _text_under(self) -> dict[int, int]:
        if getattr(self, "_under", None) is None:
            under: dict[int, int] = {}
            for item in self.raw:
                for e in set(item.get("ids") or ()) | ({item["own"]} if item.get("own") else set()):
                    under[e] = under.get(e, 0) + len(item["text"])
            self._under = under
        return self._under

    def _module(self, item: dict[str, Any], top: int | None) -> str | None:
        """The page module the block stands in: a mark on its own element or on an element below ``top`` (the container or the
        article element; with no ``top``, the two nearest), on an element small against ``top``."""
        ids = list(item.get("ids") or ())
        below = ids[ids.index(top) + 1:] if top in ids else ids[-2:]
        elements = [*below, *([item["own"]] if item.get("own") else [])]
        limit = MODULE_MAX_SHARE * self._text_under().get(top, 0) if top is not None else None
        for element in elements:
            reason = self._module_of_marks(self.marks_of.get(element, set()))
            if reason and (limit is None or self._text_under().get(element, 0) < limit):
                return reason
        return None

    def _best(self) -> int | None:
        if getattr(self, "_scoring", False):
            return super()._best()
        keep = self.raw
        # only form controls leave the scoring: a module mark may stand on the element around the whole article (a "cuerpo ad"
        # class at cl_cooperativa), so marks decide block by block below, never the container
        self.raw = [item for item in keep if not self._in_form_control(item)]
        self._scoring = True
        try:
            return super()._best()
        finally:
            self.raw, self._scoring = keep, False

    def _ancestors(self, element: int) -> list[int]:
        out, e = [], self.parent_of.get(element)
        while e is not None:
            out.append(e)
            e = self.parent_of.get(e)
        return out

    # -- the selection -------------------------------------------------------------------------------------------------------

    @staticmethod
    def _decide(block: dict[str, Any], decision: str, reason: str) -> None:
        block["selection"] = {"rule": TEMPLATE_RULE if reason == "outlet_template" else SELECTION_RULE, "decision": decision,
                              "reason": reason}
        block["role"] = E.ROLE_NON_BODY if decision == E.SELECTION_EXCLUDED else E.ROLE_BODY

    def stated_article_body(self) -> str:
        texts = self._json_ld_strings("articleBody")
        return A._norm(" ".join(texts)) if texts else ""

    def blocks(self) -> list[dict[str, Any]]:
        if getattr(self, "_blocks4", None) is not None:
            return [dict(block) for block in self._blocks4]
        blocks = [dict(block) for block in super().blocks()]
        chosen = self.containers_chosen()
        container = chosen[0] if chosen else None

        def container_of(item):
            return next((c for c in chosen if c in (item.get("ids") or ())), container)

        # 1-4: exclusions in the BODY the container rule gives. A byline mark counts at the BODY's edges only: between
        # paragraphs an "author" element holds a pull quote or the profile line of a person the article quotes (es_el_mundo)
        modules = {i: self._module(item, container_of(item)) for i, (block, item) in enumerate(zip(blocks, self.raw))
                   if block["role"] == E.ROLE_BODY}
        unmarked = [i for i, reason in modules.items() if reason is None]
        inner = range(min(unmarked), max(unmarked) + 1) if unmarked else range(0)
        seen: set[str] = set()
        for i, (block, item) in enumerate(zip(blocks, self.raw)):
            if block["role"] != E.ROLE_BODY:
                continue
            reason = modules.get(i)
            if reason == "module_byline" and i in inner:
                reason = None
            if self._in_form_control(item):
                self._decide(block, E.SELECTION_EXCLUDED, "form_control")
            elif not _ALNUM.search(block["text"]):
                self._decide(block, E.SELECTION_EXCLUDED, "no_text")
            elif reason is not None:
                self._decide(block, E.SELECTION_EXCLUDED, reason)
            elif (reason := _provenance_note(block)) is not None:
                self._decide(block, E.SELECTION_EXCLUDED, reason)
            else:
                key = A._norm(block["text"])
                if len(block["text"].split()) >= MIN_DUPLICATE_WORDS and key in seen:
                    self._decide(block, E.SELECTION_EXCLUDED, "duplicate_block")
                seen.add(key)
        # inclusions: paragraphs of the container's <article> element, and paragraphs the page states as its articleBody
        article = None
        if container is not None:
            article = next((e for e in [container, *self._ancestors(container)] if self.tag_of.get(e) == "article"), None)
            if article is not None and self._a_list(article):
                article = None                                        # an <article> that holds other articles is a list
        stated = self.stated_article_body()
        descriptions = self.stated_subtitles()
        body_keys = {A._norm(b["text"]) for b in blocks if b["role"] == E.ROLE_BODY}
        first_body = next((i for i, b in enumerate(blocks) if b["role"] == E.ROLE_BODY), None)
        # the lead: the nearest block with text before the first BODY block
        lead = None
        if first_body is not None:
            lead = next((i for i in range(first_body - 1, -1, -1) if _ALNUM.search(blocks[i]["text"])), None)
        for i, (block, item) in enumerate(zip(blocks, self.raw)):
            if block["role"] != E.ROLE_NON_BODY or "selection" in block or "module" in block or block["kind"] != "paragraph" \
                    or len(block["text"].split()) < MIN_INCLUDED_WORDS or item.get("link", 0) > A.MAX_LINK_SHARE * len(block["text"]) \
                    or self._in_form_control(item) or A._norm(block["text"]) in body_keys \
                    or (self.revision >= 1 and self._copy_of(block["text"], body_keys)):
                continue
            ids = list(item.get("ids") or ())
            reason = None
            if i == lead and article is not None and article in ids and len(block["text"].split()) >= MIN_LEAD_WORDS \
                    and not self._states(block["text"], descriptions):
                between = {self.tag_of[e] for e in ids[ids.index(article) + 1:]}
                if not A.NON_BODY_BELOW_CONTAINER & between and self._module(item, article) is None:
                    reason = "lead_paragraph"
            if reason is None and stated and len(A._norm(block["text"])) >= 40 and A._norm(block["text"]) in stated \
                    and self._module(item, None) is None and not A.NON_BODY_BELOW_CONTAINER & {self.tag_of[e] for e in ids}:
                reason = "stated_article_body"
            if reason is not None:
                self._decide(block, E.SELECTION_INCLUDED, reason)
                block["_included"] = True
                body_keys.add(A._norm(block["text"]))
        # 5: outlet templates
        if self.templates:
            body = [i for i, b in enumerate(blocks) if b["role"] == E.ROLE_BODY]
            template = {i for i in body if template_digest(blocks[i]["text"]) in self.templates}
            for n, i in enumerate(body):
                if i not in template:
                    continue
                if blocks[i]["kind"] == "heading":
                    following = next((j for j in body[n + 1:] if j not in template), None)
                    if following is not None and blocks[following]["kind"] != "heading" \
                            and len(blocks[following]["text"].split()) >= MIN_SUBHEADING_FOLLOW_WORDS:
                        continue                                      # a recurring sub-heading over real text
                self._decide(blocks[i], E.SELECTION_EXCLUDED, "outlet_template")
        # 6: label headings that end the BODY (a sentence-length heading there leads into an embed and is kept)
        for i in reversed([i for i, b in enumerate(blocks) if b["role"] == E.ROLE_BODY]):
            if blocks[i]["kind"] != "heading" or len(blocks[i]["text"].split()) > MAX_TRAILING_HEADING_WORDS:
                break
            self._decide(blocks[i], E.SELECTION_EXCLUDED, "trailing_heading")
        # 7: one short label printed again and again in the BODY -- the kicker of every card of a teaser list ("Música" eight
        # times); a label: at most MAX_LABEL_WORDS words, letters only (no digit, no colon -- a rating, a date or a data field
        # "Fase: Primer Hexagonal" repeats in real lists and stays), no sentence end, not a heading
        def label(b):
            return b["role"] == E.ROLE_BODY and b["kind"] != "heading" and len(b["text"].split()) <= MAX_LABEL_WORDS \
                and not _SENTENCE_END.search(b["text"]) and not _NOT_LABEL.search(b["text"])

        labels = Counter(A._norm(b["text"]) for b in blocks if label(b))
        for block in blocks:
            if label(block) and labels[A._norm(block["text"])] >= MIN_LABEL_REPEATS:
                self._decide(block, E.SELECTION_EXCLUDED, "repeated_label")
        for block in blocks:          # included, then excluded by a later rule: the container rule had it outside -- no selection
            if block.get("selection", {}).get("decision") == E.SELECTION_EXCLUDED and block.get("_included"):
                block.pop("selection")
            block.pop("_included", None)
        self._blocks4 = blocks
        return [dict(block) for block in blocks]


def _record(body_sha256: str, body: bytes, content_type: str, declared_charset: str, content_encoding: str,
            version: str = VERSION_4) -> dict[str, Any]:
    return {
        "schema": E.EXTRACTION_SCHEMA_3,
        "extractor": {"name": A.NAME, "version": version},
        "input": {"body_sha256": body_sha256, "body_size_bytes": len(body), "declared_content_type": content_type,
                  "declared_charset": declared_charset, "content_encoding": content_encoding},
        "outcome": E.OUTCOME_EXTRACTED,
        "reason": E.NOT_APPLICABLE,
        "decoding": {"charset": E.NOT_APPLICABLE, "basis": E.NOT_APPLICABLE, "replaced_characters": 0},
        "metadata": {name: {"value": E.UNKNOWN, "basis": E.UNKNOWN, "candidates": []} for name in E.METADATA_FIELDS},
        "blocks": [],
    }


def extract_v4(body: bytes, *, body_sha256: str, content_type: str, declared_charset: str = E.UNKNOWN,
               content_encoding: str = E.IDENTITY, templates: frozenset[str] | None = None) -> E.Extraction:
    """``article_html/0.4.0`` (``extraction/3``). ``templates``: the pinned table unless given (the table itself is built from
    runs with ``frozenset()``)."""
    return _extract(body, body_sha256=body_sha256, content_type=content_type, declared_charset=declared_charset,
                    content_encoding=content_encoding, templates=templates, version=VERSION_4)


def extract_v4_1(body: bytes, *, body_sha256: str, content_type: str, declared_charset: str = E.UNKNOWN,
                 content_encoding: str = E.IDENTITY, templates: frozenset[str] | None = None) -> E.Extraction:
    """``article_html/0.4.1`` (``extraction/3``): 0.4.0 with no copy included and teaser cards not taken for a list (CPD-0042)."""
    return _extract(body, body_sha256=body_sha256, content_type=content_type, declared_charset=declared_charset,
                    content_encoding=content_encoding, templates=templates, version=VERSION_4_1)


def _extract(body: bytes, *, body_sha256: str, content_type: str, declared_charset: str, content_encoding: str,
             templates: frozenset[str] | None, version: str) -> E.Extraction:
    if not isinstance(body, bytes):
        raise E.ExtractionError("a body is bytes")
    if sha256_bytes(body) != require_sha256(body_sha256, "body_sha256"):
        raise E.ExtractionError("the body offered is not the body the digest names")
    if not isinstance(content_type, str) or not content_type:
        raise E.ExtractionError("content_type is the declared media type or 'unknown'")
    record = _record(body_sha256, body, content_type, declared_charset, content_encoding, version)
    try:
        body = E.decode_content(body, content_encoding) if body else body
        reason = E._refusal(body, content_type)
    except E.ContentDecodingError as error:
        reason = error.reason
    if reason is None:
        text, record["decoding"] = E._decode(body, declared_charset)
        parser = _Parser4(templates=body_templates() if templates is None else templates, revision=0 if version == VERSION_4 else 1)
        parser.feed(text)
        parser.close()
        record["blocks"] = parser.blocks()
        record["metadata"] = E._metadata(parser)
    else:
        record["outcome"], record["reason"] = E.OUTCOME_NOT_EXTRACTABLE, reason
    record["extracted_text_sha256"] = sha256_bytes(E.extracted_text_bytes(record["blocks"]))
    record["body_text_sha256"] = sha256_bytes(E.body_text(record["blocks"]).encode("utf-8"))
    return E.Extraction(record)


ARTICLE_4 = E.Extractor(A.NAME, VERSION_4, extract_v4, E.LIFECYCLE_CANDIDATE, record_schema=E.EXTRACTION_SCHEMA_3)
ARTICLE_4_1 = E.Extractor(A.NAME, VERSION_4_1, extract_v4_1, E.LIFECYCLE_CANDIDATE, record_schema=E.EXTRACTION_SCHEMA_3)
PREFERRED = ARTICLE_4_1    # the candidate the operator is asked to adopt (CPD-0042; 0.4.0 was CPD-0041's); not binding


def body_before_selection(record: Any) -> str:
    """The BODY the container rule alone gives, read back from an ``extraction/3`` record (the selection undone)."""
    def original(block):
        selection = block.get("selection")
        if selection is None:
            return block["role"]
        return E.ROLE_BODY if selection["decision"] == E.SELECTION_EXCLUDED else E.ROLE_NON_BODY
    return "\n\n".join(block["text"] for block in record["blocks"] if original(block) == E.ROLE_BODY)


__all__ = ["ARTICLE_4", "ARTICLE_4_1", "PREFERRED", "extract_v4", "extract_v4_1", "body_before_selection", "template_digest",
           "body_templates", "body_templates_sha256", "MODULE_MARKS", "VERSION_4", "VERSION_4_1", "SELECTION_RULE", "TEMPLATE_RULE",
           "TEMPLATES_PATH"]
