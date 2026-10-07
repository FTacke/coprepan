"""Re-fetching end to end against the loopback server: schedule, conditional requests, permanent
redirects, robots sitemaps and crawl-delay evidence, channel health, admission labels.

Same ground rules as ``test_offline_e2e.py``: an invented outlet, synthetic documents, a server
the test started. Reproducibility and robustness of the pipeline against itself — nothing about
any real outlet.
"""

import json
from datetime import timedelta

import pytest

from coprepan import admission, channel_health, core_pipeline as C, discovery, extraction, http_acquisition as H, schedule
from coprepan.acquisition import RecordedExchange
from coprepan.document_identity import IdentityTables
from support_http import LocalSite, Response
from test_core_pipeline import Canary
from test_offline_e2e import ARTICLE, HTML, OUTLET, RSS, SITEMAP, T0, WWW, Pass, fx, script

ARTICLE_PATH = "/Economia/Puerto-crecimiento-2026.html?utm_source=rss&utm_medium=feed"
ARTICLE_CANDIDATE = discovery.candidate_id(OUTLET, ARTICLE)
V1, V2 = fx("canary/nota_v1.html"), fx("canary/nota_v2.html")


@pytest.fixture
def site():
    with LocalSite() as server:
        script(server)
        yield server


def later(first, site, days, **kwargs):
    """Another run in the same workspace, ``days`` later."""
    site._served.clear()
    site.requests.clear()
    run = Pass(first.workspace.root.parent, site, start=T0 + timedelta(days=days), **kwargs)
    run.acquire(), run.preserve(), run.derive()
    return run


def log(run):
    return [json.loads(line) for line in H.request_log_path(run.workspace).read_text(encoding="utf-8").splitlines()]


def records_of(run, url_part):
    return [r for r in run.records() if url_part in r["request"]["requested_url"] and r["fetch_kind"] == "item"]


# --- schedule ---------------------------------------------------------------------------------------


def test_nothing_is_asked_again_before_it_is_due_and_everything_due_is(tmp_path, site):
    first = Pass(tmp_path, site).all()
    early = later(first, site, 6)                                  # the test schedule revisits after 7 days
    assert early.summary["candidates_requested"] == 0 and "item:FETCHED" not in early.summary["requests"]
    due = later(first, site, 8)
    assert due.summary["candidates_requested"] == 6                # five answered pages and the absent one
    assert due.summary["lifecycle"] == {"ABSENT": 1, "FETCHED": 5, "MOVED": 1}
    assert "/breves/123" not in [p for p in site.paths()]          # the permanently redirected URL is not requested again
    assert "/breves/123/" in site.paths()                          # its target is, as its own candidate


def test_history_is_append_only_across_runs(tmp_path, site):
    first = Pass(tmp_path, site).all()
    before = H.request_log_path(first.workspace).read_bytes()
    ledger_before = first.workspace.ledger_path.read_bytes()
    later(first, site, 8)
    assert H.request_log_path(first.workspace).read_bytes().startswith(before)
    assert first.workspace.ledger_path.read_bytes().startswith(ledger_before)


def test_repeated_failures_suspend_a_candidate_and_it_comes_back_after_the_cooldown(tmp_path, site):
    site.routes["/deportes/final"] = Response(503, HTML, b"<html>caido</html>")
    first = Pass(tmp_path, site).all()
    state = lambda run: schedule.plan(  # noqa: E731
        H.discovery_tables(run.workspace).candidates, H.request_rows(run.workspace), run.schedule, now=run.clock(),
        current_policy_version="loopback-test/1", limit=0)[1][discovery.candidate_id(OUTLET, f"{WWW}/deportes/final")]
    assert state(first).state == "FAILING"
    second = later(first, site, 1)
    assert state(second).state == "FAILING"
    third = later(first, site, 2)
    assert state(third).state == "SUSPENDED"                                     # the third failed request in a row
    assert later(first, site, 3).summary["candidates_requested"] == 0          # suspended: not asked
    site.routes["/deportes/final"] = Response(200, HTML, b"<html><body><article><h1>final</h1><p>Volvio.</p></article></body></html>")
    recovered = later(first, site, 10)                                           # after the 7-day cooldown
    assert state(recovered).state == "FETCHED"
    statuses = [r["response"]["status"] for run in (first, second, third) for r in records_of(run, "/deportes/final")]
    assert len(statuses) >= 3 and set(statuses) == {503}                         # every failed answer is preserved evidence


