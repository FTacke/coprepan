"""CPD-0033: CO.PRE.PAN's shared I/O is bounded, yields to CO.RA.PAN, and its regular cycles make no full-tree reads.

Every claim is exercised on temporary directories (no share, no network beyond the loopback outlet of the intake bench). Reads
of the "preservation root" are counted by instrumenting the functions that touch it; the counts are the evidence, not a timing.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from coprepan import core_pipeline as C
from coprepan import preservation, preservation_migration as M, preservation_target, preserved_index
from coprepan import primary_backup as B
from coprepan import resource_policy as R
from coprepan import storage_roots

REPO = Path(__file__).resolve().parents[1]
NOON = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)                     # a Monday, outside every quiet window


def policy(**overrides) -> R.ResourcePolicy:
    doc = json.loads((REPO / "config" / "resource_policy.json").read_text(encoding="utf-8"))
    for dotted, value in overrides.items():
        section, key = dotted.split("__")
        doc[section][key] = value
    return R.parse_policy(doc)


@pytest.fixture(autouse=True)
def _fresh_cache_memory():
    preserved_index.reset_memory()
    yield
    preserved_index.reset_memory()


# --- the policy ------------------------------------------------------------------------------------------------


def test_the_tracked_policy_is_decided_and_parses():
    tracked = R.load_policy(REPO / "config" / "resource_policy.json")
    assert tracked.version and tracked.backup["workers"] == 1 and tracked.free_space_floor_bytes["RUNTIME"] >= 50 * R.GIB
    with pytest.raises(R.ResourcePolicyError):
        R.parse_policy({**json.loads((REPO / "config" / "resource_policy.json").read_text(encoding="utf-8")), "status": "PROPOSED"})


@pytest.mark.parametrize("local, quiet", [
    (datetime(2026, 11, 18, 2, 0), True),       # Wednesday 02:00: CO.RA.PAN's backup reconcile
    (datetime(2026, 11, 18, 8, 0), False),
    (datetime(2026, 11, 15, 5, 0), True),       # Sunday 05:00: CO.RA.PAN's historic backup
    (datetime(2026, 11, 16, 3, 40), True),      # every day 03:15-04:30: CO.RA.PAN's local storage maintenance
    (datetime(2026, 11, 16, 4, 45), True),      # Monday 04:45: a reconcile that is continued or overdue runs in any night window (CPD-0035)
    (datetime(2026, 11, 16, 8, 0), False),      # Monday 08:00: CO.PRE.PAN's scheduled start is free
    (datetime(2026, 7, 15, 7, 50), False),      # summer time: the wall clock of Europe/Berlin, not UTC
    (datetime(2026, 7, 15, 7, 40), True),
])
def test_quiet_windows_are_on_the_wall_clock_of_europe_berlin(local, quiet):
    moment = R.from_local(local.date(), local.time())
    assert (policy().quiet_window(moment) is not None) == quiet


# --- the maintenance calendar (CPD-0035) ---------------------------------------------------------------------------


def test_the_local_time_follows_the_eu_summer_time_rule_and_agrees_with_the_time_zone_database():
    assert R.local_time(datetime(2026, 3, 29, 0, 59, tzinfo=timezone.utc)).utcoffset() == timedelta(hours=1)
    assert R.local_time(datetime(2026, 3, 29, 1, 0, tzinfo=timezone.utc)).utcoffset() == timedelta(hours=2)
    assert R.local_time(datetime(2026, 10, 25, 0, 59, tzinfo=timezone.utc)).utcoffset() == timedelta(hours=2)
    assert R.local_time(datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc)).utcoffset() == timedelta(hours=1)
    zoneinfo = pytest.importorskip("zoneinfo")
    try:
        berlin = zoneinfo.ZoneInfo("Europe/Berlin")
    except Exception:                                                  # no time-zone data on this machine: the rule stands alone
        pytest.skip("no time-zone database to compare with")
    moment = datetime(2025, 1, 1, tzinfo=timezone.utc)
    while moment < datetime(2029, 1, 1, tzinfo=timezone.utc):
        assert R.local_time(moment).utcoffset() == moment.astimezone(berlin).utcoffset(), moment
        moment += timedelta(hours=7)
    for day in (datetime(2026, 3, 30).date(), datetime(2026, 10, 26).date(), datetime(2026, 11, 16).date()):
        assert R.from_local(day, datetime(2000, 1, 1, 8, 0).time()).astimezone(berlin).strftime("%H:%M") == "08:00"


@pytest.mark.parametrize("local, outcome", [
    (datetime(2026, 11, 14, 8, 0), R.SCHEDULED_PAUSE),           # Saturday
    (datetime(2026, 11, 15, 12, 0), R.SCHEDULED_PAUSE),          # Sunday noon: outside every window, still the weekend
    (datetime(2026, 11, 14, 0, 30), R.SCHEDULED_PAUSE),          # Saturday 00:30 local is Friday 23:30 UTC: the local day decides
    (datetime(2026, 3, 28, 23, 59), R.SCHEDULED_PAUSE),          # the night of the spring switch
    (datetime(2026, 11, 16, 8, 0), None),                        # Monday, the scheduled start
    (datetime(2026, 11, 20, 23, 59), None),                      # Friday late evening
    (datetime(2026, 11, 18, 3, 0), R.DEFERRED_RESOURCE_PRIORITY),  # Wednesday, CO.RA.PAN's night window
])
def test_no_automatic_maintenance_at_the_weekend_whatever_starts_the_process(tmp_path, local, outcome):
    hold = R.maintenance_hold(policy(), tmp_path, R.from_local(local.date(), local.time()), {})
    assert (hold[0] if hold else None) == outcome
    # the operator's explicit order overrides the calendar and the windows -- never the pause file or CO.RA.PAN's observation
    assert R.maintenance_hold(policy(), tmp_path, R.from_local(local.date(), local.time()), {}, calendar=False) is None
    slow = sibling(tmp_path, share_slow=True, last_probe_utc=R.from_local(local.date(), local.time()).isoformat())
    assert R.maintenance_hold(policy(), tmp_path, R.from_local(local.date(), local.time()), slow, calendar=False)[0] == R.DEFERRED_RESOURCE_PRIORITY


def test_the_calendar_counts_weekday_slots_and_none_at_the_weekend():
    calendar = policy().calendar
    friday = R.from_local(datetime(2026, 11, 20).date(), datetime(2000, 1, 1, 8, 5).time())          # Friday's backup at 08:05
    monday_morning = R.from_local(datetime(2026, 11, 23).date(), datetime(2000, 1, 1, 9, 0).time())
    assert calendar.missed(friday, monday_morning) == []          # 73 h later, and no slot is missed: Monday's run is not yet late
    tuesday_noon = R.from_local(datetime(2026, 11, 24).date(), datetime(2000, 1, 1, 12, 0).time())
    assert len(calendar.missed(friday, tuesday_noon)) == 2        # Monday's and Tuesday's slots passed without a backup
    assert calendar.next_slot(R.from_local(datetime(2026, 11, 21).date(), datetime(2000, 1, 1, 9, 0).time())) == \
        R.from_local(datetime(2026, 11, 23).date(), datetime(2000, 1, 1, 8, 0).time())


# --- CO.RA.PAN's priority for new preservation transfers (CPD-0035) ----------------------------------------------------


@pytest.mark.parametrize("fields, transfers_held, contact_held", [
    ({"mode": "RECOVERING", "verdict": {"owed": 171}}, True, False),
    ({"share_slow": True}, True, False),
    ({"reachable": False, "mode": "DEGRADED_LOCAL", "last_error_class": "AUTH_REFUSED"}, True, True),
    ({}, False, False),                                                           # NORMAL: within CO.PRE.PAN's own limits
])
def test_corapan_slow_or_recovering_holds_new_transfers_without_a_contact(tmp_path, fields, transfers_held, contact_held):
    env = sibling(tmp_path, **fields)
    if "verdict" in fields:
        fields["verdict"]["at"] = NOON.isoformat()
    gate = R.ShareGate(tmp_path / "rt", policy(), env=env, clock=Clock(NOON))
    contacts = []
    guarded = gate.guard(lambda: contacts.append(1) or tmp_path, transfer=True)
    assert (guarded.held() is not None) == transfers_held
    assert (gate.closed_because() is not None) == contact_held                    # reads (a finalizer's read-back) are another purpose
    if transfers_held:
        with pytest.raises(R.ShareBackingOff):
            guarded()
        assert contacts == []
    else:
        assert guarded() == tmp_path and contacts == [1]


@pytest.mark.parametrize("variable", ["", "absent.json", "garbage.json", "stale"])
def test_a_missing_unreadable_or_stale_signal_never_permits_more_than_the_policy(tmp_path, variable):
    env = {}
    if variable == "absent.json":
        env = {R.SIBLING_SIGNAL_VARIABLE: str(tmp_path / "absent.json")}
    elif variable == "garbage.json":
        (tmp_path / "garbage.json").write_text("{not json", encoding="utf-8")
        env = {R.SIBLING_SIGNAL_VARIABLE: str(tmp_path / "garbage.json")}
    elif variable == "stale":
        env = sibling(tmp_path, last_probe_utc=(NOON - timedelta(hours=3)).isoformat())
    gate = R.ShareGate(tmp_path / "rt", policy(), env=env, clock=Clock(NOON))
    # no signal is not "idle": the answer is the policy's own -- here, a Monday noon, transfers within the bounds, maintenance permitted
    assert gate.closed_because(transfer=True) is None
    saturday = NOON - timedelta(days=2)
    assert R.maintenance_hold(policy(), tmp_path, saturday, env)[0] == R.SCHEDULED_PAUSE
    R.pause_path(tmp_path / "rt").parent.mkdir(parents=True, exist_ok=True)
    R.pause_path(tmp_path / "rt").write_text("operator", encoding="utf-8")
    assert "PAUSE_IO" in gate.closed_because(transfer=True)


# --- the sibling advisory --------------------------------------------------------------------------------------


def sibling(tmp_path, **fields) -> dict[str, str]:
    doc = {"schema": R.SIBLING_SCHEMA, "reachable": True, "mode": "NORMAL", "share_slow": False, "last_probe_utc": NOON.isoformat(),
           "next_probe_after_utc": None, "last_error_class": None, **fields}
    path = tmp_path / "preservation_mode_state.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return {R.SIBLING_SIGNAL_VARIABLE: str(path)}


def test_the_sibling_signal_only_ever_makes_coprepan_more_careful(tmp_path):
    age = 1800
    assert R.sibling_advisory({}, NOON, max_age_seconds=age)["state"] == R.NO_SIGNAL
    assert R.sibling_advisory({R.SIBLING_SIGNAL_VARIABLE: str(tmp_path / "absent.json")}, NOON, max_age_seconds=age)["state"] == R.NO_SIGNAL
    assert R.sibling_advisory(sibling(tmp_path), NOON, max_age_seconds=age)["state"] == R.SHARE_NORMAL
    degraded = sibling(tmp_path, reachable=False, mode="DEGRADED_LOCAL", last_error_class="AUTH_REFUSED",
                       next_probe_after_utc=(NOON + timedelta(minutes=30)).isoformat())
    assert R.sibling_advisory(degraded, NOON, max_age_seconds=age)["state"] == R.SHARE_DEGRADED
    assert R.sibling_advisory(degraded, NOON + timedelta(hours=2), max_age_seconds=age)["state"] == R.STALE   # old news is no news
    assert R.sibling_advisory(sibling(tmp_path, share_slow=True), NOON, max_age_seconds=age)["state"] == R.SHARE_SLOW
    # as observed on 2026-11-14 after the outage: reachable again, CO.RA.PAN catching up -> maintenance waits, the gate stays open
    recovering = sibling(tmp_path, mode="RECOVERING", verdict={"at": NOON.isoformat(), "owed": 171})
    assert R.sibling_advisory(recovering, NOON, max_age_seconds=age)["state"] == R.SHARE_RECOVERING
    assert "catching up" in R.maintenance_refusal(policy(), tmp_path, NOON, recovering)
    assert R.ShareGate(tmp_path / "rt", policy(), env=recovering, clock=Clock(NOON)).closed_because() is None
    (tmp_path / "preservation_mode_state.json").write_text('{"schema": "something-else/v9"}', encoding="utf-8")
    assert R.sibling_advisory(degraded, NOON, max_age_seconds=age)["state"] == R.UNRECOGNISED
    # what permits maintenance is the policy alone: no signal, a stale one or a normal one are the same answer
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    for env in ({}, sibling(tmp_path)):
        assert R.maintenance_refusal(policy(), runtime, NOON, env) is None
    assert "sibling" in R.maintenance_refusal(policy(), runtime, NOON, sibling(tmp_path, share_slow=True))
    assert R.maintenance_refusal(policy(), runtime, datetime(2026, 11, 18, 2, 0).astimezone(), {}).startswith("quiet window")


# --- the share gate ---------------------------------------------------------------------------------------------


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def test_after_a_failed_contact_the_share_is_not_contacted_until_the_back_off_ends_even_across_a_restart(tmp_path):
    clock, contacts, up = Clock(NOON), [], [False]

    def resolve():
        contacts.append(clock.now)
        if not up[0]:
            raise storage_roots.StorageRootUnreachable("PRESERVATION: not reachable")
        return tmp_path

    guarded = R.ShareGate(tmp_path, policy(), clock=clock).guard(resolve)
    with pytest.raises(storage_roots.StorageRootUnreachable):
        guarded()
    for minute in range(0, 300, 1):                     # an intake retrying its pending packs every minute for five hours
        clock.now = NOON + timedelta(minutes=minute)
        restarted = R.ShareGate(tmp_path, policy(), clock=clock).guard(resolve)      # a new process every time: the state persists
        with pytest.raises(storage_roots.StorageRootUnreachable):
            restarted()
    # 5, 10, 20, 40, 60, 60, ... minutes: a handful of contacts in five hours, not 300
    assert len(contacts) <= 8, contacts
    up[0] = True
    clock.now = NOON + timedelta(hours=6)
    assert R.ShareGate(tmp_path, policy(), clock=clock).guard(resolve)() == tmp_path
    assert R.ShareGate(tmp_path, policy(), clock=clock).closed_because() is None


def test_a_fresh_degraded_observation_of_corapan_closes_the_gate_without_any_contact(tmp_path):
    contacts = []
    env = sibling(tmp_path, reachable=False, mode="DEGRADED_LOCAL", last_error_class="AUTH_REFUSED",
                  next_probe_after_utc=(NOON + timedelta(minutes=30)).isoformat())
    guarded = R.ShareGate(tmp_path, policy(), env=env, clock=Clock(NOON)).guard(lambda: contacts.append(1) or tmp_path)
    with pytest.raises(R.ShareBackingOff, match="sibling advisory"):
        guarded()
    assert contacts == [], "no logon attempt on the account CO.RA.PAN sees refused"
    later = R.ShareGate(tmp_path, policy(), env=env, clock=Clock(NOON + timedelta(minutes=31))).guard(lambda: contacts.append(1) or tmp_path)
    assert later() == tmp_path and contacts == [1]


def test_a_backing_off_root_takes_the_pipeline_outage_path(tmp_path):
    """The gate's refusal is an unreachable root to preserve_pack: the pack stays honestly PENDING (P5) and nothing is contacted."""
    from test_core_pipeline import Canary

    canary = Canary(tmp_path / "c")
    canary.acquire()
    identifier = canary.pack_id
    gate = R.ShareGate(canary.workspace.root, policy(), clock=Clock(NOON))
    gate.failed("simulated: the share refused the logon")
    contacts = []
    result = C.preserve_pack(canary.workspace, identifier, preservation_root=gate.guard(lambda: contacts.append(1) or canary.root), now=NOON)
    assert result.state == preservation.STATE_PENDING and contacts == []
    assert set(canary.workspace.ledger().states().values()) <= {"PRESERVATION_PENDING", "FETCH_FAILED"}


