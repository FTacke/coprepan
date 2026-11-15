"""The incremental workspace check (CPD-0037): it checks only what is new, and it never answers CLEAN where the full audit
(``recovery.diagnose``) would not.

Every fault below is injected **after** a verified point, into data an incremental check must read, and the check must end
in the full audit's classification. The one documented boundary -- an in-place change of an old, unchanged, verified object
that keeps its size -- is shown too: found by the rotating audit when it comes round, and by the full audit when it is due.
Offline, temporary directories on the local disk.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timedelta, timezone

import pytest

from coprepan import incremental_check as I, pack, recovery
from coprepan.canonical import sha256_bytes
from coprepan.jsonl import CHAIN_FIELD
from test_canary_driver import Drive, site  # noqa: F401  (the loopback outlet fixture)
from test_evidence_integrity import built, built_canary, clone  # noqa: F401  (module-scoped fixtures)

T0 = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def world(tmp_path, built):  # noqa: F811
    return clone(tmp_path, *built)


@pytest.fixture
def iworld(tmp_path, built_canary):  # noqa: F811
    return clone(tmp_path, *built_canary)


def verified(root, now=T0):
    diagnosis, state = I.checkpoint(root, now=now)
    assert diagnosis["check"]["mode"] == "full" and state.valid
    return state


def again(root, state=None, now=T0 + timedelta(minutes=5), **kw):
    return I.checkpoint(root, state, now=now, **kw)


def lines(path):
    return path.read_bytes().split(b"\n")[:-1]


def append_chained_row(path, row):
    previous = lines(path)[-1] + b"\n"
    row = dict(row)
    row[CHAIN_FIELD] = sha256_bytes(previous)
    with open(path, "ab") as handle:
        handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n")


# --- agreement with the full audit -------------------------------------------------------------------------------


@pytest.mark.parametrize("which", ["world", "iworld"])
def test_a_verified_point_then_an_incremental_check_agrees_with_the_full_audit(which, request):
    w = request.getfixturevalue(which)
    root = w.workspace.root
    full = recovery.diagnose(root)
    state = verified(root)
    diagnosis, state = again(root, state)
    assert diagnosis["check"]["mode"] == "incremental"
    assert diagnosis["classification"] == full["classification"]
    scope = diagnosis["check"]["scope"]
    assert scope["packs_new"] == 0 and scope["packs_skipped_as_verified"] >= 1 and scope["new_lines"] == 0
    assert recovery.diagnose(root)["classification"] == full["classification"]       # the state file breaks nothing


def test_a_new_process_continues_from_the_persisted_state_without_a_full_audit(world):
    root = world.workspace.root
    verified(root)
    diagnosis, state = again(root, None)                   # loaded from checks/verified-0.state
    assert diagnosis["check"]["mode"] == "incremental" and state.valid


def test_the_full_audit_is_repeated_when_it_is_older_than_a_week(world):
    root = world.workspace.root
    state = verified(root)
    diagnosis, _ = again(root, state, now=T0 + I.FULL_EVERY + timedelta(minutes=1))
    assert diagnosis["check"]["mode"] == "full" and "older than" in diagnosis["check"]["why"]


@pytest.mark.parametrize("damage", ["garbage", "torn", "foreign_version"])
def test_an_unreadable_check_state_only_means_a_full_audit(world, damage):
    root = world.workspace.root
    verified(root)
    path = root / "checks" / "verified-0.state"
    if damage == "garbage":
        path.write_bytes(b"not a state\n")
    elif damage == "torn":
        with open(path, "ab") as handle:
            handle.write(b'{"half')
    else:
        rows = lines(path)
        row = json.loads(rows[0])
        row["check_version"] = "incremental-check/0"
        path.write_bytes(json.dumps(row).encode() + b"\n")
    diagnosis, state = again(root, None)
    # a damaged cache is never damage of the workspace: a full audit, a new state file, the old one kept as it is
    assert diagnosis["check"]["mode"] == "full" and state.valid
    assert diagnosis["classification"] in (recovery.CLEAN, recovery.RESUMABLE)
    assert path.exists() and (root / "checks" / "verified-1.state").exists()


def test_a_check_state_extended_by_another_process_is_not_extended_again(world):
    root = world.workspace.root
    mine = verified(root)
    other = I.load(root)
    again(root, other)                                      # the other process appends first
    diagnosis, mine = again(root, mine)
    assert not mine.valid and "another process" in mine.reason
    assert I.load(root).valid                               # the file itself stays one valid chain


# --- faults after the verified point: the full audit's classification ------------------------------------------------


def expect_full(root, state, classification):
    diagnosis, state = again(root, state)
    assert diagnosis["check"]["mode"] == "full", diagnosis["check"]
    assert diagnosis["classification"] == classification == recovery.diagnose(root)["classification"]
    return diagnosis


@pytest.mark.parametrize("relative", ["requests/requests.jsonl", "discovery/events.jsonl", "ledgers/preservation.jsonl"])
def test_a_torn_tail_after_the_verified_point_needs_repair(world, relative):
    root = world.workspace.root
    state = verified(root)
    with open(root / relative, "ab") as handle:
        handle.write(b'{"half a row')
    expect_full(root, state, recovery.NEEDS_REPAIR)


@pytest.mark.parametrize("relative", ["requests/requests.jsonl", "discovery/events.jsonl", "discovery/inputs.jsonl"])
def test_a_new_row_that_does_not_follow_the_chain_is_damage(world, relative):
    root = world.workspace.root
    state = verified(root)
    row = json.loads(lines(root / relative)[-1])
    with open(root / relative, "ab") as handle:            # names a row that is not the one before it
        handle.write(json.dumps({**row, CHAIN_FIELD: "0" * 64}, sort_keys=True).encode() + b"\n")
    expect_full(root, state, recovery.DAMAGED)


@pytest.mark.parametrize("relative", ["requests/requests.jsonl", "discovery/events.jsonl", "ledgers/preservation.jsonl"])
def test_a_change_of_the_last_verified_row_is_found_by_its_anchor(world, relative):
    root = world.workspace.root
    state = verified(root)
    items = lines(root / relative)
    text = items[-1].decode()
    index = max(i for i, c in enumerate(text) if c.isdigit())
    items[-1] = (text[:index] + str((int(text[index]) + 1) % 10) + text[index + 1:]).encode()
    (root / relative).write_bytes(b"".join(i + b"\n" for i in items))
    expect_full(root, state, recovery.DAMAGED)


def test_a_table_cut_below_its_verified_size_is_found(world):
    root = world.workspace.root
    state = verified(root)
    path = root / "requests" / "requests.jsonl"
    path.write_bytes(b"".join(i + b"\n" for i in lines(path)[:-2]))
    expect_full(root, state, recovery.DAMAGED)


def test_a_duplicate_event_with_a_valid_chain_is_found(world):
    """``doppelte Events``: an event id written a second time as a different row, chained correctly."""
    root = world.workspace.root
    state = verified(root)
    path = root / "discovery" / "events.jsonl"
    first = json.loads(lines(path)[0])
    first["observed_at"] = "2026-11-15T12:00:00.000000Z"
    append_chained_row(path, first)
    expect_full(root, state, recovery.DAMAGED)


def test_a_verified_pack_that_is_gone_is_lost_evidence(world):
    root = world.workspace.root
    state = verified(root)
    identifier = next(iter(state.packs))
    for path in (root / "packs").glob(f"{identifier}.*"):
        path.unlink()
    expect_full(root, state, recovery.DAMAGED)


def test_a_new_sealed_pack_that_does_not_verify_is_found(iworld):
    """A pack sealed after the verified point is verified in full before it is believed."""
    root = iworld.workspace.root
    state = verified(root)
    identifier = next(iter(state.packs))
    del state.packs[identifier]                              # as if it had been sealed after the verified point
    sealed = root / "packs" / f"{identifier}.warc.gz"
    data = bytearray(sealed.read_bytes())
    data[len(data) // 2] ^= 0xFF
    sealed.write_bytes(bytes(data))
    diagnosis, _ = again(root, state)
    assert diagnosis["check"]["mode"] == "full" and diagnosis["classification"] == recovery.DAMAGED


def flip_keeping_size_and_time(path):
    info = path.stat()
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    path.write_bytes(bytes(data))
    os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))


def test_the_documented_boundary_an_old_pack_changed_in_place_is_found_by_the_audit_not_the_fast_path(iworld):
    root = iworld.workspace.root
    state = verified(root)
    identifier = sorted(state.packs)[0]
    flip_keeping_size_and_time(root / "packs" / f"{identifier}.warc.gz")
    quiet, state = again(root, state, audit=I.AuditBudget(packs=0, layers=0))
    assert quiet["check"]["mode"] == "incremental"          # not visible without a re-read: the boundary, stated
    found, _ = again(root, state, audit=I.AuditBudget(packs=len(state.packs), pack_bytes=1 << 40))
    assert found["check"]["mode"] == "full" and found["classification"] == recovery.DAMAGED


def test_the_rotating_audit_comes_round_to_every_verified_pack(iworld):
    root = iworld.workspace.root
    state = verified(root)
    seen = set()
    now = T0
    for _ in range(len(state.packs) + 1):
        now += timedelta(minutes=1)
        diagnosis, state = again(root, state, now=now, audit=I.AuditBudget(packs=1, layers=1))
        assert diagnosis["check"]["mode"] == "incremental"
        seen |= {i for i, entry in state.packs.items() if entry["audited_at"] == I.format_instant(now)}
    assert seen == set(state.packs)


def test_a_layer_answer_that_no_longer_verifies_is_found_by_the_audit(iworld):
    root = iworld.workspace.root
    state = verified(root)
    key = sorted(state.layers)[0]
    stage, fingerprint = key.split("/")
    slot = root / "layers" / stage / fingerprint[:2] / fingerprint
    payload = next(slot.iterdir()) / "payload"
    flip_keeping_size_and_time(payload)
    found, _ = again(root, state, audit=I.AuditBudget(packs=0, layers=len(state.layers)))
    assert found["check"]["mode"] == "full" and found["classification"] == recovery.DAMAGED


def test_an_unsupported_candidate_row_is_damage(world):
    root = world.workspace.root
    state = verified(root)
    path = root / "discovery" / "candidates.jsonl"
    row = json.loads(lines(path)[0])
    row["candidate_id"] = row["candidate_id"][:-4] + "beef"
    with open(path, "ab") as handle:
        handle.write(json.dumps(row, sort_keys=True).encode() + b"\n")
    expect_full(root, state, recovery.DAMAGED)


def test_a_ledger_transition_that_does_not_fit_is_damage(world):
    root = world.workspace.root
    state = verified(root)
    path = root / "ledgers" / "preservation.jsonl"
    last = json.loads(lines(path)[-1])
    row = {**last, "seq": last["seq"] + 1, "previous_state": None, "new_state": "RAW_PRESERVED",
           "previous_record_sha256": sha256_bytes(lines(path)[-1] + b"\n")}
    with open(path, "ab") as handle:
        handle.write(json.dumps(row, sort_keys=True).encode() + b"\n")
    expect_full(root, state, recovery.DAMAGED)


def test_an_interrupted_request_after_the_verified_point_is_resumable(world):
    root = world.workspace.root
    state = verified(root)
    path = root / "requests" / "requests.jsonl"
    planned = next(json.loads(line) for line in lines(path) if json.loads(line)["event"] == "PLANNED")
    planned = {k: v for k, v in planned.items() if k != CHAIN_FIELD}
    planned["request_id"] = planned["request_id"][:-4] + "abcd"
    planned["url"] = planned["url"] + "?never-ended"
    append_chained_row(path, planned)
    diagnosis, _ = again(root, state)
    assert diagnosis["check"]["mode"] == "incremental"
    assert diagnosis["classification"] == recovery.RESUMABLE == recovery.diagnose(root)["classification"]
    assert any("no end on record" in r for r in diagnosis["resumable"])


def test_a_canary_run_checks_fully_once_and_incrementally_after_and_agrees_with_the_full_audit(tmp_path, site, monkeypatch):  # noqa: F811
    """canary-driver/8: the checkpoints of a growing workspace -- discovery, items, packs, preservation, derivation."""
    from coprepan import canary_driver as D
    calls = {"full": 0}
    real = recovery.diagnose
    monkeypatch.setattr(recovery, "diagnose", lambda *a, **k: (calls.__setitem__("full", calls["full"] + 1), real(*a, **k))[1])
    run = Drive(tmp_path / "grow", site)
    outcome = run.go()
    modes = [c["check"] for c in outcome["checkpoints"]]
    assert modes[0] == "full" and set(modes[1:]) == {"incremental"} and len(modes) >= 3, outcome["checkpoints"]
    assert calls["full"] == 1
    last = outcome["checkpoints"][-1]["classification"]
    assert real(run.workspace.root)["classification"] == last
    diagnosis, _ = I.checkpoint(run.workspace.root, now=datetime.now(timezone.utc))       # a new process, after the run
    assert diagnosis["check"]["mode"] == "incremental" and diagnosis["classification"] == real(run.workspace.root)["classification"]


def test_the_held_request_log_reads_only_what_is_appended_and_refuses_what_does_not_follow(world):
    from coprepan import http_acquisition as H
    from coprepan.jsonl import ChainBroken, JsonlError
    log = H.RequestLog(world.workspace)
    assert log.rows() == H.request_rows(world.workspace)
    path = H.request_log_path(world.workspace)
    planned = next(json.loads(line) for line in lines(path) if json.loads(line)["event"] == "PLANNED")
    planned = {k: v for k, v in planned.items() if k != CHAIN_FIELD}
    append_chained_row(path, {**planned, "request_id": planned["request_id"][:-4] + "beef"})
    assert log.rows() == H.request_rows(world.workspace)                          # the tail only, and the same rows
    with open(path, "ab") as handle:
        handle.write(json.dumps({**planned, CHAIN_FIELD: "0" * 64}).encode() + b"\n")
    with pytest.raises(ChainBroken):
        log.rows()
    path.write_bytes(b"".join(i + b"\n" for i in lines(path)[:3]))
    with pytest.raises(JsonlError):
        H.RequestLog(world.workspace).rows() and log.rows()


def test_a_held_ledger_is_brought_up_to_date_with_what_another_ledger_object_appended(world):
    from coprepan import ledger as L
    held, other = world.workspace.ledger(), world.workspace.ledger()
    subject = "ft1:" + "a" * 64
    other.transition(subject, "DISCOVERED")
    other.transition(subject, "FETCH_PLANNED")
    assert held.state(subject) is None and held.refresh() == 2 and held.state(subject) == "FETCH_PLANNED"
    held.transition(subject, "FETCH_FAILED")                                       # it appends where the file ends
    assert world.workspace.ledger().states() == held.states()
    path = world.workspace.ledger_path
    row = json.loads(lines(path)[-1])
    with open(path, "ab") as handle:
        handle.write(json.dumps({**row, "seq": row["seq"] + 1, "previous_record_sha256": "0" * 64}).encode() + b"\n")
    with pytest.raises(L.LedgerError):
        held.refresh()


def test_nothing_new_reads_no_pack_and_no_layer(iworld, monkeypatch):
    root = iworld.workspace.root
    state = verified(root)
    calls = {"verify": 0, "scan": 0}
    real_verify, real_scan = pack.verify_sealed, pack.scan
    monkeypatch.setattr(pack, "verify_sealed", lambda *a, **k: (calls.__setitem__("verify", calls["verify"] + 1), real_verify(*a, **k))[1])
    monkeypatch.setattr(pack, "scan", lambda *a, **k: (calls.__setitem__("scan", calls["scan"] + 1), real_scan(*a, **k))[1])
    diagnosis, _ = again(root, state, audit=I.AuditBudget(packs=0, layers=0))
    assert diagnosis["check"]["mode"] == "incremental" and calls == {"verify": 0, "scan": diagnosis["check"]["scope"]["packs_open_scanned"]}
