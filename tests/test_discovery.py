"""Discovery: parsers, events, candidates, bounded expansion.

Fixtures are synthetic channel documents of the invented outlet of the canary. The legacy system
kept no channel document (no feed, sitemap or page was ever stored), so no recorded real one
exists. Nothing here validates discovery against any real outlet.
"""

import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from coprepan import discovery as D
from coprepan.identity import OutletUrlRules

FIXTURES = Path(__file__).parent / "fixtures" / "discovery"
OUTLET = "uy_diario_ejemplo"
WWW, MOBILE = "https://www.diario-ejemplo.test", "https://m.diario-ejemplo.test"
CHANNEL = f"{OUTLET}:ch:rss_001"
T0 = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)
RULES = OutletUrlRules(OUTLET, (WWW, MOBILE), f"{OUTLET}-url-rules/v1", ("id",), ("/amp",), ())
ARTICLE = f"{WWW}/Economia/Puerto-crecimiento-2026.html"
BUDGET = D.DiscoveryBudget(max_depth=3, max_documents=20, max_candidates=100, max_bytes=1_000_000)


def fixture(name):
    return (FIXTURES / name).read_bytes()


def parse(name, url=None, content_type="unknown"):
    return D.parse_channel_document(fixture(name), document_url=url or f"{WWW}/{name}", declared_content_type=content_type)


def fid(url):
    return "ft1:" + hashlib.sha256(url.encode()).hexdigest()


class Recorded:
    """A provider that serves recorded bytes by URL and remembers what it was asked for."""

    def __init__(self, documents):
        self.documents, self.asked = documents, []

    def __call__(self, url, depth):
        self.asked.append((url, depth))
        if url not in self.documents:
            return D.DocumentUnavailable(url, "http_404")
        body = self.documents[url]
        return D.ChannelDocument(url, url, fid(url), body if isinstance(body, bytes) else fixture(body))


def run(tmp_path, start, documents, budget=BUDGET, channel=CHANNEL, rules=RULES):
    tables = D.DiscoveryTables(tmp_path / "discovery")
    provider = Recorded(documents)
    result = D.discover_channel(tables, rules, channel_id=channel, start_url=start, provider=provider, budget=budget,
                                run_id="acq1-20261007T120000000000Z-000000000000", discovered_at=T0)
    return tables, provider, result


def test_fixtures_are_the_pinned_bytes():
    manifest = json.loads((FIXTURES / "MANIFEST.json").read_text(encoding="utf-8"))
    assert sorted(manifest["files"]) == sorted(p.name for p in FIXTURES.iterdir() if p.name != "MANIFEST.json")
    for name, pinned in manifest["files"].items():
        assert (hashlib.sha256(fixture(name)).hexdigest(), len(fixture(name))) == (pinned["sha256"], pinned["size_bytes"]), name


# --- formats --------------------------------------------------------------------------------------


def test_rss_items_links_guids_and_hints():
    parsed = parse("rss.xml", f"{WWW}/rss.xml")
    assert (parsed.outcome, parsed.format) == ("PARSED", "rss")
    items = [e for e in parsed.entries if e.relation == "item"]
    assert [e.url for e in items] == [
        f"{ARTICLE}?utm_source=rss&utm_medium=feed",
        f"{ARTICLE}?utm_source=rss-destacados",          # fragment dropped, query kept
        f"{WWW}/Regionales/puerto-separan-cargas",        # relative link resolved against the document
        None,                                             # no link, guid is not a permalink
        f"{WWW}/breves/123",                              # guid as permalink
        "https://agencia-ajena.test/cables/9",
        None,
    ]
    assert [e.problem for e in items] == [None, None, None, "no_link", None, None, "not_http"]
    assert items[0].hints == {"title": "El crecimiento del puerto obliga a separar cargas",
                              "published": "Mon, 05 Oct 2026 08:30:00 -0300", "guid": "ejemplo-000123"}
    assert items[2].hints["published"] == "2026-10-06T07:45:00-03:00"  # dc:date, kept as written
    assert items[1].url_raw.endswith("#comentarios")                    # the URL as written is evidence too
    assert [(e.relation, e.url) for e in parsed.entries if e.relation != "item"] == [("next_page", f"{WWW}/rss.xml?page=2")]
    assert [e.position for e in parsed.entries] == list(range(8))


