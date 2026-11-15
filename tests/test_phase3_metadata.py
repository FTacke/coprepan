"""Phase-3 integration (CPD-0039): text surfaces, IPTC section mapping, scope and genre, AI and agency provenance, text reuse,
the content-quality gate /3, and their integration with the analysis contract and the layer store.

Synthetic pages only (no stored publisher page is a fixture); every rule is exercised by the mechanism, not by its config.
"""

import hashlib
import json

import pytest

from coprepan import analysis_contract as AC
from coprepan import analysis_export as X
from coprepan import content_quality as Q
from coprepan import editorial_metadata as M
from coprepan import enrichment, iptc, layer_store
from coprepan import extraction as E
from coprepan import extraction_article as A
from coprepan import identity
from coprepan import provenance as P
from coprepan import publisher_metadata as H
from coprepan import release_export
from coprepan import text_reuse as R
from support_crosscorpus import CREATED, NOT_PINNED, annotator, press_inputs

PARAS = "".join(f"<p>El concejo municipal aprobó el {n}.º punto del presupuesto que la alcaldía había presentado a los vecinos del barrio, "
                f"y los representantes de las juntas pidieron que las obras comiencen antes de que termine el año.</p>" for n in range(8))


def page(head="", header="", body=PARAS, after="", title="El concejo aprueba el presupuesto"):
    return (f'<html lang="es"><head>{head}</head><body><header><nav><a href="/">Inicio</a></nav></header>'
            f'<main><h1>{title}</h1>{header}<div class="cuerpo">{body}</div>{after}</main></body></html>')


def run(html, extractor=A.ARTICLE_2):
    data = html.encode("utf-8")
    return extractor.run(data, body_sha256=hashlib.sha256(data).hexdigest(), content_type="text/html")


def ld(**fields):
    return '<script type="application/ld+json">' + json.dumps({"@type": "NewsArticle", **fields}) + "</script>"


SUB = "Los vecinos del barrio pidieron que las obras comiencen antes de fin de año"


# --- text structure: extraction/2 ------------------------------------------------------------------------------------


def test_a_subtitle_the_page_states_is_its_own_block_on_the_title_surface_and_the_body_is_unchanged():
    html = page(head=ld(headline="El concejo aprueba el presupuesto", description=SUB), header=f"<h2>{SUB}</h2>")
    one, two = run(html, A.ARTICLE), run(html)
    subtitle = [b for b in two.record["blocks"] if b["kind"] == E.KIND_SUBTITLE]
    assert [(b["text"], b["role"], b["basis"]) for b in subtitle] == [(SUB, E.ROLE_TITLE, E.SUBTITLE_STATED_BY_PAGE)]
    assert two.record["schema"] == E.EXTRACTION_SCHEMA_2 and one.record["schema"] == E.EXTRACTION_SCHEMA
    assert two.body_text == one.body_text and two.body_text_sha256 == one.body_text_sha256       # BODY is not touched
    assert two.extracted_text_sha256 != one.extracted_text_sha256                                 # the text structure is new
    assert SUB not in two.body_text and two.record["metadata"]["title"]["value"] == "El concejo aprueba el presupuesto"


def test_a_subtitle_by_markup_is_taken_once_and_only_when_long_enough():
    marked = '<p class="article-subtitle">Los representantes de las juntas pidieron obras antes de que termine el año</p>'
    label = '<p class="subtitle">Elecciones 2026</p>'
    two = run(page(header=marked + label))
    subtitles = [(b["text"], b["basis"]) for b in two.record["blocks"] if b["kind"] == E.KIND_SUBTITLE]
    assert subtitles == [("Los representantes de las juntas pidieron obras antes de que termine el año", E.SUBTITLE_BY_MARKUP)]


def test_the_entradilla_stays_body_even_when_the_page_repeats_it_as_its_description():
    first = "El concejo municipal aprobó el 0.º punto del presupuesto"
    two = run(page(head=ld(headline="El concejo aprueba el presupuesto", description=first + " que la alcaldía había presentado a los vecinos")))
    assert not [b for b in two.record["blocks"] if b["kind"] == E.KIND_SUBTITLE]
    assert two.body_text == run(page(), A.ARTICLE).body_text


