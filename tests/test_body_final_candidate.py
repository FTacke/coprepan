"""``article_html/0.4.2`` (CPD-0043): genuine article text that 0.4.1 left out, found on the stored pages -- a stated articleBody
given as HTML or escaped twice, an interview outside ``<p>``, a paragraph whose phrase links its source, a lead behind the opening
photo's caption. Synthetic pages modelled on those cases, each with the counter-example that must stay out (a "Lea más:" teaser, a
fully linked headline, a linked paragraph at the BODY's edge). 0.4.0 and 0.4.1 run beside it and stay what they were.
"""

import hashlib
import json

from coprepan import content_quality as Q
from coprepan import extraction as E
from coprepan import extraction_body as B
from test_body_quality import HEADLINE, LEAD, TEXT, checked
from test_phase3_metadata import ld

PARAS = [p.removeprefix("<p>") for p in TEXT.split("</p>") if p]
LINKED = 'Según la autoridad de aseo, <a href="/aseo">cada día se recogen quinientas toneladas de basura en el distrito</a>.'
LINKED_TEXT = "Según la autoridad de aseo, cada día se recogen quinientas toneladas de basura en el distrito."
TEASER = '<p>Lea más: <a href="/otra">El concejo aprueba otro presupuesto para obras en los barrios del sur de la ciudad</a></p>'
HEADLINE_LINK = '<p><a href="/otra">El concejo aprueba otro presupuesto para obras en los barrios del sur de la ciudad.</a></p>'


def run(html, extractor):
    data = html.encode("utf-8")
    return checked(extractor.function(data, body_sha256=hashlib.sha256(data).hexdigest(), content_type="text/html",
                                      templates=frozenset()))


def body(x):
    return [b["text"] for b in x.record["blocks"] if b["role"] == E.ROLE_BODY]


def reasons(x):
    return {b["text"]: b["selection"]["reason"] for b in x.record["blocks"] if b.get("selection")}


def article(inner, head=""):
    return (f'<html lang="es"><head>{ld(headline=HEADLINE)}{head}</head><body><main><article><h1>{HEADLINE}</h1>{inner}'
            f'</article></main></body></html>')


def cuerpo(paragraphs):
    return '<div class="cuerpo">' + "".join(p if p.startswith("<p>") else f"<p>{p}</p>" for p in paragraphs) + "</div>"


# --- a linked paragraph built as prose ---------------------------------------------------------------------------------------


def test_a_paragraph_whose_phrase_links_its_source_comes_back_between_body_paragraphs():
    html = article(cuerpo([*PARAS[:3], LINKED, *PARAS[3:]]))
    old, new = run(html, B.ARTICLE_4_1), run(html, B.ARTICLE_4_2)
    assert LINKED_TEXT not in body(old)                                       # 0.4.1: the link-share guard took it for a teaser
    assert body(new)[3] == LINKED_TEXT and reasons(new)[LINKED_TEXT] == "linked_paragraph"
    assert new.record["extractor"]["version"] == "0.4.2"
    assert [b["text"] for b in new.record["blocks"]] == [b["text"] for b in old.record["blocks"]]   # same blocks, one role


def test_a_teaser_a_linked_headline_and_a_linked_paragraph_at_the_edge_stay_out():
    html = article(cuerpo([*PARAS[:3], TEASER, HEADLINE_LINK, *PARAS[3:], LINKED]))
    new = run(html, B.ARTICLE_4_2)
    assert body(new) == PARAS                                                  # the label teaser, the headline, the edge: out
    assert "linked_paragraph" not in reasons(new).values()


def test_the_shape_of_linked_prose():
    parser = B._Parser4(revision=2)
    prose = {"text": LINKED_TEXT}
    assert parser._prose_shape(prose, {"head": "según la autoridad de aseo,"})
    assert not parser._prose_shape(prose, {"head": "lea más:"})                # a label before the link
    assert not parser._prose_shape(prose, {"head": "según"})                   # under MIN_LINKED_HEAD_WORDS unlinked words
    assert not parser._prose_shape(prose, {"head": None})                      # no link at all
    assert not parser._prose_shape({"text": "Según la autoridad de aseo, el balance"}, {"head": "según la autoridad de aseo,"})


def test_a_linked_lead_built_as_prose_is_the_lead_and_a_linked_teaser_before_the_body_is_not():
    lead = ('Hace cincuenta años, por disposición del ministerio, <a href="/historia">la guardia civil y las radiopatrullas '
            'realizaron redadas nocturnas en distintos barrios de la capital para detener a sospechosos</a>.')
    html = article(f'<p>{lead}</p><div class="loader"><span>‌</span></div><div class="article-body">{TEXT}</div>')
    new = run(html, B.ARTICLE_4_2)
    assert reasons(new).get(body(new)[0]) == "lead_paragraph" and body(new)[0].startswith("Hace cincuenta años")
    assert body(run(html, B.ARTICLE_4_1))[0] == PARAS[0]                      # 0.4.1: a linked lead stays out
    teaser = article(f'{TEASER}<div class="loader"><span>‌</span></div><div class="article-body">{TEXT}</div>')
    assert body(run(teaser, B.ARTICLE_4_2)) == PARAS


