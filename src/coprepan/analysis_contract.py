"""The cross-corpus analysis contract ``crosscorpus-analysis/v1`` — prototype (CPD-0008).

One **analysis layer** that CO.RA.PAN (spoken radio) and CO.PRE.PAN (written press) can both
export to. It is not a shared raw or pipeline model: each corpus keeps its own, and an adapter on
each side writes these tables. What is shared is the vocabulary, the id discipline, the value
states and the counting rule.

**Status: a technical proposal with a validator.** The contract concerns two repositories and is
decided jointly; nothing here is in force in CO.RA.PAN, and no release of either corpus exists.
The validator is fail closed: a bundle is conformant only if no check objects.

Shape of a bundle::

    release        one record: what was frozen, with which instrument, pinned by hashes
    outlets        the publishing institution (station, publication)
    documents      the sampled unit (recording; article in one textual state)
    units          the level above the sentence, with a declared kind and nature
    sentences      instrument output, neighbours addressable by id
    tokens         instrument output, one typed schema, medium-typed anchors
    relations      duplicate and syndication relations between documents
    layers         derived layers, each its own table and version; never fields of a token
    compatibility  aliases for old studies; never canonical values

A field that can lack a value is *stateful*: it comes with ``<field>_state``, and the value is
null exactly when the state is not ``known``. There is no bare null.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from . import naming
from .canonical import canonical_json, is_sha256, line_json, record_json, sha256_bytes

NAMESPACE = "crosscorpus"
CONTRACT = naming.schema_id("analysis", 1, NAMESPACE)
TOKEN_DENOMINATOR = naming.schema_id("token-denominator", 1, NAMESPACE)
COMPATIBILITY_VIEW = naming.schema_id("legacy-studies-view", 1, NAMESPACE)

# --- value states -------------------------------------------------------------------------------------

KNOWN, UNKNOWN, NOT_APPLICABLE, UNDECIDED, NOT_AVAILABLE = "known", "unknown", "not_applicable", "undecided", "not_available"
VALUE_STATES = {
    KNOWN: "a value is given",
    UNKNOWN: "the field applies; the source was consulted or the determination attempted, and no defensible value exists",
    NOT_APPLICABLE: "the field has no value for this row by the nature of the row",
    UNDECIDED: "the field applies; the value needs a human or scientific decision that has not been made",
    NOT_AVAILABLE: "the field applies; the stage that would produce the value has not delivered one",
}

# --- shared closed vocabularies -----------------------------------------------------------------------

MODALITIES = ("spoken", "written")
# The shared production dimension. The three spoken values are CO.RA.PAN's `speech_mode` values
# unchanged; `written_edited` is the one press value. Nothing maps a spoken value onto a written one.
PRODUCTION_MODES = {"unscripted": "spoken", "scripted": "spoken", "prerecorded": "spoken", "written_edited": "written"}
RELEASE_KINDS = ("release", "provisional_export", "fixture")
SURFACES = ("primary", "title", "auxiliary")
# Every unit kind states what kind of boundary made it. None of them is an utterance.
UNIT_KINDS = {
    "title": "editorial", "heading": "editorial", "paragraph": "editorial", "list_item": "editorial",
    "quote_block": "editorial", "caption": "editorial", "unstructured_text": "editorial",
    "turn": "technical", "contribution_unit": "technical",
}
SEGMENTATION_NATURES = ("editorial", "technical")
SCOPE_STATUSES = ("in_scope", "out_of_scope", "undecided")
TOKEN_KINDS = ("word", "punctuation")  # parser tokens only: what an instrument masks before parsing is no token here
UPOS = ("ADJ", "ADP", "ADV", "AUX", "CCONJ", "DET", "INTJ", "NOUN", "NUM", "PART", "PRON", "PROPN", "PUNCT",
        "SCONJ", "SYM", "VERB", "X")  # UD; SPACE is not a token of this contract
RELATIONS = ("duplicate_of", "syndicated_copy_of", "earlier_version_of")
LAYER_LEVELS = ("document", "unit", "sentence", "token")
VALIDATION_STATUSES = ("NOT_VALIDATED", "VALIDATED")
# Project labels that the legacy corpora wrote into `morph`. They are layer values, never features.
PROJECT_MORPH_FEATURES = ("PastType", "TenseRole", "FutureType", "VoiceType", "VerbLemma", "TranscriptSpecial")
# Names that belong to the compatibility view and may never appear in a canonical table.
COMPATIBILITY_ALIASES = ("register_group", "country_code_alpha3", "legacy_outlet_slug", "legacy_article_id",
                         "legacy_file_id", "legacy_standard_section", "legacy_speaker_code")
REGISTER_GROUPS = {("spoken", "unscripted"): "corapan_libre", ("spoken", "scripted"): "corapan_lectura",
                   ("written", "written_edited"): "coprepan_written"}

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_COHORT = re.compile(r"\d{4}-Q[1-4]")
_LAYER_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+/v[1-9]\d*")  # each corpus's own layer ids, as they are
_FEATURE = re.compile(r"[A-Z][A-Za-z0-9]*(?:\[[a-z]+\])?")
TABLES = ("outlets", "documents", "units", "sentences", "tokens", "relations")


class ContractViolation(ValueError):
    """A bundle does not conform; ``violations`` lists every objection."""

    def __init__(self, violations: Sequence[str]) -> None:
        super().__init__(f"{len(violations)} contract violation(s): " + "; ".join(violations[:5]))
        self.violations = list(violations)


# --- field types --------------------------------------------------------------------------------------


def _text(value: Any) -> bool:
    return isinstance(value, str) and value != "" and value == value.strip()


def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _boolean(value: Any) -> bool:
    return isinstance(value, bool)


def _one_of(values: Iterable[str]) -> Callable[[Any], bool]:
    allowed = frozenset(values)
    return lambda value: isinstance(value, str) and value in allowed


def _matches(pattern: re.Pattern) -> Callable[[Any], bool]:
    return lambda value: isinstance(value, str) and pattern.fullmatch(value) is not None


def _share(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1


DECLARED = "declared"  # the closed vocabulary is declared by the release (corpus-specific, still closed)

# table → (plain fields, stateful fields). A row has exactly these fields, plus `<field>_state` for
# every stateful one. A checker of DECLARED is looked up in `release.vocabularies[<field>]`.
SCHEMA: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
    "outlets": (
        {"outlet_id": naming.is_outlet_id, "corpus_id": _one_of(naming.CORPUS_IDS), "country_id": naming.is_country_id,
         "display_name": _text},
        {"outlet_kind": DECLARED, "city": _text, "region": _text, "scope": _text, "outlet_group": _text},
    ),
    "documents": (
        {"document_id": _text, "corpus_id": _one_of(naming.CORPUS_IDS), "release_id": _text, "outlet_id": naming.is_outlet_id,
         "country_id": naming.is_country_id, "modality": _one_of(MODALITIES), "provenance_class": DECLARED,
         "tokens_total": _integer, "tokens_counted": _integer},
        {"editorial_id": _text, "region": _text, "production_mode": _one_of(PRODUCTION_MODES), "date": _matches(_DATE),
         "date_basis": DECLARED, "cohort": _matches(_COHORT), "section_published": _text, "section_mapped": DECLARED,
         "programme": _text, "language": _text, "language_basis": DECLARED},
    ),
    "units": (
        {"unit_id": _text, "document_id": _text, "unit_kind": _one_of(UNIT_KINDS), "segmentation_nature": _one_of(SEGMENTATION_NATURES),
         "surface": _one_of(SURFACES), "order_index": _integer, "scope_status": _one_of(SCOPE_STATUSES), "tokens_counted": _integer},
        {"parent_unit_id": _text, "production_mode": _one_of(PRODUCTION_MODES), "production_mode_share": _share,
         "producer_id": _text, "producer_role": DECLARED, "scope_reason": DECLARED},
    ),
    "sentences": (
        {"sentence_id": _text, "unit_id": _text, "document_id": _text, "surface": _one_of(SURFACES), "order_index": _integer},
        {"previous_sentence_id": _text, "next_sentence_id": _text, "char_start": _integer, "char_end": _integer,
         "start_ms": _integer, "end_ms": _integer},
    ),
    "tokens": (
        {"token_id": _text, "sentence_id": _text, "unit_id": _text, "document_id": _text, "order_index": _integer,
         "form": lambda value: isinstance(value, str) and value != "", "lemma": lambda value: isinstance(value, str) and value != "",
         "upos": _one_of(UPOS), "morph": lambda value: isinstance(value, dict), "deprel": _text,
         "token_kind": _one_of(TOKEN_KINDS), "production_event_types": lambda value: isinstance(value, list), "counted": _boolean},
        {"xpos": _text, "head_token_id": _text, "char_start": _integer, "char_end": _integer, "start_ms": _integer, "end_ms": _integer},
    ),
    "relations": (
        {"relation": _one_of(RELATIONS), "document_id": _text, "target_document_id": _text, "target_in_release": _boolean, "basis": _text},
        {},
    ),
}
LAYER_ROW = ({"target_id": _text}, {"value": lambda value: value is not None})
COMPATIBILITY_ROW = {"view_id": _one_of((COMPATIBILITY_VIEW,)), "target_level": _one_of(("outlet", "document", "unit")),
                     "target_id": _text, "alias": _one_of(COMPATIBILITY_ALIASES), "value": _text}
# Which states a stateful field may take; fields not listed may take any.
STATES_ALLOWED = {
    ("tokens", "head_token_id"): (KNOWN, NOT_APPLICABLE),            # the root has no head
    ("sentences", "previous_sentence_id"): (KNOWN, NOT_APPLICABLE),  # the first of its document and surface
    ("sentences", "next_sentence_id"): (KNOWN, NOT_APPLICABLE),
    ("units", "parent_unit_id"): (KNOWN, NOT_APPLICABLE),
}


def counts_in_denominator(token: Mapping[str, Any], unit: Mapping[str, Any]) -> bool:
    """``crosscorpus-token-denominator/v1``: a token counts when it is a word — a parser token
    that is not punctuation — on the primary surface of a unit that is in scope. Whitespace and
    what an instrument masks before parsing (filled pauses, non-speech events) are never tokens.

    Numerals, symbols and the words of repetitions and repairs count. That last clause is a
    declared modality caveat, not an oversight: see the comparability matrix.
    """
    return token["token_kind"] == "word" and unit["surface"] == "primary" and unit["scope_status"] == "in_scope"


# --- hashing ------------------------------------------------------------------------------------------


def table_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    """The canonical bytes of a table: one sorted-key JSON object per line, in the given order."""
    return b"".join(line_json(dict(row)) for row in rows)


def _digest(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"rows": len(rows), "sha256": sha256_bytes(table_bytes(rows))}


def seal(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Return the bundle with its release record bound to the tables: per-table hashes, then the
    manifest hash over the release record. A study pins ``release_id`` and ``manifest_sha256``.
    """
    release = {key: value for key, value in bundle["release"].items() if key != "manifest_sha256"}
    release["tables"] = {name: _digest(bundle["tables"].get(name, [])) for name in TABLES}
    release["layers"] = {layer_id: {**{k: v for k, v in declaration.items() if k not in ("rows", "sha256")},
                                    **_digest(bundle.get("layers", {}).get(layer_id, []))}
                         for layer_id, declaration in sorted(release.get("layers", {}).items())}
    release["compatibility"] = {"view_id": COMPATIBILITY_VIEW, **_digest(bundle.get("compatibility", []))}
    release["manifest_sha256"] = sha256_bytes(canonical_json(release))
    return {**bundle, "release": release}


