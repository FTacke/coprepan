"""Concurrent writers, as real processes started at the same instant (decision CPD-0009).

For each component: what actually happens when two or three processes do the same thing at once.
The question is never "is it fast" but "can a record be lost, a wrong success be reported, or a
store be left contradicting itself". Measured before the repairs of 2026-10-08 on this platform:
600 ledger transitions reported and 389 on disk; 900 table rows reported and 597 on disk; 120
conflicting layer answers all reported as stored and every slot unreadable afterwards.

Semantics asserted here:

==============================  ====================================================================
ledger (one object per process)  explicit conflict: one writer proceeds, a stale one is refused; no loss
append-only table                safe serialisation: every row of every writer is on disk
layer store, same answer         idempotent duplicate
layer store, different answers   explicit conflict: at most one answer stays, the others are told
promotion of one object          idempotent duplicate, or an explicit I/O error; never two masters
pipeline on one workspace        safe serialisation by the writer lock, or an explicit refusal
fetch plan                       pure: two planners give the same plan
==============================  ====================================================================
"""

import hashlib
from collections import Counter

from coprepan import jsonl, layer_store, preservation
from coprepan.ledger import PRESERVATION, Ledger
from support_processes import child, race

WORKERS = 3


def errors_of(results):
    return Counter(name for result in results for name, count in result["errors"].items() for _ in range(count))


def outcomes_of(results):
    return Counter(name for result in results for name, count in result["outcomes"].items() for _ in range(count))


def test_ledger_writers_cannot_lose_or_duplicate_a_record(tmp_path):
    results = race("ledger", tmp_path, WORKERS)
    book = Ledger(tmp_path / "ledger.jsonl", PRESERVATION)            # readable: no duplicate sequence number, no garbage
    reported = sum(result["ok"] for result in results)
    assert reported == len(book) > 0                                  # every reported transition is on disk, and nothing else
    assert set(errors_of(results)) <= {"LedgerError"}                 # a stale writer is refused, explicitly
    assert reported + sum(errors_of(results).values()) == WORKERS * 150


def test_table_appends_of_several_processes_are_all_on_disk(tmp_path):
    results = race("table", tmp_path, WORKERS)
    rows = jsonl.read_rows(tmp_path / "t.jsonl", "coprepan-x/v1")
    assert errors_of(results) == Counter() and len(rows) == WORKERS * 150
    assert Counter(row["w"] for row in rows) == {number: 150 for number in range(WORKERS)}
    assert all([row["i"] for row in rows if row["w"] == number] == list(range(150)) for number in range(WORKERS))


def test_the_same_layer_answer_from_several_processes_is_stored_once(tmp_path):
    results = race("layer_same", tmp_path, WORKERS)
    assert errors_of(results) == Counter()
    assert outcomes_of(results) == {"STORED": 25, "ALREADY_STORED": 25 * (WORKERS - 1)}
    store = layer_store.LayerStore(tmp_path)
    for number in range(25):
        fingerprint = layer_store.fingerprint("extraction", "x/1", {"body": hashlib.sha256(str(number).encode()).hexdigest()})
        assert store.read("extraction", fingerprint) == b"same answer"


def test_different_layer_answers_for_one_fingerprint_never_both_stay(tmp_path):
    results = race("layer_conflict", tmp_path, WORKERS)
    assert set(errors_of(results)) <= {"FingerprintConflict"} and "ALREADY_STORED" not in outcomes_of(results)
    store, answered = layer_store.LayerStore(tmp_path), 0
    for number in range(25):
        fingerprint = layer_store.fingerprint("extraction", "x/1", {"body": hashlib.sha256(str(number).encode()).hexdigest()})
        held = store.get("extraction", fingerprint)                   # never raises: no slot holds two answers
        if held is not None:
            assert store.read("extraction", fingerprint).startswith(b"answer of worker ")
            answered += 1
    assert outcomes_of(results)["STORED"] == answered                 # exactly the answers that stayed were reported as stored
    assert sum(errors_of(results).values()) == WORKERS * 25 - answered  # and every other writer was told
    assert len(list((tmp_path / ".staging").glob("withdrawn-*"))) >= sum(errors_of(results).values()) - (WORKERS - 1) * 25


def test_promoting_one_object_from_several_processes_gives_one_verified_master(tmp_path):
    (tmp_path / "root").mkdir()
    (tmp_path / "source.bin").write_bytes(b"m" * 2_000_000)
    results = race("promote", tmp_path, WORKERS)
    assert set(outcomes_of(results)) <= {"promoted", "already_preserved", "repaired"}
    assert set(errors_of(results)) <= {"PreservationError"}           # an I/O refusal while another process holds the file: explicit
    assert preservation.verify_master(tmp_path / "root", "raw", "the-object")
    assert list((tmp_path / "root").rglob("*.part-*")) == []          # every loser removed its own staging file
    assert len(list((tmp_path / "root" / "preservation" / "raw").rglob("*.bin"))) == 1


def test_one_identity_offered_with_different_content_by_several_processes_is_bound_once(tmp_path):
    """Two workspaces that built the same pack id from different bytes, promoting at the same
    instant. Before 2026-10-08 two or three of them were told "promoted" in 8 rounds of 8, and in
    one round the surviving master did not fit its manifest.
    """
    (tmp_path / "root").mkdir()
    for number in range(WORKERS):
        (tmp_path / f"source{number}.bin").write_bytes(bytes([65 + number]) * 2_000_000)
    results = race("promote_conflict", tmp_path, WORKERS)
    winners = [result for result in results if result["ok"]]
    assert len(winners) == 1 and winners[0]["outcomes"] == {"promoted": 1}
    assert set(errors_of(results)) <= {"IdentityConflict", "PreservationError"}   # every other writer was refused
    manifest = preservation.read_manifest(tmp_path / "root", "raw", "the-object")
    assert manifest["sha256"] == winners[0]["sha256"] and preservation.verify_master(tmp_path / "root", "raw", "the-object")
    assert list((tmp_path / "root").rglob("*.part-*")) == []


def test_one_workspace_started_twice_ends_as_one_run(tmp_path):
    reference = tmp_path / "reference"
    child("pipeline", reference)
    expected = child("state", reference)
    results = race("pipeline", tmp_path / "raced", WORKERS)
    assert any(result["ok"] for result in results)
    assert set(errors_of(results)) <= {"WorkspaceBusy"}               # whoever did not get the lock was refused, not half-admitted
    state = child("state", tmp_path / "raced")
    assert {key: state[key] for key in ("ledger", "identity", "layers", "masters")} == \
           {key: expected[key] for key in ("ledger", "identity", "layers", "masters")}
    assert state["orphans"]["torn_sidecars"] == []


def test_two_planners_over_one_history_give_the_same_plan(tmp_path):
    child("http", tmp_path)
    first, second = (result["plan"] for result in race("plan", tmp_path, 2))
    assert first == second and len(first) == 7                         # a plan is a reading; it writes nothing and competes for nothing
