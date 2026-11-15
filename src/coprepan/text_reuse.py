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


@dataclass
class ReuseIndex:
    """The documents compared so far. ``add`` compares one new document with the indexed ones and returns its relations."""

    documents: dict[str, _Document] = field(default_factory=dict)
    postings: dict[int, list[str]] = field(default_factory=lambda: defaultdict(list))

    def add(self, document_id: str, *, outlet_id: str, body_text: str, published: str | None = None,
            fetched_at: str = "") -> list[dict[str, Any]]:
        if document_id in self.documents:
            raise ValueError(f"{document_id} is already indexed")
        tokens = words(body_text)
        if len(tokens) < MIN_WORDS:
            return []
        grams = shingles(tokens)
        new = _Document(document_id, outlet_id, (published or "9999", fetched_at, document_id), grams, tuple(sorted(grams)[:SKETCH]))
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


def relations(documents: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """All relations of a set of documents (``document_id``, ``outlet_id``, ``body_text``, ``published``, ``fetched_at``),
    in a fixed order: the index sees them by (publication date, fetch time, id)."""
    index, out = ReuseIndex(), []
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


__all__ = ["ReuseIndex", "relations", "clusters", "words", "shingles", "VERSION", "SYNDICATED", "DUPLICATE"]
