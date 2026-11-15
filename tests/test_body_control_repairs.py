"""The repairs the BODY control of 2026-11-15 found (CPD-0042): ``article_html/0.4.1`` (no cut-off copy of a BODY block is
included), ``content-quality/4`` (the stated articleBody measured as text; a declared LiveBlogPosting is live coverage) and
``body-quality/2`` (the same text measure). Synthetic pages modelled on the control's cases B37 (a hidden paywall teaser ending in
"…"), B20/B42 (an articleBody stated as HTML with related boxes and an embedded post) and B28/B43 (live blogs whose times are not
in the BODY). The earlier versions run beside the new ones and stay what they were.
"""

import hashlib
import json

import pytest

from coprepan import body_quality as BQ
from coprepan import content_quality as Q
from coprepan import extraction as E
from coprepan import extraction_body as B
from test_body_quality import HEADLINE, LEAD, TEXT, checked, page
from test_content_quality import varied
from test_phase3_metadata import ld


def run(html, extractor):
    data = html.encode("utf-8")
    return extractor.function(data, body_sha256=hashlib.sha256(data).hexdigest(), content_type="text/html", templates=frozenset())


def first_paragraph(text_html):
    return text_html.split("</p>")[0].removeprefix("<p>")


# --- article_html/0.4.1 ---------------------------------------------------------------------------------------------------


def test_a_cut_off_teaser_of_the_first_paragraph_is_not_included_as_the_lead():
    first = first_paragraph(TEXT)
    teaser = " ".join(first.split()[:30]) + "…"
    html = (f'<html><head>{ld(headline=HEADLINE)}</head><body><main><article><h1>{HEADLINE}</h1>'
            f'<p class="gated-teaser" hidden>{teaser}</p><div class="metered"><div class="cuerpo">{TEXT}</div></div>'
            f'</article></main></body></html>')
    old, new = checked(run(html, B.ARTICLE_4)), checked(run(html, B.ARTICLE_4_1))
    body = lambda x: [b["text"] for b in x.record["blocks"] if b["role"] == E.ROLE_BODY]  # noqa: E731
    assert body(old)[0] == teaser                                  # 0.4.0: the BODY begins twice
    assert body(new)[0] == first and teaser not in body(new)       # 0.4.1: the teaser stays out
    assert new.record["extractor"]["version"] == "0.4.1" and old.record["extractor"]["version"] == "0.4.0"
    assert [b["text"] for b in new.record["blocks"]] == [b["text"] for b in old.record["blocks"]]   # same blocks, one role


def test_only_the_beginning_of_a_body_block_counts_as_a_copy():
    # the B20/Primicias case: the article's own paragraph stands, word for word, inside an embed the rules do not see -- keep it
    stated = ld(headline=HEADLINE, articleBody=LEAD + " " + TEXT.replace("<p>", " ").replace("</p>", " "))
    inside = (f'<html><head>{stated}</head><body><main><h1>{HEADLINE}</h1><div class="cuerpo">{TEXT}'
              f'<p>La policía informó en sus redes: {LEAD} Más detalles en el comunicado oficial de la institución.</p></div>'
              f'<div class="extra"><p>{LEAD}</p></div></main></body></html>')
    keep = checked(run(inside, B.ARTICLE_4_1))
    assert {b["text"]: b["selection"]["reason"] for b in keep.record["blocks"] if b.get("selection")} == {LEAD: "stated_article_body"}
    echo = (f'<html><head>{stated}</head><body><main><h1>{HEADLINE}</h1><div class="cuerpo"><p>{LEAD} Más detalles en el comunicado '
            f'oficial de la institución.</p>{TEXT}</div><div class="extra"><p>{LEAD}</p></div></main></body></html>')
    assert LEAD in checked(run(echo, B.ARTICLE_4)).body_text.split("\n\n")                       # 0.4.0: the opening twice
    assert LEAD not in checked(run(echo, B.ARTICLE_4_1)).body_text.split("\n\n")                  # 0.4.1: once


def _with_cards(cards):
    return (f'<html><head>{ld(headline=HEADLINE)}</head><body><main><article><h1>{HEADLINE}</h1>{cards}<p>{LEAD}</p>'
            f'<div class="loader"><span>‌</span></div><div class="article-body">{TEXT}</div></article></main></body></html>')