def test_a_stated_heading_opening_the_article_container_is_a_subtitle_a_stated_paragraph_is_not():
    head = ld(headline="El concejo aprueba el presupuesto", description=SUB)
    heading = run(page(head=head, body=f"<h2>{SUB}</h2>" + PARAS))
    assert [b["basis"] for b in heading.record["blocks"] if b["kind"] == E.KIND_SUBTITLE] == [E.SUBTITLE_STATED_BY_PAGE]
    paragraph = run(page(head=head, body=f"<p>{SUB}</p>" + PARAS))
    assert not [b for b in paragraph.record["blocks"] if b["kind"] == E.KIND_SUBTITLE] and SUB in paragraph.body_text


@pytest.mark.parametrize("header", [f'<h2><a href="/otra">{SUB}</a></h2>',                       # a link to another article
                                    f'<figure><figcaption class="subtitle">{SUB}</figcaption></figure>'])  # a caption
def test_a_link_or_a_caption_is_never_a_subtitle(header):
    two = run(page(head=ld(headline="El concejo aprueba el presupuesto", description=SUB), header=header))
    assert not [b for b in two.record["blocks"] if b["kind"] == E.KIND_SUBTITLE]


def test_no_subtitle_is_read_when_the_title_block_is_not_the_article_headline():
    html = page(head=ld(headline="El concejo aprueba el presupuesto", description=SUB), header=f"<h2>{SUB}</h2>", title="Diario Ejemplo")
    assert not [b for b in run(html).record["blocks"] if b["kind"] == E.KIND_SUBTITLE]


def test_a_machine_summary_module_never_stands_in_the_body():
    module = ('<div class="ee-ai-summary"><p>El concejo aprobó el presupuesto y los vecinos piden obras.</p>'
              '<span>Resumen generado por IA. Para más detalles, consulte el artículo completo.</span></div>')
    html = page(body=module + PARAS)
    one, two = run(html, A.ARTICLE), run(html)
    assert "Resumen generado por IA" in one.body_text and "Resumen generado por IA" not in two.body_text
    modules = [b for b in two.record["blocks"] if b.get("module")]
    assert modules and {(b["module"], b["role"]) for b in modules} == {(E.MODULE_AI_SUMMARY, E.ROLE_NON_BODY)}
    assert two.body_text == run(page(), A.ARTICLE).body_text                                      # nothing else lost


def test_the_new_extractor_is_a_candidate_beside_the_old_one_and_deterministic():
    assert A.ARTICLE_2.lifecycle == E.LIFECYCLE_CANDIDATE and A.ARTICLE_2.stage_version == "article_html/0.2.0"
    assert A.ARTICLE.stage_version == "article_html/0.1.0" and A.ARTICLE.schema == E.EXTRACTION_SCHEMA
    assert A.ARTICLE_2.stage_version not in E.EXTRACTORS and A.ARTICLE.stage_version not in E.EXTRACTORS
    with pytest.raises(E.ExtractorNotActive):
        A.ARTICLE_2.require_active()
    html = page(head=ld(headline="El concejo aprueba el presupuesto", description=SUB), header=f"<h2>{SUB}</h2>")
    assert run(html).payload == run(html).payload


@pytest.mark.parametrize("mutate, problem", [
    (lambda r: r["blocks"].append({"index": 99, "kind": "subtitle", "role": "body", "text": "x", "basis": "stated_by_page"}), "subtitle"),
    (lambda r: r["blocks"].append({"index": 99, "kind": "subtitle", "role": "title", "text": "x"}), "subtitle"),
    (lambda r: r["blocks"].append({"index": 99, "kind": "paragraph", "role": "body", "text": "x", "module": "ai_summary"}), "module"),
    (lambda r: r.update(schema=E.EXTRACTION_SCHEMA), "schema"),
])
def test_a_record_that_breaks_the_schema_is_refused(mutate, problem):
    record = json.loads(run(page()).payload)
    mutate(record)
    assert any(problem in p for p in E.record_problems(record, E.EXTRACTION_SCHEMA_2))


def test_an_extraction_1_record_may_carry_no_subtitle_and_no_module():
    record = json.loads(run(page(), A.ARTICLE).payload)
    record["blocks"][0]["module"] = "ai_summary"
    assert E.record_problems(record, E.EXTRACTION_SCHEMA)


# --- IPTC and the section map ----------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def section_map():
    return M.load_section_map()


