"""Crash recovery with real process kills (decision CPD-0009).

Each test starts a pipeline in a child process, kills it from outside at a named point, and lets a
**second, independent process** say what is on disk, repair what is torn, and run the pipeline to
its end. The final state must equal that of a run nobody interrupted, and running once more must
change nothing.

What this establishes: robustness of the local pipeline against process death at these points,
and that the state is reconstructed by a process that shares nothing with the one that died. Not
established: behaviour after a power failure (lost un-synced writes), on a real preservation
target, or against a real server.
"""

import pytest

from support_processes import ChildFailed, child, kill_at, start

CLEAN, RESUMABLE, NEEDS_REPAIR, DAMAGED = "CLEAN", "INCOMPLETE_RESUMABLE", "NEEDS_REPAIR", "DAMAGED"
COMPARED = ("ledger", "identity", "layers", "masters")

# crashpoint → (classification a fresh process must give, what is left behind for good)
PIPELINE_CRASHPOINTS = {
    # acquisition
    "run_record_partial": (RESUMABLE, {"part_files": 1}),                    # half a run record, under its staging name
    "warcinfo_partial": (NEEDS_REPAIR, {"torn_sidecars": 1}),                # half the first record of a new pack
    "pack_append_partial@2": (NEEDS_REPAIR, {"torn_sidecars": 1}),           # half a fetch in the pack
    "after_pack_append@3": (RESUMABLE, {}),                                  # bytes in the pack, ledger still FETCH_PLANNED
    "ledger_line_torn@7": (NEEDS_REPAIR, {"torn_sidecars": 1}),              # half a ledger record
    "before_ledger_FETCHED@4": (RESUMABLE, {}),
    # sealing
    "seal_before_index": (RESUMABLE, {}),                                    # renamed to its sealed name, no index
    "seal_before_manifest": (RESUMABLE, {}),                                 # index written, no manifest
    "before_ledger_RAW_VERIFIED@3": (RESUMABLE, {}),
    "before_ledger_PRESERVATION_PENDING@3": (RESUMABLE, {}),
    # promotion
    "before_promotion": (RESUMABLE, {}),                                     # sealed, nothing promoted
    "promotion_partial_copy": (RESUMABLE, {"part_files": 1}),                # part of the master under a staging name
    "after_master_before_manifest": (RESUMABLE, {}),                         # master in place, no manifest
    "before_promotion@2": (RESUMABLE, {}),                                   # pack promoted, index not
    "before_raw_preserved": (RESUMABLE, {}),                                 # both promoted, no fetch marked preserved
    "before_ledger_RAW_PRESERVED@4": (RESUMABLE, {}),                        # some fetches marked, some not
    # identity, extraction, layers
    "after_identity_before_extraction@2": (RESUMABLE, {}),
    "layer_payload_partial@2": (RESUMABLE, {"layer_staging": 1}),            # half a payload
    "layer_before_metadata@2": (RESUMABLE, {"layer_staging": 1}),            # payload, half a manifest
    "layer_before_publish@2": (RESUMABLE, {"layer_staging": 1}),             # complete, not yet published
    "after_extraction_before_version@3": (RESUMABLE, {}),                    # layer stored, version not registered
    "table_row_torn@2": (NEEDS_REPAIR, {"torn_sidecars": 1}),                # half a version row
    "after_rows_before_relation": (RESUMABLE, {}),                           # rows written, relation not
    "after_rows_before_relation@2": (RESUMABLE, {}),
}


@pytest.fixture(scope="module")
def reference(tmp_path_factory):
    """The state after a run nobody interrupted, as a separate process reads it."""
    base = tmp_path_factory.mktemp("reference")
    child("pipeline", base)
    state = child("state", base)
    assert state["ledger_states"] == {"FETCH_FAILED": 1, "RAW_PRESERVED": 8}
    assert state["orphans"] == {"layer_staging": 0, "part_files": 0, "torn_sidecars": []}
    return state


