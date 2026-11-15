"""The candidate article extractor (article_html/0.1.0) and the candidate content-quality gate (content-quality/1), CPD-0038.

Offline, synthetic pages that reproduce the structures measured on the weekend qualification. Nothing here is a real page.
"""

from __future__ import annotations

import hashlib

import pytest

from coprepan import content_quality as Q, extraction as E, extraction_article as A

PROSE = ("El Gobierno anunció este sábado que la medida entrará en vigor la próxima semana, después de que el Congreso la aprobara "
         "por una amplia mayoría y de que los sectores afectados pidieran más tiempo para adaptarse a las nuevas reglas. ")
SENTENCES = [
    "La lluvia que cayó durante la madrugada obligó a cerrar tres puentes en el norte de la provincia.",
    "Los vecinos del barrio Las Flores denunciaron que el agua llegó hasta la altura de las ventanas.",
    "El intendente pidió calma y aseguró que los equipos de emergencia trabajan desde temprano en la zona.",
    "Según el servicio meteorológico, las precipitaciones continuarán hasta el martes con menor intensidad.",
    "En la escuela técnica se habilitó un centro de evacuados con capacidad para doscientas personas.",
    "Una cooperativa local donó colchones, ropa de abrigo y alimentos no perecederos para las familias.",
    "La ruta nacional permanece cortada en el kilómetro cuarenta por la caída de un talud sobre la calzada.",
    "Los productores de la región calculan pérdidas importantes en los cultivos de maíz y de soja.",
    "El gobernador recorrerá mañana las localidades más afectadas junto con el ministro de Obras Públicas.",
    "Desde la empresa eléctrica informaron que unos ocho mil usuarios siguen sin suministro en la capital.",
    "Bomberos voluntarios rescataron a una mujer mayor que había quedado atrapada en su vivienda inundada.",
    "La oposición reclamó una sesión especial para discutir el estado de las obras de drenaje pendientes.",
    "Un estudio universitario advirtió hace dos años sobre el riesgo de desborde del arroyo principal.",
    "Las clases fueron suspendidas en once establecimientos educativos hasta que mejoren las condiciones.",
    "En el hospital regional atendieron a varias personas con cortes leves y cuadros de hipotermia.",
    "El municipio abrió una línea telefónica gratuita para recibir pedidos de asistencia las veinticuatro horas.",
    "Los comerciantes del centro estiman que tardarán semanas en recuperar la mercadería dañada por el agua.",
    "La Cruz Roja envió un equipo de voluntarios con agua potable y botiquines a los parajes rurales.",
    "El concejo deliberante aprobó por unanimidad declarar la emergencia hídrica por noventa días.",
    "Para el fin de semana se espera un descenso de la temperatura y vientos fuertes del sector sur.",
    "Varias familias pasaron la noche en casas de parientes mientras esperaban que bajara el nivel del río.",
    "El club de fútbol del pueblo ofreció su gimnasio como depósito de las donaciones que llegan de otras ciudades.",
    "Técnicos de la provincia evalúan el estado de las viviendas para decidir cuándo podrán volver sus dueños.",
    "La empresa de transporte suspendió los servicios de media distancia hasta nuevo aviso por seguridad.",
]


def varied(n_paragraphs: int, seed: int = 0) -> str:
    """Running Spanish prose that does not repeat itself: four different sentences a paragraph."""
    out = []
    for p in range(n_paragraphs):
        picked = [SENTENCES[(seed + 4 * p + s) % len(SENTENCES)] for s in range(4)]
        out.append("<p>" + " ".join(picked) + "</p>")
    return "".join(out)


def run(html: str, extractor=A.ARTICLE):
    body = html.encode("utf-8")
    return extractor.run(body, body_sha256=hashlib.sha256(body).hexdigest(), content_type="text/html")


def body_of(html, extractor=A.ARTICLE):
    return run(html, extractor).body_text


ARTICLE_PARAS = "".join(f"<p>{PROSE}Párrafo {n}.</p>" for n in range(6))


