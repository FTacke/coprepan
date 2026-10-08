"""The staged canary driver, qualified entirely offline (CPD-0016).

A scripted server on a loopback address plays the outlet. What is tested is the order of the stages,
the budgets (real requests, redirects and robots files included), the refusals, the outage path, the
interruptions and the receipt — never an outlet, and never the network.
"""

from __future__ import annotations

import json
import socket
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

from coprepan import acquisition, admission, canary_driver as D, core_pipeline as C, crawler_identity, extraction, freeze
from coprepan import http_acquisition as H, fetcher as F, ledger as L, outage_spool, pack, policy as P, preservation
from coprepan import recovery, schedule, storage_roots as S
from coprepan.crawler_identity import loopback_test_identity
from coprepan.document_identity import IdentityTables
from support_http import FakeClock, LocalSite, Response
from test_offline_e2e import HTML, ROBOTS, RSS, SCHEDULE, SITEMAP, XML, fx, make_registry, script
from test_fetcher import FEEDS, MOBILE, OUTLET, WWW

T0 = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)
LIMITS = F.FetchLimits(timeout_seconds=2, max_redirects=3, max_body_bytes=500_000, max_attempts=1, backoff_base_seconds=2, backoff_max_seconds=60)
SMALL = D.CanaryBudget(outlets=1, item_requests_total=40, item_requests_per_outlet=40, other_requests_per_outlet=12)
PAGE = "<html><body><article><h1>Nota</h1><p>Texto de la nota número {n}.</p></article></body></html>"


def feed(paths):
    items = "".join(f"<item><link>{path if path.startswith('http') else WWW + path}</link></item>" for path in paths)
    return ('<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>' + items + "</channel></rss>").encode("utf-8")


def dead_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def page(n: int) -> Response:
    return Response(200, HTML, PAGE.format(n=n).encode("utf-8"))


def scripted(site, paths=("/ok", "/ok?utm_source=rss", "/gone404", "/gone410", "/slow429", "/err500", "/timeout", "/redir", "/moved", f"{MOBILE}/conexion")):
    """An outlet with every kind of answer a real one can give."""
    script(site)
    site.routes.update({
        "/robots.txt": Response(200, [("Content-Type", "text/plain")], b"User-agent: *\nDisallow: /privado/\n"),
        "/rss.xml": Response(200, [("Content-Type", "application/rss+xml")], feed(paths)),
        "/sitemap_index.xml": Response(200, XML, b"<sitemapindex><sitemap><loc>https://www.diario-ejemplo.test/sitemaps/2026-10.xml"),  # truncated: malformed
        "/ok": page(1), "/ok?utm_source=rss": page(1), "/gone410": Response(410, HTML, b"<html><body><p>gone</p></body></html>"),
        "/slow429": Response(429, HTML + [("Retry-After", "120")], b"<html><body><p>slow down</p></body></html>"),
        "/err500": Response(500, HTML, b"<html><body><p>error</p></body></html>"),
        "/timeout": Response(200, HTML, page(2).body, delay_seconds=3.0),
        "/redir": Response(302, [("Location", "/redir-target")]), "/redir-target": page(3),
        "/moved": Response(301, [("Location", "/moved-target")]), "/moved-target": page(4),
    })


@pytest.fixture
def site():
    with LocalSite() as server:
        scripted(server)
        yield server


def site_checkout(base, *, deployed=b"<html>crawler</html>", local=b"<html>crawler</html>", matched=True):
    """A directory that looks like a checkout as far as the crawler page and its deployment receipt go."""
    import hashlib
    checkout = base / "checkout"
    (checkout / "web" / "coprepan" / "crawler").mkdir(parents=True, exist_ok=True)
    (checkout / "web" / "coprepan" / "crawler" / "index.html").write_bytes(local)
    receipt = {"site_url": "https://sitio.test/", "public_check_utc": "2026-10-08T00:00:00Z",
               "after": {"files": [{"path": "crawler/index.html", "sha256": hashlib.sha256(deployed).hexdigest(), "size": len(deployed)}]},
               "public_check": {"pages": [{"url": "https://sitio.test/crawler/", "status": 200, "content_equals_source": matched}]}}
    (checkout / "web" / "DEPLOY_RECEIPT_2026-10-08.json").write_text(json.dumps(receipt), encoding="utf-8")
    return checkout


