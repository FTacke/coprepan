"""Regression tests of the findings F1–F7 of the first real canary (2026-10-08; decision CPD-0019).

Each finding is reproduced with what the canary met, rebuilt for a loopback server or as bytes: a
robots file served gzip-coded, a JavaScript challenge that comes as a 307 without a `Location`, a
workspace that holds the candidates of two outlets, a sitemap index behind redirecting channel
documents, a feed that carries whole HTML documents in CDATA, a channel that answers 404, a listing
longer than the candidate budget. Nothing here asks a real server anything.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from coprepan import access_control as AC, acquisition, candidate_filter, canary_driver as D, core_pipeline as C, discovery
from coprepan import discovery_coverage as DC, fetcher as F, http_acquisition as H, outage_spool, policy as P, registry as R
from coprepan import robots as RB
from coprepan.crawler_identity import loopback_test_identity
from coprepan.storage_roots import CHECKOUT
from support_http import FakeClock, LocalSite, Response
from test_canary_driver import Drive, SMALL, feed, page, scripted
from test_discovery import BUDGET, CHANNEL, RULES, fid
from test_fetcher import HTML, OUTLET, PAGE, WWW, get, make_fetcher
from test_offline_e2e import SCHEDULE, XML

FIXTURES = Path(__file__).parent / "fixtures" / "qualification"
T0 = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
RUN_ID = "acq1-20261009T120000000000Z-000000000000"
OTHER_OUTLET, OTHER_WWW = "es_otro_diario", "https://www.otro-diario.test"
ROBOTS_TEXT = (b"# robots.txt\nUser-agent: *\nAllow: /\nDisallow: /privado/\nDisallow: /*.pdf$\n"
               b"Sitemap: https://www.diario-ejemplo.test/sitemap-news.xml\n")
PLAIN = [("Content-Type", "text/plain; charset=utf-8")]
# The headers of the recorded answer that matter: a redirect status, no `Location`, the proxy's name.
SUCURI_HEADERS = [("Content-Type", "text/html"), ("X-Sucuri-ID", "15022"), ("Server", "Sucuri/Cloudproxy")]


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture
def site():
    with LocalSite() as server:
        yield server


def test_the_qualification_fixtures_are_the_pinned_bytes():
    manifest = json.loads((FIXTURES / "MANIFEST.json").read_text(encoding="utf-8"))
    assert sorted(manifest["files"]) == sorted(p.name for p in FIXTURES.iterdir() if p.name != "MANIFEST.json")
    for name, pinned in manifest["files"].items():
        assert (hashlib.sha256(fixture(name)).hexdigest(), len(fixture(name))) == (pinned["sha256"], pinned["size_bytes"]), name


# --- F1: a robots file served with a content coding ---------------------------------------------------


def test_a_gzip_coded_robots_file_is_read_and_preserved_as_received(site):
    coded = gzip.compress(ROBOTS_TEXT, mtime=0)
    site.routes.update({"/robots.txt": Response(200, PLAIN + [("Content-Encoding", "gzip")], coded, chunked=True),
                        "/nota": Response(200, HTML, PAGE), "/privado/informe": Response(200, HTML, PAGE)})
    fetcher, _ = make_fetcher(site)
    allowed, denied = get(fetcher, "/nota"), get(fetcher, "/privado/informe")
    assert allowed.final == "FETCHED" and allowed.last.policy["robots_decision"] == "allowed"
    assert (denied.final, denied.decision.reasons, denied.decision.evidence["robots_rule"]) == ("DENIED", ("robots_disallow",), "disallow: /privado/")
    assert site.paths() == ["/robots.txt", "/nota"]
    # what is preserved and what the digest names are the bytes as received, not the decoded text
    assert [exchange.body for _, exchange in fetcher.robots_exchanges] == [coded]
    assert allowed.last.policy["robots_txt_sha256"] == hashlib.sha256(coded).hexdigest() != hashlib.sha256(ROBOTS_TEXT).hexdigest()
    assert allowed.decision.evidence["robots_sitemaps"] == ["https://www.diario-ejemplo.test/sitemap-news.xml"]
    assert site.requests[0][1]["accept-encoding"] == "gzip"


@pytest.mark.parametrize("coding, body", [("gzip", b"\x1f\x8b not a gzip stream"), ("gzip", gzip.compress(ROBOTS_TEXT, mtime=0)[:-12]),
                                          ("br", ROBOTS_TEXT)])
def test_a_robots_body_whose_coding_cannot_be_undone_holds_and_is_never_guessed(site, coding, body):
    site.routes.update({"/robots.txt": Response(200, PLAIN + [("Content-Encoding", coding)], body), "/nota": Response(200, HTML, PAGE)})
    fetcher, _ = make_fetcher(site)
    outcome = get(fetcher, "/nota")
    assert (outcome.final, outcome.decision.reasons) == ("DEFERRED", ("robots_parse_error",))
    assert site.paths() == ["/robots.txt"] and fetcher.robots_exchanges[0][1].body == body


def test_robots_evidence_reads_the_decoded_file_and_names_the_received_bytes():
    coded = gzip.compress(ROBOTS_TEXT, mtime=0)
    evidence = RB.evidence_from_response(200, coded, "gzip")
    assert not evidence.rules.parse_error and evidence.sha256 == hashlib.sha256(coded).hexdigest()
    assert evidence.rules.evaluate("anybot", "/privado/x") == ("disallowed", "disallow: /privado/")
    assert RB.evidence_from_response(200, coded).rules.parse_error            # the defect of 2026-10-08: parsed as received
    assert RB.evidence_from_response(200, ROBOTS_TEXT, "identity").rules.groups == evidence.rules.groups
    assert RB.PARSER_VERSION == "robots-parser/3"


# --- F2: the Sucuri JavaScript challenge ---------------------------------------------------------------


def test_the_challenge_of_2026_10_08_is_recognised_by_what_it_is_not_by_its_status():
    body = fixture("sucuri_challenge_307.html")
    for status in (307, 200, 403, 503):
        assert AC.classify_response(status, SUCURI_HEADERS, body) == AC.BOT_CHALLENGE, status
    assert AC.classify_response(307, SUCURI_HEADERS + [("Content-Encoding", "gzip")], gzip.compress(body)) == AC.BOT_CHALLENGE
    assert AC.BOT_CHALLENGE in AC.ORIGIN_HOLD and AC.CLASSIFIER_VERSION == "access-control/2"
    # an ordinary redirect answer and an ordinary small page are not challenges
    moved = b"<html><head><title>307 Temporary Redirect</title></head><body>The document has moved.</body></html>"
    assert AC.classify_response(307, [("Location", "/nueva")], moved) == AC.NONE_OBSERVED
    assert AC.classify_response(404, HTML, b"<html><body><p>No existe.</p></body></html>") == AC.NONE_OBSERVED
    # a long article that only mentions the protection by name is one neither
    article = b"<html><body><article>" + b"<p>Texto sobre sucuri_cloudproxy_js en una nota larga.</p>" * 900 + b"</article></body></html>"
    assert len(article) > 32 * 1024 and AC.classify_response(200, HTML, article) == AC.NONE_OBSERVED


def test_after_the_challenge_nothing_more_is_asked_of_the_origin_and_nothing_about_the_client_changes(site):
    site.routes.update({"/robots.txt": Response(200, PLAIN, b"User-agent: *\nCrawl-Delay: 3\n"),
                        "/rss": Response(307, SUCURI_HEADERS, fixture("sucuri_challenge_307.html")),
                        "/sitemap-news.xml": Response(404, HTML, b"<html><body>No encontrada</body></html>"), "/nota": Response(200, HTML, PAGE)})
    fetcher, clock = make_fetcher(site)                                         # three attempts are allowed by the limits
    outcome = get(fetcher, "/rss", fetch_kind=acquisition.FETCH_KIND_CHANNEL_DOCUMENT)
    assert len(outcome.attempts) == 1 and outcome.last.status == 307 and outcome.last.policy["access_class_observed"] == AC.BOT_CHALLENGE
    assert outcome.last.body == fixture("sucuri_challenge_307.html")           # the challenge page itself is the preserved evidence
    asked = list(site.paths())
    assert asked == ["/robots.txt", "/rss"]
    for path, kind in (("/sitemap-news.xml", acquisition.FETCH_KIND_CHANNEL_DOCUMENT), ("/nota", acquisition.FETCH_KIND_ITEM), ("/rss", acquisition.FETCH_KIND_CHANNEL_DOCUMENT)):
        later = get(fetcher, path, fetch_kind=kind)
        assert (later.final, later.decision.reasons, later.decision.acquisition_decision) == ("DENIED", ("access_control_observed",), "HOLD")
    assert site.paths() == asked and fetcher.access_holds == {WWW: AC.BOT_CHALLENGE}
    # no cookie, no second user agent, no script: the two requests that were made say the same thing
    assert all("cookie" not in headers for _, headers in site.requests)
    assert len({headers["user-agent"] for _, headers in site.requests}) == 1


def test_the_driver_does_not_read_the_second_channel_of_an_origin_that_challenged_the_first(tmp_path, site):
    scripted(site)
    site.routes["/rss.xml"] = Response(307, SUCURI_HEADERS, fixture("sucuri_challenge_307.html"))
    run = Drive(tmp_path / "challenged", site)
    run.go()
    assert site.paths() == ["/robots.txt", "/rss.xml"]                           # stage B and stage C asked nothing
    receipt = run.receipt()
    assert receipt["policy_layers"]["outlets_with_access_control"] == [OUTLET] and receipt["counts"]["items_fetched"] == 0
    assert receipt["refused"]["DENIED:access_control_observed"] >= 1
    held = [r for r in D.fetch_records(run.workspace) if r["policy"]["access_class_observed"] == AC.BOT_CHALLENGE]
    assert len(held) == 1 and run.states()[held[0]["fetch_id"]] == "RAW_PRESERVED"


def test_a_stored_answer_the_old_classifier_missed_holds_its_origin_when_it_is_read_again(tmp_path, site, monkeypatch):
    scripted(site)
    site.routes["/rss.xml"] = Response(307, SUCURI_HEADERS, fixture("sucuri_challenge_307.html"))
    with monkeypatch.context() as patch:                                         # the classifier of 2026-10-08 saw nothing
        patch.setattr(AC, "classify_response", lambda status, headers, body: AC.NONE_OBSERVED)
        first = Drive(tmp_path / "missed", site)
        first.go()
    assert "/sitemap_index.xml" in site.paths()                                  # the request that should not have been sent
    assert D.access_holds_from_evidence(first.workspace) == {}                   # the record says what was recorded …
    assert D.access_holds_from_evidence(first.workspace, reclassify=True) == {WWW: AC.BOT_CHALLENGE}   # … the stored answer says more
    before = len(site.requests)
    again = Drive(tmp_path / "missed", site, start=datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc))
    again.fetcher.access_holds.update(D.access_holds_from_evidence(again.workspace, reclassify=True))
    again.go()
    assert len(site.requests) == before                                          # a later canary asks that origin nothing
    assert [r["policy"]["access_class_observed"] for r in D.fetch_records(first.workspace) if r["response"]["status"] == 307] == ["none_observed"]


# --- F3: the candidates of another outlet ---------------------------------------------------------------


def two_outlets() -> R.Registry:
    def outlet(outlet_id, country, origin):
        return {"outlet_id": outlet_id, "country_id": country, "registration_status": "registered",
                "display_names": [{"name": outlet_id, "valid_from": "unknown", "valid_to": "not_applicable"}],
                "outlet_type": "unknown", "outlet_group": "unknown", "city": "unknown", "region": "unknown", "scope": "unknown",
                "access_model": "unknown", "medium": "unknown", "editions": [], "web_origins": [origin], "timezone": "UTC",
                "same_outlet_basis": "not_applicable",
                "url_rules": {"version": f"{outlet_id}-url-rules/v1", "significant_query_params": [], "strip_path_prefixes": [], "strip_path_suffixes": []},
                "channels": [{"channel_id": f"{outlet_id}:ch:rss_001", "kind": "rss",
                              "url_history": [{"url": f"{origin}/rss.xml", "valid_from": "unknown"}], "legacy_observed": {}}],
                "legacy_aliases": [], "legacy_observed": {}, "review_notes": []}
    return R.validate_registry({"schema": "coprepan-outlet-registry/v1",
                                "outlets": [outlet(OTHER_OUTLET, "es", OTHER_WWW), outlet(OUTLET, "uy", WWW)]})


def serve(site, origin, paths):
    items = "".join(f"<item><link>{origin}{path}</link></item>" for path in paths)
    site.routes.update({"/robots.txt": Response(200, PLAIN, b"User-agent: *\nDisallow:\n"),
                        "/rss.xml": Response(200, XML, f'<rss version="2.0"><channel>{items}</channel></rss>'.encode())})
    site.routes.update({path: page(n) for n, path in enumerate(paths)})


class TwoOutlets:
    def __init__(self, base, first, second, *, budget):
        self.workspace = C.Workspace(base / "workspace")
        self.root, self.spool = base / "preservation", base / "spool"
        for directory in (self.workspace.root, self.root, self.spool):
            directory.mkdir(parents=True, exist_ok=True)
        self.registry, self.clock, self.identity = two_outlets(), FakeClock(T0), loopback_test_identity()
        gate = P.PolicyGate(P.loopback_test_policy(), self.registry, self.identity)
        limits = F.FetchLimits(timeout_seconds=2, max_redirects=3, max_body_bytes=500_000, max_attempts=1, backoff_base_seconds=2, backoff_max_seconds=60)
        self.fetcher = D.BudgetedFetcher(budget=budget, identity=self.identity, gate=gate, limits=limits, clock=self.clock, sleep=self.clock.sleep,
                                         connect_override={WWW: ("127.0.0.1", first.port), OTHER_WWW: ("127.0.0.1", second.port)})
        self.run = H.http_fetch_run(T0, [OUTLET, OTHER_OUTLET], {"driver": D.DRIVER_VERSION}, self.identity)

    def go(self):
        return D.run_canary(self.workspace, self.registry, self.run, outlet_ids=[OUTLET, OTHER_OUTLET], fetcher=self.fetcher,
                            schedule_policy=SCHEDULE, clock=self.clock, preservation_root=lambda: self.root, spool_root=lambda: self.spool,
                            spool_policy=outage_spool.SpoolPolicy(min_free_bytes=1, max_spool_bytes=1 << 30))


def test_each_outlet_plans_requests_and_spends_its_budget_only_its_own_candidates(tmp_path):
    budget = D.CanaryBudget(outlets=2, item_requests_total=6, item_requests_per_outlet=3)
    with LocalSite() as first, LocalSite() as second:
        serve(first, WWW, [f"/a/{n}" for n in range(5)])
        serve(second, OTHER_WWW, [f"/b/{n}" for n in range(2)])
        both = TwoOutlets(tmp_path, first, second, budget=budget)
        outcome = both.go()
        rows = H.request_rows(both.workspace)
        planned = [row for row in rows if row["event"] == H.EVENT_PLANNED]
        # every planned request is for a URL of the outlet it was planned for, and for a candidate of that outlet
        origin_of = {OUTLET: WWW, OTHER_OUTLET: OTHER_WWW}
        assert all(row["url"].startswith(origin_of[row["outlet_id"]] + "/") for row in planned)
        assert all(row["candidate_id"].startswith(row["outlet_id"] + ":cand:") for row in planned if row["candidate_id"])
        assert not [row for row in rows if row["event"] == H.EVENT_FINISHED and "off_origin" in row["policy_reasons"]]
        # no server was asked for the other outlet's pages, and nothing was asked twice
        assert all(not path.startswith("/b/") for path in first.paths()) and all(not path.startswith("/a/") for path in second.paths())
        assert len(first.paths()) == len(set(first.paths())) and len(second.paths()) == len(set(second.paths()))
        # the budget of each outlet is spent on its own candidates: 3 of 5, and both of 2
        assert len([p for p in first.paths() if p.startswith("/a/")]) == 3
        assert sorted(p for p in second.paths() if p.startswith("/b/")) == ["/b/0", "/b/1"]
        assert both.fetcher.used == {(OUTLET, D.OTHER): 2, (OUTLET, D.ITEM): 3, (OTHER_OUTLET, D.OTHER): 2, (OTHER_OUTLET, D.ITEM): 2}
        assert D.tally_from_evidence(both.workspace) == both.fetcher.used
        stages = outcome["outlets"]
        assert stages[OUTLET]["stages"]["C_item_fetch"]["candidates_known"] == 5
        assert stages[OTHER_OUTLET]["stages"]["C_item_fetch"]["candidates_known"] == 2
        assert stages[OTHER_OUTLET]["stages"]["C_item_fetch"]["qualification"] == {"QUALIFIED": 2}
        # the qualification table holds one outlet's decisions per outlet run, never the other's
        decided = H.qualification_table(both.workspace)
        assert {row["outlet_id"] for row in candidates_decided(decided, both)} == {OUTLET, OTHER_OUTLET}
        assert len(first.requests) + len(second.requests) == both.fetcher.transport_calls == sum(both.fetcher.used.values())


def candidates_decided(table, both):
    tables = H.discovery_tables(both.workspace)
    return [row for identifier in tables.candidates for row in table.history(identifier)]


def test_an_outlet_run_in_a_workspace_full_of_another_outlets_candidates_requests_none_of_them(tmp_path):
    budget = D.CanaryBudget(outlets=2, item_requests_total=20, item_requests_per_outlet=10)
    with LocalSite() as first, LocalSite() as second:
        serve(first, WWW, [f"/a/{n}" for n in range(8)])
        serve(second, OTHER_WWW, [])                                             # the second outlet lists nothing
        both = TwoOutlets(tmp_path, first, second, budget=budget)
        both.go()
        assert second.paths() == ["/robots.txt", "/rss.xml"]
        assert both.fetcher.used[(OTHER_OUTLET, D.ITEM)] == 0 and both.fetcher.used[(OUTLET, D.ITEM)] == 8
        planned_for_other = [row for row in H.request_rows(both.workspace) if row["event"] == H.EVENT_PLANNED and row["outlet_id"] == OTHER_OUTLET]
        assert [row["fetch_kind"] for row in planned_for_other] == ["channel_document"]


# --- F4: budgets, redirects and the second level of a sitemap index ---------------------------------------


def fetcher_with(site, budget):
    identity = loopback_test_identity()
    clock = FakeClock(T0)
    gate = P.PolicyGate(P.loopback_test_policy(), two_outlets(), identity)
    limits = F.FetchLimits(timeout_seconds=2, max_redirects=3, max_body_bytes=500_000, max_attempts=1, backoff_base_seconds=2, backoff_max_seconds=60)
    return D.BudgetedFetcher(budget=budget, identity=identity, gate=gate, limits=limits, clock=clock, sleep=clock.sleep,
                             connect_override={WWW: ("127.0.0.1", site.port)})


def channel(fetcher, path, depth=0):
    return fetcher.fetch(F.FetchRequest(f"{WWW}{path}", OUTLET, acquisition.FETCH_KIND_CHANNEL_DOCUMENT, f"{OUTLET}:ch:rss_001", expansion_depth=depth))


def test_requests_are_counted_hop_by_hop_and_a_hop_that_does_not_fit_is_not_made(site):
    site.routes.update({"/robots.txt": Response(200, PLAIN, b"User-agent: *\nDisallow:\n"),
                        "/rss": Response(301, [("Location", "/feed/")]), "/feed/": Response(200, XML, feed(["/n/1"])),
                        "/sitemap.xml": Response(301, [("Location", "/sitemap_index.xml")]), "/sitemap_index.xml": Response(200, XML, b"<sitemapindex/>")})
    fetcher = fetcher_with(site, D.CanaryBudget(outlets=1, item_requests_total=4, item_requests_per_outlet=4, other_requests_per_outlet=4,
                                                expansion_requests_reserved_per_outlet=0))
    first = channel(fetcher, "/rss")
    assert first.final == "FETCHED" and first.last.status == 200 and fetcher.used[(OUTLET, D.OTHER)] == 3      # robots, /rss, /feed/
    second = channel(fetcher, "/sitemap.xml")                                   # one request is left: it is made, its redirect is not followed
    assert second.last.status == 301 and second.last.redirect_not_followed == "DENY: canary_budget_exhausted"
    assert second.last.final_url == f"{WWW}/sitemap.xml" and fetcher.used[(OUTLET, D.OTHER)] == 4
    third = channel(fetcher, "/rss")
    assert (third.final, third.decision.reasons, third.attempts) == ("DENIED", ("canary_budget_exhausted",), [])
    assert site.paths() == ["/robots.txt", "/rss", "/feed/", "/sitemap.xml"] and fetcher.transport_calls == 4
    assert fetcher.remaining(OUTLET, D.OTHER) == 0 == fetcher.remaining(OUTLET, D.EXPANSION)


def test_the_reserved_part_of_the_budget_is_out_of_reach_for_robots_files_and_channel_documents(site):
    site.routes.update({"/robots.txt": Response(200, PLAIN, b"User-agent: *\nDisallow:\n"), "/c": Response(200, XML, b"<urlset/>")})
    budget = D.CanaryBudget(outlets=1, item_requests_total=4, item_requests_per_outlet=4, other_requests_per_outlet=5,
                            expansion_requests_reserved_per_outlet=3)
    fetcher = fetcher_with(site, budget)
    assert channel(fetcher, "/c").final == "FETCHED"                             # robots + one channel document: the unreserved 2
    assert channel(fetcher, "/c").decision.reasons == ("canary_budget_exhausted",)
    assert [channel(fetcher, "/c", depth=1).final for _ in range(4)] == ["FETCHED"] * 3 + ["DENIED"]
    assert fetcher.used == {(OUTLET, D.OTHER): 2, (OUTLET, D.EXPANSION): 3} and len(site.requests) == 5 == budget.other_requests_per_outlet
    with pytest.raises(ValueError):
        D.CanaryBudget(other_requests_per_outlet=2, expansion_requests_reserved_per_outlet=3)
    assert budget.total_requests_ceiling == 4 + 5                                # a reservation raises no limit


def entry(position, url, lastmod=None):
    return discovery.ChannelEntry(position, discovery.RELATION_CHILD_DOCUMENT, url, url, {"lastmod": lastmod} if lastmod else {})


def test_the_children_of_an_index_are_read_news_first_newest_first_taxonomies_last():
    names = [("post-sitemap.xml", "2026-10-08T15:41:05+00:00"), ("post-sitemap2.xml", "2026-04-21T14:14:24+00:00"),
             ("page-sitemap.xml", "2026-10-08T16:00:00+00:00"), ("category-sitemap.xml", "2026-10-08T16:07:44+00:00"),
             ("news-sitemap.xml", None), ("post_tag-sitemap.xml", "2026-10-08T16:07:44+00:00"), ("sitemap-2026-09.xml", "2026-09-30"),
             ("sitemap-sin-fecha.xml", None), ("sitemap-fecha-rara.xml", "ayer"), ("author-sitemap.xml", None)]
    entries = [entry(n, f"{WWW}/{name}", lastmod) for n, (name, lastmod) in enumerate(names)]
    ordered = [e.url.rsplit("/", 1)[1] for e in sorted(entries, key=discovery.expansion_priority)]
    assert ordered == ["news-sitemap.xml", "post-sitemap.xml", "sitemap-2026-09.xml", "post-sitemap2.xml", "sitemap-sin-fecha.xml",
                       "sitemap-fecha-rara.xml", "category-sitemap.xml", "post_tag-sitemap.xml", "page-sitemap.xml", "author-sitemap.xml"]
    assert ordered == [e.url.rsplit("/", 1)[1] for e in sorted(reversed(entries), key=discovery.expansion_priority)]   # deterministic
    # a name is matched by whole tokens: "homepage" is not a "page", "newsletter" is not "news"
    assert discovery.expansion_priority(entry(0, f"{WWW}/homepage-sitemap.xml"))[0] == 1
    assert discovery.expansion_priority(entry(0, f"{WWW}/newsletter-sitemap.xml"))[0] == 1


def yoast_index(children):
    rows = "".join(f"<sitemap><loc>{WWW}/{name}</loc>" + (f"<lastmod>{lastmod}</lastmod>" if lastmod else "") + "</sitemap>" for name, lastmod in children)
    return f'<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</sitemapindex>'.encode()


def urlset(paths):
    return ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>{WWW}{p}</loc></url>" for p in paths) + "</urlset>").encode()


CHILDREN = [("category-sitemap.xml", "2026-10-08T16:07:44+00:00")] + [(f"post-sitemap{n}.xml", f"2026-04-{n:02d}T10:00:00+00:00") for n in range(2, 30)] + [
    ("post-sitemap.xml", "2026-10-08T15:41:05+00:00"), ("page-sitemap.xml", "2026-10-08T16:00:00+00:00")]


def test_a_sitemap_index_behind_redirecting_channel_documents_is_read_to_its_second_level(tmp_path, site):
    """The situation of 2026-10-08: robots, a feed and an index, each of the two behind a redirect,
    and an index of many children — under the same eight requests per outlet.
    """
    scripted(site, paths=())
    site.routes.update({
        "/rss.xml": Response(301, [("Location", "/feed/")]), "/feed/": Response(200, XML, feed(["/de-feed/1"])),
        "/sitemap_index.xml": Response(301, [("Location", "/sitemap_index_real.xml")]),
        "/sitemap_index_real.xml": Response(200, XML, yoast_index(CHILDREN)),
        "/post-sitemap.xml": Response(200, XML, urlset(["/nuevo/1", "/nuevo/2"])), "/post-sitemap29.xml": Response(200, XML, urlset(["/abril/29"])),
        "/post-sitemap28.xml": Response(200, XML, urlset(["/abril/28"])), "/category-sitemap.xml": Response(200, XML, urlset(["/categoria/x"])),
        "/de-feed/1": page(1), "/nuevo/1": page(2), "/nuevo/2": page(3), "/abril/29": page(4), "/abril/28": page(5)})
    budget = D.CanaryBudget(outlets=1, item_requests_total=40, item_requests_per_outlet=40)       # eight non-item requests, three reserved
    run = Drive(tmp_path / "index", site, budget=budget)
    run.go()
    non_item = [p for p in site.paths() if p.endswith(".xml") or p in ("/robots.txt", "/feed/")]
    assert non_item == ["/robots.txt", "/rss.xml", "/feed/", "/sitemap_index.xml", "/sitemap_index_real.xml",
                        "/post-sitemap.xml", "/post-sitemap29.xml", "/post-sitemap28.xml"]         # newest first; the taxonomy sitemap not at all
    assert len(non_item) == budget.other_requests_per_outlet
    assert run.fetcher.used[(OUTLET, D.OTHER)] == 5 and run.fetcher.used[(OUTLET, D.EXPANSION)] == 3
    assert {p for p in site.paths() if p not in non_item} == {"/de-feed/1", "/nuevo/1", "/nuevo/2", "/abril/29", "/abril/28"}
    receipt = run.receipt()
    assert receipt["requests"]["by_outlet"][OUTLET] == {"item": 5, "other": 8} and receipt["expansion_requests"]["total"] == 3
    assert receipt["counts"]["items_fetched"] == 5 and receipt["requests"]["total"] == len(site.requests) == run.fetcher.transport_calls
    # the 27 children that were not asked for are not 27 refused requests: the document budget ended the pass
    assert "DENIED:canary_budget_exhausted" not in receipt["refused"]
    tables = H.discovery_tables(run.workspace)
    waiting = DC.frontier(tables, f"{OUTLET}:ch:sitemap_001")
    assert len(waiting) == len(CHILDREN) - 3 and waiting[0]["url"].endswith("/post-sitemap27.xml") and waiting[-1]["url"].endswith("/page-sitemap.xml")
    # after a restart the budget of the evidence has the same three groups
    assert D.tally_from_evidence(run.workspace) == run.fetcher.used


def test_a_document_that_was_asked_for_and_not_supplied_has_used_its_place(tmp_path):
    asked = []

    def provider(url, depth):
        asked.append(url)
        if depth == 0:
            return discovery.ChannelDocument(url, url, fid(url), yoast_index(CHILDREN))
        return discovery.DocumentUnavailable(url, "DENIED: canary_budget_exhausted")

    tables = discovery.DiscoveryTables(tmp_path / "discovery")
    result = discovery.discover_channel(tables, RULES, channel_id=CHANNEL, start_url=f"{WWW}/sitemap_index.xml", provider=provider,
                                        budget=discovery.DiscoveryBudget(2, 4, 100, 10**6), run_id=RUN_ID, discovered_at=T0)
    assert len(asked) == 4 == result.documents_asked and result.documents_read == 1 and result.stopped_by == ["max_documents"]
    assert len(result.not_read) == len(CHILDREN) - 3 and {entry["reason"] for entry in result.not_read} == {"max_documents"}
    assert [row["outcome"] for row in tables.inputs] == ["PARSED", "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE"]


def test_a_canary_has_the_budget_of_its_baseline_not_of_the_workspace(tmp_path, site):
    scripted(site, paths=("/ok", "/gone410"))
    first = Drive(tmp_path / "shared", site)
    first.run = H.http_fetch_run(first.clock.now, [OUTLET], {"driver": D.DRIVER_VERSION, "baseline_id": "a" * 64}, first.identity)
    first.go()
    spent = D.tally_from_evidence(first.workspace)
    assert sum(spent.values()) == len(site.requests) > 0
    assert D.tally_from_evidence(first.workspace, baseline_id="a" * 64) == spent    # started again: the same budget, already spent
    assert D.tally_from_evidence(first.workspace, baseline_id="b" * 64) == {}       # armed and frozen anew: a new budget
    assert D.runs_of_baseline(first.workspace, "a" * 64) == {first.run.run_id}


def test_a_wider_canary_keeps_every_per_outlet_limit_and_the_hard_ceiling():
    assert D.canary_budget(5) == D.CanaryBudget()
    for outlets in range(6, 16):
        budget = D.canary_budget(outlets)
        assert budget.outlets == outlets and budget.item_requests_total <= D.HARD_ITEM_REQUESTS
        assert budget.item_requests_total == budget.item_requests_per_outlet * outlets and budget.item_requests_per_outlet >= 6
        assert (budget.other_requests_per_outlet, budget.channels_per_outlet) == (8, 2)
    assert D.canary_budget(12).item_requests_per_outlet == 8
    for outlets in (0, 4, 16):
        with pytest.raises(D.CanaryStopped):
            D.canary_budget(outlets)


# --- F5: `<!DOCTYPE` inside character data ----------------------------------------------------------------


def test_a_feed_that_carries_html_documents_in_cdata_is_read():
    parsed = discovery.parse_channel_document(fixture("rss_cdata_doctype.xml"), document_url=f"{WWW}/feed/", declared_content_type="application/rss+xml")
    assert (parsed.outcome, parsed.format, parsed.problems) == ("PARSED", "rss", ())
    assert [e.url for e in parsed.entries] == [f"{WWW}/economia/puerto-amplia-terminal/", f"{WWW}/regionales/lluvias-en-el-norte/"]
    assert parsed.entries[0].hints["published"] == "Thu, 08 Oct 2026 20:25:50 +0000" and discovery.PARSER_VERSION == "channel-parser/6"


LAUGHS = (b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;">]>'
          b"<rss><channel><item><link>https://www.diario-ejemplo.test/a</link><title>&lol2;</title></item></channel></rss>")


@pytest.mark.parametrize("body", [
    LAUGHS,
    b'<!DOCTYPE rss SYSTEM "http://www.diario-ejemplo.test/x.dtd"><rss><channel/></rss>',
    b'<?xml version="1.0"?><!-- <![CDATA[ --><!DOCTYPE rss [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss><channel/></rss>',
    b'<?xml version="1.0"?><!-- nota --><!doctype rss [<!entity x "y">]><rss><channel/></rss>',
    b"<rss><channel><item><title><![CDATA[ <!-- ]]></title></item></channel><!DOCTYPE x></rss>",
    b"<rss><channel><item><title><![CDATA[ never closed <!DOCTYPE html></title></item></channel></rss>",
    b"<rss><channel><!-- never closed <!ENTITY a 'b'></channel></rss>",
])
def test_a_real_declaration_is_still_refused_wherever_text_is_used_to_hide_it(body):
    parsed = discovery.parse_channel_document(body, document_url=f"{WWW}/feed/")
    assert parsed.outcome == "UNPARSEABLE" and parsed.entries == ()
    assert parsed.problems == ("dtd_or_entity_declaration_refused",)


def test_the_feed_of_2026_10_08_yields_candidates_through_discovery(tmp_path):
    def provider(url, depth):
        return discovery.ChannelDocument(url, url, fid(url), gzip.compress(fixture("rss_cdata_doctype.xml"), mtime=0), "application/rss+xml", "gzip")

    tables = discovery.DiscoveryTables(tmp_path / "discovery")
    result = discovery.discover_channel(tables, RULES, channel_id=CHANNEL, start_url=f"{WWW}/feed/", provider=provider, budget=BUDGET,
                                        run_id=RUN_ID, discovered_at=T0)
    assert len(result.candidates_new) == 2 and tables.inputs[0]["outcome"] == "PARSED" and tables.inputs[0]["parser"] == discovery.PARSER_VERSION


# --- F8 (second canary, 2026-10-09): a publisher's own sitemap states its pages with http ------------------


def test_an_http_entry_of_a_host_registered_under_https_is_read_as_https_and_nothing_else_is_widened(tmp_path):
    """The Arc sitemap of ``py_la_nacion`` listed 100 pages as ``http://www…`` on 2026-10-09: all were off-origin, no candidate."""
    origins = ("https://www.diario.example", "https://diario.example")
    read = discovery.https_for_registered_host
    assert read("http://www.diario.example/politica/2026/10/09/a/", origins) == "https://www.diario.example/politica/2026/10/09/a/"
    assert read("http://WWW.diario.example/a?id=1#x", origins) == "https://WWW.diario.example/a?id=1#x"
    for untouched in ("https://www.diario.example/a", "http://otro.example/a", "http://m.diario.example/a", "http://www.diario.example:8080/a",
                      "http://user@www.diario.example/a", "ftp://www.diario.example/a", "/a", ""):
        assert read(untouched, origins) is None
    assert read("http://www.diario.example/a", (*origins, "http://www.diario.example")) is None      # an outlet that registers http is left alone

    rules = discovery.OutletUrlRules(OUTLET, origins, f"{OUTLET}-url-rules/v1")
    body = (b'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            b"<url><loc>http://www.diario.example/politica/2026/10/09/uno/</loc><lastmod>2026-10-09T13:44:15.782Z</lastmod></url>"
            b"<url><loc>https://www.diario.example/politica/2026/10/09/dos/</loc></url>"
            b"<url><loc>http://otro.example/tres/</loc></url></urlset>")

    def provider(url, depth):
        return discovery.ChannelDocument(url, url, fid(url), body, "application/xml", "identity")

    tables = discovery.DiscoveryTables(tmp_path / "discovery")
    result = discovery.discover_channel(tables, rules, channel_id=f"{OUTLET}:ch:sitemap_001", start_url="https://www.diario.example/sitemap.xml",
                                        provider=provider, budget=BUDGET, run_id=RUN_ID, discovered_at=T0)
    events = sorted(tables.events.values(), key=lambda row: row["position"])
    assert len(result.candidates_new) == 2 and [event["problem"] for event in events] == [None, None, "off_origin"]
    # what the publisher stated is kept; what was read is said; the candidate is fetched from the registered origin
    assert events[0]["observed_url"].startswith("http://") and events[0]["resolved_url"].startswith("https://www.diario.example/")
    assert events[0]["hints"]["scheme_read_as"] == "https" and "scheme_read_as" not in events[1]["hints"]
    assert all(tables.candidates[c]["fetch_url"].startswith("https://www.diario.example/") for c in result.candidates_new)
    assert discovery.PARSER_VERSION == "channel-parser/6"