# --- validation ---------------------------------------------------------------------------------------


def validate(bundle: Mapping[str, Any]) -> list[str]:
    """Every objection to a bundle; empty when it conforms. Reads only; never repairs."""
    out: list[str] = []
    release = bundle.get("release")
    if not isinstance(release, dict):
        return ["release: missing"]
    tables = {name: list(bundle.get("tables", {}).get(name, [])) for name in TABLES}
    layers = {key: list(rows) for key, rows in bundle.get("layers", {}).items()}
    compatibility = list(bundle.get("compatibility", []))
    out += _check_release(release, tables, layers, compatibility)
    vocabularies = release.get("vocabularies") if isinstance(release.get("vocabularies"), dict) else {}

    for name in TABLES:
        plain, stateful = SCHEMA[name]
        for number, row in enumerate(tables[name]):
            out += _check_row(f"{name}[{number}]", row, plain, stateful, vocabularies, name)
    if out:
        return out  # structural objections first: the relational checks below assume well-formed rows

    out += _check_ids(tables)
    outlets = {row["outlet_id"]: row for row in tables["outlets"]}
    documents = {row["document_id"]: row for row in tables["documents"]}
    units = {row["unit_id"]: row for row in tables["units"]}
    sentences = {row["sentence_id"]: row for row in tables["sentences"]}
    tokens = {row["token_id"]: row for row in tables["tokens"]}

    for document in tables["documents"]:
        where = f"document {document['document_id']}"
        outlet = outlets.get(document["outlet_id"])
        if outlet is None:
            out.append(f"{where}: outlet {document['outlet_id']} is not in outlets")
        elif outlet["country_id"] != document["country_id"]:
            out.append(f"{where}: country_id differs from its outlet's")
        if (document["corpus_id"], document["release_id"], document["modality"]) != (release["corpus_id"], release["release_id"], release["modality"]):
            out.append(f"{where}: corpus_id, release_id or modality differs from the release")
        out += _check_mode(where, document, document["modality"])
        if document["date_state"] == KNOWN and document["cohort_state"] == KNOWN:
            month = int(document["date"][5:7])
            if document["cohort"] != f"{document['date'][:4]}-Q{(month - 1) // 3 + 1}":
                out.append(f"{where}: cohort does not contain its date")
        if (document["date_state"] == KNOWN) != (document["date_basis_state"] == KNOWN):
            out.append(f"{where}: a date and its basis are known together or not at all")

    by_document = defaultdict(list)
    for unit in tables["units"]:
        where = f"unit {unit['unit_id']}"
        document = documents.get(unit["document_id"])
        if document is None:
            out.append(f"{where}: document {unit['document_id']} is not in documents")
            continue
        by_document[unit["document_id"]].append(unit)
        if unit["segmentation_nature"] != UNIT_KINDS[unit["unit_kind"]]:
            out.append(f"{where}: a {unit['unit_kind']} is {UNIT_KINDS[unit['unit_kind']]} segmentation, not {unit['segmentation_nature']}")
        out += _check_mode(where, unit, document["modality"])
        if (unit["scope_status"] == "out_of_scope") != (unit["scope_reason_state"] == KNOWN):
            out.append(f"{where}: exactly an out-of-scope unit states its reason")
        if unit["parent_unit_id_state"] == KNOWN:
            parent = units.get(unit["parent_unit_id"])
            if parent is None or parent["document_id"] != unit["document_id"] or parent is unit:
                out.append(f"{where}: parent unit is missing, is itself, or belongs to another document")
    for document_id, rows in by_document.items():
        out += _check_order(f"units of {document_id}", rows)

    chains = defaultdict(list)
    for sentence in tables["sentences"]:
        where = f"sentence {sentence['sentence_id']}"
        unit = units.get(sentence["unit_id"])
        if unit is None or unit["document_id"] != sentence["document_id"] or unit["surface"] != sentence["surface"]:
            out.append(f"{where}: unit is missing, or its document or surface differs")
            continue
        chains[(sentence["document_id"], sentence["surface"])].append(sentence)
        out += _check_anchors(where, sentence, documents[sentence["document_id"]]["modality"], word=True)
    for (document_id, surface), rows in chains.items():
        rows.sort(key=lambda row: row["order_index"])
        out += _check_order(f"sentences of {document_id} ({surface})", rows)
        for position, sentence in enumerate(rows):
            expected = (rows[position - 1]["sentence_id"] if position else None,
                        rows[position + 1]["sentence_id"] if position + 1 < len(rows) else None)
            if (sentence["previous_sentence_id"], sentence["next_sentence_id"]) != expected:
                out.append(f"sentence {sentence['sentence_id']}: neighbours do not follow the order of its document and surface")

    in_sentence = defaultdict(list)
    counted_by_unit: Counter[str] = Counter()
    total_by_document: Counter[str] = Counter()
    inventory = frozenset(release["annotator_contract"]["morph_features"])
    for token in tables["tokens"]:
        where = f"token {token['token_id']}"
        sentence = sentences.get(token["sentence_id"])
        if sentence is None or (sentence["unit_id"], sentence["document_id"]) != (token["unit_id"], token["document_id"]):
            out.append(f"{where}: sentence is missing, or its unit or document differs")
            continue
        unit = units[token["unit_id"]]
        in_sentence[token["sentence_id"]].append(token)
        total_by_document[token["document_id"]] += 1
        if (token["upos"] == "PUNCT") != (token["token_kind"] == "punctuation"):
            out.append(f"{where}: upos PUNCT and token_kind punctuation go together")
        if set(token["production_event_types"]) & set(release["annotator_contract"]["masked_event_types"]):
            out.append(f"{where}: carries a production event the instrument masks before parsing; such material is not a token")
        if token["production_event_types"] and documents[token["document_id"]]["modality"] == "written":
            out.append(f"{where}: a written token has no production event")
        if token["counted"] != counts_in_denominator(token, unit):
            out.append(f"{where}: counted does not follow {TOKEN_DENOMINATOR}")
        counted_by_unit[token["unit_id"]] += token["counted"]
        for feature, value in token["morph"].items():
            if feature in PROJECT_MORPH_FEATURES:
                out.append(f"{where}: {feature} is a project label and belongs in a layer, not in morph")
            elif feature not in inventory or not _FEATURE.fullmatch(feature) or not _text(value):
                out.append(f"{where}: morph feature {feature!r} is not in the declared inventory, or has no value")
        if token["head_token_id_state"] == KNOWN:
            head = tokens.get(token["head_token_id"])
            if head is None or head["sentence_id"] != token["sentence_id"] or head is token:
                out.append(f"{where}: head is missing, is itself, or lies in another sentence")
        out += _check_anchors(where, token, documents[token["document_id"]]["modality"], word=token["token_kind"] == "word")
    for sentence_id, rows in in_sentence.items():
        out += _check_order(f"tokens of {sentence_id}", rows)
        if sum(1 for token in rows if token["head_token_id_state"] == NOT_APPLICABLE) != 1:
            out.append(f"sentence {sentence_id}: exactly one token is the root")
    for sentence in tables["sentences"]:
        if sentence["sentence_id"] not in in_sentence:
            out.append(f"sentence {sentence['sentence_id']}: has no token")

    for unit in tables["units"]:
        if unit["tokens_counted"] != counted_by_unit[unit["unit_id"]]:
            out.append(f"unit {unit['unit_id']}: tokens_counted is {unit['tokens_counted']}, its tokens give {counted_by_unit[unit['unit_id']]}")
    for document in tables["documents"]:
        counted = sum(counted_by_unit[unit["unit_id"]] for unit in by_document[document["document_id"]])
        if (document["tokens_counted"], document["tokens_total"]) != (counted, total_by_document[document["document_id"]]):
            out.append(f"document {document['document_id']}: token counts do not equal the sums over its tokens")

    seen = set()
    for relation in tables["relations"]:
        where = f"relation {relation['relation']} {relation['document_id']} → {relation['target_document_id']}"
        key = (relation["relation"], relation["document_id"], relation["target_document_id"])
        if relation["document_id"] not in documents or relation["document_id"] == relation["target_document_id"] or key in seen:
            out.append(f"{where}: its document is not in the release, it points at itself, or it is stated twice")
        if relation["target_in_release"] != (relation["target_document_id"] in documents):
            out.append(f"{where}: target_in_release does not say whether the target is in documents")
        seen.add(key)

    targets = {"document": documents, "unit": units, "sentence": sentences, "token": tokens}
    for layer_id, rows in layers.items():
        declaration = release["layers"].get(layer_id)
        if declaration is None:
            out.append(f"layer {layer_id}: not declared by the release")
            continue
        keys = set()
        for number, row in enumerate(rows):
            where = f"layer {layer_id}[{number}]"
            problems = _check_row(where, row, {**LAYER_ROW[0], **{name: _text for name in declaration.get("attributes", [])}},
                                  {"value": _one_of(declaration["values"])}, {}, "layer")
            out += problems
            if problems:
                continue
            if row["target_id"] not in targets[declaration["target_level"]] or row["target_id"] in keys:
                out.append(f"{where}: target is not a {declaration['target_level']} of the bundle, or is labelled twice")
            keys.add(row["target_id"])

    known = {"outlet": outlets, "document": documents, "unit": units}
    for number, row in enumerate(compatibility):
        where = f"compatibility[{number}]"
        if not isinstance(row, dict) or set(row) != set(COMPATIBILITY_ROW) or not all(check(row[name]) for name, check in COMPATIBILITY_ROW.items()):
            out.append(f"{where}: not a compatibility row (view, level, target, alias, value)")
        elif row["target_id"] not in known[row["target_level"]]:
            out.append(f"{where}: target is not in the bundle")
    return out


