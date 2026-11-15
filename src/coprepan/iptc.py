"""The pinned IPTC NewsCodes extracts (CPD-0039): Media Topics and Genre, read only through a digest check.

An extract (``config/taxonomy/iptc-<vocabulary>_<release date>.json``, built by ``scripts/build_iptc_extract.py``) names the
SHA-256 of the exact bytes retrieved from the IPTC CV server and carries IPTC's attribution. A mapping names the extract it was
written against by path and file digest; a vocabulary update is a new extract beside the old one, so a stored mapping result
never changes under a taxonomy update -- a new mapping version has to adopt the new extract explicitly.

IPTC NewsCodes are (c) IPTC, International Press Telecommunications Council, licensed CC BY 4.0; the attribution travels in
every extract and is repeated in any release that carries a code (``ATTRIBUTION``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .canonical import sha256_file

EXTRACT_SCHEMA = "coprepan-iptc-extract/v1"
_REPOSITORY = Path(__file__).resolve().parents[2]
MEDIATOPIC = "config/taxonomy/iptc-mediatopic_2026-09-30.json"
GENRE = "config/taxonomy/iptc-genre_2024-02-13.json"


class TaxonomyError(ValueError):
    """An extract that is not the pinned one, or a code that it does not hold."""


@dataclass(frozen=True)
class Vocabulary:
    path: str
    sha256: str
    scheme: dict[str, Any]
    source: dict[str, Any]
    attribution: str
    concepts: dict[str, dict[str, Any]] = field(repr=False)

    def concept(self, qcode: str) -> dict[str, Any]:
        if qcode not in self.concepts:
            raise TaxonomyError(f"{qcode} is not a concept of {self.path}")
        return self.concepts[qcode]

    def current(self, qcode: str) -> bool:
        return not self.concept(qcode).get("retired")

    def top(self, qcode: str) -> str:
        """The top concept above ``qcode`` (itself when it is one). Media Topics is a tree: one broader per concept."""
        seen, code = set(), qcode
        while self.concept(code)["broader"]:
            if code in seen:
                raise TaxonomyError(f"{qcode}: the broader chain loops")
            seen.add(code)
            code = self.concept(code)["broader"][0]
        return code

    def label(self, qcode: str, language: str = "es") -> str | None:
        return self.concept(qcode).get(f"label_{language}")

    def pin(self) -> dict[str, str]:
        return {"extract": self.path, "sha256": self.sha256, "date_released": self.scheme.get("date_released") or "",
                "source_sha256": self.source["sha256"]}


def load(relative: str, *, expected_sha256: str | None = None, root: Path = _REPOSITORY) -> Vocabulary:
    """Read an extract; refuse it when its file digest is not ``expected_sha256`` (when given) or its schema is unknown."""
    path = root / relative
    digest, _ = sha256_file(path)
    if expected_sha256 is not None and digest != expected_sha256:
        raise TaxonomyError(f"{relative}: sha256 {digest} is not the pinned {expected_sha256}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != EXTRACT_SCHEMA:
        raise TaxonomyError(f"{relative}: not a {EXTRACT_SCHEMA} extract")
    return Vocabulary(relative, digest, data["scheme"], data["source"], data["attribution"],
                      {concept["qcode"]: concept for concept in data["concepts"]})


ATTRIBUTION = ("Contains IPTC NewsCodes (Media Topics, Genre), (c) IPTC, International Press Telecommunications Council "
               "(https://iptc.org), CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).")

__all__ = ["load", "Vocabulary", "TaxonomyError", "MEDIATOPIC", "GENRE", "ATTRIBUTION"]