# --- conditional requests ---------------------------------------------------------------------------


def test_an_unchanged_page_is_revalidated_with_304_and_no_body_is_invented(tmp_path, site):
    site.routes[ARTICLE_PATH] = Response(200, HTML, V1, etag='"v1"')
    first = Pass(tmp_path, site).all()
    version = next(r for r in first.results if r["url_key"] == ARTICLE)["document_version_id"]
    held = records_of(first, "Puerto-crecimiento")[0]

    second = later(first, site, 8)
    request = [headers for path, headers in site.requests if path == ARTICLE_PATH][-1]
    assert request["if-none-match"] == '"v1"'
    record = records_of(second, "Puerto-crecimiento")[0]
    assert record["response"]["status"] == 304 and record["body_size_bytes"] == 0
    assert record["revalidates"] == {"fetch_id": held["fetch_id"], "body_sha256": held["body_sha256"]}
    assert second.states()[record["fetch_id"]] == "RAW_PRESERVED"                # the 304 answer itself is preserved evidence
    result = next(r for r in second.results if r["fetch_id"] == record["fetch_id"])
    assert (result["identity"], result["url_key_basis"], result["document_version_id"]) == ("assigned", "revalidation", version)
    assert result["extraction_outcome"] == "NOT_APPLICABLE" and result["is_new_version"] is False
    tables = IdentityTables(first.workspace.identity)
    assert tables.versions_of(result["document_id"]) == [version]               # one version, now observed by two fetches
    assert (version, record["fetch_id"]) in tables.version_observations
    # replay still works from the fetch that holds the body
    replay = C.replay_extraction(first.workspace, preservation_root=first.root, identifier=first.pack_id, fetch_id=held["fetch_id"])
    assert replay["status"] == "ALREADY_STORED"
    label = admission.label_pack(second.workspace, preservation_root=second.root, identifier=second.pack_id, results=second.results,
                                 extractor=extraction.BASELINE, labelled_at="2026-10-15T12:00:00.000000Z")
    not_modified = next(l for l in label if l["fetch_id"] == record["fetch_id"])
    assert not_modified["blocking_reasons"] == ["not_modified_answer"] and not_modified["document_version_id"] == version
    # unchanged twice: the next revisit is further away
    state = schedule.plan(H.discovery_tables(first.workspace).candidates, H.request_rows(first.workspace), second.schedule,
                          now=second.clock(), current_policy_version="loopback-test/1", limit=0)[1][ARTICLE_CANDIDATE]
    assert state.state == "FETCHED" and state.reason == "unchanged since the previous answer"


def test_a_stale_validator_gets_the_new_body_and_a_new_version(tmp_path, site):
    site.routes[ARTICLE_PATH] = Response(200, HTML, V1, etag='"v1"')
    first = Pass(tmp_path, site).all()
    site.routes[ARTICLE_PATH] = Response(200, HTML, V2, etag='"v2"')          # the page changed: "v1" no longer matches
    second = later(first, site, 8)
    record = records_of(second, "Puerto-crecimiento")[0]
    assert record["response"]["status"] == 200 and record["revalidates"] == "not_applicable"
    result = next(r for r in second.results if r["fetch_id"] == record["fetch_id"])
    document = next(r for r in first.results if r["url_key"] == ARTICLE)
    assert result["document_id"] == document["document_id"] and result["is_new_version"] is True
    assert IdentityTables(first.workspace.identity).versions_of(result["document_id"]) == [
        document["document_version_id"], result["document_version_id"]]          # the old version stays


