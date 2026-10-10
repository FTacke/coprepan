"""The intake controller, qualified entirely offline (CPD-0029).

A scripted server on a loopback address plays an outlet whose feed changes from poll to poll, and a
clock that does not wait plays the hours. What is tested is the controller: its schedule, its budgets,
its deadline, what it asks for first, what a restart keeps, and what its finalizer verifies — never an
outlet, and never the network.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest

from coprepan import acquisition, canary_driver as D, core_pipeline as C, intake as I, outage_spool, policy as P, storage_roots as S
from coprepan.crawler_identity import loopback_test_identity
from coprepan.exclusive import WorkspaceBusy
from support_http import FakeClock, LocalSite, Response
from test_fetcher import FEEDS, HTML, MOBILE, OUTLET, WWW, make_registry
from test_offline_e2e import SCHEDULE

T0 = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
RSS, RSS2 = f"{OUTLET}:ch:rss_001", f"{OUTLET}:ch:rss_002"
PAGE = "<html><body><article><h1>Nota {n}</h1><p>Texto de la nota {n}, con lo necesario para ser leída.</p></article></body></html>"
BUDGET = I.IntakeBudget(duration_seconds=4 * 3600, cycle_seconds=3600, item_requests_per_outlet=120, item_requests_per_outlet_hour=10,
                        item_requests_per_origin=150, total_requests=12000, items_per_outlet_cycle=3, backlog_items_per_outlet_cycle=1)


def feed(items) -> Response:
    """``items``: (path, publication instant or None)."""
    body = "".join(f"<item><link>{WWW}{path}</link>" + (f"<pubDate>{format_datetime(at)}</pubDate>" if at else "") + "</item>" for path, at in items)
    return Response(200, [("Content-Type", "application/rss+xml")],
                    ('<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>' + body + "</channel></rss>").encode("utf-8"))


def readiness(entries=6, **outlet):
    return {"readiness_version": "test.1", "held_origins": {}, "held_urls": {}, "outlets": [{
        "outlet_id": OUTLET, "country_id": "uy", "tier": "A", "web_origins": [WWW, MOBILE], "candidate_rule": None,
        "limits": {"robots_crawl_delay_seconds_observed": None},
        "channels": [{"channel_id": RSS, "kind": "rss", "url": f"{WWW}/rss.xml", "formats": ["rss"], "entries_last": entries}], **outlet}]}


def make_plan(budget=BUDGET, source=None, policy=None):
    return I.build_plan(source or readiness(), intake_id="in1-test", budget=budget, policy=policy or P.loopback_test_policy(),
                        registry_sha256="r" * 64, readiness_sha256="s" * 64)


class Bench:
    """One intake against the scripted outlet, in its own workspace and preservation root."""

    def __init__(self, base, site, *, budget=BUDGET, start=T0, plan=None):
        self.workspace = C.Workspace(base / "workspace")
        self.root, self.spool, self.state_dir = base / "preservation", base / "spool", base / "workspace" / "intake" / "in1-test"
        for directory in (self.workspace.root, self.root, self.spool):
            directory.mkdir(parents=True, exist_ok=True)
        self.site, self.registry, self.clock, self.policy = site, make_registry(), FakeClock(start), P.loopback_test_policy()
        self.plan = plan or make_plan(budget)
        self.target_up, self.permitted = True, None
        self.before_sleep = None
        self.environment = I.Environment(
            workspace=self.workspace, registry=self.registry, policy=self.policy, identity=loopback_test_identity(), schedule_policy=SCHEDULE,
            candidate_rules={}, preservation_root=self.preservation_root, spool_root=lambda: self.spool,
            spool_policy=outage_spool.SpoolPolicy(min_free_bytes=1, max_spool_bytes=1 << 30), clock=self.clock, sleep=self.sleep,
            fetcher_options={"connect_override": {origin: ("127.0.0.1", site.port) for origin in (WWW, FEEDS, MOBILE)}},
            still_permitted=lambda: self.permitted)

    def preservation_root(self):
        if not self.target_up:
            raise S.StorageRootUnreachable("PRESERVATION: not reachable")
        return self.root

    def sleep(self, seconds):
        if self.before_sleep is not None:
            self.before_sleep(self)
        self.clock.sleep(seconds)

    def start(self):
        I.write_state(self.state_dir, I.initial_state(self.plan, started_at=self.clock(), baseline={"manifest_sha256": "b" * 64}))
        return self

    def run(self):
        return I.run(self.plan, self.state_dir, self.environment)

    def finalize(self):
        return I.finalize(self.plan, self.state_dir, self.environment)

    def items(self):
        return [path for path in self.site.paths() if path.startswith("/n")]

    def records(self):
        return D.fetch_records(self.workspace)


def serve(site, polls, pages=40):
    """The outlet: a robots file, a feed that is another document at each poll, and its pages."""
    site.routes.update({"/robots.txt": Response(200, [("Content-Type", "text/plain")], b"User-agent: *\nDisallow: /privado/\n"),
                        "/rss.xml": [feed(items) for items in polls]})
    site.routes.update({f"/n{n}": Response(200, HTML, PAGE.format(n=n).encode("utf-8")) for n in range(1, pages + 1)})


@pytest.fixture
def site():
    with LocalSite() as server:
        yield server


OLD = T0 - timedelta(days=3)
STOCK = [("/n1", OLD), ("/n2", OLD + timedelta(hours=1)), ("/n3", None), ("/n4", None)]


# --- the plan ------------------------------------------------------------------------------------------


def test_a_plan_takes_what_the_readiness_file_lists_and_leaves_out_what_is_held_disabled_or_an_archive():
    source = readiness()
    source["outlets"][0]["channels"] += [
        {"channel_id": RSS2, "kind": "rss", "url": f"{FEEDS}/diario-ejemplo", "formats": ["rss"], "entries_last": 20},
        {"channel_id": f"{OUTLET}:ch:sitemap_index_001", "kind": "sitemap_index", "url": f"{WWW}/sitemap_index.xml", "formats": ["sitemap_index"], "entries_last": 90000}]
    plan = make_plan(source=source)
    outlet, = plan["outlets"]
    assert [c["channel_id"] for c in outlet["channels"]] == [RSS, RSS2] and outlet["bulk_channels_not_polled"] == [f"{OUTLET}:ch:sitemap_index_001"]
    assert {c["poll_seconds"] for c in outlet["channels"]} == {3600} and plan["totals"] == {"outlets": 1, "channels": 2, "countries": ["uy"], "tier_a": 1, "tier_b": 0}
    assert make_plan(source=source) == plan                                                    # deterministic
    held = make_plan(source={**source, "held_urls": {f"{FEEDS}/diario-ejemplo": "bot_challenge"}})
    assert [c["channel_id"] for c in held["outlets"][0]["channels"]] == [RSS]
    gone = make_plan(source={**source, "held_origins": {WWW: "captcha"}})
    assert gone["outlets"] == [] and gone["left_out"] == {OUTLET: "an origin of the outlet is held"}
    disabled = make_plan(source=source, policy=P.loopback_test_policy(disabled_channels=[RSS]))
    assert [c["channel_id"] for c in disabled["outlets"][0]["channels"]] == [RSS2]


def test_how_often_a_channel_is_polled_follows_from_what_it_is():
    kinds = {("rss", ("rss",), 100): "feed", ("sitemap", ("sitemap_urlset",), 100): "sitemap", ("sitemap", ("sitemap_urlset",), 2000): "large_sitemap",
             ("sitemap_index", ("sitemap_index", "sitemap_urlset"), 2000): "sitemap_index", ("section_page", ("html_listing",), 300): "listing",
             ("rss", ("html_listing",), 30): "listing", ("sitemap", ("sitemap_urlset",), 11000): "bulk"}
    for (kind, formats, entries), expected in kinds.items():
        assert I.channel_class({"kind": kind, "formats": list(formats), "entries_last": entries}) == expected
    assert I.POLL_SECONDS == {"feed": 3600, "sitemap": 3600, "large_sitemap": 21600, "sitemap_index": 21600, "listing": 7200, "bulk": 43200}


def test_an_only_channel_that_is_an_archive_stays_and_is_polled_twice_a_day():
    plan = make_plan(source=readiness(entries=139368))
    channel, = plan["outlets"][0]["channels"]
    assert channel["poll_class"] == "bulk" and channel["poll_seconds"] == 12 * 3600 and plan["outlets"][0]["bulk_channels_not_polled"] == []


def test_a_plan_is_run_only_against_the_registry_the_policy_and_the_holds_it_was_made_for():
    plan, registry, policy = make_plan(), make_registry(), P.loopback_test_policy()
    assert I.validate_plan(plan, registry, policy, {}) == BUDGET
    for change, holds, said in (({"policy_version": "other/1"}, {}, "policy"), ({}, {WWW: "captcha"}, "held"), ({}, {f"{WWW}/rss.xml": "bot_challenge"}, "held"),
                                ({"controller": "intake-controller/0"}, {}, "not a"), ({"outlets": []}, {}, "at least one")):
        with pytest.raises(I.IntakeStopped, match=said):
            I.validate_plan({**plan, **change}, registry, policy, holds)
    moved = json.loads(json.dumps(plan))
    moved["outlets"][0]["channels"][0]["url"] = f"{WWW}/otro.xml"
    with pytest.raises(I.IntakeStopped, match="not a channel of the registry"):
        I.validate_plan(moved, registry, policy, {})
    with pytest.raises(Exception, match="proposed"):
        I.validate_plan(plan, make_registry("proposed"), policy, {})


def test_a_budget_is_whole_numbers_and_a_cycle_never_asks_for_more_than_the_hour_allows():
    record = BUDGET.as_record()
    for change in ({"items_per_outlet_cycle": 11}, {"backlog_items_per_outlet_cycle": 4}, {"cycle_seconds": 30}, {"duration_seconds": 600}, {"total_requests": -1},
                   {"item_requests_per_outlet": 1.5}, {"item_requests_per_outlet": True}):
        with pytest.raises(ValueError):
            I.IntakeBudget(**{**record, **change})


# --- the schedule, the order and the budgets ------------------------------------------------------------------


def test_an_intake_polls_by_the_hour_asks_for_what_is_new_first_and_ends_at_its_deadline(tmp_path, site):
    new = [(f"/n{n}", T0 + timedelta(hours=1, minutes=n)) for n in (10, 11)]
    serve(site, [STOCK, STOCK + new, STOCK + new, STOCK + new + [("/n20", None)]])
    bench = Bench(tmp_path, site).start()
    state = bench.run()
    assert state["status"] == I.FINALIZING and state["cycle"] == 4
    assert bench.site.paths().count("/rss.xml") == 4 and bench.site.paths().count("/robots.txt") == 1      # hourly; robots once per process
    asked = bench.items()
    assert asked[0] == "/n2"                                                                                 # cycle 1: only stock, and one page of it (the most recently dated)
    assert asked[1:4] == ["/n11", "/n10", "/n1"]                                                             # cycle 2: what is new and dated in the window, newest first; then one of the stock
    assert asked[5] == "/n20" and {asked[4], asked[6]} == {"/n3", "/n4"}                                     # cycle 4: what a later poll listed first, before the stock
    assert len(asked) == 7 and len(set(asked)) == 7                                                          # no page is asked for twice
    deadline = datetime.fromisoformat(state["deadline_at_utc"].replace("Z", "+00:00"))
    assert deadline == datetime.fromisoformat(state["started_at_utc"].replace("Z", "+00:00")) + timedelta(hours=4)
    assert all(datetime.fromisoformat(r["fetch_started_at"].replace("Z", "+00:00")) < deadline for r in bench.records())
    assert set(bench.workspace.ledger().states().values()) == {"RAW_PRESERVED"}                              # every answer preserved as it went
    receipt = bench.finalize()
    assert receipt["outcome"] == I.COMPLETED and receipt["verification"]["status"] == "PASS", receipt["verification"]
    assert receipt["requests"]["total"] == len(bench.site.requests) and I.read_state(bench.state_dir)["status"] == I.COMPLETED


def test_what_a_channel_lists_at_its_first_poll_is_stock_and_only_a_later_listing_or_a_date_in_the_window_is_new(tmp_path, site):
    started, done = T0, {RSS: "2026-10-10T12:05:00.000000Z"}

    def kind(listed, published=None, channel=RSS):
        hints = {"published": format_datetime(published)} if published else {}
        return I.novelty({"first_listed_at": listed, "first_channel_id": channel}, {"hints": hints}, started, done)

    assert kind("2026-10-09T08:00:00.000000Z") == I.KNOWN_BEFORE
    assert kind("2026-10-10T12:04:00.000000Z") == I.FIRST_POLL_UNDATED and kind("2026-10-10T13:04:00.000000Z") == I.NEW_UNDATED
    assert kind("2026-10-10T12:04:00.000000Z", T0 + timedelta(minutes=1)) == I.NEW_IN_WINDOW                  # dated in the window: new even at the first poll
    assert kind("2026-10-10T13:04:00.000000Z", T0 - timedelta(days=2)) == I.OLDER                             # found late, published long ago: not new
    assert kind("2026-10-10T12:04:00.000000Z", channel=RSS2) == I.FIRST_POLL_UNDATED                          # a channel not polled yet


def test_old_stock_never_takes_more_than_its_small_share(tmp_path, site):
    stock = [(f"/n{n}", OLD + timedelta(minutes=n)) for n in range(1, 31)]
    serve(site, [stock])
    bench = Bench(tmp_path, site).start()
    bench.run()
    assert len(bench.items()) == 4 and bench.items() == ["/n30", "/n29", "/n28", "/n27"]                     # one per cycle, the most recent first


def test_the_hourly_and_the_daily_limit_of_an_outlet_hold_and_the_refusals_are_on_record(tmp_path, site):
    fresh = [(f"/n{n}", T0 + timedelta(minutes=n)) for n in range(1, 31)]
    serve(site, [fresh])
    budget = I.IntakeBudget(**{**BUDGET.as_record(), "item_requests_per_outlet": 7, "item_requests_per_outlet_hour": 3, "items_per_outlet_cycle": 3})
    bench = Bench(tmp_path, site, budget=budget).start()
    bench.run()
    assert len(bench.items()) == 7                                                                            # 3 + 3 + 1, and not one more
    rows = [json.loads(line) for line in (bench.workspace.root / "requests" / "requests.jsonl").read_bytes().splitlines()]
    refused = [row for row in rows if row.get("event") == "FINISHED" and row["policy_reasons"] == ["intake_budget_exhausted"]]
    assert refused and all(row["final"] == "DENIED" and row["fetch_ids"] == [] for row in refused)
    assert bench.finalize()["verification"]["status"] == "PASS"


def test_the_hourly_limit_counts_the_last_hour_not_the_cycle(tmp_path, site):
    clock = FakeClock(T0)
    fetcher = I.IntakeFetcher(budget=I.IntakeBudget(**{**BUDGET.as_record(), "item_requests_per_outlet_hour": 3}), deadline=T0 + timedelta(hours=4),
                              used={"item_times": {OUTLET: [T0 - timedelta(minutes=50), T0 - timedelta(minutes=40), T0 - timedelta(minutes=30)]}},
                              identity=loopback_test_identity(), gate=P.PolicyGate(P.loopback_test_policy(), make_registry(), loopback_test_identity()),
                              limits=D.CANARY_LIMITS, clock=clock, sleep=clock.sleep)
    assert fetcher.refusal(OUTLET, acquisition.FETCH_KIND_ITEM, f"{WWW}/n1") == "intake_budget_exhausted: outlet_hour"
    assert fetcher.refusal(OUTLET, acquisition.FETCH_KIND_CHANNEL_DOCUMENT, f"{WWW}/rss.xml") is None          # the limit is on item pages
    clock.sleep(11 * 60)
    assert fetcher.refusal(OUTLET, acquisition.FETCH_KIND_ITEM, f"{WWW}/n1") is None                            # the oldest is more than an hour ago


def test_the_total_and_the_origin_limit_stop_every_further_request(tmp_path, site):
    fresh = [(f"/n{n}", T0 + timedelta(minutes=n)) for n in range(1, 31)]
    serve(site, [fresh])
    bench = Bench(tmp_path, site, budget=I.IntakeBudget(**{**BUDGET.as_record(), "total_requests": 5})).start()
    bench.run()
    assert len(bench.site.requests) == 5                                                                      # robots, feed, three pages — and nothing after
    other = Bench(tmp_path / "origin", site, budget=I.IntakeBudget(**{**BUDGET.as_record(), "item_requests_per_origin": 2})).start()
    before = len(site.requests)
    other.run()
    assert len([path for path in site.paths()[before:] if path.startswith("/n")]) == 2


def test_a_redirect_hop_is_a_request_of_the_budget(tmp_path, site):
    serve(site, [[("/n1", T0 + timedelta(minutes=1))]])
    site.routes["/n1"] = Response(302, [("Location", "/n2")])
    bench = Bench(tmp_path, site).start()
    bench.run()
    assert I.used_from_evidence(bench.workspace, I.read_state(bench.state_dir)["run_ids"], bench.clock())["items_by_outlet"] == {OUTLET: 2}


def test_a_transport_call_that_must_not_be_made_is_an_integrity_failure(tmp_path, site):
    clock = FakeClock(T0)
    fetcher = I.IntakeFetcher(budget=BUDGET, deadline=T0 + timedelta(hours=1), identity=loopback_test_identity(),
                              gate=P.PolicyGate(P.loopback_test_policy(), make_registry(), loopback_test_identity()), limits=D.CANARY_LIMITS,
                              clock=clock, sleep=clock.sleep, connect_override={WWW: ("127.0.0.1", site.port)})
    with pytest.raises(I.IntakeStopped, match="outside any intake context"):
        fetcher._request(f"{WWW}/n1")
    clock.sleep(3600)
    fetcher._context = (OUTLET, acquisition.FETCH_KIND_ITEM)
    with pytest.raises(I.IntakeStopped, match="intake_deadline_reached"):
        fetcher._request(f"{WWW}/n1")
    assert site.requests == []


# --- the deadline -------------------------------------------------------------------------------------------


def test_nothing_is_decided_so_late_that_its_pacing_could_pass_the_deadline(tmp_path, site):
    serve(site, [STOCK])
    budget = I.IntakeBudget(**{**BUDGET.as_record(), "duration_seconds": 3600 + 400, "cycle_seconds": 3600})
    bench = Bench(tmp_path, site, budget=budget).start()
    state = bench.run()
    deadline = datetime.fromisoformat(state["deadline_at_utc"].replace("Z", "+00:00"))
    last = max(datetime.fromisoformat(r["fetch_started_at"].replace("Z", "+00:00")) for r in bench.records())
    assert last < deadline - timedelta(seconds=I.PACE_MARGIN_SECONDS) + timedelta(seconds=30) and state["status"] == I.FINALIZING
    assert bench.site.paths().count("/rss.xml") == 2                                                          # the second cycle began before the margin


def test_after_the_deadline_a_controller_asks_nothing_and_the_deadline_is_the_one_of_the_start(tmp_path, site):
    serve(site, [STOCK])
    bench = Bench(tmp_path, site).start()
    deadline = I.read_state(bench.state_dir)["deadline_at_utc"]
    bench.clock.sleep(5 * 3600)                                                                               # the machine slept through the whole window
    state = bench.run()
    assert state["status"] == I.FINALIZING and site.requests == [] and state["deadline_at_utc"] == deadline
    assert bench.finalize()["outcome"] == I.COMPLETED


def test_the_finalizer_refuses_a_running_intake_before_its_deadline(tmp_path, site):
    serve(site, [STOCK])
    bench = Bench(tmp_path, site).start()
    with pytest.raises(I.IntakeStopped, match="deadline has not come"):
        bench.finalize()


# --- restart ------------------------------------------------------------------------------------------------


class Killed(BaseException):
    """The process ends here."""


def test_a_restart_keeps_the_deadline_and_the_budgets_and_closes_what_was_cut_short(tmp_path, site):
    fresh = [(f"/n{n}", T0 + timedelta(minutes=n)) for n in range(1, 31)]
    serve(site, [fresh])
    budget = I.IntakeBudget(**{**BUDGET.as_record(), "item_requests_per_outlet": 5})
    bench = Bench(tmp_path, site, budget=budget).start()
    started = I.read_state(bench.state_dir)

    def kill(b):
        if len(b.items()) >= 3:
            raise Killed()
    bench.before_sleep = kill
    with pytest.raises(Killed):
        bench.run()
    assert len(bench.items()) == 3
    again = Bench(tmp_path, site, budget=budget, start=bench.clock.now)                                       # a new process: nothing in memory
    state = again.run()
    assert state["deadline_at_utc"] == started["deadline_at_utc"] and state["started_at_utc"] == started["started_at_utc"]
    assert len(again.items()) == 5 and len(set(again.items())) == 5                                           # the budget of the evidence, not a second one
    assert acquisition.unfinished_runs(again.workspace.root) == []
    receipt = again.finalize()
    assert receipt["verification"]["status"] == "PASS" and receipt["requests"]["item"] == 5


def test_a_process_that_dies_inside_a_cycle_leaves_a_run_that_the_next_start_closes_as_failed(tmp_path, site):
    serve(site, [STOCK])
    bench = Bench(tmp_path, site).start()
    original = D._preserve

    def dying(*args, **kwargs):
        raise Killed()
    D._preserve = dying
    try:
        with pytest.raises(Killed):
            bench.run()
    finally:
        D._preserve = original
    open_run, = acquisition.unfinished_runs(bench.workspace.root)
    assert any(path.stat().st_size for path in bench.workspace.packs.glob("*.warc.gz.open"))                  # received, not yet preserved
    again = Bench(tmp_path, site, start=bench.clock.now)
    state = again.run()
    assert acquisition.read_run_result(again.workspace.root, open_run)["status"] == "FAILED" and state["restarts"] == 1
    assert set(again.workspace.ledger().states().values()) == {"RAW_PRESERVED"}                              # what the dead process received is preserved
    assert again.finalize()["verification"]["status"] == "PASS"


def test_there_is_one_controller_at_a_time(tmp_path, site):
    serve(site, [STOCK])
    bench = Bench(tmp_path, site).start()
    import subprocess
    import sys
    holder = subprocess.Popen([sys.executable, "-c", "import sys, time; sys.path.insert(0, 'src'); from coprepan.exclusive import exclusive\n"
                               f"with exclusive(r'{bench.state_dir}', 'another controller'):\n    print('held', flush=True); time.sleep(30)"],
                              stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "held"
        with pytest.raises(WorkspaceBusy):
            bench.run()
        assert site.requests == []
    finally:
        holder.kill()
        holder.wait()


def test_a_changed_plan_is_not_run(tmp_path, site):
    serve(site, [STOCK])
    bench = Bench(tmp_path, site).start()
    bench.plan = make_plan(I.IntakeBudget(**{**BUDGET.as_record(), "total_requests": 99999}))
    with pytest.raises(I.IntakeStopped, match="not the plan this intake was started with"):
        bench.run()
    assert site.requests == []


# --- stops ---------------------------------------------------------------------------------------------------


def test_a_stop_request_ends_the_intake_and_the_finalizer_still_verifies_it(tmp_path, site):
    serve(site, [STOCK])
    bench = Bench(tmp_path, site).start()
    bench.before_sleep = lambda b: (b.state_dir / I.STOP_FILE).write_text("stop", encoding="utf-8") if b.items() else None
    state = bench.run()
    assert state["status"] == I.STOPPED and state["cycle"] == 1
    receipt = bench.finalize()
    assert receipt["outcome"] == I.STOPPED and receipt["verification"]["status"] == "PASS"
    assert bench.run()["status"] == I.STOPPED and len(bench.items()) == 1                                    # a stopped intake is not started again


def test_when_the_permission_is_gone_no_further_cycle_begins(tmp_path, site):
    serve(site, [STOCK])
    bench = Bench(tmp_path, site).start()
    bench.before_sleep = lambda b: setattr(b, "permitted", "external_acquisition is `disabled`")
    state = bench.run()
    assert state["status"] == I.BLOCKED and state["stopped_because"] == "external_acquisition is `disabled`" and state["cycle"] == 1
    assert bench.site.paths().count("/rss.xml") == 1


def test_while_the_preservation_target_is_away_nothing_more_is_asked(tmp_path, site):
    fresh = [(f"/n{n}", T0 + timedelta(minutes=n)) for n in range(1, 31)]
    serve(site, [fresh])
    bench = Bench(tmp_path, site)
    bench.target_up = False
    bench.start()
    seen = []

    def back(b):
        seen.append(len(b.site.requests))
        if b.clock.now > T0 + timedelta(hours=2):
            b.target_up = True
    bench.before_sleep = back
    state = bench.run()
    first_cycle = seen[0]
    assert first_cycle == 5 and seen.count(first_cycle) >= 2                                                  # one outlet call, then silence while the target is away
    assert len(bench.site.requests) > first_cycle and state["preservation"] == "nothing pending"             # it came back: the rest followed
    assert set(bench.workspace.ledger().states().values()) == {"RAW_PRESERVED"}
    assert bench.finalize()["verification"]["status"] == "PASS"


def test_an_outlet_that_becomes_held_is_passed_over_and_the_hold_is_in_the_state(tmp_path, site):
    serve(site, [[(f"/n{n}", T0 + timedelta(minutes=n)) for n in range(1, 10)]])
    site.routes["/n9"] = Response(403, HTML, b"<html><head><title>Just a moment...</title></head><body><div id='challenge-form'>cf-chl</div>"
                                             b"<script src='/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page/v1'></script></body></html>")
    bench = Bench(tmp_path, site).start()
    state = bench.run()
    assert bench.items() == ["/n9"] and state["holds"].get(WWW)                                               # the newest page answered with a challenge: nothing after it
    assert bench.site.paths().count("/rss.xml") == 1 and state["holds"][OUTLET] == "an origin of the outlet is held"
    again = Bench(tmp_path, site, start=T0 + timedelta(hours=1))                                              # and a restart reads the hold from the evidence
    before = len(site.requests)
    again.run()
    assert len(site.requests) == before


# --- the finalizer -------------------------------------------------------------------------------------------


def test_a_finalization_is_repeatable_and_says_what_it_verified(tmp_path, site):
    serve(site, [STOCK])
    bench = Bench(tmp_path, site).start()
    bench.run()
    first = bench.finalize()
    names = [check["check"] for check in first["verification"]["checks"]]
    assert names == ["nothing_left_open", "every_answer_is_raw_preserved", "preservation_readback_and_fixity", "raw_preserved_matches_verified_bytes",
                     "recovery_diagnosis", "budget_respected", "no_request_after_the_deadline"]
    second = bench.finalize()
    assert {k: v for k, v in second.items() if k != "finalized_at_utc"} == {k: v for k, v in first.items() if k != "finalized_at_utc"}
    assert len(site.requests) == first["requests"]["total"]                                                   # a finalizer asks nothing


def test_a_damaged_preserved_pack_fails_the_verification_and_the_outcome_says_partial(tmp_path, site):
    serve(site, [STOCK])
    bench = Bench(tmp_path, site).start()
    bench.run()
    master = next(path for path in bench.root.rglob("*.warc.gz"))
    master.chmod(0o666)
    data = bytearray(master.read_bytes())
    data[len(data) // 2] ^= 0xFF
    master.write_bytes(bytes(data))
    receipt = bench.finalize()
    assert receipt["verification"]["status"] == "FAIL" and receipt["outcome"] == "PARTIAL"


def test_the_state_file_says_what_an_operator_needs_at_any_time(tmp_path, site):
    serve(site, [STOCK])
    bench = Bench(tmp_path, site).start()
    line = I.status_line(I.read_state(bench.state_dir), bench.clock())
    assert line["status"] == I.RUNNING and line["remaining_seconds"] > 3 * 3600 and line["requests_total"] == 0
    bench.run()
    line = I.status_line(I.read_state(bench.state_dir), bench.clock())
    assert line["status"] == I.FINALIZING and line["remaining_seconds"] < 120 and line["requests_total"] == len(site.requests)
    assert line["item_requests"] == len(bench.items()) and line["preservation"] == "nothing pending" and line["cycle"] == 4