def require_valid(bundle: Mapping[str, Any]) -> None:
    violations = validate(bundle)
    if violations:
        raise ContractViolation(violations)


def _check_release(release: Mapping[str, Any], tables, layers, compatibility) -> list[str]:
    out = []
    required = ("contract", "corpus_id", "release_id", "release_kind", "fixture", "modality", "created_at", "annotator_contract",
                "token_denominator", "anchors", "vocabularies", "selection_policy", "coverage_reference", "id_stability",
                "layers", "tables", "compatibility", "manifest_sha256")
    missing = [name for name in required if name not in release]
    if missing:
        return [f"release: missing {', '.join(missing)}"]
    if release["contract"] != CONTRACT or release["token_denominator"] != TOKEN_DENOMINATOR:
        out.append(f"release: contract is not {CONTRACT}, or the token denominator is not {TOKEN_DENOMINATOR}")
    if release["corpus_id"] not in naming.CORPUS_IDS or not str(release["release_id"]).startswith(f"{release['corpus_id']}-"):
        out.append("release: unknown corpus_id, or a release_id that does not begin with it")
    if release["release_kind"] not in RELEASE_KINDS or release["modality"] not in MODALITIES:
        out.append("release: release_kind or modality is not in the vocabulary")
    if (release["release_kind"] == "fixture") != (release["fixture"] is True):
        out.append("release: a fixture is marked as one in both places, and nothing else is")
    annotator = release["annotator_contract"]
    wanted = ("annotator_id", "pins", "chain_version", "sentence_boundary_policy", "morph_features", "masked_event_types")
    if not isinstance(annotator, dict) or any(name not in annotator for name in wanted) or not isinstance(annotator.get("pins"), dict) or not annotator["pins"]:
        return out + ["release: annotator_contract needs " + ", ".join(wanted) + ", with at least one pin"]
    for name in ("selection_policy", "coverage_reference"):
        value = release[name]
        if not isinstance(value, dict) or value.get("state") not in VALUE_STATES or \
                (value["state"] == KNOWN) != (_text(value.get("id")) and is_sha256(value.get("sha256"))):
            out.append(f"release: {name} is pinned by id and sha256, or carries a state saying why not")
    if release["release_kind"] == "release" and release["selection_policy"].get("state") != KNOWN:
        out.append("release: a release (not a provisional export) pins its selection policy")
    if not isinstance(release["vocabularies"], dict) or any(not isinstance(v, list) or not all(_text(x) for x in v) for v in release["vocabularies"].values()):
        out.append("release: vocabularies are lists of values")
    for layer_id, declaration in release["layers"].items():
        if not _LAYER_ID.fullmatch(layer_id) or declaration.get("target_level") not in LAYER_LEVELS \
                or declaration.get("validation_status") not in VALIDATION_STATUSES or not _text(declaration.get("rule_version")) \
                or not isinstance(declaration.get("values"), list):
            out.append(f"release: layer {layer_id} needs a schema id, target_level, validation_status, rule_version and values")
        if release["release_kind"] == "release" and declaration.get("validation_status") != "VALIDATED":
            out.append(f"release: layer {layer_id} is not validated and cannot be part of a release")
    expected = {"tables": {name: _digest(tables[name]) for name in TABLES},
                "compatibility": {"view_id": COMPATIBILITY_VIEW, **_digest(compatibility)}}
    if release["tables"] != expected["tables"] or release["compatibility"] != expected["compatibility"]:
        out.append("release: a table or the compatibility view does not have the size and sha256 the release pins")
    for layer_id, declaration in release["layers"].items():
        if {key: declaration.get(key) for key in ("rows", "sha256")} != _digest(layers.get(layer_id, [])):
            out.append(f"release: layer {layer_id} does not have the size and sha256 the release pins")
    body = {key: value for key, value in release.items() if key != "manifest_sha256"}
    if not is_sha256(release["manifest_sha256"]) or release["manifest_sha256"] != sha256_bytes(canonical_json(body)):
        out.append("release: manifest_sha256 is not the sha256 of the release record")
    return out


