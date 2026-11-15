"""intake-controller/3 (CPD-0037): the items of a cycle interleaved across outlets.

Two loopback outlets, each on its own origin, a 10-second minimum interval per origin (the production policy's). Offline.
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest

from coprepan import acquisition, canary_driver as D, core_pipeline as C, incremental_check, intake as I, outage_spool, policy as P, recovery
from coprepan.crawler_identity import loopback_test_identity
from support_http import FakeClock, LocalSite, Response
from test_canary_findings import OTHER_OUTLET, OTHER_WWW, OUTLET, WWW, two_outlets
from test_offline_e2e import SCHEDULE

T0 = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
HTML = [("Content-Type", "text/html; charset=utf-8")]
PAGE = "<html><body><article><h1>Nota {n}</h1><p>Texto de la nota {n}, con lo necesario para ser leída.</p></article></body></html>"
BUDGET = I.IntakeBudget(duration_seconds=3 * 3600, cycle_seconds=3600, item_requests_per_outlet=120, item_requests_per_outlet_hour=10,
                        item_requests_per_origin=150, total_requests=12000, items_per_outlet_cycle=6, backlog_items_per_outlet_cycle=0)


def paced_policy():
    policy = copy.deepcopy(P.loopback_test_policy())
    policy["rate_limit"]["min_interval_seconds_per_origin"] = 10
    return policy


def feed(origin, paths, at):
    items = "".join(f"<item><link>{origin}{p}</link><pubDate>{format_datetime(at)}</pubDate></item>" for p in paths)
    return Response(200, [("Content-Type", "application/rss+xml")], f'<rss version="2.0"><channel>{items}</channel></rss>'.encode())


def serve(site, origin, prefix, polls):
    site.routes.update({"/robots.txt": Response(200, [("Content-Type", "text/plain")], b"User-agent: *\nDisallow:\n"),
                        "/rss.xml": [feed(origin, paths, at) for paths, at in polls]})
    site.routes.update({f"/{prefix}{n}": Response(200, HTML, PAGE.format(n=n).encode()) for n in range(40)})


def readiness():
    def entry(outlet, country, origin):
        return {"outlet_id": outlet, "country_id": country, "tier": "A", "web_origins": [origin], "candidate_rule": None,
                "limits": {"robots_crawl_delay_seconds_observed": None},
                "channels": [{"channel_id": f"{outlet}:ch:rss_001", "kind": "rss", "url": f"{origin}/rss.xml", "formats": ["rss"], "entries_last": 6}]}
    return {"readiness_version": "test.1", "held_origins": {}, "held_urls": {}, "outlets": [entry(OTHER_OUTLET, "es", OTHER_WWW), entry(OUTLET, "uy", WWW)]}


def plan_of(controller=I.CONTROLLER_VERSION, budget=BUDGET, allowances=None):
    return I.build_plan(readiness(), intake_id="in3-test", budget=budget, policy=paced_policy(), registry_sha256="r" * 64,
                        readiness_sha256="s" * 64, allowances=allowances, controller=controller)


class Bench:
    def __init__(self, base, first, second, plan):
        self.workspace = C.Workspace(base / "workspace")
        self.root, self.spool, self.state_dir = base / "preservation", base / "spool", base / "workspace" / "intake" / "in3-test"
        for directory in (self.workspace.root, self.root, self.spool):
            directory.mkdir(parents=True, exist_ok=True)
        self.clock, self.plan = FakeClock(T0), plan
        self.environment = I.Environment(
            workspace=self.workspace, registry=two_outlets(), policy=paced_policy(), identity=loopback_test_identity(), schedule_policy=SCHEDULE,
            candidate_rules={}, preservation_root=lambda: self.root, spool_root=lambda: self.spool,
            spool_policy=outage_spool.SpoolPolicy(min_free_bytes=1, max_spool_bytes=1 << 30), clock=self.clock, sleep=self.clock.sleep,
            fetcher_options={"connect_override": {WWW: ("127.0.0.1", first.port), OTHER_WWW: ("127.0.0.1", second.port)}})

    def run(self):
        I.write_state(self.state_dir, I.initial_state(self.plan, started_at=self.clock(), baseline={"manifest_sha256": "b" * 64}))
        return I.run(self.plan, self.state_dir, self.environment)

    def items(self):
        rows = [r for r in D.fetch_records(self.workspace) if r["fetch_kind"] == acquisition.FETCH_KIND_ITEM]
        return sorted(rows, key=lambda r: r["fetch_started_at"])


@pytest.fixture
def sites():
    with LocalSite() as first, LocalSite() as second:
        yield first, second


def fresh(n, prefix, hours=0):
    return ([f"/{prefix}{k}" for k in range(n)], T0 + timedelta(minutes=5, hours=hours))


@pytest.fixture
def pacing(monkeypatch):
    """What the fetcher's pacing did: every wait, and the instant each request was released to its origin."""
    from coprepan import fetcher as F
    seen = {"waits": [], "sent": []}
    original = F.HttpFetcher._pace

    def spy(self, origin):
        real_sleep = self.sleep

        def record(seconds):
            seen["waits"].append(seconds)
            real_sleep(seconds)
        self.sleep = record
        try:
            original(self, origin)
        finally:
            self.sleep = real_sleep
        seen["sent"].append((origin, self._last_request[origin]))
    monkeypatch.setattr(F.HttpFetcher, "_pace", spy)
    return seen


