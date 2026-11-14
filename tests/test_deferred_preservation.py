"""A canary whose preservation is deferred (CPD-0036), qualified offline against the loopback outlet of the driver's tests.

What is shown: the run never resolves the preservation target (no contact, no write probe) and writes nothing to the spool; every
received body ends sealed, verified and honestly ``PRESERVATION_PENDING`` in the runtime workspace, never ``RAW_PRESERVED``; the
local verification passes on that evidence and fails on a damaged pack; the record that authorises a deferring wave is pinned with
that mode; the frozen baseline passes O-3 only by the local report, and only for a canary; the later promotion waits for every gate
of shared storage and then preserves what was pending. Nothing here is a real outlet, a real share or a real backup.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from coprepan import canary, canary_driver as D, canary_evidence as E, delegation, freeze, preservation_target as PT
from coprepan import resource_policy as R
from test_canary_driver import Drive, OUTLET, RSS, SITEMAP, site  # noqa: F401  (the loopback outlet fixture)
from test_delegated_operator import a_record, checked


def deferred_run(tmp_path, site):  # noqa: F811
    run = Drive(tmp_path / "deferred", site)
    outcome = D.run_canary(run.workspace, run.registry, run.run, outlet_ids=[OUTLET], fetcher=run.fetcher, schedule_policy=run.schedule,
                           clock=run.clock, preservation_root=D.deferred_root, spool_root=None, spool_policy=None, disabled_channels=())
    return run, outcome


def deferred_receipt(run):
    receipt = D.build_receipt(run.workspace, run=run.run, commit="0" * 40, baseline_id="b" * 64, policy_record=run.fetcher.gate.policy,
                              schedule_policy=run.schedule, identity=run.identity, storage_contract_sha256="c" * 64, outlet_ids=[OUTLET],
                              channels={OUTLET: [RSS, SITEMAP]}, preservation_root=None, spool_root=run.spool, started_at="s", finished_at="f",
                              preservation_mode=delegation.PRESERVATION_DEFERRED_LOCAL)
    return {**receipt, "fetcher_transport_calls": run.fetcher.transport_calls}


# --- the run --------------------------------------------------------------------------------------------------


def test_a_deferred_run_keeps_every_body_pending_in_the_workspace_and_never_touches_target_or_spool(tmp_path, site):  # noqa: F811
    run, outcome = deferred_run(tmp_path, site)
    stages = outcome["outlets"][OUTLET]["stages"]
    (pack_id, preserved), = stages["D_preserve"].items()
    assert (preserved["state"], preserved["route"], preserved["pending_location"]) == ("PRESERVATION_PENDING", "workspace", "WORKSPACE")
    assert "PreservationDeferred" in preserved["reason"]
    assert stages["E_derive"][pack_id].keys() == {"skipped"}
    assert not any(run.root.iterdir()) and not any(run.spool.iterdir())           # neither the target nor the spool was written
    states = set(run.states().values())
    assert "RAW_PRESERVED" not in states and "PRESERVATION_PENDING" in states
    receipt = deferred_receipt(run)
    assert receipt["preservation"] == delegation.PRESERVATION_DEFERRED_LOCAL and D.deferred_complete(receipt)
    assert receipt["counts"]["preserved"] == 0 and receipt["counts"]["spooled_objects_pending"] == 0
    assert D.pending_pack_ids(run.workspace) == [pack_id]


def test_the_deferred_root_is_a_storage_refusal_so_preservation_keeps_the_pack_pending():
    with pytest.raises(D.PreservationDeferred) as raised:
        D.deferred_root()
    from coprepan import storage_roots
    assert isinstance(raised.value, storage_roots.StorageRefusal)


def test_a_direct_receipt_is_unchanged_by_the_deferred_mode(tmp_path, site):  # noqa: F811
    run = Drive(tmp_path / "direct", site)
    run.go()
    assert "preservation" not in run.receipt()


# --- the local verification and measurement --------------------------------------------------------------------


def test_the_local_verification_passes_on_honest_pending_evidence(tmp_path, site):  # noqa: F811
    run, _ = deferred_run(tmp_path, site)
    receipt = deferred_receipt(run)
    result = E.verify_deferred(run.workspace, run=SimpleNamespace(run_id=run.run.run_id), spool_root=run.spool,
                               stored_receipt=receipt, rebuilt_receipt=deferred_receipt(run))
    assert result["status"] == "PASS", result["checks"]
    assert {c["check"] for c in result["checks"]} >= {"workspace_readback_and_fixity", "pending_matches_received_bytes",
                                                      "extraction_reproducible_from_local_bytes", "receipt_rederived_from_evidence", "nothing_spooled"}
    measured = E.measure_deferred(run.workspace, run_id=run.run.run_id, stored_receipt=receipt)
    assert measured["packs_pending_in_the_workspace"] == 1 and measured["pending_pack_and_index_bytes"] > 0
    assert measured["request_seconds"]["n"] == receipt["counts"]["fetch_records"]


def test_the_local_verification_fails_on_a_damaged_pack_or_a_changed_receipt(tmp_path, site):  # noqa: F811
    run, _ = deferred_run(tmp_path, site)
    receipt = deferred_receipt(run)
    changed = {**receipt, "counts": {**receipt["counts"], "items_fetched": receipt["counts"]["items_fetched"] + 1}}
    result = E.verify_deferred(run.workspace, run=SimpleNamespace(run_id=run.run.run_id), spool_root=run.spool,
                               stored_receipt=changed, rebuilt_receipt=receipt)
    assert result["status"] == "FAIL" and any(c["check"] == "receipt_rederived_from_evidence" and c["status"] == "FAIL" for c in result["checks"])
    (pack_path,) = run.workspace.packs.glob("*.warc.gz")
    data = bytearray(pack_path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    pack_path.write_bytes(bytes(data))
    damaged = E.verify_deferred(run.workspace, run=SimpleNamespace(run_id=run.run.run_id), spool_root=run.spool,
                                stored_receipt=receipt, rebuilt_receipt=receipt)
    assert any(c["check"] == "workspace_readback_and_fixity" and c["status"] == "FAIL" for c in damaged["checks"])


# --- the record, the baseline, the preflight -------------------------------------------------------------------


def test_a_deferring_wave_is_valid_pinned_with_its_mode_and_a_direct_wave_is_as_before():
    record = a_record()
    record["waves"][0]["preservation"] = delegation.PRESERVATION_DEFERRED_LOCAL
    delegation.validate(record)
    block = checked(record)
    assert block["preservation"] == delegation.PRESERVATION_DEFERRED_LOCAL and delegation.deferred(block)
    plain = checked(a_record())
    assert "preservation" not in plain and not delegation.deferred(plain) and not delegation.deferred(None)
    record["waves"][0]["preservation"] = "somewhere_else"
    with pytest.raises(delegation.AuthorizationError):
        delegation.validate(record)
    record["waves"][0].pop("preservation")
    record["waves"][0]["extra"] = 1
    with pytest.raises(delegation.AuthorizationError):
        delegation.validate(record)


def test_a_wave_may_read_up_to_four_channels_and_no_request_limit_rises_with_it():
    record = a_record()
    record["waves"][0]["limits"]["channels_per_outlet"] = 3
    delegation.validate(record)
    limits = {"item_requests_total": 96, "item_requests_per_outlet": 6, "other_requests_per_outlet": 8, "total_requests_ceiling": 224,
              "channels_per_outlet": 3}
    budget = D.canary_budget(16, limits)
    assert (budget.channels_per_outlet, budget.item_requests_per_outlet, budget.other_requests_per_outlet) == (3, 6, 8)
    assert D.canary_budget(16, {k: v for k, v in limits.items() if k != "channels_per_outlet"}).channels_per_outlet == 2
    assert D.canary_budget(16, {**limits, "other_requests_per_outlet": 20}).other_requests_per_outlet == 8   # never raised
    for bad in (0, 5, True, "3"):
        record["waves"][0]["limits"]["channels_per_outlet"] = bad
        with pytest.raises(delegation.AuthorizationError):
            delegation.validate(record)


def test_the_deferred_readiness_reads_only_the_workspace_and_is_never_ready(tmp_path):
    now = datetime(2026, 11, 14, 20, 0, tzinfo=timezone.utc)
    (tmp_path / "ws").mkdir()
    report = PT.deferred_readiness(tmp_path / "ws", required_free_bytes=1, now=now)
    assert report["status"] == PT.DEFERRED_LOCAL != PT.READY and report["target_id"] is None
    assert PT.deferred_readiness(tmp_path / "ws", required_free_bytes=1 << 62, now=now)["status"] == PT.NOT_READY
    assert PT.deferred_readiness(tmp_path / "missing", required_free_bytes=1, now=now)["status"] == PT.NOT_READY


def test_o3_is_passed_by_the_local_report_only_for_a_canary(tmp_path):
    now = datetime(2026, 11, 14, 20, 0, tzinfo=timezone.utc)
    (tmp_path / "ws").mkdir()
    report = PT.deferred_readiness(tmp_path / "ws", required_free_bytes=1, now=now)
    common = dict(code_commit="0" * 40, created_at=now, operator="o", test_baseline={"passed": 1}, storage_target=report)
    assert not any(b.startswith("O-3") for b in freeze.build_manifest(scope=freeze.SCOPE_CANARY, **common)["blocking"])
    assert any(b.startswith("O-3") for b in freeze.build_manifest(scope=freeze.SCOPE_ACQUISITION, **common)["blocking"])


def test_the_canary_pin_of_a_deferring_wave_reads_no_target_identity(tmp_path, site):  # noqa: F811
    run = Drive(tmp_path / "pin", site)
    from test_canary_driver import site_checkout
    checkout = site_checkout(tmp_path)
    block = {"mode": delegation.MODE_DELEGATED, "authorization_id": "A", "authorization_sha256": "s", "wave": "w",
             "issued_by": "o", "issued_to": "a", "preservation": delegation.PRESERVATION_DEFERRED_LOCAL}
    pin = D.canary_pin(D.canary_budget(1, {"item_requests_total": 8, "item_requests_per_outlet": 8, "other_requests_per_outlet": 8,
                                           "total_requests_ceiling": 16}), run.registry, [OUTLET], (), None, run.fetcher.gate.policy,
                       repository=checkout, authorization=block)
    assert pin["storage_target"] == {"mode": delegation.PRESERVATION_DEFERRED_LOCAL, "target_id": None}
    with pytest.raises(D.CanaryStopped):                       # a direct canary still needs the target's identity
        D.canary_pin(D.canary_budget(5), run.registry, [OUTLET], (), tmp_path / "no-target", run.fetcher.gate.policy, repository=checkout)


def test_the_deferred_preflight_does_not_resolve_the_target_or_the_backup(tmp_path):
    (tmp_path / "ws").mkdir()
    (tmp_path / "spool").mkdir()
    environment = {"COPREPAN_WORKSPACE_ROOT": str(tmp_path / "ws"), "COPREPAN_SPOOL_ROOT": str(tmp_path / "spool"),
                   "COPREPAN_PRESERVATION_ROOT": str(tmp_path / "share-that-is-not-there"), "COPREPAN_BACKUP_ROOT": str(tmp_path / "backup-not-there")}
    report = canary.preflight(outlet_ids=[], tests_passed=1, tests_commit="c", code_commit="c", approved_baseline=None, required_free_bytes=1,
                              now=datetime(2026, 11, 14, 20, 0, tzinfo=timezone.utc), environment=environment, deferred_preservation=True)
    by_name = {c["check"]: c for c in report["checks"]}
    assert by_name["preservation_deferred_local"]["status"] == canary.PASS
    assert by_name["storage_roles_separate"]["status"] == canary.PASS and "not resolved" in by_name["storage_roles_separate"]["detail"]
    assert "preservation_target_ready" not in by_name
    assert not (tmp_path / "share-that-is-not-there").exists() and not (tmp_path / "backup-not-there").exists()
    assert canary.local_roles(environment) == {"RUNTIME": tmp_path / "ws", "SPOOL": tmp_path / "spool"}


# --- the later promotion ---------------------------------------------------------------------------------------


@pytest.fixture
def pending_world(tmp_path, site):  # noqa: F811
    run, _ = deferred_run(tmp_path, site)
    receipt = deferred_receipt(run)
    environment = {"COPREPAN_WORKSPACE_ROOT": str(run.workspace.root), "COPREPAN_PRESERVATION_ROOT": str(run.root)}
    return run, receipt, environment


SATURDAY = datetime(2026, 11, 14, 20, 0, tzinfo=timezone.utc)
MONDAY = datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc)          # 11:00 in Berlin: a weekday, outside every quiet window


def test_the_promotion_waits_for_the_calendar_and_for_a_current_backup(pending_world):
    run, receipt, environment = pending_world
    weekend = D.preserve_deferred(receipt, environment=environment, now=SATURDAY)
    assert weekend["attempted"] == 0 and weekend["held_because"].startswith(R.SCHEDULED_PAUSE) and weekend["still_pending"]
    no_backup = D.preserve_deferred(receipt, environment=environment, now=MONDAY)
    assert no_backup["attempted"] == 0 and "backup" in no_backup["held_because"]
    assert not any(run.root.iterdir())                                 # nothing was promoted while a gate held


def test_the_promotion_preserves_what_was_pending_once_every_gate_permits(pending_world, monkeypatch):
    run, receipt, environment = pending_world
    from coprepan import primary_backup
    monkeypatch.setattr(primary_backup, "backup_health", lambda *a, **k: {"level": "OK"})
    done = D.preserve_deferred(receipt, environment=environment, now=MONDAY, registry_=run.registry)
    assert done["held_because"] is None and len(done["preserved"]) == 1 and done["still_pending"] == []
    assert set(run.states().values()) - {"FETCH_FAILED"} == {"RAW_PRESERVED"}
    again = D.preserve_deferred(receipt, environment=environment, now=MONDAY, registry_=run.registry)
    assert again["pending_before"] == 0 and again["attempted"] == 0
    with pytest.raises(D.CanaryStopped):
        D.preserve_deferred({**receipt, "preservation": "direct"}, environment=environment, now=MONDAY)


def test_the_promotion_waits_while_co_ra_pan_observes_the_share_slow(pending_world, monkeypatch):
    run, receipt, environment = pending_world
    from coprepan import primary_backup
    monkeypatch.setattr(primary_backup, "backup_health", lambda *a, **k: {"level": "OK"})
    monkeypatch.setattr(R, "sibling_advisory", lambda *a, **k: {"state": R.SHARE_SLOW, "detail": "slow"})
    held = D.preserve_deferred(receipt, environment=environment, now=MONDAY)
    assert held["attempted"] == 0 and held["held_because"].startswith(R.DEFERRED_RESOURCE_PRIORITY)