def _check_row(where, row, plain, stateful, vocabularies, table) -> list[str]:
    if not isinstance(row, dict):
        return [f"{where}: not an object"]
    out = []
    expected = set(plain) | set(stateful) | {f"{name}_state" for name in stateful}
    extra, missing = sorted(set(row) - expected), sorted(expected - set(row))
    for name in extra:
        note = " (a compatibility alias: it belongs in the compatibility view)" if name in COMPATIBILITY_ALIASES else ""
        out.append(f"{where}: unknown field {name}{note}")
    if missing:
        out.append(f"{where}: missing {', '.join(missing)}")
    if extra or missing:
        return out

    def ok(name: str, check: Any, value: Any) -> bool:
        if check is DECLARED:
            return isinstance(value, str) and value in vocabularies.get(name, ())
        return bool(check(value))

    for name, check in plain.items():
        if row[name] is None or not ok(name, check, row[name]):
            out.append(f"{where}: {name}={row[name]!r} is not a valid value")
    for name, check in stateful.items():
        state, value = row[f"{name}_state"], row[name]
        if state not in VALUE_STATES or state not in STATES_ALLOWED.get((table, name), tuple(VALUE_STATES)):
            out.append(f"{where}: {name}_state={state!r} is not an allowed value state")
        elif (state == KNOWN) != (value is not None):
            out.append(f"{where}: {name} is null exactly when its state is not 'known' (state {state}, value {value!r})")
        elif state == KNOWN and not ok(name, check, value):
            out.append(f"{where}: {name}={value!r} is not a valid value")
    return out