# --- F9, F10 (wave B, 2026-10-09) --------------------------------------------------------------------------


def test_a_feed_that_redirects_to_an_html_page_is_a_listing_and_what_it_links_waits_for_a_rule(tmp_path, site):
    """``ec_primicias``' registered feed URL answered 301 to the home page: 361 links, sections among the articles, and
    twelve of them were requested without an allow rule because the channel is registered as ``rss`` (F9)."""
    scripted(site, paths=("/ok",))
    home = b'<html><body><a href="/deportes/futbol/">Futbol</a><a href="/ok">Una nota</a><a href="/opinion/autor/">Autor</a></body></html>'
    site.routes["/rss.xml"] = Response(301, [("Location", f"{WWW}/")], b"")
    site.routes["/"] = Response(200, HTML, home)
    run = Drive(tmp_path / "redirected", site)
    run.go()
    assert "/" in site.paths() and not {"/ok", "/deportes/futbol/", "/opinion/autor/"} & set(site.paths())       # read and preserved; nothing it links was asked
    table = H.qualification_table(run.workspace)
    decisions = {row["url_key"][len(WWW):]: (row["decision"], row["reasons"]) for row in table.rows.values()}
    assert [r for r in D.fetch_records(run.workspace) if r["fetch_kind"] == "item"] == [] and run.receipt()["counts"]["items_fetched"] == 0
    assert decisions["/ok"] == ("DEFERRED", [candidate_filter.LISTING_NEEDS_RULE]) and len(decisions) == 3, decisions
    assert {decision for decision, _ in decisions.values()} == {"DEFERRED"}
    assert D.DRIVER_VERSION == "canary-driver/5"


