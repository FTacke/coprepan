"""BODY selection (CPD-0041): ``article_html/0.4.0`` on ``extraction/3`` -- every BODY decision recorded with rule and reason;
the pinned template table; ``body-quality/1``; ``agency-credit/3`` and ``editorial-metadata/3``; the frozen BODY control's merge.

Synthetic pages only, modelled on the failures of the phase-3 blind control (C01 lead outside the body component, C05/C54 an
author filter as the article, C49 a submission note, promotions, share bars, embeds) and on the false deletions the study found
and removed (a "cuerpo ad" class around the article, an "article-body__teaser" lead, interviewee profile lines in "author"
elements, data lists with repeated values). The earlier extractors are run beside the new one: they stay what they were.
"""

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

from coprepan import body_quality as BQ
from coprepan import editorial_metadata as M
from coprepan import enrichment
from coprepan import extraction as E
from coprepan import extraction_article as A
from coprepan import extraction_body as B
from coprepan import provenance as P
from coprepan import publisher_metadata as H
from test_content_quality import varied
from test_phase3_metadata import ld

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import study_body_quality as STUDY  # noqa: E402

HEADLINE = "El concejo aprueba el presupuesto de obras"
TEXT = varied(6)


def page(body=TEXT, before="", after="", head="", article=True):
    inner = f'<h1>{HEADLINE}</h1>{before}<div class="cuerpo">{body}</div>{after}'
    return (f'<html lang="es"><head>{ld(headline=HEADLINE)}{head}</head><body><nav><a href="/">Inicio</a></nav>'
            f'<main>{"<article>" + inner + "</article>" if article else inner}</main></body></html>')


def run(html, extractor=None, templates=frozenset()):
    data = html.encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    if extractor is not None:
        return extractor.run(data, body_sha256=digest, content_type="text/html")
    return B.extract_v4(data, body_sha256=digest, content_type="text/html", templates=templates)


def selections(x):
    return {b["text"]: b["selection"]["reason"] for b in x.record["blocks"] if b.get("selection")}


def body_of(x):
    return [b["text"] for b in x.record["blocks"] if b["role"] == E.ROLE_BODY]


def checked(x):
    assert E.record_problems(x.record, E.EXTRACTION_SCHEMA_3) == []
    return x


# --- container ----------------------------------------------------------------------------------------------------------


def test_an_author_filter_in_a_form_is_never_the_article():
    names = "".join(f"<option>Autora Número {n} de la Redacción Central</option>" for n in range(300))
    html = (f'<html><body><form class="search"><select name="autor">{names}</select></form>'
            f'<main><h1>{HEADLINE}</h1><div class="paywall">{TEXT}</div></main></body></html>')
    three, four = run(html, A.ARTICLE_3), checked(run(html))
    assert "Autora Número 7" in three.body_text and "Autora Número 7" not in four.body_text
    assert four.body_text.split("\n\n") == re.findall(r"<p>(.*?)</p>", TEXT)           # the article, verbatim


def test_a_module_mark_around_the_whole_article_does_not_move_the_container_or_remove_the_article():
    html = page(body=f'<div class="cuerpo ad tag-politica">{TEXT}</div>')
    three, four = run(html, A.ARTICLE_3), checked(run(html))
    assert four.body_text == three.body_text and not selections(four)


# --- exclusions ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("module, reason", [
    ('<p class="ad-label">PUBLICIDAD</p>', "module_advertising"),
    ('<div class="share-bar"><span>Compartir nota:</span></div>', "module_share"),
    ('<div class="related-news"><p>Noticias relacionadas</p></div>', "module_related"),
    ('<div class="newsletter-box"><p>Recibí en tu mail todas las noticias</p></div>', "module_newsletter"),
    ('<blockquote class="twitter-tweet"><p>Un mensaje de otra cuenta #hashtag pic.twitter.com/x</p></blockquote>', "module_social_embed"),
    ('<div class="audio-player"><span>Escuchar audio noticia</span></div>', "module_media_controls"),
    ('<p class="google-preferred-source">Agréganos a tus fuentes preferidas en Google</p>', "module_channel_promo"),
])
def test_a_marked_page_module_inside_the_article_leaves_the_body_with_its_reason(module, reason):
    three, four = run(page(body=TEXT + module + varied(2, seed=7)), A.ARTICLE_3), checked(run(page(body=TEXT + module + varied(2, seed=7))))
    removed = selections(four)
    assert list(removed.values()) == [reason] and set(removed) <= {b["text"] for b in three.record["blocks"] if b["role"] == E.ROLE_BODY}
    assert B.body_before_selection(four.record) == three.body_text          # the selection can be undone from the record
    assert all(t in three.body_text for t in body_of(four))                  # nothing new, nothing rewritten


