"""Conformance of the cross-corpus analysis contract ``crosscorpus-analysis/v1`` (CPD-0008).

Two synthetic bundles — written press through COPREPAN's adapter, spoken radio modelled on
CO.RA.PAN 3.0's observed semantics — go through one validator. What passes here is the
*contract's internal consistency and implementability*: reproducibility and robustness of a
prototype. Nothing here is a linguistic result, and no annotation was made by an instrument.
"""

import copy

import pytest

from coprepan import analysis_contract as A
from coprepan import analysis_export as X
from coprepan import naming
from support_crosscorpus import PROFI, VERBAL_COMPLEX, broken, corapan_bundle, press_bundle, press_inputs
from test_canary import outlet


@pytest.fixture(scope="module")
def press():
    return press_bundle()


@pytest.fixture(scope="module")
def radio():
    return corapan_bundle()


def table(bundle, name):
    return bundle["tables"][name]


# --- both modalities, one contract ------------------------------------------------------------------


def test_both_corpora_pass_the_same_validator(press, radio):
    assert A.validate(press) == [] and A.validate(radio) == []
    assert press["release"]["contract"] == radio["release"]["contract"] == "crosscorpus-analysis/v1"
    assert (press["release"]["modality"], radio["release"]["modality"]) == ("written", "spoken")
    assert A.check_disjoint([press, radio]) == []


def test_the_contract_namespace_belongs_to_neither_corpus():
    assert naming.is_schema_id(A.CONTRACT, "crosscorpus") and not naming.is_schema_id(A.CONTRACT)
    assert A.NAMESPACE not in naming.CORPUS_IDS


def test_the_export_is_deterministic_and_the_bundle_survives_storage(press, tmp_path):
    assert press_bundle() == press
    A.write_bundle(press, tmp_path / "bundle")
    assert A.read_bundle(tmp_path / "bundle") == press
    with pytest.raises(FileExistsError):
        A.write_bundle(press, tmp_path / "bundle")                 # a bundle is written once


def test_a_fixture_says_that_it_is_one(press, radio):
    for bundle in (press, radio):
        assert bundle["release"]["fixture"] is True and bundle["release"]["release_kind"] == "fixture"
        assert bundle["release"]["release_id"].endswith("-0000.1")   # a year no release will carry
    assert "fixture is marked" in " ".join(broken(press, lambda b: b["release"].update(fixture=False)))


# --- release pinning ---------------------------------------------------------------------------------


def test_the_release_pins_every_table_by_hash_and_itself_by_one_more(press):
    release = press["release"]
    assert set(release["tables"]) == set(A.TABLES)
    assert all(len(entry["sha256"]) == 64 for entry in release["tables"].values())
    assert release["tables"]["tokens"]["rows"] == len(table(press, "tokens")) == 25
    tampered = copy.deepcopy(press)
    tampered["tables"]["tokens"][0]["lemma"] = "otro"              # one value changed, hashes not updated
    assert any("does not have the size and sha256" in v for v in A.validate(tampered))
    tampered = copy.deepcopy(press)
    tampered["release"]["release_id"] = "coprepan-0000.2"
    assert any("manifest_sha256" in v for v in A.validate(tampered))
    with pytest.raises(A.ContractViolation):
        A.require_valid(tampered)


def test_a_release_without_a_pinned_selection_policy_or_with_an_unvalidated_layer_is_not_a_release(press):
    objections = broken(press, lambda b: b["release"].update(release_kind="release", fixture=False))
    assert any("pins its selection policy" in v for v in objections)
    assert any("not validated and cannot be part of a release" in v for v in objections)
    half = broken(press, lambda b: b["release"]["selection_policy"].update(state="known", id="policy/1"))
    assert any("pinned by id and sha256" in v for v in half)


def test_the_instrument_is_named_with_its_pins(press, radio):
    for bundle in (press, radio):
        annotator = bundle["release"]["annotator_contract"]
        assert annotator["pins"] == {"spacy": "3.8.15", "model": "es_dep_news_trf", "model_version": "3.8.0"}
    assert press["release"]["annotator_contract"]["sentence_boundary_policy"] != radio["release"]["annotator_contract"]["sentence_boundary_policy"]
    assert any("at least one pin" in v for v in broken(press, lambda b: b["release"]["annotator_contract"].update(pins={})))