def test_atom_entries_take_the_alternate_link_only():
    parsed = parse("atom.xml", f"{WWW}/feeds/atom.xml")
    assert parsed.format == "atom"
    assert [(e.url, e.problem) for e in parsed.entries] == [
        (f"{MOBILE}/amp/Economia/Puerto-crecimiento-2026.html", None),  # not the enclosure
        (f"{WWW}/breves/123", None),                                    # relative to the document URL
        (None, "no_link"),
    ]
    assert parsed.entries[0].hints == {"title": "El crecimiento del puerto obliga a separar cargas",
                                       "published": "2026-10-05T11:30:00Z", "updated": "2026-10-06T10:45:00Z",
                                       "guid": "tag:diario-ejemplo.test,2026:nota-123"}


def test_sitemap_urlset_ignores_extension_locations_and_keeps_path_case():
    parsed = parse("sitemap_urlset.xml")
    assert parsed.format == "sitemap_urlset"
    assert [(e.url, e.problem) for e in parsed.entries] == [
        (ARTICLE, None), (f"{WWW}/Regionales/puerto-separan-cargas", None),
        (f"{WWW}/Deportes/Final", None), (f"{WWW}/deportes/final", None), (None, "no_link")]
    assert not any("puerto.jpg" in (e.url or "") for e in parsed.entries)  # image:loc is not a candidate
    assert parsed.entries[0].hints == {"lastmod": "2026-10-06T07:45:00-03:00",
                                       "title": "El crecimiento del puerto obliga a separar cargas",
                                       "published": "2026-10-05T08:30:00-03:00"}


def test_sitemap_index_lists_child_documents_not_candidates():
    parsed = parse("sitemap_index.xml")
    assert parsed.format == "sitemap_index" and {e.relation for e in parsed.entries} == {"child_document"}
    assert [e.url for e in parsed.entries][:2] == [f"{WWW}/sitemaps/2026-10.xml", f"{WWW}/sitemaps/anidado.xml"]


def test_html_listing_base_relative_links_and_malformed_markup():
    parsed = parse("listing.html", f"{WWW}/Economia/?pagina=1", "text/html")
    assert parsed.format == "html_listing" and parsed.base_url == f"{WWW}/Economia/"  # the first <base> only
    assert [(e.relation, e.url, e.problem) for e in parsed.entries] == [
        ("next_page", f"{WWW}/Economia/?pagina=2", None),
        ("item", f"{WWW}/", None),
        ("item", None, "not_http"),                                             # javascript:
        ("item", ARTICLE, None),
        ("item", ARTICLE, None),                                                # same URL, fragment dropped
        ("item", f"{WWW}/Regionales/puerto-separan-cargas?ref=listado", None),  # query kept
        ("item", f"{MOBILE}/amp/Economia/Puerto-crecimiento-2026.html", None),  # scheme-relative
        ("item", "https://red-social.test/compartir?u=x", None),
        ("item", None, "no_link"),
        ("item", None, "invalid_url"),                                          # a space in the href
    ]
    assert parsed.entries[3].hints == {"title": "El crecimiento del puerto obliga a separar cargas"}
    assert not any("contenido" in (e.url_raw or "") for e in parsed.entries)  # a bare #anchor lists nothing


@pytest.mark.parametrize(
    "body, problem",
    [(b"", "empty_document"), (b"   \n", "empty_document"), (b"not xml at all", "invalid_xml"),
     (b"<?xml version='1.0'?><opml><body/></opml>", "unknown_root_element: opml"),
     (b"<?xml version='1.0'?><!DOCTYPE rss [<!ENTITY a 'aaaa'>]><rss><channel><item><link>&a;</link></item></channel></rss>",
      "dtd_or_entity_declaration_refused")],
)
def test_unparseable_documents_are_an_outcome_with_a_reason(body, problem):
    parsed = D.parse_channel_document(body, document_url=f"{WWW}/x")
    assert parsed.outcome == "UNPARSEABLE" and parsed.entries == () and parsed.problems[0].startswith(problem)


def test_malformed_xml_yields_nothing_rather_than_half_a_feed():
    parsed = parse("malformed.xml")
    assert parsed.outcome == "UNPARSEABLE" and parsed.entries == () and parsed.problems[0].startswith("invalid_xml")


