"""Document identity: which fetch is which article, in which textual state (decision CPD-0005).

Five identities are kept apart (``docs/architecture/TARGET_ARCHITECTURE.md`` §6):

* the **fetch** — one retrieval event (``fetch_id``);
* the **source object** — the body bytes (``body_sha256``);
* the **document** — the article as an editorial unit, identified by its canonical URL key within
  an outlet (``document_id``). *Not* by the observed URL: tracking parameters, origin aliases and
  declared variants fold into one key;
* the **document version** — one textual state (``document_version_id``), identified by the
  digest of the extracted text. The same URL with new text is a new version of the same
  document; the same text fetched again is the same version;
* **relations** between documents — ``duplicate_of`` (identical body text under another
  document) and ``moved_to`` (a URL that now leads to another document). A relation never
  rewrites an id and never removes a row.

Tables are append-only line files. Opening replays them, so an id that would collide with an
existing one under a different key is refused instead of silently merged.
"""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urljoin

from . import naming
from .canonical import require_sha256
from .identity import (
    IdentityError,
    OutletUrlRules,
    canonical_url_key,
    document_id,
    document_version_id,
    is_document_id,
    is_fetch_id,
)
from .jsonl import append_row, read_rows

DOCUMENT_SCHEMA = naming.schema_id("document-identity", 1)
OBSERVATION_SCHEMA = naming.schema_id("document-observation", 1)
VERSION_SCHEMA = naming.schema_id("document-version", 1)
RELATION_SCHEMA = naming.schema_id("document-relation", 1)
HEAD_SCAN_VERSION = "head-scan/1"

RELATION_DUPLICATE_OF = "duplicate_of"
RELATION_MOVED_TO = "moved_to"
RELATIONS = (RELATION_DUPLICATE_OF, RELATION_MOVED_TO)

_HEAD_SCAN_LIMIT = 512 * 1024


class DocumentIdCollision(IdentityError):
    """Two different keys (or two different texts) produce the same truncated id."""


@dataclass(frozen=True)
class Assignment:
    document_id: str
    is_new_document: bool
    url_key: str
    url_key_basis: str


@dataclass(frozen=True)
class VersionAssignment:
    document_version_id: str
    is_new_version: bool
    duplicate_of: str | None