# --- ids, parents, order -----------------------------------------------------------------------------


def test_ids_are_unique_within_a_bundle_and_across_corpora(press, radio):
    def duplicate(bundle):
        bundle["tables"]["tokens"][1]["token_id"] = bundle["tables"]["tokens"][0]["token_id"]
    assert any("used twice" in v for v in broken(press, duplicate))
    clash = copy.deepcopy(radio)
    clash["tables"]["documents"][0]["document_id"] = table(press, "documents")[0]["document_id"]
    assert A.check_disjoint([press, clash]) != []


def test_every_child_has_its_parent_and_agrees_with_it(press):
    def orphan_unit(bundle):
        bundle["tables"]["units"][0]["document_id"] = "uy_diario_ejemplo:doc:ffffffffffffffff:v:ffffffffffff"
    def token_in_wrong_unit(bundle):
        bundle["tables"]["tokens"][0]["unit_id"] = bundle["tables"]["units"][-1]["unit_id"]
    def head_in_other_sentence(bundle):
        bundle["tables"]["tokens"][0]["head_token_id"] = bundle["tables"]["tokens"][-1]["token_id"]
    def unknown_outlet(bundle):
        bundle["tables"]["documents"][0]["outlet_id"] = "uy_no_existe"
    assert any("is not in documents" in v for v in broken(press, orphan_unit))
    assert any("its unit or document differs" in v for v in broken(press, token_in_wrong_unit))
    assert any("lies in another sentence" in v for v in broken(press, head_in_other_sentence))
    assert any("is not in outlets" in v for v in broken(press, unknown_outlet))


def test_order_indexes_are_dense_and_every_sentence_has_one_root(press):
    def gap(bundle):
        bundle["tables"]["tokens"][2]["order_index"] = 9
    def two_roots(bundle):
        bundle["tables"]["tokens"][0].update(head_token_id=None, head_token_id_state="not_applicable")
    def empty_sentence(bundle):
        sentence = bundle["tables"]["sentences"][-1]["sentence_id"]
        bundle["tables"]["tokens"] = [t for t in bundle["tables"]["tokens"] if t["sentence_id"] != sentence]
    assert any("order_index is not 0" in v for v in broken(press, gap))
    assert any("exactly one token is the root" in v for v in broken(press, two_roots))
    assert any("has no token" in v for v in broken(press, empty_sentence))


def test_sentence_neighbours_follow_document_order_within_a_surface(press, radio):
    body = [s for s in table(press, "sentences") if s["surface"] == "primary"]
    title = [s for s in table(press, "sentences") if s["surface"] == "title"]
    assert [s["previous_sentence_id"] for s in body[:3]] == [None, body[0]["sentence_id"], body[1]["sentence_id"]]
    assert (body[0]["previous_sentence_id_state"], title[0]["next_sentence_id_state"]) == ("not_applicable", "not_applicable")
    assert title[0]["next_sentence_id"] is None                  # the title is not the sentence before the body
    context = A.sentence_context(press, body[1]["sentence_id"])
    assert context == {"previous": "El puerto creció un doce por ciento .", "sentence": "La carga ha aumentado .",
                       "next": "Los vecinos esperan obras .", "same_unit_as_previous": True}
    assert A.sentence_context(press, body[2]["sentence_id"])["same_unit_as_previous"] is False   # across a paragraph break
    spoken = table(radio, "sentences")
    assert A.sentence_context(radio, spoken[2]["sentence_id"])["same_unit_as_previous"] is False  # across a change of turn

    def crossed(bundle):
        bundle["tables"]["sentences"][1]["previous_sentence_id"] = bundle["tables"]["sentences"][0]["sentence_id"]
        bundle["tables"]["sentences"][1]["previous_sentence_id_state"] = "known"
    assert any("neighbours do not follow" in v for v in broken(press, crossed))


# --- value states ------------------------------------------------------------------------------------


def test_the_value_state_vocabulary_is_small_closed_and_defined():
    assert tuple(A.VALUE_STATES) == ("known", "unknown", "not_applicable", "undecided", "not_available")
    assert all(len(meaning) > 10 for meaning in A.VALUE_STATES.values())