def test_the_teaser_lead_of_a_paywalled_article_is_not_a_related_module():
    html = page(body=f'<div class="article-body__teaser article-body__teaser--locked">{varied(1, seed=3)}</div>{TEXT}')
    assert not selections(checked(run(html)))


def test_a_byline_mark_counts_at_the_edges_of_the_body_only():
    profile = '<p class="ue-c-author">48 años. Barcelona. Agente de la propiedad inmobiliaria</p>'
    html = page(body=f'<p class="byline">Por Juana Pérez</p>{varied(3)}{profile}{varied(3, seed=5)}')
    four = checked(run(html))
    assert selections(four) == {"Por Juana Pérez": "module_byline"}
    assert "48 años. Barcelona. Agente de la propiedad inmobiliaria" in body_of(four)


def test_production_notes_leave_the_body_and_stay_in_the_provenance_layers():
    notes = "<p>Con información de EFE.</p><p>Este artículo fue creado con ayuda de una inteligencia artificial.</p>"
    tail = "<p>La alcaldía presentó el plan a los vecinos del barrio. Foto: Imagen creada con IA</p>"
    html = page(body=TEXT + tail + notes)
    four = checked(run(html))
    assert set(selections(four).values()) == {"provenance_agency_note", "provenance_ai_note"}
    assert "La alcaldía presentó el plan a los vecinos del barrio. Foto: Imagen creada con IA" in body_of(four)   # a paragraph stays
    harvest = H.harvest(html, url="https://d.test/nota")
    assert P.ai_disclosure(four.record)["value"] == "assisted"
    assert P.agency_credit_3(four.record, harvest)["attributes"]["use_declared"] == "material_used_declared"


def test_only_a_long_verbatim_repeat_is_a_duplicate():
    once = "<p>El concejo municipal aprobó anoche el presupuesto de obras que la alcaldía había presentado a los vecinos.</p>"
    four = checked(run(page(body=TEXT + once + "<p>¡Viva!</p>" + varied(1, seed=9) + once + "<p>¡Viva!</p>")))
    assert list(selections(four).values()) == ["duplicate_block"] and body_of(four).count("¡Viva!") == 2


def test_label_headings_that_end_the_body_go_and_a_sentence_heading_stays():
    four = checked(run(page(body=TEXT + "<h3>Temas relacionados</h3>")))
    assert selections(four) == {"Temas relacionados": "trailing_heading"}
    sentence = "<h3>Vea la entrevista completa que realizó la redacción al ministro:</h3>"
    assert not selections(checked(run(page(body=TEXT + sentence))))


def test_a_label_repeated_in_the_body_goes_but_repeated_data_stay():
    cards = "".join(f"<p>Música</p><p>{t}</p>" for t in ("Uno", "Dos", "Tres"))
    data = "".join(f"<p>Fase: Primer Hexagonal</p><p>{n}</p>" for n in (6, 6, 6))
    four = checked(run(page(body=TEXT + cards + data)))
    assert set(selections(four).values()) == {"repeated_label"} and "Música" not in body_of(four)
    assert body_of(four).count("Fase: Primer Hexagonal") == 3 and body_of(four).count("6") == 3


def test_a_block_of_the_template_table_goes_unless_it_heads_real_text():
    table = frozenset({B.template_digest("Publicidad"), B.template_digest("Contexto")})
    html = page(body=TEXT + "<p>Publicidad</p><h2>Contexto</h2>" + varied(1, seed=11))
    four = checked(run(html, templates=table))
    assert selections(four) == {"Publicidad": "outlet_template"}
    assert four.record["blocks"][[b["text"] for b in four.record["blocks"]].index("Publicidad")]["selection"]["rule"] == B.TEMPLATE_RULE


def test_no_text_blocks_and_form_controls_inside_the_article_go():
    four = checked(run(page(body=TEXT + "<p>‌‌</p><button>Compartir</button>")))
    assert set(selections(four).values()) == {"no_text", "form_control"}


# --- inclusions ---------------------------------------------------------------------------------------------------------

LEAD = ("Hace cincuenta años, por disposición del ministerio, la guardia civil y las radiopatrullas realizaron redadas nocturnas "
        "en distintos barrios de la capital para detener a sospechosos de varios delitos.")


