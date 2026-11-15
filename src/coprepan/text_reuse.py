"""Document relations from a text comparison (``text-reuse/1``, CPD-0039): the same, or nearly the same, BODY text in two
documents.

This is evidence of a *different kind* from an agency credit (``coprepan.provenance``): it says that two documents carry the
same text, not who wrote it. Two outlets with the same text point to one text version or to syndication; they do not prove an
agency, and an agency credit does not prove that anyone else printed the text. Neither ever excludes a document: whether a study
counts a syndicated text once or every time it was published is the study's selection.

Method -- deterministic, cheap, incremental:

* the BODY is folded (NFC, lower case) into words; a document of fewer than ``MIN_WORDS`` words is not compared;
* its word ``SHINGLE``-grams are hashed (BLAKE2b, 8 bytes); a bottom-``SKETCH`` sketch (the smallest hashes) is its index key;
* a new document is compared only with the documents that share at least ``MIN_SHARED_SKETCH`` sketch values with it (an
  inverted index, so the work per new document does not grow with the whole corpus);
* ``containment(a in b)`` = the share of ``a``'s shingles that ``b`` has; a pair is a relation when the containment of the
  shorter in the longer is at least ``MIN_CONTAINMENT``. ``identical`` when both containments reach it, ``contained`` when only
  the shorter text is (nearly) all inside the longer one.

Relations (the analysis contract's vocabulary): ``syndicated_copy_of`` between documents of different outlets,
``duplicate_of`` within one outlet. The target is the earlier document (publication date as published, then fetch time, then
id) -- an order of appearance in this corpus, not a finding about which outlet the text came from; the basis says so.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Mapping

VERSION = "text-reuse/1"
SHINGLE, SKETCH, MIN_SHARED_SKETCH = 8, 32, 4
MIN_WORDS, MIN_CONTAINMENT = 50, 0.9
SYNDICATED, DUPLICATE = "syndicated_copy_of", "duplicate_of"
_WORD = re.compile(r"\w+", re.UNICODE)

# --- text-reuse/2 (CPD-0040): the kind of textual match, as its own versioned attribute ------------------------------------
#
# /1 calls a pair ``identical`` when both shingle containments reach 0.9 -- a pair can be "identical" with a tenth of its
# shingles different. /2 keeps /1's candidates, threshold and relation kinds (the joint contract's ``duplicate_of`` /
# ``syndicated_copy_of``, unchanged) and classifies the match in ``text_match``:
#
# * ``exact`` -- the canonical BODY text of both is the same string. Canonical = the BODY as extracted with only technical
#   normalisations: Unicode NFC; the invisible format characters of ``_INVISIBLE`` (soft hyphen, zero-width characters, BOM)
#   removed; every run of white space -- spaces, no-break spaces, line and paragraph breaks -- folded to one space; trimmed.
#   Case, punctuation, quotation marks, digits, diacritics and wording are *not* normalised: a pair that differs in any of them
#   is not exact. (Paragraph breaks are folded: two outlets set the same wire text in different paragraphs.)
# * ``near_identical`` -- not exact, and each text has at least ``MIN_CONTAINMENT`` of its 8-word shingles in the other: the
#   same text with a changed opening or close, a sentence added or cut, a word changed.
# * ``contained`` -- only the shorter text is (almost) all inside the longer one: a short version, or a text embedded in a
#   longer article.
#
# The measured values travel with the relation (both containments, the shingle and word counts, the shared shingles), and the
# words of each text that the other lacks are counted (``differing_words``: a bag-of-words difference, not an alignment).
# Exactness is decided by the canonical digest, never by containment. The direction of a relation is the order of appearance in
# this corpus (publication date as published, fetch time, id), never a finding about which outlet published first or where the
# text came from; a text match is not evidence of agency authorship, and nothing here removes a document from CORE.

VERSION_2 = "text-reuse/2"
VERSIONS = (VERSION, VERSION_2)
TEXT_MATCHES = ("exact", "near_identical", "contained")
_INVISIBLE = dict.fromkeys(map(ord, "­​‌‍⁠﻿"))
_SPACE = re.compile(r"\s+", re.UNICODE)


def canonical_text(text: str) -> str:
    """The BODY with the technical normalisations of ``text-reuse/2`` only (see the module notes)."""
    return _SPACE.sub(" ", unicodedata.normalize("NFC", text).translate(_INVISIBLE)).strip()


def canonical_sha256(text: str) -> str:
    return hashlib.sha256(canonical_text(text).encode("utf-8")).hexdigest()


def words(text: str) -> list[str]:
    return _WORD.findall(unicodedata.normalize("NFC", text).lower())


def shingles(tokens: list[str]) -> set[int]:
    return {int.from_bytes(hashlib.blake2b(" ".join(tokens[i:i + SHINGLE]).encode("utf-8"), digest_size=8).digest(), "big")
            for i in range(max(0, len(tokens) - SHINGLE + 1))}


@dataclass
class _Document:
    document_id: str
    outlet_id: str
    order: tuple[str, str, str]
    shingles: set[int]
    sketch: tuple[int, ...]
    canonical_sha256: str = ""
    word_counts: Counter = field(default_factory=Counter)


@dataclass
class ReuseIndex:
    """The documents compared so far. ``add`` compares one new document with the indexed ones and returns its relations.
    ``version``: ``text-reuse/1`` (the default, unchanged) or ``text-reuse/2`` (with ``text_match``)."""

    documents: dict[str, _Document] = field(default_factory=dict)
    postings: dict[int, list[str]] = field(default_factory=lambda: defaultdict(list))
    version: str = VERSION

    def __post_init__(self) -> None:
        if self.version not in VERSIONS:
            raise ValueError(f"not a text-reuse version: {self.version!r}")

    def add(self, document_id: str, *, outlet_id: str, body_text: str, published: str | None = None,
            fetched_at: str = "") -> list[dict[str, Any]]:
        if document_id in self.documents:
            raise ValueError(f"{document_id} is already indexed")
        tokens = words(body_text)
        if len(tokens) < MIN_WORDS:
            return []
        grams = shingles(tokens)
        new = _Document(document_id, outlet_id, (published or "9999", fetched_at, document_id), grams, tuple(sorted(grams)[:SKETCH]))
        if self.version == VERSION_2:
            new.canonical_sha256, new.word_counts = canonical_sha256(body_text), Counter(tokens)
        shared = Counter(other for value in new.sketch for other in self.postings.get(value, ()))
        relations = []
        for other_id, count in sorted(shared.items()):
            if count < MIN_SHARED_SKETCH:
                continue
            other = self.documents[other_id]
            common = len(new.shingles & other.shingles)
            a_in_b, b_in_a = common / len(new.shingles), common / len(other.shingles)
            if min(len(new.shingles), len(other.shingles)) and max(a_in_b, b_in_a) >= MIN_CONTAINMENT \
                    and (a_in_b if len(new.shingles) <= len(other.shingles) else b_in_a) >= MIN_CONTAINMENT:
                later, earlier = (new, other) if new.order > other.order else (other, new)
                kind = SYNDICATED if new.outlet_id != other.outlet_id else DUPLICATE
                if self.version == VERSION_2:
                    relations.append(self._relation_2(kind, later, earlier, common))
                    continue
                match = "identical" if min(a_in_b, b_in_a) >= MIN_CONTAINMENT else "contained"
                relations.append({
                    "relation": kind, "document_id": later.document_id, "target_document_id": earlier.document_id,
                    "basis": f"{VERSION}: {SHINGLE}-word shingle containment {min(a_in_b, b_in_a):.3f}/{max(a_in_b, b_in_a):.3f} of the BODY "
                             f"({match}); target = earlier by publication date, fetch time, id -- not a finding of origin",
                    "match": match, "containment": [round(a_in_b, 4), round(b_in_a, 4)],
                    "outlets": sorted({new.outlet_id, other.outlet_id})})
        self.documents[document_id] = new
        for value in new.sketch:
            self.postings[value].append(document_id)
        return relations

    @staticmethod
    def _relation_2(kind: str, later: _Document, earlier: _Document, common: int) -> dict[str, Any]:
        """A ``text-reuse/2`` relation: /1's relation with the kind of match and its measured values."""
        later_in_earlier, earlier_in_later = common / len(later.shingles), common / len(earlier.shingles)
        if later.canonical_sha256 == earlier.canonical_sha256:
            match = "exact"
        elif min(later_in_earlier, earlier_in_later) >= MIN_CONTAINMENT:
            match = "near_identical"
        else:
            match = "contained"
        words_later, words_earlier = sum(later.word_counts.values()), sum(earlier.word_counts.values())
        return {
            "relation": kind, "rule": VERSION_2, "document_id": later.document_id, "target_document_id": earlier.document_id,
            "text_match": match,
            "basis": f"{VERSION_2}: {match} -- canonical BODY text {'equal' if match == 'exact' else 'not equal'} (NFC, invisible "
                     f"characters removed, white space folded); 8-word shingle containment {later_in_earlier:.3f} of this document in "
                     f"the target, {earlier_in_later:.3f} of the target in this document; target = earlier in this corpus by "
                     f"publication date, fetch time, id -- an order of appearance, not a finding of origin or authorship",
            "containment": [round(later_in_earlier, 4), round(earlier_in_later, 4)],
            "shingles": [len(later.shingles), len(earlier.shingles)], "shared_shingles": common,
            "words": [words_later, words_earlier],
            "differing_words": [sum((later.word_counts - earlier.word_counts).values()),
                                sum((earlier.word_counts - later.word_counts).values())],
            "outlets": sorted({later.outlet_id, earlier.outlet_id}), "outlet_of": [later.outlet_id, earlier.outlet_id]}