# --- the content check of a promotion -----------------------------------------------------------------------------


def _target(tmp_path) -> Path:
    root = tmp_path / "primary"
    root.mkdir()
    preservation_target.initialise_target(root, "coprepan-test-primary", operator="test", now=NOON)
    return root


def _promote(root, source, object_id, index):
    data = source.read_bytes()
    from coprepan.canonical import sha256_bytes

    return preservation.promote(source, root=root, area="raw", object_id=object_id, relative_path=f"x/{object_id}.bin",
                                declared_sha256=sha256_bytes(data), now=NOON, content_index=index)


def test_a_promotion_no_longer_reads_every_manifest_of_its_area(tmp_path, monkeypatch):
    root = _target(tmp_path)
    workspace = tmp_path / "runtime"
    for n in range(60):                                              # an area that already holds 60 objects
        source = tmp_path / f"s{n}"
        source.write_bytes(f"object {n}".encode())
        _promote(root, source, f"o{n:03d}", None)
    reads = []
    real = preservation.read_manifest
    monkeypatch.setattr(preservation, "read_manifest", lambda r, a, o: reads.append(o) or real(r, a, o))
    index = preserved_index.ManifestCache.for_root(workspace, root)
    first = tmp_path / "new1"
    first.write_bytes(b"a new object")
    assert _promote(root, first, "n001", index).action == preservation.ACTION_PROMOTED
    cold = len(reads)                                                 # the cache is empty: the area is read once, then never again
    reads.clear()
    second = tmp_path / "new2"
    second.write_bytes(b"another new object")
    assert _promote(root, second, "n002", index).action == preservation.ACTION_PROMOTED
    assert len(reads) <= 2, reads                                     # its own manifest only (and nothing per existing object)
    reads.clear()
    third = tmp_path / "new3"
    third.write_bytes(b"a third new object")
    _promote(root, third, "n003", None)                               # the old path, for comparison: every manifest of the area
    without = len(reads)
    reads.clear()
    duplicate = tmp_path / "dup"
    duplicate.write_bytes(b"object 7")                                # the same bytes as o007 under another identity
    result = _promote(root, duplicate, "d001", index)
    assert result.action == preservation.ACTION_DUPLICATE_RECORDED and result.duplicate_of == "o007"
    assert cold >= 60 and without >= 60
    # evidence for the run report: manifest reads on the root per promotion, cached vs. linear
    print(json.dumps({"manifests_in_area": 62, "reads_first_promotion_cold_cache": cold, "reads_warm_cache": 1, "reads_linear_scan": without}))


