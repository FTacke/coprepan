"""The HTTP fetcher against a real HTTP server on a loopback address.

Nothing here leaves the machine and nothing here says anything about a real outlet: the server is
started by the test and serves what the test scripts. What is exercised for real is the transport
code — sockets, HTTP parsing, redirects, limits, retries.

TLS is **not** exercised: the outlet's ``https`` URLs are dialled as plain HTTP on loopback.
"""

import gzip
import hashlib

import pytest

from coprepan import acquisition as A
from coprepan import fetcher as F
from coprepan import policy as P
from coprepan import registry as R
from coprepan.crawler_identity import loopback_test_identity
from support_http import FakeClock, LocalSite, Response

OUTLET = "uy_diario_ejemplo"
WWW, MOBILE, FEEDS = "https://www.diario-ejemplo.test", "https://m.diario-ejemplo.test", "https://feeds.agregador.test"
HTML = [("Content-Type", "text/html; charset=utf-8")]
PAGE = "<html><body><article><h1>Nota</h1><p>Texto con ñ.</p></article></body></html>".encode("utf-8")
LIMITS = F.FetchLimits(timeout_seconds=2, max_redirects=3, max_body_bytes=200_000, max_attempts=3,
                       backoff_base_seconds=2, backoff_max_seconds=60)


def make_registry(status="registered"):
    return R.validate_registry({"schema": "coprepan-outlet-registry/v1", "outlets": [{
        "outlet_id": OUTLET, "country_id": "uy", "registration_status": status,
        "display_names": [{"name": "Diario Ejemplo", "valid_from": "unknown", "valid_to": "not_applicable"}],
        "outlet_type": "unknown", "outlet_group": "unknown", "city": "unknown", "region": "unknown",
        "scope": "unknown", "access_model": "unknown", "medium": "unknown", "editions": [],
        "web_origins": [WWW, MOBILE], "timezone": "America/Montevideo", "same_outlet_basis": "not_applicable",
        "url_rules": {"version": f"{OUTLET}-url-rules/v1", "significant_query_params": ["id"],
                      "strip_path_prefixes": ["/amp"], "strip_path_suffixes": []},
        "channels": [
            {"channel_id": f"{OUTLET}:ch:rss_001", "kind": "rss",
             "url_history": [{"url": f"{WWW}/rss.xml", "valid_from": "unknown"}], "legacy_observed": {}},
            {"channel_id": f"{OUTLET}:ch:rss_002", "kind": "rss",
             "url_history": [{"url": f"{FEEDS}/diario-ejemplo", "valid_from": "unknown"}], "legacy_observed": {}},
        ],
        "legacy_aliases": [], "legacy_observed": {}, "review_notes": [],
    }]})


@pytest.fixture
def site():
    with LocalSite() as server:
        yield server


def make_fetcher(site, *, policy=None, limits=LIMITS, registry=None, clock=None):
    clock = clock or FakeClock()
    identity = loopback_test_identity()
    gate = P.PolicyGate(policy or P.loopback_test_policy(), registry or make_registry(), identity)
    override = {origin: ("127.0.0.1", site.port) for origin in (WWW, MOBILE, FEEDS)}
    return F.HttpFetcher(identity=identity, gate=gate, limits=limits, clock=clock, sleep=clock.sleep,
                         connect_override=override), clock


def get(fetcher, path, **kwargs):
    return fetcher.fetch(F.FetchRequest(f"{WWW}{path}", OUTLET, **kwargs))


# --- the plain cases --------------------------------------------------------------------------------


def test_200_html_is_recorded_exactly(site):
    site.routes["/nota?utm=x"] = Response(200, HTML + [("Set-Cookie", "a=1"), ("Set-Cookie", "b=2")], PAGE)
    fetcher, _ = make_fetcher(site)
    outcome = get(fetcher, "/nota?utm=x")
    assert outcome.final == "FETCHED" and len(outcome.attempts) == 1 and outcome.attempts[0].retry == "none"
    exchange = outcome.last
    assert exchange.body == PAGE and exchange.status == 200 and exchange.final_url == f"{WWW}/nota?utm=x"
    assert [h for h in exchange.response_headers if h[0] == "Set-Cookie"] == [("Set-Cookie", "a=1"), ("Set-Cookie", "b=2")]
    assert exchange.request_id == outcome.request_id and outcome.request_id.startswith("rq1:")
    path, headers = site.requests[-1]
    assert path == "/nota?utm=x" and headers["host"] == "www.diario-ejemplo.test"  # the outlet's name, not the loopback address
    assert headers["user-agent"] == loopback_test_identity().user_agent and headers["accept-encoding"] == "gzip"

    run = A.AcquisitionRun("http_fetch", exchange.fetch_started_at, (OUTLET,), "channels", "0.3.0", {}, {})
    record = A.build_fetch_record(run, OUTLET, exchange)
    assert record["body_sha256"] == hashlib.sha256(PAGE).hexdigest() and record["fetch_kind"] == "item"
    assert record["policy"]["policy_decision"] == "ALLOW" and record["policy"]["policy_version"] == "loopback-test/1"
    assert record["policy"]["robots_decision"] == "absent" and record["policy"]["user_agent"] == headers["user-agent"]
    assert record["attempt_number"] == 1 and record["request_id"] == outcome.request_id
    assert record["response"]["content_encoding"] == "identity"