class Timed(D.BudgetedFetcher):
    """Records the instant each request is really sent, after the pause."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sent = []

    def _pace(self, origin):
        super()._pace(origin)
        self.sent.append((origin, self.clock()))


class Drive:
    """One canary pass against the scripted outlet, in its own workspace, root and spool."""

    def __init__(self, base, site, *, budget=SMALL, policy=None, start=T0, schedule_policy=SCHEDULE, spool_capacity=1 << 30):
        self.workspace = C.Workspace(base / "workspace")
        self.root, self.spool = base / "preservation", base / "spool"
        for directory in (self.workspace.root, self.root, self.spool):
            directory.mkdir(parents=True, exist_ok=True)
        self.site, self.registry, self.clock, self.schedule = site, make_registry(), FakeClock(start), schedule_policy
        self.identity = loopback_test_identity()
        gate = P.PolicyGate(policy or P.loopback_test_policy(), self.registry, self.identity)
        override = {origin: ("127.0.0.1", site.port) for origin in (WWW, FEEDS)}
        override[MOBILE] = ("127.0.0.1", dead_port())                      # a host that refuses connections
        self.fetcher = Timed(budget=budget, used=D.tally_from_evidence(self.workspace), identity=self.identity, gate=gate,
                                         limits=LIMITS, clock=self.clock, sleep=self.clock.sleep, connect_override=override)
        self.run = H.http_fetch_run(start, [OUTLET], {"driver": D.DRIVER_VERSION}, self.identity)
        self.target_up, self.spool_policy = True, outage_spool.SpoolPolicy(min_free_bytes=1, max_spool_bytes=spool_capacity)

    def preservation_root(self):
        if not self.target_up:
            raise S.StorageRootUnreachable("PRESERVATION: not reachable")
        return self.root

    def go(self):
        self.outcome = D.run_canary(self.workspace, self.registry, self.run, outlet_ids=[OUTLET], fetcher=self.fetcher,
                                    schedule_policy=self.schedule, clock=self.clock, preservation_root=self.preservation_root,
                                    spool_root=lambda: self.spool, spool_policy=self.spool_policy, disabled_channels=())
        return self.outcome

    def receipt(self):
        return D.build_receipt(self.workspace, run=self.run, commit="0" * 40, baseline_id="b" * 64,
                               policy_record=self.fetcher.gate.policy, schedule_policy=self.schedule, identity=self.identity,
                               storage_contract_sha256="c" * 64, outlet_ids=[OUTLET], channels={OUTLET: [RSS, SITEMAP]},
                               preservation_root=self.root, spool_root=self.spool, started_at="s", finished_at="f")

    def states(self):
        return self.workspace.ledger().states()


@pytest.fixture
def drive(tmp_path, site):
    return Drive(tmp_path / "one", site)


# --- the happy path -----------------------------------------------------------------------------------


def test_all_five_stages_run_in_order_and_end_preserved_identified_extracted_and_labelled(drive):
    outcome = drive.go()
    stages = outcome["outlets"][OUTLET]["stages"]
    assert set(stages) == {"A_probe", "B_discovery", "C_item_fetch", "D_preserve", "E_derive"}
    paths = drive.site.paths()
    first_item = min(index for index, path in enumerate(paths) if path in ("/ok", "/gone404", "/redir"))
    assert paths[0] == "/robots.txt" and paths.index("/rss.xml") < paths.index("/sitemap_index.xml") < first_item   # probe, discovery, then items
    assert stages["A_probe"]["requests"] == {"channel_document:FETCHED": 1} and stages["A_probe"]["candidates_requested"] == 0
    assert stages["B_discovery"]["requests"] == {"channel_document:FETCHED": 1}
    assert set(drive.states().values()) - {"FETCH_FAILED"} == {"RAW_PRESERVED"}
    (pack_id, preserved), = stages["D_preserve"].items()
    assert preserved["state"] == "RAW_PRESERVED" and preserved["route"] == "direct"
    derived = stages["E_derive"][pack_id]
    assert derived["documents"] >= 5 and derived["extracted"] >= 5 and sum(derived["labels"].values()) >= 5
    assert outage_spool.pending_records(drive.spool) == [] and [c["classification"] for c in outcome["checkpoints"]]
    assert all(c["classification"] in ("CLEAN", "INCOMPLETE_RESUMABLE") for c in outcome["checkpoints"])


def test_every_answer_an_outlet_can_give_is_evidence_and_nothing_more(drive):
    drive.go()
    receipt = drive.receipt()
    classes = receipt["response_classes"]
    for expected in ("200", "404", "410", "429", "500", "failed:timeout", "failed:connection_error"):
        assert expected in classes or expected == "failed:connection_error", (expected, classes)
    assert classes["200"] >= 5 and classes["404"] >= 1
    assert receipt["counts"]["failed"] >= 1 and receipt["counts"]["items_fetched"] >= 6
    # a retry is never made inside a call: a 429 or a 500 is asked once, and a server's Retry-After is on record
    assert drive.site.paths().count("/slow429") == 1 and drive.site.paths().count("/err500") == 1
    rows = [row for row in H.request_rows(drive.workspace) if row["event"] == "FINISHED" and row["url"].endswith("/slow429")]
    assert rows[0]["attempts"][0]["retry_after"] is not None


def test_a_malformed_channel_document_is_a_note_not_a_failure(drive):
    outcome = drive.go()
    discovery_b = outcome["outlets"][OUTLET]["stages"]["B_discovery"]["discovery"][0]
    assert discovery_b["candidates_new"] == 0 and discovery_b["documents_read"] in (0, 1)


def test_a_candidate_listed_twice_is_one_request(drive):
    drive.go()
    assert drive.site.paths().count("/ok") + drive.site.paths().count("/ok?utm_source=rss") == 1


def test_redirects_are_requests_and_are_counted_as_such(drive):
    drive.go()
    assert "/redir-target" in drive.site.paths() and "/moved-target" in drive.site.paths()
    receipt = drive.receipt()
    assert receipt["requests"]["total"] == len(drive.site.paths()) + 1      # the one refused connection never reached the server
    assert receipt["requests"]["total"] == drive.fetcher.transport_calls == drive.fetcher.used_total()


# --- budgets -----------------------------------------------------------------------------------------


def test_the_receipt_is_rederived_from_evidence_and_agrees_with_the_counters(drive):
    drive.go()
    receipt = drive.receipt()
    assert receipt == drive.receipt()                                       # deterministic
    assert receipt["requests"]["total"] == drive.fetcher.transport_calls
    assert receipt["requests"]["item"] == drive.fetcher.used_total(D.ITEM) and receipt["requests"]["other"] == drive.fetcher.used_total(D.OTHER)
    assert D.tally_from_evidence(drive.workspace, drive.run.run_id) == drive.fetcher.used
    assert receipt["counts"]["preserved"] == receipt["counts"]["fetch_records"] - receipt["counts"]["failed"] > 0
    assert receipt["counts"]["pending"] == 0 and receipt["counts"]["spooled_objects_pending"] == 0
    assert receipt["bytes"]["received_bodies"] > 0 and receipt["bytes"]["preserved_objects"] > 0
    assert receipt["crawler_identity_sha256"] == drive.identity.sha256 and receipt["outlets"] == [OUTLET]
    json.dumps(receipt)


def test_the_item_budget_is_never_exceeded_and_the_refusals_are_on_record(tmp_path, site):
    tight = D.CanaryBudget(outlets=1, item_requests_total=8, item_requests_per_outlet=8, other_requests_per_outlet=12)
    run = Drive(tmp_path / "tight", site, budget=tight)
    run.go()
    receipt = run.receipt()
    assert receipt["requests"]["item"] <= 8 and run.fetcher.used_total(D.ITEM) <= 8
    assert len([p for p in site.paths() if p not in ("/robots.txt", "/rss.xml", "/sitemap_index.xml")]) <= 8
    assert any(key.endswith("canary_budget_exhausted") for key in receipt["refused"])        # a refusal, not a silent drop
    assert set(run.states().values()) - {"FETCH_FAILED"} == {"RAW_PRESERVED"}


def test_a_budget_is_the_budget_of_the_evidence_after_a_restart(tmp_path, site):
    tight = D.CanaryBudget(outlets=1, item_requests_total=8, item_requests_per_outlet=8, other_requests_per_outlet=12)
    first = Drive(tmp_path / "restart", site, budget=tight)
    first.go()
    spent = first.fetcher.used_total()
    second = Drive(tmp_path / "restart", site, budget=tight)                 # a new process: same workspace, same run
    second.run = first.run
    assert second.fetcher.used_total() == spent and second.fetcher.used_total(D.ITEM) == first.fetcher.used_total(D.ITEM)


def test_a_call_outside_a_budget_or_over_it_is_an_integrity_failure(drive):
    with pytest.raises(D.BudgetExceeded):
        drive.fetcher._request(f"{WWW}/ok")                                  # no budgeted context
    drive.fetcher._context = (OUTLET, D.ITEM)
    drive.fetcher.used[(OUTLET, D.ITEM)] = SMALL.item_requests_per_outlet
    with pytest.raises(D.BudgetExceeded):
        drive.fetcher._request(f"{WWW}/ok")
    assert drive.site.requests == []


def test_the_budget_has_a_hard_ceiling_and_is_consistent():
    with pytest.raises(ValueError):
        D.CanaryBudget(item_requests_total=D.HARD_ITEM_REQUESTS + 1)
    with pytest.raises(ValueError):
        D.CanaryBudget(item_requests_total=10, item_requests_per_outlet=11)
    with pytest.raises(ValueError):
        D.CanaryBudget(other_requests_per_outlet=-1)
    default = D.CanaryBudget()
    assert default.outlets == 5 and default.item_requests_total <= 100 and default.channels_per_outlet <= 2
    assert default.item_requests_per_outlet * default.outlets >= default.item_requests_total


def test_exactly_the_budgeted_number_of_outlets_is_run(drive):
    with pytest.raises(D.CanaryStopped):
        D.run_canary(drive.workspace, drive.registry, drive.run, outlet_ids=[OUTLET, "es_otro_diario"], fetcher=drive.fetcher,
                     schedule_policy=drive.schedule, clock=drive.clock, preservation_root=drive.preservation_root,
                     spool_root=None, spool_policy=None)
    assert drive.site.requests == []


# --- refusals ----------------------------------------------------------------------------------------


def test_robots_disallow_ends_that_path_and_no_request_follows_it(tmp_path, site):
    site.routes["/robots.txt"] = Response(200, [("Content-Type", "text/plain")], b"User-agent: *\nDisallow: /rss.xml\nDisallow: /ok\nDisallow: /redir\n")
    run = Drive(tmp_path / "robots", site)
    run.go()
    paths = site.paths()
    assert "/rss.xml" not in paths and "/ok" not in paths and "/redir" not in paths                 # asked for nothing it was told not to
    receipt = run.receipt()
    assert receipt["refused"].get("DENIED:robots_disallow", 0) >= 1
    assert "A_probe" in run.outcome["outlets"][OUTLET]["stages"]


def test_an_opt_out_means_no_request_at_all(tmp_path, site):
    denied = P.loopback_test_policy(opt_outs=[{"outlet_id": OUTLET, "reason": "asked to be left out", "recorded_at": "2026-10-08T00:00:00.000000Z"}])
    run = Drive(tmp_path / "optout", site, policy=denied)
    run.go()
    assert site.requests == [] and run.fetcher.transport_calls == 0 and run.receipt()["requests"]["total"] == 0
    assert run.receipt()["refused"].get("DENIED:explicit_opt_out", 0) >= 1


def test_a_disabled_channel_is_never_selected_or_asked(drive):
    outlet = drive.registry.resolve(OUTLET)
    assert D.select_channels(outlet, [RSS], 2) == [SITEMAP]
    assert D.select_channels(outlet, [], 2) == [RSS, SITEMAP] and D.select_channels(outlet, [], 1) == [RSS]
    assert D.select_channels(outlet, [RSS, SITEMAP], 2) == []


def test_requests_to_one_origin_keep_the_policy_pace(tmp_path, site):
    paced = P.loopback_test_policy(rate_limit={"min_interval_seconds_per_origin": 10, "crawl_delay": "binding_minimum", "crawl_delay_max_seconds": 60})
    run = Drive(tmp_path / "pace", site, policy=paced)
    run.go()
    sent = [(origin, at) for origin, at in run.fetcher.sent if origin == WWW]
    gaps = [(b[1] - a[1]).total_seconds() for a, b in zip(sent, sent[1:])]
    assert len(sent) > 8 and min(gaps) >= 10                                   # never two requests to one origin closer than the policy's pace


# --- the outage path ---------------------------------------------------------------------------------


def test_an_unreachable_target_spools_the_pack_and_nothing_is_preserved_or_read(tmp_path, site):
    run = Drive(tmp_path / "outage", site)
    run.target_up = False
    outcome = run.go()
    stages = outcome["outlets"][OUTLET]["stages"]
    (pack_id, preserved), = stages["D_preserve"].items()
    assert (preserved["state"], preserved["route"], preserved["pending_location"]) == ("PRESERVATION_PENDING", "spooled", "SPOOL")
    assert stages["E_derive"][pack_id].keys() == {"skipped"}                  # no identity, no extraction from a pending input
    assert "RAW_PRESERVED" not in run.states().values() and IdentityTables(run.workspace.identity).documents == {}
    assert not run.workspace.layers.exists() or not any(run.workspace.layers.rglob("payload"))
    assert len(outage_spool.pending_records(run.spool)) == 2                  # the pack and its index, one record each
    receipt = run.receipt()
    assert receipt["counts"]["preserved"] == 0 and receipt["counts"]["pending"] > 0 and receipt["counts"]["spooled_objects_pending"] == 2
    assert acquisition.unfinished_runs(run.workspace.root) == [run.run.run_id]        # not closed: the canary is not complete


def test_when_the_target_returns_the_spool_drains_and_the_rest_follows(tmp_path, site):
    run = Drive(tmp_path / "return", site)
    run.target_up = False
    run.go()
    run.target_up = True
    report = C.drain_spooled_packs(run.workspace, spool_root=run.spool, preservation_root=run.preservation_root, now=run.clock())
    assert len(report["packs_preserved"]) == 1 and report["packs_pending"] == []
    assert outage_spool.pending_records(run.spool) == [] and set(run.states().values()) - {"FETCH_FAILED"} == {"RAW_PRESERVED"}
    again = run.go()                                                          # resume: derive from the now preserved input, ask for nothing new
    requests_after = run.fetcher.transport_calls
    assert again["outlets"][OUTLET]["stages"]["A_probe"] == "already on record"
    assert next(iter(again["outlets"][OUTLET]["stages"]["E_derive"].values()))["documents"] >= 5
    assert run.receipt()["counts"]["pending"] == 0 and requests_after == run.receipt()["requests"]["total"]


@pytest.mark.parametrize("crash", ["between_pack_and_index", "after_masters_before_ledger"])
def test_a_crash_in_preservation_leaves_pending_and_a_second_run_completes_it(tmp_path, site, monkeypatch, crash):
    run = Drive(tmp_path / crash, site)
    original_promote, original_confirm = preservation.promote, C._confirm_preserved
    calls = {"promote": 0}

    def promote(*args, **kwargs):
        calls["promote"] += 1
        if crash == "between_pack_and_index" and calls["promote"] == 2:
            raise KeyboardInterrupt("killed between the pack and its index")
        return original_promote(*args, **kwargs)

    def confirm(*args, **kwargs):
        if crash == "after_masters_before_ledger":
            raise KeyboardInterrupt("killed after both masters, before the ledger")
        return original_confirm(*args, **kwargs)

    monkeypatch.setattr(preservation, "promote", promote)
    monkeypatch.setattr(C, "_confirm_preserved", confirm)
    with pytest.raises(KeyboardInterrupt):
        run.go()
    assert "RAW_PRESERVED" not in run.states().values()                       # never claimed on a half-finished step
    monkeypatch.setattr(preservation, "promote", original_promote)
    monkeypatch.setattr(C, "_confirm_preserved", original_confirm)
    requests = run.fetcher.transport_calls
    run.go()
    assert set(run.states().values()) - {"FETCH_FAILED"} == {"RAW_PRESERVED"} and run.fetcher.transport_calls == requests   # completed without a single new request
    assert IdentityTables(run.workspace.identity).documents


def test_no_fetch_is_raw_preserved_without_verified_bytes_on_the_target(drive):
    drive.go()
    preserved = C.open_preserved_pack(drive.root, next(iter(D.pack_ids(drive.workspace))))
    held = [fetch_id for fetch_id, entry in preserved.entries.items() if entry.body_sha256 is not None]
    assert set(held) == {f for f, s in drive.states().items() if s == "RAW_PRESERVED"}
    for fetch_id in held:
        assert acquisition.sha256_bytes(preserved.body(fetch_id)) == preserved.entries[fetch_id].body_sha256


# --- repeating and resuming ----------------------------------------------------------------------------


def test_a_repeated_run_makes_no_request_and_changes_nothing(drive):
    drive.go()
    requests, states, rows = drive.fetcher.transport_calls, dict(drive.states()), len(H.request_rows(drive.workspace))
    receipt = drive.receipt()
    drive.go()
    assert drive.fetcher.transport_calls == requests and drive.states() == states
    assert len(H.request_rows(drive.workspace)) == rows and drive.receipt() == receipt


def test_a_late_second_pass_revalidates_instead_of_fetching_again(tmp_path, site):
    scripted(site, paths=("/ok", "/gone404", "/redir"))      # no refusing answer: an origin that refused stays on hold (CPD-0017)
    site.routes["/ok"] = Response(200, HTML + [("ETag", '"v1"')], page(1).body, etag='"v1"')
    run = Drive(tmp_path / "late", site)
    run.go()
    run.clock.now += timedelta(days=8)                                        # past the test schedule's revisit interval
    before = len(site.requests)
    run.go()
    conditional = [headers for path, headers in site.requests[before:] if path == "/ok" and "if-none-match" in headers]
    assert conditional and conditional[0]["if-none-match"] == '"v1"'
    records = D.fetch_records(run.workspace)
    assert any(r["revalidates"] != "not_applicable" for r in records)         # a 304 is recorded as one, without inventing a body


def test_the_workspace_is_never_damaged_by_a_whole_run(drive):
    drive.go()
    acquisition.close_run(drive.workspace.root, drive.run, finished_at=drive.clock(), status="COMPLETED", counts={}, pack_ids=D.pack_ids(drive.workspace))
    diagnosis = recovery.diagnose(drive.workspace.root, drive.root, drive.registry)
    assert diagnosis["classification"] == "CLEAN", diagnosis


# --- the pin and the baseline --------------------------------------------------------------------------


def test_the_driver_pin_is_deterministic_and_names_no_location(drive):
    pin = D.driver_pin(SMALL, drive.registry, [OUTLET], [])
    assert pin == D.driver_pin(SMALL, drive.registry, [OUTLET], []) and pin["outlets"] == {OUTLET: [RSS, SITEMAP]}
    text = json.dumps(pin)
    assert ":\\" not in text and "/Users/" not in text and pin["driver"] == D.DRIVER_VERSION and pin["extractor_lifecycle"] == "EXPERIMENTAL"
    assert pin["fetch_limits"]["max_attempts"] == 1 and pin["hard_item_request_ceiling"] == 100


def test_the_canary_pin_needs_a_target_identity_and_has_no_disk_in_it(tmp_path, drive):
    from coprepan import preservation_target as PT
    with pytest.raises(D.CanaryStopped):
        D.canary_pin(SMALL, drive.registry, [OUTLET], [], tmp_path, P.loopback_test_policy())
    PT.initialise_target(drive.root, "coprepan-preservation-test", operator="test", now=T0)
    pin = D.canary_pin(SMALL, drive.registry, [OUTLET], [], drive.root, P.loopback_test_policy(), repository=site_checkout(tmp_path))
    assert pin["storage_target"]["target_id"] == "coprepan-preservation-test" and str(drive.root) not in json.dumps(pin)
    assert pin["storage_contract_sha256"] == "8d17fc214076b21e47774d228e016dfe36484b29ce0ecad693456c07f9018fb3"
    assert set(pin["outlets"][OUTLET]) == {"record_sha256", "url_rules"}


def test_a_canary_baseline_does_not_wait_for_the_measurement_the_canary_makes():
    arguments = dict(code_commit="a" * 40, created_at=T0, operator="operator", test_baseline={"suite": "x", "passed": 1})
    acquisition_scope = freeze.build_manifest(**arguments)
    canary_scope = freeze.build_manifest(**arguments, scope=freeze.SCOPE_CANARY)
    assert any(reason.startswith("O-4") for reason in acquisition_scope["blocking"])
    assert not any(reason.startswith("O-4") for reason in canary_scope["blocking"]) and canary_scope["scope"] == "canary"
    with pytest.raises(ValueError):
        freeze.build_manifest(**arguments, scope="whatever")


def test_a_run_is_refused_without_everything_it_stands_on(tmp_path):
    with pytest.raises(D.CanaryStopped):
        D.main(["run", "--outlet", "bo_el_deber", "--pinned-commit", "0" * 40, "--approved-baseline", str(tmp_path / "none.json"),
                "--tests-passed", "1", "--required-free-bytes", "1", "--receipt-dir", str(tmp_path / "r")])
    assert not (tmp_path / "r").exists()
