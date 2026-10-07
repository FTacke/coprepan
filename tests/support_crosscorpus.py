"""Test support: two small, fully synthetic bundles of ``crosscorpus-analysis/v1``.

**Everything here is a fixture.** No sentence was produced by a parser, no page was fetched, no
recording exists. The annotations are written by hand so that the tests are about the contract —
ids, parents, states, anchors, counts — and say nothing about any instrument's quality.

* The press bundle goes through COPREPAN's real code path as far as one exists: an invented HTML
  page → the baseline extractor → real document, version, unit, sentence and token ids → the
  adapter ``coprepan.analysis_export``.
* The radio bundle is modelled on the semantics **observed read-only** in CO.RA.PAN 3.0 on
  2026-10-07 (commit ``3a6972ff``): recording, technical turns with content-addressed ids,
  contribution units, ``speech_mode`` projected on turns with an overlap share, analysis tokens
  with a 1-based ``idx``, ``head_idx`` 0 for the root, ``pos`` / ``tag``, ``morph`` as a dict, time
  on the lexical layer. ``corapan_bundle`` is a sketch of the adapter CO.RA.PAN would need; it is
  not CO.RA.PAN code and no CO.RA.PAN export produces these tables today.
"""

from __future__ import annotations

import copy
import hashlib

from coprepan import analysis_contract as A
from coprepan import analysis_export as X
from coprepan import extraction, identity
from test_canary import outlet

CREATED = "2026-10-07T22:00:00.000000Z"
PINS = {"spacy": "3.8.15", "model": "es_dep_news_trf", "model_version": "3.8.0"}
MORPH = ["Definite", "Gender", "Mood", "Number", "NumType", "Person", "PronType", "Tense", "VerbForm"]
VERBAL_COMPLEX = "corapan3-verbal-complex/v2"
PROFI = "corapan-professional-status/v1"
NOT_PINNED = {"state": A.NOT_AVAILABLE, "id": None, "sha256": None}


def annotator(sentence_policy: str, masked: list[str]) -> dict:
    return {"annotator_id": "corapan-spacy-annotator/v2", "pins": dict(PINS), "chain_version": "fixture-chain/0",
            "sentence_boundary_policy": sentence_policy, "morph_features": list(MORPH), "masked_event_types": masked}


def parse(spec: str) -> list[dict]:
    """``form|lemma|UPOS|head|deprel|Feat=Val,…`` per line; ``head`` is 1-based, 0 for the root."""
    out = []
    for line in spec.strip().splitlines():
        form, lemma, upos, head, deprel, *features = [part.strip() for part in line.split("|")]
        morph = dict(pair.split("=") for pair in features[0].split(",")) if features and features[0] else {}
        out.append({"form": form, "lemma": lemma, "upos": upos, "head": int(head), "deprel": deprel, "morph": morph})
    return out


# --- press ------------------------------------------------------------------------------------------

PAGE = """<!doctype html><html lang="es"><head><title>El puerto crece | Diario Ejemplo</title>
<meta property="article:section" content="Economía"></head><body><article>
<h1>El puerto crece</h1>
<p>El puerto creció un doce por ciento. La carga ha aumentado.</p>
<figure><figcaption>Foto: archivo</figcaption></figure>
<p>Los vecinos esperan obras.</p>
</article></body></html>""".encode("utf-8")
COPY = "<html><body><article><p>El puerto crecerá.</p></article></body></html>".encode("utf-8")