def test_rss_xml_and_a_content_type_that_lies_are_recorded_as_sent(site):
    feed = b"<?xml version='1.0'?><rss version='2.0'><channel><item><link>/a</link></item></channel></rss>"
    site.routes["/rss.xml"] = Response(200, [("Content-Type", "application/rss+xml")], feed)
    site.routes["/feed-as-html"] = Response(200, HTML, feed)
    fetcher, _ = make_fetcher(site)
    first = get(fetcher, "/rss.xml", fetch_kind="channel_document", channel_id=f"{OUTLET}:ch:rss_001").last
    second = get(fetcher, "/feed-as-html").last
    assert first.body == second.body == feed
    assert dict(first.response_headers)["Content-Type"] == "application/rss+xml"
    assert dict(second.response_headers)["Content-Type"].startswith("text/html")  # no sniffing, no correction here


def test_404_is_a_fetched_response_not_a_failure_and_is_not_retried(site):
    fetcher, _ = make_fetcher(site)
    outcome = get(fetcher, "/no-existe")
    assert outcome.final == "FETCHED" and outcome.last.status == 404 and outcome.last.body.startswith(b"<html>")
    assert len(outcome.attempts) == 1


def test_an_empty_200_is_a_fetch_with_an_empty_body(site):
    site.routes["/vacio"] = Response(200, HTML, b"")
    fetcher, _ = make_fetcher(site)
    outcome = get(fetcher, "/vacio")
    assert outcome.final == "FETCHED" and outcome.last.body == b""


def test_gzip_is_stored_as_sent_and_chunking_is_removed(site):
    packed = gzip.compress(PAGE, mtime=0)
    site.routes["/gz"] = Response(200, HTML + [("Content-Encoding", "gzip")], packed)
    site.routes["/chunked"] = Response(200, HTML, PAGE, chunked=True)
    fetcher, _ = make_fetcher(site)
    gz, chunked = get(fetcher, "/gz").last, get(fetcher, "/chunked").last
    assert gz.body == packed and gzip.decompress(gz.body) == PAGE          # content coding intact
    assert A.content_encoding_of(gz.response_headers) == "gzip"
    assert chunked.body == PAGE and dict(chunked.response_headers)["Transfer-Encoding"] == "chunked"


def test_a_large_body_within_the_limit_arrives_whole_and_one_over_it_is_a_failure(site):
    big = (b"0123456789abcdef" * 20000)[:LIMITS.max_body_bytes]
    assert len(big) == LIMITS.max_body_bytes
    site.routes["/grande"] = Response(200, HTML, big)
    site.routes["/demasiado"] = Response(200, HTML, big + b"x")
    fetcher, _ = make_fetcher(site)
    assert get(fetcher, "/grande").last.body == big
    outcome = get(fetcher, "/demasiado")
    assert outcome.final == "FETCH_FAILED" and outcome.last.body is None
    assert outcome.last.failure_reason == "body_limit_exceeded" and len(outcome.attempts) == 1  # not retried


# --- redirects --------------------------------------------------------------------------------------