def test_the_lead_paragraph_outside_the_body_component_comes_back():
    html = (f'<html><head>{ld(headline=HEADLINE)}</head><body><main><article><h1>{HEADLINE}</h1><p>{LEAD}</p>'
            f'<div class="loader"><span>‌</span></div><div class="article-body">{TEXT}</div></article></main></body></html>')
    three, four = run(html, A.ARTICLE_3), checked(run(html))
    assert LEAD not in three.body_text and body_of(four)[0] == LEAD and selections(four) == {LEAD: "lead_paragraph"}


def test_a_lead_that_is_the_stated_description_or_not_adjacent_is_not_included():
    described = (f'<html><head>{ld(headline=HEADLINE, description=LEAD)}</head><body><main><article><h1>{HEADLINE}</h1><p>{LEAD}</p>'
                 f'<div class="article-body">{TEXT}</div></article></main></body></html>')
    assert LEAD not in checked(run(described)).body_text
    distant = (f'<html><head>{ld(headline=HEADLINE)}</head><body><main><article><h1>{HEADLINE}</h1><p>{LEAD}</p><span>Por la redacción</span>'
               f'<div class="article-body">{TEXT}</div></article></main></body></html>')
    assert LEAD not in checked(run(distant)).body_text


def test_a_paragraph_the_page_states_as_its_article_body_comes_back():
    stated = ld(headline=HEADLINE, articleBody=LEAD + " " + TEXT.replace("<p>", " ").replace("</p>", " "))
    html = (f'<html><head>{stated}</head><body><main><h1>{HEADLINE}</h1><div class="cuerpo">{TEXT}</div>'
            f'<div class="extra"><p>{LEAD}</p></div></main></body></html>')
    four = checked(run(html))
    assert selections(four) == {LEAD: "stated_article_body"} and LEAD in four.body_text


# --- the record, the version, the table -----------------------------------------------------------------------------------


def test_0_4_0_is_a_candidate_on_extraction_3_deterministic_and_selection_is_checked():
    assert (B.ARTICLE_4.version, B.ARTICLE_4.lifecycle, B.ARTICLE_4.schema) == ("0.4.0", E.LIFECYCLE_CANDIDATE, E.EXTRACTION_SCHEMA_3)
    assert B.PREFERRED is B.ARTICLE_4 and B.ARTICLE_4.stage_version not in E.EXTRACTORS
    html = page(body=TEXT + '<p class="ad">PUBLICIDAD</p>')
    assert run(html).record == run(html).record
    record = run(html).record
    bad = json.loads(json.dumps(record))
    excluded = next(b for b in bad["blocks"] if b.get("selection"))
    excluded["role"] = E.ROLE_BODY
    assert E.record_problems(bad, E.EXTRACTION_SCHEMA_3)
    assert E.record_problems({**record, "schema": E.EXTRACTION_SCHEMA_2}, E.EXTRACTION_SCHEMA_2)   # no selection under /2
    unknown = json.loads(json.dumps(record))
    next(b for b in unknown["blocks"] if b.get("selection"))["selection"]["reason"] = "looks_like_an_ad"
    assert E.record_problems(unknown, E.EXTRACTION_SCHEMA_3)


def test_the_pinned_template_table_holds_digests_only_and_is_read_from_the_repository():
    data = json.loads((B._REPOSITORY / B.TEMPLATES_PATH).read_text(encoding="utf-8"))
    assert data["schema"] == B.TEMPLATES_SCHEMA and data["parameters"]["min_unrelated_articles"] == 5
    assert all(len(d) == 24 and set(d) <= set("0123456789abcdef") for d in data["digests"] + data["recurring_kept"])
    assert B.body_templates() == frozenset(data["digests"]) and len(B.body_templates_sha256()) == 64


def test_a_missing_or_foreign_table_is_an_error_never_an_empty_table(tmp_path):
    with pytest.raises(FileNotFoundError):
        B.body_templates("config/extraction/none.json", root=tmp_path)
    (tmp_path / "t.json").write_text(json.dumps({"schema": "other"}), encoding="utf-8")
    with pytest.raises(E.ExtractionError):
        B.body_templates("t.json", root=tmp_path)


def test_the_joint_release_export_refuses_an_extraction_3_record():
    from coprepan import release_export

    item = {"extraction_payload": run(page()).payload, "source": {}, "admission_label": {}, "document_version_id": "v",
            "document_id": "ar_diario:doc:0000000000000000"}
    with pytest.raises(release_export.ExportRefused, match="only an extracted text"):
        release_export._document_record("ar_diario", "provisional", item)


