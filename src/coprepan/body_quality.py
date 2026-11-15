"""BODY contamination status (``body-quality/1``, CPD-0041): how clean the extracted running text is -- a statement *about the
extraction*, apart from the CORE decision (``content_quality``), which it does not change.

States (closed vocabulary, first match wins):

* ``not_article`` -- there is no running text to speak of: no BODY, or the BODY is not running prose (function-word share
  under the gate's minimum), or the selection removed nearly all of what the container rule had (the "article" was page
  furniture: an author list, a submission note);
* ``incomplete`` -- the page states a much longer article body than was extracted (the gate's shortfall rule, read as a
  status), a stub or a paywall;
* ``residual_suspect`` -- usable text with signals of foreign material the selection did not remove (it never removes text
  inside a block): a technical address or file path in a BODY block, a block that opens as a photo credit, several short
  label-like blocks among the paragraphs, a long block the outlet prints in a few unrelated articles (the template table's
  ``recurring_kept``: too few to remove safely);
* ``cleaned`` -- usable text, and the selection changed the BODY (blocks excluded or included), with no residual signal;
* ``clean`` -- usable text the container rule already gave without foreign material the rules can see.

Every state names its evidence (``signals``, the selection's reasons and counts, words before and after). The signals are
indicators, never deletions; a short genuine block (an interview question) is not a signal by itself.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Mapping

from . import content_quality as Q
from . import extraction as E

VERSION = "body-quality/1"
STATES = ("clean", "cleaned", "residual_suspect", "incomplete", "not_article")
MAX_REMOVED_SHARE = 0.9              # the selection removed at least this share of the container rule's words: furniture, not an article
MIN_BEFORE_WORDS = 50
LABEL_WORDS = 3                      # a block of at most this many words without a sentence end, not a heading: label-like
MIN_LABEL_BLOCKS = 3
_ADDRESS = re.compile(r"(?:https?://|\bwww\.)\S+|\b[\w\-/]+\.(?:jpe?g|png|webp|gif|svg|html?|php|aspx?)\b", re.I)
_CREDIT_OPENING = re.compile(r"^\s*\(?\s*(?:foto|fotos|fotograf[ií]a|imagen|im[aá]genes|cr[eé]dito|video)\s*:", re.I)
_SENTENCE_END = re.compile(r"[.!?…:;»”\")]\s*$")


def _before_words(record: Mapping[str, Any]) -> int:
    words = 0
    for block in record["blocks"]:
        selection = block.get("selection")
        before = block["role"] == E.ROLE_BODY if selection is None else selection["decision"] == E.SELECTION_EXCLUDED
        if before:
            words += len(block["text"].split())
    return words


def recurring_digests() -> frozenset[str]:
    """The long blocks the pinned template table lists as recurring but not removed (``recurring_kept``)."""
    import json

    from . import extraction_body as B   # noqa: PLC0415

    if not hasattr(recurring_digests, "_cache"):
        data = json.loads((B._REPOSITORY / B.TEMPLATES_PATH).read_text(encoding="utf-8"))
        recurring_digests._cache = frozenset(data.get("recurring_kept", ()))
    return recurring_digests._cache


def assess(record: Mapping[str, Any], *, html: str | None = None, recurring: frozenset[str] | None = None) -> dict[str, Any]:
    """``body-quality/1`` for one extraction record (any schema; the selection is read under ``extraction/3``). ``recurring``:
    the recurring-but-kept digests (the pinned table's unless given)."""
    from . import extraction_body as B   # noqa: PLC0415

    recurring = recurring_digests() if recurring is None else recurring
    blocks = record["blocks"]
    body = [b for b in blocks if b["role"] == E.ROLE_BODY]
    words = sum(len(b["text"].split()) for b in body)
    before = _before_words(record)
    selection = Counter(f"{b['selection']['decision']}:{b['selection']['reason']}" for b in blocks if b.get("selection"))
    signals = []
    for b in body:
        if _ADDRESS.search(b["text"]):
            signals.append({"signal": "address_or_path", "block_index": b["index"]})
        if _CREDIT_OPENING.match(b["text"]):
            signals.append({"signal": "credit_opening", "block_index": b["index"]})
        if recurring and B.template_digest(b["text"]) in recurring:
            signals.append({"signal": "recurring_text", "block_index": b["index"]})
    labels = [b["index"] for b in body if b["kind"] != "heading" and len(b["text"].split()) <= LABEL_WORDS
              and not _SENTENCE_END.search(b["text"])]
    if len(labels) >= MIN_LABEL_BLOCKS:
        signals.append({"signal": "label_blocks", "block_indexes": labels[:20], "count": len(labels)})
    features = Q.features(record, html=html)
    evidence = {"words": words, "words_before_selection": before, "selection": dict(selection), "signals": signals,
                "function_word_share": features["function_word_share"], "stated_body_characters": features["stated_body_characters"],
                "body_characters": features["body_characters"]}
    t = Q.THRESHOLDS
    if not words or features["function_word_share"] < t["min_function_word_share"] or (
            before >= MIN_BEFORE_WORDS and words <= (1 - MAX_REMOVED_SHARE) * before):
        state = "not_article"
    elif (features["stated_body_characters"] or 0) >= t["min_stated_body_characters"] and \
            features["body_characters"] < t["max_stated_body_shortfall"] * features["stated_body_characters"]:
        state = "incomplete"
    elif signals:
        state = "residual_suspect"
    elif selection:
        state = "cleaned"
    else:
        state = "clean"
    return {"rule": VERSION, "state": state, "evidence": evidence}


__all__ = ["assess", "VERSION", "STATES"]
