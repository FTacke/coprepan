"""Policy gate, robots evidence and crawler identity: fail closed, nothing allowed by default."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from coprepan import crawler_identity as CI
from coprepan import policy as P
from coprepan import robots as RB
from test_fetcher import MOBILE, OUTLET, WWW, make_registry

REPO = Path(__file__).resolve().parents[1]
AT = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)
REAL = CI.OperatorIdentity("coprepan-research", "Universidad Ficticia", "https://corpus.uni-ficticia.es/crawler", "corpus@uni-ficticia.es")
EXTERNAL = CI.CrawlerIdentity(REAL, CI.SCOPE_EXTERNAL)
ABSENT = RB.RobotsEvidence(RB.EVIDENCE_ABSENT)


def decided(**overrides):
    policy = {**P.loopback_test_policy(), "scope": "external", "external_acquisition": "enabled", "policy_version": "policy/2026.1"}
    policy.update(overrides)
    return policy


def intent(url=f"{WWW}/nota", host="203.0.113.7", kind="item", channel=None, at=AT):
    return P.FetchIntent(url, OUTLET, kind, at, host, channel)


def gate(policy, identity=EXTERNAL, registry=None):
    return P.PolicyGate(policy, registry or make_registry(), identity)


# --- the tracked configuration fails closed ---------------------------------------------------------


def test_the_tracked_policy_is_the_decided_canary_policy():
    """O-1 is decided for the canary (CPD-0013). The switch that lets a request out is on only while
    the canary is armed (CPD-0016); while it is off, the policy denies every external request. Either
    state is legal; what is not legal is an armed policy that is not the canary policy.
    """
    policy = P.load_policy()
    armed = policy["external_acquisition"] == "enabled"
    assert policy["status"] == "DECIDED" and policy["external_acquisition"] in ("enabled", "disabled")
    assert policy["policy_version"].startswith("canary/") and policy["schema"] == "coprepan-acquisition-policy/v2"
    assert policy["robots"] == {"mode": "enforce", "on_absent": "allow", "on_unreachable": "defer"}
    assert policy["rate_limit"]["crawl_delay"] == "binding_minimum"
    assert policy["rate_limit"]["min_interval_seconds_per_origin"] >= 10 and policy["rate_limit"]["crawl_delay_max_seconds"] >= 10
    for kind in ("item", "channel_document", "robots_txt"):
        decision = gate(policy).evaluate(intent(kind=kind), ABSENT)
        if not armed:
            assert (decision.decision, decision.reasons) == ("DENY", ("external_acquisition_disabled",))
        else:  # armed: only the registered canary outlets can be asked, and only inside the policy
            assert gate(policy).evaluate(intent(kind=kind, url="https://www.unregistered.test/x"), ABSENT).decision == "DENY"
    if armed:
        assert [o for o in policy["disabled_outlets"]] == [] and policy["opt_outs"] == []


def test_every_disabled_channel_of_the_tracked_policy_is_a_registered_channel():
    from coprepan import registry as R
    known = {c["channel_id"] for o in R.load_registry(REPO / "config" / "outlet_registry.json").outlets.values() for c in o["channels"]}
    assert set(P.load_policy()["disabled_channels"]) <= known


# --- Crawl-delay as a binding minimum pause (policy v2) ----------------------------------------------


def binding(maximum=60, minimum=10):
    return decided(rate_limit={"min_interval_seconds_per_origin": minimum, "crawl_delay": "binding_minimum", "crawl_delay_max_seconds": maximum})


def robots_with(lines: str) -> RB.RobotsEvidence:
    return RB.evidence_from_response(200, lines.encode("utf-8"))


@pytest.mark.parametrize("written, seconds", [("5", 5.0), ("2.5", 2.5), ("0", 0.0), ("30", 30.0)])
def test_an_unambiguous_crawl_delay_binds_as_the_minimum_pause(written, seconds):
    evidence = robots_with(f"User-agent: *\nCrawl-delay: {written}\n")
    assert gate(binding()).crawl_delay_seconds(evidence) == seconds
    assert gate(binding()).interval_seconds(evidence) == max(10.0, seconds)       # never faster than the policy's own pace
    decision = gate(binding()).evaluate(intent(), evidence)
    assert decision.decision == "ALLOW" and decision.evidence["robots_crawl_delay_binding_seconds"] == seconds
    assert decision.evidence["robots_crawl_delay"] == written                       # still recorded as written


@pytest.mark.parametrize("written", ["soon", "-1", "1e3", "5 seconds", "", "1,5", "0x10"])
def test_a_crawl_delay_that_is_not_a_plain_number_is_recorded_and_not_applied(written):
    evidence = robots_with(f"User-agent: *\nCrawl-delay: {written}\n")
    assert gate(binding()).crawl_delay_seconds(evidence) is None
    assert gate(binding()).interval_seconds(evidence) == 10.0
    assert gate(binding()).evaluate(intent(), evidence).decision == "ALLOW"


def test_the_line_for_the_crawler_itself_wins_and_a_recording_policy_applies_nothing():
    evidence = robots_with("User-agent: *\nCrawl-delay: 5\n\nUser-agent: coprepan-research\nCrawl-delay: 40\n")
    assert gate(binding()).crawl_delay_seconds(evidence) == 40.0 and gate(binding()).interval_seconds(evidence) == 40.0
    recording = decided(rate_limit={"min_interval_seconds_per_origin": 10, "crawl_delay": "record_only", "crawl_delay_max_seconds": 0})
    assert gate(recording).crawl_delay_seconds(evidence) is None and gate(recording).interval_seconds(evidence) == 10.0
    assert gate(binding()).interval_seconds(None) == 10.0 and gate(binding()).interval_seconds(ABSENT) == 10.0


def test_an_origin_that_asks_for_more_patience_than_the_policy_has_is_not_fetched():
    """It is not fetched faster than it asked: it is not fetched, and the reason is on record."""
    evidence = robots_with("User-agent: *\nCrawl-delay: 600\n")
    decision = gate(binding(maximum=60)).evaluate(intent(), evidence)
    assert (decision.decision, decision.reasons) == ("DENY", ("robots_crawl_delay_exceeds_limit",))
    assert decision.evidence["robots_crawl_delay_binding_seconds"] == 600.0
    assert gate(binding(maximum=600)).evaluate(intent(), evidence).decision == "ALLOW"


def test_the_tracked_crawler_identity_is_the_decided_one_and_is_not_a_placeholder():
    """O-2 (CPD-0014): the operator's values, an https page on a real domain, a real address."""
    identity = CI.load_identity()
    document = json.loads((REPO / "config" / "crawler_identity.json").read_text(encoding="utf-8"))
    assert identity.scope == CI.SCOPE_EXTERNAL
    assert (document["crawler_name"], document["organisation"]) == ("PanhispanicMediaResearchBot", "Marburg University")
    assert document["contact_url"] == "https://coprepan.hispanistica.com/crawler/" and document["contact_email"] == "felix.tacke@uni-marburg.de"
    assert CI.validate_operator(identity.operator) == []
    assert identity.user_agent == ("PanhispanicMediaResearchBot/" + CI.SoftwareIdentity().version
                                   + " (+https://coprepan.hispanistica.com/crawler/; felix.tacke@uni-marburg.de)")
    assert identity.robots_product_token == "panhispanicmediaresearchbot"
    assert "not_configured" not in json.dumps(document["crawler_name"]) + document["organisation"] + document["contact_url"] + document["contact_email"]