def _check_ids(tables) -> list[str]:
    out, seen = [], {}
    for name, key in (("outlets", "outlet_id"), ("documents", "document_id"), ("units", "unit_id"),
                      ("sentences", "sentence_id"), ("tokens", "token_id")):
        for row in tables[name]:
            if row[key] in seen:
                out.append(f"{name}: id {row[key]} is used twice (also in {seen[row[key]]})")
            seen[row[key]] = name
    return out


def _check_order(where: str, rows: Sequence[Mapping[str, Any]]) -> list[str]:
    if sorted(row["order_index"] for row in rows) != list(range(len(rows))):
        return [f"{where}: order_index is not 0 … n-1 without gap or repetition"]
    return []


def _check_mode(where: str, row: Mapping[str, Any], modality: str) -> list[str]:
    if row["production_mode_state"] == KNOWN and PRODUCTION_MODES[row["production_mode"]] != modality:
        return [f"{where}: production_mode {row['production_mode']} does not occur in the {modality} modality"]
    return []


def _check_anchors(where: str, row: Mapping[str, Any], modality: str, *, word: bool) -> list[str]:
    """Medium-typed anchors. Character offsets are known for every row of either modality (each
    instrument parses a text). Time exists for speech only: a written row says ``not_applicable``,
    and so does a spoken punctuation token, which was never uttered.
    """
    out = []
    for first, second in (("char_start", "char_end"), ("start_ms", "end_ms")):
        if row[f"{first}_state"] != row[f"{second}_state"]:
            out.append(f"{where}: {first} and {second} share one state")
        elif row[f"{first}_state"] == KNOWN and not row[first] <= row[second]:
            out.append(f"{where}: {first} lies after {second}")
    if row["char_start_state"] != KNOWN:
        out.append(f"{where}: character anchors are known in both modalities")
    time = row["start_ms_state"]
    if modality == "written" and time != NOT_APPLICABLE:
        out.append(f"{where}: a written row has no time anchor (state not_applicable)")
    if modality == "spoken" and word and time not in (KNOWN, UNKNOWN, NOT_AVAILABLE):
        out.append(f"{where}: a spoken word has a time anchor, or says that it is unknown or not available")
    if modality == "spoken" and not word and time not in (KNOWN, NOT_APPLICABLE):
        out.append(f"{where}: spoken punctuation has no time anchor of its own")
    return out


