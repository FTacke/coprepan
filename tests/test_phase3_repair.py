"""Phase-3 repair (CPD-0040): ``article_html/0.3.0`` (the title chosen among the h1 blocks, bounded subtitle paths),
``agency-credit/2`` (the agency's role and the declared use of its material, apart), ``text-reuse/2`` (exact, near-identical
and contained text), the ``editorial-metadata/2`` envelope, and the frozen blind control's merge.

Synthetic pages only, modelled on the failures the operator found in the 2026-11-15 review (no stored publisher page is a
fixture). The earlier versions are exercised beside the new ones: they stay what they were.
"""

import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest

from coprepan import content_quality as Q
from coprepan import editorial_metadata as M
from coprepan import enrichment, layer_store
from coprepan import extraction as E
from coprepan import extraction_article as A
from coprepan import provenance as P
from coprepan import publisher_metadata as H
from coprepan import text_reuse as R
from test_phase3_metadata import PARAS, SUB, ld, run

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import study_phase3_repair as STUDY  # noqa: E402

HEADLINE = "El concejo aprueba el presupuesto de obras"


def doc(head="", before="", header="", body=PARAS, after="", h1=HEADLINE):
    return (f'<html lang="es"><head>{head}</head><body><header>{before}<nav><a href="/">Inicio</a></nav></header>'
            f'<main><h1>{h1}</h1>{header}<div class="cuerpo">{body}</div>{after}</main></body></html>')


def title_of(extraction):
    return next((b["text"] for b in extraction.record["blocks"] if b["kind"] == "title"), None)


def subtitles(extraction):
    return [(b["text"], b["basis"]) for b in extraction.record["blocks"] if b["kind"] == E.KIND_SUBTITLE]


def both(html):
    two, three = run(html, A.ARTICLE_2), run(html, A.ARTICLE_3)
    assert three.body_text == two.body_text and three.body_text_sha256 == two.body_text_sha256      # BODY is not touched
    assert E.record_problems(three.record, E.EXTRACTION_SCHEMA_2) == []
    return two, three


# --- A: the title -------------------------------------------------------------------------------------------------------


def test_a_logo_h1_before_the_article_h1_gives_way_to_the_stated_headline():
    html = doc(head=ld(headline=HEADLINE) + f"<title>La Nación / {HEADLINE}</title>", before="<h1>La Nación</h1>")
    two, three = both(html)
    assert title_of(two) == "La Nación" and title_of(three) == HEADLINE
    logo = next(b for b in three.record["blocks"] if b["text"] == "La Nación")
    assert (logo["kind"], logo["role"]) == ("heading", E.ROLE_NON_BODY)


@pytest.mark.parametrize("head, h1", [
    (ld(headline=HEADLINE, articleSection="Cochabamba"), "Cochabamba"),                                   # a section label
    (f'<meta property="og:title" content="{HEADLINE}"><title>{HEADLINE} - Juventud Rebelde - Diario de la juventud cubana</title>',
     "Juventud Rebelde - Diario de la Juventud Cubana"),                                                  # the site's name
    (f'<meta property="og:site_name" content="Opinión Bolivia">{ld(headline=HEADLINE)}', "Opinión Bolivia"),
])
def test_an_h1_that_is_branding_or_a_section_label_is_no_title_and_the_title_stays_unknown(head, h1):
    two, three = both(doc(head=head, h1=h1))
    assert title_of(two) == h1 and title_of(three) is None
    assert three.record["metadata"]["title"]["value"] == HEADLINE            # what the page states, with its basis -- not text
    assert not subtitles(three)                                              # no reliable header region without a title
    assert three.body_text and not any(b["role"] == E.ROLE_BODY and b["text"] == h1 for b in three.record["blocks"])


def test_a_printed_headline_that_differs_from_the_search_title_stays_the_title():
    head = f'<meta property="og:title" content="Presupuesto 2027: lo que aprobó el concejo"><meta property="og:site_name" content="Diario">'
    _, three = both(doc(head=head))
    assert title_of(three) == HEADLINE


def test_a_good_body_without_a_title_is_not_rejected_for_it():
    from test_content_quality import varied

    _, three = both(doc(head=ld(headline=HEADLINE, articleSection="Cochabamba"), h1="Cochabamba", body=varied(6)))
    assert title_of(three) is None
    features = Q.features(three.record, http_status=200)
    assert Q.assess(features, ruleset=Q.RULESET_3)["decision"] == Q.ACCEPT


# --- A: the subtitle ----------------------------------------------------------------------------------------------------