def test_a_value_is_null_exactly_when_its_state_is_not_known(press):
    def silent_null(bundle):
        bundle["tables"]["documents"][0]["date"] = None            # state still says 'known'
    def value_with_state(bundle):
        bundle["tables"]["documents"][0].update(section_mapped="economy")   # state still says 'not_available'
    def invented_state(bundle):
        bundle["tables"]["documents"][0]["programme_state"] = "n/a"
    def empty_string(bundle):
        bundle["tables"]["outlets"][0].update(city="", city_state="known")
    def missing_state(bundle):
        del bundle["tables"]["documents"][0]["language_state"]
    for change, text in ((silent_null, "null exactly when"), (value_with_state, "null exactly when"),
                         (invented_state, "not an allowed value state"), (empty_string, "not a valid value"),
                         (missing_state, "missing language_state")):
        assert any(text in v for v in broken(press, change)), change.__name__


def test_unknown_not_applicable_undecided_and_not_available_mean_different_things(press, radio):
    document, second = table(press, "documents")
    assert (document["programme_state"], document["section_mapped_state"]) == ("not_applicable", "not_available")
    assert (document["date"], document["date_basis"], document["cohort"]) == ("2026-09-04", "json_ld", "2026-Q3")
    assert (second["date_state"], second["section_published_state"]) == ("unknown", "unknown")   # the page states neither
    recording = table(radio, "documents")[0]
    assert (recording["section_published_state"], recording["language_state"]) == ("not_applicable", "not_available")
    profi = {row["value_state"] for row in radio["layers"][PROFI]}
    assert profi == {"known", "undecided", "not_available"}
    modes = [(u["production_mode"], u["production_mode_state"]) for u in table(radio, "units") if u["unit_kind"] == "turn"]
    assert modes == [("scripted", "known"), ("unscripted", "known"), (None, "unknown"), (None, "not_applicable")]


def test_a_page_date_nobody_has_parsed_is_not_available_rather_than_guessed():
    inputs = press_inputs()
    record = copy.deepcopy(inputs["documents"][0]["record"])
    record["metadata"]["publication_date"] = {"value": "4 de septiembre de 2026", "basis": "html_meta", "candidates": []}
    inputs["documents"][0] = {**inputs["documents"][0], "record": record, "publication_date": None}
    document = X.export_bundle(**inputs)["tables"]["documents"][0]
    assert (document["date"], document["date_state"], document["date_basis_state"]) == (None, "not_available", "not_available")

    def basis_without_date(bundle):
        bundle["tables"]["documents"][0].update(date=None, date_state="unknown")
    assert any("known together or not at all" in v for v in broken(press_bundle(), basis_without_date))

    def wrong_cohort(bundle):
        bundle["tables"]["documents"][0]["cohort"] = "2026-Q4"
    assert any("cohort does not contain its date" in v for v in broken(press_bundle(), wrong_cohort))


# --- modality, production mode, units ----------------------------------------------------------------


def test_production_mode_is_shared_without_mapping_speech_onto_writing(press, radio):
    assert set(A.PRODUCTION_MODES) == {"unscripted", "scripted", "prerecorded", "written_edited"}
    assert {u["production_mode"] for u in table(press, "units")} == {"written_edited"}
    assert table(radio, "documents")[0]["production_mode_state"] == "not_applicable"   # a recording has no single mode

    def scripted_press(bundle):
        bundle["tables"]["units"][0]["production_mode"] = "scripted"
    def written_radio(bundle):
        bundle["tables"]["units"][0]["production_mode"] = "written_edited"
    assert any("does not occur in the written modality" in v for v in broken(press, scripted_press))
    assert any("does not occur in the spoken modality" in v for v in broken(radio, written_radio))