def test_redirects_are_followed_and_the_chain_is_recorded(site):
    site.routes["/viejo"] = Response(301, [("Location", "/medio")])
    site.routes["/medio"] = Response(302, [("Location", f"{MOBILE}/amp/nuevo")])
    site.routes["/amp/nuevo"] = Response(200, HTML, PAGE)
    fetcher, _ = make_fetcher(site)
    exchange = get(fetcher, "/viejo").last
    assert exchange.redirect_chain == (f"{WWW}/viejo", f"{WWW}/medio") and exchange.final_url == f"{MOBILE}/amp/nuevo"
    assert exchange.requested_url == f"{WWW}/viejo" and exchange.body == PAGE and exchange.status == 200
    # every hop was put to the gate; the second origin's robots file was asked for before its page
    assert site.paths() == ["/robots.txt", "/viejo", "/medio", "/robots.txt", "/amp/nuevo"]
    assert [headers["host"] for _, headers in site.requests] == [
        "www.diario-ejemplo.test"] * 3 + ["m.diario-ejemplo.test"] * 2


def test_a_redirect_loop_ends_at_the_limit_as_a_failed_fetch(site):
    site.routes["/a"] = Response(302, [("Location", "/b")])
    site.routes["/b"] = Response(302, [("Location", "/a")])
    fetcher, _ = make_fetcher(site)
    outcome = get(fetcher, "/a")
    assert outcome.final == "FETCH_FAILED" and outcome.last.failure_reason == "redirect_limit_exceeded"
    assert len(outcome.last.redirect_chain) == LIMITS.max_redirects and len(outcome.attempts) == 1


def test_a_redirect_off_the_outlet_is_not_followed_and_the_redirect_answer_is_what_was_fetched(site):
    site.routes["/sale"] = Response(302, [("Location", "https://login.otro-sitio.test/muro")] + HTML, b"<html><body>redirigiendo</body></html>")
    fetcher, _ = make_fetcher(site)
    fetcher.connect_override["https://login.otro-sitio.test"] = ("127.0.0.1", site.port)  # reachable, and still refused
    exchange = get(fetcher, "/sale").last
    assert exchange.status == 302 and exchange.final_url == f"{WWW}/sale" and exchange.redirect_chain == ()
    assert exchange.redirect_not_followed == "DENY: off_origin"
    assert "/muro" not in site.paths()  # no request was made for the off-origin target


# --- failures and retries ---------------------------------------------------------------------------


def test_503_is_retried_with_backoff_and_each_attempt_is_an_exchange(site):
    site.routes["/inestable"] = [Response(503, HTML, b"<html>caido</html>"), Response(500, HTML, b"<html>error</html>"),
                                 Response(200, HTML, PAGE)]
    fetcher, clock = make_fetcher(site)
    outcome = get(fetcher, "/inestable")
    assert [(a.number, a.exchange.status, a.retry, a.delay_seconds) for a in outcome.attempts] == [
        (1, 503, "retry", 2), (2, 500, "retry", 4), (3, 200, "none", None)]
    assert outcome.final == "FETCHED" and clock.slept == [2, 4]  # waited by the injected clock, not by the test
    assert outcome.attempts[0].exchange.body == b"<html>caido</html>"  # an error page is evidence too
    assert len({a.exchange.request_id for a in outcome.attempts}) == 1
    assert [a.exchange.attempt_number for a in outcome.attempts] == [1, 2, 3]


def test_retries_are_exhausted_and_the_outcome_says_so(site):
    site.routes["/caido"] = Response(503, HTML, b"<html>caido</html>")
    fetcher, clock = make_fetcher(site)
    outcome = get(fetcher, "/caido")
    assert [a.retry for a in outcome.attempts] == ["retry", "retry", "gave_up"] and clock.slept == [2, 4]
    assert outcome.final == "FETCHED" and outcome.last.status == 503  # a response came back; it is not an article
    assert outcome.attempts[-1].retry_after is not None


def test_429_is_a_refusal_of_this_client_and_its_retry_after_is_recorded_not_waited_out(site):
    """CPD-0017 §4: an enforced rate limit is an access control. It is not asked again in this call
    (nor is the origin, in this run); the time the server named is on record for the schedule.
    """
    site.routes["/lento"] = [Response(429, HTML + [("Retry-After", "30")], b"<html>despacio</html>"), Response(200, HTML, PAGE)]
    fetcher, clock = make_fetcher(site)
    outcome = get(fetcher, "/lento")
    assert [(a.exchange.status, a.retry, a.delay_seconds) for a in outcome.attempts] == [(429, "gave_up", 30.0)]
    assert clock.slept == [] and outcome.attempts[0].retry_after is not None
    assert outcome.last.policy["access_class_observed"] == "rate_limited" and site.paths().count("/lento") == 1