# --- body-quality/1 ------------------------------------------------------------------------------------------------------


def test_the_contamination_states():
    clean = checked(run(page()))
    assert BQ.assess(clean.record, recurring=frozenset())["state"] == "clean"
    cleaned = checked(run(page(body=TEXT + '<p class="ad">PUBLICIDAD</p>')))
    assert BQ.assess(cleaned.record, recurring=frozenset())["state"] == "cleaned"
    residual = checked(run(page(body=TEXT + "<p>Más en https://d.test/otra-nota.html y en la portada.</p>")))
    result = BQ.assess(residual.record, recurring=frozenset())
    assert result["state"] == "residual_suspect" and result["evidence"]["signals"][0]["signal"] == "address_or_path"
    names = "".join(f"<option>Autora Número {n} de la Redacción</option>" for n in range(80))
    furniture = run(page(body=f'<div class="share">{names}</div>'))
    assert BQ.assess(furniture.record, recurring=frozenset())["state"] == "not_article"
    stub = page(head=ld(articleBody=" ".join(["palabra"] * 2000)), body=varied(2))
    assert BQ.assess(checked(run(stub)).record, html=stub, recurring=frozenset())["state"] == "incomplete"


# --- agency-credit/3, editorial-metadata/3 -----------------------------------------------------------------------------------


def test_the_bylines_of_teaser_cards_are_not_the_articles_credit():
    cards = '<div class="related-list"><p>Por EFE</p><p>Por The Associated Press</p></div>'
    html = page(body=TEXT + cards)
    four = checked(run(html))
    harvest = H.harvest(html, url="https://d.test/nota")
    assert P.agency_credit_2(four.record, harvest)["value"] == ["ap", "efe"]          # /2 would credit the cards' agencies
    assert P.agency_credit_3(four.record, harvest)["value_state"] == "unknown"
    plain = run(page(), A.ARTICLE_3)
    assert P.agency_credit_3(plain.record, harvest) | {"layer_id": None, "rule": None} == \
        P.agency_credit_2(plain.record, harvest) | {"layer_id": None, "rule": None}


def test_the_envelope_3_carries_agency_credit_3_and_2_is_unchanged():
    section_map = M.load_section_map()
    html = page(body=TEXT + "<p>Con información de EFE.</p>")
    four = run(html)
    common = dict(html=html, url="https://d.test/nota", record=four.record, outlet_id="ar_clarin", country_id="ar", section_map=section_map)
    two, three = enrichment.derive(**common, version=enrichment.VERSION_2), enrichment.derive(**common, version=enrichment.VERSION_3)
    assert set(three["layers"]) == set(enrichment.LAYERS_3) and enrichment.PREFERRED == enrichment.VERSION_3
    assert all(two["layers"][n] == three["layers"][n] for n in enrichment.LAYERS_2 if n != P.LAYER_AGENCY_2)
    digest = hashlib.sha256(four.payload).hexdigest()
    body = four.record["input"]["body_sha256"]
    fingerprints = {v: enrichment.fingerprint(body_sha256=body, extraction_payload_sha256=digest, section_map=section_map, version=v)
                    for v in enrichment.VERSIONS}
    assert len(set(fingerprints.values())) == 3


# --- the frozen BODY control ---------------------------------------------------------------------------------------------------


_KEY_NAME = "KEY_machine_predictions_open_only_after_the_verdicts.json"


def _control(tmp_path, rows, fields=("case_id", "question", "allowed", "answer", "note")):
    """A frozen control in ``tmp_path`` (key, blank form, manifest) and a filled form with ``rows``."""
    key = {"cases": [{"case_id": "B01", "component": "random", "stratum": "R00_random", "fetch_id": "ft1:x",
                      "predictions_0_4_0": {"FOREIGN": "2,5", "MISSING": "complete", "CORE": "yes"},
                      "predictions_0_3_0": {"FOREIGN": "0", "CORE": "yes"}}]}
    key_bytes = json.dumps(key).encode("utf-8")
    (tmp_path / _KEY_NAME).write_bytes(key_bytes)
    blank = "case_id,question,allowed,answer,note\n" + "".join(f"B01,{q},,,\n" for q in ("FOREIGN", "MISSING", "CORE"))
    (tmp_path / "verdicts_form.csv").write_bytes(blank.encode("utf-8"))
    (tmp_path / "manifest.json").write_text(json.dumps({"files": {_KEY_NAME: hashlib.sha256(key_bytes).hexdigest(),
                                                                  "verdicts_form.csv": hashlib.sha256(blank.encode()).hexdigest()}}),
                                            encoding="utf-8")
    verdicts = tmp_path / "v.csv"
    with verdicts.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields))
        writer.writeheader()
        writer.writerows([{f: r.get(f, "") for f in fields} for r in rows])
    return key_bytes, verdicts