def test_a_unit_declares_its_kind_and_what_made_its_boundary(press, radio):
    assert {u["segmentation_nature"] for u in table(press, "units")} == {"editorial"}
    assert {u["segmentation_nature"] for u in table(radio, "units")} == {"technical"}
    assert "utterance" not in A.UNIT_KINDS and "segment" not in A.UNIT_KINDS
    kinds = [(u["unit_kind"], u["surface"], u["scope_status"]) for u in table(press, "units") if u["document_id"] == table(press, "documents")[0]["document_id"]]
    assert kinds == [("title", "title", "in_scope"), ("paragraph", "primary", "in_scope"),
                     ("caption", "auxiliary", "out_of_scope"), ("paragraph", "primary", "in_scope")]

    def turn_as_editorial(bundle):
        bundle["tables"]["units"][0]["segmentation_nature"] = "editorial"
    def reason_missing(bundle):
        unit = next(u for u in bundle["tables"]["units"] if u["scope_status"] == "out_of_scope")
        unit.update(scope_reason=None, scope_reason_state="unknown")
    def undeclared_reason(bundle):
        unit = next(u for u in bundle["tables"]["units"] if u["scope_status"] == "out_of_scope")
        unit["scope_reason"] = "too_short"
    assert any("is technical segmentation" in v for v in broken(radio, turn_as_editorial))
    assert any("exactly an out-of-scope unit states its reason" in v for v in broken(press, reason_missing))
    assert any("scope_reason='too_short' is not a valid value" in v for v in broken(press, undeclared_reason))


def test_contribution_units_hang_under_their_turn(radio):
    children = [u for u in table(radio, "units") if u["unit_kind"] == "contribution_unit"]
    assert len(children) == 4 and all(u["parent_unit_id"] in {t["unit_id"] for t in table(radio, "units")} for u in children)

    def parent_elsewhere(bundle):
        bundle["tables"]["units"][1]["parent_unit_id"] = "no-such-unit"
    assert any("parent unit is missing" in v for v in broken(radio, parent_elsewhere))


# --- tokens: schema, anchors, denominator ------------------------------------------------------------


def test_one_typed_token_schema_for_both_modalities(press, radio):
    assert set(table(press, "tokens")[0]) == set(table(radio, "tokens")[0])
    token = next(t for t in table(press, "tokens") if t["form"] == "creció")
    assert (token["lemma"], token["upos"], token["morph"]) == ("crecer", "VERB", {"Mood": "Ind", "Number": "Sing", "Person": "3", "Tense": "Past", "VerbForm": "Fin"})
    assert (token["head_token_id"], token["head_token_id_state"], token["deprel"]) == (None, "not_applicable", "ROOT")
    assert token["token_id"].endswith(":TOKEN:00000005") and token["order_index"] == 2

    def morph_as_string(bundle):
        bundle["tables"]["tokens"][0]["morph"] = "Definite=Def|Gender=Masc"
    def project_label_in_morph(bundle):
        bundle["tables"]["tokens"][5]["morph"]["PastType"] = "simplePast"
    def undeclared_feature(bundle):
        bundle["tables"]["tokens"][5]["morph"]["Evident"] = "Fh"
    def space_token(bundle):
        bundle["tables"]["tokens"][0]["upos"] = "SPACE"
    assert any("morph=" in v and "not a valid value" in v for v in broken(press, morph_as_string))
    assert any("PastType is a project label and belongs in a layer" in v for v in broken(press, project_label_in_morph))
    assert any("not in the declared inventory" in v for v in broken(press, undeclared_feature))
    assert any("upos='SPACE'" in v for v in broken(press, space_token))


def test_anchors_are_typed_by_medium(press, radio):
    written, spoken = table(press, "tokens")[5], table(radio, "tokens")[2]
    assert (written["char_start"], written["char_end"], written["start_ms"], written["start_ms_state"]) == (10, 16, None, "not_applicable")
    assert (spoken["start_ms"], spoken["end_ms"], spoken["char_start_state"]) == (1800, 2100, "known")
    assert press["release"]["anchors"]["time_reference"] == "not_applicable" and "milliseconds" in radio["release"]["anchors"]["time_reference"]

    def time_on_paper(bundle):
        bundle["tables"]["tokens"][0].update(start_ms=0, start_ms_state="known", end_ms=10, end_ms_state="known")
    def speech_without_time(bundle):
        bundle["tables"]["tokens"][0].update(start_ms=None, start_ms_state="not_applicable", end_ms=None, end_ms_state="not_applicable")
    def backwards(bundle):
        bundle["tables"]["tokens"][0].update(char_start=9, char_end=2)
    def half(bundle):
        bundle["tables"]["tokens"][0].update(end_ms=None, end_ms_state="unknown")
    assert any("a written row has no time anchor" in v for v in broken(press, time_on_paper))
    assert any("a spoken word has a time anchor" in v for v in broken(radio, speech_without_time))
    assert any("char_start lies after char_end" in v for v in broken(press, backwards))
    assert any("share one state" in v for v in broken(radio, half))
    lost = broken(radio, lambda b: b["tables"]["tokens"][0].update(start_ms=None, start_ms_state="unknown", end_ms=None, end_ms_state="unknown"))
    assert lost == []                                             # an alignment that failed is sayable