def test_the_iptc_extracts_are_pinned_by_digest_and_carry_the_attribution(tmp_path):
    topics = iptc.load(iptc.MEDIATOPIC)
    assert topics.scheme["date_released"] == "2026-09-30T12:00:00+00:00" and "CC BY 4.0" in topics.attribution
    assert topics.source["sha256"] == "16216d085254db34ae4c6f620fd27ac0fa67f58caf6da537b5306ba99d2166e8"
    assert topics.top("medtop:20001065") == "medtop:15000000" and topics.label("medtop:15000000", "es") == "Deporte"
    with pytest.raises(iptc.TaxonomyError):
        iptc.load(iptc.MEDIATOPIC, expected_sha256="0" * 64)
    genre = iptc.load(iptc.GENRE)
    assert all(code in genre.concepts for code, _ in M.GENRE_IPTC.values())


def test_every_code_of_the_section_map_is_a_current_concept_and_no_mapping_claims_equality(section_map):
    codes = [(code, relation) for entries in section_map.topics.values() for code, relation in entries]
    assert codes and all(section_map.taxonomy.current(code) for code, _ in codes)
    assert {relation for _, relation in codes} <= {"closeMatch", "broadMatch"}      # a placement is never a subject


def test_a_section_map_with_a_repeated_key_or_an_invented_code_is_refused(tmp_path, section_map):
    root = tmp_path / "repo"
    (root / "config" / "taxonomy").mkdir(parents=True)
    (root / iptc.MEDIATOPIC).write_bytes((M._REPOSITORY / iptc.MEDIATOPIC).read_bytes())
    text = (M._REPOSITORY / M.SECTION_MAP).read_text(encoding="utf-8")
    (root / M.SECTION_MAP).write_text(text.replace('"deporte": [["medtop:15000000"', '"deporte": [["medtop:99999999"'), encoding="utf-8")
    with pytest.raises(M.MappingError):
        M.load_section_map(root=root)
    (root / M.SECTION_MAP).write_text(text.replace('"topics": {', '"topics": {"deportes": [], ', 1), encoding="utf-8")
    with pytest.raises(M.MappingError, match="twice"):
        M.load_section_map(root=root)


def test_labels_are_folded_and_a_tag_list_is_read_by_its_first_entry_only():
    assert M.components("Política > Elecciones") == ["politica", "elecciones"]
    assert M.components("https://www.perfil.com/seccion/deportes") == ["deportes"]
    assert M.components("Noticias, Política") == ["noticias", "politica"]
    assert M.components("Nacional, CAM, Contenedores de basura, San Salvador") == ["nacional"]


def classify(html, url="https://d.test/deportes/nota", outlet="ar_diario", country="ar", section_map=None):
    return M.classify(H.harvest(html, url=url), outlet_id=outlet, country_id=country, section_map=section_map)


def test_a_sports_section_maps_to_sport_with_its_relation_and_keeps_the_published_value(section_map):
    layer = classify(ld(articleSection="Deportes"), section_map=section_map)[M.LAYER_SECTION]
    assert (layer["value"], layer["value_state"], layer["validation_status"]) == (["medtop:15000000"], "known", "NOT_VALIDATED")
    assert layer["attributes"]["concepts"][0]["relation"] == "closeMatch"
    assert layer["attributes"]["published"] == [{"basis": "json_ld_articleSection", "value": "Deportes"},
                                                {"basis": "url_path", "value": "deportes"}]    # every statement kept, the first decides
    assert layer["basis"] == [{"basis": "json_ld_articleSection", "value": "Deportes"}]


@pytest.mark.parametrize("section, state, reason", [("Sociedad", "undecided", "ambiguous_label"),
                                                    ("Actualidad", "unknown", "generic_or_template_label"),
                                                    ("Mundo", "unknown", "section_names_no_topic"),
                                                    ("Conversaciones de domingo", "unknown", "unmapped_label")])
def test_a_section_that_does_not_name_a_topic_maps_to_none_and_says_why(section_map, section, state, reason):
    layer = classify(ld(articleSection=section), url="https://d.test/nota", section_map=section_map)[M.LAYER_SECTION]
    assert (layer["value"], layer["value_state"], layer["reason"]) == (None, state, reason)


def test_no_section_published_is_unknown_never_a_default(section_map):
    layers = classify(ld(), url="https://d.test/2026/10/10/nota", section_map=section_map)
    assert all(layers[name]["value_state"] == "unknown" for name in (M.LAYER_SECTION, M.LAYER_SCOPE, M.LAYER_PLACEMENT, M.LAYER_DECLARED))
    assert layers[M.LAYER_SECTION]["reason"] == "no_section_published"