TITLE = parse("""
El|el|DET|2|det|Definite=Def,Gender=Masc,Number=Sing,PronType=Art
puerto|puerto|NOUN|3|nsubj|Gender=Masc,Number=Sing
crece|crecer|VERB|0|ROOT|Mood=Ind,Number=Sing,Person=3,Tense=Pres,VerbForm=Fin
""")
S1 = parse("""
El|el|DET|2|det|Definite=Def,Gender=Masc,Number=Sing,PronType=Art
puerto|puerto|NOUN|3|nsubj|Gender=Masc,Number=Sing
creció|crecer|VERB|0|ROOT|Mood=Ind,Number=Sing,Person=3,Tense=Past,VerbForm=Fin
un|uno|DET|7|det|Definite=Ind,Gender=Masc,Number=Sing,PronType=Art
doce|doce|NUM|7|nummod|NumType=Card
por|por|ADP|7|case|
ciento|ciento|NOUN|3|obj|Gender=Masc,Number=Sing
.|.|PUNCT|3|punct|
""")
S2 = parse("""
La|el|DET|2|det|Definite=Def,Gender=Fem,Number=Sing,PronType=Art
carga|carga|NOUN|4|nsubj|Gender=Fem,Number=Sing
ha|haber|AUX|4|aux|Mood=Ind,Number=Sing,Person=3,Tense=Pres,VerbForm=Fin
aumentado|aumentar|VERB|0|ROOT|Gender=Masc,Number=Sing,Tense=Past,VerbForm=Part
.|.|PUNCT|4|punct|
""")
S3 = parse("""
Los|el|DET|2|det|Definite=Def,Gender=Masc,Number=Plur,PronType=Art
vecinos|vecino|NOUN|3|nsubj|Gender=Masc,Number=Plur
esperan|esperar|VERB|0|ROOT|Mood=Ind,Number=Plur,Person=3,Tense=Pres,VerbForm=Fin
obras|obra|NOUN|3|obj|Gender=Fem,Number=Plur
.|.|PUNCT|3|punct|
""")
S4 = parse("""
El|el|DET|2|det|Definite=Def,Gender=Masc,Number=Sing,PronType=Art
puerto|puerto|NOUN|3|nsubj|Gender=Masc,Number=Sing
crecerá|crecer|VERB|0|ROOT|Mood=Ind,Number=Sing,Person=3,Tense=Fut,VerbForm=Fin
.|.|PUNCT|3|punct|
""")


def anchored(text: str, sentences: list[list[dict]]) -> list[list[dict]]:
    """Give hand-written tokens the offsets of their forms in a unit's text, left to right."""
    out, cursor = [], 0
    for sentence in sentences:
        rows = []
        for token in sentence:
            start = text.index(token["form"], cursor)
            cursor = start + len(token["form"])
            rows.append({**token, "head": token["head"] - 1 if token["head"] else None, "xpos": token["upos"],
                         "char_start": start, "char_end": cursor})
        out.append(rows)
    return out


def press_document(outlet_id: str, url_key: str, page: bytes, sentences_by_text: dict[str, list], **extra) -> dict:
    record = extraction.extract(page, body_sha256=hashlib.sha256(page).hexdigest(), content_type="text/html").record
    document = identity.document_id(outlet_id, url_key)
    annotation = {block["index"]: anchored(block["text"], sentences_by_text[block["text"]])
                  for block in record["blocks"] if block["text"] in sentences_by_text}
    return {"outlet_id": outlet_id, "document_id": document, "record": record, "annotation": annotation,
            "document_version_id": identity.document_version_id(document, record["extracted_text_sha256"]), **extra}


def press_inputs() -> dict:
    first = press_document("uy_diario_ejemplo", "https://www.diario-ejemplo.test/economia/puerto", PAGE,
                           {"El puerto crece": [TITLE], "El puerto creció un doce por ciento. La carga ha aumentado.": [S1, S2],
                            "Los vecinos esperan obras.": [S3]},
                           publication_date={"date": "2026-09-04", "basis": "json_ld", "cohort": "2026-Q3"})
    second = press_document("es_otro_diario", "https://www.otro-diario.test/puerto", COPY, {"El puerto crecerá.": [S4]})
    verbs = [identity.token_id(first["document_version_id"], 5), identity.token_id(first["document_version_id"], 14)]
    return {
        "release": {"release_id": "coprepan-0000.1", "release_kind": "fixture", "fixture": True, "created_at": CREATED,
                    "annotator_contract": annotator("fixture-press-sentence-policy/0", []),
                    "selection_policy": dict(NOT_PINNED), "coverage_reference": dict(NOT_PINNED)},
        "outlets": [outlet("uy_diario_ejemplo", "rss"), outlet("es_otro_diario", "rss", "regional")],
        "documents": [first, second],
        "relations": [{"relation": "syndicated_copy_of", "document_id": second["document_id"],
                       "target_document_id": first["document_id"], "basis": "fixture: declared by hand"},
                      {"relation": "duplicate_of", "document_id": second["document_id"],
                       "target_document_id": "uy_diario_ejemplo:doc:0000000000000000", "basis": "fixture: a target outside the release"}],
        "layers": {VERBAL_COMPLEX: {
            "declaration": {"target_level": "token", "validation_status": "NOT_VALIDATED", "rule_version": VERBAL_COMPLEX,
                            "values": ["PRETERITE", "PRESENT_PERFECT", "PRESENT", "FUTURE"], "attributes": ["role"]},
            "rows": [{"target_id": verbs[0], "value": "PRETERITE", "value_state": A.KNOWN, "role": "PREDICATE"},
                     {"target_id": verbs[1], "value": "PRESENT_PERFECT", "value_state": A.KNOWN, "role": "PREDICATE"}]}},
    }