def test_items_of_a_cycle_go_round_the_outlets_and_each_origin_keeps_its_interval(tmp_path, sites, pacing):
    first, second = sites
    serve(first, WWW, "a", [fresh(6, "a")] * 3)
    serve(second, OTHER_WWW, "b", [fresh(6, "b")] * 3)
    bench = Bench(tmp_path, first, second, plan_of())
    state = bench.run()
    assert state["status"] == I.FINALIZING
    outlets = [r["outlet_id"] for r in bench.items()]
    assert outlets.count(OUTLET) == 6 and outlets.count(OTHER_OUTLET) == 6
    assert all(a != b for a, b in zip(outlets, outlets[1:])), outlets            # never twice in a row while both have items
    by_origin: dict[str, list[datetime]] = {}
    for origin, at in pacing["sent"]:
        by_origin.setdefault(origin, []).append(at)
    assert len(by_origin) >= 2
    for times in by_origin.values():                                            # the policy's interval, per origin, as released
        assert all((b - a).total_seconds() >= 10 for a, b in zip(times, times[1:])), times


class StillClock(FakeClock):
    """Time passes only while waiting: transport and processing take no time (the measured case: well under a second, against
    a 10-second interval per origin)."""

    def __call__(self):
        return self.now


def test_interleaving_waits_less_for_the_same_work(tmp_path, sites, pacing):
    first, second = sites
    results = {}
    for controller in (I.CONTROLLER_2, I.CONTROLLER_VERSION):
        for site, origin, prefix in ((first, WWW, "a"), (second, OTHER_WWW, "b")):
            site.routes.clear()
            serve(site, origin, prefix, [fresh(6, prefix)] * 3)
        pacing["waits"].clear()
        bench = Bench(tmp_path / controller.replace("/", "-"), first, second,
                      plan_of(controller=controller, budget=I.IntakeBudget(**{**BUDGET.as_record(), "duration_seconds": 3600 + 120})))
        bench.clock = StillClock(T0)
        bench.environment.clock, bench.environment.sleep = bench.clock, bench.clock.sleep
        bench.run()
        results[controller] = (len(bench.items()), round(sum(w for w in pacing["waits"]), 1))
    (n2, waited2), (n3, waited3) = results[I.CONTROLLER_2], results[I.CONTROLLER_VERSION]
    print("pacing waits (items, seconds):", results)
    assert n2 == n3 == 12
    # /2: each outlet's six items one after another, five 10-second waits each; /3: the two origins' waits overlap
    assert waited2 >= 100 and waited3 <= 0.6 * waited2, results


def test_each_outlet_has_its_own_allowance(tmp_path, sites):
    first, second = sites
    serve(first, WWW, "a", [fresh(6, "a")] * 3)
    serve(second, OTHER_WWW, "b", [fresh(6, "b")] * 3)
    allowances = {OUTLET: {"items_per_cycle": 2, "item_requests_per_hour": 2, "item_requests": 4}}
    bench = Bench(tmp_path, first, second, plan_of(allowances=allowances, budget=I.IntakeBudget(**{**BUDGET.as_record(), "duration_seconds": 3600 + 120})))
    bench.run()
    outlets = [r["outlet_id"] for r in bench.items()]
    assert outlets.count(OUTLET) == 2 and outlets.count(OTHER_OUTLET) == 6


def test_a_plan_cannot_give_an_outlet_more_than_the_budget_and_a_2_plan_has_no_allowance():
    registry, policy = two_outlets(), paced_policy()
    over = plan_of(allowances={OUTLET: {"items_per_cycle": 7, "item_requests_per_hour": 10, "item_requests": 10}})
    with pytest.raises(I.IntakeStopped, match="up to the budget"):
        I.validate_plan(over, registry, policy, {})
    old = plan_of(controller=I.CONTROLLER_2)
    assert "allowance" not in old["outlets"][0] and I.validate_plan(old, registry, policy, {}) == BUDGET
    with pytest.raises(I.IntakeStopped, match="no allowance"):
        I.validate_plan({**old, "outlets": [{**o, "allowance": I.default_allowance(BUDGET)} for o in old["outlets"]]}, registry, policy, {})
    drained = I.IntakeBudget(**{**BUDGET.as_record(), "drain_seconds": 600})
    with pytest.raises(I.IntakeStopped, match="no drain"):
        I.validate_plan(plan_of(controller=I.CONTROLLER_2, budget=drained), registry, policy, {})
    assert "drain_seconds" not in BUDGET.as_record() and drained.as_record()["drain_seconds"] == 600