def test_teaser_cards_before_the_article_are_not_the_body_and_the_article_is():
    teasers = "".join(f'<article class="card"><h2><a href="/n{n}">Titular {n}</a></h2><p>Bajada breve {n}.</p></article>' for n in range(5))
    html = f"<html><body><main>{teasers}<div class='nota'><h1>Título</h1>{ARTICLE_PARAS}</div></main></body></html>"
    assert "Bajada breve" in body_of(html, E.BASELINE) and "Párrafo 3" not in body_of(html, E.BASELINE)   # the measured defect
    text = body_of(html)
    assert "Párrafo 0" in text and "Párrafo 5" in text and "Bajada breve" not in text


def test_an_article_container_inside_a_page_header_is_found():
    html = f"<html><body><header><div class='wrap'><article><h1>T</h1>{ARTICLE_PARAS}</article></div></header></body></html>"
    assert body_of(html, E.BASELINE) == ""                                   # pa_diaadia: nothing
    assert "Párrafo 4" in body_of(html)


def test_unclosed_paragraphs_do_not_nest_and_the_whole_article_is_the_body():
    paras = "".join(f"<p>{PROSE}Párrafo {n}." for n in range(6))
    html = f"<html><body><div class='foto'><p>Pie de foto largo de una imagen de satélite del huracán sobre el Golfo.</p></div><div class='texto'>{paras}</div></body></html>"
    text = body_of(html)
    assert all(f"Párrafo {n}" in text for n in range(6)) and "Pie de foto" not in text


def test_an_article_split_into_sibling_elements_is_taken_whole():
    parts = "".join(f"<article class='parte'><p>{PROSE}Parte {n}.</p><p>{PROSE}</p></article>" for n in range(3))
    html = f"<html><body><main><div class='cuerpo'>{parts}</div></main></body></html>"
    text = body_of(html)
    assert all(f"Parte {n}" in text for n in range(3))


def test_a_list_of_related_links_inside_the_container_is_not_body():
    related = "<ul>" + "".join(f'<li><a href="/r{n}">Otra noticia relacionada número {n} con un título largo</a></li>' for n in range(6)) + "</ul>"
    html = f"<html><body><article><h1>T</h1>{ARTICLE_PARAS}{related}<nav><p>Menú</p></nav></article></body></html>"
    text = body_of(html)
    assert "Párrafo 2" in text and "relacionada" not in text and "Menú" not in text


def test_the_candidate_is_not_active_and_the_baseline_is_unchanged():
    assert A.ARTICLE.lifecycle == E.LIFECYCLE_CANDIDATE and E.BASELINE.stage_version == "baseline_html/0.1.0"
    with pytest.raises(E.ExtractorNotActive):
        A.ARTICLE.require_active()
    record = run(f"<html><body><article>{ARTICLE_PARAS}</article></body></html>").record
    assert record["extractor"] == {"name": "article_html", "version": "0.1.0"} and record["schema"] == E.EXTRACTION_SCHEMA


# --- the gate -------------------------------------------------------------------------------------------------------


def feats(html, url="https://www.diario.test/nacional/una-nota", status=200):
    extraction = run(html)
    return Q.features(extraction.record, http_status=status, html=html), url


def decide(html, **kwargs):
    f, url = feats(html, **kwargs)
    return Q.assess(f, url=url)


LONG = f"<html><body><article><h1>T</h1>{varied(6)}<p>Párrafo 0.</p><p>Párrafo 1.</p><p>Párrafo 2.</p></article></body></html>"


def test_a_long_running_text_is_accepted_and_the_decision_says_on_what():
    decision = decide(LONG)
    assert decision["decision"] == Q.ACCEPT and decision["reasons"] == [] and decision["ruleset"] == "content-quality/1"
    assert decision["evidence"]["words"] >= 150


