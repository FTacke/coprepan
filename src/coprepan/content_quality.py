"""Content quality of an extracted press text (CPD-0038): deterministic features, and the candidate gate that decides from them.

Three states are kept apart and none implies another:

* **raw archiving** -- whether the received bytes are preserved (the ledger, ``RAW_PRESERVED``);
* **technical usability** -- whether an extracted text exists (``admission-technical/1``, ``coprepan.admission``);
* **content quality** -- whether the extracted body is a coherent editorial text fit for linguistic analysis (this module).

A rejection here deletes nothing and labels nothing as bad evidence: it says that this extraction of this page is not taken
into the analysis corpus under this rule set. Whether a rule set is binding for corpus admission or a release is the
operator's decision (CPD-0038 §5); until then the gate is ``CANDIDATE`` and changes no existing admission or release gate.

Precision before recall: a doubtful page is rejected. The features are simple text measures; none of them is a linguistic
category. Every decision carries machine-readable reasons and the measured values it rests on, and the rule set is versioned:
a changed threshold is a new rule set whose decisions are written beside the old ones.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping

from . import extraction as E
from .canonical import sha256_bytes

FEATURES_VERSION = "content-features/1"

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_SENTENCE_END = re.compile(r"[.!?…:;»\"”’)\]]\s*$")
# The commonest Spanish function words (closed classes: articles, prepositions, conjunctions, pronouns, auxiliaries). Their
# share separates running prose from lists of names, menus and teaser headlines; it is not a language identifier.
FUNCTION_WORDS = frozenset("""
de la que el en y a los se del las un por con no una su para es al lo como más o pero sus le ha me si sin sobre este ya entre
cuando todo esta ser son dos también fue había era muy hasta desde está mi porque qué sólo solo han yo hay vez puede todos así
nos ni parte tiene él uno donde bien mismo ese ahora cada e otro después te otros aunque esa eso hace otra tan durante siempre
tanto ella sí sido según menos les fueron estos estas cual quien ante tras hacia contra mientras pues u ya que sea será
""".split())
# Text of a page frame that is not the article: consent, subscription and login walls, sharing and reading prompts.
BOILERPLATE = re.compile(
    r"\b(cookies?|suscr[ií]bete|suscribirse|suscripci[oó]n|suscriptor(?:es|a)?|inicia(?:r)? sesi[oó]n|reg[ií]strate|newsletter|"
    r"todos los derechos reservados|derechos reservados|habilita(?:r)? (?:el )?javascript|javascript|"
    r"lee tambi[eé]n|te puede interesar|tambi[eé]n te puede|m[aá]s noticias|noticias relacionadas|comparte? (?:en|esta)|"
    r"s[ií]guenos|whatsapp|telegram|haz clic|clic aqu[ií]|ver m[aá]s|leer m[aá]s|contenido exclusivo|ya eres suscriptor|"
    r"pol[ií]tica de privacidad|t[eé]rminos y condiciones|publicidad)\b", re.IGNORECASE)
PAYWALL = re.compile(r"\b(contenido exclusivo para suscriptores|ya eres suscriptor|para seguir leyendo|"
                     r"suscr[ií]bete para (?:leer|continuar|seguir)|inicia sesi[oó]n para (?:leer|continuar|seguir)|"
                     r"este contenido es exclusivo|art[ií]culo exclusivo para)\b", re.IGNORECASE)
# A page frame that speaks to the reader instead of an article: ad-blocker, JavaScript, browser and consent walls.
FRAME = re.compile(r"\b(bloqueador(?:es)? de anuncios|adblock\w*|desactiva(?:r)? (?:tu|el) bloqueador|"
                   r"habilita(?:r)? (?:el )?javascript|activa(?:r)? (?:el )?javascript|tu navegador no|actualiza(?:r)? (?:tu|el) navegador|"
                   r"acepta(?:r)? (?:las )?cookies|uso de cookies|verifica(?:r)? que eres (?:un )?humano|no eres un robot)\b", re.IGNORECASE)


# Text that a machine wrote about the article and the page shows beside it (a generated summary): not the newspaper's text.
# /2: also a summary or text "generated / written / produced with a tool of" AI, and the disclosure of an editorial team working
# with AI tools (both seen in the control of /1). A text *about* AI is not matched: the pattern needs the disclosure's form.
MACHINE = re.compile(r"(\b(?:resumen|texto|contenido|nota|art[ií]culo)\s+(?:fue\s+|ha sido\s+)?(?:generad|elaborad|cread|redactad|"
                     r"producid|asistid)[oa]s?\s+(?:con|por|mediante|a partir de|en colaboraci[oó]n con)\b[^.]{0,60}"
                     r"(?:inteligencia artificial|\bIA\b)|equipo editorial y (?:las |nuestras )?herramientas de inteligencia artificial|"
                     r"\bgenerado (?:con|por) inteligencia artificial\b)", re.IGNORECASE)
# /2: pages about the publication, not of it -- institutional sections, FAQs, terms, privacy, subscription and contact pages.
NOT_EDITORIAL_URL = re.compile(r"/(institucional(?:es)?|preguntas-frecuentes|faq|terminos(?:-y-condiciones)?|condiciones-de-uso[\w-]*|"
                               r"politica-?de-?privacidad|privacidad|quienes-somos|acerca-de[\w-]*|contacto|contactenos|aviso-legal|"
                               r"suscripci[oó]n(?:es)?(?:-[\w]+)?|suscribete|mapa-?del-?sitio)(?:/|$|\.)", re.IGNORECASE)
# Paid content presented as an article: a block that *begins* with the sponsor's mark ("Presentado por Naturgy") -- in running
# text "presentado por" is ordinary news language (a bill presented by a deputy) -- or an address in an advertising section.
SPONSORED = re.compile(r"^\s*(presentado por|patrocinado por|contenido patrocinado|publirreportaje|contenido de marca|"
                       r"espacio publicitario|nota pagada|en alianza con|branded content)\b", re.IGNORECASE)
SPONSORED_URL = re.compile(r"(/(?:[a-z]+-)?(comercial|patrocinado|patrocinados|publirreportajes?|branded|marcas)(/|-)|"
                           r"contenido-patrocinado|contenido-de-marca|publirreportaje|branded-content|informacion-comercial)", re.IGNORECASE)
# A live page: timestamped entries, or an address that says so. Its text is a series of updates or a preview without them.
_TIMESTAMP_LED = re.compile(r"^\s*(?:\d{1,2}[:.h]\d{2}(?:\s*(?:hs?|horas|a\.?\s?m\.?|p\.?\s?m\.?))?|minuto \d+|\d{1,3}['’]\s)", re.IGNORECASE)
# Only an address that *is* a live page: a slug that begins with the live mark, or a live section. A slug that merely contains
# "en-vivo" is as often an article about a live broadcast ("la ejecución en vivo", "un show en vivo").
_PLAYER_ZERO = re.compile(r"^\s*0?0:00(?::00)?\s*$")
LIVE_URL = re.compile(r"(/minuto-a-minuto[/-]|/(?:en-?vivo|vivo|en-directo|directo)(?:[/-]|$)|/live/)", re.IGNORECASE)
# /2: a title that announces a live page ("EN VIVO | ...", "..., minuto a minuto").
LIVE_TITLE = re.compile(r"(^\s*(?:en vivo|en directo|directo)\b|\bminuto a minuto\b)", re.IGNORECASE)
_INVISIBLE = dict.fromkeys(map(ord, "­​‌‍⁠﻿"))   # soft hyphen, zero-width characters
_LD = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", text.translate(_INVISIBLE))).strip().lower()


def stated_body_characters(html: str) -> int:
    """The length of the longest schema.org ``articleBody`` the page states in its JSON-LD (0 when none): what the publisher
    says the article is. A comparison value, not a ground truth (it can be a summary, a teaser or missing)."""
    import json

    found: list[int] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("articleBody"), str):
                found.append(len(re.sub(r"\s+", " ", node["articleBody"]).strip()))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for block in _LD.findall(html):
        try:
            walk(json.loads(block.strip()))
        except ValueError:
            continue
    return max(found, default=0)


def features(record: Mapping[str, Any], *, http_status: int | None = None, html: str | None = None) -> dict[str, Any]:
    """The features of one extraction record's body. Pure: the record (and, for ``stated_body_characters``, the decoded page)
    in, numbers out."""
    blocks = [b for b in record["blocks"] if b["role"] == E.ROLE_BODY]
    texts = [b["text"].translate(_INVISIBLE) for b in blocks]
    body = "\n\n".join(texts)
    words = _WORD.findall(body.lower())
    n = len(words)
    norm_blocks = [_norm(t) for t in texts]
    counts: dict[str, int] = {}
    for t in norm_blocks:
        counts[t] = counts.get(t, 0) + 1
    repeated_chars = sum(len(t) for t in norm_blocks if counts[t] > 1 and len(t) >= 20)
    grams = [tuple(words[i:i + 5]) for i in range(max(0, n - 4))]
    paragraph_words = [len(_WORD.findall(t)) for t in texts]
    prose = [t for t, w in zip(texts, paragraph_words) if w >= 5]
    letters = sum(1 for c in body if c.isalpha())
    visible = sum(1 for c in body if not c.isspace())
    title = next((b["text"] for b in record["blocks"] if b["role"] == E.ROLE_TITLE), None)
    meta_title = (record.get("metadata") or {}).get("title", {}).get("value")
    return {
        "version": FEATURES_VERSION,
        "http_status": http_status,
        "body_blocks": len(blocks),
        "words": n,
        "distinct_words": len(set(words)),
        "paragraphs_25w": sum(1 for w in paragraph_words if w >= 25),
        "longest_paragraph_words": max(paragraph_words, default=0),
        "mean_paragraph_words": round(n / len(blocks), 1) if blocks else 0.0,
        "list_item_share": round(sum(1 for b in blocks if b["kind"] == "list_item") / len(blocks), 3) if blocks else 0.0,
        "repeated_block_share": round(repeated_chars / max(1, sum(len(t) for t in norm_blocks)), 3),
        "distinct_5gram_ratio": round(len(set(grams)) / len(grams), 3) if grams else 1.0,
        "sentence_end_share": round(sum(1 for t in prose if _SENTENCE_END.search(t)) / len(prose), 3) if prose else 0.0,
        "function_word_share": round(sum(1 for w in words if w in FUNCTION_WORDS) / n, 3) if n else 0.0,
        "letter_share": round(letters / visible, 3) if visible else 0.0,
        "boilerplate_hits": len(BOILERPLATE.findall(body)),
        "paywall_hits": len(PAYWALL.findall(body)),
        "frame_hits": len(FRAME.findall(body)),
        "machine_text_hits": len(MACHINE.findall(body)),
        "sponsored_hits": sum(1 for t in texts if SPONSORED.match(t)),
        # a ticker's update begins with the time it was posted (in the block, or as a block of its own before it); "0:00" is the
        # label of an audio or video player, not a time
        "timestamp_led_share": round(sum(1 for t in texts if _TIMESTAMP_LED.match(t) and not _PLAYER_ZERO.match(t)) / len(texts), 3)
                               if texts else 0.0,
        "body_characters": len(body),
        "stated_body_characters": stated_body_characters(html) if html is not None else None,
        "title": bool(title) or (meta_title not in (None, E.UNKNOWN)),
        "title_text": (title or (meta_title if meta_title not in (None, E.UNKNOWN) else "") or "")[:200],
        "replaced_characters": (record.get("decoding") or {}).get("replaced_characters", 0),
        "body_text_sha256": sha256_bytes(_norm(body).encode("utf-8")),
    }


# --- the gate ---------------------------------------------------------------------------------------------------------

# /1 (commit b7d5f86): chosen on the calibration and hard-negative samples of one half of the stored pages; its blind control
# on the other half: 94 of 100 accepted pages good. /2 closes the five classes of that control's false accepts that have a
# general form (machine-text disclosures, institutional pages, live pages by slug or title, sponsor marks anywhere in the
# address); it is measured on a second control drawn after it was written.
RULESET = "content-quality/2"
LIFECYCLE = E.LIFECYCLE_CANDIDATE          # not binding for admission or release until the operator decides (CPD-0038 §5)
ACCEPT, REJECT = "ACCEPT", "REJECT"
THRESHOLDS = {
    "min_words": 150,                      # below: a brief, a fragment or a frame; above, the calibration found no frame text
    "min_function_word_share": 0.30,       # running Spanish prose is 0.37-0.50 (5th-95th pct.); lists, names, other languages lower
    "max_stated_body_shortfall": 0.5,      # extracted body under half of what the page itself states: incomplete
    "min_stated_body_characters": 1000,    # ... only where the page states a body of at least this length
    "min_distinct_5gram_ratio": 0.8,       # a text that repeats itself
    "max_repeated_block_share": 0.3,
    "template_urls": 3,                    # one body under this many URLs of one outlet is the page's template, not an article
    "max_timestamp_led_share": 0.2,        # more body blocks than this led by a time stamp: a live ticker
}
# The closed vocabulary of reasons. Every one is a rejection; the first is the one a summary names.
REASONS = {
    "http_not_2xx": "the answer was not a 2xx",
    "not_extracted": "the extraction record says the page was not extractable",
    "no_body": "no body text",
    "too_short": "fewer words than the minimum",
    "not_running_prose": "function-word share below the minimum: a list, names, a menu, or not Spanish",
    "page_frame": "the body speaks to the reader about the page (ad blocker, JavaScript, consent, browser)",
    "paywall_text": "the body is a subscription or login wall",
    "machine_text": "the body carries a machine-generated summary, or the page declares its text made with AI (whether such texts "
                    "belong in the corpus is the operator's decision; until then they are not admitted)",
    "sponsored": "paid content presented as an article",
    "live_coverage": "a live page (time-stamped updates, or an address or title that says live): updates or a preview, not an article",
    "not_editorial_page": "a page about the publication (institutional, FAQ, terms, privacy, subscription, contact)",
    "incomplete_against_stated_body": "the extracted body is less than half of the article body the page states",
    "repetitive": "the text repeats itself",
    "template_body": "the same body under several URLs of one outlet: a page template",
    "duplicate_of_earlier": "the same body as an earlier page of the same outlet",
}


def assess(f: Mapping[str, Any], *, extracted: bool = True, url: str | None = None,
           thresholds: Mapping[str, Any] = THRESHOLDS) -> dict[str, Any]:
    """The decision for one page from its features and its address (the cross-document rules are :func:`assess_corpus`'s)."""
    t = thresholds
    reasons = []
    status = f.get("http_status")
    if status is not None and not 200 <= int(status) < 300:
        reasons.append("http_not_2xx")
    if not extracted:
        reasons.append("not_extracted")
    if not f.get("words"):
        reasons.append("no_body")
    else:
        if f["words"] < t["min_words"]:
            reasons.append("too_short")
        if f["function_word_share"] < t["min_function_word_share"]:
            reasons.append("not_running_prose")
    if f.get("frame_hits"):
        reasons.append("page_frame")
    if f.get("paywall_hits"):
        reasons.append("paywall_text")
    if f.get("machine_text_hits"):
        reasons.append("machine_text")
    if f.get("sponsored_hits") or (url is not None and SPONSORED_URL.search(url)):
        reasons.append("sponsored")
    if (f.get("timestamp_led_share", 0) > t["max_timestamp_led_share"] or (url is not None and LIVE_URL.search(url))
            or LIVE_TITLE.search(f.get("title_text") or "")):
        reasons.append("live_coverage")
    if url is not None and NOT_EDITORIAL_URL.search(url):
        reasons.append("not_editorial_page")
    stated = f.get("stated_body_characters") or 0
    if stated >= t["min_stated_body_characters"] and f.get("body_characters", 0) < t["max_stated_body_shortfall"] * stated:
        reasons.append("incomplete_against_stated_body")
    if f.get("words") and (f["distinct_5gram_ratio"] < t["min_distinct_5gram_ratio"] or f["repeated_block_share"] > t["max_repeated_block_share"]):
        reasons.append("repetitive")
    return {"ruleset": RULESET, "decision": REJECT if reasons else ACCEPT, "reasons": reasons,
            "evidence": {k: f.get(k) for k in ("words", "function_word_share", "body_characters", "stated_body_characters",
                                                "distinct_5gram_ratio", "repeated_block_share", "frame_hits", "paywall_hits",
                                                "machine_text_hits")}}


def assess_corpus(pages: list[Mapping[str, Any]], *, thresholds: Mapping[str, Any] = THRESHOLDS) -> dict[str, dict[str, Any]]:
    """Decisions for a set of pages, each ``{"fetch_id", "outlet_id", "url", "fetched_at", "features", "extracted"}``.

    Adds the two rules a single page cannot know: a body that stands under ``template_urls`` or more distinct URLs of one
    outlet is a template (all are rejected); otherwise a body that an earlier page of the same outlet already has is a
    duplicate (the earliest is assessed on its own merits, the later ones are rejected). A body shared by *different* outlets
    (agency copy) is not rejected here: whether syndicated text counts once is a corpus decision, not a quality one.
    """
    by_body: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for page in pages:
        if page["features"] and page["features"].get("words"):
            by_body.setdefault((page["outlet_id"], page["features"]["body_text_sha256"]), []).append(page)
    out = {}
    for page in pages:
        f = page["features"] or {"words": 0}
        decision = assess(f, extracted=page.get("extracted", True), url=page.get("url"), thresholds=thresholds)
        group = by_body.get((page["outlet_id"], f.get("body_text_sha256")), [])
        if len({p["url"] for p in group}) >= thresholds["template_urls"]:
            decision["reasons"].append("template_body")
        elif len(group) > 1 and min(group, key=lambda p: (p["fetched_at"], p["fetch_id"]))["fetch_id"] != page["fetch_id"]:
            decision["reasons"].append("duplicate_of_earlier")
        decision["decision"] = REJECT if decision["reasons"] else ACCEPT
        out[page["fetch_id"]] = decision
    return out


__all__ = ["features", "assess", "assess_corpus", "stated_body_characters", "FEATURES_VERSION", "FUNCTION_WORDS", "RULESET",
           "THRESHOLDS", "REASONS", "ACCEPT", "REJECT", "LIFECYCLE"]