def leftovers(state):
    found = dict(state["orphans"], torn_sidecars=len(state["orphans"]["torn_sidecars"]))
    return {key: value for key, value in found.items() if value}


@pytest.mark.parametrize("crashpoint", list(PIPELINE_CRASHPOINTS))
def test_a_pipeline_killed_at_any_point_is_classified_recovered_and_ends_as_if_never_interrupted(tmp_path, reference, crashpoint):
    expected, left = PIPELINE_CRASHPOINTS[crashpoint]
    kill_at("pipeline", tmp_path, crashpoint)
    out = child("recover", tmp_path, "pipeline")

    diagnosis = out["diagnosis"]
    assert diagnosis["classification"] == expected, diagnosis
    assert diagnosis["damaged"] == [] and diagnosis["unreadable"] == {}        # interrupted is never "damaged"
    assert diagnosis["ledger_and_packs"]["ledger_claims_bytes_no_pack_has"] == 0  # no success without its evidence
    assert (out["repair"]["moved_aside"] != []) == (expected == NEEDS_REPAIR)
    assert out["after_repair"] in (RESUMABLE, CLEAN)

    assert {key: out["state"][key] for key in COMPARED} == {key: reference[key] for key in COMPARED}
    assert out["state_again"] == out["state"]                                  # once more changes nothing
    assert out["again"] == out["resumed"]
    assert out["final"]["classification"] == CLEAN
    assert leftovers(out["state"]) == left                                     # nothing is deleted; what is left is named


def test_what_a_fresh_process_sees_right_after_the_kill(tmp_path):
    kill_at("pipeline", tmp_path, "after_pack_append@3")
    diagnosis = child("diagnose", tmp_path)
    assert diagnosis["ledger_and_packs"]["in_pack_ledger_planned"] == 1        # the bytes are there; the ledger does not say so yet
    assert diagnosis["ledger"] == {"FETCHED": 2, "FETCH_PLANNED": 1}
    assert diagnosis["packs"]["pk1-uy_diario_ejemplo-20261007-000"] == {"fetches": 3, "state": "OPEN"}
    assert len(diagnosis["unfinished_runs"]) == 1

    other = tmp_path / "torn"
    kill_at("pipeline", other, "pack_append_partial@2")
    diagnosis = child("diagnose", other)
    assert diagnosis["packs"]["pk1-uy_diario_ejemplo-20261007-000"]["state"] == "OPEN_TORN_TAIL"
    assert diagnosis["ledger"] == {"FETCHED": 1, "FETCH_PLANNED": 1}           # the half-written fetch is not claimed
    with pytest.raises(ChildFailed, match="PackTornTail"):
        child("pipeline", other)                                               # nothing appends after a torn tail …
    assert child("repair", other)["moved_aside"] == ["packs/pk1-uy_diario_ejemplo-20261007-000.warc.gz.open.torn-0"]
    assert child("repair", other)["moved_aside"] == []                         # … and repair is idempotent


def test_a_killed_promotion_never_leaves_a_master_that_is_believed(tmp_path):
    kill_at("pipeline", tmp_path, "promotion_partial_copy")
    state = child("state", tmp_path)
    assert state["masters"] == {} and state["orphans"]["part_files"] == 1      # a staging file is not a master
    assert state["ledger_states"] == {"FETCH_FAILED": 1, "PRESERVATION_PENDING": 8}   # pending is not preserved
    kill_at("pipeline", tmp_path, "after_master_before_manifest")              # killed again, one step further
    state = child("state", tmp_path)
    assert state["masters"] == {} and state["ledger_states"]["PRESERVATION_PENDING"] == 8   # bytes without a manifest claim nothing
    kill_at("pipeline", tmp_path, "before_raw_preserved")                      # and a third time
    diagnosis = child("diagnose", tmp_path)
    assert diagnosis["ledger_and_packs"]["pending_and_master_verifies"] == 8 and diagnosis["classification"] == RESUMABLE
    child("pipeline", tmp_path)
    assert child("state", tmp_path)["ledger_states"] == {"FETCH_FAILED": 1, "RAW_PRESERVED": 8}


