"""Source structures beyond the first canary's (decision CPD-0020): feed families, a candidate budget
that keeps the newest, HTML archives with pagination and dated teasers, an index read incrementally,
and a listing outlet taken end to end.

**Every document here is synthetic** — written for the test after structures that research describes
(RSS 1.0, Atom, Arc-style and WordPress-style feeds, yearly archives with numbered pages). None is a
recorded answer of a publisher and none says how any real outlet behaves.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from coprepan import acquisition, candidate_filter, canary_driver as D, core_pipeline as C, discovery, discovery_coverage as DC
from coprepan import fetcher as F, http_acquisition as H, outage_spool, policy as P, registry as R
from coprepan.crawler_identity import loopback_test_identity
from support_http import FakeClock, LocalSite, Response
from test_discovery import CHANNEL, RULES, fid
from test_fetcher import HTML, OUTLET, WWW
from test_offline_e2e import SCHEDULE, XML

T0 = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
RUN = "acq1-20261009T120000000000Z-00000000000{n}"


def parse(body, url=f"{WWW}/feed/", content_type="unknown"):
    return discovery.parse_channel_document(body.encode("utf-8") if isinstance(body, str) else body, document_url=url,
                                            declared_content_type=content_type)


def discover(tmp_path, documents, start, budget, n=0, tables=None):
    tables = tables or discovery.DiscoveryTables(tmp_path / "discovery")
    asked = []

    def provider(url, depth):
        asked.append(url)
        body = documents.get(url)
        if body is None:
            return discovery.DocumentUnavailable(url, "http_404")
        return discovery.ChannelDocument(url, url, fid(f"{url}|{n}"), body.encode("utf-8") if isinstance(body, str) else body)

    result = discovery.discover_channel(tables, RULES, channel_id=CHANNEL, start_url=start, provider=provider, budget=budget,
                                        run_id=RUN.format(n=n), discovered_at=T0)
    return tables, result, asked


# --- feed families -------------------------------------------------------------------------------------

RSS_1_0 = f"""<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel rdf:about="{WWW}/"><title>Diario Ejemplo</title><link>{WWW}/</link></channel>
  <item rdf:about="{WWW}/nacional/uno"><title>Uno</title><link>{WWW}/nacional/uno</link><dc:date>2026-10-09T08:15:00-03:00</dc:date></item>
  <item rdf:about="{WWW}/nacional/dos"><title>Dos &amp; medio</title><link>{WWW}/nacional/dos</link><dc:date>2026-10-08</dc:date></item>
</rdf:RDF>"""

ATOM = f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="es"><title>Diario Ejemplo</title>
  <entry><title>Tres</title><link rel="alternate" href="/mundo/tres"/><link rel="enclosure" href="/media/tres.mp3"/>
    <id>tag:diario-ejemplo.test,2026:3</id><updated>2026-10-09</updated><category term="mundo"/></entry>
  <entry><title>Cuatro</title><link href="{WWW}/mundo/cuatro"/><id>tag:diario-ejemplo.test,2026:4</id>
    <published>2026-10-07T23:59:59Z</published><updated>2026-10-08T01:00:00Z</updated></entry>
</feed>"""

ARC_STYLE = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/" version="2.0">
<channel><title><![CDATA[Diario Ejemplo]]></title><link>{WWW}</link><atom:link href="{WWW}/arc/outboundfeeds/rss/?outputType=xml" rel="self"/>
<item><title><![CDATA[Cinco: "comillas" & más]]></title><link>{WWW}/politica/2026/10/09/cinco/</link>
  <guid isPermaLink="true">{WWW}/politica/2026/10/09/cinco/</guid><pubDate>Fri, 09 Oct 2026 14:05:00 +0000</pubDate>
  <content:encoded><![CDATA[<p>Texto inventado.</p><a href="{WWW}/galeria/1">galería</a>]]></content:encoded>
  <media:content url="{WWW}/resizer/foto.jpg" type="image/jpeg"/></item>