def test_a_feed_served_as_xml_still_yields_its_items_after_an_html_answer_of_another_channel(tmp_path, site):
    """The rule is about the document that listed a candidate: a real feed beside it is not held back."""
    scripted(site, paths=("/ok",))
    run = Drive(tmp_path / "feed", site)
    run.go()
    assert "/ok" in site.paths() and run.receipt()["counts"]["items_fetched"] >= 1


@pytest.mark.parametrize("front", [b"\n\n\n", b"\r\n \t\n", b""])
def test_white_space_before_the_xml_declaration_does_not_make_a_feed_or_an_index_unparseable(front):
    """``gt_lahora`` served its feed and its Yoast index with three empty lines in front: both were ``UNPARSEABLE`` (F10)."""
    rss = front + b'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>x</title><item><link>' + f"{WWW}/a".encode() + b"</link></item></channel></rss>"
    parsed = discovery.parse_channel_document(rss, document_url=f"{WWW}/feed/", declared_content_type="application/rss+xml")
    assert (parsed.outcome, parsed.format, len(parsed.entries)) == ("PARSED", "rss", 1)
    index = (front + b'<?xml version="1.0" encoding="UTF-8"?><?xml-stylesheet type="text/xsl" href="//x/main-sitemap.xsl"?>'
             b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>' + f"{WWW}/post-sitemap.xml".encode()
             + b"</loc><lastmod>2026-10-09T13:42:43+00:00</lastmod></sitemap></sitemapindex>")
    parsed = discovery.parse_channel_document(index, document_url=f"{WWW}/sitemap_index.xml", declared_content_type="text/xml")
    assert (parsed.outcome, parsed.format, parsed.entries[0].relation) == ("PARSED", "sitemap_index", "child_document")
    # white space alone is still an empty document, and a DTD is still refused wherever the document starts
    assert discovery.parse_channel_document(b"\n\n \n", document_url=f"{WWW}/feed/").problems == ("empty_document",)
    assert discovery.parse_channel_document(front + b'<?xml version="1.0"?><!DOCTYPE rss [<!ENTITY x "y">]><rss/>', document_url=f"{WWW}/feed/").problems == (
        "dtd_or_entity_declaration_refused",)
    assert discovery.PARSER_VERSION == "channel-parser/6"


