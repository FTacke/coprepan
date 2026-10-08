"""The end-of-canary checks and the O-4 measurement, on an offline run (CPD-0016)."""

from __future__ import annotations

import json
import socket

import pytest

from coprepan import acquisition, canary_driver as D, canary_evidence as E, outage_spool
from test_canary_driver import Drive, OUTLET, site  # noqa: F401  (the fixture)


@pytest.fixture
def finished(tmp_path, site):  # noqa: F811
    drive = Drive(tmp_path / "run", site)
    drive.go()
    receipt = drive.receipt()
    receipt["fetcher_transport_calls"] = drive.fetcher.transport_calls
    acquisition.close_run(drive.workspace.root, drive.run, finished_at=drive.clock(), status="COMPLETED",
                          counts={"requests": receipt["requests"]["total"]}, pack_ids=receipt["packs"])
    drive.stored = receipt
    return drive


def verify(drive, **changes):
    stored = {**drive.stored, **changes}
    return E.verify(drive.workspace, drive.registry, run=drive.run, preservation_root=drive.root, spool_root=drive.spool,
                    stored_receipt=stored, rebuilt_receipt=drive.receipt())


def failed(report):
    return {c["check"] for c in report["checks"] if c["status"] == "FAIL"}


# --- verification ------------------------------------------------------------------------------------


def test_a_finished_canary_verifies_from_evidence(finished):
    report = verify(finished)
    assert report["status"] == "PASS", [c for c in report["checks"] if c["status"] == "FAIL"]
    assert {c["check"] for c in report["checks"]} == {
        "recovery_diagnosis", "preservation_readback_and_fixity", "raw_preserved_matches_verified_bytes", "replay_without_network",
        "receipt_rederived_from_evidence", "receipt_request_count_equals_the_runs_own_counter", "no_pending_objects", "budget_respected"}
    replay = next(c for c in report["checks"] if c["check"] == "replay_without_network")
    assert replay["detail"].startswith("9 extractions") or int(replay["detail"].split()[0]) >= 5


def test_the_network_is_really_unavailable_during_replay_and_restored_after():
    with E.network_unavailable():
        with pytest.raises(OSError, match="network is unavailable"):
            socket.socket().connect(("127.0.0.1", 9))
    probe = socket.socket()
    try:
        with pytest.raises(OSError) as refusal:
            probe.connect(("127.0.0.1", 9))
        assert "network is unavailable" not in str(refusal.value)       # the ordinary refusal of a closed port again
    finally:
        probe.close()