<item><title>Seis</title><link>https://otro-sitio.test/externo/seis</link><pubDate>Fri, 09 Oct 2026 13:00:00 +0000</pubDate></item>
</channel></rss>"""


def test_rss_1_0_atom_and_arc_style_feeds_yield_item_addresses_and_dates_and_nothing_else():
    rdf = parse(RSS_1_0)
    assert (rdf.outcome, rdf.format, [e.url for e in rdf.entries]) == ("PARSED", "rss", [f"{WWW}/nacional/uno", f"{WWW}/nacional/dos"])
    assert [e.hints["published"] for e in rdf.entries] == ["2026-10-09T08:15:00-03:00", "2026-10-08"] and rdf.entries[1].hints["title"] == "Dos & medio"
    atom = parse(ATOM)
    assert (atom.format, [e.url for e in atom.entries]) == ("atom", [f"{WWW}/mundo/tres", f"{WWW}/mundo/cuatro"])       # the alternate link, not the enclosure
    assert atom.entries[0].hints == {"title": "Tres", "updated": "2026-10-09", "guid": "tag:diario-ejemplo.test,2026:3"}
    arc = parse(ARC_STYLE, url=f"{WWW}/arc/outboundfeeds/rss/?outputType=xml")
    assert [e.url for e in arc.entries] == [f"{WWW}/politica/2026/10/09/cinco/", "https://otro-sitio.test/externo/seis"]  # a link inside CDATA is content
    assert arc.entries[0].hints["title"] == 'Cinco: "comillas" & más'


def test_dates_of_every_family_are_read_for_ordering_with_and_without_a_time_or_an_offset():
    read = discovery.hint_instant
    assert read("2026-10-09T08:15:00-03:00") == datetime(2026, 10, 9, 11, 15, tzinfo=timezone.utc)
    assert read("2026-10-08") == datetime(2026, 10, 8, tzinfo=timezone.utc)                       # a date without a time: its midnight, UTC
    assert read("Fri, 09 Oct 2026 14:05:00 +0000") == datetime(2026, 10, 9, 14, 5, tzinfo=timezone.utc)
    assert read("2026-10-07T23:59:59Z") == datetime(2026, 10, 7, 23, 59, 59, tzinfo=timezone.utc)
    assert read("2026-10-09 10:00") == datetime(2026, 10, 9, 10, tzinfo=timezone.utc)             # no offset: read as UTC, for ordering only
    assert [read(text) for text in (None, "", "  ", "ayer", "09/10/2026", "2026-13-40")] == [None] * 6
    assert discovery.entry_instant({"updated": "2026-10-09", "lastmod": "2020-01-01"}) == datetime(2026, 10, 9, tzinfo=timezone.utc)


def test_a_feed_on_a_foreign_host_gives_candidates_only_for_the_outlets_own_addresses(tmp_path):
    tables, result, _ = discover(tmp_path, {"https://cdn.agregador.test/diario/rss/portada.xml": ARC_STYLE},
                                 "https://cdn.agregador.test/diario/rss/portada.xml", discovery.DiscoveryBudget(1, 2, 10, 10**6))
    assert [tables.candidates[c]["url_key"] for c in result.candidates_new] == [f"{WWW}/politica/2026/10/09/cinco/"]
    assert [e["problem"] for e in tables.events.values()] == [None, "off_origin"]                  # the foreign item is on record, not a candidate


def test_the_same_article_in_two_section_feeds_is_one_candidate_and_two_sets_of_events(tmp_path):
    feed = '<rss version="2.0"><channel>' + "".join(f"<item><link>{WWW}/nota/{n}?utm_source=rss</link></item>" for n in (1, 2)) + "</channel></rss>"
    other = '<rss version="2.0"><channel>' + "".join(f"<item><link>{WWW}/nota/{n}</link></item>" for n in (2, 3)) + "</channel></rss>"
    tables, first, _ = discover(tmp_path, {f"{WWW}/rss/portada.xml": feed}, f"{WWW}/rss/portada.xml", discovery.DiscoveryBudget(1, 2, 10, 10**6))
    _, second, _ = discover(tmp_path, {f"{WWW}/rss/politica.xml": other}, f"{WWW}/rss/politica.xml", discovery.DiscoveryBudget(1, 2, 10, 10**6), n=1, tables=tables)
    assert (len(first.candidates_new), len(second.candidates_new), len(tables.candidates), len(tables.events)) == (2, 1, 3, 4)


# --- F7: the candidate budget keeps the newest -----------------------------------------------------------


def mixed_sitemap(hours):
    """A news sitemap that is *not* newest-first, like the one of 2026-10-08."""
    rows = "".join(f"<url><loc>{WWW}/nota/{n}</loc><news:news><news:publication_date>2026-10-0{8 - h // 24}T{23 - h % 24:02d}:00:00-04:00"
                   f"</news:publication_date></news:news></url>" for n, h in enumerate(hours))
    return ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">'
            + rows + "<url><loc>" + WWW + "/sin-fecha/a</loc></url><url><loc>" + WWW + "/sin-fecha/b</loc></url></urlset>")


def test_when_a_listing_exceeds_the_budget_the_newest_dated_entries_become_candidates(tmp_path):
    hours = [5, 0, 30, 2, 47, 1, 12, 3, 40, 4, 20, 6]                            # age in hours, in document order
    tables, result, _ = discover(tmp_path, {f"{WWW}/sitemapnews": mixed_sitemap(hours)}, f"{WWW}/sitemapnews", discovery.DiscoveryBudget(1, 2, 6, 10**6))
    kept = sorted(int(tables.candidates[c]["url_key"].rsplit("/", 1)[1]) for c in result.candidates_new)
    assert kept == sorted(sorted(range(len(hours)), key=hours.__getitem__)[:6]) == [0, 1, 3, 5, 7, 9]
    assert result.stopped_by == ["max_candidates"]
    report = DC.coverage(tables)["channels"][CHANNEL]
    assert (report["item_entries"], report["item_entries_with_candidate"], report["item_entries_turned_away_by_candidate_budget"]) == (14, 6, 8)
    assert report["turned_away_newer_than_oldest_newly_kept"] == 0 == report["turned_away_newer_than_oldest_kept"]   # in document order: 6 and more
    assert report["item_entries_first_listing_their_candidate"] == 6
    # events are in document order whatever the allotment; the undated come after every dated entry
    assert [e["position"] for e in tables.events.values()] == list(range(14))
    assert [e["problem"] for e in tables.events.values()][-2:] == ["candidate_budget_exhausted"] * 2
    # a later pass over the same listing continues with the next newest, then the undated, and nothing is asked twice
    _, second, _ = discover(tmp_path, {f"{WWW}/sitemapnews": mixed_sitemap(hours)}, f"{WWW}/sitemapnews", discovery.DiscoveryBudget(1, 2, 6, 10**6), n=1, tables=tables)
    _, third, _ = discover(tmp_path, {f"{WWW}/sitemapnews": mixed_sitemap(hours)}, f"{WWW}/sitemapnews", discovery.DiscoveryBudget(1, 2, 6, 10**6), n=2, tables=tables)
    assert sorted(int(tables.candidates[c]["url_key"].rsplit("/", 1)[1]) for c in second.candidates_new) == [2, 4, 6, 8, 10, 11]
    assert [tables.candidates[c]["url_key"].rsplit("/", 2)[1] for c in third.candidates_new] == ["sin-fecha", "sin-fecha"] and third.stopped_by == []


def test_the_allotment_is_deterministic_and_a_listing_within_the_budget_is_untouched(tmp_path):
    hours = [3, 1, 2, 1, 3]                                                      # ties: document order decides
    first, r1, _ = discover(tmp_path / "a", {f"{WWW}/s": mixed_sitemap(hours)}, f"{WWW}/s", discovery.DiscoveryBudget(1, 2, 3, 10**6))
    second, r2, _ = discover(tmp_path / "b", {f"{WWW}/s": mixed_sitemap(hours)}, f"{WWW}/s", discovery.DiscoveryBudget(1, 2, 3, 10**6))
    assert r1.candidates_new == r2.candidates_new and [first.candidates[c]["url_key"].rsplit("/", 1)[1] for c in r1.candidates_new] == ["1", "2", "3"]
    whole, r3, _ = discover(tmp_path / "c", {f"{WWW}/s": mixed_sitemap(hours)}, f"{WWW}/s", discovery.DiscoveryBudget(1, 2, 7, 10**6))
    assert len(r3.candidates_new) == 7 and r3.stopped_by == []
    assert [whole.candidates[c]["url_key"].rsplit("/", 1)[1] for c in r3.candidates_new] == ["0", "1", "2", "3", "4", "a", "b"]   # document order


# --- HTML archives -------------------------------------------------------------------------------------


def archive(page, pages, *, base="/2026", marker="path", rel_next=False, per_page=3):
    """A yearly archive page in the manner of a WordPress theme: teasers in <article>, navigation, numbered pages."""
    def link(n):
        return f"{base}/page/{n}/" if marker == "path" else f"{base}/?page={n}"

    teasers = "".join(
        f'<article class="post"><a href="/2026/10/{10 - page:02d}/nota-{page}-{k}/"><img alt=""></a><h2><a href="/2026/10/{10 - page:02d}/nota-{page}-{k}/">'
        f'Nota {page}.{k}</a></h2><time datetime="2026-10-{10 - page:02d}T{9 + k:02d}:00:00-06:00">hace poco</time><a href="/autor/redaccion/">Redacción</a></article>'
        for k in range(per_page))
    numbers = "".join(f'<a class="page-numbers" href="{link(n) if n > 1 else base + "/"}">{n}</a>' for n in range(1, pages + 1) if n != page)
    rel = 'rel="next" ' if rel_next else ""
    following = f'<a class="next page-numbers" {rel}href="{link(page + 1)}">Siguiente</a>' if page < pages else ""
    return (f'<!doctype html><html><head><title>2026</title></head><body><nav><a href="/">Inicio</a><a href="/categoria/nacion/">Nación</a>'
            f'<a href="/contacto/">Contacto</a></nav><main>{teasers}</main><div class="pagination">{numbers}{following}</div>'
            f'<aside><a href="https://publicidad.test/anuncio">Anuncio</a><a href="/2026/10/01/la-mas-leida/">La más leída</a></aside></body></html>')


@pytest.mark.parametrize("marker, rel_next", [("path", False), ("query", False), ("path", True)])
def test_a_paginated_archive_is_followed_page_by_page_within_the_budget(tmp_path, marker, rel_next):
    url = (lambda n: f"{WWW}/2026/" if n == 1 else (f"{WWW}/2026/page/{n}/" if marker == "path" else f"{WWW}/2026/?page={n}"))
    documents = {url(n): archive(n, 5, marker=marker, rel_next=rel_next) for n in range(1, 6)}
    tables, result, asked = discover(tmp_path, documents, f"{WWW}/2026/", discovery.DiscoveryBudget(2, 4, 100, 10**6))
    assert asked == [url(1), url(2), url(3)]                                     # depth 2 ends it: page by page, never page 5 from page 1
    assert result.stopped_by == ["max_depth"] and result.not_read == [{"url": url(4), "reason": "max_depth"}]
    nexts = [e for e in tables.events.values() if e["relation"] == "next_page"]
    assert [e["resolved_url"] for e in nexts] == [url(2), url(3), url(4)] and all(e["candidate_id"] is None for e in nexts)
    articles = sorted(c["url_key"] for c in tables.candidates.values() if "/nota-" in c["url_key"])
    assert len(articles) == 9 and articles[0] == f"{WWW}/2026/10/07/nota-3-0/"
    # the teaser's own <time> is the date hint of the article's links, and of nothing outside the <article>
    dated = {e["resolved_url"]: e["hints"].get("published") for e in tables.events.values() if e["relation"] == "item"}
    assert dated[f"{WWW}/2026/10/09/nota-1-2/"] == "2026-10-09T11:00:00-06:00" and dated[f"{WWW}/autor/redaccion/"] is not None   # inside an <article>
    assert dated[f"{WWW}/contacto/"] is None and dated[f"{WWW}/2026/10/01/la-mas-leida/"] is None


def test_what_is_and_is_not_the_next_page():
    page = discovery._listing_page
    assert page(f"{WWW}/2026/")[1] == 1 and page(f"{WWW}/2026/page/2/") == (page(f"{WWW}/2026/")[0], 2) == page(f"{WWW}/2026/page/2")
    assert page(f"{WWW}/noticias?page=3") == (page(f"{WWW}/noticias")[0], 3) and page(f"{WWW}/seccion/pagina/4/")[1] == 4
    assert page(f"{WWW}/?p=2")[1] == 1 and page(f"{WWW}/?p=2")[0] != page(f"{WWW}/")[0]            # `p` is an article id, not a page
    assert page(f"{WWW}/2026/page/2/")[0] != page(f"{WWW}/2025/page/2/")[0] and page("https://otro.test/2026/page/2/")[0] != page(f"{WWW}/2026/")[0]
    # a page that links only to page 3 and beyond has no next page; a link to another listing's page 2 is not it
    body = ('<html><body><a href="/2026/page/3/">3</a><a href="/2025/page/2/">2025</a><a href="/2026/10/09/nota/">Nota</a>'
            '<a href="/2026/page/1/">1</a></body></html>')
    parsed = parse(body, url=f"{WWW}/2026/", content_type="text/html")
    assert [e.relation for e in parsed.entries] == ["item"] * 4
    declared = parse('<html><head><link rel="next" href="/siguiente"></head><body><a href="/2026/page/2/">2</a></body></html>', url=f"{WWW}/2026/")
    assert [(e.relation, e.url) for e in declared.entries] == [("next_page", f"{WWW}/siguiente"), ("item", f"{WWW}/2026/page/2/")]  # what the page declares wins


def test_an_endless_archive_and_a_page_that_points_at_itself_end_at_the_budget(tmp_path):
    documents = {f"{WWW}/a/": '<html><body><a rel="next" href="/a/">más</a><a href="/n/1">n</a></body></html>'}
    _, result, asked = discover(tmp_path / "self", documents, f"{WWW}/a/", discovery.DiscoveryBudget(9, 9, 10, 10**6))
    assert asked == [f"{WWW}/a/"] and any(note.startswith("cycle_or_repeat_not_followed") for note in result.notes)

    class Endless(dict):
        def get(self, url, default=None):
            n = int(url.rsplit("/", 2)[1]) if "/page/" in url else 1
            return f'<html><body><a href="/n/{n}">n</a><a href="/z/page/{n + 1}/">sig</a></body></html>'

    _, result, asked = discover(tmp_path / "endless", Endless(), f"{WWW}/z/", discovery.DiscoveryBudget(50, 6, 100, 10**6))
    assert len(asked) == 6 and result.stopped_by == ["max_documents"] and len(result.candidates_new) == 6


# --- an index read incrementally --------------------------------------------------------------------------


def index(children):
    rows = "".join(f"<sitemap><loc>{WWW}/{name}</loc>" + (f"<lastmod>{lastmod}</lastmod>" if lastmod else "") + "</sitemap>" for name, lastmod in children)
    return f'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</sitemapindex>'


def urlset(paths):
    return '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>{WWW}{p}</loc></url>" for p in paths) + "</urlset>"


def test_a_child_read_before_and_stated_unchanged_is_not_asked_again_so_a_later_pass_moves_on(tmp_path):
    children = [(f"post-sitemap{n}.xml", f"2026-0{n}-01T00:00:00+00:00") for n in range(1, 8)] + [("sin-fecha.xml", None)]
    documents = {f"{WWW}/sitemap_index.xml": index(children), **{f"{WWW}/{name}": urlset([f"/de/{name}"]) for name, _ in children}}
    budget = discovery.DiscoveryBudget(2, 4, 100, 10**6)
    tables, first, asked1 = discover(tmp_path, documents, f"{WWW}/sitemap_index.xml", budget)
    assert [u.rsplit("/", 1)[1] for u in asked1[1:]] == ["post-sitemap7.xml", "post-sitemap6.xml", "post-sitemap5.xml"]
    # the same run, resumed, repeats its own requests: what it records is the same evidence (CPD-0009), nothing is skipped
    _, resumed, asked_again = discover(tmp_path, documents, f"{WWW}/sitemap_index.xml", budget, tables=tables)
    assert asked_again == asked1 and resumed.events_new == 0 and not [n for n in resumed.notes if n.startswith("unchanged_since_read")]
    _, second, asked2 = discover(tmp_path, documents, f"{WWW}/sitemap_index.xml", budget, n=1, tables=tables)
    assert [u.rsplit("/", 1)[1] for u in asked2[1:]] == ["post-sitemap4.xml", "post-sitemap3.xml", "post-sitemap2.xml"]   # continuation, no higher limit
    assert sum(1 for note in second.notes if note.startswith("unchanged_since_read_not_asked_again")) == 3
    # the newest child changes: it is read again, first; a child without a lastmod can never be called unchanged
    changed = dict(documents)
    changed[f"{WWW}/sitemap_index.xml"] = index([(name, "2026-10-09T00:00:00+00:00" if name == "post-sitemap7.xml" else lastmod) for name, lastmod in children])
    _, third, asked3 = discover(tmp_path, changed, f"{WWW}/sitemap_index.xml", budget, n=2, tables=tables)
    assert [u.rsplit("/", 1)[1] for u in asked3[1:]] == ["post-sitemap7.xml", "post-sitemap1.xml", "sin-fecha.xml"]
    _, fourth, asked4 = discover(tmp_path, changed, f"{WWW}/sitemap_index.xml", budget, n=3, tables=tables)
    assert [u.rsplit("/", 1)[1] for u in asked4[1:]] == ["sin-fecha.xml"] and len(tables.candidates) == 8
    assert DC.frontier(tables, CHANNEL) == []


def test_a_child_whose_reading_was_cut_by_the_candidate_budget_is_read_again(tmp_path):
    documents = {f"{WWW}/i.xml": index([("grande.xml", "2026-10-09T00:00:00+00:00")]), f"{WWW}/grande.xml": urlset([f"/n/{n}" for n in range(5)])}
    tables, first, _ = discover(tmp_path, documents, f"{WWW}/i.xml", discovery.DiscoveryBudget(2, 4, 3, 10**6))
    assert len(first.candidates_new) == 3 and discovery.read_unchanged(tables, CHANNEL) == {}
    _, second, asked = discover(tmp_path, documents, f"{WWW}/i.xml", discovery.DiscoveryBudget(2, 4, 3, 10**6), n=1, tables=tables)
    assert asked == [f"{WWW}/i.xml", f"{WWW}/grande.xml"] and len(second.candidates_new) == 2 and len(tables.candidates) == 5
    assert discovery.read_unchanged(tables, CHANNEL) == {f"{WWW}/grande.xml": "2026-10-09T00:00:00+00:00"}


# --- a listing outlet, end to end --------------------------------------------------------------------------

ARCHIVE = f"{OUTLET}:ch:archive_r001"
ALLOW = {OUTLET: {"version": f"{OUTLET}-candidate-rules/v1", "reject_path_prefixes": [], "reject_path_patterns": [],
                  "allow_path_patterns": [r"^/2026/[0-9]{2}/[0-9]{2}/nota-"]}}


def listing_registry() -> R.Registry:
    return R.validate_registry({"schema": "coprepan-outlet-registry/v1", "outlets": [{
        "outlet_id": OUTLET, "country_id": "uy", "registration_status": "registered",
        "display_names": [{"name": "Diario Ejemplo", "valid_from": "unknown", "valid_to": "not_applicable"}],
        "outlet_type": "unknown", "outlet_group": "unknown", "city": "unknown", "region": "unknown", "scope": "unknown",
        "access_model": "unknown", "medium": "unknown", "editions": [], "web_origins": [WWW], "timezone": "UTC",
        "same_outlet_basis": "not_applicable",
        "url_rules": {"version": f"{OUTLET}-url-rules/v1", "significant_query_params": [], "strip_path_prefixes": [], "strip_path_suffixes": []},
        "channels": [{"channel_id": ARCHIVE, "kind": "archive", "url_history": [{"url": f"{WWW}/2026/", "valid_from": "unknown"}], "legacy_observed": {}}],
        "legacy_aliases": [], "legacy_observed": {}, "review_notes": []}]})


class ListingRun:
    def __init__(self, base, site, start, rules=None):
        self.workspace = C.Workspace(base / "workspace")
        self.root, self.spool, self.rules = base / "preservation", base / "spool", rules
        for directory in (self.workspace.root, self.root, self.spool):
            directory.mkdir(parents=True, exist_ok=True)
        self.registry, self.clock, identity = listing_registry(), FakeClock(start), loopback_test_identity()
        limits = F.FetchLimits(timeout_seconds=2, max_redirects=3, max_body_bytes=500_000, max_attempts=1, backoff_base_seconds=2, backoff_max_seconds=60)
        self.fetcher = D.BudgetedFetcher(budget=D.CanaryBudget(outlets=1, item_requests_total=12, item_requests_per_outlet=12), identity=identity,
                                         gate=P.PolicyGate(P.loopback_test_policy(), self.registry, identity), limits=limits, clock=self.clock,
                                         sleep=self.clock.sleep, connect_override={WWW: ("127.0.0.1", site.port)})
        self.run = H.http_fetch_run(start, [OUTLET], {"driver": D.DRIVER_VERSION, "baseline_id": start.isoformat()}, identity)

    def go(self):
        return D.run_canary(self.workspace, self.registry, self.run, outlet_ids=[OUTLET], fetcher=self.fetcher, schedule_policy=SCHEDULE,
                            clock=self.clock, preservation_root=lambda: self.root, spool_root=lambda: self.spool,
                            spool_policy=outage_spool.SpoolPolicy(min_free_bytes=1, max_spool_bytes=1 << 30), candidate_rules=self.rules)


def test_a_listing_outlet_is_first_read_and_preserved_and_only_under_a_reviewed_rule_acquired(tmp_path):
    with LocalSite() as site:
        site.routes.update({"/robots.txt": Response(200, [("Content-Type", "text/plain")], b"User-agent: *\nDisallow:\n"),
                            "/2026/": Response(200, HTML, archive(1, 5).encode("utf-8")),
                            **{f"/2026/page/{n}/": Response(200, HTML, archive(n, 5).encode("utf-8")) for n in range(2, 6)}})
        for page in range(1, 6):
            for k in range(3):
                site.routes[f"/2026/10/{10 - page:02d}/nota-{page}-{k}/"] = Response(200, HTML, (
                    f"<html><body><nav>Inicio</nav><article><h1>Nota {page}.{k}</h1><p>Texto inventado de la nota {page}.{k}.</p></article></body></html>").encode())

        # 1. no rule: the archive is read page by page within the reserved budget, preserved — and nothing it names is requested
        first = ListingRun(tmp_path, site, T0)
        outcome = first.go()
        assert site.paths() == ["/robots.txt", "/2026/", "/2026/page/2/", "/2026/page/3/"]
        assert first.fetcher.used == {(OUTLET, D.OTHER): 2, (OUTLET, D.EXPANSION): 2}
        stage = outcome["outlets"][OUTLET]["stages"]["C_item_fetch"]
        # everything the archive lists waits; the site root and the archive itself are rejected by the generic rules as before
        assert stage["qualification"] == {"DEFERRED": stage["candidates_known"] - 2, "REJECTED": 2} and stage["candidates_requested"] == 0
        table = H.qualification_table(first.workspace)
        assert {row["reasons"][0] for row in table.rows.values() if row["decision"] == "DEFERRED"} == {candidate_filter.LISTING_NEEDS_RULE}
        states = first.workspace.ledger().states()
        assert len(states) == 4 and set(states.values()) == {"RAW_PRESERVED"}       # the listing pages are the evidence a rule is written from
        # 2. the rule can be derived from what is preserved: the candidates are on record with their addresses and dates
        tables = H.discovery_tables(first.workspace)
        assert sum(1 for c in tables.candidates.values() if "/nota-" in c["url_key"]) == 9 and len(tables.candidates) > 9

        # 3. a later canary with the reviewed rule: the articles and only the articles
        before = len(site.requests)
        second = ListingRun(tmp_path, site, datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc), rules=ALLOW)
        outcome = second.go()
        later = site.paths()[before:]
        items = [p for p in later if "/nota-" in p]
        assert sorted(items) == sorted(f"/2026/10/{10 - page:02d}/nota-{page}-{k}/" for page in (1, 2, 3) for k in range(3))
        assert not [p for p in later if p in ("/contacto/", "/categoria/nacion/", "/autor/redaccion/", "/") or "publicidad" in p or "la-mas-leida" in p]
        stage = outcome["outlets"][OUTLET]["stages"]["C_item_fetch"]
        assert stage["qualification"]["QUALIFIED"] == 9 and stage["candidates_requested"] == 9
        derived = outcome["outlets"][OUTLET]["stages"]["E_derive"]
        assert sum(v["extracted"] for v in derived.values() if "extracted" in v) == 9
        records = [r for r in D.fetch_records(second.workspace) if r["run_id"] == second.run.run_id and r["fetch_kind"] == acquisition.FETCH_KIND_ITEM]
        assert len(records) == 9 and all(second.workspace.ledger().states()[r["fetch_id"]] == "RAW_PRESERVED" for r in records)
        assert second.fetcher.used[(OUTLET, D.ITEM)] == 9 and len(site.requests) - before == second.fetcher.transport_calls