def test_namespace_variants_and_the_bytes_decide_the_format():
    rdf = (b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" '
           b'xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><title>t</title></channel>'
           b"<item><title>Uno</title><link>https://www.diario-ejemplo.test/uno</link><dc:date>2026-10-01</dc:date></item></rdf:RDF>")
    parsed = D.parse_channel_document(rdf, document_url=f"{WWW}/rdf")
    assert parsed.format == "rss" and [(e.url, e.hints["published"]) for e in parsed.entries] == [(f"{WWW}/uno", "2026-10-01")]
    bare = b"<urlset><url><loc>https://www.diario-ejemplo.test/a</loc></url></urlset>"  # no namespace
    assert [e.url for e in D.parse_channel_document(bare, document_url=WWW).entries] == [f"{WWW}/a"]
    prefixed = (b'<s:urlset xmlns:s="http://www.sitemaps.org/schemas/sitemap/0.9"><s:url><s:loc>https://www.diario-ejemplo.test/b'
                b"</s:loc></s:url></s:urlset>")
    assert [e.url for e in D.parse_channel_document(prefixed, document_url=WWW).entries] == [f"{WWW}/b"]
    # a feed served as text/html is still a feed; a page served as text/xml is still a page
    assert parse("rss.xml", content_type="text/html").format == "rss"
    assert parse("listing.html", content_type="text/xml").format == "html_listing"
    assert D.parse_channel_document(b"<p>suelto <a href='/x'>x</a>", document_url=WWW, declared_content_type="text/html").format == "html_listing"


def test_parsing_is_deterministic():
    for name in ("rss.xml", "atom.xml", "sitemap_urlset.xml", "sitemap_index.xml", "listing.html"):
        assert parse(name) == parse(name)


# --- events and candidates ------------------------------------------------------------------------


def test_events_record_what_was_listed_and_candidates_fold_by_url_key(tmp_path):
    tables, provider, result = run(tmp_path, f"{WWW}/rss.xml", {f"{WWW}/rss.xml": "rss.xml", f"{WWW}/rss.xml?page=2": "rss_page2.xml"})
    assert provider.asked == [(f"{WWW}/rss.xml", 0), (f"{WWW}/rss.xml?page=2", 1)]
    assert (result.documents_read, result.events_new, result.stopped_by) == (2, 10, [])
    events = list(tables.events.values())
    assert len({e["event_id"] for e in events}) == 10 and all(e["event_id"].startswith("de1:") for e in events)
    # two items of the feed list the same article under different tracking parameters: two events, one candidate
    assert events[0]["url_key"] == events[1]["url_key"] == ARTICLE and events[0]["candidate_id"] == events[1]["candidate_id"]
    assert events[0]["observed_url"] != events[1]["observed_url"]
    assert [tables.candidates[c]["url_key"] for c in result.candidates_new] == [
        ARTICLE, f"{WWW}/Regionales/puerto-separan-cargas", f"{WWW}/breves/123", f"{WWW}/docs/informe.pdf"]
    assert tables.candidates[result.candidates_new[0]]["fetch_url"] == f"{ARTICLE}?utm_source=rss&utm_medium=feed"
    problems = [e["problem"] for e in events if e["relation"] == "item"]
    assert problems == [None, None, None, "no_link", None, "off_origin", "not_http", None]
    event = events[0]
    assert {"run_id", "channel_id", "outlet_id", "input_fetch_id", "position", "relation", "observed_url", "resolved_url",
            "hints", "discovered_at", "parser"} <= set(event)
    assert (event["parser"], event["discovered_at"], event["input_fetch_id"]) == (
        "channel-parser/1", "2026-10-07T12:00:00.000000Z", fid(f"{WWW}/rss.xml"))
    assert [(i["format"], i["outcome"], i["depth"], i["entries"]) for i in tables.inputs] == [
        ("rss", "PARSED", 0, 8), ("rss", "PARSED", 1, 2)]
    assert tables.inputs[1]["parent_fetch_id"] == fid(f"{WWW}/rss.xml")
    assert any("cycle_or_repeat_not_followed" in note for note in result.notes)  # page 2 points back at page 1