def test_a_validator_is_a_hint_and_never_an_identity(tmp_path, site):
    """A server that keeps an ETag while changing the body: the body's hash decides, not the ETag."""
    site.routes[ARTICLE_PATH] = Response(200, HTML + [("ETag", '"same"')], V1)   # never answers 304
    first = Pass(tmp_path, site).all()
    site.routes[ARTICLE_PATH] = Response(200, HTML + [("ETag", '"same"')], V2)
    second = later(first, site, 8)
    record = records_of(second, "Puerto-crecimiento")[0]
    assert record["response"]["status"] == 200 and dict(map(tuple, record["response"]["headers"]))["ETag"] == '"same"'
    assert next(r for r in second.results if r["fetch_id"] == record["fetch_id"])["is_new_version"] is True


def test_a_304_nobody_asked_for_is_not_a_success(tmp_path, site):
    site.routes[ARTICLE_PATH] = Response(304, [])                               # an unconditional request answered 304
    run = Pass(tmp_path, site).all()
    record = records_of(run, "Puerto-crecimiento")[0]
    assert record["response"]["status"] == 304 and record["revalidates"] == "not_applicable"
    result = next(r for r in run.results if r["fetch_id"] == record["fetch_id"])
    assert result["document_version_id"] is None and result["extraction_outcome"] == "NOT_EXTRACTABLE"
    labels = admission.label_pack(run.workspace, preservation_root=run.root, identifier=run.pack_id, results=run.results,
                                  extractor=extraction.BASELINE, labelled_at="2026-10-07T13:00:00.000000Z")
    label = next(l for l in labels if l["fetch_id"] == record["fetch_id"])
    assert label["blocking_reasons"] == ["not_modified_answer", "not_extractable"]
    state = schedule.plan(H.discovery_tables(run.workspace).candidates, H.request_rows(run.workspace), run.schedule,
                          now=run.clock(), current_policy_version="loopback-test/1", limit=0)[1][ARTICLE_CANDIDATE]
    assert state.state == "FAILING" and "304_without_a_conditional_request" in state.reason


def test_a_revalidation_of_a_fetch_the_tables_do_not_know_assigns_nothing(tmp_path):
    start = T0 + timedelta(minutes=5)
    orphan = RecordedExchange(requested_url=f"{WWW}/nota", fetch_started_at=start, fetch_finished_at=start + timedelta(seconds=1),
                              status=304, response_headers=(), body=b"",
                              revalidates={"fetch_id": "ft1:" + "0" * 64, "body_sha256": "1" * 64})
    canary = Canary(tmp_path, items=[orphan]).all()
    assert canary.results[0]["identity"] == "revalidation_target_unknown" and canary.results[0]["document_id"] is None
    assert IdentityTables(canary.workspace.identity).documents == {}
    labels = admission.label_pack(canary.workspace, preservation_root=canary.root, identifier=canary.pack_id,
                                  results=canary.results, extractor=extraction.BASELINE, labelled_at="2026-10-07T13:00:00.000000Z")
    assert labels[0]["blocking_reasons"] == ["not_modified_answer", "no_document"]


def test_conditional_requests_can_be_switched_off_by_the_schedule_policy(tmp_path, site):
    site.routes[ARTICLE_PATH] = Response(200, HTML, V1, etag='"v1"')
    values = {name: getattr(Pass(tmp_path / "x", site).schedule, name) for name in schedule.SchedulePolicy.__dataclass_fields__}
    plain = schedule.SchedulePolicy(**{**values, "use_conditional_requests": False})
    first = Pass(tmp_path, site, schedule_policy=plain).all()
    later(first, site, 8, schedule_policy=plain)
    request = [headers for path, headers in site.requests if path == ARTICLE_PATH][-1]
    assert "if-none-match" not in request