def _merge(tmp_path, verdicts):
    out = tmp_path / "r.json"
    assert STUDY.main(["merge", "--out-dir", str(tmp_path), "--verdicts", str(verdicts), "--out", str(out)]) == 0
    return json.loads(out.read_text(encoding="utf-8"))


def test_merge_counts_false_deletions_and_residuals_and_refuses_a_changed_key(tmp_path):
    key_bytes, verdicts = _control(tmp_path, [{"case_id": "B01", "question": "FOREIGN", "answer": "2, 7"},
                                              {"case_id": "B01", "question": "MISSING", "answer": "middle_missing"},
                                              {"case_id": "B01", "question": "CORE", "answer": "yes"}])
    result = _merge(tmp_path, verdicts)["all_answers"]
    new = result["random|FOREIGN|0_4_0"]
    assert (new["blocks_kept_out_and_foreign"], new["blocks_false_deletion"], new["blocks_residual"]) == (1, 1, 1)
    assert result["random|FOREIGN|0_3_0"]["blocks_residual"] == 2 and result["random|CORE|0_4_0"]["agree"] == 1
    assert result["random|MISSING|0_4_0"] == {"disagree": 1, "disagree_coarse": 1}
    (tmp_path / _KEY_NAME).write_bytes(key_bytes.replace(b'"yes"', b'"no"'))
    with pytest.raises(SystemExit):
        _merge(tmp_path, verdicts)


def test_merge_keeps_the_operators_gold_apart_from_what_the_run_established(tmp_path):
    fields = ("case_id", "question", "allowed", "answer", "basis", "operator_answer", "operator_open", "note")
    # the operator: blocks 2-3 foreign, block 5 left open (the run then judged it article text); CORE not given (the run: no)
    _, verdicts = _control(tmp_path, [
        {"case_id": "B01", "question": "FOREIGN", "answer": "2-3", "basis": "AGENT_ASSESSED", "operator_answer": "2–3", "operator_open": "5"},
        {"case_id": "B01", "question": "MISSING", "answer": "complete", "basis": "TECHNICALLY_VERIFIED"},
        {"case_id": "B01", "question": "CORE", "answer": "no", "basis": "TECHNICALLY_VERIFIED"}], fields)
    result = _merge(tmp_path, verdicts)
    gold = result["operator_confirmed_only"]
    assert gold["random|FOREIGN|0_4_0"]["blocks_false_deletion"] == 0       # block 5 is out of the gold
    assert gold["random|FOREIGN|0_4_0"]["blocks_residual"] == 1             # block 3
    assert "random|CORE|0_4_0" not in gold and "random|MISSING|0_4_0" not in gold
    every = result["all_answers"]
    assert every["random|FOREIGN|0_4_0"]["blocks_false_deletion"] == 1      # block 5 with the run's answer
    assert every["random|CORE|0_4_0"]["disagree"] == 1
    assert result["bases"] == {"CORE|TECHNICALLY_VERIFIED": 1, "FOREIGN|AGENT_ASSESSED": 1, "MISSING|TECHNICALLY_VERIFIED": 1}
    assert result["cases"]["B01"]["false_deletion|0_4_0"] == [5]


def test_merge_refuses_an_unknown_basis_and_a_form_with_other_questions(tmp_path):
    fields = ("case_id", "question", "allowed", "answer", "basis", "operator_answer", "operator_open", "note")
    rows = [{"case_id": "B01", "question": q, "answer": "0" if q == "FOREIGN" else "yes", "basis": "OPERATOR_CONFIRMED"}
            for q in ("FOREIGN", "MISSING", "CORE")]
    _, verdicts = _control(tmp_path, rows[:2] + [{**rows[2], "basis": "GUESSED"}], fields)
    with pytest.raises(SystemExit):
        _merge(tmp_path, verdicts)
    _, verdicts = _control(tmp_path, rows[:2], fields)
    with pytest.raises(SystemExit):
        _merge(tmp_path, verdicts)