def test_the_content_index_is_bound_to_the_targets_identity(tmp_path):
    root = _target(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    preservation_target.initialise_target(other, "another-target", operator="test", now=NOON)
    a = preserved_index.ManifestCache.for_root(tmp_path / "runtime", root)
    b = preserved_index.ManifestCache.for_root(tmp_path / "runtime", other)
    assert a.directory != b.directory and a.target_id == "coprepan-test-primary"
    unmarked = tmp_path / "unmarked"
    unmarked.mkdir()
    assert preserved_index.ManifestCache.for_root(tmp_path / "runtime", unmarked) is None


# --- the verified local read ------------------------------------------------------------------------------------------


def test_derivation_right_after_preservation_reads_the_verified_local_copy_and_every_other_read_the_root(tmp_path, monkeypatch):
    from test_core_pipeline import Canary
    from coprepan import canary_driver, extraction

    canary = Canary(tmp_path / "c")
    canary.acquire()
    identifier = canary.pack_id
    calls = []
    real = preservation.verify_master
    monkeypatch.setattr(preservation, "verify_master", lambda r, a, o: calls.append((a, o)) or real(r, a, o))
    preserved = canary_driver._preserve(canary.workspace, [identifier], lambda: canary.root, None, None, lambda: NOON)
    after_preserve = len(calls)
    assert after_preserve == 2                                         # P2: both masters re-read on the root, once
    canary_driver._derive(canary.workspace, canary.registry, lambda: canary.root, preserved, extraction.BASELINE, lambda: NOON)
    assert len(calls) == after_preserve, "the derivation in the same step reads the workspace copy that hashes to the verified masters"
    held = C.open_preserved_pack(canary.root, identifier, workspace=canary.workspace)
    assert held.read_from == C.READ_FROM_ROOT and len(calls) == after_preserve + 2   # by default: re-verified on the root
    trusted = C.open_preserved_pack(canary.root, identifier, workspace=canary.workspace, trust_local_copy=True)
    assert trusted.read_from == C.READ_FROM_VERIFIED_LOCAL_COPY
    # a workspace copy that does not hash is never read: the root is read (and verified) instead
    local = canary.workspace.packs / f"{identifier}.warc.gz"
    data = bytearray(local.read_bytes())
    data[-10] ^= 0xFF
    os.chmod(local, 0o666)
    local.write_bytes(bytes(data))
    fallback = C.open_preserved_pack(canary.root, identifier, workspace=canary.workspace, trust_local_copy=True)
    assert fallback.read_from == C.READ_FROM_ROOT


# --- the incremental backup -------------------------------------------------------------------------------------------


LIMITS = {"workers": 1, "max_bytes_per_second": 0, "max_minutes": 60, "fixity_objects_per_run": 2, "fixity_bytes_per_run": 1 << 20,
          "fixity_cycle_max_days": 90, "restore_samples": 2, "receipt_warning_hours": 72, "receipt_failure_hours": 336}


@pytest.fixture()
def backup_roots(tmp_path, monkeypatch):
    primary, backup = tmp_path / "newfs" / "coprepan", tmp_path / "d" / "backup"
    primary.mkdir(parents=True)
    preservation_target.initialise_target(primary, "coprepan-test-primary", operator="test", now=NOON)
    for n in range(6):
        p = primary / "preservation" / "raw" / f"o{n}.bin"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(f"write-once object {n}".encode())
    monkeypatch.setattr(storage_roots, "volume_of", lambda root: 1 if "newfs" in str(root) else 2)
    B.init_root(backup, primary=primary, operator="test")
    base = M.baseline(primary)                                         # the FULL run, as the CLI does it
    assert B.copy(primary, backup, base)["ok"] and B.verify(backup, base)["ok"]
    B.write_receipt(backup, {"written_at": "2026-11-13T05:04:18Z", "mode": B.MODE_FULL, "primary_target_id": "coprepan-test-primary",
                             "objects": base["files"], "bytes": base["bytes"], "tree_sha256": base["tree_sha256"],
                             "produced_from_primary": True, "verified_against_primary": True, "last_full_verification_at": "2026-11-13T05:04:18Z"})
    return primary, backup


class Reads:
    """Counts what an incremental run reads of the primary: whole-file hashes and unbuffered re-reads."""

    def __init__(self, monkeypatch, primary):
        self.source, self.uncached, self.primary = [], [], str(primary)
        real_source, real_uncached = B._hash_source, M.sha256_uncached
        monkeypatch.setattr(B, "_hash_source", lambda path, rate: self.source.append(str(path)) or real_source(path, rate))

        def uncached(path):
            if str(path).startswith(self.primary) or self.primary in str(path):
                self.uncached.append(str(path))
            return real_uncached(path)
        monkeypatch.setattr(M, "sha256_uncached", uncached)


def incremental(primary, backup, tmp_path, name, **kw):
    return B.run_incremental(primary, backup, scratch=tmp_path / f"scratch-{name}", limits={**LIMITS, **kw.pop("limits", {})}, **kw)


def test_an_unchanged_primary_is_backed_up_without_reading_it_beyond_the_fixity_slice(backup_roots, tmp_path, monkeypatch):
    primary, backup = backup_roots
    reads = Reads(monkeypatch, primary)
    previous = B.read_receipt(backup)
    run = incremental(primary, backup, tmp_path, "1")
    assert run["ok"] and run["counts"] == {"REUSED_EVIDENCE": run["objects"]} and run["tree_sha256"] == previous["tree_sha256"]
    assert reads.source == [] and len(reads.uncached) == LIMITS["fixity_objects_per_run"]   # no full-tree read: the slice only
    assert run["fixity"]["checked"] == 2 and run["restore_test"]["all_ok"]


def test_the_fixity_rotation_covers_every_object_over_successive_runs(backup_roots, tmp_path):
    primary, backup = backup_roots
    objects = len(B.list_tree(primary, B._primary_excluded)[0])
    for number in range(-(-objects // LIMITS["fixity_objects_per_run"])):
        assert incremental(primary, backup, tmp_path, f"r{number}")["ok"]
    assert set(B.load_fixity(backup)) == set(B.list_tree(primary, B._primary_excluded)[0])


def test_new_objects_are_copied_and_verified_and_a_changed_one_is_reported_never_overwritten(backup_roots, tmp_path, monkeypatch):
    primary, backup = backup_roots
    new = primary / "preservation" / "raw" / "n1.bin"
    new.write_bytes(b"a new object")
    reads = Reads(monkeypatch, primary)
    run = incremental(primary, backup, tmp_path, "new")
    assert run["ok"] and run["counts"].get(M.COPIED) == 1 and len(reads.source) == 1       # the new object only
    assert (backup / "preservation" / "raw" / "n1.bin").read_bytes() == b"a new object"
    assert run["tree_sha256"] != B.read_receipt(backup)["tree_sha256"]
    # a write-once object rewritten in place: reported, and the backup copy is kept as it was
    victim = primary / "preservation" / "raw" / "o1.bin"
    before = (backup / "preservation" / "raw" / "o1.bin").read_bytes()
    victim.write_bytes(b"other bytes, other size")
    run = incremental(primary, backup, tmp_path, "changed")
    assert not run["ok"] and {p["problem"] for p in run["problems"]} >= {"SOURCE_CHANGED_SINCE_BACKUP"}
    assert (backup / "preservation" / "raw" / "o1.bin").read_bytes() == before


def test_a_touched_but_identical_object_is_restamped_and_a_lost_backup_copy_is_copied_again(backup_roots, tmp_path):
    primary, backup = backup_roots
    touched = primary / "preservation" / "raw" / "o2.bin"
    os.utime(touched, ns=(touched.stat().st_atime_ns, touched.stat().st_mtime_ns + 10_000_000_000))
    lost = backup / "preservation" / "raw" / "o3.bin"
    os.chmod(lost, 0o666)
    lost.unlink()                                                        # a test's own fixture file, removed to simulate a loss
    run = incremental(primary, backup, tmp_path, "t")
    assert run["ok"] and run["counts"].get(B.RESTAMPED) == 1 and run["recopied"] == 1 and lost.is_file()
    assert incremental(primary, backup, tmp_path, "t2")["counts"] == {"REUSED_EVIDENCE": run["objects"]}


def test_an_object_gone_from_the_primary_is_a_finding_and_nothing_is_removed_from_the_backup(backup_roots, tmp_path):
    primary, backup = backup_roots
    gone = primary / "preservation" / "raw" / "o4.bin"
    os.chmod(gone, 0o666)
    gone.unlink()
    run = incremental(primary, backup, tmp_path, "g")
    assert not run["ok"] and any(p["problem"] == "MISSING_ON_PRIMARY" for p in run["problems"])
    assert (backup / "preservation" / "raw" / "o4.bin").is_file()


def test_a_damaged_backup_copy_is_found_by_the_fixity_rotation(backup_roots, tmp_path):
    primary, backup = backup_roots
    copy = backup / "preservation" / "raw" / "o0.bin"
    os.chmod(copy, 0o666)
    data = bytearray(copy.read_bytes())
    data[0] ^= 0xFF
    copy.write_bytes(bytes(data))
    found = False
    for number in range(4):
        run = incremental(primary, backup, tmp_path, f"f{number}")
        found = found or any(p["problem"] == "FIXITY_MISMATCH_BACKUP" for p in run["problems"])
    assert found


def test_a_run_stops_at_its_budget_or_a_refusal_claims_nothing_and_resumes(backup_roots, tmp_path):
    primary, backup = backup_roots
    for n in range(5):
        (primary / "preservation" / "raw" / f"new{n}.bin").write_bytes(f"new {n}".encode())
    asked = []

    def stop():
        asked.append(1)
        return "paused by PAUSE_IO" if len(asked) > 2 else None
    run = incremental(primary, backup, tmp_path, "s", stop=stop)
    assert run["stopped"] and not run["ok"] and run["tree_sha256"] is None and run["stop_reason"] == "paused by PAUSE_IO"
    resumed = incremental(primary, backup, tmp_path, "s2")
    assert resumed["ok"] and resumed["counts"].get(M.COPIED, 0) < 5          # what the stopped run copied is not copied again
    ticks = iter(range(0, 10_000, 3600))
    timed = incremental(primary, backup, tmp_path, "s3", monotonic=lambda: next(ticks), limits={"max_minutes": 1})
    assert timed["stopped"] and timed["stop_reason"].startswith("TIME_BUDGET")


def test_an_incremental_run_needs_a_verified_receipt_of_this_primary(backup_roots, tmp_path):
    primary, backup = backup_roots
    (backup / B.STATE / B.RECEIPT).rename(backup / B.STATE / "moved_aside.json")
    with pytest.raises(B.BackupError, match="run --full"):
        incremental(primary, backup, tmp_path, "x")


def _health(backup, now):
    return B.backup_health(backup, now=now, calendar=policy().calendar, failure_hours=336)


def test_the_backup_health_counts_missed_weekday_slots_and_keeps_its_facts_apart(backup_roots):
    _, backup = backup_roots
    # the fixture's receipt (Friday 05:04Z, 06:04 local) predates Friday's 08:00 slot: that slot would count as missed. The
    # backup of Friday's scheduled run:
    B.write_receipt(backup, {**B.read_receipt(backup), "written_at": "2026-11-13T07:30:00Z"})
    monday = R.from_local(datetime(2026, 11, 16).date(), datetime(2000, 1, 1, 9, 0).time())
    B.write_last_run(backup, {"at": "2026-11-14T07:00:00Z", "outcome": R.SCHEDULED_PAUSE, "reason": "sat"})
    B.write_last_run(backup, {"at": "2026-11-15T07:00:00Z", "outcome": R.SCHEDULED_PAUSE, "reason": "sun"})
    weekend = _health(backup, monday)
    assert weekend["level"] == "OK" and weekend["missed_weekday_slots"] == 0     # a weekend pause is not a failure
    assert weekend["last_verified_age_hours"] > 72                                # and the real age stays visible
    assert weekend["attempts_since_verified"] == {R.SCHEDULED_PAUSE: 2}
    assert weekend["next_scheduled_start"] == "2026-11-17T07:00:00Z"              # Tuesday 08:00 CET (Monday's slot passed at 07:00Z)
    assert weekend["restore_evidence"] is not None and weekend["last_verified_mode"] == B.MODE_FULL
    B.write_last_run(backup, {"at": "2026-11-16T07:00:00Z", "outcome": R.DEFERRED_RESOURCE_PRIORITY, "reason": "sibling advisory: slow"})
    one = _health(backup, monday + timedelta(hours=2))
    assert one["level"] == "OK" and one["missed_weekday_slots"] == 1               # one deferral for CO.RA.PAN: visible, no alarm
    B.write_last_run(backup, {"at": "2026-11-17T07:00:00Z", "outcome": R.DEFERRED_SHARE_UNAVAILABLE, "reason": "refused"})
    two = _health(backup, monday + timedelta(days=1, hours=2))
    assert two["level"] == "WARNING" and two["missed_weekday_slots"] == 2 and "DEFERRED_SHARE_UNAVAILABLE" in " ".join(two["reasons"])
    week = _health(backup, monday + timedelta(days=4, hours=2))
    assert week["level"] == "FAILURE" and week["operator_action"]               # a working week without a backup is a real risk
    B.write_last_run(backup, {"at": "2026-11-16T07:00:00Z", "outcome": R.FAILED, "problem_count": 1, "first_problems": [{"problem": "X"}]})
    assert _health(backup, monday)["level"] == "FAILURE"
    B.write_last_run(backup, {"at": "2026-11-16T07:00:00Z", "outcome": R.NEEDS_FULL_AUTHORIZATION, "reason": "journal damaged"})
    needs = _health(backup, monday)
    assert needs["level"] == "FAILURE" and any("--full" in a for a in needs["operator_action"])


def test_no_slot_before_the_calendar_existed_counts_and_a_real_missed_slot_still_does(backup_roots):
    """The transition of 2026-11-14 (policy 2026-11-14.3): the real receipt of Friday 2026-11-13 05:04Z precedes Friday's 08:00
    slot of a calendar that only came into force on Saturday; that slot was never scheduled and is not missed. Monday's is."""
    _, backup = backup_roots                                       # the fixture's receipt: 2026-11-13T05:04:18Z, as on the real root
    saturday = datetime(2026, 11, 14, 12, 28, tzinfo=timezone.utc)
    assert _health(backup, saturday)["missed_weekday_slots"] == 0 and _health(backup, saturday)["last_verified_age_hours"] > 31
    before_grace = R.from_local(datetime(2026, 11, 16).date(), datetime(2000, 1, 1, 9, 59).time())
    after_grace = R.from_local(datetime(2026, 11, 16).date(), datetime(2000, 1, 1, 10, 1).time())
    assert _health(backup, before_grace)["missed_weekday_slots"] == 0
    late = _health(backup, after_grace)
    assert late["missed_weekday_slots"] == 1 and late["missed_slot_starts"] == ["2026-11-16T07:00:00Z"] and late["level"] == "OK"
    tuesday = _health(backup, after_grace + timedelta(days=1))
    assert tuesday["missed_weekday_slots"] == 2 and tuesday["level"] == "WARNING"     # nothing real is suppressed
    doc = json.loads((REPO / "config" / "resource_policy.json").read_text(encoding="utf-8"))
    earlier = R.parse_policy({**doc, "maintenance_calendar": {**doc["maintenance_calendar"], "effective_from": "2026-11-01"}})
    assert len(earlier.calendar.missed(datetime(2026, 11, 13, 5, 4, tzinfo=timezone.utc), saturday)) == 1   # an earlier start counts Friday


def test_a_damaged_basis_or_a_mass_of_changed_timestamps_needs_the_operators_full_order(backup_roots, tmp_path, monkeypatch):
    primary, backup = backup_roots
    reads = Reads(monkeypatch, primary)
    for n in range(4):                                                   # more changed timestamps than one run's fixity slice (2)
        p = primary / "preservation" / "raw" / f"o{n}.bin"
        os.utime(p, ns=(p.stat().st_atime_ns, p.stat().st_mtime_ns + 10_000_000_000))
    with pytest.raises(B.NeedsFullAuthorization, match="operator"):
        incremental(primary, backup, tmp_path, "mass")
    assert reads.source == [] and reads.uncached == []                    # nothing of the primary was read beyond its listing
    journal = backup / B.STATE / B.JOURNAL
    lines = journal.read_text(encoding="utf-8").splitlines()
    os.chmod(journal, 0o666)
    journal.write_text("\n".join(lines[:2]) + "\n", encoding="utf-8")     # the test's own fixture journal, truncated: a damaged basis
    with pytest.raises(B.NeedsFullAuthorization, match="damaged"):
        incremental(primary, backup, tmp_path, "torn")
    assert reads.source == [] and reads.uncached == []


def test_the_manifest_cache_is_seeded_from_the_verified_backup_without_the_share(tmp_path, monkeypatch):
    from coprepan.canonical import sha256_bytes

    primary, backup = tmp_path / "newfs" / "coprepan", tmp_path / "d" / "backup"
    primary.mkdir(parents=True)
    preservation_target.initialise_target(primary, "coprepan-test-primary", operator="test", now=NOON)
    for n in range(5):
        source = tmp_path / f"s{n}"
        source.write_bytes(f"object {n}".encode())
        preservation.promote(source, root=primary, area="raw", object_id=f"o{n:03d}", relative_path=f"x/o{n:03d}.bin",
                             declared_sha256=sha256_bytes(source.read_bytes()), now=NOON)
    monkeypatch.setattr(storage_roots, "volume_of", lambda root: 1 if "newfs" in str(root) else 2)
    B.init_root(backup, primary=primary, operator="test")
    base = M.baseline(primary)
    assert B.copy(primary, backup, base)["ok"] and B.verify(backup, base)["ok"]
    B.write_receipt(backup, {"written_at": "2026-11-13T05:04:18Z", "mode": B.MODE_FULL, "primary_target_id": "coprepan-test-primary",
                             "objects": base["files"], "verified_against_primary": True, "produced_from_primary": True})
    tampered = backup / "preservation" / "manifests" / "raw" / "o004.json"
    os.chmod(tampered, 0o666)
    tampered.write_text(tampered.read_text(encoding="utf-8").replace("o004", "o004 "), encoding="utf-8")   # not the verified bytes
    cache = preserved_index.ManifestCache(tmp_path / "runtime" / preserved_index.CACHE_DIRECTORY / "coprepan-test-primary", "coprepan-test-primary")
    seeded = B.seed_manifest_cache(backup, cache)
    assert seeded["counts"] == {"SEEDED": 4, "DIFFERS_FROM_EVIDENCE": 1}
    assert B.seed_manifest_cache(backup, cache)["counts"] == {"HELD": 4, "DIFFERS_FROM_EVIDENCE": 1}     # resumable: nothing read twice
    # with the seeded cache a promotion reads only what the seed could not give (one manifest), not the area
    reads = []
    real = preservation.read_manifest
    monkeypatch.setattr(preservation, "read_manifest", lambda r, a, o: reads.append(o) or real(r, a, o))
    new = tmp_path / "new"
    new.write_bytes(b"a new object")
    preserved_index.reset_memory()
    index = preserved_index.ManifestCache.for_root(tmp_path / "runtime", primary)
    assert preservation.promote(new, root=primary, area="raw", object_id="n001", relative_path="x/n001.bin",
                                declared_sha256=sha256_bytes(b"a new object"), now=NOON, content_index=index).action == preservation.ACTION_PROMOTED
    assert sorted(reads) == ["n001", "o004"], reads
    other = preserved_index.ManifestCache(tmp_path / "rt2", "another-target")
    with pytest.raises(B.BackupError):
        B.seed_manifest_cache(backup, other)                                   # a backup of another target seeds nothing


def test_a_promotion_never_warms_a_cold_cache_from_the_share_and_the_warm_up_is_bounded(tmp_path, monkeypatch):
    root = _target(tmp_path)
    for n in range(12):
        source = tmp_path / f"s{n}"
        source.write_bytes(f"object {n}".encode())
        _promote(root, source, f"o{n:03d}", None)
    monkeypatch.setattr(preserved_index, "PROMOTION_DELTA_READS", 5)
    reads = []
    real = preservation.read_manifest
    monkeypatch.setattr(preservation, "read_manifest", lambda r, a, o: reads.append(o) or real(r, a, o))
    index = preserved_index.ManifestCache.for_root(tmp_path / "runtime", root)
    new = tmp_path / "new"
    new.write_bytes(b"a new object")
    with pytest.raises(preserved_index.CacheIncomplete):
        _promote(root, new, "n001", index)
    assert reads == ["n001"]                                                    # its own manifest only; no burst over the area
    assert not (root / "x" / "n001.bin").exists()                               # nothing landed: the pack stays honestly pending
    assert preserved_index.warm(index, root, ["raw"], max_reads=8) == {"read": 8, "missing": 4}
    assert preserved_index.warm(index, root, ["raw"], max_reads=8) == {"read": 4, "missing": 0}
    reads.clear()
    assert _promote(root, new, "n001", index).action == preservation.ACTION_PROMOTED and len(reads) <= 2


def test_the_cli_defers_in_a_quiet_window_and_while_paused_and_one_run_holds_the_root(backup_roots, tmp_path, monkeypatch, capsys):
    import importlib.util

    primary, backup = backup_roots
    spec = importlib.util.spec_from_file_location("preservation_backup_cli_iso", REPO / "scripts" / "preservation_backup.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("COPREPAN_PRESERVATION_ROOT", str(primary))
    monkeypatch.setenv("COPREPAN_PRESERVATION_TARGET_ID", "coprepan-test-primary")
    monkeypatch.setenv("COPREPAN_BACKUP_ROOT", str(backup))
    monkeypatch.setenv("COPREPAN_WORKSPACE_ROOT", str(runtime))
    checkout = tmp_path / "checkout-without-env"
    checkout.mkdir()
    argv = ["--workstation-checkout", str(checkout), "run"]
    monkeypatch.setattr(cli, "_now", lambda: R.from_local(datetime(2026, 11, 18).date(), datetime(2000, 1, 1, 2, 0).time()))   # Wednesday 02:00
    assert cli.main(argv) == 0 and "DEFERRED_RESOURCE_PRIORITY: quiet window" in capsys.readouterr().out
    assert B.read_last_run(backup)["outcome"] == R.DEFERRED_RESOURCE_PRIORITY
    monkeypatch.setattr(cli, "_now", lambda: NOON - timedelta(days=2))                     # Saturday noon: the calendar's pause
    assert cli.main(argv) == 0 and "SCHEDULED_PAUSE" in capsys.readouterr().out
    assert B.read_last_run(backup)["outcome"] == R.SCHEDULED_PAUSE and B.read_receipt(backup)["mode"] == B.MODE_FULL   # nothing ran
    monkeypatch.setattr(cli, "_now", lambda: NOON)
    R.pause_path(runtime).parent.mkdir(parents=True, exist_ok=True)
    R.pause_path(runtime).write_text("CO.RA.PAN release night", encoding="utf-8")
    assert cli.main(argv) == 0 and "paused by PAUSE_IO" in capsys.readouterr().out
    R.pause_path(runtime).unlink()
    assert cli.main(argv) == 0 and "BACKUP_VERIFIED" in capsys.readouterr().out
    assert B.read_receipt(backup)["mode"] == B.MODE_INCREMENTAL and B.read_last_run(backup)["outcome"] == "BACKUP_VERIFIED"
    # a second run while another PROCESS holds the backup root's lock is deferred (the lock is re-entrant inside one process)
    import subprocess
    import sys
    import time

    ready, release = tmp_path / "holder-ready", tmp_path / "holder-release"
    code = ("import sys, time, pathlib; sys.path.insert(0, sys.argv[1]); from coprepan.exclusive import exclusive\n"
            "with exclusive(pathlib.Path(sys.argv[2]), 'another backup run'):\n"
            "    pathlib.Path(sys.argv[3]).write_text('x')\n"
            "    while not pathlib.Path(sys.argv[4]).exists(): time.sleep(0.05)\n")
    holder = subprocess.Popen([sys.executable, "-c", code, str(REPO / "src"), str(backup / B.STATE), str(ready), str(release)])
    try:
        for _ in range(400):
            if ready.exists():
                break
            time.sleep(0.05)
        assert ready.exists()
        assert cli.main(argv) == 0 and "another backup run holds this backup root" in capsys.readouterr().out
    finally:
        release.write_text("x", encoding="utf-8")
        holder.wait(timeout=60)


def test_without_a_verified_receipt_a_scheduled_run_asks_for_the_full_order_and_reads_nothing(backup_roots, tmp_path, monkeypatch, capsys):
    import importlib.util

    primary, backup = backup_roots
    spec = importlib.util.spec_from_file_location("preservation_backup_cli_full", REPO / "scripts" / "preservation_backup.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    for name, value in (("COPREPAN_PRESERVATION_ROOT", primary), ("COPREPAN_PRESERVATION_TARGET_ID", "coprepan-test-primary"),
                        ("COPREPAN_BACKUP_ROOT", backup), ("COPREPAN_WORKSPACE_ROOT", runtime)):
        monkeypatch.setenv(name, str(value))
    checkout = tmp_path / "checkout-without-env"
    checkout.mkdir()
    monkeypatch.setattr(cli, "_now", lambda: NOON)
    (backup / B.STATE / B.RECEIPT).rename(backup / B.STATE / "moved_aside.json")    # the test's own fixture receipt
    reads = Reads(monkeypatch, primary)
    full = []
    monkeypatch.setattr(cli, "_full", lambda *a, **k: full.append(1))
    assert cli.main(["--workstation-checkout", str(checkout), "run"]) == 1
    assert R.NEEDS_FULL_AUTHORIZATION in capsys.readouterr().out and full == [] and reads.source == [] and reads.uncached == []
    assert B.read_last_run(backup)["outcome"] == R.NEEDS_FULL_AUTHORIZATION


def test_the_task_check_reads_the_scheduler_definition_against_the_calendar():
    import importlib.util

    spec = importlib.util.spec_from_file_location("preservation_backup_cli_task", REPO / "scripts" / "preservation_backup.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    ns = 'xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"'
    daily = (f'<Task {ns}><Triggers><CalendarTrigger><StartBoundary>2026-10-19T04:45:00+01:00</StartBoundary><Enabled>true</Enabled>'
             '<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay></CalendarTrigger></Triggers></Task>')
    weekly = (f'<Task {ns}><Triggers><CalendarTrigger><StartBoundary>2026-11-16T08:00:00</StartBoundary><Enabled>true</Enabled>'
              '<ScheduleByWeek><DaysOfWeek><Monday /><Tuesday /><Wednesday /><Thursday /><Friday /></DaysOfWeek><WeeksInterval>1</WeeksInterval>'
              '</ScheduleByWeek></CalendarTrigger></Triggers></Task>')
    assert not cli.schedule_check(cli.task_triggers(daily), policy())["consistent"]
    assert cli.schedule_check(cli.task_triggers(weekly), policy()) ["consistent"]


# --- the intake under the resource policy -------------------------------------------------------------------------------


def test_with_the_policy_an_intake_keeps_acquiring_while_pending_stays_inside_its_bounds(tmp_path, site):
    from test_intake import T0, Bench, serve

    fresh = [(f"/n{n}", T0 + timedelta(minutes=n)) for n in range(1, 31)]
    serve(site, [fresh])
    bench = Bench(tmp_path, site)
    bench.environment.resource_policy = policy()
    bench.target_up = False
    bench.start()

    def back(b):
        if b.clock.now > T0 + timedelta(hours=2):
            b.target_up = True
    bench.before_sleep = back
    state = bench.run()
    asked_while_away = [r for r in bench.records() if r["fetch_kind"] == "item"]
    assert len(asked_while_away) > 5                      # not one outlet call and silence: the bounded pending let it go on
    assert state["preservation"] == "nothing pending"     # it came back and every pack was preserved
    assert set(bench.workspace.ledger().states().values()) <= {"RAW_PRESERVED", "FETCH_FAILED"}
    assert bench.finalize()["verification"]["status"] == "PASS"


def test_beyond_its_pending_bound_or_while_paused_an_intake_asks_nothing(tmp_path, site):
    from test_intake import T0, Bench, serve

    fresh = [(f"/n{n}", T0 + timedelta(minutes=n)) for n in range(1, 31)]
    serve(site, [fresh])
    bench = Bench(tmp_path, site)
    bench.environment.resource_policy = policy(pending__max_packs=0)
    bench.target_up = False
    bench.start()
    seen = []
    bench.before_sleep = lambda b: seen.append(len(b.site.requests))

    def stop_after_a_while(b):
        seen.append(len(b.site.requests))
        if b.clock.now > T0 + timedelta(hours=1, minutes=30):
            (b.state_dir / "STOP").write_text("", encoding="utf-8")
    bench.before_sleep = stop_after_a_while
    state = bench.run()
    assert seen[0] == seen[-1] == 5, seen                 # one outlet call, then nothing while more than 0 packs are pending
    assert "more than the policy's 0" in (state.get("held_because") or "")
    # the operator's pause: nothing is asked while it exists, and the intake goes on when it is gone
    paused = Bench(tmp_path / "paused", site)
    paused.environment.resource_policy = policy()
    R.pause_path(paused.workspace.root).parent.mkdir(parents=True, exist_ok=True)
    R.pause_path(paused.workspace.root).write_text("CO.RA.PAN backup night", encoding="utf-8")
    paused.start()
    before = len(site.requests)

    def resume(b):
        if b.clock.now > T0 + timedelta(minutes=20) and R.pause_path(b.workspace.root).exists():
            assert len(site.requests) == before
            R.pause_path(b.workspace.root).unlink()
    paused.before_sleep = resume
    final = paused.run()
    assert len(site.requests) > before and final["held_because"] is None


def test_while_corapan_recovers_an_intake_acquires_locally_and_afterwards_catches_up_bounded(tmp_path, site):
    """CPD-0035: RECOVERING holds every new transfer (no contact), the intake goes on locally within its bounds; back to NORMAL,
    the backlog is preserved at most ``catch_up_packs_per_hour`` per hour -- in the controller, across a restart, and in the
    bounded drain before the finalizer -- never in one burst."""
    from test_intake import T0, Bench, serve

    serve(site, [[(f"/n{n}", T0 + timedelta(minutes=n)) for n in range(1, 31)]])
    bench = Bench(tmp_path, site)
    resources = policy(pending__catch_up_packs_per_hour=1)
    bench.environment.resource_policy = resources
    signal, mode = tmp_path / "corapan_state.json", ["RECOVERING"]

    def observe(b):
        signal.write_text(json.dumps({"schema": R.SIBLING_SCHEMA, "reachable": True, "mode": mode[0], "share_slow": False,
                                      "last_probe_utc": b.clock().isoformat(), "verdict": {"at": b.clock().isoformat(), "owed": 9}}), encoding="utf-8")
    observe(bench)
    contacts = []
    gate = R.ShareGate(bench.workspace.root, resources, env={R.SIBLING_SIGNAL_VARIABLE: str(signal)}, clock=bench.clock)
    bench.environment.preservation_root = gate.guard(lambda: contacts.append(bench.clock()) or bench.preservation_root(), transfer=True)
    bench.start()
    seen = []

    def step(b):
        if b.clock.now > T0 + timedelta(hours=2, minutes=30):
            mode[0] = "NORMAL"
        observe(b)
        state = json.loads((b.state_dir / "state.json").read_text(encoding="utf-8"))
        seen.append((b.clock(), mode[0], state.get("catch_up"), len(contacts)))
    bench.before_sleep = step
    state = bench.run()
    recovering = [s for s in seen if s[1] == "RECOVERING"]
    assert recovering and recovering[-1][3] == 0, "no contact with the share while CO.RA.PAN catches up"
    asked_while_recovering = [r for r in bench.records() if r["fetch_kind"] == "item"
                              and datetime.fromisoformat(r["fetch_started_at"].replace("Z", "+00:00")) < T0 + timedelta(hours=2, minutes=30)]
    assert asked_while_recovering, "local acquisition went on within the pending bounds"
    held = [s[2] for s in recovering if s[2] and s[2]["backlog"]]
    assert held and all(c["attempted"] == 0 and "transfers wait" in (c["held_because"] or "") for c in held)
    after = [s[2] for s in seen if s[1] == "NORMAL" and s[2]]
    assert after and all(c["attempted"] <= 1 for c in after)                      # never more than the hourly budget at once
    pending = canary_driver_pending(bench)
    assert state["status"] == "FINALIZING"
    # the drain before the finalizer: the same hourly budget, spent per hour, kept in the state file across processes
    from coprepan import intake as I

    drained = []
    while pending:
        before = len(pending)
        left = I.drain(bench.plan, bench.state_dir, bench.environment)
        again = I.drain(bench.plan, bench.state_dir, bench.environment)          # a second tick in the same hour: the budget is spent
        assert again == left and before - left <= 1
        drained.append(before - left)
        bench.clock.sleep(3600)
        pending = canary_driver_pending(bench)
        assert len(drained) < 50
    assert bench.finalize()["verification"]["status"] == "PASS"


def canary_driver_pending(bench):
    from coprepan import canary_driver

    return canary_driver.pending_pack_ids(bench.workspace)


def test_the_pending_packs_come_from_the_ledger_without_reading_every_pack(tmp_path, monkeypatch):
    from test_core_pipeline import Canary
    from coprepan import canary_driver, pack

    canary = Canary(tmp_path / "c")
    canary.acquire()
    identifier = canary.pack_id
    gate = R.ShareGate(canary.workspace.root, policy(), clock=Clock(NOON))
    gate.failed("simulated outage")
    C.preserve_pack(canary.workspace, identifier, preservation_root=gate.guard(lambda: canary.root), now=NOON)
    scans = []
    real = pack.scan
    monkeypatch.setattr(pack, "scan", lambda path, expected: scans.append(expected) or real(path, expected))
    assert canary_driver.pending_pack_ids(canary.workspace) == [identifier] and scans == []


def test_a_full_runtime_volume_stops_the_requests_before_corapan_would_notice(tmp_path, site, monkeypatch):
    from test_intake import T0, Bench, serve

    serve(site, [[(f"/n{n}", T0 + timedelta(minutes=n)) for n in range(1, 6)]])
    bench = Bench(tmp_path, site)
    bench.environment.resource_policy = policy()

    class Usage:
        free = 10 * R.GIB
    monkeypatch.setattr(R.shutil, "disk_usage", lambda path: Usage())
    bench.start()
    bench.before_sleep = lambda b: (b.state_dir / "STOP").write_text("", encoding="utf-8")
    state = bench.run()
    assert len(site.requests) == 0 and "floor" in (state.get("held_because") or "")


def test_a_tick_of_a_running_intake_loads_without_the_share_and_reaches_it_only_through_the_gate(tmp_path, monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location("intake_operator_iso", REPO / "scripts" / "intake_operator.py")
    operator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(operator)
    for name in ("runtime", "spool"):
        (tmp_path / name).mkdir()
    monkeypatch.setenv("COPREPAN_WORKSPACE_ROOT", str(tmp_path / "runtime"))
    monkeypatch.setenv("COPREPAN_SPOOL_ROOT", str(tmp_path / "spool"))
    monkeypatch.setenv("COPREPAN_PRESERVATION_ROOT", str(tmp_path / "share-that-is-away"))
    monkeypatch.delenv("COPREPAN_BACKUP_ROOT", raising=False)
    environment, roles = operator.load_environment(REPO)                    # before CPD-0033 this raised StorageRootUnreachable
    assert roles["PRESERVATION"] is None and environment.resource_policy is not None
    with pytest.raises(storage_roots.StorageRootUnreachable):
        environment.preservation_root()                                      # one contact; it fails and closes the gate
    with pytest.raises(R.ShareBackingOff):
        environment.preservation_root()                                      # no second contact during the back-off
    with pytest.raises(storage_roots.StorageRootUnreachable):
        operator.load_environment(REPO, need_preservation=True)              # a start still needs the target


@pytest.fixture
def site():
    from test_intake import LocalSite

    with LocalSite() as server:
        yield server