# --- redirects --------------------------------------------------------------------------------------


def test_a_temporary_redirect_keeps_the_candidate_and_a_permanent_one_moves_it(tmp_path, site):
    site.routes["/Regionales/puerto-separan-cargas"] = Response(302, [("Location", "/Regionales/puerto-separan-cargas/v2")])
    site.routes["/Regionales/puerto-separan-cargas/v2"] = Response(200, HTML, fx("canary/nota_republicada.html"))
    run = Pass(tmp_path, site).all()
    tables = H.discovery_tables(run.workspace)
    temporary = discovery.candidate_id(OUTLET, f"{WWW}/Regionales/puerto-separan-cargas")
    assert discovery.candidate_id(OUTLET, f"{WWW}/Regionales/puerto-separan-cargas/v2") not in tables.candidates
    moved_from = discovery.candidate_id(OUTLET, f"{WWW}/breves/123")
    moved_to = discovery.candidate_id(OUTLET, f"{WWW}/breves/123/")
    assert tables.candidates[moved_to]["discovered_via"] == "permanent_redirect"
    assert tables.candidates[moved_to]["redirected_from"] == moved_from and tables.candidates[moved_to]["first_event_id"] is None
    states = schedule.plan(tables.candidates, H.request_rows(run.workspace), run.schedule, now=run.clock(),
                           current_policy_version="loopback-test/1", limit=0)[1]
    assert (states[temporary].state, states[moved_from].state, states[moved_from].moved_to) == ("FETCHED", "MOVED", moved_to)
    assert states[moved_to].state == "FETCHED"                                   # answered by the request that was redirected
    record = records_of(run, "/breves/123")[0]
    assert record["request"]["requested_url"] == f"{WWW}/breves/123"            # the URL as observed is never lost
    assert record["response"]["redirect_statuses"] == [301] and record["response"]["redirect_chain"] == [f"{WWW}/breves/123"]
    assert records_of(run, "puerto-separan-cargas")[0]["response"]["redirect_statuses"] == [302]


# --- robots: sitemaps and crawl-delay ---------------------------------------------------------------


def test_sitemaps_named_by_robots_are_one_more_discovery_source_when_asked_for(tmp_path, site):
    robots = (b"User-agent: *\nCrawl-delay: 7\nSitemap: https://www.diario-ejemplo.test/sitemap_index.xml\n"
              b"Sitemap: https://www.diario-ejemplo.test/sitemaps/extra.xml\nSitemap: https://otro-sitio.test/sitemap.xml\n")
    site.routes["/robots.txt"] = Response(200, [("Content-Type", "text/plain")], robots)
    site.routes["/sitemaps/extra.xml"] = Response(200, [("Content-Type", "application/xml")],
                                                  b"<urlset><url><loc>https://www.diario-ejemplo.test/solo-en-robots</loc></url></urlset>")
    without = Pass(tmp_path / "without", site)
    without.acquire()
    assert "/sitemaps/extra.xml" not in site.paths()                             # off unless asked for

    site._served.clear()
    site.requests.clear()
    run = Pass(tmp_path / "with", site)
    run.acquire(use_robots_sitemaps=True)
    source = f"{OUTLET}:ch:robots_sitemaps"
    by_source = {d["start_url"]: d for d in run.summary["discovery"] if d["channel_id"] == source}
    assert sorted(by_source) == ["https://otro-sitio.test/sitemap.xml", f"{WWW}/sitemaps/extra.xml"]  # the registered one is not read twice
    assert by_source[f"{WWW}/sitemaps/extra.xml"]["candidates_new"] == 1
    assert by_source["https://otro-sitio.test/sitemap.xml"]["documents_read"] == 0  # off-origin: refused by the gate, recorded
    tables = H.discovery_tables(run.workspace)
    new = tables.candidates[discovery.candidate_id(OUTLET, f"{WWW}/solo-en-robots")]
    assert new["first_channel_id"] == source and "/solo-en-robots" in site.paths()
    assert [i["outcome"] for i in tables.inputs if i["channel_id"] == source] == ["UNAVAILABLE", "PARSED"]  # in URL order
    # crawl-delay: recorded with every decision, applied by nothing
    finished = [row for row in log(run) if row["event"] == "FINISHED" and row["fetch_kind"] == "item"]
    assert {row["policy_hints"]["robots_crawl_delay"] for row in finished} == {"7"}
    assert 7 not in run.clock.slept and 7.0 not in run.clock.slept