# --- F11, F12, F13 and the scope of an allow rule (qualification run, 2026-10-09) ------------------------------


def test_a_nameless_query_is_kept_only_for_an_outlet_that_declares_it_and_named_parameters_are_still_dropped():
    """``uy_montevideo_portal`` links each article as ``auc.aspx?978027``: 60 feed entries were one candidate (F12)."""
    from coprepan.identity import NAMELESS_QUERY, OutletUrlRules, canonical_url_key

    origin = "https://www.portal.example"
    generic = OutletUrlRules("uy_portal", (origin,), "uy_portal-url-rules/v1")
    declared = OutletUrlRules("uy_portal", (origin,), "uy_portal-url-rules/v2", (NAMELESS_QUERY,))
    key = lambda rules, url: canonical_url_key(rules, requested_url=url).key  # noqa: E731
    assert key(generic, f"{origin}/auc.aspx?978027") == key(generic, f"{origin}/auc.aspx?978024") == f"{origin}/auc.aspx"     # the defect
    assert key(declared, f"{origin}/auc.aspx?978027") == f"{origin}/auc.aspx?978027" != key(declared, f"{origin}/auc.aspx?978024")
    # tracking and other named parameters beside it are dropped; the order does not matter; a key of a key is the key
    assert key(declared, f"{origin}/auc.aspx?utm_source=rss&978027&fbclid=x") == f"{origin}/auc.aspx?978027"
    assert key(declared, f"{origin}/auc.aspx?978027&utm_medium=feed") == key(declared, key(declared, f"{origin}/auc.aspx?978027"))
    assert key(declared, f"{origin}/Noticias/una-nota-uc978027?utm_source=x") == f"{origin}/Noticias/una-nota-uc978027"     # an ordinary address is unchanged
    assert key(declared, f"{origin}/x?id=7") == f"{origin}/x"                                                                  # `id` is not declared
    both = OutletUrlRules("uy_portal", (origin,), "uy_portal-url-rules/v3", (NAMELESS_QUERY, "id"))
    assert key(both, f"{origin}/x?id=7&abc") == f"{origin}/x?abc&id=7"
    tracked = R.load_registry(CHECKOUT / "config" / "outlet_registry.json")
    assert tracked.url_rules("uy_montevideo_portal").significant_query_params == (NAMELESS_QUERY,)
    assert [o for o in tracked.outlets.values() if o["url_rules"]["significant_query_params"]] == [tracked.outlets["uy_montevideo_portal"]]
    assert tracked.outlets["ec_el_universo"]["web_origins"] == ["https://www.eluniverso.com", "https://eluniverso.com"]             # F11