def test_a_url_slug_counts_only_when_its_first_segment_is_a_known_section(section_map):
    assert classify(ld(), url="https://d.test/deportes/nota", section_map=section_map)[M.LAYER_SECTION]["value"] == ["medtop:15000000"]
    assert classify(ld(), url="https://d.test/la-final-de-deportes", section_map=section_map)[M.LAYER_SECTION]["value_state"] == "unknown"


@pytest.mark.parametrize("section, outlet, country, scope", [("Mundo", "ar_diario", "ar", "international"),
                                                              ("Nacionales", "ar_diario", "ar", "national"),
                                                              ("Venezuela", "ve_diario", "ve", "national"),
                                                              ("Venezuela", "ar_diario", "ar", "international"),
                                                              ("Salta", "ar_el_tribuno", "ar", "subnational"),
                                                              ("Locales", "pr_diario", "pr", "local")])
def test_the_scope_comes_from_a_section_that_names_a_reach_never_from_the_text(section_map, section, outlet, country, scope):
    html = ld(articleSection=section) + "<p>Una nota sobre Buenos Aires, Madrid y Caracas.</p>"
    assert classify(html, url="https://d.test/nota", outlet=outlet, country=country, section_map=section_map)[M.LAYER_SCOPE]["value"] == scope


def test_salta_is_a_place_label_only_for_the_outlet_that_publishes_it(section_map):
    layer = classify(ld(articleSection="Salta"), url="https://d.test/nota", outlet="es_diario", country="es", section_map=section_map)
    assert layer[M.LAYER_SCOPE]["value_state"] == "unknown"


def test_an_opinion_section_is_a_placement_and_a_declared_opinion_is_a_declaration(section_map):
    placed = classify(ld(articleSection="Opinión"), url="https://d.test/nota", section_map=section_map)
    assert placed[M.LAYER_PLACEMENT]["value"] == ["opinion"] and placed[M.LAYER_DECLARED]["value_state"] == "unknown"
    assert placed[M.LAYER_SECTION]["value_state"] == "unknown"                    # no topic is read from a genre section
    declared = classify('<script type="application/ld+json">{"@type": "OpinionNewsArticle", "articleSection": "Deportes"}</script>',
                        url="https://d.test/nota", section_map=section_map)
    assert declared[M.LAYER_DECLARED]["value"] == ["opinion"] and declared[M.LAYER_PLACEMENT]["value_state"] == "unknown"
    assert declared[M.LAYER_DECLARED]["attributes"]["iptc_genre"] == [{"genre": "opinion", "qcode": "genre:Opinion", "relation": "closeMatch"}]


@pytest.mark.parametrize("markup", ['{"@type": "ReportageNewsArticle"}', '{"@type": "NewsArticle", "genre": "News"}',
                                    '{"@type": "NewsArticle", "genre": "https://www.perfil.com/seccion/politica"}'])
def test_a_generic_type_a_generic_genre_or_a_section_in_the_genre_field_declares_no_genre(section_map, markup):
    layer = classify(f'<script type="application/ld+json">{markup}</script>', url="https://d.test/nota", section_map=section_map)[M.LAYER_DECLARED]
    assert layer["value_state"] == "unknown"


# --- AI provenance -------------------------------------------------------------------------------------------------


def ai(paragraph, where="body"):
    body = PARAS + (f"<p>{paragraph}</p>" if where == "body" else "")
    after = f"<footer><p>{paragraph}</p></footer>" if where == "footer" else ""
    return P.ai_disclosure(run(page(body=body, after=after)).record)


@pytest.mark.parametrize("statement, value", [
    ("Nota generada con inteligencia artificial bajo supervisión y edición humana.", "generated"),
    ("Este artículo fue generado por inteligencia artificial.", "generated"),
    ("*Este artículo fue creado con ayuda de una inteligencia artificial y curado por un periodista.", "assisted"),
    ("Este contenido fue producido por un equipo del diario con la asistencia de la IA", "assisted"),
    ("*Este artículo fue elaborado mediante la colaboración estratégica entre nuestro equipo editorial y herramientas de inteligencia artificial.", "assisted"),
    ("Este contenido incluye redacción realizada con la inteligencia artificial de ChatGPT. Supervisado y verificado por el equipo editorial.", "assisted"),
    ("Esta historia fue traducida del inglés al español con una herramienta de inteligencia artificial y fue revisada por un editor.", "translated"),
    ("Este artículo fue escrito originalmente en inglés y usamos una herramienta de inteligencia artificial para traducirlo.", "translated"),
])
def test_an_explicit_disclosure_about_the_article_is_read_with_its_form(statement, value):
    layer = ai(statement)
    assert (layer["value"], layer["value_state"]) == (value, "known")
    assert layer["attributes"]["statements"][0]["text"] == statement