def test_discovery_creates_no_document_and_fetches_no_candidate(tmp_path):
    tables, provider, _ = run(tmp_path, f"{WWW}/rss.xml", {f"{WWW}/rss.xml": "rss.xml"})
    assert sorted(p.name for p in (tmp_path / "discovery").iterdir()) == ["candidates.jsonl", "events.jsonl", "inputs.jsonl"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["discovery"]        # no pack, no identity table, no layer
    assert {url for url, _ in provider.asked} == {f"{WWW}/rss.xml", f"{WWW}/rss.xml?page=2"}  # channel documents only


def test_the_same_url_from_two_channels_is_two_sets_of_events_and_one_candidate(tmp_path):
    documents = {f"{WWW}/rss.xml": "rss.xml", f"{WWW}/atom.xml": "atom.xml"}
    tables, _, first = run(tmp_path, f"{WWW}/rss.xml", documents)
    second = D.discover_channel(tables, RULES, channel_id=f"{OUTLET}:ch:atom_001", start_url=f"{WWW}/atom.xml",
                                provider=Recorded(documents), budget=BUDGET, run_id="acq1-20261007T120000000000Z-000000000000",
                                discovered_at=T0)
    assert second.candidates_new == []                                # the AMP link folds to the article, the brief is known
    assert second.candidates_listed == [first.candidates_new[0], first.candidates_new[2]]
    article_events = [e for e in tables.events.values() if e["url_key"] == ARTICLE]
    assert {e["channel_id"] for e in article_events} == {CHANNEL, f"{OUTLET}:ch:atom_001"} and len(article_events) == 3
    assert tables.candidates[first.candidates_new[0]]["first_channel_id"] == CHANNEL  # first listing stays first


def test_discovery_is_reproducible_and_idempotent(tmp_path):
    documents = {f"{WWW}/rss.xml": "rss.xml", f"{WWW}/rss.xml?page=2": "rss_page2.xml"}
    tables, _, first = run(tmp_path / "a", f"{WWW}/rss.xml", documents)
    _, _, other = run(tmp_path / "b", f"{WWW}/rss.xml", documents)
    for name in ("inputs.jsonl", "events.jsonl", "candidates.jsonl"):
        assert (tmp_path / "a" / "discovery" / name).read_bytes() == (tmp_path / "b" / "discovery" / name).read_bytes()
    before = {p.name: p.read_bytes() for p in (tmp_path / "a" / "discovery").iterdir()}
    again = D.discover_channel(D.DiscoveryTables(tmp_path / "a" / "discovery"), RULES, channel_id=CHANNEL,
                               start_url=f"{WWW}/rss.xml", provider=Recorded(documents), budget=BUDGET,
                               run_id="acq1-20261007T120000000000Z-000000000000", discovered_at=T0)
    assert (again.events_new, again.events_seen, again.candidates_new) == (0, 10, [])
    assert again.candidates_listed == first.candidates_listed
    assert {p.name: p.read_bytes() for p in (tmp_path / "a" / "discovery").iterdir()} == before


def test_a_changed_channel_document_is_a_new_input_with_new_events(tmp_path):
    tables, _, _ = run(tmp_path, f"{WWW}/rss.xml", {f"{WWW}/rss.xml": "rss_page2.xml"})
    changed = fixture("rss_page2.xml").replace(b"informe.pdf", b"informe-2.pdf")

    def provider(url, depth):
        return D.ChannelDocument(url, url, fid(url + "#later"), changed) if url == f"{WWW}/rss.xml" else D.DocumentUnavailable(url, "x")

    later = D.discover_channel(tables, RULES, channel_id=CHANNEL, start_url=f"{WWW}/rss.xml", provider=provider,
                               budget=BUDGET, run_id="acq1-20261008T120000000000Z-000000000000", discovered_at=T0)
    assert later.events_new == 2 and len(later.candidates_new) == 1 and len(tables.inputs) == 2


# --- expansion, cycles, budgets -------------------------------------------------------------------

SITEMAPS = {
    f"{WWW}/sitemap_index.xml": "sitemap_index.xml",
    f"{WWW}/sitemaps/2026-10.xml": "sitemap_urlset.xml",
    f"{WWW}/sitemaps/anidado.xml": "sitemap_nested_index.xml",
    f"{WWW}/sitemaps/profundo.xml": b"<urlset><url><loc>https://www.diario-ejemplo.test/profundo/1</loc></url></urlset>",
}


def test_sitemap_index_is_expanded_breadth_first_and_cycles_are_recorded_not_followed(tmp_path):
    tables, provider, result = run(tmp_path, f"{WWW}/sitemap_index.xml", SITEMAPS,
                                   channel=f"{OUTLET}:ch:sitemap_001")
    assert provider.asked == [(f"{WWW}/sitemap_index.xml", 0), (f"{WWW}/sitemaps/2026-10.xml", 1),
                              (f"{WWW}/sitemaps/anidado.xml", 1), (f"{WWW}/sitemaps/profundo.xml", 2)]
    assert result.stopped_by == [] and result.documents_read == 4
    # listed twice in the index, the index naming itself, the nested index naming the top index
    assert len([n for n in result.notes if n.startswith("cycle_or_repeat_not_followed")]) == 3
    assert [tables.candidates[c]["url_key"] for c in result.candidates_new] == [
        f"{WWW}/Economia/Puerto-crecimiento-2026.html", f"{WWW}/Regionales/puerto-separan-cargas",
        f"{WWW}/Deportes/Final", f"{WWW}/deportes/final", f"{WWW}/profundo/1"]  # path case keeps two candidates apart
    assert [e["relation"] for e in tables.events.values()].count("child_document") == 6
    assert all(e["candidate_id"] is None for e in tables.events.values() if e["relation"] == "child_document")


@pytest.mark.parametrize(
    "budget, stopped, documents, candidates",
    [(D.DiscoveryBudget(0, 20, 100, 10**6), ["max_depth"], 1, 0),
     (D.DiscoveryBudget(1, 20, 100, 10**6), ["max_depth"], 3, 4),
     (D.DiscoveryBudget(3, 2, 100, 10**6), ["max_documents"], 2, 4),
     (D.DiscoveryBudget(3, 20, 3, 10**6), ["max_candidates"], 4, 3),
     (D.DiscoveryBudget(3, 20, 100, 700), ["max_bytes"], 1, 0),
     (D.DiscoveryBudget(3, 0, 100, 10**6), ["max_documents"], 0, 0)],
)
def test_every_budget_stops_expansion_and_says_so(tmp_path, budget, stopped, documents, candidates):
    tables, provider, result = run(tmp_path, f"{WWW}/sitemap_index.xml", SITEMAPS, budget=budget,
                                   channel=f"{OUTLET}:ch:sitemap_001")
    assert (result.stopped_by, result.documents_read, len(result.candidates_new)) == (stopped, documents, candidates)
    assert len(provider.asked) <= max(budget.max_documents, 1) + 1 and result.bytes_read <= budget.max_bytes


def test_a_budget_has_no_default_and_no_negative(tmp_path):
    with pytest.raises(TypeError):
        D.DiscoveryBudget(max_depth=1)
    with pytest.raises(D.DiscoveryError):
        D.DiscoveryBudget(-1, 1, 1, 1)
    with pytest.raises(D.DiscoveryError):
        run(tmp_path, f"{WWW}/rss.xml", {}, channel="uy_otro:ch:rss_001")


def test_an_endless_pagination_is_cut_by_the_budget(tmp_path):
    class Endless:
        asked = 0

        def __call__(self, url, depth):
            Endless.asked += 1
            page = int(url.rsplit("=", 1)[1]) if "=" in url else 1
            body = (f'<feed xmlns="http://www.w3.org/2005/Atom"><link rel="next" href="/atom?p={page + 1}"/>'
                    f'<entry><link href="/nota/{page}"/></entry></feed>').encode()
            return D.ChannelDocument(url, url, fid(url), body)

    tables = D.DiscoveryTables(tmp_path / "discovery")
    result = D.discover_channel(tables, RULES, channel_id=CHANNEL, start_url=f"{WWW}/atom", provider=Endless(),
                                budget=D.DiscoveryBudget(50, 7, 100, 10**6), run_id="acq1-20261007T120000000000Z-000000000000",
                                discovered_at=T0)
    assert (Endless.asked, result.documents_read, result.stopped_by, len(result.candidates_new)) == (7, 7, ["max_documents"], 7)


# --- failures are evidence -------------------------------------------------------------------------


def test_unavailable_and_unparseable_documents_are_recorded_inputs(tmp_path):
    documents = {f"{WWW}/sitemap_index.xml": "sitemap_index.xml", f"{WWW}/sitemaps/2026-10.xml": "malformed.xml"}
    tables, _, result = run(tmp_path, f"{WWW}/sitemap_index.xml", documents, channel=f"{OUTLET}:ch:sitemap_001")
    assert [(i["document_url"].rsplit("/", 1)[1], i["outcome"]) for i in tables.inputs] == [
        ("sitemap_index.xml", "PARSED"), ("2026-10.xml", "UNPARSEABLE"), ("anidado.xml", "UNAVAILABLE")]
    assert tables.inputs[1]["problems"][0].startswith("invalid_xml") and tables.inputs[2]["problems"] == ["http_404"]
    assert result.candidates_new == [] and tables.candidates == {}  # half a feed yields no candidate
    assert tables.inputs[1]["body_sha256"] == hashlib.sha256(fixture("malformed.xml")).hexdigest()


def test_a_compressed_channel_document_is_decoded_for_reading_only(tmp_path):
    compressed = gzip.compress(fixture("sitemap_urlset.xml"), mtime=0)

    def provider(url, depth):
        return D.ChannelDocument(url, url, fid(url), compressed, "application/xml", "gzip")

    tables = D.DiscoveryTables(tmp_path / "discovery")
    result = D.discover_channel(tables, RULES, channel_id=CHANNEL, start_url=f"{WWW}/sitemap.xml.gz", provider=provider,
                                budget=BUDGET, run_id="acq1-20261007T120000000000Z-000000000000", discovered_at=T0)
    assert len(result.candidates_new) == 4 and tables.inputs[0]["body_sha256"] == hashlib.sha256(compressed).hexdigest()

    def broken(url, depth):
        return D.ChannelDocument(url, url, fid(url), compressed[:40], "application/xml", "gzip")

    tables2 = D.DiscoveryTables(tmp_path / "other")
    D.discover_channel(tables2, RULES, channel_id=CHANNEL, start_url=f"{WWW}/sitemap.xml.gz", provider=broken,
                       budget=BUDGET, run_id="acq1-20261007T120000000000Z-000000000000", discovered_at=T0)
    assert (tables2.inputs[0]["outcome"], tables2.inputs[0]["problems"]) == ("UNPARSEABLE", ["undecodable_content_encoding"])


def test_a_redirected_channel_document_resolves_against_where_it_came_from_and_rewrites_nothing(tmp_path):
    def provider(url, depth):
        return D.ChannelDocument(url, f"{WWW}/feeds/atom.xml", fid(url), fixture("atom.xml"))

    tables = D.DiscoveryTables(tmp_path / "discovery")
    D.discover_channel(tables, RULES, channel_id=CHANNEL, start_url=f"{WWW}/old-feed", provider=provider, budget=BUDGET,
                       run_id="acq1-20261007T120000000000Z-000000000000", discovered_at=T0)
    assert tables.inputs[0]["document_url"] == f"{WWW}/old-feed" and tables.inputs[0]["final_url"] == f"{WWW}/feeds/atom.xml"
    assert [e["resolved_url"] for e in tables.events.values()][1] == f"{WWW}/breves/123"  # ../breves relative to /feeds/


def test_same_canonical_input_gives_the_same_candidate(tmp_path):
    variants = [ARTICLE, f"{ARTICLE}?utm_source=a", f"{ARTICLE}#x", f"{MOBILE}/amp/Economia/Puerto-crecimiento-2026.html",
                "HTTPS://WWW.DIARIO-EJEMPLO.TEST/Economia/Puerto-crecimiento-2026.html"]
    body = ("<urlset>" + "".join(f"<url><loc>{u.replace('&', '&amp;')}</loc></url>" for u in variants) + "</urlset>").encode()
    tables, _, result = run(tmp_path, f"{WWW}/s.xml", {f"{WWW}/s.xml": body})
    assert len(result.candidates_new) == 1 and result.events_new == 5
    assert D.candidate_id(OUTLET, ARTICLE) == result.candidates_new[0]