FIELDS = ("<h2>Lugar: Teatro Martí, calle Dragones, esquina a Zulueta, La Habana Vieja, Cuba.</h2>"
          "<h2>Fecha de inicio: 12-10-2026, 3:00 pm.</h2><h2>Fecha de fin: 12-10-2026, 5:00 pm.</h2>")
DESCRIPTION = ("Lugar: Teatro Martí, calle Dragones, esquina a Zulueta, La Habana Vieja, Cuba. Fecha de inicio: 12-10-2026, 3:00 pm. "
               "Fecha de fin: 12-10-2026, 5:00 pm")


def test_the_fields_of_an_event_listing_are_no_subtitle():
    two, three = both(doc(head=ld(headline=HEADLINE, description=DESCRIPTION), header=FIELDS))
    assert subtitles(two) and not subtitles(three)


def test_a_newsletter_box_is_no_subtitle_even_when_it_is_the_first_marked_block():
    box = ('<div class="newsletter-block"><p class="block-header__subtitle">Lo bueno que es estar informado y de una manera diferente '
           'desde tu correo electrónico.</p></div>')
    two, three = both(doc(head=ld(headline=HEADLINE), header=box))
    assert subtitles(two) and not subtitles(three)


def test_a_promotion_mark_on_the_element_around_the_title_does_not_exclude_the_subtitle():
    html = (f'<html><head>{ld(headline=HEADLINE, description=SUB)}</head><body><main><div class="promo-article"><h1>{HEADLINE}</h1>'
            f'<h2>{SUB}</h2></div><div class="cuerpo">{PARAS}</div></main></body></html>')
    _, three = both(html)
    assert subtitles(three) == [(SUB, E.SUBTITLE_STATED_BY_PAGE)]


def test_a_subtitle_by_markup_alone_is_read_in_the_header_only():
    marked = '<p class="bajada">Los representantes de las juntas pidieron obras antes de que termine el año en curso</p>'
    filler = "".join(f"<span>Elemento {n} del encabezado de la página</span>" for n in range(A.MAX_MARKED_GAP + 2))
    near, far = both(doc(header=marked))[1], both(doc(header=filler + marked))[1]
    assert [b for _, b in subtitles(near)] == [E.SUBTITLE_BY_MARKUP] and not subtitles(far)


def test_one_subtitle_per_stated_text_and_never_a_caption_or_a_gallery():
    header = (f"<h2>{SUB}</h2><figure><figcaption>{SUB}</figcaption></figure>"
              f'<div class="gallery"><p class="caption-description">{SUB}</p></div>')
    two, three = both(doc(head=ld(headline=HEADLINE, description=SUB), header=header))
    assert len(subtitles(two)) == 2 and subtitles(three) == [(SUB, E.SUBTITLE_STATED_BY_PAGE)]


def test_a_stated_description_that_is_the_headline_is_no_subtitle_source():
    header = f'<p class="photo-text">{HEADLINE} en la sesión de este sábado</p>'
    _, three = both(doc(head=ld(headline=HEADLINE, description=HEADLINE + " en la sesión de este sábado"), header=header))
    assert not subtitles(three)


def test_a_stated_subtitle_and_the_entradilla_rule_of_0_2_0_still_hold():
    html = doc(head=ld(headline=HEADLINE, description=SUB), header=f"<h2>{SUB}</h2>")
    _, three = both(html)
    assert subtitles(three) == [(SUB, E.SUBTITLE_STATED_BY_PAGE)]
    entradilla = doc(head=ld(headline=HEADLINE, description="El concejo municipal aprobó el 0.º punto del presupuesto que la alcaldía "
                                                             "había presentado a los vecinos del barrio"))
    assert not subtitles(both(entradilla)[1])


def test_0_3_0_is_a_candidate_beside_0_2_0_deterministic_and_on_the_same_record_schema():
    assert (A.ARTICLE_3.version, A.ARTICLE_3.lifecycle, A.ARTICLE_3.schema) == ("0.3.0", E.LIFECYCLE_CANDIDATE, E.EXTRACTION_SCHEMA_2)
    assert A.PREFERRED is A.ARTICLE_3 and A.ARTICLE_3.stage_version != A.ARTICLE_2.stage_version
    assert A.ARTICLE_3.stage_version not in E.EXTRACTORS                    # not entered into the adopted registry
    html = doc(head=ld(headline=HEADLINE, description=DESCRIPTION), header=FIELDS, before="<h1>La Nación</h1>")
    assert run(html, A.ARTICLE_3).record == run(html, A.ARTICLE_3).record
    assert run(html, A.ARTICLE_3).record["extractor"] == {"name": "article_html", "version": "0.3.0"}


