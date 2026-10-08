"""The research-TDM acquisition policy (decision CPD-0017): three layers that are never one.

```text
robots protocol evidence   ≠   research-TDM eligibility   ≠   the acquisition decision
```

What is asserted: a ``Disallow`` is recorded as observed and is overridden only by the research
layer, openly and with its provenance; a technical access control is never weighed against
anything and never worked around; an opt-out and a legal review hold stop a source for a person to
decide; the pace is never faster than the origin asked. Everything runs against a server on a
loopback address that the test started, or against no server at all.
"""

from __future__ import annotations

import gzip
import itertools
import json

import pytest

from coprepan import access_control as AC
from coprepan import acquisition as A
from coprepan import canary_driver as D
from coprepan import fetcher as F
from coprepan import http_acquisition as H
from coprepan import policy as P
from coprepan import robots as RB
from support_http import Response
from test_canary_driver import Drive, SMALL, page, scripted, site_checkout
from test_fetcher import HTML, MOBILE, OUTLET, PAGE, WWW, get, make_fetcher, site  # noqa: F401  (site is a fixture)
from test_policy import ABSENT, EXTERNAL, decided, gate, intent

TOKEN = EXTERNAL.robots_product_token
RESEARCH = {"basis": "SCIENTIFIC_TDM_POLICY_V1", "decision": "CPD-0017", "conditions": {name: True for name in P.TDM_CONDITIONS},
            "legal_review_holds": []}
OVERRIDE = {"mode": "research_tdm_override", "on_absent": "allow", "on_unreachable": "defer", "on_parse_error": "defer"}
PRIVATE = RB.evidence_from_response(200, b"User-agent: *\nDisallow: /privado/\n")
ROBOTS_TXT = [("Content-Type", "text/plain")]


def research(**overrides):
    """A decided external policy with the research layer, as the canary's is."""
    return decided(**{"robots": dict(OVERRIDE), "research_tdm": json.loads(json.dumps(RESEARCH)), **overrides})


def loopback(**overrides):
    return P.loopback_test_policy(robots=dict(OVERRIDE), research_tdm=json.loads(json.dumps(RESEARCH)), **overrides)


def layers(decision):
    return (decision.decision, decision.reasons[0], decision.evidence["robots_evidence"], decision.evidence.get("research_tdm"),
            decision.acquisition_decision)


# --- layer by layer, at the gate ------------------------------------------------------------------------


def test_a_path_robots_allows_is_plainly_allowed_and_no_override_is_recorded():
    decision = gate(research()).evaluate(intent(url=f"{WWW}/nota"), PRIVATE)
    assert layers(decision) == ("ALLOW", "allowed_by_policy", "ROBOTS_ALLOW", "RESEARCH_TDM_ELIGIBLE", "ALLOW")
    assert "override" not in decision.evidence


def test_a_disallow_is_observed_and_overridden_only_openly_with_its_provenance():
    g = gate(research())
    decision = g.evaluate(intent(url=f"{WWW}/privado/x"), PRIVATE)
    assert layers(decision) == ("ALLOW", "research_tdm_override", "ROBOTS_DISALLOW_OBSERVED", "RESEARCH_TDM_ELIGIBLE",
                                "ALLOW_RESEARCH_OVERRIDE")
    override = decision.evidence["override"]
    assert override == {"basis": "SCIENTIFIC_TDM_POLICY_V1", "decided_in": "CPD-0017", "robots_rule": "disallow: /privado/",
                        "robots_txt_sha256": PRIVATE.sha256, "product_token": TOKEN, "conditions": list(P.TDM_CONDITIONS),
                        "url": f"{WWW}/privado/x", "at": "2026-10-07T12:00:00.000000Z"}
    assert decision.evidence["robots_decision"] == "disallowed" and decision.evidence["robots_decision_semantics"] == "robots-decision/2"
    again = g.evaluate(intent(url=f"{WWW}/privado/x"), PRIVATE)                # deterministic
    assert (again.decision, again.reasons, dict(again.evidence)) == (decision.decision, decision.reasons, dict(decision.evidence))


