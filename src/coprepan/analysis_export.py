"""CO.PRE.PAN's side of the cross-corpus analysis contract — adapter prototype (CPD-0008).

Turns what this repository's own stages produce — registry rows, document identity, extraction
records — plus an **annotation supplied from outside** into a ``crosscorpus-analysis/v1`` bundle.

What it is not: an export of corpus material (none exists), and not an annotator. COPREPAN has no
NLP stage yet; the sentences and tokens come in as an argument. In the tests they are written by
hand for a synthetic page. The adapter's job is the *mapping*: which internal thing becomes which
contract row, under which id, with which value state — and to refuse what does not fit.

Mapping, in one place:

=====================  ===========================================================================
contract               from
=====================  ===========================================================================
document               one document version (the sampled unit); ``editorial_id`` is the document
unit                   one extraction block; ``surface`` from its role (body → primary)
sentence, token        the supplied annotation; ids hang on the document version (CPD-0003)
production_mode        ``written_edited`` — declared by corpus design, never inferred
char anchors           offsets into the unit's text, checked against the token's form
time anchors           ``not_applicable``
date                   only from a parsed date handed in with its basis; a page value nobody has
                       parsed yet is ``not_available``, a page without one ``unknown``
=====================  ===========================================================================
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import analysis_contract as A
from . import extraction, identity, naming, registry

SURFACE_OF_ROLE = {extraction.ROLE_BODY: "primary", extraction.ROLE_TITLE: "title", extraction.ROLE_NON_BODY: "auxiliary"}
SCOPE_REASON_NON_BODY = "non_body_block"
VOCABULARIES = {
    "outlet_kind": [value for value in registry.OUTLET_TYPES if value != registry.UNKNOWN],
    "provenance_class": list(naming.PROVENANCE_CLASSES),
    "date_basis": list(extraction.BASES[:-1]),
    "language_basis": ["declared_by_page", "identified"],
    "section_mapped": [],            # no section mapping exists
    "producer_role": [],             # no author-role vocabulary exists
    "scope_reason": [SCOPE_REASON_NON_BODY, "technically_unusable"],
}


class ExportRefused(ValueError):
    """Internal material that cannot be stated in the contract without guessing."""


def _stateful(name: str, value: Any, state: str | None = None) -> dict[str, Any]:
    """A stateful field. COPREPAN's internal ``unknown`` becomes the state, never a value."""
    if state is None:
        state = A.UNKNOWN if value in (None, "", extraction.UNKNOWN) else A.KNOWN
    return {name: value if state == A.KNOWN else None, f"{name}_state": state}


def outlet_row(outlet: Mapping[str, Any]) -> dict[str, Any]:
    if outlet["registration_status"] != "registered":
        raise ExportRefused(f"{outlet['outlet_id']} is not registered: a proposed outlet has no id to export under")
    return {"outlet_id": outlet["outlet_id"], "corpus_id": naming.CORPUS_ID, "country_id": outlet["country_id"],
            "display_name": outlet["display_names"][-1]["name"], **_stateful("outlet_kind", outlet["outlet_type"]),
            **_stateful("city", outlet["city"]), **_stateful("region", outlet["region"]), **_stateful("scope", outlet["scope"]),
            **_stateful("outlet_group", outlet["outlet_group"])}