def test_the_adapter_refuses_offsets_that_do_not_point_at_the_form():
    inputs = press_inputs()
    inputs["documents"][0]["annotation"][1][0][2]["char_start"] += 1
    with pytest.raises(X.ExportRefused, match="do not point at"):
        X.export_bundle(**inputs)


def test_the_token_denominator_is_one_rule_applied_to_both(press, radio):
    assert A.TOKEN_DENOMINATOR == "crosscorpus-token-denominator/v1"
    first = table(press, "documents")[0]
    assert (first["tokens_total"], first["tokens_counted"]) == (21, 15)      # 3 title tokens and 3 full stops do not count
    recording = table(radio, "documents")[0]
    assert (recording["tokens_total"], recording["tokens_counted"]) == (14, 13)   # the liturgy turn is out of scope
    repeated = [t for t in table(radio, "tokens") if t["production_event_types"] == ["REPETITION"]]
    assert len(repeated) == 1 and repeated[0]["counted"] is True             # a repeated word is a word: a declared caveat

    def count_punctuation(bundle):
        next(t for t in bundle["tables"]["tokens"] if t["upos"] == "PUNCT")["counted"] = True
    def wrong_sum(bundle):
        bundle["tables"]["documents"][0]["tokens_counted"] += 1
    def filled_pause(bundle):
        bundle["tables"]["tokens"][0]["production_event_types"] = ["FILLED_PAUSE"]
    def event_in_print(bundle):
        bundle["tables"]["tokens"][0]["production_event_types"] = ["REPETITION"]
    assert any("counted does not follow" in v for v in broken(press, count_punctuation))
    assert any("token counts do not equal" in v for v in broken(press, wrong_sum))
    assert any("masks before parsing" in v for v in broken(radio, filled_pause))
    assert any("a written token has no production event" in v for v in broken(press, event_in_print))


# --- relations, layers, compatibility ----------------------------------------------------------------


def test_duplicate_and_syndication_are_relations_between_documents(press):
    first, second = (d["document_id"] for d in table(press, "documents"))
    relations = table(press, "relations")
    assert relations[0] == {"relation": "syndicated_copy_of", "document_id": second, "target_document_id": first,
                            "target_in_release": True, "basis": "fixture: declared by hand"}
    assert relations[1]["target_in_release"] is False             # a relation may point outside the release, and says so
    assert table(press, "documents")[0]["editorial_id"] != first  # the document, and the version that was sampled

    def to_itself(bundle):
        bundle["tables"]["relations"][0]["target_document_id"] = bundle["tables"]["relations"][0]["document_id"]
    def lie(bundle):
        bundle["tables"]["relations"][1]["target_in_release"] = True
    def twice(bundle):
        bundle["tables"]["relations"].append(dict(bundle["tables"]["relations"][0]))
    assert any("points at itself" in v for v in broken(press, to_itself))
    assert any("target_in_release does not say" in v for v in broken(press, lie))
    assert any("stated twice" in v for v in broken(press, twice))


def test_two_versions_of_one_document_are_not_silently_both_exported():
    inputs = press_inputs()
    other = {**inputs["documents"][1], "document_id": inputs["documents"][0]["document_id"]}
    inputs["documents"].append(other)
    with pytest.raises(X.ExportRefused):
        X.export_bundle(**inputs)


