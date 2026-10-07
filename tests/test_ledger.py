"""State-machine and ledger primitives: ledger before state, illegal transitions raise."""

import hashlib
import json
from datetime import datetime, timezone

import pytest

from coprepan import ledger as L
from coprepan.ledger import PRESERVATION, IllegalTransition, Ledger, LedgerError, LedgerTornTail

AT = datetime(2026, 10, 7, 19, 0, 0, tzinfo=timezone.utc)
HAPPY_PATH = ["DISCOVERED", "FETCH_PLANNED", "FETCHED", "RAW_VERIFIED", "PRESERVATION_PENDING", "RAW_PRESERVED"]


def walk(ledger, subject, states):
    for state in states:
        ledger.transition(subject, state, at=AT)


# --- machine --------------------------------------------------------------------------------------


def test_preservation_machine_has_the_documented_states():
    assert set(PRESERVATION.states) == set(HAPPY_PATH) | {"FETCH_FAILED", "REFUSED_BY_POLICY", "QUARANTINED"}
    assert PRESERVATION.initial == "DISCOVERED"
    assert PRESERVATION.is_terminal("RAW_PRESERVED") and not PRESERVATION.is_terminal("FETCH_FAILED")


def test_every_undeclared_transition_raises():
    for current in PRESERVATION.states:
        for target in PRESERVATION.states:
            if target in PRESERVATION.transitions[current]:
                PRESERVATION.check(current, target)
            else:
                with pytest.raises(IllegalTransition):
                    PRESERVATION.check(current, target)


def test_pending_is_not_preserved_and_cannot_be_skipped():
    with pytest.raises(IllegalTransition):
        PRESERVATION.check("RAW_VERIFIED", "RAW_PRESERVED")
    with pytest.raises(IllegalTransition):
        PRESERVATION.check("FETCHED", "RAW_PRESERVED")


def test_a_subject_starts_in_the_initial_state_only():
    PRESERVATION.check(None, "DISCOVERED")
    with pytest.raises(IllegalTransition):
        PRESERVATION.check(None, "FETCHED")


def test_unknown_states_are_not_free_text():
    with pytest.raises(L.StateMachineError):
        PRESERVATION.check("DISCOVERED", "fetched")
    with pytest.raises(L.StateMachineError):
        PRESERVATION.check("ok", "FETCHED")


@pytest.mark.parametrize(
    "initial, transitions",
    [
        ("A", {"A": ("B",)}),            # transition into an undeclared state
        ("C", {"A": (), "B": ()}),       # undeclared initial state
        ("a", {"a": ()}),                # not an upper-case token
        ("A", {"A": ("free text",), "free text": ()}),
    ],
)
def test_inconsistent_machines_are_refused(initial, transitions):
    with pytest.raises(L.StateMachineError):
        L.machine("broken", initial, transitions)


# --- ledger ---------------------------------------------------------------------------------------


def test_transitions_are_recorded_and_replayed(tmp_path):
    path = tmp_path / "state" / "ledger.jsonl"
    ledger = Ledger(path, PRESERVATION)
    assert ledger.state("f1") is None
    walk(ledger, "f1", HAPPY_PATH)
    walk(ledger, "f2", ["DISCOVERED", "FETCH_PLANNED", "FETCH_FAILED", "FETCH_PLANNED"])
    assert ledger.state("f1") == "RAW_PRESERVED" and ledger.state("f2") == "FETCH_PLANNED"

    reopened = Ledger(path, PRESERVATION)
    assert reopened.states() == ledger.states() and len(reopened) == 10
    assert [record.seq for record in reopened.records()] == list(range(10))


def test_record_format_is_pinned(tmp_path):
    path = tmp_path / "ledger.jsonl"
    book = Ledger(path, PRESERVATION)
    book.transition("f1", "DISCOVERED", at=AT, details={"channel": "uy_el_pais:ch:rss_001"})
    first = (
        b'{"at": "2026-10-07T19:00:00.000000Z", "details": {"channel": "uy_el_pais:ch:rss_001"}, '
        b'"machine": "preservation", "new_state": "DISCOVERED", "previous_record_sha256": null, "previous_state": null, '
        b'"schema": "coprepan-ledger-record/v2", "seq": 0, "subject": "f1"}\n'
    )
    assert path.read_bytes() == first
    book.transition("f1", "FETCH_PLANNED", at=AT)
    second = json.loads(path.read_bytes().split(b"\n")[1])
    assert second["previous_record_sha256"] == hashlib.sha256(first).hexdigest()      # each record names the one before it


def test_a_changed_record_is_detected_by_the_record_after_it(tmp_path):
    path = tmp_path / "ledger.jsonl"
    walk(Ledger(path, PRESERVATION), "f1", HAPPY_PATH[:4])
    lines = path.read_bytes().split(b"\n")
    lines[1] = lines[1].replace(b"19:00:00", b"19:00:01")                     # one digit of a timestamp: still a valid record
    path.write_bytes(b"\n".join(lines))
    with pytest.raises(LedgerError, match="does not follow the record before it"):
        Ledger(path, PRESERVATION)
    old = tmp_path / "v1.jsonl"                                                # a record of the superseded format is not read as v2
    old.write_bytes(b'{"at": "x", "details": {}, "machine": "preservation", "new_state": "DISCOVERED", "previous_state": null, '
                    b'"schema": "coprepan-ledger-record/v1", "seq": 0, "subject": "f1"}\n')
    with pytest.raises(LedgerError, match="coprepan-ledger-record/v1"):
        Ledger(old, PRESERVATION)