class _CanonicalLink(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.href: str | None = None
        self.done = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.done:
            return
        if tag == "body":
            self.done = True
        elif tag == "link":
            attributes = dict(attrs)
            if "canonical" in (attributes.get("rel") or "").lower().split() and attributes.get("href"):
                self.href, self.done = attributes["href"].strip(), True

    def handle_endtag(self, tag: str) -> None:
        if tag == "head":
            self.done = True


def read_rel_canonical(body: bytes, base_url: str) -> str | None:
    """The first ``<link rel="canonical">`` of the document head, made absolute against the URL the
    body came from. Versioned as ``head-scan/1``: it reads markup only, decodes leniently (the
    link is ASCII or percent-escaped in practice) and never fails — no link means ``None``.
    """
    parser = _CanonicalLink()
    try:
        parser.feed(body[:_HEAD_SCAN_LIMIT].decode("utf-8", errors="replace"))
    except Exception:  # noqa: BLE001 - a malformed head is "no canonical link", not an error
        return None
    if not parser.href:
        return None
    try:
        return urljoin(base_url, parser.href)
    except ValueError:
        return None


class IdentityTables:
    """The append-only identity tables of one workspace."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self._documents = self.directory / "documents.jsonl"
        self._observations = self.directory / "observations.jsonl"
        self._versions = self.directory / "versions.jsonl"
        self._relations = self.directory / "relations.jsonl"
        self.documents: dict[str, dict[str, Any]] = {r["document_id"]: r for r in read_rows(self._documents, DOCUMENT_SCHEMA)}
        self.observations: dict[str, dict[str, Any]] = {r["fetch_id"]: r for r in read_rows(self._observations, OBSERVATION_SCHEMA)}
        self.versions: dict[str, dict[str, Any]] = {}
        self.version_observations: set[tuple[str, str]] = set()
        for row in read_rows(self._versions, VERSION_SCHEMA):
            self.versions.setdefault(row["document_version_id"], row)
            self.version_observations.add((row["document_version_id"], row["fetch_id"]))
        self.relations: list[dict[str, Any]] = read_rows(self._relations, RELATION_SCHEMA)
        self._by_key = {(row["outlet_id"], row["url_key"]): row["document_id"] for row in self.documents.values()}

    # -- documents -----------------------------------------------------------------------------

    def assign_document(
        self, rules: OutletUrlRules, fetch_record: Mapping[str, Any], body: bytes | None
    ) -> Assignment:
        """Assign a fetch to its document. Idempotent per fetch."""
        fetch = fetch_record["fetch_id"]
        if fetch_record["outlet_id"] != rules.outlet_id:
            raise IdentityError(f"{fetch} belongs to {fetch_record['outlet_id']}, rules are for {rules.outlet_id}")
        if fetch in self.observations:
            seen = self.observations[fetch]
            return Assignment(seen["document_id"], False, seen["url_key"], seen["url_key_basis"])

        requested = fetch_record["request"]["requested_url"]
        final = fetch_record["response"]["final_url"]
        final = final if final not in ("not_applicable", None) else None
        canonical = None
        if body is not None:
            try:
                from .extraction import decode_content  # local: extraction does not import this module
                canonical = read_rel_canonical(decode_content(body, fetch_record["response"]["content_encoding"]),
                                               final or requested)
            except ValueError:
                canonical = None  # an undecodable body has no readable head; the URL still keys it
        key = canonical_url_key(rules, requested_url=requested, final_url=final, rel_canonical=canonical)
        document = document_id(rules.outlet_id, key.key)
        # The keys of the request and of the final URL on their own, kept beside the chosen key:
        # they are what makes a mis-declared canonical (many pages naming one URL) detectable.
        own_keys = {}
        for name, url in (("requested_url_key", requested), ("final_url_key", final)):
            try:
                own_keys[name] = canonical_url_key(rules, requested_url=url).key if url else None
            except IdentityError:
                own_keys[name] = None

        existing = self.documents.get(document)
        if existing is not None and existing["url_key"] != key.key:
            raise DocumentIdCollision(
                f"{document} is the id of {existing['url_key']!r} and would also be the id of {key.key!r}"
            )
        is_new = existing is None
        if is_new:
            row = append_row(
                self._documents,
                DOCUMENT_SCHEMA,
                {"document_id": document, "outlet_id": rules.outlet_id, "url_key": key.key,
                 "url_key_ruleset": key.ruleset, "outlet_url_rules_version": key.outlet_rules_version,
                 "first_fetch_id": fetch},
            )
            self.documents[document] = row
            self._by_key[(rules.outlet_id, key.key)] = document

        observation = append_row(
            self._observations,
            OBSERVATION_SCHEMA,
            {"fetch_id": fetch, "document_id": document, "requested_url": requested, "final_url": final,
             "rel_canonical": canonical, "head_scan": HEAD_SCAN_VERSION, **own_keys, **key.as_record()},
        )
        self.observations[fetch] = observation

        # The requested URL, keyed on its own, may be the key of another document: the outlet has
        # moved that article here. Recorded as a relation; neither id changes.
        if key.basis != "requested_url":
            requested_key = own_keys["requested_url_key"]
            other = self._by_key.get((rules.outlet_id, requested_key)) if requested_key else None
            if other is not None and other != document:
                self._relate(RELATION_MOVED_TO, other, document, {"fetch_id": fetch, "requested_url_key": requested_key})
        return Assignment(document, is_new, key.key, key.basis)

    def assign_revalidation(self, fetch_record: Mapping[str, Any]) -> tuple[str, list[str]] | None:
        """Record a ``304 Not Modified`` fetch as one more observation of what it revalidates.

        The fetch has no body, so nothing about it can be keyed or extracted on its own: it
        belongs to the document of the fetch whose body the server confirmed, and to that fetch's
        version(s). Returns ``(document_id, version ids)``, or ``None`` when the revalidated fetch
        is not in these tables — then nothing is assigned, and nothing is guessed.
        """
        fetch, target = fetch_record["fetch_id"], fetch_record["revalidates"]
        if not isinstance(target, Mapping) or target["fetch_id"] not in self.observations:
            return None
        held = self.observations[target["fetch_id"]]
        versions = [version for (version, seen) in sorted(self.version_observations) if seen == target["fetch_id"]]
        if fetch not in self.observations:
            self.observations[fetch] = append_row(
                self._observations, OBSERVATION_SCHEMA,
                {"fetch_id": fetch, "document_id": held["document_id"], "requested_url": fetch_record["request"]["requested_url"],
                 "final_url": fetch_record["response"]["final_url"], "rel_canonical": None, "head_scan": HEAD_SCAN_VERSION,
                 "requested_url_key": held.get("requested_url_key"), "final_url_key": held.get("final_url_key"),
                 "url_key": held["url_key"], "url_key_basis": "revalidation", "url_key_input": held["url_key_input"],
                 "url_key_ruleset": held["url_key_ruleset"], "outlet_url_rules_version": held["outlet_url_rules_version"],
                 "revalidates_fetch_id": target["fetch_id"]})
        for version in versions:
            if (version, fetch) not in self.version_observations:
                append_row(self._versions, VERSION_SCHEMA, {**{k: v for k, v in self.versions[version].items() if k != "schema"},
                                                            "fetch_id": fetch, "revalidates_fetch_id": target["fetch_id"]})
                self.version_observations.add((version, fetch))
        return held["document_id"], versions

    # -- versions ------------------------------------------------------------------------------

    def assign_version(
        self,
        document: str,
        fetch: str,
        *,
        extracted_text_sha256: str,
        body_text_sha256: str,
        extractor: str,
        extractor_version: str,
        extraction_fingerprint: str,
        has_body_text: bool = True,
    ) -> VersionAssignment:
        """Assign the textual state a fetch showed. Idempotent per (version, fetch).

        ``has_body_text=False`` (nothing was extracted as body) suppresses the duplicate check:
        two empty bodies are not the same article.
        """
        if document not in self.documents:
            raise IdentityError(f"unknown document: {document!r}")
        if not is_fetch_id(fetch) or self.observations.get(fetch, {}).get("document_id") != document:
            raise IdentityError(f"{fetch} was not assigned to {document}")
        require_sha256(body_text_sha256, "body_text_sha256")
        version = document_version_id(document, extracted_text_sha256)
        existing = self.versions.get(version)
        if existing is not None and existing["extracted_text_sha256"] != extracted_text_sha256:
            raise DocumentIdCollision(f"{version} already identifies another extracted text")
        is_new = existing is None

        duplicate_of = None
        if is_new and has_body_text:
            for other in self.versions.values():
                if other["body_text_sha256"] == body_text_sha256 and other["document_id"] != document:
                    duplicate_of = other["document_id"]
                    break
        if (version, fetch) not in self.version_observations:
            row = append_row(
                self._versions,
                VERSION_SCHEMA,
                {"document_version_id": version, "document_id": document, "fetch_id": fetch,
                 "extracted_text_sha256": extracted_text_sha256, "body_text_sha256": body_text_sha256,
                 "extractor": extractor, "extractor_version": extractor_version,
                 "extraction_fingerprint": require_sha256(extraction_fingerprint, "extraction_fingerprint")},
            )
            self.versions.setdefault(version, row)
            self.version_observations.add((version, fetch))
        if duplicate_of is not None:
            self._relate(RELATION_DUPLICATE_OF, document, duplicate_of,
                         {"document_version_id": version, "body_text_sha256": body_text_sha256})
        return VersionAssignment(version, is_new, duplicate_of)

    def canonical_collapse_suspects(self, minimum_distinct_urls: int = 3) -> list[dict[str, Any]]:
        """Documents whose key came from ``rel=canonical`` while their fetches were answered at
        several *different* final URLs — the signature of pages that all declare one canonical
        (a section page, the home page). A diagnosis for review: it changes no id and decides
        nothing; folding real variants of one article produces the same picture, which is why the
        threshold is a parameter and the result is a list to look at.
        """
        final_keys: dict[str, set[str]] = {}
        for row in self.observations.values():
            if row["url_key_basis"] == "rel_canonical" and row.get("final_url_key") not in (None, row["url_key"]):
                final_keys.setdefault(row["document_id"], set()).add(row["final_url_key"])
        return [
            {"document_id": document, "url_key": self.documents[document]["url_key"], "distinct_final_url_keys": sorted(keys)}
            for document, keys in sorted(final_keys.items()) if len(keys) >= minimum_distinct_urls
        ]

    def versions_of(self, document: str) -> list[str]:
        """The versions of a document, in the order they were first seen."""
        return [version for version, row in self.versions.items() if row["document_id"] == document]

    def _relate(self, relation: str, subject: str, target: str, evidence: Mapping[str, Any]) -> None:
        if not is_document_id(subject) or not is_document_id(target) or relation not in RELATIONS:
            raise IdentityError(f"not a relation: {relation} {subject} {target}")
        if any(r["relation"] == relation and r["document_id"] == subject and r["target_document_id"] == target
               for r in self.relations):
            return
        self.relations.append(
            append_row(self._relations, RELATION_SCHEMA,
                       {"relation": relation, "document_id": subject, "target_document_id": target,
                        "evidence": dict(evidence)})
        )