def test_the_public_crawler_page_in_the_repository_says_what_the_identity_says():
    """The page a publisher finds behind contact_url (web/coprepan/crawler/) is versioned with the identity.
    That it is also reachable is a deployment check (`scripts/deploy_public_site.py verify`), not a test:
    tests never touch the network.
    """
    identity = CI.load_identity()
    page = (REPO / "web" / "coprepan" / "crawler" / "index.html").read_text(encoding="utf-8")
    assert identity.operator.contact_email in page and identity.operator.crawler_name in page and identity.operator.contact_url in page
    for statement in ("robots.txt", "Retry-After", "opt-out", "CAPTCHA", "paywalls", "conditional requests", "Marburg University"):
        assert statement in page, statement
    home = (REPO / "web" / "coprepan" / "index.html").read_text(encoding="utf-8")
    assert "/crawler/" in home and "under development" in home
    for text in (page, home):
        assert "http://" not in text.replace("http://www.w3.org", "")        # no mixed content
        assert "Pronunciation" not in text and "Coming soon" not in text


def test_external_acquisition_needs_every_precondition_at_once():
    """Decided policy + enabled + external identity + registered outlet + pace + robots evidence."""
    assert gate(decided()).evaluate(intent(), ABSENT).decision == "ALLOW"
    cases = [
        (gate(decided(external_acquisition="disabled")), "external_acquisition_disabled"),
        (gate(decided(status="NOT_DECIDED")), "policy_not_decided"),
        (gate(decided(), identity=CI.loopback_test_identity()), "identity_scope_does_not_match_policy_scope"),
        (gate(decided(), registry=make_registry("proposed")), "outlet_not_registered"),
        (gate(decided(disabled_outlets=[OUTLET])), "outlet_disabled"),
    ]
    for gatekeeper, reason in cases:
        decision = gatekeeper.evaluate(intent(), ABSENT)
        assert (decision.decision, decision.reasons) == ("DENY", (reason,)), reason
    assert gate(decided()).evaluate(intent(host="127.0.0.1"), ABSENT).reasons == ("external_policy_does_not_cover_loopback_targets",)


