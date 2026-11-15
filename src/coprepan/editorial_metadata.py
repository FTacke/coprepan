"""Editorial placement metadata derived from what the publisher states (CPD-0039): section → IPTC Media Topic, editorial
scope, genre placement and declared genre. Four layers, each with its own id, version, value state and evidence.

**A published section is an editorial placement.** An IPTC Media Topic describes a subject. The layer ``section-iptc/1`` says
which Media Topic the *placement* corresponds to under the versioned mapping ``section-map/1`` (with the SKOS relation of the
label to the concept); it says nothing about what the article is about, and no topic model reads the text. The section the
page published is kept verbatim beside every derived value.

Kept apart, never filled from one another:

=====================  =====================================================  ==============================================
layer                  value                                                  from
=====================  =====================================================  ==============================================
``section-iptc/1``     IPTC Media Topic qcodes of the published section       section labels, ``section-map/1``
``editorial-scope/1``  ``local`` · ``regional`` · ``subnational`` ·            section labels that name a reach or a place
                       ``national`` · ``international``
``genre-placement/1``  the kind of text the *section* names (``opinion`` …)   section labels (an Opinión section places a
                                                                              text; it does not prove it argues)
``genre-declared/1``   the genre the page declares for the article            JSON-LD ``@type`` (schema.org NewsArticle
                       (``opinion``, ``analysis`` …) and its IPTC Genre        subtypes) and ``genre``
=====================  =====================================================  ==============================================

Missing evidence is a value state (``unknown``, ``undecided``) with a reason, never a default and never a negative: an article
without a mapped section is not "general news", an article without a declared genre is not "news". No layer reads a place name
in the text; the country of the outlet is registry metadata and is used only to read a section named after a country.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from . import iptc
from .canonical import sha256_file

SECTION_MAP = "config/taxonomy/section-map_1.json"
SECTION_MAP_SCHEMA = "coprepan-section-map/v1"
_REPOSITORY = Path(__file__).resolve().parents[2]
NOT_VALIDATED = "NOT_VALIDATED"
KNOWN, UNKNOWN, UNDECIDED, NOT_APPLICABLE = "known", "unknown", "undecided", "not_applicable"
RELATIONS = ("closeMatch", "broadMatch", "narrowMatch", "relatedMatch", "exactMatch")
SCOPES = ("local", "regional", "subnational", "national", "international")
GENRE_PLACEMENTS = ("opinion", "editorial", "letters", "analysis", "interview", "reportage", "essay", "cartoon", "obituary")
SECTION_BASES = ("json_ld_articleSection", "meta_article_section", "meta_parsely_section", "meta_section", "breadcrumb", "url_path")

LAYER_SECTION, LAYER_SCOPE = "section-iptc/1", "editorial-scope/1"
LAYER_PLACEMENT, LAYER_DECLARED = "genre-placement/1", "genre-declared/1"

# Declared genre: the schema.org NewsArticle subtypes and ``genre`` values seen on the stored pages, and the IPTC Genre each
# corresponds to. Generic values ("News", "Noticia", NewsArticle) declare no genre and are not read as one -- nor is
# ReportageNewsArticle, which schema.org defines as ordinary journalistic news reporting (not the *reportaje*), and which the
# stored pages show as a CMS default (es_el_mundo 77 of 81 pages, pe_diariocorreo 63 of 85, 2026-11-15).
DECLARED_TYPES = {"OpinionNewsArticle": "opinion", "AnalysisNewsArticle": "analysis", "BackgroundNewsArticle": "background",
                  "ReviewNewsArticle": "review", "SatiricalArticle": "satire",
                  "LiveBlogPosting": "live_coverage", "AskPublicNewsArticle": "ask_public"}
GENERIC_TYPES = frozenset({"NewsArticle", "Article", "BlogPosting", "Report", "ReportageNewsArticle", "SocialMediaPosting",
                           "ScholarlyArticle", "TechArticle", "Posting"})
DECLARED_GENRE_LABELS = {"opinion": "opinion", "editorial": "editorial", "analisis": "analysis", "entrevista": "interview",
                         "reportaje": "reportage", "cronica": "reportage", "satira": "satire", "resena": "review", "critica": "review"}
GENERIC_GENRE_LABELS = frozenset({"news", "noticia", "noticias", "article", "articulo", "nota"})
GENRE_IPTC = {"opinion": ("genre:Opinion", "closeMatch"), "editorial": ("genre:Opinion", "broadMatch"),
              "analysis": ("genre:Analysis", "closeMatch"), "background": ("genre:Background", "closeMatch"),
              "review": ("genre:Review", "closeMatch"), "satire": ("genre:Satire", "closeMatch"),
              "live_coverage": ("genre:LiveCoverage", "closeMatch"), "ask_public": ("genre:Help_Us_to_Report", "closeMatch"),
              "interview": ("genre:Interview", "closeMatch")}
DECLARED_GENRES = tuple(sorted(set(DECLARED_TYPES.values()) | set(DECLARED_GENRE_LABELS.values())))
_URL = re.compile(r"^https?://", re.I)


class MappingError(ValueError):
    """A mapping file that is not the pinned one, or that names a code the pinned taxonomy does not hold."""


def fold(label: str) -> str:
    """The comparison form of a label (``section-map/1``): accents and case dropped, hyphen/underscore/space runs to one space."""
    text = unicodedata.normalize("NFKD", label.strip().lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[\s_\-]+", " ", text).strip()


MAX_LISTED_SECTIONS = 2   # "Noticias, Política" is a section path; "Nacional, CAM, Recogida de basuras, San Salvador" is a tag list


def components(label: str) -> list[str]:
    """The folded components of a published section label (a URL counts by its last path segment). A comma list longer than
    ``MAX_LISTED_SECTIONS`` is the section followed by the article's tags (subject keywords, place names): only its first
    entry is a placement, the tags are never read as one."""
    if _URL.match(label.strip()):
        label = urlsplit(label.strip()).path.rstrip("/").split("/")[-1]
    if len([p for p in label.split(",") if p.strip()]) > MAX_LISTED_SECTIONS:
        label = label.split(",")[0]
    return [part for part in (fold(p) for p in re.split(r"[,|>/]", label)) if part]


def layer(layer_id: str, value: Any, state: str, *, basis: list[dict[str, Any]], rule: Mapping[str, Any],
          attributes: Mapping[str, Any] | None = None, reason: str | None = None) -> dict[str, Any]:
    """One derived-layer record (PHASE3_SCIENTIFIC_ARCHITECTURE §7): value exactly when the state is ``known``."""
    if (value is not None) != (state == KNOWN):
        raise ValueError(f"{layer_id}: a value is given exactly when the state is known")
    return {"layer_id": layer_id, "target_level": "document", "value": value, "value_state": state, "reason": reason,
            "basis": basis, "rule": dict(rule), "validation_status": NOT_VALIDATED, "attributes": dict(attributes or {})}


@dataclass(frozen=True)
class SectionMap:
    path: str
    sha256: str
    mapping_id: str
    topics: dict[str, list[tuple[str, str]]]
    scope_of: dict[str, str]
    country_of: dict[str, str]
    outlet_scopes: dict[str, dict[str, str]]
    placement_of: dict[str, str]
    not_mapped: dict[str, str]
    taxonomy: iptc.Vocabulary

    def pin(self) -> dict[str, Any]:
        return {"mapping": self.mapping_id, "path": self.path, "sha256": self.sha256, "taxonomy": self.taxonomy.pin()}


def load_section_map(relative: str = SECTION_MAP, *, root: Path = _REPOSITORY, taxonomy: iptc.Vocabulary | None = None) -> SectionMap:
    """Read and check a section map: every code exists in the pinned taxonomy and is current, every relation is SKOS, every
    label is in folded form and stands in one table only."""
    path = root / relative
    digest, _ = sha256_file(path)

    def unique(pairs):
        keys = [key for key, _ in pairs]
        if len(keys) != len(set(keys)):
            raise MappingError(f"{relative}: a key is given twice ({sorted(k for k in keys if keys.count(k) > 1)[0]!r})")
        return dict(pairs)

    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    if data.get("schema") != SECTION_MAP_SCHEMA:
        raise MappingError(f"{relative}: not a {SECTION_MAP_SCHEMA} file")
    taxonomy = taxonomy or iptc.load(data["taxonomy"]["extract"], root=root)
    if taxonomy.path != data["taxonomy"]["extract"]:
        raise MappingError(f"{relative} is written against {data['taxonomy']['extract']}, not {taxonomy.path}")
    topics = {label: [(code, relation) for code, relation in entries] for label, entries in data["topics"].items()}
    for label, entries in topics.items():
        for code, relation in entries:
            if relation not in RELATIONS:
                raise MappingError(f"{label}: {relation!r} is not a SKOS mapping relation")
            try:
                if not taxonomy.current(code):
                    raise MappingError(f"{label}: {code} is retired in {taxonomy.path}")
            except iptc.TaxonomyError as error:
                raise MappingError(f"{label}: {error}") from error
    scope_of = {label: scope for scope, labels in data["scopes"].items() for label in labels}
    placement_of = {label: kind for kind, labels in data["genre_placements"].items() for label in labels}
    not_mapped = {label: why for why, labels in data["not_mapped"].items() for label in labels}
    if set(scope_of.values()) - set(SCOPES) or set(placement_of.values()) - set(GENRE_PLACEMENTS):
        raise MappingError(f"{relative}: a scope or genre placement outside the closed vocabulary")
    for scopes in data["outlet_scopes"].values():
        if set(scopes.values()) - set(SCOPES):
            raise MappingError(f"{relative}: an outlet scope outside the closed vocabulary")
    tables = [set(topics), set(scope_of), set(placement_of), set(not_mapped), set(data["country_labels"])]
    every = [label for table in tables for label in table]
    if len(every) != len(set(every)) or any(fold(label) != label for label in every):
        raise MappingError(f"{relative}: a label stands in two tables or is not in folded form")
    return SectionMap(relative, digest, data["mapping_id"], topics, scope_of, dict(data["country_labels"]),
                      {outlet: dict(scopes) for outlet, scopes in data["outlet_scopes"].items()}, placement_of, not_mapped, taxonomy)


def _sources(harvest: Mapping[str, Any], known: set[str]) -> list[tuple[str, str, list[str]]]:
    """``(basis, published value, components)`` in the order of precedence. Breadcrumbs without their first item (the home
    page) and last item (the article); the address only by a first path segment the map knows -- a slug is not a section."""
    out = []
    for basis in SECTION_BASES[:4]:
        out += [(basis, s["value"], components(s["value"])) for s in harvest.get("sections", []) if s["basis"] == basis]
    crumbs = list(harvest.get("breadcrumb") or [])[1:-1]
    if crumbs:
        out.append(("breadcrumb", " > ".join(crumbs), [part for crumb in crumbs for part in components(crumb)]))
    path = harvest.get("url_path") or []
    if path and fold(path[0]) in known:
        out.append(("url_path", path[0], [fold(path[0])]))
    return out


def classify(harvest: Mapping[str, Any], *, outlet_id: str, country_id: str, section_map: SectionMap) -> dict[str, dict[str, Any]]:
    """The four layers for one page, from its publisher statements."""
    m = section_map
    known = set(m.topics) | set(m.scope_of) | set(m.placement_of) | set(m.country_of) | set(m.outlet_scopes.get(outlet_id, {}))
    sources = _sources(harvest, known)
    rule = m.pin()
    published = [{"basis": basis, "value": value} for basis, value, _ in sources]
    out: dict[str, dict[str, Any]] = {}

    # section-iptc/1: the first source (in precedence) that names a mapped topic decides; the others stay as published
    for basis, value, parts in sources:
        concepts = [(code, relation, part) for part in parts for code, relation in m.topics.get(part, [])]
        if concepts:
            codes = sorted(dict.fromkeys(code for code, _, _ in concepts))
            out[LAYER_SECTION] = layer(LAYER_SECTION, codes, KNOWN, basis=[{"basis": basis, "value": value}], rule=rule, attributes={
                "published": published,
                "concepts": [{"qcode": code, "relation": relation, "label": part, "label_es": m.taxonomy.label(code, "es"),
                              "label_en": m.taxonomy.label(code, "en"), "top": m.taxonomy.top(code)} for code, relation, part in concepts],
                "tops": sorted({m.taxonomy.top(code) for code in codes})})
            break
    else:
        parts = [part for _, _, ps in sources for part in ps]
        if not sources:
            state, reason = UNKNOWN, "no_section_published"
        elif any(m.not_mapped.get(part) == "ambiguous" for part in parts):
            state, reason = UNDECIDED, "ambiguous_label"
        elif parts and all(part in m.not_mapped for part in parts):
            state, reason = UNKNOWN, "generic_or_template_label"
        elif any(part in m.scope_of or part in m.country_of or part in m.placement_of or part in m.outlet_scopes.get(outlet_id, {})
                 for part in parts):
            state, reason = UNKNOWN, "section_names_no_topic"
        else:
            state, reason = UNKNOWN, "unmapped_label"
        out[LAYER_SECTION] = layer(LAYER_SECTION, None, state, basis=published, rule=rule, reason=reason,
                                   attributes={"published": published})

    # editorial-scope/1
    for basis, value, parts in sources:
        scopes = []
        for part in parts:
            if part in m.outlet_scopes.get(outlet_id, {}):
                scopes.append((m.outlet_scopes[outlet_id][part], part, "outlet_place_label"))
            elif part in m.scope_of:
                scopes.append((m.scope_of[part], part, "scope_label"))
            elif part in m.country_of:
                own = m.country_of[part] == country_id
                scopes.append(("national" if own else "international", part, "own_country_label" if own else "other_country_label"))
        if scopes:
            distinct = sorted({scope for scope, _, _ in scopes})
            evidence = [{"basis": basis, "value": value, "label": part, "rule": how} for _, part, how in scopes]
            if len(distinct) == 1:
                out[LAYER_SCOPE] = layer(LAYER_SCOPE, distinct[0], KNOWN, basis=evidence, rule=rule)
            else:
                out[LAYER_SCOPE] = layer(LAYER_SCOPE, None, UNDECIDED, basis=evidence, rule=rule, reason="conflicting_scope_labels",
                                         attributes={"candidates": distinct})
            break
    else:
        out[LAYER_SCOPE] = layer(LAYER_SCOPE, None, UNKNOWN, basis=published, rule=rule,
                                 reason="no_section_published" if not sources else "no_scope_label")

    # genre-placement/1
    for basis, value, parts in sources:
        placements = sorted({m.placement_of[part] for part in parts if part in m.placement_of})
        if placements:
            out[LAYER_PLACEMENT] = layer(LAYER_PLACEMENT, placements, KNOWN, basis=[{"basis": basis, "value": value}], rule=rule,
                                         attributes={"note": "a placement, not a property of the text"})
            break
    else:
        out[LAYER_PLACEMENT] = layer(LAYER_PLACEMENT, None, UNKNOWN, basis=published, rule=rule,
                                     reason="no_section_published" if not sources else "no_genre_section")

    out[LAYER_DECLARED] = declared_genre(harvest, rule={"rule": LAYER_DECLARED, "genre_vocabulary": iptc.GENRE})
    return out


def declared_genre(harvest: Mapping[str, Any], *, rule: Mapping[str, Any]) -> dict[str, Any]:
    """``genre-declared/1``: the genre the page states for the article (a schema.org NewsArticle subtype, or ``genre``)."""
    found, unread = [], []
    for t in harvest.get("article_types", []):
        if t in DECLARED_TYPES:
            found.append((DECLARED_TYPES[t], "json_ld_type", t))
    for value in harvest.get("genre", []):
        label = fold(value)
        if _URL.match(value) or label in GENERIC_GENRE_LABELS:
            unread.append(value)
        elif label in DECLARED_GENRE_LABELS:
            found.append((DECLARED_GENRE_LABELS[label], "json_ld_genre", value))
        else:
            unread.append(value)
    if not found:
        return layer(LAYER_DECLARED, None, UNKNOWN, basis=[], rule=rule,
                     reason="genre_values_not_read" if unread else "no_genre_declared", attributes={"unread": unread})
    values = sorted({genre for genre, _, _ in found})
    return layer(LAYER_DECLARED, values, KNOWN, basis=[{"basis": basis, "value": verbatim} for _, basis, verbatim in found], rule=rule,
                 attributes={"iptc_genre": [{"genre": genre, "qcode": GENRE_IPTC[genre][0], "relation": GENRE_IPTC[genre][1]}
                                            for genre in values if genre in GENRE_IPTC], "unread": unread})


__all__ = ["classify", "declared_genre", "load_section_map", "fold", "components", "layer", "SectionMap", "MappingError",
           "SCOPES", "GENRE_PLACEMENTS", "DECLARED_GENRES", "LAYER_SECTION", "LAYER_SCOPE", "LAYER_PLACEMENT", "LAYER_DECLARED"]