def relations(documents: list[Mapping[str, Any]], *, version: str = VERSION) -> list[dict[str, Any]]:
    """All relations of a set of documents (``document_id``, ``outlet_id``, ``body_text``, ``published``, ``fetched_at``),
    in a fixed order: the index sees them by (publication date, fetch time, id)."""
    index, out = ReuseIndex(version=version), []
    for document in sorted(documents, key=lambda d: (d.get("published") or "9999", d.get("fetched_at") or "", d["document_id"])):
        out += index.add(document["document_id"], outlet_id=document["outlet_id"], body_text=document["body_text"],
                         published=document.get("published"), fetched_at=document.get("fetched_at") or "")
    return out


def clusters(found: list[Mapping[str, Any]]) -> dict[str, str]:
    """Each related document's cluster, named by the smallest document id it is (transitively) related to -- a label, not an
    origin."""
    parent: dict[str, str] = {}

    def root(x: str) -> str:
        while parent.get(x, x) != x:
            x = parent[x]
        return x

    for relation in found:
        a, b = root(relation["document_id"]), root(relation["target_document_id"])
        if a != b:
            parent[max(a, b)] = min(a, b)
            parent.setdefault(min(a, b), min(a, b))
    return {x: root(x) for x in parent}


__all__ = ["ReuseIndex", "relations", "clusters", "words", "shingles", "canonical_text", "canonical_sha256", "VERSION", "VERSION_2",
           "VERSIONS", "TEXT_MATCHES", "SYNDICATED", "DUPLICATE"]