def test_without_the_research_layer_a_disallow_refuses():
    enforce = decided()                                                         # mode enforce, no research basis
    decision = gate(enforce).evaluate(intent(url=f"{WWW}/privado/x"), PRIVATE)
    assert layers(decision) == ("DENY", "robots_disallow", "ROBOTS_DISALLOW_OBSERVED", "RESEARCH_TDM_NOT_APPLICABLE", "REFUSE")
    eligible_but_enforced = research(robots={**OVERRIDE, "mode": "enforce"})
    assert layers(gate(eligible_but_enforced).evaluate(intent(url=f"{WWW}/privado/x"), PRIVATE))[4] == "REFUSE"


@pytest.mark.parametrize("condition", P.TDM_CONDITIONS)
def test_one_condition_that_is_not_stated_true_and_there_is_no_override(condition):
    block = json.loads(json.dumps(RESEARCH))
    block["conditions"][condition] = False
    decision = gate(decided(robots=dict(OVERRIDE), research_tdm=block)).evaluate(intent(url=f"{WWW}/privado/x"), PRIVATE)
    assert layers(decision) == ("DENY", "robots_disallow", "ROBOTS_DISALLOW_OBSERVED", "RESEARCH_TDM_REVIEW", "REFUSE")
    assert decision.evidence["research_tdm_unmet"] == [condition] and "override" not in decision.evidence


def test_an_override_mode_without_a_basis_or_with_a_condition_missing_is_not_a_policy():
    none = {"basis": "not_applicable", "decision": "not_applicable", "conditions": {}, "legal_review_holds": []}
    with pytest.raises(P.PolicyError, match="needs a research_tdm.basis"):
        P.validate_policy(decided(robots=dict(OVERRIDE), research_tdm=none))
    partial = json.loads(json.dumps(RESEARCH))
    del partial["conditions"]["non_commercial"]
    with pytest.raises(P.PolicyError, match="conditions"):
        P.validate_policy(decided(robots=dict(OVERRIDE), research_tdm=partial))
    with pytest.raises(P.PolicyError, match="basis"):
        P.validate_policy(decided(research_tdm={**RESEARCH, "basis": "BECAUSE_WE_WANT_TO"}))
    with pytest.raises(P.PolicyError, match="on_parse_error"):
        P.validate_policy(decided(robots={"mode": "enforce", "on_absent": "allow", "on_unreachable": "deny"}))


def test_an_access_control_refuses_whatever_robots_and_the_research_layer_say():
    for evidence, url in ((PRIVATE, f"{WWW}/privado/x"), (PRIVATE, f"{WWW}/nota"), (ABSENT, f"{WWW}/nota"), (None, f"{WWW}/nota")):
        decision = gate(research()).evaluate(intent(url=url), evidence, access_observed=AC.FORBIDDEN)
        assert (decision.decision, decision.reasons, decision.acquisition_decision) == ("DENY", ("access_control_observed",), "HOLD")
        assert decision.evidence["hold_class"] == "ACCESS_CONTROL_OBSERVED" and decision.evidence["access_class_observed"] == "forbidden"
        assert "override" not in decision.evidence
    robots_file = gate(research()).evaluate(intent(url=f"{WWW}/robots.txt", kind="robots_txt"), access_observed=AC.BOT_CHALLENGE)
    assert robots_file.decision == "DENY"                                       # not even the robots file is asked for again


def test_a_direct_opt_out_holds_the_source_for_a_person_and_is_never_overridden():
    opted = research(opt_outs=[{"outlet_id": OUTLET, "reason": "publisher e-mail", "recorded_at": "2026-10-08"}])
    for url in (f"{WWW}/privado/x", f"{WWW}/nota"):
        decision = gate(opted).evaluate(intent(url=url), PRIVATE)
        assert (decision.decision, decision.reasons, decision.acquisition_decision) == ("DENY", ("explicit_opt_out",), "HOLD")
        assert decision.evidence["hold_class"] == "DIRECT_OPT_OUT" and decision.evidence["opt_out"]["reason"] == "publisher e-mail"
    assert gate(opted).evaluate(intent(url=f"{WWW}/robots.txt", kind="robots_txt")).decision == "DENY"