def press_bundle() -> dict:
    return X.export_bundle(**press_inputs())


# --- radio (a fixture modelled on observed CO.RA.PAN 3.0 semantics; see the module docstring) -----------

RECORDING = {"recording_id": "UY_RadioEjemplo_Informativo_2026-09-04_0800-0810_0a1b2c3d", "radio_id": "uy_radio_ejemplo",
             "country_id": "uy", "station": "Radio Ejemplo", "program": "Informativo", "broadcast_date": "2026-09-04"}
TURNS = [
    {"hash": "0b6310019be21dcd", "speaker": "SPK_01", "speech_mode": "scripted", "applicability": "applicable", "share": 0.94,
     "start_ms": 1000, "sentences": [parse("""
El|el|DET|2|det|Definite=Def,Gender=Masc,Number=Sing,PronType=Art
puerto|puerto|NOUN|3|nsubj|Gender=Masc,Number=Sing
creció|crecer|VERB|0|ROOT|Mood=Ind,Number=Sing,Person=3,Tense=Past,VerbForm=Fin
"""), parse("""
La|el|DET|2|det|Definite=Def,Gender=Fem,Number=Sing,PronType=Art
carga|carga|NOUN|4|nsubj|Gender=Fem,Number=Sing
ha|haber|AUX|4|aux|Mood=Ind,Number=Sing,Person=3,Tense=Pres,VerbForm=Fin
aumentado|aumentar|VERB|0|ROOT|Gender=Masc,Number=Sing,Tense=Past,VerbForm=Part
""")]},
    {"hash": "56fbb5f0608d2b84", "speaker": "SPK_02", "speech_mode": "unscripted", "applicability": "applicable", "share": 1.0,
     "start_ms": 9000, "events": {1: ["REPETITION"]}, "sentences": [parse("""
los|el|DET|3|det|Definite=Def,Gender=Masc,Number=Plur,PronType=Art
los|el|DET|3|det|Definite=Def,Gender=Masc,Number=Plur,PronType=Art
vecinos|vecino|NOUN|4|nsubj|Gender=Masc,Number=Plur
esperan|esperar|VERB|0|ROOT|Mood=Ind,Number=Plur,Person=3,Tense=Pres,VerbForm=Fin
obras|obra|NOUN|4|obj|Gender=Fem,Number=Plur
""")]},
    {"hash": "aa00bb11cc22dd33", "speaker": "SPK_03", "speech_mode": "unknown", "applicability": "applicable", "share": None,
     "start_ms": 15000, "sentences": [parse("""
esperamos|esperar|VERB|0|ROOT|Mood=Ind,Number=Plur,Person=1,Tense=Pres,VerbForm=Fin
""")]},
    {"hash": "ee44ff5566778899", "speaker": "SPK_04", "speech_mode": None, "applicability": "not_applicable", "share": None,
     "start_ms": 18000, "population_label": "RECITED_LITURGY", "sentences": [parse("""
amén|amén|INTJ|0|ROOT|
""")]},
]


def _state(name: str, value, state: str | None = None) -> dict:
    state = state or (A.KNOWN if value is not None else A.UNKNOWN)
    return {name: value if state == A.KNOWN else None, f"{name}_state": state}