def test_a_teaser_card_inside_the_article_does_not_cost_the_lead():
    card = '<article class="v-card"><p>Noticia relacionada</p><p>Madrid da forma a la Gran Vía verde</p></article>'
    html = _with_cards(card)
    assert LEAD not in checked(run(html, B.ARTICLE_4)).body_text                     # 0.4.0: an article holding an article is a list
    new = checked(run(html, B.ARTICLE_4_1))
    assert [b["text"] for b in new.record["blocks"] if b["role"] == E.ROLE_BODY][0] == LEAD
    assert {b["text"]: b["selection"]["reason"] for b in new.record["blocks"] if b.get("selection")}[LEAD] == "lead_paragraph"


def test_an_article_element_whose_nested_articles_hold_much_of_its_text_is_still_a_list():
    cards = "".join(f'<article class="teaser"><p>{first_paragraph(varied(1, seed=s))}</p></article>' for s in range(1, 9))
    html = _with_cards(cards)
    parser = B._Parser4(revision=1)
    parser.feed(html)
    parser.close()
    blocks = parser.blocks()
    article = next(e for e, t in parser.tag_of.items() if t == "article" and not any(parser.tag_of.get(a) == "article"
                                                                                       for a in parser._ancestors(e)))
    assert parser._a_list(article)                                                      # 8 teasers: most of the text
    assert all((b.get("selection") or {}).get("reason") != "lead_paragraph" for b in blocks)
    card = B._Parser4(revision=1)
    card.feed(_with_cards('<article class="v-card"><p>Noticia relacionada</p></article>'))
    card.close()
    card.blocks()
    outer = next(e for e, t in card.tag_of.items() if t == "article" and not any(card.tag_of.get(a) == "article" for a in card._ancestors(e)))
    assert not card._a_list(outer)                                                      # one small card: not a list under 0.4.1


def test_a_real_lead_and_a_short_line_are_still_included_by_0_4_1():
    html = (f'<html><head>{ld(headline=HEADLINE)}</head><body><main><article><h1>{HEADLINE}</h1><p>{LEAD}</p>'
            f'<div class="loader"><span>‌</span></div><div class="article-body">{TEXT}</div></article></main></body></html>')
    new = checked(run(html, B.ARTICLE_4_1))
    assert [b["text"] for b in new.record["blocks"] if b["role"] == E.ROLE_BODY][0] == LEAD
    assert B.PREFERRED is B.ARTICLE_4_1 and B.ARTICLE_4_1.lifecycle == E.LIFECYCLE_CANDIDATE
    assert B.ARTICLE_4_1.schema == E.EXTRACTION_SCHEMA_3 and B.ARTICLE_4_1.stage_version not in E.EXTRACTORS
    assert B._Parser4._copy_of("Una línea corta…", {"una línea corta del texto que sigue"}) is False   # under 40 characters
    long = "una línea bastante más larga que cuarenta caracteres en total"
    assert B._Parser4._copy_of(long.capitalize() + "…", {long + " y sigue"}) is True
    assert B._Parser4._copy_of(long.capitalize(), {"antes de eso, " + long}) is False                  # inside, not the beginning


# --- content-quality/4: the stated body as text ------------------------------------------------------------------------------


def _stated_html(stated_body):
    return page(head=ld(articleBody=stated_body))