def test_no_robots_evidence_defers_and_never_allows():
    decision = gate(decided()).evaluate(intent())
    assert (decision.decision, decision.reasons) == ("DEFER", ("robots_not_consulted",))
    assert gate(decided()).evaluate(intent(), RB.RobotsEvidence(RB.EVIDENCE_NOT_CONSULTED)).decision == "DEFER"
    assert gate(decided()).evaluate(intent(url=f"{WWW}/robots.txt", kind="robots_txt")).decision == "ALLOW"


def test_a_decided_policy_has_decided_everything():
    for overrides in ({"robots": {"mode": "not_decided", "on_absent": "allow", "on_unreachable": "deny"}},
                      {"robots": {"mode": "enforce", "on_absent": "maybe", "on_unreachable": "deny"}},
                      {"rate_limit": {"min_interval_seconds_per_origin": "not_decided", "crawl_delay": "record_only", "crawl_delay_max_seconds": 0}},
                      {"rate_limit": {"min_interval_seconds_per_origin": 1, "crawl_delay": "sometimes", "crawl_delay_max_seconds": 0}},
                      {"rate_limit": {"min_interval_seconds_per_origin": 1, "crawl_delay": "binding_minimum", "crawl_delay_max_seconds": "not_decided"}},
                      {"rate_limit": {"min_interval_seconds_per_origin": 1}},
                      {"rate_limit": {"min_interval_seconds_per_origin": -1, "crawl_delay": "record_only", "crawl_delay_max_seconds": 0}},
                      {"policy_version": "undecided"}):
        with pytest.raises(P.PolicyError):
            gate(decided(**overrides))


@pytest.mark.parametrize(
    "broken",
    [{"schema": "coprepan-acquisition-policy/v1"}, {"status": "MAYBE"}, {"scope": "everywhere"}, {"allow_all": True},
     {"external_acquisition": "yes"}, {"opt_outs": [{"reason": "x"}]}, {"suppressions": [{"outlet_id": OUTLET, "reason": "x", "until": "soon"}]},
     {"disabled_outlets": "all"}, {"robots": {"mode": "enforce"}}],
)
def test_a_malformed_policy_is_refused(broken):
    with pytest.raises(P.PolicyError):
        P.validate_policy({**decided(), **broken})


def test_a_loopback_policy_is_never_loaded_from_configuration(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(P.loopback_test_policy()), encoding="utf-8")
    with pytest.raises(P.PolicyError):
        P.load_policy(path)
    with pytest.raises(P.PolicyError):
        P.load_policy(tmp_path / "absent.json")