def test_a_legal_review_hold_needs_a_named_source_and_holds_exactly_it():
    block = {**json.loads(json.dumps(RESEARCH)), "legal_review_holds": [{"origin": MOBILE, "reason": "letter of counsel", "recorded_at": "2026-10-08"}]}
    held = decided(robots=dict(OVERRIDE), research_tdm=block)
    decision = gate(held).evaluate(intent(url=f"{MOBILE}/x"), ABSENT)
    assert (decision.decision, decision.reasons, decision.acquisition_decision) == ("DENY", ("legal_review_hold",), "HOLD")
    assert decision.evidence["hold_class"] == "LEGAL_REVIEW_HOLD"
    assert gate(held).evaluate(intent(url=f"{WWW}/privado/x"), PRIVATE).acquisition_decision == "ALLOW_RESEARCH_OVERRIDE"
    with pytest.raises(P.PolicyError, match="legal review hold"):
        P.validate_policy(decided(research_tdm={**RESEARCH, "legal_review_holds": [{"reason": "a feeling"}]}))


def test_crawl_delay_binds_under_an_override_and_an_origin_that_asks_too_much_is_not_fetched():
    slow = RB.evidence_from_response(200, b"User-agent: *\nCrawl-delay: 25\nDisallow: /privado/\n")
    rate = {"min_interval_seconds_per_origin": 10, "crawl_delay": "binding_minimum", "crawl_delay_max_seconds": 60}
    g = gate(research(rate_limit=rate))
    decision = g.evaluate(intent(url=f"{WWW}/privado/x"), slow)
    assert decision.acquisition_decision == "ALLOW_RESEARCH_OVERRIDE" and decision.evidence["robots_crawl_delay_binding_seconds"] == 25.0
    assert g.interval_seconds(slow) == 25.0 and g.interval_seconds(PRIVATE) == 10.0     # max(project minimum, Crawl-delay)
    slower = RB.evidence_from_response(200, b"User-agent: *\nCrawl-delay: 600\nDisallow: /privado/\n")
    for url in (f"{WWW}/privado/x", f"{WWW}/nota"):
        refused = g.evaluate(intent(url=url), slower)
        assert (refused.decision, refused.reasons, refused.acquisition_decision) == ("DENY", ("robots_crawl_delay_exceeds_limit",), "REFUSE")


def test_the_most_specific_rule_decides_which_layer_is_asked():
    rules = RB.evidence_from_response(200, b"User-agent: *\nDisallow: /a/\nAllow: /a/b/\nDisallow: /a/b/c/\n")
    g = gate(research())
    assert layers(g.evaluate(intent(url=f"{WWW}/a/b/x"), rules))[2:] == ("ROBOTS_ALLOW", "RESEARCH_TDM_ELIGIBLE", "ALLOW")
    for url, rule in ((f"{WWW}/a/x", "disallow: /a/"), (f"{WWW}/a/b/c/x", "disallow: /a/b/c/")):
        decision = g.evaluate(intent(url=url), rules)
        assert decision.acquisition_decision == "ALLOW_RESEARCH_OVERRIDE" and decision.evidence["override"]["robots_rule"] == rule


def test_the_group_for_this_crawler_is_read_instead_of_the_wildcard_group():
    named_out = RB.evidence_from_response(200, f"User-agent: *\nAllow: /\n\nUser-agent: {TOKEN}\nDisallow: /\n".encode())
    named_in = RB.evidence_from_response(200, f"User-agent: *\nDisallow: /\n\nUser-agent: {TOKEN.upper()}\nAllow: /\n".encode())
    g = gate(research())
    out = g.evaluate(intent(), named_out)
    assert out.acquisition_decision == "ALLOW_RESEARCH_OVERRIDE" and out.evidence["override"]["robots_rule"] == "disallow: /"
    assert layers(g.evaluate(intent(), named_in))[2:] == ("ROBOTS_ALLOW", "RESEARCH_TDM_ELIGIBLE", "ALLOW")
    assert layers(gate(decided()).evaluate(intent(), named_out))[4] == "REFUSE"         # enforce: the group that names us binds