# --- HTTP acquisition: requests are at-least-once, evidence is never doubled ---------------------------


@pytest.fixture(scope="module")
def http_reference(tmp_path_factory):
    out = child("http", tmp_path_factory.mktemp("http_reference"))
    assert out["summary"]["requests"] == {"channel_document:FETCHED": 6, "item:FETCHED": 6}
    return out


@pytest.mark.parametrize("crashpoint, planned_without_end, items_after, repeated_later", [
    ("after_intent_before_request@2", 1, 5, (1,)),      # intent on record, the request not sent
    ("after_response_before_record@2", 1, 5, (1,)),     # the server answered; nothing of the answer was recorded
    ("request_row_torn@3", 0, 6, (0, 1)),               # the end of a request half-written to the log
    ("after_pack_append@5", 1, 6, (0, 1)),              # the answer is in the pack; ledger and log do not say so
])
def test_an_http_run_killed_mid_request_is_resumed_without_losing_or_inventing_evidence(
        tmp_path, http_reference, crashpoint, planned_without_end, items_after, repeated_later):
    kill_at("http", tmp_path, crashpoint)
    out = child("recover", tmp_path, "http")
    diagnosis = out["diagnosis"]
    assert diagnosis["damaged"] == [] and diagnosis["unreadable"] == {}
    assert diagnosis.get("requests_planned_without_end", 0) == planned_without_end
    assert out["resumed"]["summary"]["lifecycle"] == http_reference["summary"]["lifecycle"]   # every candidate ends where it should
    assert out["resumed"]["summary"]["requests"].get("item:FETCHED") == items_after
    assert out["state"]["ledger_states"] == {"RAW_PRESERVED": 14}
    assert out["state_again"] == out["state"]
    assert out["again"]["summary"]["candidates_requested"] == 0                # nothing is due a second time
    final = out["final"]
    assert final["damaged"] == [] and final["ledger_and_packs"]["ledger_claims_bytes_no_pack_has"] == 0
    # an intent without an end stays on record for good — as what it is, not as an open task
    assert final["interrupted_requests_repeated_later"] in repeated_later
    assert final.get("requests_planned_without_end", 0) == 0


# --- replay ------------------------------------------------------------------------------------------


def test_replay_needs_no_network_and_changes_no_preserved_byte(tmp_path):
    child("pipeline", tmp_path)
    layers = child("state", tmp_path)["layers"]
    out = child("replay", tmp_path)                                            # every socket is forbidden in that process
    # seven answers are re-derived byte for byte; the eighth fetch (a page off the outlet's
    # origin, never a document) had no extraction yet and gets its first one — beside the others
    assert out == {"files": 4, "preserved_files_unchanged": True, "replayed": {"ALREADY_STORED": 7, "STORED": 1}}
    after = child("state", tmp_path)["layers"]
    assert set(layers) < set(after) and len(after) == len(layers) + 1          # nothing replaced, one added
    assert child("replay", tmp_path)["replayed"] == {"ALREADY_STORED": 8}


# --- the writer lock: held by a living process, released by a dead one -----------------------------


def test_a_second_process_is_refused_while_one_writes_and_admitted_when_it_has_died(tmp_path):
    holder = start("hold", tmp_path)
    while not (tmp_path / "AT_CRASHPOINT").exists():
        assert holder.poll() is None
    with pytest.raises(ChildFailed, match="WorkspaceBusy"):
        child("pipeline", tmp_path)                                            # refused at once, nothing written
    assert not (tmp_path / "workspace" / "ledgers").exists()
    holder.kill()
    holder.wait(timeout=30)
    assert child("pipeline", tmp_path)["results"] == 8                         # no stale lock: the system released it