# --- B: agency-credit/2 --------------------------------------------------------------------------------------------------


def credit2(head="", body=PARAS, after=""):
    html = doc(head=head, body=body, after=after)
    record = run(html, A.ARTICLE_3).record
    harvest = H.harvest(html, url="https://d.test/mundo/nota")
    return P.agency_credit(record, harvest), P.agency_credit_2(record, harvest)


def test_with_information_from_an_agency_is_declared_use_of_material_not_editing():
    one, two = credit2(after="<p>Con información de EFE.</p>")
    assert one["attributes"]["agency_use"] == "edited_declared"                # /1 unchanged: its records stay as written
    assert (two["value"], two["attributes"]["agency_roles"], two["attributes"]["use_declared"]) == (
        ["efe"], ["material_source"], "material_used_declared")
    assert two["layer_id"] == "agency-credit/2" and two["basis"][0]["text"] == "Con información de EFE."   # the credit, verbatim


def test_a_joint_credit_names_the_newsroom_and_a_place_or_handle_is_no_co_credit():
    _, joint = credit2(head=ld(author="EFE / Redacción Primicias"))
    assert joint["attributes"]["agency_roles"] == ["co_credited"]
    assert joint["attributes"]["evidence"][0]["credited_with"] == ["Redacción Primicias"]
    assert joint["attributes"]["use_declared"] == "not_stated"                 # a joint credit is not a statement of editing
    _, place = credit2(head=ld(author="Madrid| EFE| @PanamaAmerica"))
    assert (place["attributes"]["agency_roles"], place["attributes"]["evidence"][0]["credited_with"]) == (["credited"], [])
    publisher = {"@type": "Organization", "name": "Panamá América"}
    _, own = credit2(head=ld(author="Panamá / EFE / PanamaAmerica", publisher=publisher))
    assert own["attributes"]["evidence"][0]["credited_with"] == ["PanamaAmerica"]        # the publisher, not the place
    _, only_place = credit2(head=ld(author="Panamá / EFE", publisher=publisher))
    assert only_place["attributes"]["agency_roles"] == ["credited"]
    _, handle = credit2(head=ld(author="Madrid| EFE| @PanamaAmerica", publisher=publisher))
    assert handle["attributes"]["agency_roles"] == ["credited"]                          # a handle is not a party
    html = doc(header="<p>Redacción / EFE / @PanamaAmerica</p>")
    byline = P.agency_credit_2(run(html, A.ARTICLE_3).record, H.harvest(html, url="https://d.test/mundo/nota"))
    [evidence] = [e for e in byline["attributes"]["evidence"] if e["position"] == "byline_block"]
    assert (evidence["role"], evidence["credited_with"]) == ("co_credited", ["Redacción"])
    html = doc(header="<p>Redacción EFE</p>")
    desk = P.agency_credit_2(run(html, A.ARTICLE_3).record, H.harvest(html, url="https://d.test/mundo/nota"))
    assert desk["attributes"]["agency_roles"] == ["credited"]                              # the agency's own desk


@pytest.mark.parametrize("note, use", [
    ("Texto de la agencia EFE editado por la redacción.", "edited_declared"),
    ("Reproducido íntegramente de la agencia AFP.", "verbatim_declared"),
])
def test_only_an_explicit_statement_declares_editing_or_a_verbatim_take_over(note, use):
    _, two = credit2(after=f"<p>{note}</p>")
    assert two["attributes"]["use_declared"] == use


def test_a_wire_dateline_or_an_author_credit_states_no_use():
    _, dateline = credit2(body="<p>Washington, 10 oct (EFE).- El presidente habló con la prensa sobre el acuerdo y sus plazos.</p>" + PARAS)
    _, author = credit2(head=ld(author={"@type": "Organization", "name": "Agencia EFE"}))
    for layer in (dateline, author):
        assert layer["attributes"]["agency_roles"] == ["credited"] and layer["attributes"]["use_declared"] == "not_stated"


def test_several_agencies_with_different_roles_are_all_kept():
    _, two = credit2(head=ld(author="AFP"), after="<p>Con información de EFE.</p>")
    assert two["value"] == ["afp", "efe"] and two["attributes"]["agency_roles"] == ["credited", "material_source"]