def test_a_robots_file_that_is_not_one_is_a_parse_error_and_holds():
    page_instead = RB.evidence_from_response(200, b"<!doctype html><html><body>P\xc3\xa1gina no encontrada</body></html>")
    assert page_instead.rules.parse_error
    decision = gate(research()).evaluate(intent(), page_instead)
    assert layers(decision) == ("DEFER", "robots_parse_error", "ROBOTS_PARSE_ERROR", None, "HOLD")
    lenient = research(robots={**OVERRIDE, "on_parse_error": "allow"})
    assert layers(gate(lenient).evaluate(intent(), page_instead))[:3] == ("ALLOW", "allowed_by_policy", "ROBOTS_PARSE_ERROR")
    for readable in (b"", b"# nothing here\n", b"\xef\xbb\xbfUser-agent: *\nDisallow: /privado/\n", b"User-agent: *\nDisallow:\nfoo bar\n"):
        assert not RB.parse_robots(readable).parse_error
    with_mark = RB.parse_robots(b"\xef\xbb\xbfUser-agent: *\nDisallow: /privado/\n")     # a byte-order mark does not hide the first group
    assert with_mark.evaluate(TOKEN, "/privado/x")[0] == RB.DISALLOWED


def test_an_unavailable_robots_file_allows_and_an_unreachable_one_holds():
    g = gate(research())
    assert layers(g.evaluate(intent(), RB.evidence_from_response(404, b""))) == (
        "ALLOW", "allowed_by_policy", "ROBOTS_UNAVAILABLE", "RESEARCH_TDM_ELIGIBLE", "ALLOW")
    for unreachable in (RB.evidence_from_response(503, b""), RB.evidence_from_response(None, None)):
        assert layers(g.evaluate(intent(), unreachable)) == ("DEFER", "robots_unreachable", "ROBOTS_UNREACHABLE", None, "HOLD")
    assert layers(g.evaluate(intent()))[:2] == ("DEFER", "robots_not_consulted")         # never decided without the evidence


def test_no_decision_allows_a_disallowed_path_without_saying_so():
    """The regression invariant: there is no hidden fallback. Over every mode, every state of the
    research layer and every kind of robots evidence, a disallowed path is allowed only as
    ``ALLOW_RESEARCH_OVERRIDE`` with an override record — and only under the mode that names it.
    """
    blocks = [json.loads(json.dumps(RESEARCH)), {"basis": "not_applicable", "decision": "not_applicable", "conditions": {}, "legal_review_holds": []}]
    broken = json.loads(json.dumps(RESEARCH))
    broken["conditions"]["protected_research_storage"] = False
    blocks.append(broken)
    seen = set()
    for mode, block, access in itertools.product(("enforce", "research_tdm_override"), blocks, (None, AC.CAPTCHA)):
        try:
            policy = decided(robots={**OVERRIDE, "mode": mode}, research_tdm=block)
            g = gate(policy)
        except P.PolicyError:
            continue
        decision = g.evaluate(intent(url=f"{WWW}/privado/x"), PRIVATE, access_observed=access)
        seen.add(decision.acquisition_decision)
        if decision.allowed:
            assert mode == "research_tdm_override" and access is None and block is blocks[0]
            assert decision.acquisition_decision == "ALLOW_RESEARCH_OVERRIDE" and decision.evidence["override"]["basis"] == block["basis"]
    assert seen == {"ALLOW_RESEARCH_OVERRIDE", "REFUSE", "HOLD"}


def test_a_policy_from_configuration_cannot_ignore_robots_silently(tmp_path):
    silent = {**research(robots={**OVERRIDE, "mode": "record_only"}), "external_acquisition": "disabled"}
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(silent), encoding="utf-8")
    with pytest.raises(P.PolicyError, match="silently"):
        P.load_policy(path)