def test_origins_channels_opt_outs_and_suppressions():
    policy = decided(
        disabled_channels=[f"{OUTLET}:ch:rss_001"],
        opt_outs=[{"origin": MOBILE, "reason": "publisher letter", "recorded_at": "2026-09-01"}],
        suppressions=[{"origin": WWW, "reason": "maintenance", "until": "2026-10-07T12:30:00.000000Z"}],
    )
    g = gate(policy)
    assert g.evaluate(intent(url="https://otro.test/x"), ABSENT).reasons == ("off_origin",)
    assert g.evaluate(intent(url="ftp://www.diario-ejemplo.test/x"), ABSENT).reasons == ("unusable_url",)
    assert g.evaluate(intent(channel=f"{OUTLET}:ch:nope"), ABSENT).reasons == ("channel_not_registered",)
    assert g.evaluate(intent(channel=f"{OUTLET}:ch:rss_001"), ABSENT).reasons == ("channel_disabled",)
    opted_out = g.evaluate(intent(url=f"{MOBILE}/x"), ABSENT)
    assert opted_out.reasons == ("explicit_opt_out",) and opted_out.evidence["opt_out"]["reason"] == "publisher letter"
    deferred = g.evaluate(intent(), ABSENT)
    assert (deferred.decision, deferred.retry_at) == ("DEFER", "2026-10-07T12:30:00.000000Z")
    assert g.evaluate(intent(at=AT.replace(hour=13)), ABSENT).decision == "ALLOW"


def test_robots_evidence_is_weighed_as_the_policy_says():
    fetched = RB.evidence_from_response(200, b"User-agent: *\nDisallow: /privado/\n")
    assert gate(decided()).evaluate(intent(url=f"{WWW}/privado/x"), fetched).reasons == ("robots_disallow",)
    record_only = decided(robots={"mode": "record_only", "on_absent": "allow", "on_unreachable": "deny"})
    decision = gate(record_only).evaluate(intent(url=f"{WWW}/privado/x"), fetched)
    assert decision.decision == "ALLOW" and decision.evidence["robots_decision"] == "disallowed"
    assert decision.evidence["robots_txt_sha256"] == fetched.sha256
    unreachable = RB.evidence_from_response(503, b"")
    for action, expected in (("deny", "DENY"), ("defer", "DEFER"), ("allow", "ALLOW")):
        policy = decided(robots={"mode": "enforce", "on_absent": "allow", "on_unreachable": action})
        assert gate(policy).evaluate(intent(), unreachable).decision == expected
    strict = decided(robots={"mode": "enforce", "on_absent": "deny", "on_unreachable": "deny"})
    assert gate(strict).evaluate(intent(), ABSENT).reasons == ("robots_absent",)


# --- robots parser ----------------------------------------------------------------------------------

ROBOTS = b"""# comentario
User-agent: *
Disallow: /privado/
Allow: /privado/abierto
Disallow: /*.pdf$
Disallow:

User-agent: coprepan-research
User-agent: OtroBot
Disallow: /solo-para-otros/
Crawl-delay: 5

Sitemap: https://www.diario-ejemplo.test/sitemap_index.xml
Linea sin sentido
User-agent: GPTBot
Disallow: /
"""


@pytest.mark.parametrize(
    "token, path, verdict, rule",
    [("desconocido", "/nota", "allowed", None),
     ("desconocido", "/privado/x", "disallowed", "disallow: /privado/"),
     ("desconocido", "/privado/abierto/1", "allowed", "allow: /privado/abierto"),   # the longer rule wins
     ("desconocido", "/docs/informe.pdf", "disallowed", "disallow: /*.pdf$"),
     ("desconocido", "/docs/informe.pdf?x=1", "allowed", None),                    # $ anchors the end
     ("COPREPAN-Research", "/privado/x", "allowed", None),                        # its own group, matched case-insensitively
     ("coprepan-research", "/solo-para-otros/x", "disallowed", "disallow: /solo-para-otros/"),
     ("otrobot", "/solo-para-otros/x", "disallowed", "disallow: /solo-para-otros/"),
     ("gptbot", "/nota", "disallowed", "disallow: /")],
)
def test_robots_rules(token, path, verdict, rule):
    assert RB.parse_robots(ROBOTS).evaluate(token, path) == (verdict, rule)