def check_disjoint(bundles: Sequence[Mapping[str, Any]]) -> list[str]:
    """Ids are unique across the corpora that are analysed together, not only inside one bundle."""
    out, seen = [], {}
    for bundle in bundles:
        corpus = bundle["release"]["corpus_id"]
        for name, key in (("outlets", "outlet_id"), ("documents", "document_id"), ("units", "unit_id"),
                          ("sentences", "sentence_id"), ("tokens", "token_id")):
            for row in bundle["tables"][name]:
                if seen.setdefault(row[key], corpus) != corpus:
                    out.append(f"id {row[key]} exists in {seen[row[key]]} and in {corpus}")
    return out


# --- storage ------------------------------------------------------------------------------------------


def write_bundle(bundle: Mapping[str, Any], directory: Path) -> None:
    """Write a conformant bundle to a new directory. A non-conformant one is refused, not written."""
    require_valid(bundle)
    directory = Path(directory)
    (directory / "layers").mkdir(parents=True, exist_ok=False)
    (directory / "release.json").write_bytes(record_json(dict(bundle["release"])))
    for name in TABLES:
        (directory / f"{name}.jsonl").write_bytes(table_bytes(bundle["tables"].get(name, [])))
    for layer_id, rows in bundle.get("layers", {}).items():
        (directory / "layers" / (layer_id.replace("/", "@") + ".jsonl")).write_bytes(table_bytes(rows))
    (directory / "compatibility.jsonl").write_bytes(table_bytes(bundle.get("compatibility", [])))