def test_campaign_tags_are_not_requested_and_nothing_else_about_a_url_changes(tmp_path):
    """``ni_nicaragua_investiga``'s feed links carried ``utm_`` tags the site redirected away: ten requests for five pages (F13)."""
    plain = discovery.without_tracking
    assert plain("https://d.example/a/?utm_source=rss&utm_medium=feed") == "https://d.example/a/"
    assert plain("https://d.example/a?id=7&utm_campaign=x&page=2#top") == "https://d.example/a?id=7&page=2#top"
    assert plain("https://d.example/a?utm_source=x&978027") == "https://d.example/a?978027"
    for untouched in ("https://d.example/a", "https://d.example/a?id=7&fbclid=1", "https://d.example/utm_source/a", "https://d.example/a?autm_x=1&mutm_=2", "https://d.example/a?UTM_Source=x"):   # the lower-case tags only
        assert plain(untouched) == untouched
    assert plain("https://d.example/a?utm_source=rss", ("utm_source",)) == "https://d.example/a?utm_source=rss"      # declared significant: kept

    rules = discovery.OutletUrlRules(OUTLET, (WWW,), f"{OUTLET}-url-rules/v1")
    body = feed((f"{WWW}/nota/1?utm_source=rss&amp;utm_medium=feed", f"{WWW}/nota/2"))

    def provider(url, depth):
        return discovery.ChannelDocument(url, url, fid(url), body, "application/rss+xml", "identity")

    tables = discovery.DiscoveryTables(tmp_path / "discovery")
    result = discovery.discover_channel(tables, rules, channel_id=CHANNEL, start_url=f"{WWW}/feed/", provider=provider, budget=BUDGET, run_id=RUN_ID, discovered_at=T0)
    events = sorted(tables.events.values(), key=lambda row: row["position"])
    assert events[0]["observed_url"].endswith("utm_medium=feed") and events[0]["resolved_url"] == f"{WWW}/nota/1"
    assert events[0]["hints"]["tracking_parameters_removed"] == "utm_" and "tracking_parameters_removed" not in events[1]["hints"]
    assert [tables.candidates[c]["fetch_url"] for c in result.candidates_new] == [f"{WWW}/nota/1", f"{WWW}/nota/2"]