def test_robots_records_what_else_it_saw_and_interprets_none_of_it():
    rules = RB.parse_robots(ROBOTS)
    assert rules.sitemaps == ("https://www.diario-ejemplo.test/sitemap_index.xml",)
    assert rules.crawl_delays == {"coprepan-research": "5", "otrobot": "5"}  # recorded as written; not applied
    assert RB.parse_robots(b"").evaluate("x", "/a") == ("allowed", None)
    assert RB.parse_robots(b"\xff\xfe garbage \x00").evaluate("x", "/a") == ("allowed", None)
    tie = RB.parse_robots(b"User-agent: *\nDisallow: /a\nAllow: /a\n")
    assert tie.evaluate("x", "/a") == ("allowed", "allow: /a")  # equal length: allow


def test_robots_evidence_states():
    assert RB.evidence_from_response(200, b"User-agent: *\n").state == "fetched"
    assert RB.evidence_from_response(404, b"<html>").state == "absent" and RB.evidence_from_response(403, b"").state == "absent"
    for status, body in ((500, b""), (503, b""), (None, None), (301, b"")):
        assert RB.evidence_from_response(status, body).state == "unreachable"
    with pytest.raises(ValueError):
        RB.RobotsEvidence("fetched")


# --- crawler identity -------------------------------------------------------------------------------


def test_user_agent_is_derived_and_the_four_identities_stay_apart():
    assert EXTERNAL.user_agent == f"coprepan-research/{CI.SoftwareIdentity().version} (+https://corpus.uni-ficticia.es/crawler; corpus@uni-ficticia.es)"
    assert EXTERNAL.robots_product_token == "coprepan-research" and EXTERNAL.crawler_version.endswith("http-fetcher/1")
    record = EXTERNAL.as_record()
    assert set(record) == {"schema", "scope", "user_agent", "operator", "software"} and "run_id" not in json.dumps(record)
    assert EXTERNAL.sha256 == CI.CrawlerIdentity(REAL, CI.SCOPE_EXTERNAL).sha256
    assert CI.validate_operator(REAL) == []


@pytest.mark.parametrize(
    "field, value",
    [("contact_email", "research@university.edu"), ("contact_email", "bot@example.org"), ("contact_email", "not-an-address"),
     ("contact_url", "https://www.example.com/bot"), ("contact_url", "http://corpus.uni-ficticia.es/crawler"),
     ("contact_url", "https://corpus.test/crawler"), ("crawler_name", "Mozilla/5.0 (compatible)"), ("crawler_name", "x"),
     ("organisation", ""), ("organisation", "not_configured")],
)
def test_placeholders_and_borrowed_identities_are_refused(field, value, tmp_path):
    document = {"schema": "coprepan-crawler-identity/v1", "crawler_name": REAL.crawler_name, "organisation": REAL.organisation,
                "contact_url": REAL.contact_url, "contact_email": REAL.contact_email, field: value}
    path = tmp_path / "identity.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(CI.CrawlerIdentityNotConfigured):
        CI.load_identity(path)


def test_a_complete_identity_loads_as_external(tmp_path):
    path = tmp_path / "identity.json"
    path.write_text(json.dumps({"schema": "coprepan-crawler-identity/v1", **EXTERNAL.as_record()["operator"]}), encoding="utf-8")
    loaded = CI.load_identity(path)
    assert loaded.scope == "external" and loaded.user_agent == EXTERNAL.user_agent
    with pytest.raises(CI.CrawlerIdentityNotConfigured):
        CI.load_identity(tmp_path / "absent.json")


def test_the_loopback_identity_says_what_it_is_and_cannot_pass_for_a_real_one():
    identity = CI.loopback_test_identity()
    assert identity.scope == "loopback_test" and "loopback-test" in identity.user_agent
    assert CI.validate_operator(identity.operator) != []