def test_a_retry_after_longer_than_a_run_can_wait_ends_the_attempts(site):
    site.routes["/muy-lento"] = Response(429, HTML + [("Retry-After", "86400")], b"")
    fetcher, clock = make_fetcher(site)
    outcome = get(fetcher, "/muy-lento")
    assert len(outcome.attempts) == 1 and outcome.attempts[0].retry == "gave_up" and clock.slept == []
    assert outcome.attempts[0].delay_seconds == 86400.0 and outcome.attempts[0].retry_after is not None


def test_a_503_that_asks_for_more_patience_than_a_run_has_ends_the_attempts(site):
    site.routes["/mantenimiento"] = Response(503, HTML + [("Retry-After", "86400")], b"<html>mantenimiento</html>")
    fetcher, clock = make_fetcher(site)
    outcome = get(fetcher, "/mantenimiento")
    assert len(outcome.attempts) == 1 and outcome.attempts[0].retry == "gave_up" and clock.slept == []
    assert outcome.last.policy["access_class_observed"] == "none_observed"


def test_retry_after_forms():
    now = FakeClock().now
    assert F.parse_retry_after("120", now) == 120.0
    assert F.parse_retry_after("Wed, 07 Oct 2026 12:05:00 GMT", now) == 300.0
    assert F.parse_retry_after("Wed, 07 Oct 2026 11:00:00 GMT", now) == 0.0  # in the past: no extra wait
    assert F.parse_retry_after("pronto", now) is None and F.parse_retry_after(None, now) is None


@pytest.mark.parametrize("status", [400, 401, 403, 404, 410, 451])
def test_client_errors_are_not_retried(site, status):
    site.routes["/x"] = Response(status, HTML, b"<html>no</html>")
    fetcher, _ = make_fetcher(site)
    outcome = get(fetcher, "/x")
    assert len(outcome.attempts) == 1 and outcome.last.status == status


def test_a_body_cut_before_its_declared_length_is_a_failed_fetch_not_a_short_body(site):
    site.routes["/cortado"] = Response(200, HTML, PAGE[:20], declared_length=len(PAGE))
    fetcher, clock = make_fetcher(site, limits=F.FetchLimits(2, 3, 200_000, 2, 1, 60))
    outcome = get(fetcher, "/cortado")
    assert outcome.final == "FETCH_FAILED" and [a.exchange.failure_reason for a in outcome.attempts] == ["incomplete_response"] * 2
    assert all(a.exchange.body is None for a in outcome.attempts) and clock.slept == [1]


def test_a_chunked_body_without_its_end_is_a_failed_fetch(site):
    site.routes["/sin-fin"] = Response(200, HTML, PAGE, chunked=True, cut_chunked=True)
    fetcher, _ = make_fetcher(site, limits=F.FetchLimits(2, 3, 200_000, 1, 1, 60))
    outcome = get(fetcher, "/sin-fin")
    assert outcome.final == "FETCH_FAILED" and outcome.last.failure_reason == "incomplete_response"


def test_a_timeout_is_a_failed_fetch_and_is_retried(site):
    site.routes["/lento"] = [Response(200, HTML, PAGE, delay_seconds=0.6), Response(200, HTML, PAGE)]
    fetcher, clock = make_fetcher(site, limits=F.FetchLimits(0.2, 3, 200_000, 2, 1, 60))
    outcome = get(fetcher, "/lento")
    assert [(a.exchange.failure_reason, a.retry) for a in outcome.attempts] == [("timeout", "retry"), (None, "none")]
    assert outcome.final == "FETCHED" and outcome.last.body == PAGE


def test_a_refused_connection_is_a_failed_fetch(site):
    # Whether a closed loopback port answers "refused" at once or not at all depends on the
    # platform; both are a failed fetch with a named reason.
    no_answer = {"connection_error", "timeout"}
    limits = F.FetchLimits(0.4, 3, 200_000, 2, 1, 60)
    fetcher, _ = make_fetcher(site, limits=limits)
    fetcher.connect_override[WWW] = ("127.0.0.1", 1)  # nothing listens there
    # robots.txt cannot be read either, and the test policy denies on an unreachable robots file
    refused = get(fetcher, "/nota")
    assert (refused.final, refused.decision.reasons, refused.attempts) == ("DENIED", ("robots_unreachable",), [])
    assert fetcher.robots_exchanges[0][1].failure_reason in no_answer  # the failed robots request is evidence

    lenient = P.loopback_test_policy(robots={"mode": "enforce", "on_absent": "allow", "on_unreachable": "allow", "on_parse_error": "defer"})
    fetcher, _ = make_fetcher(site, policy=lenient, limits=limits)
    fetcher.connect_override[WWW] = ("127.0.0.1", 1)
    outcome = get(fetcher, "/nota")
    assert outcome.final == "FETCH_FAILED" and {a.exchange.failure_reason for a in outcome.attempts} <= no_answer
    assert outcome.last.failure_detail and len(outcome.attempts) == 2 and outcome.last.policy["robots_decision"] == "unreachable"