def test_an_allow_rule_sorts_what_a_listing_names_and_does_not_narrow_a_feed_of_the_same_outlet():
    rules = {"version": "v1", "reject_path_prefixes": ["/temas"], "reject_path_patterns": [], "allow_path_patterns": [r"^/cuba/[a-z0-9-]+_1_[0-9]+[.]html$"]}
    listing = frozenset({f"{OUTLET}:ch:section_page_001"})

    def decide(path, channel):
        return candidate_filter.qualify({"candidate_id": f"{OUTLET}:cand:x", "outlet_id": OUTLET, "url_key": f"{WWW}{path}", "first_channel_id": channel},
                                        outlet_rules=rules, listing_channel_ids=listing)["decision"]

    assert decide("/cuba/una-nota_1_1131569.html", f"{OUTLET}:ch:section_page_001") == "QUALIFIED"
    assert decide("/cultura/otra-nota_1_1131570.html", f"{OUTLET}:ch:section_page_001") == "REJECTED"          # listed, and not what the rule calls an article
    assert decide("/cultura/otra-nota_1_1131570.html", f"{OUTLET}:ch:rss_001") == "QUALIFIED"                   # the feed's own entry: not narrowed
    assert decide("/temas/cine/", f"{OUTLET}:ch:rss_001") == "REJECTED"                                         # a reject rule applies to every candidate