def test_the_reserved_source_cannot_be_registered_as_a_channel():
    from coprepan import registry as R
    from test_canary import outlet

    entry = outlet("uy_uno", "rss")
    entry["channels"][0]["channel_id"] = "uy_uno:ch:robots_sitemaps"
    with pytest.raises(R.RegistryError):
        R.validate_registry({"schema": "coprepan-outlet-registry/v1", "outlets": [entry]})


# --- channel health and admission, on the run's own records -----------------------------------------


def test_channel_health_is_read_from_the_run_and_changes_nothing(tmp_path, site):
    policy = channel_health.HealthPolicy(failing_after_consecutive_failures=2, stale_after_runs_without_new_candidates=1)
    first = Pass(tmp_path, site).all()
    tables = H.discovery_tables(first.workspace)
    assert [h["state"] for h in channel_health.report(tables, [RSS, SITEMAP], policy)] == ["HEALTHY", "HEALTHY"]
    site.routes["/rss.xml"] = Response(503, HTML, b"<html>caido</html>")
    second = later(first, site, 1)
    health = {h["channel_id"]: h for h in channel_health.report(H.discovery_tables(first.workspace), [RSS, SITEMAP], policy)}
    assert health[RSS]["state"] == "DEGRADED" and "http_503" in health[RSS]["reason"]
    assert health[SITEMAP]["state"] == "STALE"                                   # readable, nothing new: not a fault
    later(first, site, 2)
    health = {h["channel_id"]: h for h in channel_health.report(H.discovery_tables(first.workspace), [RSS, SITEMAP], policy)}
    assert health[RSS]["state"] == "FAILING"
    assert RSS in [d["channel_id"] for d in second.summary["discovery"]]         # a failing channel is still read: health switches nothing off
    assert channel_health.health(H.discovery_tables(first.workspace), RSS, policy, disabled_channels=[RSS])["state"] == "DISABLED"


def test_admission_labels_of_a_real_transport_run(tmp_path, site):
    run = Pass(tmp_path, site).all()
    labels = admission.label_pack(run.workspace, preservation_root=run.root, identifier=run.pack_id, results=run.results,
                                  extractor=extraction.BASELINE, labelled_at="2026-10-07T13:00:00.000000Z")
    by_url = {}
    for label in labels:
        record = next(r for r in run.records() if r["fetch_id"] == label["fetch_id"])
        by_url.setdefault(record["request"]["requested_url"], []).append(label)
    assert len(labels) == 7 and {l["technical_status"] for l in labels} == {"TECHNICALLY_USABLE", "TECHNICALLY_UNUSABLE"}
    assert by_url[f"{WWW}/profundo/1"][0]["blocking_reasons"] == ["http_error_status"]       # the 404 page, kept and labelled
    retried = sorted(by_url[f"{WWW}/Regionales/puerto-separan-cargas"], key=lambda l: l["technical_status"])
    assert retried[0]["blocking_reasons"] == ["http_error_status"]                            # the 503 attempt
    assert "superseded_attempt" in [r["reason"] for r in retried[0]["reasons"]]
    assert retried[1]["technical_status"] == "TECHNICALLY_USABLE"                             # the attempt that succeeded
    assert sum(1 for l in labels if l["technical_status"] == "TECHNICALLY_USABLE") == 5