def test_the_tracked_policy_pins_its_research_layer():
    tracked = P.load_policy()
    pin = P.research_tdm_pin(tracked)
    assert pin == P.research_tdm_pin(P.load_policy()) and len(pin["research_tdm_policy_sha256"]) == 64
    assert (pin["research_tdm_policy_version"], pin["decided_in"], pin["robots_decision_semantics"], pin["robots_mode"]) == (
        "SCIENTIFIC_TDM_POLICY_V1", "CPD-0017", "robots-decision/2", "research_tdm_override")
    changed = json.loads(json.dumps(tracked))
    changed["research_tdm"]["conditions"]["non_commercial"] = False
    slower = json.loads(json.dumps(tracked))
    slower["rate_limit"]["min_interval_seconds_per_origin"] = 11
    assert len({pin["research_tdm_policy_sha256"], P.research_tdm_pin(changed)["research_tdm_policy_sha256"],
                P.research_tdm_pin(slower)["research_tdm_policy_sha256"]}) == 3
    note = tracked["note"]
    assert "not a claim of conformance with RFC 9309" in note and "not legal advice" in note


# --- access controls, at the transport ------------------------------------------------------------------

CHALLENGE = b"<html><head><title>Just a moment...</title></head><body><script src='/cdn-cgi/challenge-platform/h/b/orchestrate'></script></body></html>"
CAPTCHA_PAGE = b"<html><body><form><div class='g-recaptcha' data-sitekey='x'></div></form></body></html>"

REFUSALS = {
    "401": (Response(401, HTML + [("WWW-Authenticate", 'Basic realm="x"')], b"<html>auth</html>"), AC.AUTH_REQUIRED),
    "403": (Response(403, HTML, b"<html>forbidden</html>"), AC.FORBIDDEN),
    "429": (Response(429, HTML + [("Retry-After", "5")], b"<html>slow</html>"), AC.RATE_LIMITED),
    "451": (Response(451, HTML, b"<html>legal</html>"), AC.LEGAL_BLOCK),
    "captcha_200": (Response(200, HTML, CAPTCHA_PAGE), AC.CAPTCHA),
    "captcha_403": (Response(403, HTML, CAPTCHA_PAGE), AC.CAPTCHA),
    "challenge_503": (Response(503, HTML, CHALLENGE), AC.BOT_CHALLENGE),
    "challenge_gzip": (Response(403, HTML + [("Content-Encoding", "gzip")], gzip.compress(CHALLENGE)), AC.BOT_CHALLENGE),
    "challenge_header": (Response(403, HTML + [("cf-mitigated", "challenge")], b"<html></html>"), AC.BOT_CHALLENGE),
}


@pytest.mark.parametrize("name", sorted(REFUSALS))
def test_an_access_control_is_recorded_ends_the_call_and_holds_the_origin(site, name):
    response, expected = REFUSALS[name]
    site.routes.update({"/robots.txt": Response(200, ROBOTS_TXT, b"User-agent: *\nDisallow: /cerrado\n"),
                        "/cerrado": [response, Response(200, HTML, PAGE)], "/otra": Response(200, HTML, PAGE)})
    fetcher, clock = make_fetcher(site, policy=loopback())                      # three attempts are allowed by the limits
    outcome = get(fetcher, "/cerrado")
    assert len(outcome.attempts) == 1 and outcome.last.policy["access_class_observed"] == expected
    assert outcome.last.policy["policy_decision"] == "ALLOW_RESEARCH_OVERRIDE"  # the request went out under the override, and was refused
    assert clock.slept == [] and site.paths().count("/cerrado") == 1            # not retried, not waited out
    asked = len(site.requests)
    for path in ("/cerrado", "/otra", "/robots.txt"):
        later = get(fetcher, path)
        assert (later.final, later.decision.reasons, later.decision.acquisition_decision) == ("DENIED", ("access_control_observed",), "HOLD")
    assert len(site.requests) == asked                                          # nothing more was asked of the origin
    assert fetcher.access_holds == {WWW: expected}


