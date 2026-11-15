"""What canary-driver/7 changed for a qualification wave, found by the first weekend wave (wq-1, 2026-11-14).

* Stage B reads every selected channel after the first: canary-driver/6 selected up to four (CPD-0036) and read the second only.
* A wave with deferred preservation requests the newest pages its own channels list (``item-selection/1``), not the planner's
  oldest-due-first order, which had sent wq-1 to pages first listed in October and earlier.

Offline: the loopback outlet of the driver's tests. Nothing here is a real outlet.
"""

from __future__ import annotations

from types import SimpleNamespace

from coprepan import canary_driver as D, registry as R, schedule
from test_canary_driver import Drive, OUTLET, site  # noqa: F401  (the loopback outlet fixture)
from test_offline_e2e import make_registry

THIRD = f"{OUTLET}:ch:sitemap_q001"


def with_a_third_channel():
    document = {"schema": "coprepan-outlet-registry/v1", "outlets": [dict(make_registry().resolve(OUTLET))]}
    outlet = document["outlets"][0]
    www = outlet["web_origins"][0]
    outlet["channels"] = list(outlet["channels"]) + [
        {"channel_id": THIRD, "kind": "sitemap", "url_history": [{"url": f"{www}/sitemaps/profundo.xml", "valid_from": "unknown"}],
         "legacy_observed": {}}]
    return R.validate_registry(document)


def test_stage_b_reads_every_selected_channel_after_the_first(tmp_path, site, monkeypatch):  # noqa: F811
    import test_canary_driver
    monkeypatch.setattr(test_canary_driver, "make_registry", with_a_third_channel)
    budget = D.CanaryBudget(outlets=1, channels_per_outlet=3, item_requests_total=8, item_requests_per_outlet=8, other_requests_per_outlet=12)
    run = Drive(tmp_path / "three", site, budget=budget)
    outcome = D.run_canary(run.workspace, run.registry, run.run, outlet_ids=[OUTLET], fetcher=run.fetcher, schedule_policy=run.schedule,
                           clock=run.clock, preservation_root=D.deferred_root, spool_root=None, spool_policy=None, disabled_channels=())
    result = outcome["outlets"][OUTLET]
    assert len(result["channels"]) == 3 and THIRD in result["channels"]
    asked = {r["request"]["requested_url"] for r in D.fetch_records(run.workspace) if r["fetch_kind"] == "channel_document"}
    assert any(url.endswith("/sitemaps/profundo.xml") for url in asked)            # canary-driver/6 never asked the third
    assert len(result["stages"]["B_discovery"]["channels"]) == 2


def test_two_channels_are_read_as_before(tmp_path, site):  # noqa: F811
    run = Drive(tmp_path / "two", site)
    outcome = run.go()
    assert outcome["outlets"][OUTLET]["stages"]["B_discovery"]["requests"] == {"channel_document:FETCHED": 1}


def _state(identifier, state=schedule.NEVER_FETCHED):
    return schedule.CandidateState(identifier, state, None, "r", 0)


def test_the_qualification_order_is_newest_listed_here_first_and_never_a_page_fetched_before():
    run_id = "this-run"
    events = {
        "e1": {"candidate_id": "old", "run_id": run_id, "hints": {"published": "2026-11-10T08:00:00Z"}},
        "e2": {"candidate_id": "new", "run_id": run_id, "hints": {"lastmod": "2026-11-14T18:00:00Z"}},
        "e3": {"candidate_id": "undated", "run_id": run_id, "hints": {}},
        "e4": {"candidate_id": "october", "run_id": "an-october-run", "hints": {"published": "2026-11-14T19:00:00Z"}},
        "e5": {"candidate_id": "fetched", "run_id": run_id, "hints": {"published": "2026-11-14T20:00:00Z"}},
        "e6": {"candidate_id": "old", "run_id": run_id, "hints": {"published": "2026-11-12T08:00:00Z"}},   # listed twice: its newest date
    }
    candidates = {"october": {"first_listed_at": "2026-10-09T00:00:00Z"}, "september": {"first_listed_at": "2026-09-01T00:00:00Z"}}
    tables = SimpleNamespace(events=events, candidates=candidates)
    due = [_state("october"), _state("september"), _state("old"), _state("undated"), _state("new"), _state("fetched", schedule.FETCHED)]
    order = [s.candidate_id for s in D.qualification_selector(run_id)(due, tables)]
    assert order == ["new", "old", "undated", "october", "september"]


def _evaluation():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "scripts" / "build_weekend_qualification.py"
    spec = importlib.util.spec_from_file_location("build_weekend_qualification_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_coverage_dimension_tells_a_quiet_weekend_from_a_channel_months_behind():
    from datetime import datetime, timezone
    q = _evaluation()
    started = datetime(2026, 11, 14, 21, 0, tzinfo=timezone.utc)

    def channel(listed, recent, newest):
        return {"entries_listed": listed, "entries_dated": listed if newest else 0, "entries_recent": recent, "newest_entry": newest}

    assert q.coverage_of([channel(91, 91, "2026-11-14T20:00:00+00:00")], started, True) == "CURRENT"
    assert q.coverage_of([channel(200, 0, "2026-11-10T08:00:00+00:00")], started, True) == "NO_RECENT_ENTRY_AT_THE_WEEKEND"
    assert q.coverage_of([channel(200, 0, "2026-11-10T08:00:00+00:00")], started, False) == "NO_RECENT_ENTRY"
    assert q.coverage_of([channel(296, 0, "2025-07-22T10:00:00+00:00")], started, True) == "STALE_CHANNEL"
    assert q.coverage_of([channel(228, 0, None)], started, True) == "UNDATED"
    assert q.coverage_of([channel(0, 0, None)], started, True) == "NO_ENTRIES"


def test_pages_of_one_and_the_same_length_are_a_shell_not_a_functional_acquisition():
    q = _evaluation()
    assert q.raw_of(6, [9004] * 6, [], True) == "UNIFORM_SHELL"
    assert q.raw_of(6, [9004, 120000, 80000, 9004, 70000, 65000], [], True) == "FUNCTIONAL"
    assert q.raw_of(2, [9004, 9004], [], True) == "PARTIAL"
    assert q.raw_of(0, [], ["403"], True) == "ACCESS_SIGNAL"
    assert q.raw_of(0, [], [], False) == "NOT_ATTEMPTED"


def test_the_driver_pins_the_item_selection():
    pin = D.driver_pin(D.CanaryBudget(outlets=1), make_registry(), [OUTLET], ())
    assert pin["item_selection"].startswith(D.ITEM_SELECTION) and D.DRIVER_VERSION == "canary-driver/8"
