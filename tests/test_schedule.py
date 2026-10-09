"""Re-fetch scheduling, candidate qualification and channel health: pure functions of recorded
evidence. Every number in these tests is a test input, not a recommended policy value.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from coprepan import candidate_filter as CF
from coprepan import channel_health as CH
from coprepan import discovery as D
from coprepan import schedule as S
from coprepan.identity import OutletUrlRules, format_instant

REPO = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)
HOUR, DAY = 3600, 86400
OUTLET = "uy_diario_ejemplo"
WWW = "https://www.diario-ejemplo.test"
CAND = f"{OUTLET}:cand:0000000000000001"
POLICY = S.SchedulePolicy(
    version="test-schedule/1", revisit_after_success_seconds=DAY, revisit_backoff_factor=2,
    revisit_max_interval_seconds=8 * DAY, revisit_window_seconds=30 * DAY, retry_after_failure_seconds=HOUR,
    failure_backoff_factor=2, failure_max_interval_seconds=6 * HOUR, max_consecutive_failures=3,
    failure_cooldown_seconds=7 * DAY, gone_recheck_seconds=3 * DAY, max_gone_rechecks=2,
    denied_recheck_seconds=5 * DAY, use_conditional_requests=True)


def at(hours=0.0):
    return T0 + timedelta(hours=hours)


def row(hours, final="FETCHED", status=200, body="a" * 64, **extra):
    """A FINISHED request-log row as http_acquisition writes it."""
    result = {"status": status if final == "FETCHED" else None, "body_sha256": body if status == 200 else None,
              "etag": extra.pop("etag", None), "last_modified": extra.pop("last_modified", None),
              "failure_reason": extra.pop("failure_reason", None), "revalidates": extra.pop("revalidates", None),
              "moved_permanently_to": extra.pop("moved_to", None), "redirect_not_followed": extra.pop("not_followed", None)}
    return {"event": "FINISHED", "fetch_kind": "item", "candidate_id": CAND, "final": final, "result": result,
            "finished_at": format_instant(at(hours)), "policy_version": extra.pop("policy_version", "policy/1"),
            "policy_reasons": extra.pop("reasons", ["allowed_by_policy"]), "retry_at": extra.pop("retry_at", None),
            "fetch_ids": ["ft1:" + "f" * 64], "attempts": extra.pop("attempts", [])}


def state(rows, policy=POLICY, version="policy/1"):
    return S.lifecycle(CAND, T0, [S.outcome_of(r) for r in rows], policy, current_policy_version=version)


# --- the tracked schedule policy fails closed -------------------------------------------------------


def test_the_tracked_schedule_policy_is_the_decided_canary_policy():
    """Decided for the canary (CPD-0013): slow on purpose. Nothing is asked twice within a day, a
    failing candidate is left alone after three failures, an absent one is retired after one recheck.
    """
    policy = S.load_schedule_policy()
    assert policy.version.startswith("canary/") and policy.use_conditional_requests is True
    assert policy.revisit_after_success_seconds >= 86400 and policy.retry_after_failure_seconds >= 3600
    assert policy.max_consecutive_failures <= 3 and policy.max_gone_rechecks <= 1
    assert policy.failure_cooldown_seconds >= 86400 and policy.denied_recheck_seconds >= 86400
    document = json.loads((REPO / "config" / "schedule_policy.json").read_text(encoding="utf-8"))
    assert "not_decided" not in document.values()


def test_a_schedule_policy_has_no_default_and_refuses_half_decided_values(tmp_path):
    with pytest.raises(TypeError):
        S.SchedulePolicy(version="x")
    values = {f: getattr(POLICY, f) for f in POLICY.__dataclass_fields__}
    for bad in ({"revisit_after_success_seconds": "not_decided"}, {"max_consecutive_failures": -1}, {"version": "undecided"},
                {"use_conditional_requests": "yes"}, {"revisit_backoff_factor": 0.5}):
        with pytest.raises(S.ScheduleNotDecided):
            S.SchedulePolicy(**{**values, **bad})
    path = tmp_path / "schedule.json"
    path.write_text(json.dumps({"schema": "coprepan-schedule-policy/v1", "status": "DECIDED", **values}), encoding="utf-8")
    assert S.load_schedule_policy(path) == POLICY
    path.write_text(json.dumps({"schema": "coprepan-schedule-policy/v1", "status": "NOT_DECIDED", **values}), encoding="utf-8")
    with pytest.raises(S.ScheduleNotDecided):
        S.load_schedule_policy(path)


# --- lifecycle --------------------------------------------------------------------------------------


def test_never_fetched_is_due_from_its_first_listing():
    s = state([])
    assert (s.state, s.due_at, s.attempts) == ("NEVER_FETCHED", T0, 0)


def test_success_then_unchanged_backs_off_and_changed_content_resets():
    assert state([row(0)]).due_at == at(24)                                   # first revisit
    assert state([row(0), row(24)]).due_at == at(24 + 48)                     # unchanged once: interval doubles
    assert state([row(0), row(24), row(72)]).due_at == at(72 + 96)            # unchanged twice
    capped = state([row(0), row(24), row(72), row(168), row(360)])
    assert capped.due_at == at(360 + 8 * 24)                                  # never beyond the maximum
    changed = state([row(0), row(24), row(72, body="b" * 64)])
    assert (changed.state, changed.due_at, changed.reason) == ("FETCHED", at(72 + 24), "answered; first revisit")


def test_not_modified_counts_as_unchanged():
    held = {"fetch_id": "ft1:" + "f" * 64, "body_sha256": "a" * 64}
    s = state([row(0, etag='"v1"'), row(24, status=304, revalidates=held)])
    assert (s.state, s.due_at) == ("FETCHED", at(24 + 48))
    assert s.conditional == {"if_none_match": '"v1"', "revalidates_fetch_id": "ft1:" + "f" * 64, "revalidates_body_sha256": "a" * 64}


def test_conditional_requests_are_offered_only_with_a_validator_and_only_when_the_policy_says_so():
    assert state([row(0)]).conditional is None                                # nothing to validate with
    with_both = state([row(0, etag='W/"x"', last_modified="Mon, 05 Oct 2026 08:30:00 GMT")]).conditional
    assert with_both["if_none_match"] == 'W/"x"' and with_both["if_modified_since"] == "Mon, 05 Oct 2026 08:30:00 GMT"
    off = S.SchedulePolicy(**{**{f: getattr(POLICY, f) for f in POLICY.__dataclass_fields__}, "use_conditional_requests": False})
    assert state([row(0, etag='"v1"')], policy=off).conditional is None


def test_the_revisit_window_closes_and_nothing_is_deleted():
    s = state([row(0), row(31 * 24)])
    assert (s.state, s.due_at, s.reason) == ("SETTLED", None, "revisit window closed")


def test_clock_boundary_due_exactly_now_is_due():
    candidates = {CAND: {"first_listed_at": format_instant(T0)}}
    rows = [row(0)]
    for now, expected in ((at(24) - timedelta(microseconds=1), 0), (at(24), 1), (at(24) + timedelta(microseconds=1), 1)):
        due, _ = S.plan(candidates, rows, POLICY, now=now, current_policy_version="policy/1", limit=10)
        assert len(due) == expected


def test_repeated_failures_back_off_then_suspend_and_come_back():
    fail = lambda h: row(h, final="FETCH_FAILED", failure_reason="timeout")  # noqa: E731
    assert (state([fail(0)]).state, state([fail(0)]).due_at) == ("FAILING", at(1))
    assert state([fail(0), fail(1)]).due_at == at(1 + 2)
    suspended = state([fail(0), fail(1), fail(3)])
    assert (suspended.state, suspended.due_at) == ("SUSPENDED", at(3 + 7 * 24))  # a cooldown, not a blacklist
    recovered = state([fail(0), fail(1), fail(3), row(200)])
    assert (recovered.state, recovered.due_at) == ("FETCHED", at(200 + 24))
    assert state([row(0), fail(24)]).state == "FAILING"                          # a failure after a success is one failure


def test_429_and_5xx_are_transient_and_retry_after_is_honoured():
    assert state([row(0, status=503)]).state == "FAILING" and state([row(0, status=429)]).due_at == at(1)
    patient = row(0, status=429, attempts=[{"number": 1, "retry": "gave_up", "retry_after": format_instant(at(10))}])
    assert state([patient]).due_at == at(10)                                     # the server asked for more than the backoff
    assert state([row(0, status=304)]).state == "FAILING"                        # a 304 nobody asked for is not a success


def test_404_and_410_are_rechecked_a_bounded_number_of_times():
    assert (state([row(0, status=404)]).state, state([row(0, status=404)]).due_at) == ("ABSENT", at(72))
    assert state([row(0, status=404), row(72, status=410)]).state == "ABSENT"
    retired = state([row(0, status=404), row(72, status=410), row(144, status=404)])
    assert (retired.state, retired.due_at) == ("RETIRED", None)
    assert state([row(0, status=404), row(72)]).state == "FETCHED"               # it came back: counted from there


def test_refused_by_server_and_redirect_not_followed_are_rechecked_slowly():
    for status in (401, 403, 451):
        assert (state([row(0, status=status)]).state, state([row(0, status=status)]).due_at) == ("REFUSED", at(5 * 24))
    blocked = state([row(0, status=302, not_followed="DENY: off_origin")])
    assert blocked.state == "REFUSED" and "off_origin" in blocked.reason


def test_a_permanent_redirect_ends_the_old_candidate_without_losing_it():
    target = f"{OUTLET}:cand:00000000000000ff"
    s = state([row(0, moved_to=target)])
    assert (s.state, s.due_at, s.moved_to) == ("MOVED", None, target)


def test_policy_deny_is_re_asked_when_the_policy_changes_and_suppression_ends_at_its_time():
    denied = row(0, final="DENIED", reasons=["explicit_opt_out"])
    assert (state([denied]).state, state([denied]).due_at) == ("DENIED", at(5 * 24))
    assert state([denied], version="policy/2").due_at == at(0)                   # a new policy is a new question
    robots = row(0, final="DENIED", reasons=["robots_disallow"])
    assert "robots_disallow" in state([robots]).reason
    deferred = row(0, final="DEFERRED", reasons=["temporarily_suppressed"], retry_at=format_instant(at(36)))
    assert (state([deferred]).state, state([deferred]).due_at) == ("DEFERRED", at(36))


def test_the_plan_is_deterministic_ordered_and_limited():
    candidates = {f"{OUTLET}:cand:{n:016x}": {"first_listed_at": format_instant(at(-n))} for n in range(1, 6)}
    due, states = S.plan(candidates, [], POLICY, now=T0, current_policy_version="policy/1", limit=3)
    assert [s.candidate_id[-1] for s in due] == ["5", "4", "3"] and len(states) == 5    # oldest due first
    again, _ = S.plan(dict(reversed(list(candidates.items()))), [], POLICY, now=T0, current_policy_version="policy/1", limit=3)
    assert [s.as_row() for s in again] == [s.as_row() for s in due]                    # input order does not matter
    assert S.plan(candidates, [], POLICY, now=T0, current_policy_version="policy/1", limit=0)[0] == []
    assert due[0].as_row()["planner"] == "fetch-planner/1"


def test_history_rows_are_read_never_written():
    rows = [row(0), row(24, status=503)]
    before = json.dumps(rows, sort_keys=True)
    S.plan({CAND: {"first_listed_at": format_instant(T0)}}, rows, POLICY, now=at(100), current_policy_version="policy/1", limit=5)
    assert json.dumps(rows, sort_keys=True) == before
    assert S.histories([{"event": "PLANNED", "candidate_id": CAND}, {**row(0), "fetch_kind": "channel_document"}]) == {}


# --- candidate qualification ------------------------------------------------------------------------


def cand(path, outlet=OUTLET):
    key = f"{WWW}{path}"
    return {"candidate_id": D.candidate_id(outlet, key), "outlet_id": outlet, "url_key": key}


@pytest.mark.parametrize(
    "path, decision, reason",
    [("/Economia/Nota-1.html", "QUALIFIED", "no_rule_rejects"), ("/breves/123/", "QUALIFIED", "no_rule_rejects"),
     ("/", "REJECTED", "generic: site_root_is_not_an_item"), ("/img/puerto.JPG", "REJECTED", "generic: asset_extension .jpg"),
     ("/static/app.js", "REJECTED", "generic: asset_extension .js"),
     ("/docs/informe.pdf", "REJECTED", "generic: binary_document_out_of_scope .pdf"),
     ("/sitemap.xml", "REJECTED", "generic: channel_document_extension .xml"),
     ("/rss", "REJECTED", "generic: is_a_registered_channel_document"),
     ("/nota.v2/texto", "QUALIFIED", "no_rule_rejects"), ("/?id=7", "QUALIFIED", "no_rule_rejects")],
)
def test_generic_rules_are_about_the_url_only(path, decision, reason):
    row_ = CF.qualify(cand(path), channel_url_keys=frozenset({f"{WWW}/rss"}))
    assert (row_["decision"], row_["reasons"][0]) == (decision, reason)
    assert row_["ruleset"] == "candidate-filter-generic/3+no-outlet-rules"


def test_outlet_rules_reject_allow_and_conflict():
    rules = {"version": "uy_diario_ejemplo-candidates/1", "reject_path_prefixes": ["/tag", "/autor"],
             "reject_path_patterns": [r"/galeria/"], "allow_path_patterns": [r"-\d+\.html$", r"^/tag/destacado"]}
    listing = f"{OUTLET}:ch:section_page_001"
    # the candidates of a listing: an allow pattern says which of them are articles
    q = lambda path: CF.qualify({**cand(path), "first_channel_id": listing}, outlet_rules=rules, listing_channel_ids=frozenset({listing}))  # noqa: E731
    # the candidates of a feed of the same outlet: reject rules apply, the allow patterns do not narrow them (`/3`)
    fed = lambda path: CF.qualify({**cand(path), "first_channel_id": f"{OUTLET}:ch:rss_001"}, outlet_rules=rules, listing_channel_ids=frozenset({listing}))  # noqa: E731
    assert (fed("/sin-numero")["decision"], fed("/sin-numero")["reasons"]) == ("QUALIFIED", ["no_rule_rejects"])
    assert fed("/tag/economia")["reasons"] == ["outlet: path_prefix /tag"] and fed("/Economia/Nota-1.html")["decision"] == "QUALIFIED"
    assert q("/Economia/Nota-1.html")["decision"] == "QUALIFIED"
    assert q("/tag/economia")["reasons"] == ["outlet: path_prefix /tag", "outlet: not_matched_by_any_allow_pattern"]
    assert q("/tagliatelle-1.html")["decision"] == "QUALIFIED"               # a prefix ends at a segment boundary
    assert q("/sin-numero")["reasons"] == ["outlet: not_matched_by_any_allow_pattern"]
    conflict = q("/tag/destacado")
    assert conflict["decision"] == "DEFERRED" and conflict["reasons"][0] == "conflicting_rules"
    assert "outlet: allow_pattern ^/tag/destacado" in conflict["reasons"] and "outlet: path_prefix /tag" in conflict["reasons"]
    assert CF.qualify(cand("/galeria/1.jpg"), outlet_rules=rules)["decision"] == "REJECTED"
    assert q("/x")["ruleset"] == "candidate-filter-generic/3+uy_diario_ejemplo-candidates/1"


def test_an_outlet_without_rules_gets_generic_rules_and_the_tracked_file_guesses_none():
    # No legacy evidence, no invented rule: the only entries are the two written on 2026-10-09 from listing pages that
    # wave C1 preserved (reviewed in the run report; held against those pages in tests/test_canary_findings.py).
    assert sorted(CF.load_rules()) == ["hn_criterio", "pr_noticel"]
    assert CF.qualify(cand("/x", outlet="zz_desconocido"), outlet_rules=None)["decision"] == "QUALIFIED"


@pytest.mark.parametrize(
    "rules",
    [{"version": ""}, {"version": "v1", "reject_path_prefixes": ["tag"], "reject_path_patterns": [], "allow_path_patterns": []},
     {"version": "v1", "reject_path_prefixes": [], "reject_path_patterns": ["("], "allow_path_patterns": []},
     {"version": "v1", "reject_path_prefixes": [], "reject_path_patterns": [], "allow_path_patterns": [], "extra": 1}],
)
def test_malformed_outlet_rules_are_refused(rules, tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"schema": "coprepan-candidate-rules/v1", "outlets": {OUTLET: rules}}), encoding="utf-8")
    with pytest.raises(CF.CandidateRulesError):
        CF.load_rules(path)
    with pytest.raises(CF.CandidateRulesError):
        CF.load_rules(tmp_path / "absent.json")


def test_a_rule_version_change_adds_a_decision_and_keeps_the_old_one(tmp_path):
    table = CF.QualificationTable(tmp_path / "qualifications.jsonl")
    candidate = cand("/tag/economia")
    common = dict(channel_url_keys=frozenset(), run_id="acq1-20261007T120000000000Z-000000000000", decided_at=format_instant(T0))
    first = table.decide(candidate, outlet_rules=None, **common)
    assert first["decision"] == "QUALIFIED" and table.decide(candidate, outlet_rules=None, **common) is first  # recorded once
    v1 = {"version": "rules/1", "reject_path_prefixes": ["/tag"], "reject_path_patterns": [], "allow_path_patterns": []}
    second = table.decide(candidate, outlet_rules=v1, **common)
    assert second["decision"] == "REJECTED"
    history = CF.QualificationTable(tmp_path / "qualifications.jsonl").history(candidate["candidate_id"])
    assert [(h["ruleset"].split("+")[1], h["decision"]) for h in history] == [("no-outlet-rules", "QUALIFIED"), ("rules/1", "REJECTED")]
    assert len((tmp_path / "qualifications.jsonl").read_text(encoding="utf-8").splitlines()) == 2


# --- channel health ---------------------------------------------------------------------------------

RULES = OutletUrlRules(OUTLET, (WWW,), f"{OUTLET}-url-rules/v1")
CHANNEL = f"{OUTLET}:ch:rss_001"
HEALTH = CH.HealthPolicy(failing_after_consecutive_failures=3, stale_after_runs_without_new_candidates=2)


def feed(*paths):
    items = "".join(f"<item><link>{WWW}{p}</link></item>" for p in paths)
    return f"<rss><channel>{items}</channel></rss>".encode()


def observe(tables, number, document, final_url=None):
    run_id = f"acq1-202610{number:02d}T120000000000Z-000000000000"

    def provider(url, depth):
        if document is None:
            return D.DocumentUnavailable(url, "http_503")
        body = document[url] if isinstance(document, dict) else document
        if body is None:
            return D.DocumentUnavailable(url, "http_404")
        return D.ChannelDocument(url, final_url or url, f"ft1:{number:02d}{abs(hash(url)) % 10**6:062d}", body)

    D.discover_channel(tables, RULES, channel_id=CHANNEL, start_url=f"{WWW}/rss", provider=provider,
                       budget=D.DiscoveryBudget(2, 10, 100, 10**6), run_id=run_id, discovered_at=T0 + timedelta(days=number))


def health_after(tmp_path, *documents, disabled=()):
    tables = D.DiscoveryTables(tmp_path / "discovery")
    for number, document in enumerate(documents, 1):
        observe(tables, number, document)
    return CH.health(tables, CHANNEL, HEALTH, disabled_channels=disabled)


def test_health_states_follow_from_the_observations(tmp_path):
    assert health_after(tmp_path / "a")["state"] == "UNKNOWN"
    assert health_after(tmp_path / "b", feed("/n1"))["state"] == "HEALTHY"
    assert health_after(tmp_path / "c", feed("/n1"), None)["state"] == "DEGRADED"
    assert health_after(tmp_path / "d", feed("/n1"), None, None, None)["state"] == "FAILING"
    assert health_after(tmp_path / "e", None, None, None, feed("/n1"))["state"] == "HEALTHY"  # one good run ends the streak
    assert health_after(tmp_path / "f", feed("/n1"), b"<rss><channel><item>")["state"] == "DEGRADED"  # parse failure


def test_stale_is_information_not_a_fault(tmp_path):
    stale = health_after(tmp_path, feed("/n1"), feed("/n1"), feed("/n1"))
    assert stale["state"] == "STALE" and "not a fault" in stale["reason"]
    assert stale["evidence"]["consecutive_readable_runs_without_new_candidates"] == 2
    assert stale["evidence"]["consecutive_unreadable_runs"] == 0 and stale["evidence"]["last_run"]["candidates_listed"] == 1
    fresh = health_after(tmp_path / "x", feed("/n1"), feed("/n1"), feed("/n1", "/n2"))
    assert fresh["state"] == "HEALTHY" and fresh["evidence"]["last_run"]["candidates_new"] == 1


def test_partial_success_is_degraded(tmp_path):
    index = (b'<sitemapindex><sitemap><loc>https://www.diario-ejemplo.test/s1.xml</loc></sitemap>'
             b"<sitemap><loc>https://www.diario-ejemplo.test/s2.xml</loc></sitemap></sitemapindex>")
    documents = {f"{WWW}/rss": index, f"{WWW}/s1.xml": b"<urlset><url><loc>https://www.diario-ejemplo.test/a</loc></url></urlset>",
                 f"{WWW}/s2.xml": None}
    result = health_after(tmp_path, documents)
    assert result["state"] == "DEGRADED" and "1 of 3 documents" in result["reason"]
    assert result["evidence"]["last_run"]["candidates_new"] == 1


def test_a_disabled_channel_is_reported_and_health_changes_nothing(tmp_path):
    result = health_after(tmp_path, feed("/n1"), disabled=[CHANNEL])
    assert result["state"] == "DISABLED" and result["evidence"]["runs_observed"] == 1
    assert result["effect"].startswith("none")
    before = {p.name: p.read_bytes() for p in (tmp_path / "discovery").iterdir()}
    CH.report(D.DiscoveryTables(tmp_path / "discovery"), [CHANNEL], HEALTH)
    assert {p.name: p.read_bytes() for p in (tmp_path / "discovery").iterdir()} == before  # a report writes nothing


def test_a_changed_redirect_target_is_noted(tmp_path):
    tables = D.DiscoveryTables(tmp_path / "discovery")
    observe(tables, 1, feed("/n1"))
    observe(tables, 2, feed("/n1", "/n2"), final_url=f"{WWW}/feeds/portada.xml")
    result = CH.health(tables, CHANNEL, HEALTH)
    assert result["state"] == "HEALTHY" and "another URL than before" in result["notes"][0]


def test_health_thresholds_have_no_default():
    with pytest.raises(TypeError):
        CH.HealthPolicy()
    with pytest.raises(ValueError):
        CH.HealthPolicy(0, 1)