def read_bundle(directory: Path) -> dict[str, Any]:
    """Read a bundle and refuse it unless it conforms and its hashes hold."""
    directory = Path(directory)

    def rows(path: Path) -> list[dict[str, Any]]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    release = json.loads((directory / "release.json").read_text(encoding="utf-8"))
    bundle = {"release": release, "tables": {name: rows(directory / f"{name}.jsonl") for name in TABLES},
              "layers": {layer_id: rows(directory / "layers" / (layer_id.replace("/", "@") + ".jsonl")) for layer_id in release.get("layers", {})},
              "compatibility": rows(directory / "compatibility.jsonl")}
    require_valid(bundle)
    return bundle


# --- compatibility view -------------------------------------------------------------------------------


def legacy_studies_view(bundle: Mapping[str, Any], *, country_alpha3: Mapping[str, str],
                        legacy_outlet_slugs: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    """Aliases the finished studies know, derived from canonical values. Never read by a stage.

    ``register_group`` is derived from modality and production mode alone. The legacy studies also
    restricted it by speaker type and section; those conditions are selections, not part of the
    alias, and a unit without a matching pair simply gets no alias row.
    """
    def row(level: str, target: str, alias: str, value: str) -> dict[str, Any]:
        return {"view_id": COMPATIBILITY_VIEW, "target_level": level, "target_id": target, "alias": alias, "value": value}

    out = []
    for outlet in bundle["tables"]["outlets"]:
        if outlet["country_id"] in country_alpha3:
            out.append(row("outlet", outlet["outlet_id"], "country_code_alpha3", country_alpha3[outlet["country_id"]]))
        if legacy_outlet_slugs and outlet["outlet_id"] in legacy_outlet_slugs:
            out.append(row("outlet", outlet["outlet_id"], "legacy_outlet_slug", legacy_outlet_slugs[outlet["outlet_id"]]))
    modality = bundle["release"]["modality"]
    for unit in bundle["tables"]["units"]:
        group = REGISTER_GROUPS.get((modality, unit["production_mode"])) if unit["production_mode_state"] == KNOWN else None
        if group and unit["surface"] == "primary":
            out.append(row("unit", unit["unit_id"], "register_group", group))
    return out


# --- queries (demonstrations of the contract, not analyses) -------------------------------------------


def _index(bundle: Mapping[str, Any], table: str, key: str) -> dict[str, dict[str, Any]]:
    return {row[key]: row for row in bundle["tables"][table]}


def counted_tokens_by(bundles: Sequence[Mapping[str, Any]], *fields: str) -> dict[tuple, int]:
    """Counted tokens grouped by fields of the unit or its document (``country_id``,
    ``modality``, ``production_mode`` …). A stateful field that is not known groups under its state.
    """
    out: Counter[tuple] = Counter()
    for bundle in bundles:
        documents = _index(bundle, "documents", "document_id")
        for unit in bundle["tables"]["units"]:
            document = documents[unit["document_id"]]
            key = []
            for field in fields:
                row = unit if field in unit else document
                key.append(row[field] if row.get(f"{field}_state", KNOWN) == KNOWN else f"<{row[f'{field}_state']}>")
            out[tuple(key)] += unit["tokens_counted"]
    return {key: count for key, count in sorted(out.items()) if count}


def morph_value_counts(bundles: Sequence[Mapping[str, Any]], feature: str, *, upos: Sequence[str] = ("VERB", "AUX")) -> dict[tuple, int]:
    """Counted tokens by modality and the value of one morphological feature."""
    out: Counter[tuple] = Counter()
    for bundle in bundles:
        for token in bundle["tables"]["tokens"]:
            if token["counted"] and token["upos"] in upos and feature in token["morph"]:
                out[(bundle["release"]["modality"], token["morph"][feature])] += 1
    return dict(sorted(out.items()))


def row_counts(bundles: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    return {bundle["release"]["corpus_id"]: {name: len(bundle["tables"][name]) for name in TABLES} for bundle in bundles}


def sentence_context(bundle: Mapping[str, Any], sentence_id: str) -> dict[str, Any]:
    """A sentence with its neighbours, by id — no rescanning of a corpus."""
    sentences = _index(bundle, "sentences", "sentence_id")
    by_sentence = defaultdict(list)
    for token in bundle["tables"]["tokens"]:
        by_sentence[token["sentence_id"]].append(token)

    def text(identifier: str | None) -> str | None:
        if identifier is None:
            return None
        return " ".join(token["form"] for token in sorted(by_sentence[identifier], key=lambda token: token["order_index"]))

    sentence = sentences[sentence_id]
    return {"previous": text(sentence["previous_sentence_id"]), "sentence": text(sentence_id), "next": text(sentence["next_sentence_id"]),
            "same_unit_as_previous": sentence["previous_sentence_id"] is not None
            and sentences[sentence["previous_sentence_id"]]["unit_id"] == sentence["unit_id"]}
