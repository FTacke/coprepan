"""Editorial and provenance metadata of one page, as one write-once layer artifact (``editorial-metadata/1``, CPD-0039).

One derivation per (preserved body, extraction record, rule versions, mapping and taxonomy digests): the fingerprint names all
of them, so a stored answer is reused as long as none changes, and a new mapping or rule version is a new artifact beside the
old one -- never an edit of it (AGENTS §10, §11). The derivation needs the page's decoded markup and its extraction record
only; it fetches nothing and reads no other document. Cross-document evidence (text reuse, site-wide notices, outlet-level
constants) is a separate, corpus-level step: :mod:`coprepan.text_reuse` and :func:`coprepan.provenance.site_wide_statements`.

Payload: the publisher statements (``publisher-metadata/1``) and the six derived layers, every one ``NOT_VALIDATED``. Nothing
here is read by the content-quality gate: CORE membership is a property of the text, never of these layers.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from . import editorial_metadata as M
from . import layer_store, provenance, publisher_metadata
from .canonical import canonical_json, record_json, require_sha256, sha256_bytes

STAGE = "enrichment"
VERSION = "editorial-metadata/1"
LAYERS = (M.LAYER_SECTION, M.LAYER_SCOPE, M.LAYER_PLACEMENT, M.LAYER_DECLARED, provenance.LAYER_AI, provenance.LAYER_AGENCY)


def fingerprint(*, body_sha256: str, extraction_payload_sha256: str, section_map: M.SectionMap,
                site_wide: frozenset[str] = frozenset()) -> str:
    return layer_store.fingerprint(STAGE, VERSION, {"body": require_sha256(body_sha256, "body_sha256"),
                                                    "extraction": require_sha256(extraction_payload_sha256, "extraction")},
                                   {"section_map": section_map.sha256, "taxonomy": section_map.taxonomy.sha256,
                                    "harvest": publisher_metadata.VERSION, "layers": list(LAYERS),
                                    "site_wide_statements": sha256_bytes(canonical_json(sorted(site_wide)))})


def derive(*, html: str, url: str, record: Mapping[str, Any], outlet_id: str, country_id: str, section_map: M.SectionMap,
           site_wide: frozenset[str] = frozenset()) -> dict[str, Any]:
    """The metadata of one page. Pure: the same inputs give the same bytes."""
    harvest = publisher_metadata.harvest(html, url=url)
    layers = M.classify(harvest, outlet_id=outlet_id, country_id=country_id, section_map=section_map)
    layers[provenance.LAYER_AI] = provenance.ai_disclosure(record, site_wide=set(site_wide))
    layers[provenance.LAYER_AGENCY] = provenance.agency_credit(record, harvest)
    return {"version": VERSION, "extraction": {"extractor": record["extractor"], "schema": record["schema"],
                                               "extracted_text_sha256": record["extracted_text_sha256"],
                                               "body_text_sha256": record["body_text_sha256"]},
            "publisher": harvest, "layers": {name: layers[name] for name in LAYERS}}


def derive_stored(store: layer_store.LayerStore, *, body_sha256: str, extraction_payload: bytes, html: str, url: str,
                  outlet_id: str, country_id: str, section_map: M.SectionMap, site_wide: frozenset[str] = frozenset(),
                  provenance_record: Mapping[str, Any] | None = None, now=None) -> tuple[dict[str, Any], str, bool]:
    """``(metadata, fingerprint, reused)``: the stored answer when its fingerprint is held, otherwise derived and stored once."""
    value = fingerprint(body_sha256=body_sha256, extraction_payload_sha256=sha256_bytes(extraction_payload), section_map=section_map,
                        site_wide=site_wide)
    if store.get(STAGE, value) is not None:
        return json.loads(store.read(STAGE, value).decode("utf-8")), value, True
    record = json.loads(extraction_payload.decode("utf-8"))
    metadata = derive(html=html, url=url, record=record, outlet_id=outlet_id, country_id=country_id, section_map=section_map,
                      site_wide=site_wide)
    store.put(STAGE, value, record_json(metadata), provenance=dict(provenance_record or {}), now=now)
    return metadata, value, False


__all__ = ["derive", "derive_stored", "fingerprint", "STAGE", "VERSION", "LAYERS"]