def test_same_transitions_give_the_same_bytes(tmp_path):
    for name in ("a.jsonl", "b.jsonl"):
        walk(Ledger(tmp_path / name, PRESERVATION), "f1", HAPPY_PATH)
    assert (tmp_path / "a.jsonl").read_bytes() == (tmp_path / "b.jsonl").read_bytes()


def test_an_illegal_transition_raises_and_leaves_no_trace(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = Ledger(path, PRESERVATION)
    walk(ledger, "f1", ["DISCOVERED", "FETCH_PLANNED"])
    before = path.read_bytes()
    with pytest.raises(IllegalTransition):
        ledger.transition("f1", "RAW_PRESERVED", at=AT)
    with pytest.raises(IllegalTransition):
        ledger.transition("new", "FETCHED", at=AT)
    assert path.read_bytes() == before and ledger.state("f1") == "FETCH_PLANNED" and ledger.state("new") is None


def test_ledger_is_written_before_the_state_changes(tmp_path, monkeypatch):
    ledger = Ledger(tmp_path / "ledger.jsonl", PRESERVATION)
    ledger.transition("f1", "DISCOVERED", at=AT)

    def fail(line):
        raise OSError("disk full")

    monkeypatch.setattr(ledger, "_append", fail)
    with pytest.raises(OSError):
        ledger.transition("f1", "FETCH_PLANNED", at=AT)
    assert ledger.state("f1") == "DISCOVERED"  # no record, no state change


def test_a_naive_timestamp_is_refused(tmp_path):
    with pytest.raises(ValueError):
        Ledger(tmp_path / "ledger.jsonl", PRESERVATION).transition("f1", "DISCOVERED", at=datetime(2026, 1, 1))


def rewrite(path, edit):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    edit(rows)
    path.write_bytes("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode("utf-8"))


@pytest.mark.parametrize(
    "edit",
    [
        lambda rows: rows.pop(1),                                    # a record removed
        lambda rows: rows.reverse(),                                 # reordered
        lambda rows: rows[2].update(new_state="RAW_PRESERVED"),     # an illegal transition written in
        lambda rows: rows[1].update(previous_state="FETCHED"),      # a false previous state
        lambda rows: rows[0].update(machine="other"),               # another machine's ledger
        lambda rows: rows[0].pop("subject"),                        # a field missing
    ],
)
def test_an_edited_ledger_is_refused_not_believed(tmp_path, edit):
    path = tmp_path / "ledger.jsonl"
    walk(Ledger(path, PRESERVATION), "f1", HAPPY_PATH[:4])
    rewrite(path, edit)
    with pytest.raises(LedgerError):
        Ledger(path, PRESERVATION)


# --- crash recovery (robustness) -------------------------------------------------------------------


def test_a_torn_last_line_is_detected_and_quarantined_not_dropped(tmp_path):
    path = tmp_path / "ledger.jsonl"
    walk(Ledger(path, PRESERVATION), "f1", HAPPY_PATH[:3])
    intact = path.read_bytes()
    torn = b'{"at": "2026-10-07T19:00:00.000000Z", "deta'
    path.write_bytes(intact + torn)

    with pytest.raises(LedgerTornTail):
        Ledger(path, PRESERVATION)

    sidecar = L.quarantine_torn_tail(path)
    assert sidecar.read_bytes() == torn and path.read_bytes() == intact
    recovered = Ledger(path, PRESERVATION)
    assert recovered.state("f1") == "FETCHED"
    recovered.transition("f1", "RAW_VERIFIED", at=AT)
    assert Ledger(path, PRESERVATION).state("f1") == "RAW_VERIFIED"
    assert L.quarantine_torn_tail(path) is None  # intact: nothing to do


def test_a_second_torn_tail_gets_its_own_sidecar(tmp_path):
    path = tmp_path / "ledger.jsonl"
    walk(Ledger(path, PRESERVATION), "f1", HAPPY_PATH[:2])
    for expected in ("ledger.jsonl.torn-0", "ledger.jsonl.torn-1"):
        path.write_bytes(path.read_bytes() + b"{half")
        assert L.quarantine_torn_tail(path).name == expected
    assert sorted(p.name for p in tmp_path.iterdir()) == ["ledger.jsonl", "ledger.jsonl.torn-0", "ledger.jsonl.torn-1"]


def test_appending_after_a_torn_tail_is_refused(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = Ledger(path, PRESERVATION)
    ledger.transition("f1", "DISCOVERED", at=AT)
    path.write_bytes(path.read_bytes() + b"{half")
    with pytest.raises(LedgerTornTail):
        ledger.transition("f1", "FETCH_PLANNED", at=AT)
    assert ledger.state("f1") == "DISCOVERED"