def test_a_refused_robots_file_is_an_access_control_not_an_absent_robots_file(site):
    site.routes.update({"/robots.txt": Response(403, HTML, b"<html>forbidden</html>"), "/nota": Response(200, HTML, PAGE)})
    fetcher, _ = make_fetcher(site, policy=loopback())
    outcome = get(fetcher, "/nota")
    assert (outcome.final, outcome.decision.reasons) == ("DENIED", ("access_control_observed",)) and site.paths() == ["/robots.txt"]
    assert fetcher.robots_exchanges[0][1].policy["access_class_observed"] == "forbidden"
    absent, _ = make_fetcher(site, policy=loopback())
    site.routes["/robots.txt"] = Response(404, HTML, b"")
    assert get(absent, "/nota").final == "FETCHED"                              # 404: no robots file, and no refusal


@pytest.mark.parametrize("target, expected", [("/login?next=/nota", AC.LOGIN_REDIRECT), ("/iniciar-sesion", AC.LOGIN_REDIRECT),
                                              ("/suscripcion/planes", AC.PAYWALL_REDIRECT), (f"{MOBILE}/paywall", AC.PAYWALL_REDIRECT)])
def test_a_redirect_to_a_login_or_a_paywall_is_not_followed(site, target, expected):
    site.routes.update({"/nota": Response(302, [("Location", target)] + HTML, b"<html>redirigiendo</html>"),
                        "/otra": Response(200, HTML, PAGE)})
    fetcher, _ = make_fetcher(site, policy=loopback())
    exchange = get(fetcher, "/nota").last
    assert exchange.status == 302 and exchange.redirect_chain == () and exchange.policy["access_class_observed"] == expected
    assert exchange.redirect_not_followed == f"ACCESS_CONTROL_OBSERVED: {expected}"
    assert [path for path in site.paths() if path not in ("/robots.txt", "/nota")] == []     # the target was never requested
    assert get(fetcher, "/otra").final == "FETCHED" and fetcher.access_holds == {}           # one page behind a wall is not a refusing origin


def test_an_article_whose_address_only_mentions_such_a_word_is_followed(site):
    assert AC.classify_redirect(f"{WWW}/politica/acceso-a-la-salud-y-login-social") is None
    assert AC.classify_redirect(f"{WWW}/economia/suscripcion-de-acciones-2026.html") is None
    assert AC.classify_redirect("https://login.diario-ejemplo.test/") == AC.LOGIN_REDIRECT
    assert AC.classify_response(200, HTML, PAGE) == AC.NONE_OBSERVED and AC.classify_response(404, HTML, b"") == AC.NONE_OBSERVED
    long_article = b"<html><body>" + b"<p>texto</p>" * 4000 + b"<div class='g-recaptcha'></div></body></html>"
    assert AC.classify_response(200, HTML, long_article) == AC.NONE_OBSERVED    # a form widget on a full page is not a challenge


def test_nothing_about_the_client_changes_after_a_refusal(site):
    """No rotation, no cookie, no second identity: every request of a fetcher that was refused, robots
    file included, carries the same headers, and none of them is a credential or a browser's name.
    """
    site.routes.update({"/robots.txt": Response(200, ROBOTS_TXT, b"User-agent: *\nAllow: /\n"),
                        "/a": Response(200, HTML + [("Set-Cookie", "session=abc")], PAGE),
                        "/b": Response(403, HTML + [("Set-Cookie", "challenge=1")], CHALLENGE), "/c": Response(200, HTML, PAGE)})
    fetcher, _ = make_fetcher(site, policy=loopback())
    for path in ("/a", "/b", "/c", "/b"):
        get(fetcher, path)
    assert site.paths() == ["/robots.txt", "/a", "/b"]
    sent = [{name: value for name, value in headers.items() if name != "host"} for _, headers in site.requests]
    assert all(headers == sent[0] for headers in sent)
    assert not {"cookie", "authorization", "proxy-authorization", "referer", "x-forwarded-for"} & set(sent[0])
    assert sent[0]["user-agent"] == fetcher.identity.user_agent and "Mozilla" not in sent[0]["user-agent"]