def test_a_2_plan_runs_outlet_after_outlet_and_checks_the_whole_workspace(tmp_path, sites, monkeypatch):
    first, second = sites
    serve(first, WWW, "a", [fresh(3, "a")] * 3)
    serve(second, OTHER_WWW, "b", [fresh(3, "b")] * 3)
    used = {"full": 0, "incremental": 0}
    real_full, real_inc = recovery.diagnose, incremental_check.checkpoint
    monkeypatch.setattr(recovery, "diagnose", lambda *a, **k: (used.__setitem__("full", used["full"] + 1), real_full(*a, **k))[1])
    monkeypatch.setattr(incremental_check, "checkpoint", lambda *a, **k: (used.__setitem__("incremental", used["incremental"] + 1), real_inc(*a, **k))[1])
    bench = Bench(tmp_path, first, second, plan_of(controller=I.CONTROLLER_2))
    state = bench.run()
    outlets = [r["outlet_id"] for r in bench.items()]
    first_cycle = outlets[:6]
    assert first_cycle in ([OTHER_OUTLET] * 3 + [OUTLET] * 3, [OUTLET] * 3 + [OTHER_OUTLET] * 3)        # one outlet's items, then the other's
    assert used["incremental"] == 0 and used["full"] >= state["cycle"] and state["controller"] == I.CONTROLLER_2


def test_the_check_after_a_cycle_is_incremental_after_the_first(tmp_path, sites, monkeypatch):
    first, second = sites
    serve(first, WWW, "a", [fresh(2, "a"), fresh(2, "a", 1), fresh(2, "a", 2)])
    serve(second, OTHER_WWW, "b", [fresh(2, "b"), fresh(2, "b", 1), fresh(2, "b", 2)])
    modes = []
    real = incremental_check.checkpoint

    def spy(*a, **k):
        diagnosis, state = real(*a, **k)
        modes.append(diagnosis["check"]["mode"])
        return diagnosis, state
    monkeypatch.setattr(incremental_check, "checkpoint", spy)
    bench = Bench(tmp_path, first, second, plan_of())
    state = bench.run()
    assert modes[0] == "full" and set(modes[1:]) == {"incremental"} and len(modes) == state["cycle"] >= 2
    assert recovery.diagnose(bench.workspace.root)["classification"] in (recovery.CLEAN, recovery.RESUMABLE)


def test_in_the_drain_period_nothing_is_polled_and_what_was_listed_is_still_requested(tmp_path, sites):
    first, second = sites
    serve(first, WWW, "a", [fresh(2, "a")] * 3)
    serve(second, OTHER_WWW, "b", [fresh(2, "b")] * 3)
    drained = I.IntakeBudget(**{**BUDGET.as_record(), "duration_seconds": 3 * 3600, "drain_seconds": 3600, "items_per_outlet_cycle": 1})
    bench = Bench(tmp_path, first, second, plan_of(budget=drained))
    state = bench.run()
    polls = [path for path, _ in first.requests if path == "/rss.xml"]
    assert len(polls) == 2 and state["cycle"] == 3                        # three cycles, the last one polls nothing
    assert [r["outlet_id"] for r in bench.items()].count(OUTLET) == 2      # one a cycle: the second in cycle 2, none left


def test_items_left_when_the_cycle_ends_stay_due_and_are_counted(tmp_path, sites):
    first, second = sites
    serve(first, WWW, "a", [fresh(30, "a")] * 3)
    serve(second, OTHER_WWW, "b", [fresh(30, "b")] * 3)
    short = I.IntakeBudget(**{**BUDGET.as_record(), "cycle_seconds": 120, "duration_seconds": 3 * 120, "items_per_outlet_cycle": 10,
                              "item_requests_per_outlet_hour": 40})
    bench = Bench(tmp_path, first, second, plan_of(budget=short))
    state = bench.run()
    assert state["items_left_at_cycle_end"], state.get("items_left_at_cycle_end")
    asked = [r["request"]["requested_url"] for r in bench.items()]
    assert len(asked) == len(set(asked))                                   # what was left is asked later, never twice