def test_an_amendment_adds_to_a_registration_and_refuses_everything_else(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("amend_registration_under_test", CHECKOUT / "scripts" / "amend_registration.py")
    amender = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(amender)
    document = json.loads((CHECKOUT / "config" / "outlet_registry.json").read_text(encoding="utf-8"))
    evidence = [{"claim": "c", "how": "h", "source": "s"}]

    def amendment(**entry):
        return {"schema": "coprepan-registry-amendment/v1", "gate": "O-11", "record_stem": "t", "prepared_on": "2026-10-09", "purpose": "p",
                "amendments": [{"outlet_id": "bo_el_deber", "reason": "r", "add_web_origins": [], "url_rules": None, "add_channels": [], "evidence": evidence, **entry}]}

    apply = lambda a: amender.apply(a, document, approved_by="A Tester", approved_on="2026-10-09")  # noqa: E731
    result = apply(amendment(add_web_origins=["https://www.eldeber.com.bo"]))
    amended = {o["outlet_id"]: o for o in result["registry"]["outlets"]}["bo_el_deber"]
    assert amended["web_origins"] == ["https://eldeber.com.bo", "https://www.eldeber.com.bo"]                   # added at the end: the canonical origin stays first
    assert result["record"]["registry_sha256_before"] != result["record"]["registry_sha256_after"] and "A Tester" in result["record"]["authority"]
    for refused in (amendment(), amendment(add_web_origins=["https://eldeber.com.bo"]), amendment(add_web_origins=["https://www.diariolibre.com"]),
                    amendment(outlet_id="co_el_tiempo", add_web_origins=["https://x.example"]), amendment(add_web_origins=["https://x.example"], evidence=[]),
                    amendment(add_web_origins=["https://x.example"], reason=""), amendment(url_rules={"version": "bo_el_deber-url-rules/v1", "significant_query_params": [], "basis": "b"}),
                    amendment(add_web_origins=["https://x.example"], force=True), {**amendment(add_web_origins=["https://x.example"]), "gate": "O-1"}):
        with pytest.raises((amender.AmendmentError, R.RegistryError)):
            apply(refused)
    with pytest.raises(amender.AmendmentError):
        amender.apply(amendment(add_web_origins=["https://x.example"]), document, approved_by=" ", approved_on="2026-10-09")


def test_every_outlet_hypothesis_has_one_disposition_and_what_is_registered_is_what_the_rules_registered():
    dispositions = json.loads((CHECKOUT / "config" / "source_discovery" / "qualification_dispositions_2026-10-09.json").read_text(encoding="utf-8"))
    rows = dispositions["dispositions"]
    assert dispositions["hypotheses"] == len(rows) == len({row["outlet_id"] for row in rows}) == 145
    assert dispositions["by_disposition"] == {"ALREADY_REGISTERED": 22, "CLOSED": 2, "DOMAIN_CHANGE": 2, "IDENTITY_OPEN": 2, "LEGAL_HOLD": 1,
                                              "NO_EVIDENCED_CHANNEL": 22, "NO_ORIGIN": 2, "REGISTER": 92}
    assert all(row["reason"] for row in rows)
    by_id = {row["outlet_id"]: row for row in rows}
    assert by_id["co_el_tiempo"]["disposition"] == "LEGAL_HOLD" and by_id["bo_pagina_siete"]["disposition"] == "CLOSED"
    tracked = R.load_registry(CHECKOUT / "config" / "outlet_registry.json")
    registered = {o["outlet_id"] for o in tracked.outlets.values() if o["registration_status"] == "registered"}
    assert registered == {row["outlet_id"] for row in rows if row["disposition"] in ("REGISTER", "ALREADY_REGISTERED")} and len(registered) == 114
    assert "co_el_tiempo" not in registered
    # a deferred hypothesis of the registry stays proposed; one from research alone is not in the registry at all
    for row in rows:
        if row["disposition"] not in ("REGISTER", "ALREADY_REGISTERED"):
            assert (tracked.outlets[row["outlet_id"]]["registration_status"] == "proposed") if row["in_registry_before"] else (row["outlet_id"] not in tracked.outlets)


# --- F14 (wave C2, 2026-10-09): a second run for an outlet on a day whose pack is sealed ---------------------


def test_a_second_run_on_the_same_day_writes_to_the_next_pack_and_the_sealed_one_is_untouched(tmp_path, site):
    """Wave C2 asked ``hn_criterio`` again on the day wave C1 had sealed its pack: the first answer could not be recorded."""
    from datetime import timedelta

    scripted(site, paths=("/ok",))
    first = Drive(tmp_path / "day", site)
    first.go()
    sealed = sorted(path for path in first.workspace.packs.glob("*.warc.gz"))
    assert [path.name for path in sealed] == [f"pk1-{OUTLET}-20261008-000.warc.gz"]
    before = {path.name: path.read_bytes() for path in first.workspace.packs.iterdir() if path.is_file()}

    site.routes["/rss.xml"] = Response(200, [("Content-Type", "application/rss+xml")], feed(("/ok", "/nueva")))
    site.routes["/nueva"] = page(2)
    second = Drive(tmp_path / "day", site, start=first.clock.now + timedelta(hours=2))        # the same workspace, the same UTC day
    assert second.run.run_id != first.run.run_id
    second.go()
    assert "/nueva" in site.paths()
    names = sorted(path.name for path in second.workspace.packs.glob("*.warc.gz"))
    assert names == [f"pk1-{OUTLET}-20261008-000.warc.gz", f"pk1-{OUTLET}-20261008-001.warc.gz"]
    assert all(second.workspace.packs.joinpath(name).read_bytes() == content for name, content in before.items())   # nothing sealed was changed
    records = {r["fetch_id"]: r for r in D.fetch_records(second.workspace)}
    assert any(r["response"]["final_url"].endswith("/nueva") for r in records.values())
    assert all(state == "RAW_PRESERVED" for fetch_id, state in second.states().items() if fetch_id in records)

    from coprepan import pack as P_
    assert P_.first_unsealed_id(second.workspace.packs, OUTLET, "20261008") == f"pk1-{OUTLET}-20261008-002"
    assert P_.first_unsealed_id(second.workspace.packs, OUTLET, "20261009") == f"pk1-{OUTLET}-20261009-000"


# --- the allow rules written from the listing pages preserved in wave C1 -----------------------------------


@pytest.mark.parametrize("outlet_id, origin, articles, navigation", [
    ("hn_criterio", "https://criterio.hn",
     ["/la-ley-no-basta/", "/agrecasa-acumula-dictamenes-sin-que-se-concrete-clausura-definitiva-de-mina/",
      "/17-congresistas-piden-a-marco-rubio-que-apoye-investigacion-internacional-sobre-la-masacre-de-campesinos-de-rigores/"],
     ["/contacto", "/nosotros", "/quienes-somos", "/especiales", "/redes", "/donaciones/", "/politica-de-privacidad", "/category/actualidad/page/2/",
      "/category/derechos-humanos/", "/category/actualidad/page/3580/", "/tag/honduras/", "/author/redaccion-criterio/"]),
    ("pr_noticel", "https://noticel.com",
     ["/ultima-hora/20261008/sequia-continua-disminuyendo-en-puerto-rico/", "/ultima-hora/20261009/la-junta-da-luz-verde-al-reglamento-de-salarios-del-sistema-de-rango-de-la-policia/"],
     ["/auth/login", "/contact-us/", "/privacy-policy/", "/author/cmendez/", "/category/noticias/", "/category/ultima-hora/page/2/",
      "/en/category/ultima-hora/", "/en/ultima-hora/20261009/an-english-item/", "/ultima-hora/", "/ultima-hora/20261008/"])])
def test_the_listing_rules_qualify_the_articles_the_preserved_pages_named_and_none_of_their_navigation(outlet_id, origin, articles, navigation):
    rules = candidate_filter.load_rules()[outlet_id]
    listing = frozenset({f"{outlet_id}:ch:section_page_r001"})

    def decide(path):
        return candidate_filter.qualify({"candidate_id": f"{outlet_id}:cand:x", "outlet_id": outlet_id, "url_key": origin + path,
                                         "first_channel_id": f"{outlet_id}:ch:section_page_r001"}, outlet_rules=rules, listing_channel_ids=listing)["decision"]

    assert [decide(path) for path in articles] == ["QUALIFIED"] * len(articles)
    assert "QUALIFIED" not in {decide(path) for path in navigation}
    assert rules["version"] == f"{outlet_id}-candidate-rules/v1" and len(rules["allow_path_patterns"]) == 1


def test_only_the_two_outlets_of_wave_c2_have_candidate_rules():
    assert sorted(candidate_filter.load_rules()) == ["hn_criterio", "pr_noticel"]


# --- F6: a channel that answers 404 is disabled, not replaced ---------------------------------------------


def test_the_channel_that_answered_404_is_disabled_and_no_other_path_of_that_origin_was_added():
    tracked = P.load_policy()
    registered = R.load_registry(CHECKOUT / "config" / "outlet_registry.json")
    outlet = registered.resolve("hn_proceso_digital")
    assert "hn_proceso_digital:ch:sitemap_news" in tracked["disabled_channels"]
    selected = D.select_channels(outlet, tracked["disabled_channels"], 2, candidate_filter.load_rules())
    assert selected == ["hn_proceso_digital:ch:rss_main", "hn_proceso_digital:ch:sitemap_index_main"]
    # the registration of 2026-10-08 is what it was: six channels, no new address for an origin that challenges this client
    assert len(outlet["channels"]) == 6 and outlet["web_origins"] == ["https://proceso.hn"]


def test_a_listing_channel_is_read_and_what_it_lists_waits_for_an_allow_rule():
    """CPD-0019 let a canary read a listing only under an allow rule; CPD-0020 reads it and lets its
    candidates wait (`candidate-filter-generic/2`): the listing is preserved, nothing is requested on a guess.
    """
    outlet = {"outlet_id": OUTLET, "channels": [{"channel_id": f"{OUTLET}:ch:archive_001", "kind": "archive"},
                                                {"channel_id": f"{OUTLET}:ch:rss_001", "kind": "rss"},
                                                {"channel_id": f"{OUTLET}:ch:unknown_001", "kind": "unknown"}]}
    assert D.select_channels(outlet, (), 2) == [f"{OUTLET}:ch:rss_001", f"{OUTLET}:ch:archive_001"]
    listing = frozenset({f"{OUTLET}:ch:archive_001"})
    rules = {"version": "v1", "reject_path_prefixes": [], "reject_path_patterns": [], "allow_path_patterns": [r"^/[0-9]{4}/"]}

    def candidate(path, channel):
        return {"candidate_id": f"{OUTLET}:cand:x", "outlet_id": OUTLET, "url_key": f"{WWW}{path}", "first_channel_id": channel}

    from_listing = candidate_filter.qualify(candidate("/2026/10/09/nota", f"{OUTLET}:ch:archive_001"), listing_channel_ids=listing)
    assert (from_listing["decision"], from_listing["reasons"]) == ("DEFERRED", [candidate_filter.LISTING_NEEDS_RULE])
    assert candidate_filter.qualify(candidate("/2026/10/09/nota", f"{OUTLET}:ch:rss_001"), listing_channel_ids=listing)["decision"] == "QUALIFIED"
    assert candidate_filter.qualify(candidate("/2026/10/09/nota", f"{OUTLET}:ch:archive_001"), outlet_rules=rules, listing_channel_ids=listing)["decision"] == "QUALIFIED"
    assert candidate_filter.qualify(candidate("/contacto", f"{OUTLET}:ch:archive_001"), outlet_rules=rules, listing_channel_ids=listing)["decision"] == "REJECTED"
    assert candidate_filter.qualify(candidate("/logo.png", f"{OUTLET}:ch:archive_001"), listing_channel_ids=listing)["decision"] == "REJECTED"
    assert candidate_filter.GENERIC_RULESET == "candidate-filter-generic/3"


# --- F7: what the candidate budget of a pass keeps out -----------------------------------------------------


def news_sitemap(count):
    rows = "".join(
        f"<url><loc>{WWW}/nota/{n}</loc><news:news><news:publication_date>2026-10-{8 - n // 300:02d}T{23 - (n % 300) // 13:02d}:00:00-04:00"
        f"</news:publication_date></news:news></url>" for n in range(count))
    return ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">'
            + rows + "</urlset>").encode()