def test_the_tool_and_a_human_review_are_kept_when_the_statement_names_them():
    statement = ai("Este contenido incluye redacción realizada con la inteligencia artificial de ChatGPT. Supervisado y verificado por el equipo editorial.")["attributes"]["statements"][0]
    assert statement["tools_named"] == ["ChatGPT"] and statement["human_review_stated"] is True


@pytest.mark.parametrize("text", ["La inteligencia artificial generará nuevos empleos, según el informe que el ministerio presentó.",
                                  "El primer ministro reaccionó a un video creado con inteligencia artificial en el que aparece bailando.",
                                  "Política de uso de la IA"])
def test_a_text_about_ai_is_not_a_disclosure_and_no_disclosure_is_unknown_not_human(text):
    layer = ai(text)
    assert (layer["value"], layer["value_state"], layer["reason"]) == (None, "unknown", "no_disclosure_observed")


@pytest.mark.parametrize("statement, component", [("Resumen generado por IA. Para más detalles, consulte el artículo completo.", "summary"),
                                                  ("Audio generado con IA de Google", "audio"),
                                                  ("El audio de esta noticia utiliza una voz sintética generada por Inteligencia Artificial.", "audio")])
def test_a_machine_component_is_listed_and_never_stands_for_the_article(statement, component):
    layer = ai(statement, where="footer")
    assert layer["value_state"] == "unknown" and layer["reason"] == "components_only" and layer["attributes"]["components"] == [component]


def test_a_caption_credit_is_an_image_component_and_a_headline_about_ai_images_is_nothing():
    caption = P.ai_disclosure(run(page(body=PARAS + "<figure><figcaption>Vecinos en la plaza. Imagen ilustrativa generada con IA</figcaption></figure>")).record)
    assert caption["attributes"]["components"] == ["image"]
    headline = P.ai_disclosure(run(page(after="<aside><h3>Una imagen creada con IA provoca un operativo en Singapur</h3></aside>")).record)
    assert headline["attributes"]["components"] == [] and headline["reason"] == "no_disclosure_observed"


def test_a_statement_the_outlet_prints_on_nearly_every_page_is_a_site_notice():
    statement = "Este artículo fue creado con ayuda de una inteligencia artificial."
    pages = [{"outlet_id": "o", "statements": [{"text": statement, "value": "assisted"}]} for _ in range(10)]
    site = P.site_wide_statements(pages)["o"]
    record = run(page(body=PARAS + f"<p>{statement}</p>")).record
    layer = P.ai_disclosure(record, site_wide=site)
    assert layer["value_state"] == "unknown" and layer["reason"] == "site_wide_statement_only"
    components = [{"outlet_id": "o", "statements": [{"text": "Audio generado por IA", "value": "audio"}]} for _ in range(10)]
    assert P.site_wide_statements(components).get("o", set()) == set()   # a module on every page is still a component


# --- agency credit -----------------------------------------------------------------------------------------------


def agency(head="", body=PARAS, after=""):
    html = page(head=head, body=body, after=after)
    return P.agency_credit(run(html).record, H.harvest(html, url="https://d.test/mundo/nota"))


def test_an_agency_in_the_json_ld_author_is_a_credit_whose_take_over_is_unknown():
    layer = agency(head=ld(author={"@type": "Person", "name": "Agencia EFE"}))
    assert (layer["value"], layer["attributes"]["agency_use"]) == (["efe"], "credit_only")
    assert "unchanged" in layer["attributes"]["note"]


def test_with_information_from_an_agency_is_declared_edited_material():
    layer = agency(after="<p>Con información de AFP y Reuters.</p>")
    assert (layer["value"], layer["attributes"]["agency_use"]) == (["afp", "reuters"], "edited_declared")