def test_a_body_stated_as_html_is_measured_as_its_text():
    paragraphs = varied(4)
    box = ('<div class="lee-tambien-bbcl"><div class="lee-tambien-titulo">Lee también...</div><a href="https://d.test/'
           + "x" * 400 + '" aria-label="lee también"><div class="lee-tambien-img lazy" style="background-image: url(https://d.test/'
           + "y" * 400 + '.jpg)"></div></a></div>')
    tweet = ('<blockquote class="twitter-tweet"><p lang="es">' + " ".join(["mensaje"] * 60) + '</p>&mdash; Cuenta (@cuenta) '
             '<a href="https://twitter.com/cuenta/status/1">July 20, 2025</a></blockquote>')
    stated = paragraphs[:len(paragraphs) // 2] + box + tweet + paragraphs[len(paragraphs) // 2:]
    html = page(body=paragraphs, head=ld(articleBody=stated))
    record = checked(run(html, B.ARTICLE_4_1)).record
    f = Q.features(record, html=html)
    assert f["version"] == Q.FEATURES_VERSION == "content-features/2"
    assert f["stated_body_characters"] > 2 * f["body_characters"] > f["stated_body_text_characters"]
    three, four = Q.assess(f, ruleset=Q.RULESET_3), Q.assess(f, ruleset=Q.RULESET_4)
    assert "incomplete_against_stated_body" in three["reasons"] and "incomplete_against_stated_body" not in four["reasons"]
    assert four["evidence"]["stated_body_text_characters"] == f["stated_body_text_characters"]
    assert BQ.assess(record, html=html, recurring=frozenset())["state"] == "incomplete"                       # /1 unchanged
    two = BQ.assess(record, html=html, recurring=frozenset(), version=BQ.VERSION_2)
    assert two["rule"] == "body-quality/2" and two["state"] != "incomplete" and BQ.PREFERRED == BQ.VERSION_2


def test_a_plain_stated_body_measures_the_same_and_a_real_stub_stays_incomplete():
    stub = page(head=ld(articleBody=" ".join(["palabra"] * 2000)), body=varied(2))
    record = checked(run(stub, B.ARTICLE_4_1)).record
    f = Q.features(record, html=stub)
    assert f["stated_body_text_characters"] == f["stated_body_characters"]
    assert "incomplete_against_stated_body" in Q.assess(f, ruleset=Q.RULESET_4)["reasons"]
    assert BQ.assess(record, html=stub, recurring=frozenset(), version=BQ.VERSION_2)["state"] == "incomplete"


# --- content-quality/4: a declared live blog -----------------------------------------------------------------------------------


def _live(json_ld):
    return page(body=varied(8), head='<script type="application/ld+json">' + json.dumps(json_ld) + "</script>")


@pytest.mark.parametrize("json_ld, live", [
    ({"@type": "LiveBlogPosting", "headline": HEADLINE}, True),
    ([{"@type": "WebPage"}, {"@type": ["BlogPosting", "LiveBlogPosting"]}], True),
    ({"@context": "https://schema.org", "@graph": [{"@type": "WebSite"}, {"@type": "LiveBlogPosting"}]}, True),
    ({"@type": "NewsArticle", "mentions": {"@type": "LiveBlogPosting", "url": "https://d.test/en-vivo"}}, False),
    ({"@type": "NewsArticle"}, False),
    # live-blog markup around a static article: every "update" at one time (cr_la_nacion) -- not live
    ({"@type": "LiveBlogPosting", "liveBlogUpdate": [{"@type": "BlogPosting", "datePublished": "2026-10-10T17:15:16Z"}] * 9}, False),
    # a real series of updates, and a declared live blog with a single update so far -- live
    ({"@type": "LiveBlogPosting", "liveBlogUpdate": [{"datePublished": "2026-10-10T17:15Z"}, {"datePublished": "2026-10-10T17:31Z"}]}, True),
    ({"@type": "LiveBlogPosting", "liveBlogUpdate": {"datePublished": "2026-10-10T15:00:00Z"}}, True),
])
def test_a_page_that_declares_itself_a_live_blog_is_live_coverage_under_4_only(json_ld, live):
    html = _live(json_ld)
    f = Q.features(checked(run(html, B.ARTICLE_4_1)).record, html=html)
    assert f["declares_live_blog"] is live
    assert ("live_coverage" in Q.assess(f, ruleset=Q.RULESET_4)["reasons"]) is live
    assert "live_coverage" not in Q.assess(f, ruleset=Q.RULESET_3)["reasons"]


def test_4_reads_content_features_2_only_and_3_is_unchanged():
    assert Q.PREFERRED == Q.RULESET_4 and Q.RULESETS == ("content-quality/2", "content-quality/3", "content-quality/4")
    html = page()
    f = Q.features(checked(run(html, B.ARTICLE_4_1)).record, html=html)
    with pytest.raises(ValueError):
        Q.assess({**f, "version": Q.FEATURES_VERSION_1}, ruleset=Q.RULESET_4)
    assert Q.assess(f, ruleset=Q.RULESET_3)["decision"] == Q.assess(f, ruleset=Q.RULESET_4)["decision"] == Q.ACCEPT
    assert "stated_body_text_characters" not in Q.assess(f, ruleset=Q.RULESET_3)["evidence"]