def corapan_bundle() -> dict:
    """What an adapter on CO.RA.PAN's side would have to do, on invented data."""
    recording = RECORDING["recording_id"]
    tables = {name: [] for name in A.TABLES}
    tables["outlets"].append({"outlet_id": RECORDING["radio_id"], "corpus_id": "corapan", "country_id": RECORDING["country_id"],
                              "display_name": RECORDING["station"], **_state("outlet_kind", "radio_station"),
                              **_state("city", None), **_state("region", None), **_state("scope", None), **_state("outlet_group", None)})
    units, sentences, tokens, profi = [], [], [], []
    for position, turn in enumerate(TURNS):
        turn_id = f"{recording}:d59v1:T:{turn['hash']}"
        # speech_mode → production_mode: the three substantive values pass unchanged; the abstention
        # `unknown` becomes the *state* unknown; `not_applicable` stays what it is.
        if turn["applicability"] == "not_applicable":
            mode = _state("production_mode", None, A.NOT_APPLICABLE)
        elif turn["speech_mode"] == "unknown":
            mode = _state("production_mode", None, A.UNKNOWN)
        else:
            mode = _state("production_mode", turn["speech_mode"])
        labelled = turn.get("population_label")
        index, clock, counted = 0, turn["start_ms"], 0
        for number, sentence in enumerate(turn["sentences"]):
            sentence_id = f"{turn_id}:S{number}"
            ids = [f"{turn_id}:TOKEN:{index + offset:08d}" for offset in range(len(sentence))]
            first_char = sum(len(t["form"]) + 1 for s in turn["sentences"][:number] for t in s)
            cursor, rows = first_char, []
            for offset, token in enumerate(sentence):
                events = turn.get("events", {}).get(index + offset, [])
                row = {"token_id": ids[offset], "sentence_id": sentence_id, "unit_id": turn_id, "document_id": recording,
                       "order_index": offset, "form": token["form"], "lemma": token["lemma"], "upos": token["upos"],
                       "morph": dict(sorted(token["morph"].items())), "deprel": token["deprel"], "token_kind": "word",
                       "production_event_types": list(events), "counted": labelled is None,
                       **_state("xpos", token["upos"]),
                       **_state("head_token_id", ids[token["head"] - 1] if token["head"] else None,
                                A.KNOWN if token["head"] else A.NOT_APPLICABLE),   # head_idx 0 = ROOT
                       **_state("char_start", cursor), **_state("char_end", cursor + len(token["form"])),
                       **_state("start_ms", clock), **_state("end_ms", clock + 300)}  # joined from the lexical layer
                cursor, clock = cursor + len(token["form"]) + 1, clock + 400
                counted += row["counted"]
                rows.append(row)
            index += len(sentence)
            tokens += rows
            sentences.append({"sentence_id": sentence_id, "unit_id": turn_id, "document_id": recording, "surface": "primary",
                              "order_index": len(sentences),
                              **_state("char_start", rows[0]["char_start"]), **_state("char_end", rows[-1]["char_end"]),
                              **_state("start_ms", rows[0]["start_ms"]), **_state("end_ms", rows[-1]["end_ms"])})
        units.append({"unit_id": turn_id, "document_id": recording, "unit_kind": "turn", "segmentation_nature": "technical",
                      "surface": "primary", "order_index": 2 * position, "tokens_counted": counted,
                      "scope_status": "out_of_scope" if labelled else "in_scope",
                      **_state("scope_reason", labelled.lower() if labelled else None, A.KNOWN if labelled else A.NOT_APPLICABLE),
                      **_state("parent_unit_id", None, A.NOT_APPLICABLE), **mode,
                      **_state("production_mode_share", turn["share"], A.KNOWN if turn["share"] is not None else A.NOT_APPLICABLE),
                      **_state("producer_id", f"{RECORDING['radio_id']}:occ:{turn['hash'][:12]}"),
                      **_state("producer_role", None, A.NOT_AVAILABLE)})
        unit_id = f"{turn_id}-CU-01"   # professional status is assigned at the contribution unit
        units.append({"unit_id": unit_id, "document_id": recording, "unit_kind": "contribution_unit", "segmentation_nature": "technical",
                      "surface": "primary", "order_index": 2 * position + 1, "tokens_counted": 0,
                      "scope_status": "out_of_scope" if labelled else "in_scope",
                      **_state("scope_reason", labelled.lower() if labelled else None, A.KNOWN if labelled else A.NOT_APPLICABLE),
                      **_state("parent_unit_id", turn_id), **mode,
                      **_state("production_mode_share", None, A.NOT_APPLICABLE),
                      **_state("producer_id", f"{RECORDING['radio_id']}:occ:{turn['hash'][:12]}"),
                      **_state("producer_role", None, A.NOT_AVAILABLE)})
        # CO.RA.PAN value states → contract states: VALUE → known, REVIEW_PENDING → undecided, NOT_RUN → not_available
        profi.append({"target_id": unit_id, **[_state("value", "professional"), _state("value", "non_professional"),
                                              _state("value", None, A.UNDECIDED), _state("value", None, A.NOT_AVAILABLE)][position]})
    for position, sentence in enumerate(sentences):
        sentence.update(_state("previous_sentence_id", sentences[position - 1]["sentence_id"] if position else None,
                               A.KNOWN if position else A.NOT_APPLICABLE))
        last = position + 1 == len(sentences)
        sentence.update(_state("next_sentence_id", None if last else sentences[position + 1]["sentence_id"],
                               A.NOT_APPLICABLE if last else A.KNOWN))
    tables["units"], tables["sentences"], tables["tokens"] = units, sentences, tokens
    tables["documents"].append({
        "document_id": recording, "corpus_id": "corapan", "release_id": "corapan-0000.1", "outlet_id": RECORDING["radio_id"],
        "country_id": RECORDING["country_id"], "modality": "spoken", "provenance_class": "fresh_ingest",
        "tokens_total": len(tokens), "tokens_counted": sum(t["counted"] for t in tokens),
        **_state("editorial_id", recording), **_state("region", None),
        **_state("production_mode", None, A.NOT_APPLICABLE),      # a recording has no single mode: it varies by region
        **_state("date", RECORDING["broadcast_date"]), **_state("date_basis", "broadcast_date"), **_state("cohort", "2026-Q3"),
        **_state("section_published", None, A.NOT_APPLICABLE), **_state("section_mapped", None, A.NOT_APPLICABLE),
        **_state("programme", RECORDING["program"]), **_state("language", None, A.NOT_AVAILABLE),   # "language is not measured"
        **_state("language_basis", None, A.NOT_AVAILABLE)})
    verbs = [t["token_id"] for t in tokens if t["form"] in ("creció", "aumentado")]
    release = {
        "contract": A.CONTRACT, "corpus_id": "corapan", "release_id": "corapan-0000.1", "release_kind": "fixture", "fixture": True,
        "modality": "spoken", "created_at": CREATED, "token_denominator": A.TOKEN_DENOMINATOR,
        "annotator_contract": annotator("layer2-terminals-forced/v1", ["FILLED_PAUSE", "NON_SPEECH_EVENT"]),
        "anchors": {"char_reference": "code-point offsets, half-open, into the projection text of the token's turn",
                    "time_reference": "milliseconds on the source-audio timeline, joined from the lexical layer"},
        "vocabularies": {"outlet_kind": ["radio_station"], "provenance_class": ["fresh_ingest", "legacy_ingest"],
                         "date_basis": ["broadcast_date", "publication_timestamp"], "language_basis": [],
                         "section_mapped": [], "producer_role": ["host", "newsreader", "reporter", "caller"],
                         "scope_reason": ["recited_liturgy", "technical_empty_or_broken", "p3_uncovered_tail"]},
        "selection_policy": dict(NOT_PINNED), "coverage_reference": dict(NOT_PINNED),
        "id_stability": "turn, sentence and token ids embed the ASR and diarisation snapshot; stable within a release only",
        "layers": {
            VERBAL_COMPLEX: {"target_level": "token", "validation_status": "NOT_VALIDATED", "rule_version": VERBAL_COMPLEX,
                             "values": ["PRETERITE", "PRESENT_PERFECT", "PRESENT", "FUTURE"], "attributes": ["role"]},
            PROFI: {"target_level": "unit", "validation_status": "NOT_VALIDATED", "rule_version": "profi-operational/c7_v1",
                    "values": ["professional", "non_professional"], "attributes": []}},
    }
    layers = {VERBAL_COMPLEX: [{"target_id": verbs[0], "value": "PRETERITE", "value_state": A.KNOWN, "role": "PREDICATE"},
                               {"target_id": verbs[1], "value": "PRESENT_PERFECT", "value_state": A.KNOWN, "role": "PREDICATE"}],
              PROFI: profi}
    return A.seal({"release": release, "tables": tables, "layers": layers, "compatibility": []})


def broken(bundle: dict, change) -> list[str]:
    """Apply ``change`` to a copy, reseal it (so the hashes hold), and return the objections."""
    damaged = copy.deepcopy(bundle)
    change(damaged)
    return A.validate(A.seal(damaged))