def test_limits_have_no_defaults():
    with pytest.raises(TypeError):
        F.FetchLimits(timeout_seconds=1)
    for bad in ((0, 3, 1, 1, 1, 1), (1, 3, 1, 0, 1, 1), (1, -1, 1, 1, 1, 1)):
        with pytest.raises(ValueError):
            F.FetchLimits(*bad)
    assert [LIMITS.backoff(n) for n in (1, 2, 3, 4, 5, 6, 7)] == [2, 4, 8, 16, 32, 60, 60]


# --- policy in front of the transport ---------------------------------------------------------------


def test_a_denied_intent_makes_no_transport_call(site):
    site.routes["/nota"] = Response(200, HTML, PAGE)
    for policy, reason in (
        (P.loopback_test_policy(disabled_outlets=[OUTLET]), "outlet_disabled"),
        (P.loopback_test_policy(opt_outs=[{"origin": WWW, "reason": "letter of 2026-09-01", "recorded_at": "2026-09-02"}]), "explicit_opt_out"),
        (P.loopback_test_policy(status="NOT_DECIDED", policy_version="undecided"), "policy_not_decided"),
    ):
        fetcher, _ = make_fetcher(site, policy=policy)
        outcome = get(fetcher, "/nota")
        assert (outcome.final, outcome.decision.reasons) == ("DENIED", (reason,))
        assert outcome.attempts == [] and fetcher.transport_calls == 0
    assert site.requests == []


def test_an_unregistered_outlet_is_never_fetched(site):
    fetcher, _ = make_fetcher(site, registry=make_registry(status="proposed"))
    outcome = get(fetcher, "/nota")
    assert outcome.decision.reasons == ("outlet_not_registered",) and site.requests == []


def test_a_suppression_defers_until_it_ends(site):
    site.routes["/nota"] = Response(200, HTML, PAGE)
    until = "2026-10-07T13:00:00.000000Z"
    policy = P.loopback_test_policy(suppressions=[{"outlet_id": OUTLET, "reason": "outage at the outlet", "until": until}])
    fetcher, clock = make_fetcher(site, policy=policy)
    outcome = get(fetcher, "/nota")
    assert (outcome.final, outcome.decision.retry_at) == ("DEFERRED", until) and site.requests == []
    clock.sleep(2 * 3600)
    assert get(fetcher, "/nota").final == "FETCHED"


def test_robots_is_fetched_once_per_origin_through_the_gate_and_enforced(site):
    robots = b"User-agent: *\nDisallow: /privado/\nAllow: /privado/abierto\n"
    site.routes["/robots.txt"] = Response(200, [("Content-Type", "text/plain")], robots)
    site.routes["/nota"] = Response(200, HTML, PAGE)
    site.routes["/privado/abierto"] = Response(200, HTML, PAGE)
    fetcher, _ = make_fetcher(site)
    assert get(fetcher, "/nota").final == "FETCHED"
    denied = get(fetcher, "/privado/informe")
    assert (denied.final, denied.decision.reasons, denied.decision.evidence["robots_rule"]) == (
        "DENIED", ("robots_disallow",), "disallow: /privado/")
    assert get(fetcher, "/privado/abierto").final == "FETCHED"
    assert site.paths() == ["/robots.txt", "/nota", "/privado/abierto"]  # robots once; nothing for the denied path
    assert [(outlet, e.fetch_kind, e.body) for outlet, e in fetcher.robots_exchanges] == [(OUTLET, "robots_txt", robots)]
    allowed = get(fetcher, "/nota").last
    assert allowed.policy["robots_decision"] == "allowed"
    assert allowed.policy["robots_txt_sha256"] == hashlib.sha256(robots).hexdigest()


def test_record_only_mode_records_the_robots_answer_without_enforcing_it(site):
    site.routes["/robots.txt"] = Response(200, [("Content-Type", "text/plain")], b"User-agent: *\nDisallow: /\n")
    site.routes["/nota"] = Response(200, HTML, PAGE)
    policy = P.loopback_test_policy(robots={"mode": "record_only", "on_absent": "allow", "on_unreachable": "deny", "on_parse_error": "defer"})
    fetcher, _ = make_fetcher(site, policy=policy)
    outcome = get(fetcher, "/nota")
    assert outcome.final == "FETCHED" and outcome.last.policy["robots_decision"] == "disallowed"