def test_an_overridden_request_is_a_fetch_record_that_says_so(site):
    site.routes.update({"/robots.txt": Response(200, ROBOTS_TXT, b"User-agent: *\nDisallow: /privado/\n"),
                        "/privado/nota": Response(200, HTML + [("tdm-reservation", "1")], PAGE), "/nota": Response(200, HTML, PAGE),
                        "/viejo": Response(301, [("Location", "/privado/nota")])})
    fetcher, _ = make_fetcher(site, policy=loopback())
    overridden, plain, hop = get(fetcher, "/privado/nota"), get(fetcher, "/nota"), get(fetcher, "/viejo")
    assert (overridden.final, overridden.decision.reasons, overridden.decision.acquisition_decision) == (
        "FETCHED", ("research_tdm_override",), "ALLOW_RESEARCH_OVERRIDE")
    assert (overridden.last.policy["policy_decision"], overridden.last.policy["robots_decision"]) == ("ALLOW_RESEARCH_OVERRIDE", "disallowed")
    assert (plain.last.policy["policy_decision"], plain.last.policy["robots_decision"]) == ("ALLOW", "allowed")
    assert (hop.last.policy["policy_decision"], hop.last.policy["robots_decision"]) == ("ALLOW_RESEARCH_OVERRIDE", "disallowed")  # a hop into a disallowed path
    run = H.http_fetch_run(fetcher.clock(), [OUTLET], {"test": "research"}, fetcher.identity)
    record = A.build_fetch_record(run, OUTLET, overridden.last)
    assert record["policy"]["policy_decision"] == "ALLOW_RESEARCH_OVERRIDE" and record["policy"]["robots_txt_sha256"] != "not_applicable"
    # A general machine-readable reservation is evidence, recorded with the response; it is not what decides research TDM.
    assert AC.tdm_reservation(overridden.last.response_headers) == "1" and AC.tdm_reservation(plain.last.response_headers) is None
    with pytest.raises(A.AcquisitionError):
        A.build_fetch_record(run, OUTLET, A.RecordedExchange(**{**overridden.last.__dict__, "policy": {**overridden.last.policy, "policy_decision": "REFUSE"}}))


# --- the whole driver -----------------------------------------------------------------------------------


def test_the_driver_reads_disallowed_paths_under_the_override_and_its_receipt_counts_them(tmp_path, site):
    scripted(site, paths=("/ok", "/privado/uno", "/privado/dos", "/gone404"))
    site.routes.update({"/privado/uno": page(11), "/privado/dos": page(12)})
    run = Drive(tmp_path / "research", site, policy=loopback())
    run.go()
    receipt = run.receipt()
    stats = receipt["policy_layers"]
    assert {"/privado/uno", "/privado/dos", "/ok"} <= set(site.paths()) and not any(key.endswith("robots_disallow") for key in receipt["refused"])
    assert stats["requests_under_research_override"] == 2 == stats["answered_2xx_under_research_override"]
    assert stats["outlets_with_applicable_disallow"] == [OUTLET] and stats["outlets_with_access_control"] == []
    assert stats["acquisition_decisions"]["ALLOW_RESEARCH_OVERRIDE"] == 2 and stats["semantics"] == "robots-decision/2"
    assert receipt["research_tdm"] == P.research_tdm_pin(run.fetcher.gate.policy)
    rows = [row for row in H.request_rows(run.workspace) if row["event"] == "FINISHED" and (row.get("policy_layers") or {}).get("override")]
    assert sorted(row["url"] for row in rows) == [f"{WWW}/privado/dos", f"{WWW}/privado/uno"]
    assert all(row["policy_layers"]["override"]["basis"] == "SCIENTIFIC_TDM_POLICY_V1" for row in rows)
    overridden = [r for r in D.fetch_records(run.workspace) if r["policy"]["policy_decision"] == "ALLOW_RESEARCH_OVERRIDE"]
    assert len(overridden) == 2 and all(run.states()[r["fetch_id"]] == "RAW_PRESERVED" for r in overridden)
    assert receipt["requests"]["total"] == run.fetcher.used_total() == len(site.requests)