# --- the stated articleBody as text ------------------------------------------------------------------------------------------


EXTRA = ("La guardia civil liberó a <b>veinticinco mujeres</b>, detuvo a cuatro personas y desarticuló una organización criminal "
         "asentada en la isla desde hace años.")
EXTRA_TEXT = EXTRA.replace("<b>", "").replace("</b>", "")


def _outside(paragraph, stated):
    return (f'<html lang="es"><head>{ld(headline=HEADLINE, articleBody=stated)}</head><body><main><h1>{HEADLINE}</h1>'
            f'<div class="cuerpo">{TEXT}</div><div class="extra">{paragraph}</div></main></body></html>')


def test_a_paragraph_the_page_states_in_an_articlebody_given_as_html_is_included():
    html = _outside(f"<p>{EXTRA}</p>", TEXT + f"<p>{EXTRA}</p>")
    assert EXTRA_TEXT not in body(run(html, B.ARTICLE_4_1))                   # 0.4.1 compared the markup
    new = run(html, B.ARTICLE_4_2)
    assert EXTRA_TEXT in body(new) and reasons(new)[EXTRA_TEXT] == "stated_article_body"


def test_a_quote_the_publisher_escaped_twice_does_not_hide_the_paragraph():
    quoted = ('El presidente dijo que "lo que pasó fue grave" y que la organización tiene derecho a opinar sobre la marcha del '
              'jueves por la tarde.')
    html = _outside(f"<p>{quoted}</p>", " ".join(PARAS) + " " + quoted.replace('"', '\\"'))
    assert quoted not in body(run(html, B.ARTICLE_4_1))
    assert quoted in body(run(html, B.ARTICLE_4_2))


def test_an_interview_answer_outside_p_that_the_page_states_is_included():
    answer = ("F. B: Los mejores alumnos no son genios, sino que tienen un sistema y mantienen ciertos hábitos de estudio "
              "durante todo el curso.")
    html = _outside(f"<div>{answer}</div>", " ".join(PARAS) + " " + answer)
    assert answer not in body(run(html, B.ARTICLE_4_1))
    new = run(html, B.ARTICLE_4_2)
    assert answer in body(new) and next(b for b in new.record["blocks"] if b["text"] == answer)["kind"] == "unstructured_text"


def test_text_the_page_does_not_state_stays_out():
    html = _outside(f"<p>{EXTRA}</p>", TEXT)
    assert EXTRA_TEXT not in body(run(html, B.ARTICLE_4_2))


def test_the_comparison_form_changes_no_text():
    assert B._comparable("25 mujeres , ha detenido ( en la isla )") == "25 mujeres, ha detenido (en la isla)"
    assert Q.stated_body_text('<p>Uno &amp; dos</p><blockquote class="twitter-tweet"><p>x</p></blockquote><script>y</script>') \
        == "Uno & dos"
    html = f'<html><head>{ld(articleBody="<p>Uno &amp; dos</p>")}</head><body></body></html>'
    assert Q.stated_body_text_characters(html) == len("Uno & dos")                       # content-features/2 unchanged


# --- the lead behind the opening photo ---------------------------------------------------------------------------------------


def test_the_lead_behind_the_caption_of_the_opening_photo_comes_back():
    html = article(f'<p>{LEAD}</p><figure><img src="x.jpg"><figcaption>La marcha en el centro de la capital</figcaption></figure>'
                   f'<div class="loader"><span>‌</span></div><div class="article-body">{TEXT}</div>')
    assert LEAD not in body(run(html, B.ARTICLE_4_1))                         # 0.4.1: the caption was the nearest block
    new = run(html, B.ARTICLE_4_2)
    assert body(new)[0] == LEAD and reasons(new)[LEAD] == "lead_paragraph"
    assert "La marcha en el centro de la capital" not in body(new)


# --- versions ------------------------------------------------------------------------------------------------------------------


def test_the_versions_stand_side_by_side():
    assert B.PREFERRED is B.ARTICLE_4_2 and B.ARTICLE_4_2.lifecycle == E.LIFECYCLE_CANDIDATE
    assert B.ARTICLE_4_2.schema == E.EXTRACTION_SCHEMA_3 and B.ARTICLE_4_2.stage_version not in E.EXTRACTORS
    assert B.REVISIONS == {"0.4.0": 0, "0.4.1": 1, "0.4.2": 2}
    assert "linked_paragraph" in E.SELECTION_INCLUDING
    html = article(cuerpo([*PARAS[:3], LINKED, *PARAS[3:]]))
    assert json.dumps(run(html, B.ARTICLE_4).record["blocks"]) == json.dumps(run(html, B.ARTICLE_4_1).record["blocks"])