def test_a_damaged_preserved_body_fails_the_read_back(finished):
    master = next(finished.root.rglob("*.warc.gz"))
    data = bytearray(master.read_bytes())
    data[len(data) // 2] ^= 0xFF
    master.write_bytes(bytes(data))
    report = verify(finished)
    assert report["status"] == "FAIL" and "preservation_readback_and_fixity" in failed(report)


def test_a_receipt_that_does_not_match_the_evidence_is_caught(finished):
    wrong = json.loads(json.dumps(finished.stored))
    wrong["requests"]["total"] += 1
    report = verify(finished, requests=wrong["requests"])
    assert {"receipt_rederived_from_evidence", "receipt_request_count_equals_the_runs_own_counter"} <= failed(report)


def test_a_pending_object_fails_the_end_of_the_canary(finished):
    outage_spool.spool_object(next(finished.root.rglob("*.index.jsonl")), spool_root=finished.spool, policy=finished.spool_policy,
                              reason="test", area="raw_index", object_id="pk1-uy_diario_ejemplo-20261008-009",
                              relative_path="uy/uy_diario_ejemplo/x.index.jsonl", declared_sha256=acquisition.sha256_bytes(
                                  next(finished.root.rglob("*.index.jsonl")).read_bytes()), details={})
    assert "no_pending_objects" in failed(verify(finished))


def test_a_run_over_its_item_ceiling_fails_the_budget_check(finished):
    over = {**finished.stored["requests"], "item": D.HARD_ITEM_REQUESTS + 1}
    assert "budget_respected" in failed(verify(finished, requests=over))


# --- measurement -------------------------------------------------------------------------------------


def measure(drive, **kwargs):
    arguments = dict(run_id=drive.run.run_id, preservation_root=drive.root, target_free_bytes=10**12,
                     new_filesystem_bytes=2 * 10**12,
                     legacy_sourced={"per_outlet_day_median": 115, "per_outlet_day_max": 367, "outlet_counts": [5, 53, 82]})
    return E.measure(drive.workspace, **{**arguments, **kwargs})


def test_the_measurement_is_made_of_what_is_on_disk_and_labels_what_it_is(finished):
    result = measure(finished)
    assert result == measure(finished) and json.dumps(result)                       # deterministic and plain data
    receipt = finished.stored
    assert result["measured"]["fetch_records"]["value"] == receipt["counts"]["fetch_records"]
    assert sum(g["fetches"] for g in result["groups"].values()) == receipt["counts"]["fetch_records"]
    assert result["measured"]["preserved_object_bytes_total"]["value"] == receipt["bytes"]["preserved_objects"] > 0
    on_disk = sum(p.stat().st_size for p in finished.root.rglob("*") if p.is_file() and (p.name.endswith(".warc.gz") or p.name.endswith(".index.jsonl")))
    assert result["measured"]["preserved_object_bytes_total"]["value"] == on_disk
    assert sum(g["received_body_bytes_total"] for g in result["groups"].values()) == receipt["bytes"]["received_bodies"]
    assert {v["label"] for v in result["measured"].values()} <= {"MEASURED", "DERIVED"}
    assert all(s["label"] == "PROJECTED" for s in result["scenarios"].values())
    assert all(a["label"] == "ASSUMED" for a in result["annual_conditional"].values())
    assert result["limits"] and "sizes, not a crawl rate" in result["limits"][0]


def test_scenarios_are_ordered_and_scale_with_volume(finished):
    scenarios = measure(finished)["scenarios"]
    low, central, upper = (scenarios[name] for name in ("LOW", "CENTRAL", "UPPER"))
    assert low["all_layers_bytes_per_fetch"] <= central["all_layers_bytes_per_fetch"] <= upper["all_layers_bytes_per_fetch"]
    for scenario in scenarios.values():
        assert abs(scenario["per_100000_fetches_gib"] * 2**30 / 100000 - scenario["all_layers_bytes_per_fetch"]) < 2**30 / 100000 * 0.01 + 1
        assert abs(scenario["per_1000_fetches_mib"] * 2**20 / 1000 - scenario["all_layers_bytes_per_fetch"]) < 2**20 / 1000 * 0.01 + 1


def test_every_outlet_and_the_dominant_component_are_named(finished):
    result = measure(finished)
    assert list(result["outlets"]) == [OUTLET] and result["outlets"][OUTLET]["real_requests"] == finished.stored["requests"]["total"]
    assert result["dominant_component_in_the_canary"]["name"] in ("preserved raw packs", "extraction layer", "workspace records", "preservation manifests")
    assert result["spread"]["min"] <= result["spread"]["mean"] <= result["spread"]["max"]


def test_the_comparison_with_a_target_is_left_out_unless_the_operator_states_it(finished):
    result = measure(finished, target_free_bytes=None, new_filesystem_bytes=None)
    assert result["comparison"] == {}
    stated = measure(finished)["comparison"]
    assert stated["canary_footprint_share_of_interim_free"]["value"] < 1e-3 and stated["planned_filesystem_bytes_stated"]["label"] == "STATED_BY_OPERATOR"
    assert all(years is None or years > 0 for years in stated["years_to_fill_planned_filesystem"].values())


def test_nothing_to_measure_is_a_refusal(finished):
    with pytest.raises(ValueError):
        measure(finished, run_id="r1-" + "0" * 32)