def test_the_driver_stops_asking_an_origin_that_refused_and_a_restart_does_not_ask_again(tmp_path, site):
    scripted(site, paths=("/a1", "/a2", "/a3", "/a4"))
    site.routes.update({path: Response(403, HTML, CHALLENGE) for path in ("/a1", "/a2", "/a3", "/a4")})
    run = Drive(tmp_path / "blocked", site, policy=loopback())
    run.go()
    asked = [path for path in site.paths() if path.startswith("/a")]
    assert len(asked) == 1                                                       # the first refusal was the last request for an item
    receipt = run.receipt()
    stats = receipt["policy_layers"]
    assert receipt["refused"]["DENIED:access_control_observed"] == 3 == stats["requests_stopped_by_access_control"]
    assert stats["outlets_with_access_control"] == [OUTLET] and stats["holds"] == {"ACCESS_CONTROL_OBSERVED": 3}
    assert stats["by_outlet"][OUTLET]["access_classes_observed"]["bot_challenge"] == 1
    assert receipt["requests"]["total"] <= SMALL.total_requests_ceiling and receipt["requests"]["total"] == len(site.requests)
    held = [r for r in D.fetch_records(run.workspace) if r["policy"]["access_class_observed"] == "bot_challenge"]
    assert len(held) == 1 and run.states()[held[0]["fetch_id"]] == "RAW_PRESERVED"   # the refusal itself is preserved as evidence
    assert D.access_holds_from_evidence(run.workspace) == {WWW: "bot_challenge"} == D.access_holds_from_evidence(run.workspace, run.run.run_id)
    before = len(site.requests)
    again = Drive(tmp_path / "blocked", site, policy=loopback())                # a new process on the same workspace
    again.fetcher.access_holds.update(D.access_holds_from_evidence(again.workspace))
    again.run = run.run
    again.go()
    assert [path for path in site.paths()[before:] if path.startswith("/a")] == []


def test_the_canary_pin_holds_the_research_layer_and_the_deployed_crawler_page(tmp_path, site):
    from coprepan import preservation_target as PT
    from test_canary_driver import T0
    drive = Drive(tmp_path / "pin", site)
    PT.initialise_target(drive.root, "coprepan-preservation-test", operator="test", now=T0)
    checkout = site_checkout(tmp_path)
    pin = D.canary_pin(SMALL, drive.registry, [OUTLET], [], drive.root, loopback(), repository=checkout)
    assert pin["research_tdm"] == P.research_tdm_pin(loopback()) and pin["access_control_classifier"] == AC.CLASSIFIER_VERSION
    assert pin["crawler_page"]["receipt"] == "DEPLOY_RECEIPT_2026-10-08.json" and len(pin["crawler_page"]["crawler_page_sha256"]) == 64
    enforce = D.canary_pin(SMALL, drive.registry, [OUTLET], [], drive.root, P.loopback_test_policy(), repository=checkout)
    assert enforce["research_tdm"] != pin["research_tdm"] and enforce["driver"] == pin["driver"]
    for broken in (site_checkout(tmp_path / "edited", local=b"<html>edited after the deployment</html>"),
                   site_checkout(tmp_path / "unchecked", matched=False), tmp_path / "nothing"):
        with pytest.raises(D.CanaryStopped):
            D.canary_pin(SMALL, drive.registry, [OUTLET], [], drive.root, loopback(), repository=broken)


def test_the_crawler_page_of_this_checkout_says_what_the_policy_does():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / "web" / "coprepan" / "crawler" / "index.html").read_text(encoding="utf-8")
    plain = " ".join(text.split())
    for said in ("does not treat every", "as an absolute exclusion", "scientific text and data mining", "is recorded",
                 "does not bypass authentication", "Crawl-delay", "Retry-After", "opt-out"):
        assert said in plain, said
    for unsaid in ("A <code>Disallow</code> rule that applies to it is followed", "ignores robots.txt", "RFC 9309 compliant"):
        assert unsaid not in plain
    pin = D.crawler_page_pin()                     # the page of this checkout is the page the latest receipt says is public
    assert pin["site_url"] == "https://coprepan.hispanistica.com/" and pin["receipt"].startswith("DEPLOY_RECEIPT_")