def test_a_derived_layer_is_its_own_table_with_its_own_version(press, radio):
    for bundle in (press, radio):
        declaration = bundle["release"]["layers"][VERBAL_COMPLEX]
        assert (declaration["target_level"], declaration["validation_status"], declaration["rows"]) == ("token", "NOT_VALIDATED", 2)
        assert [row["value"] for row in bundle["layers"][VERBAL_COMPLEX]] == ["PRETERITE", "PRESENT_PERFECT"]
        assert all("PastType" not in t["morph"] for t in table(bundle, "tokens"))

    def undeclared_layer(bundle):
        bundle["layers"]["coprepan-article-type/v1"] = [{"target_id": "x", "value": "news", "value_state": "known"}]
    def value_outside(bundle):
        bundle["layers"][VERBAL_COMPLEX][0]["value"] = "simplePast"
    def target_missing(bundle):
        bundle["layers"][VERBAL_COMPLEX][0]["target_id"] = "no-such-token"
    def labelled_twice(bundle):
        bundle["layers"][VERBAL_COMPLEX][1]["target_id"] = bundle["layers"][VERBAL_COMPLEX][0]["target_id"]
    assert any("not declared by the release" in v for v in broken(press, undeclared_layer))
    assert any("value='simplePast' is not a valid value" in v for v in broken(press, value_outside))
    assert any("target is not a token" in v for v in broken(press, target_missing))
    assert any("labelled twice" in v for v in broken(press, labelled_twice))


def test_compatibility_aliases_live_in_their_own_view_and_never_in_a_canonical_table(press, radio):
    view = A.legacy_studies_view(press, country_alpha3={"uy": "URY", "es": "ESP"}, legacy_outlet_slugs={"uy_diario_ejemplo": "diario_ejemplo"})
    with_view = X.with_compatibility(press, view)
    assert with_view["release"]["compatibility"]["rows"] == len(view) == 6
    assert with_view["tables"] == press["tables"]                 # the canonical tables are untouched
    aliases = {(row["alias"], row["value"]) for row in view}
    assert {("country_code_alpha3", "URY"), ("legacy_outlet_slug", "diario_ejemplo"), ("register_group", "coprepan_written")} <= aliases
    spoken = A.legacy_studies_view(radio, country_alpha3={"uy": "URY"})
    groups = [row["value"] for row in spoken if row["alias"] == "register_group"]
    assert sorted(set(groups)) == ["corapan_lectura", "corapan_libre"] and len(groups) == 4   # no alias without a known mode

    def alias_in_canonical(bundle):
        bundle["tables"]["units"][0]["register_group"] = "coprepan_written"
    def alpha3_as_country(bundle):
        bundle["tables"]["outlets"][0]["country_id"] = "URY"
    def unknown_alias(bundle):
        bundle["compatibility"] = [{"view_id": A.COMPATIBILITY_VIEW, "target_level": "outlet", "target_id": "uy_diario_ejemplo",
                                    "alias": "country_id", "value": "URY"}]
    assert any("a compatibility alias: it belongs in the compatibility view" in v for v in broken(press, alias_in_canonical))
    assert any("country_id='URY'" in v for v in broken(press, alpha3_as_country))
    assert any("not a compatibility row" in v for v in broken(press, unknown_alias))


def test_an_unregistered_outlet_cannot_be_exported():
    inputs = press_inputs()
    inputs["outlets"][0] = outlet("uy_diario_ejemplo", "rss", status="proposed")
    with pytest.raises(X.ExportRefused, match="not registered"):
        X.export_bundle(**inputs)


# --- queries over both corpora: the contract works; nothing here is a finding -------------------------


def test_queries_run_over_both_corpora_through_the_contract_alone(press, radio):
    both = [radio, press]
    assert A.row_counts(both) == {"corapan": {"outlets": 1, "documents": 1, "units": 8, "sentences": 5, "tokens": 14, "relations": 0},
                                  "coprepan": {"outlets": 2, "documents": 2, "units": 5, "sentences": 5, "tokens": 25, "relations": 2}}
    assert A.counted_tokens_by(both, "country_id", "modality", "production_mode") == {
        ("es", "written", "written_edited"): 3, ("uy", "spoken", "<unknown>"): 1, ("uy", "spoken", "scripted"): 7,
        ("uy", "spoken", "unscripted"): 5, ("uy", "written", "written_edited"): 15}
    assert A.morph_value_counts(both, "Tense") == {("spoken", "Past"): 2, ("spoken", "Pres"): 3,
                                                   ("written", "Fut"): 1, ("written", "Past"): 2, ("written", "Pres"): 2}
    by_layer = {b["release"]["modality"]: sorted(r["value"] for r in b["layers"][VERBAL_COMPLEX]) for b in both}
    assert by_layer["spoken"] == by_layer["written"] == ["PRESENT_PERFECT", "PRETERITE"]