def test_an_unreachable_robots_file_denies_when_the_policy_says_so(site):
    site.routes["/robots.txt"] = Response(503, [], b"")
    site.routes["/nota"] = Response(200, HTML, PAGE)
    fetcher, _ = make_fetcher(site)
    outcome = get(fetcher, "/nota")
    assert (outcome.final, outcome.decision.reasons) == ("DENIED", ("robots_unreachable",)) and "/nota" not in site.paths()


def test_a_channel_document_may_live_on_a_registered_channel_host_but_an_item_may_not(site):
    feed = b"<rss><channel/></rss>"
    site.routes["/diario-ejemplo"] = Response(200, [("Content-Type", "text/xml")], feed)
    fetcher, _ = make_fetcher(site)
    channel = fetcher.fetch(F.FetchRequest(f"{FEEDS}/diario-ejemplo", OUTLET, "channel_document", f"{OUTLET}:ch:rss_002"))
    item = fetcher.fetch(F.FetchRequest(f"{FEEDS}/nota/1", OUTLET))
    assert channel.final == "FETCHED" and channel.last.body == feed
    assert (item.final, item.decision.reasons) == ("DENIED", ("off_origin",))


def test_requests_to_one_origin_are_paced(site):
    site.routes["/a"] = Response(200, HTML, PAGE)
    policy = P.loopback_test_policy(rate_limit={"min_interval_seconds_per_origin": 10, "crawl_delay": "record_only", "crawl_delay_max_seconds": 0})
    fetcher, clock = make_fetcher(site, policy=policy)
    for _ in range(3):
        assert get(fetcher, "/a").final == "FETCHED"
    assert len(clock.slept) >= 2 and all(0 < wait <= 10 for wait in clock.slept)


def test_a_binding_crawl_delay_slows_the_pace_of_its_origin(site):
    """Where the policy makes `Crawl-delay` binding, the origin's own number is the pause between
    two requests to it — when it is longer than the policy's minimum, and only then.
    """
    site.routes["/a"] = Response(200, HTML, PAGE)
    site.routes["/robots.txt"] = Response(200, [("Content-Type", "text/plain")], b"User-agent: *\nCrawl-delay: 30\n")
    policy = P.loopback_test_policy(rate_limit={"min_interval_seconds_per_origin": 10, "crawl_delay": "binding_minimum", "crawl_delay_max_seconds": 60})
    fetcher, clock = make_fetcher(site, policy=policy)
    for _ in range(3):
        outcome = get(fetcher, "/a")
        assert outcome.final == "FETCHED" and outcome.decision.evidence["robots_crawl_delay_binding_seconds"] == 30.0
    assert len(clock.slept) >= 3 and max(clock.slept) > 10 and all(0 < wait <= 30 for wait in clock.slept)
    slower = P.loopback_test_policy(rate_limit={"min_interval_seconds_per_origin": 10, "crawl_delay": "binding_minimum", "crawl_delay_max_seconds": 20})
    refused, _ = make_fetcher(site, policy=slower)
    before = len(site.requests)
    outcome = get(refused, "/a")
    assert (outcome.final, outcome.decision.reasons) == ("DENIED", ("robots_crawl_delay_exceeds_limit",))
    assert [request for request in site.paths()[before:]] == ["/robots.txt"]      # the page itself was never asked for


def test_a_loopback_policy_cannot_be_pointed_at_the_outside(site):
    fetcher, _ = make_fetcher(site)
    fetcher.connect_override.clear()  # the outlet's real host name would now be dialled
    outcome = get(fetcher, "/nota")
    assert outcome.decision.reasons == ("loopback_test_policy_cannot_reach_a_non_loopback_address",)
    assert fetcher.transport_calls == 0 and site.requests == []


def test_same_script_same_clock_same_exchanges(site):
    site.routes["/nota"] = Response(200, HTML, PAGE)
    site.routes["/inestable"] = [Response(503, HTML, b"x"), Response(200, HTML, PAGE)]
    results = []
    for _ in range(2):
        site._served.clear()
        fetcher, _ = make_fetcher(site)
        results.append([get(fetcher, "/nota").exchanges, get(fetcher, "/inestable").exchanges])
    assert results[0] == results[1]