def test_a_quoted_agency_is_a_reason_of_unknown_and_a_photo_credit_is_nothing():
    _, quoted = credit2(body=PARAS + "<p>Según informó la agencia EFE, el acuerdo se firmará el lunes en la sede del gobierno.</p>")
    assert (quoted["value_state"], quoted["reason"]) == ("unknown", "agency_named_as_quoted_source_only")
    assert quoted["attributes"]["quoted_source_mentions"][0]["agencies"] == ["efe"]
    _, photo = credit2(after="<p>Foto: AFP</p><figure><figcaption>Los vecinos frente a la alcaldía. (EFE)</figcaption></figure>")
    assert (photo["value_state"], photo["reason"]) == ("unknown", "no_agency_credit_observed")


def test_the_metadata_envelope_2_carries_agency_credit_2_and_1_is_unchanged(tmp_path):
    section_map = M.load_section_map()
    html = doc(after="<p>Con información de EFE.</p>")
    extracted = run(html, A.ARTICLE_3)
    common = dict(html=html, url="https://d.test/mundo/nota", record=extracted.record, outlet_id="ar_clarin", country_id="ar",
                  section_map=section_map)
    one, two = enrichment.derive(**common), enrichment.derive(**common, version=enrichment.VERSION_2)
    assert set(one["layers"]) == set(enrichment.LAYERS) and set(two["layers"]) == set(enrichment.LAYERS_2)
    assert P.LAYER_AGENCY_2 in two["layers"] and P.LAYER_AGENCY not in two["layers"] and two["version"] == "editorial-metadata/2"
    assert all(one["layers"][n] == two["layers"][n] for n in enrichment.LAYERS if n != P.LAYER_AGENCY)
    digest = hashlib.sha256(extracted.payload).hexdigest()
    f1 = enrichment.fingerprint(body_sha256=extracted.record["input"]["body_sha256"], extraction_payload_sha256=digest, section_map=section_map)
    assert f1 == enrichment.fingerprint(body_sha256=extracted.record["input"]["body_sha256"], extraction_payload_sha256=digest,
                                        section_map=section_map, version=enrichment.VERSION)
    assert f1 != enrichment.fingerprint(body_sha256=extracted.record["input"]["body_sha256"], extraction_payload_sha256=digest,
                                        section_map=section_map, version=enrichment.VERSION_2)
    store = layer_store.LayerStore(tmp_path)
    stored = dict(body_sha256=extracted.record["input"]["body_sha256"], extraction_payload=extracted.payload, html=html,
                  url=common["url"], outlet_id="ar_clarin", country_id="ar", section_map=section_map, version=enrichment.VERSION_2)
    first, value, reused = enrichment.derive_stored(store, **stored)
    again, value_again, reused_again = enrichment.derive_stored(store, **stored)
    assert (reused, reused_again, value == value_again, first == again) == (False, True, True, True)
    with pytest.raises(ValueError):
        enrichment.derive(**common, version="editorial-metadata/9")


# --- C: text-reuse/2 -----------------------------------------------------------------------------------------------------

WIRE = " ".join(f"El ministro número {n} anunció un plan de obras para la región, que costará {n} millones según el gobierno." for n in range(14))


def pair(a, b, *, outlets=("x", "y")):
    return R.relations([{"document_id": "a", "outlet_id": outlets[0], "body_text": a, "published": "2026-10-10T08:00"},
                        {"document_id": "b", "outlet_id": outlets[1], "body_text": b, "published": "2026-10-10T09:00"}], version=R.VERSION_2)


def test_exact_means_the_same_canonical_text_and_only_technical_differences_are_folded():
    spaced = WIRE.replace(". ", ".\n\n", 3).replace("ministro", "mi­nistro", 1).replace(" ", " ", 2)
    [relation] = pair(WIRE, spaced)
    assert relation["text_match"] == "exact" and relation["relation"] == R.SYNDICATED and relation["rule"] == R.VERSION_2


@pytest.mark.parametrize("other", [WIRE.replace("El ministro número 3", "el ministro número 3"),        # case
                                   WIRE.replace("región,", "región;", 1),                                   # punctuation
                                   WIRE.replace("según el gobierno.", "según el Gobierno central.", 1)])   # wording
def test_a_difference_of_case_punctuation_or_wording_is_never_exact_even_at_full_containment(other):
    [relation] = pair(WIRE, other)
    assert relation["text_match"] == "near_identical"
    assert R.canonical_sha256(WIRE) != R.canonical_sha256(other)


