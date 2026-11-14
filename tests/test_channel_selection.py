"""``channel-selection/2`` (CPD-0036): which registered channels a canary reads. Pure functions over registry-shaped records."""

from __future__ import annotations

from coprepan import canary_driver as D


def channel(cid, kind, url):
    return {"channel_id": f"x_o:ch:{cid}", "kind": kind, "url_history": [{"url": url, "valid_from": "unknown"}]}


def outlet(*channels):
    return {"outlet_id": "x_o", "channels": list(channels)}


def test_a_news_channel_is_read_before_an_archive_of_the_same_kind_listed_before_it():
    o = outlet(channel("s1", "sitemap", "https://w.test/sitemap.xml"), channel("i1", "sitemap_index", "https://w.test/megasitemap.xml"),
               channel("s2", "sitemap", "https://w.test/sitemapforgoogle.xml"))
    assert D.select_channels(o, (), 2) == ["x_o:ch:s2", "x_o:ch:i1"]
    assert D.select_channels(o, (), 3) == ["x_o:ch:s2", "x_o:ch:i1", "x_o:ch:s1"]


def test_the_kind_order_still_comes_first_and_the_registry_order_decides_among_equals():
    o = outlet(channel("s1", "sitemap", "https://w.test/news-sitemap.xml"), channel("r1", "rss", "https://w.test/feed"),
               channel("r2", "rss", "https://w.test/rss/portada.xml"), channel("r3", "rss", "https://w.test/other"))
    assert D.select_channels(o, (), 2) == ["x_o:ch:r2", "x_o:ch:s1"]           # rss before sitemap; the news rss first
    assert D.select_channels(o, (), 4) == ["x_o:ch:r2", "x_o:ch:s1", "x_o:ch:r1", "x_o:ch:r3"]


def test_a_url_pattern_with_a_placeholder_is_never_read_and_the_host_does_not_count_as_news():
    o = outlet(channel("p1", "section_page", "https://w.test/noticia/<id>-<slug>"), channel("p2", "section_page", "https://news.test/a"),
               channel("p3", "section_page", "https://news.test/noticias/"))
    assert D.select_channels(o, (), 3) == ["x_o:ch:p3", "x_o:ch:p2"]
    assert "x_o:ch:p1" not in D.select_channels(o, (), 4)


def test_a_disabled_channel_is_still_never_read_and_the_selection_is_deterministic():
    o = outlet(channel("s1", "sitemap", "https://w.test/news.xml"), channel("s2", "sitemap", "https://w.test/sitemap.xml"))
    assert D.select_channels(o, ["x_o:ch:s1"], 2) == ["x_o:ch:s2"]
    assert D.select_channels(o, (), 2) == D.select_channels(o, (), 2) == ["x_o:ch:s1", "x_o:ch:s2"]
    assert D.CHANNEL_SELECTION == "channel-selection/2"