def test_the_coverage_report_says_what_the_candidate_budget_turned_away_and_a_later_pass_continues(tmp_path):
    body = news_sitemap(534)

    def provider(url, depth):
        return discovery.ChannelDocument(url, url, fid(url + str(len(tables.inputs))), body)

    tables = discovery.DiscoveryTables(tmp_path / "discovery")
    budget = discovery.DiscoveryBudget(2, 3, 200, 10**7)
    first = discovery.discover_channel(tables, RULES, channel_id=CHANNEL, start_url=f"{WWW}/sitemapnews", provider=provider, budget=budget,
                                       run_id=RUN_ID, discovered_at=T0)
    assert len(first.candidates_new) == 200 and first.stopped_by == ["max_candidates"]
    report = DC.coverage(tables, RUN_ID)["channels"][CHANNEL]
    assert (report["item_entries"], report["item_entries_with_candidate"], report["item_entries_turned_away_by_candidate_budget"]) == (534, 200, 334)
    # the listing is newest first, so what was turned away is its old end: nothing turned away is newer than anything kept
    assert report["turned_away_newer_than_oldest_kept"] == 0
    assert report["kept_dates"]["oldest"] >= report["turned_away_dates"]["newest"]
    # continuation needs no higher limit: a later pass over the same listing takes the next 200, then the rest
    later = "acq1-20261010T120000000000Z-000000000000"
    second = discovery.discover_channel(tables, RULES, channel_id=CHANNEL, start_url=f"{WWW}/sitemapnews", provider=provider, budget=budget,
                                        run_id=later, discovered_at=T0)
    third = discovery.discover_channel(tables, RULES, channel_id=CHANNEL, start_url=f"{WWW}/sitemapnews", provider=provider, budget=budget,
                                       run_id="acq1-20261011T120000000000Z-000000000000", discovered_at=T0)
    assert (len(second.candidates_new), len(third.candidates_new), third.stopped_by, len(tables.candidates)) == (200, 134, [], 534)
    assert DC.coverage(tables, later)["channels"][CHANNEL]["item_entries_turned_away_by_candidate_budget"] == 134
    assert DC.coverage(tables)["totals"]["item_entries"] == 3 * 534
    json.dumps(DC.coverage(tables))


def test_the_coverage_report_counts_what_a_channel_named_and_nobody_read(tmp_path):
    def provider(url, depth):
        if depth == 0:
            return discovery.ChannelDocument(url, url, fid(url), yoast_index(CHILDREN))
        return discovery.ChannelDocument(url, url, fid(url), urlset([f"/de/{url.rsplit('/', 1)[1]}"]))

    tables = discovery.DiscoveryTables(tmp_path / "discovery")
    discovery.discover_channel(tables, RULES, channel_id=CHANNEL, start_url=f"{WWW}/sitemap_index.xml", provider=provider,
                               budget=discovery.DiscoveryBudget(2, 4, 100, 10**6), run_id=RUN_ID, discovered_at=T0)
    report = DC.coverage(tables)["channels"][CHANNEL]
    assert (report["documents"], report["documents_named"], report["documents_named_and_not_read"]) == ({"PARSED": 4}, len(CHILDREN), len(CHILDREN) - 3)
    assert [entry["url"].rsplit("/", 1)[1] for entry in DC.frontier(tables, CHANNEL)][:2] == ["post-sitemap27.xml", "post-sitemap26.xml"]