def test_near_identical_and_contained_are_told_apart_with_their_measured_values():
    [near] = pair(WIRE, WIRE + " Con información de EFE y de la redacción local.")
    assert near["text_match"] == "near_identical" and min(near["containment"]) >= R.MIN_CONTAINMENT
    longer = WIRE + " " + " ".join(f"Los vecinos del barrio {n} opinaron sobre el plan en una reunión con el concejo." for n in range(14))
    [contained] = pair(WIRE, longer, outlets=("x", "x"))
    assert contained["text_match"] == "contained" and contained["relation"] == R.DUPLICATE
    assert contained["words"][0] > contained["words"][1] and contained["differing_words"][0] > 0
    assert set(contained) >= {"containment", "shingles", "shared_shingles", "words", "differing_words", "basis", "outlet_of"}


def test_the_relation_says_order_of_appearance_not_origin_and_1_is_unchanged():
    [two] = pair(WIRE, WIRE)
    assert "not a finding of origin or authorship" in two["basis"] and (two["document_id"], two["target_document_id"]) == ("b", "a")
    [one] = R.relations([{"document_id": "a", "outlet_id": "x", "body_text": WIRE}, {"document_id": "b", "outlet_id": "y", "body_text": WIRE}])
    assert one["match"] == "identical" and "text_match" not in one and "rule" not in one
    assert R.relations([{"document_id": "a", "outlet_id": "x", "body_text": WIRE}], version=R.VERSION_2) == []
    with pytest.raises(ValueError):
        R.ReuseIndex(version="text-reuse/9")


def test_the_index_of_2_stays_incremental():
    index = R.ReuseIndex(version=R.VERSION_2)
    assert index.add("a", outlet_id="x", body_text=WIRE) == []
    assert index.add("short", outlet_id="y", body_text="dos palabras") == [] and "short" not in index.documents
    assert [r["text_match"] for r in index.add("b", outlet_id="y", body_text=WIRE)] == ["exact"]
    assert index.add("c", outlet_id="z", body_text="otra cosa distinta " * 40) == []


# --- the blind control -----------------------------------------------------------------------------------------------------


def test_the_systematic_sample_takes_every_item_with_the_same_probability():
    items = list(range(100))
    sample = STUDY._systematic(items, 24, "seed")
    assert len(sample) == len(set(sample)) == 24 and sample == STUDY._systematic(items, 24, "seed")
    assert max(b - a for a, b in zip(sample, sample[1:])) <= 5           # spread over the ordered list


def test_merge_refuses_a_key_that_is_not_the_frozen_one_and_keeps_the_components_apart(tmp_path):
    key = {"cases": [{"case_id": "C01", "component": "random", "stratum": "R00_random", "fetch_ids": ["ft1:x"],
                      "predictions": {"CORE": "yes", "TITLE": "A"}},
                     {"case_id": "C02", "component": "targeted", "stratum": "T01_title_changed", "fetch_ids": ["ft1:y"],
                      "predictions": {"CORE": "no", "TITLE": "N"}}]}
    key_bytes = json.dumps(key).encode("utf-8")
    name = "KEY_machine_predictions_open_only_after_the_verdicts.json"
    (tmp_path / name).write_bytes(key_bytes)
    (tmp_path / "manifest.json").write_text(json.dumps({"files": {name: hashlib.sha256(key_bytes).hexdigest()}}), encoding="utf-8")
    verdicts = tmp_path / "verdicts.csv"
    with verdicts.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "question", "allowed", "answer", "note"])
        writer.writeheader()
        writer.writerows([{"case_id": "C01", "question": "CORE", "allowed": "", "answer": "yes", "note": ""},
                          {"case_id": "C01", "question": "TITLE", "allowed": "", "answer": "b", "note": ""},
                          {"case_id": "C02", "question": "CORE", "allowed": "", "answer": "unsure", "note": ""}])
    out = tmp_path / "result.json"
    assert STUDY.main(["merge", "--out-dir", str(tmp_path), "--verdicts", str(verdicts), "--out", str(out)]) == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["by_component"]["random|CORE"]["agree"] == 1 and result["by_component"]["random|TITLE"]["disagree"] == 1
    assert result["by_component"]["targeted|CORE"]["unsure"] == 1 and "agreement_wilson_95" not in result["by_component"]["targeted|CORE"]
    (tmp_path / name).write_bytes(key_bytes.replace(b'"yes"', b'"no"'))
    with pytest.raises(SystemExit):
        STUDY.main(["merge", "--out-dir", str(tmp_path), "--verdicts", str(verdicts), "--out", str(out)])