def export_bundle(
    *,
    release: Mapping[str, Any],
    outlets: Sequence[Mapping[str, Any]],
    documents: Sequence[Mapping[str, Any]],
    relations: Sequence[Mapping[str, Any]] = (),
    layers: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build and seal a bundle; raise unless it conforms.

    Each of ``documents``: ``outlet_id``, ``document_id``, ``document_version_id``, ``record`` (an
    extraction record), ``annotation`` (``{block index: [sentence, …]}``, a sentence being a list
    of tokens with ``form, lemma, upos, xpos, morph, head, deprel, char_start, char_end`` — ``head``
    the index of the head inside the sentence, ``None`` for the root), optional ``publication_date``
    (``{"date": "YYYY-MM-DD", "basis": …, "cohort": "YYYY-Qn"}``) and ``provenance_class``.

    Each of ``relations``: ``relation``, ``document_id``, ``target_document_id`` (internal document
    ids), ``basis``. ``layers``: ``{layer id: {"declaration": …, "rows": […]}}``.
    """
    tables: dict[str, list[dict[str, Any]]] = {name: [] for name in A.TABLES}
    tables["outlets"] = [outlet_row(outlet) for outlet in sorted(outlets, key=lambda o: o["outlet_id"])]
    countries = {row["outlet_id"]: row["country_id"] for row in tables["outlets"]}
    regions = {row["outlet_id"]: (row["region"], row["region_state"]) for row in tables["outlets"]}
    version_of: dict[str, str] = {}

    for document in documents:
        record, version = document["record"], document["document_version_id"]
        if record["outcome"] != extraction.OUTCOME_EXTRACTED:
            raise ExportRefused(f"{version}: a fetch that was not extracted has no text to export")
        if identity.document_version_id(document["document_id"], record["extracted_text_sha256"]) != version:
            raise ExportRefused(f"{version}: the version id does not belong to this extraction")
        if version_of.setdefault(document["document_id"], version) != version:
            raise ExportRefused(f"{document['document_id']}: two versions of one document in one bundle need an explicit relation; not built")
        metadata, annotation = record["metadata"], document.get("annotation", {})
        dated = document.get("publication_date")
        page_date = metadata["publication_date"]["value"] != extraction.UNKNOWN
        date_state = A.KNOWN if dated else (A.NOT_AVAILABLE if page_date else A.UNKNOWN)
        declared = metadata["language"]["value"]
        units, sentences, tokens = [], [], []
        chain: dict[str, list[dict[str, Any]]] = {}
        token_index = 0
        for block in record["blocks"]:
            surface = SURFACE_OF_ROLE[block["role"]]
            unit_id = identity.unit_id(version, block["index"])
            counted = 0
            for sentence in annotation.get(block["index"], ()):
                if surface == "auxiliary":
                    raise ExportRefused(f"{unit_id}: a non-body block is not annotated in this contract version")
                sentence_id = identity.sentence_id(version, len(sentences))
                ids = [identity.token_id(version, token_index + offset) for offset in range(len(sentence))]
                for position, token in enumerate(sentence):
                    if block["text"][token["char_start"]:token["char_end"]] != token["form"]:
                        raise ExportRefused(f"{ids[position]}: the offsets do not point at {token['form']!r} in the unit's text")
                    kind = "punctuation" if token["upos"] == "PUNCT" else "word"
                    row = {"token_id": ids[position], "sentence_id": sentence_id, "unit_id": unit_id, "document_id": version,
                           "order_index": position, "form": token["form"], "lemma": token["lemma"], "upos": token["upos"],
                           "morph": dict(sorted(token["morph"].items())), "deprel": token["deprel"], "token_kind": kind,
                           "production_event_types": [], "counted": kind == "word" and surface == "primary",
                           **_stateful("xpos", token.get("xpos")),
                           **_stateful("head_token_id", None if token["head"] is None else ids[token["head"]],
                                       A.NOT_APPLICABLE if token["head"] is None else A.KNOWN),
                           **_stateful("char_start", token["char_start"], A.KNOWN), **_stateful("char_end", token["char_end"], A.KNOWN),
                           **_stateful("start_ms", None, A.NOT_APPLICABLE), **_stateful("end_ms", None, A.NOT_APPLICABLE)}
                    counted += row["counted"]
                    tokens.append(row)
                token_index += len(sentence)
                row = {"sentence_id": sentence_id, "unit_id": unit_id, "document_id": version, "surface": surface,
                       "order_index": len(chain.setdefault(surface, [])),
                       **_stateful("char_start", min(t["char_start"] for t in sentence), A.KNOWN),
                       **_stateful("char_end", max(t["char_end"] for t in sentence), A.KNOWN),
                       **_stateful("start_ms", None, A.NOT_APPLICABLE), **_stateful("end_ms", None, A.NOT_APPLICABLE)}
                chain[surface].append(row)
                sentences.append(row)
            in_scope = surface != "auxiliary"
            units.append({"unit_id": unit_id, "document_id": version, "unit_kind": block["kind"], "segmentation_nature": "editorial",
                          "surface": surface, "order_index": block["index"], "scope_status": "in_scope" if in_scope else "out_of_scope",
                          "tokens_counted": counted, **_stateful("parent_unit_id", None, A.NOT_APPLICABLE),
                          **_stateful("production_mode", "written_edited", A.KNOWN),
                          **_stateful("production_mode_share", None, A.NOT_APPLICABLE),
                          **_stateful("producer_id", None, A.NOT_AVAILABLE), **_stateful("producer_role", None, A.NOT_AVAILABLE),
                          **_stateful("scope_reason", None if in_scope else SCOPE_REASON_NON_BODY,
                                      A.NOT_APPLICABLE if in_scope else A.KNOWN)})
        for rows in chain.values():
            for position, row in enumerate(rows):
                row.update(_stateful("previous_sentence_id", rows[position - 1]["sentence_id"] if position else None,
                                     A.KNOWN if position else A.NOT_APPLICABLE))
                last = position + 1 == len(rows)
                row.update(_stateful("next_sentence_id", None if last else rows[position + 1]["sentence_id"],
                                     A.NOT_APPLICABLE if last else A.KNOWN))
        region, region_state = regions[document["outlet_id"]]
        tables["documents"].append({
            "document_id": version, "corpus_id": naming.CORPUS_ID, "release_id": release["release_id"],
            "outlet_id": document["outlet_id"], "country_id": countries[document["outlet_id"]], "modality": "written",
            "provenance_class": document.get("provenance_class", "native_v3"),
            "tokens_total": len(tokens), "tokens_counted": sum(t["counted"] for t in tokens),
            **_stateful("editorial_id", document["document_id"], A.KNOWN), **_stateful("region", region, region_state),
            **_stateful("production_mode", "written_edited", A.KNOWN),
            **_stateful("date", dated["date"] if dated else None, date_state),
            **_stateful("date_basis", dated["basis"] if dated else None, date_state),
            **_stateful("cohort", dated["cohort"] if dated else None, date_state),
            **_stateful("section_published", metadata["section"]["value"]),
            **_stateful("section_mapped", None, A.NOT_AVAILABLE), **_stateful("programme", None, A.NOT_APPLICABLE),
            **_stateful("language", declared), **_stateful("language_basis", "declared_by_page" if declared != extraction.UNKNOWN else None),
        })
        tables["units"] += units
        tables["sentences"] += sentences
        tables["tokens"] += tokens

    for relation in relations:
        if relation["document_id"] not in version_of:
            raise ExportRefused(f"relation from {relation['document_id']}: not a document of this bundle")
        target = version_of.get(relation["target_document_id"])
        tables["relations"].append({"relation": relation["relation"], "document_id": version_of[relation["document_id"]],
                                    "target_document_id": target or relation["target_document_id"],
                                    "target_in_release": target is not None, "basis": relation["basis"]})

    layers = layers or {}
    record = {"contract": A.CONTRACT, "corpus_id": naming.CORPUS_ID, "modality": "written", "token_denominator": A.TOKEN_DENOMINATOR,
              "vocabularies": VOCABULARIES,
              "anchors": {"char_reference": "code-point offsets, half-open, into the text of the token's unit",
                          "time_reference": "not_applicable"},
              "id_stability": "unit, sentence and token ids hang on the document version and the annotator contract; "
                              "they are stable within a release and not promised across releases",
              "layers": {layer_id: dict(layer["declaration"]) for layer_id, layer in layers.items()},
              **release}
    bundle = A.seal({"release": record, "tables": tables, "layers": {layer_id: list(layer["rows"]) for layer_id, layer in layers.items()},
                     "compatibility": []})
    A.require_valid(bundle)
    return bundle


def with_compatibility(bundle: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The same bundle with a compatibility view attached, resealed and revalidated."""
    out = A.seal({**bundle, "compatibility": list(rows)})
    A.require_valid(out)
    return out
