"""Lexical naming rules of docs/architecture/TERMINOLOGY_AND_NAMING.md (CPD-0002)."""

import pytest

from coprepan import naming


def test_corpus_id_carries_no_generation():
    assert naming.CORPUS_ID == "coprepan"
    assert naming.CORPUS_IDS == ("corapan", "coprepan")
    assert not any(char.isdigit() for corpus_id in naming.CORPUS_IDS for char in corpus_id)


def test_generation_is_an_attribute_with_two_values():
    assert naming.GENERATIONS == ("legacy", "v3")
    assert naming.GENERATION == "v3"


def test_provenance_classes_are_the_decided_four():
    assert naming.PROVENANCE_CLASSES == (
        "native_v3",
        "legacy_refetched",
        "legacy_text_reannotated",
        "legacy_frozen",
    )


@pytest.mark.parametrize("value", ["ar", "es", "pr", "uy"])
def test_country_id_accepts_alpha2_lower_case(value):
    assert naming.is_country_id(value)


@pytest.mark.parametrize("value", ["ARG", "AR", "arg", "ar-cba", "ESP-SEV", "", "a1", None])
def test_country_id_refuses_legacy_and_malformed_forms(value):
    assert not naming.is_country_id(value)


@pytest.mark.parametrize("value", ["uy_el_pais", "es_el_pais", "ar_clarin", "pe_peru21"])
def test_outlet_id_accepts_registry_form(value):
    assert naming.is_outlet_id(value)


@pytest.mark.parametrize(
    "value",
    [
        "clarin",  # no country prefix
        "URY_el_pais",  # alpha-3 upper case
        "ury_el_pais",  # alpha-3 lower case
        "uy_el_país",  # non-ASCII, as the legacy system produced
        "uy_El_Pais",
        "uy-el-pais",
        "uy__el_pais",
        "uy_el_pais_",
        "uy_",
        "",
    ],
)
def test_outlet_id_refuses_legacy_slug_forms(value):
    assert not naming.is_outlet_id(value)


def test_same_outlet_name_in_two_countries_gives_two_ids():
    assert naming.outlet_country("es_el_pais") == "es"
    assert naming.outlet_country("uy_el_pais") == "uy"


def test_outlet_country_refuses_a_non_id():
    with pytest.raises(ValueError):
        naming.outlet_country("El País")


def test_form_check_is_not_a_registration_check():
    # A legacy slug such as `el_pais` has the lexical form of an outlet_id ("el" + "pais"). Only
    # the registry can say that `el` is not a country and that the id was never assigned.
    assert naming.is_outlet_id("el_pais")


@pytest.mark.parametrize("value", ["coprepan-2027.1", "coprepan-2027.12", naming.LEGACY_RELEASE_ID])
def test_release_id_accepts_dated_and_legacy_forms(value):
    assert naming.is_release_id(value)


@pytest.mark.parametrize(
    "value",
    [
        "coprepan3-2027.1",  # generation in the corpus id
        "coprepan-v3-2027.1",
        "coprepan-3.0",
        "coprepan-2027",
        "coprepan-2027.0",
        "corapan-2027.1",  # another corpus
        "COPREPAN-2027.1",
    ],
)
def test_release_id_refuses_generation_and_foreign_forms(value):
    assert not naming.is_release_id(value)


def test_release_id_is_checked_per_corpus():
    assert naming.is_release_id("corapan-2027.1", corpus_id="corapan")


def test_schema_id_form():
    assert naming.schema_id("fetch-record", 1) == "coprepan-fetch-record/v1"
    assert naming.is_schema_id("coprepan-status-assertions/v1")


@pytest.mark.parametrize(
    "value",
    [
        "coprepan3-fetch-record/v1",  # generation in the namespace
        "corapan-fetch-record/v1",  # the sibling's namespace is never minted here
        "coprepan-fetch-record/v0",
        "coprepan-fetch-record",
        "coprepan-Fetch-Record/v1",
        "coprepan-fetch_record/v1",
    ],
)
def test_schema_id_refuses_malformed_and_foreign_ids(value):
    assert not naming.is_schema_id(value)


def test_schema_id_builder_refuses_a_bad_thing():
    with pytest.raises(ValueError):
        naming.schema_id("Fetch Record", 1)