def test_agency_and_own_newsroom_together_is_a_joint_credit_but_a_place_or_a_handle_is_not():
    assert agency(head=ld(author="EFE / Redacción Primicias"))["attributes"]["agency_use"] == "joint_credit"
    assert agency(head=ld(author="Madrid| EFE| @PanamaAmerica"))["attributes"]["agency_use"] == "credit_only"
    assert agency(head=ld(author="EFE EFE"))["value"] == ["efe"]


def test_a_wire_dateline_opening_the_body_is_a_credit():
    layer = agency(body="<p>Washington, 10 oct (EFE).- El presidente de Estados Unidos habló con la prensa sobre el acuerdo y sus plazos.</p>" + PARAS)
    assert layer["value"] == ["efe"] and layer["basis"][0]["basis"] == "body_dateline"


@pytest.mark.parametrize("body, after", [
    (PARAS + "<p>Según informó la agencia EFE, el acuerdo se firmará el lunes en la sede del gobierno regional.</p>", ""),
    (PARAS, "<figure><figcaption>Los vecinos protestan frente a la alcaldía. (EFE)</figcaption></figure>"),
    (PARAS, "<p>Foto: AFP</p>"),
])
def test_an_agency_as_a_quoted_source_or_a_photo_credit_is_not_a_text_credit(body, after):
    layer = agency(body=body, after=after)
    assert (layer["value"], layer["value_state"], layer["reason"]) == (None, "unknown", "no_agency_credit_observed")


# --- text reuse ----------------------------------------------------------------------------------------------------

TEXT = " ".join(f"palabra{n} del texto de la agencia sobre el acuerdo regional número {n}" for n in range(12))


def test_the_same_text_in_two_outlets_is_a_syndication_relation_and_in_one_outlet_a_duplicate():
    found = R.relations([{"document_id": "a", "outlet_id": "x", "body_text": TEXT, "published": "2026-10-10T08:00"},
                         {"document_id": "b", "outlet_id": "y", "body_text": TEXT + " Con información de EFE.", "published": "2026-10-10T09:00"},
                         {"document_id": "c", "outlet_id": "x", "body_text": TEXT, "published": "2026-10-11T09:00"},
                         {"document_id": "d", "outlet_id": "z", "body_text": "otra cosa " * 80, "published": "2026-10-10T07:00"}])
    pairs = {(r["relation"], r["document_id"], r["target_document_id"]) for r in found}
    assert ("syndicated_copy_of", "b", "a") in pairs and ("duplicate_of", "c", "a") in pairs
    assert not any("d" in (r["document_id"], r["target_document_id"]) for r in found)
    assert all("not a finding of origin" in r["basis"] for r in found)


def test_the_index_compares_a_new_document_only_with_its_candidates_and_short_texts_not_at_all():
    index = R.ReuseIndex()
    assert index.add("a", outlet_id="x", body_text=TEXT) == []
    assert index.add("short", outlet_id="y", body_text="dos palabras") == [] and "short" not in index.documents
    assert [r["target_document_id"] for r in index.add("b", outlet_id="y", body_text=TEXT)] == ["a"]
    with pytest.raises(ValueError):
        index.add("a", outlet_id="x", body_text=TEXT)


# --- the quality gate: content-quality/3 ------------------------------------------------------------------------------

from test_content_quality import CASES, LONG, feats  # noqa: E402


@pytest.mark.parametrize("reason", [r for r in CASES if r != "machine_text"])
def test_every_other_rule_of_2_rejects_unchanged_under_3(reason):
    f, url = feats(CASES[reason])
    assert reason in Q.assess(f, url=url, ruleset=Q.RULESET_3)["reasons"]


def test_3_does_not_reject_a_declared_ai_text_and_2_still_does():
    f, url = feats(LONG.replace("Párrafo 0.", "Este artículo fue creado con ayuda de una inteligencia artificial que utiliza machine learning."))
    assert "machine_text" in Q.assess(f, url=url)["reasons"]
    decision = Q.assess(f, url=url, ruleset=Q.RULESET_3)
    assert decision["decision"] == Q.ACCEPT and decision["ruleset"] == "content-quality/3" and decision["evidence"]["machine_text_hits"]
    with pytest.raises(ValueError):
        Q.assess(f, url=url, ruleset="content-quality/9")
    assert Q.PREFERRED == Q.RULESET_3 and Q.LIFECYCLE == E.LIFECYCLE_CANDIDATE