CASES = {
    "too_short": "<html><body><article><p>Una nota breve de dos frases. Nada más que esto.</p></article></body></html>",
    "no_body": "<html><body></body></html>",
    "not_running_prose": "<html><body><article>" + "".join(f"<p>Juan Pérez {n} ¶ María López {n} ¶ Pedro Gómez {n} ¶ Ana Ruiz {n}</p>" for n in range(40))
                         + "</article></body></html>",
    "page_frame": LONG.replace("Párrafo 0.", "Haz clic en el icono de la extensión del bloqueador de anuncios instalada en tu navegador."),
    "paywall_text": LONG.replace("Párrafo 1.", "Este contenido es exclusivo para suscriptores."),
    "machine_summary": LONG.replace("<p>", "<p>Resumen generado por IA. ", 1),
    "sponsored": LONG.replace("<p>", "<p>Presentado por Empresa Ejemplo. ", 1),
    "live_coverage": LONG.replace("<p>", "<p>10:45 ", 4),
    "incomplete_against_stated_body": LONG.replace("</body>", '<script type="application/ld+json">{"articleBody": "'
                                                   + " ".join(f"palabra{n}" for n in range(1500)) + '"}</script></body>'),
    "repetitive": f"<html><body><article>{ARTICLE_PARAS * 3}</article></body></html>",
}


@pytest.mark.parametrize("reason", list(CASES))
def test_each_rule_rejects_with_its_reason(reason):
    html = CASES[reason]
    decision = decide(html)
    assert decision["decision"] == Q.REJECT and reason in decision["reasons"], decision


def test_presented_by_in_running_text_is_news_language_not_sponsorship():
    assert decide(LONG.replace("Párrafo 2.", "El proyecto presentado por el diputado fue aprobado."))["decision"] == Q.ACCEPT


def test_an_address_that_is_a_live_page_is_rejected_an_article_about_a_live_broadcast_is_not():
    assert "live_coverage" in decide(LONG, url="https://www.diario.test/deportes/envivo-equipo-a-vs-equipo-b")["reasons"]
    assert decide(LONG, url="https://www.diario.test/mundo/la-ejecucion-en-vivo-que-anuncio-el-gobierno")["decision"] == Q.ACCEPT


def test_an_audio_player_label_is_not_a_ticker():
    assert decide(LONG.replace("<p>", "<p>0:00</p><p>", 3))["decision"] == Q.ACCEPT


def test_a_non_2xx_answer_is_rejected():
    assert "http_not_2xx" in decide(LONG, status=404)["reasons"]


def test_soft_hyphens_do_not_cut_words():
    f, _ = feats(LONG.replace("Gobierno", "Gobier­no"))
    g, _ = feats(LONG)
    assert f["words"] == g["words"] and f["function_word_share"] == g["function_word_share"]


def page(fetch_id, outlet, url, html, at):
    f, _ = feats(html, url=url)
    return {"fetch_id": fetch_id, "outlet_id": outlet, "url": url, "fetched_at": at, "features": f, "extracted": True}


def test_one_body_under_three_urls_of_an_outlet_is_a_template_and_all_are_rejected():
    terms = LONG.replace("Párrafo", "Condición")
    pages = [page(f"f{n}", "o", f"https://o.test/opinion/{n}", terms, f"2026-11-15T0{n}:00:00Z") for n in range(3)]
    decisions = Q.assess_corpus(pages)
    assert all(d["decision"] == Q.REJECT and "template_body" in d["reasons"] for d in decisions.values())


def test_the_same_body_again_in_one_outlet_is_a_duplicate_and_the_first_is_judged_on_its_merits():
    pages = [page("late", "o", "https://o.test/b", LONG, "2026-11-15T02:00:00Z"), page("early", "o", "https://o.test/a", LONG, "2026-11-15T01:00:00Z")]
    decisions = Q.assess_corpus(pages)
    assert decisions["early"]["decision"] == Q.ACCEPT and decisions["late"]["reasons"] == ["duplicate_of_earlier"]


def test_agency_copy_in_two_outlets_is_not_rejected_here():
    pages = [page("a", "outlet_a", "https://a.test/x", LONG, "2026-11-15T01:00:00Z"), page("b", "outlet_b", "https://b.test/y", LONG, "2026-11-15T01:00:00Z")]
    assert {d["decision"] for d in Q.assess_corpus(pages).values()} == {Q.ACCEPT}


def test_the_decision_is_deterministic_and_the_gate_is_a_candidate():
    assert decide(LONG) == decide(LONG) and Q.LIFECYCLE == E.LIFECYCLE_CANDIDATE
    assert set(Q.REASONS) >= {"too_short", "not_running_prose", "page_frame", "template_body", "duplicate_of_earlier"}