def test_core_quality_does_not_depend_on_provenance_or_placement():
    """The same text with an agency byline, an AI note beside it, an opinion section or no section: one decision."""
    variants = [page(), page(head=ld(author="Agencia EFE", articleSection="Opinión")),
                page(after="<footer><p>Audio generado por IA</p></footer>"), page(head=ld(articleSection="Sociedad"))]
    decisions = [Q.assess(Q.features(run(v).record, http_status=200, html=v), url="https://d.test/nota", ruleset=Q.RULESET_3)
                 for v in variants]
    assert len({(d["decision"], tuple(d["reasons"])) for d in decisions}) == 1


# --- enrichment: one write-once artifact, reused by fingerprint ------------------------------------------------------


def test_the_metadata_is_derived_once_and_reused_while_no_input_changes(tmp_path, section_map):
    html = page(head=ld(articleSection="Deportes", author="AFP"))
    extracted = run(html)
    store = layer_store.LayerStore(tmp_path)
    arguments = dict(body_sha256=hashlib.sha256(html.encode()).hexdigest(), extraction_payload=extracted.payload, html=html,
                     url="https://d.test/deportes/nota", outlet_id="ar_diario", country_id="ar", section_map=section_map)
    first, value, reused = enrichment.derive_stored(store, **arguments)
    again, value_again, reused_again = enrichment.derive_stored(store, **arguments)
    assert (reused, reused_again, value) == (False, True, value_again) and first == again
    assert set(first["layers"]) == set(enrichment.LAYERS)
    assert all(layer["validation_status"] == "NOT_VALIDATED" for layer in first["layers"].values())
    other = enrichment.fingerprint(body_sha256=arguments["body_sha256"], extraction_payload_sha256=hashlib.sha256(extracted.payload).hexdigest(),
                                   section_map=section_map, site_wide=frozenset({"x"}))
    assert other != value                                         # a changed input is a new artifact, never an edit


# --- the analysis contract and the release contract ----------------------------------------------------------------


def test_a_subtitle_is_a_unit_of_its_own_on_the_title_surface_and_the_body_count_is_the_same():
    inputs = press_inputs()
    html = ('<html><head><script type="application/ld+json">{"@type": "NewsArticle", "headline": "El puerto crece", '
            '"description": "La terminal suma carga por tercer mes consecutivo"}</script></head><body><article>'
            "<h1>El puerto crece</h1><h2>La terminal suma carga por tercer mes consecutivo</h2>"
            "<p>El puerto creció un doce por ciento. La carga ha aumentado.</p><p>Los vecinos esperan obras.</p></article></body></html>")
    counts = []
    for extractor in (A.ARTICLE, A.ARTICLE_2):
        document = dict(inputs["documents"][0])
        record = run(html, extractor).record
        document["record"] = record
        document["document_version_id"] = identity.document_version_id(document["document_id"], record["extracted_text_sha256"])
        texts = {b["text"]: b["index"] for b in record["blocks"]}
        old = inputs["documents"][0]
        by_text = {b["text"]: old["annotation"][b["index"]] for b in old["record"]["blocks"] if b["index"] in old["annotation"]}
        document["annotation"] = {texts[t]: sentences for t, sentences in by_text.items() if t in texts}
        bundle = X.export_bundle(release=inputs["release"], outlets=inputs["outlets"][:1], documents=[document])
        units = bundle["tables"]["units"]
        counts.append(bundle["tables"]["documents"][0]["tokens_counted"])
        if extractor is A.ARTICLE_2:
            subtitle = [u for u in units if u["unit_kind"] == "subtitle"]
            assert [(u["surface"], u["tokens_counted"]) for u in subtitle] == [("title", 0)]
    assert counts[0] == counts[1] > 0                              # the shared denominator does not move


def test_the_joint_release_export_stays_on_extraction_1_until_the_joint_contract_names_the_subtitle():
    assert "subtitle" not in release_export.R.ANCHORS["written"]["unit_kinds"]       # the pinned joint contract, unchanged
    assert AC.UNIT_KINDS["subtitle"] == "editorial"                                    # this repository's analysis proposal
    record = run(page()).record
    item = {"extraction_payload": run(page()).payload, "source": {}, "admission_label": {}, "document_version_id": "v",
            "document_id": "ar_diario:doc:0000000000000000"}
    with pytest.raises(release_export.ExportRefused, match="only an extracted text"):
        release_export._document_record("ar_diario", "provisional", item)
    assert record["schema"] == E.EXTRACTION_SCHEMA_2
