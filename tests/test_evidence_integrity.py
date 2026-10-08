"""Evidence-table integrity (decision CPD-0010).

Primary append-only evidence is chained: every row names the row before it. Derived state — the
candidates and the identity tables — is checked against, and can be rebuilt from, the evidence.

Classification (CPD-0010 §1) and what the tests below attack:

====================================  =====================  ==============================================
store                                 class                  protection
====================================  =====================  ==============================================
ledger                                PRIMARY_EVIDENCE       chained (CPD-0009)
request log                           PRIMARY_EVIDENCE       chained
discovery inputs, events              PRIMARY_EVIDENCE       chained
candidate qualifications, labels      PRIMARY_EVIDENCE       chained
discovery candidates                  DERIVED_REBUILDABLE    checked against events + request log
identity: documents, observations,
versions, relations                   DERIVED_REBUILDABLE    rebuilt from preserved evidence and compared
====================================  =====================  ==============================================

Robustness and reproducibility on temporary directories of one machine.
"""

import hashlib
import os
import random
import shutil
import socket
from types import SimpleNamespace

import pytest

from coprepan import admission, canonical, core_pipeline as C, discovery, evidence, extraction, freeze, identity_rebuild as R, jsonl, recovery
from coprepan import http_acquisition as H
from coprepan.jsonl import ChainBroken, JsonlError, TornTail
from support_http import LocalSite
from test_core_pipeline import Canary
from support_processes import child, kill_at, race
from test_offline_e2e import Pass, script

TABLES = {
    "request log": ("requests/requests.jsonl", lambda ws: H.request_rows(ws)),
    "discovery inputs": ("discovery/inputs.jsonl", lambda ws: H.discovery_tables(ws)),
    "discovery events": ("discovery/events.jsonl", lambda ws: H.discovery_tables(ws)),
    "qualifications": ("discovery/qualifications.jsonl", lambda ws: H.qualification_table(ws)),
    "admission labels": ("admission/labels.jsonl", lambda ws: admission.label_table(ws)),
}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """One complete acquisition pass with labels, built once and copied for each test."""
    base = tmp_path_factory.mktemp("built")
    with LocalSite() as site:
        script(site)
        one = Pass(base, site).all()
    admission.label_pack(one.workspace, preservation_root=one.root, identifier=one.pack_id, results=one.results,
                         extractor=extraction.BASELINE, labelled_at="2026-10-07T13:00:00.000000Z")
    return base, one


def clone(tmp_path, base, one):
    shutil.copytree(base, tmp_path / "w")
    return SimpleNamespace(workspace=C.Workspace(tmp_path / "w" / "workspace"), root=tmp_path / "w" / "preservation_root",
                           registry=one.registry, pack_id=one.pack_id, base=tmp_path / "w")


@pytest.fixture
def world(tmp_path, built):
    """An HTTP acquisition pass: every chained table, the candidates, documents without relations."""
    return clone(tmp_path, *built)


@pytest.fixture(scope="module")
def built_canary(tmp_path_factory):
    base = tmp_path_factory.mktemp("built_canary")
    return base, Canary(base).all()


@pytest.fixture
def iworld(tmp_path, built_canary):
    """The recorded-replay canary: documents, versions, duplicates and a moved URL — all four identity tables."""
    return clone(tmp_path, *built_canary)


def lines(path):
    return path.read_bytes().split(b"\n")[:-1]


def write(path, items):
    path.write_bytes(b"".join(item + b"\n" for item in items))


def tamper(path, how):
    items = lines(path)
    assert len(items) >= 5, f"{path.name} has too few rows to attack the middle of"
    middle = len(items) // 2
    if how == "change":
        text = items[middle].decode("utf-8")
        position = next(i for i in range(text.rindex('"schema"') - 1, 20, -1) if text[i] in "0123456789")
        items[middle] = (text[:position] + str((int(text[position]) + 1) % 10) + text[position + 1:]).encode("utf-8")
    elif how == "remove":
        del items[middle]
    elif how == "insert":
        items.insert(middle, items[middle - 1])
    elif how == "reorder":
        items[middle], items[middle + 1] = items[middle + 1], items[middle]
    write(path, items)


# --- chained tables: every manipulation of earlier evidence is detected ----------------------------------


@pytest.mark.parametrize("how", ["change", "remove", "insert", "reorder"])
@pytest.mark.parametrize("name", list(TABLES))
def test_a_manipulation_of_earlier_evidence_is_detected_refused_and_never_repaired(world, name, how):
    relative, read = TABLES[name]
    path = world.workspace.root / relative
    assert read(world.workspace)                                     # the table is whole before
    tamper(path, how)
    damaged = path.read_bytes()
    with pytest.raises(ChainBroken, match="earlier row was changed, removed, inserted or moved"):
        read(world.workspace)
    found = recovery.diagnose(world.workspace.root, world.root)
    assert found["classification"] == "DAMAGED" and relative in found["chain_broken_or_unreadable"]
    assert recovery.repair(world.workspace.root)["moved_aside"] == []   # historical evidence is not repaired
    assert path.read_bytes() == damaged


@pytest.mark.parametrize("name", list(TABLES))
def test_a_torn_tail_is_a_crash_not_a_manipulation_and_no_earlier_row_becomes_invalid(world, name):
    relative, read = TABLES[name]
    path = world.workspace.root / relative
    whole = path.read_bytes()
    count = len(lines(path))
    with open(path, "ab") as handle:
        handle.write(b'{"previous_row_sha256": "ab')                     # a write that was cut off
    with pytest.raises(TornTail):
        read(world.workspace)
    found = recovery.diagnose(world.workspace.root, world.root)
    assert relative in found["torn_tails"] and found["classification"] == "NEEDS_REPAIR" and found["chain_broken_or_unreadable"] == []
    moved = recovery.repair(world.workspace.root)["moved_aside"]
    assert moved == [relative + ".torn-0"] and path.read_bytes() == whole      # exactly the old bytes are back
    assert recovery.diagnose(world.workspace.root, world.root)["classification"] == "CLEAN"
    schema = evidence.chained_tables()[relative]
    jsonl.append_chained(path, schema, {"after": "the repair"})            # and the chain goes on from the last whole row
    assert len(jsonl.read_chained(path, schema)) == count + 1


@pytest.mark.parametrize("name", list(TABLES))
def test_the_chain_names_the_hash_of_the_line_before_and_the_first_row_names_nothing(world, name):
    relative, _ = TABLES[name]
    rows = [__import__("json").loads(line) for line in lines(world.workspace.root / relative)]
    raw = lines(world.workspace.root / relative)
    assert rows[0]["previous_row_sha256"] is None
    for number in range(1, len(rows)):
        assert rows[number]["previous_row_sha256"] == hashlib.sha256(raw[number - 1] + b"\n").hexdigest()


def test_a_run_refuses_to_start_on_a_request_log_that_does_not_authenticate_and_sends_nothing(tmp_path):
    with LocalSite() as site:
        script(site)
        first = Pass(tmp_path, site).all()
        tamper(first.workspace.root / "requests" / "requests.jsonl", "remove")
        site.requests.clear()
        later = Pass(tmp_path, site, start=first.run.started_at.replace(day=9))
        with pytest.raises(ChainBroken):
            later.acquire()
        assert site.requests == []                                       # the evidence is checked before the first request


# --- the mechanism itself --------------------------------------------------------------------------------


def test_a_valid_append_leaves_the_old_prefix_valid_and_every_row_authenticates_the_whole_prefix(tmp_path):
    rng = random.Random(20261008)
    for round_ in range(15):
        path = tmp_path / f"t{round_}.jsonl"
        total = rng.randrange(3, 30)
        prefixes = []
        for number in range(total):
            jsonl.append_chained(path, "coprepan-x/v2", {"n": number, "pad": "y" * rng.randrange(0, 600)})
            prefixes.append(path.read_bytes())
        for older, newer in zip(prefixes, prefixes[1:]):
            assert newer.startswith(older)                              # an append never touches what is there
        assert len(jsonl.read_chained(path, "coprepan-x/v2")) == total
        items = lines(path)
        victim = rng.randrange(0, total - 1)                            # any row but the last
        changed = list(items)
        changed[victim] = changed[victim].replace(b'"n": ', b'"n":  ', 1)
        write(path, changed)
        with pytest.raises(ChainBroken, match=f"line {victim + 2} "):   # the row after it vouches for it
            jsonl.read_chained(path, "coprepan-x/v2")


def test_the_last_row_has_no_successor_to_vouch_for_it(tmp_path):
    """The one documented limit of a chain: the newest row is protected by the next append only."""
    path = tmp_path / "t.jsonl"
    for number in range(4):
        jsonl.append_chained(path, "coprepan-x/v2", {"n": number})
    items = lines(path)
    items[-1] = items[-1].replace(b'"n": 3', b'"n": 9')
    write(path, items)
    assert jsonl.read_chained(path, "coprepan-x/v2")[-1]["n"] == 9       # not noticed — and said so, in CPD-0010


def test_schema_versions_are_not_read_as_each_other(tmp_path):
    plain, chained = tmp_path / "plain.jsonl", tmp_path / "chained.jsonl"
    jsonl.append_row(plain, "coprepan-request-log/v1", {"event": "PLANNED"})
    jsonl.append_chained(chained, "coprepan-request-log/v2", {"event": "PLANNED"})
    with pytest.raises(JsonlError, match="schema 'coprepan-request-log/v1'"):
        jsonl.read_chained(plain, "coprepan-request-log/v2")             # an old row is not silently a new one
    with pytest.raises(JsonlError, match="schema 'coprepan-request-log/v2'"):
        jsonl.read_rows(chained, "coprepan-request-log/v1")              # and a new row is not read as an old one
    no_chain = tmp_path / "no_chain.jsonl"
    no_chain.write_bytes(canonical.line_json({"schema": "coprepan-request-log/v2", "event": "PLANNED"}))
    with pytest.raises(JsonlError):
        jsonl.read_chained(no_chain, "coprepan-request-log/v2")           # v2 without a chain field is not v2
    with pytest.raises(JsonlError, match="set by the table"):
        jsonl.append_chained(chained, "coprepan-request-log/v2", {"previous_row_sha256": "0" * 64})
    schemas = freeze.schema_ids()
    for current in ("coprepan-request-log/v2", "coprepan-discovery-input/v2", "coprepan-discovery-event/v2",
                    "coprepan-candidate-qualification/v2", "coprepan-admission-label/v2", "coprepan-discovery-candidate/v1"):
        assert current in schemas
    for superseded in ("coprepan-request-log/v1", "coprepan-discovery-input/v1", "coprepan-discovery-event/v1"):
        assert superseded not in schemas


def test_chained_appends_of_several_real_processes_are_all_on_disk_in_one_valid_chain(tmp_path):
    results = race("chained", tmp_path, 3)
    assert all(not result["errors"] for result in results)
    rows = jsonl.read_chained(tmp_path / "t.jsonl", "coprepan-x/v2")      # raises if two appenders built on one predecessor
    assert len(rows) == 360
    for number in range(3):
        assert [row["i"] for row in rows if row["w"] == number] == list(range(120))


def test_a_request_log_cut_by_a_real_kill_is_a_torn_tail_and_the_chain_before_it_holds(tmp_path):
    kill_at("http", tmp_path, "request_row_torn@3")
    found = child("diagnose", tmp_path)
    assert "requests/requests.jsonl" in found["torn_tails"] and found["chain_broken_or_unreadable"] == []
    assert found["damaged"] == [] and found["classification"] == "NEEDS_REPAIR"
    assert child("repair", tmp_path)["moved_aside"] == ["requests/requests.jsonl.torn-0"]
    assert child("diagnose", tmp_path)["chain_broken_or_unreadable"] == []


# --- candidates: derived, and checked against the evidence -----------------------------------------------


def candidates_path(world):
    return world.workspace.root / "discovery" / "candidates.jsonl"


def test_the_candidate_table_is_exactly_what_events_and_requests_give(world):
    assert H.candidate_consistency(world.workspace) == {"missing": [], "unsupported": [], "different": []}
    stored = H.discovery_tables(world.workspace).candidates
    derived = H.derived_candidates(world.workspace)
    assert set(stored) == set(derived) and len(stored) >= 6
    moved = [row for row in stored.values() if row.get("discovered_via") == "permanent_redirect"]
    assert len(moved) == 1 and moved[0] in [{**option, "schema": discovery.CANDIDATE_SCHEMA} for option in derived[moved[0]["candidate_id"]]]


@pytest.mark.parametrize("which", ["listed", "redirected"])
def test_a_lost_candidate_row_is_found_and_restored_from_the_evidence_without_touching_the_rest(world, which):
    path = candidates_path(world)
    items = lines(path)
    index = next(i for i, line in enumerate(items) if (b"permanent_redirect" in line) == (which == "redirected"))
    removed = items.pop(index)
    write(path, items)
    assert H.candidate_consistency(world.workspace)["missing"] == [__import__("json").loads(removed)["candidate_id"]]
    assert recovery.diagnose(world.workspace.root, world.root)["classification"] == "INCOMPLETE_RESUMABLE"
    before = path.read_bytes()
    assert H.complete_candidates(world.workspace) == [__import__("json").loads(removed)["candidate_id"]]
    assert path.read_bytes().startswith(before)                          # appended; nothing rewritten
    assert H.candidate_consistency(world.workspace) == {"missing": [], "unsupported": [], "different": []}
    assert __import__("json").loads(lines(path)[-1]) == __import__("json").loads(removed)   # the same row the evidence gives
    assert recovery.diagnose(world.workspace.root, world.root)["classification"] == "CLEAN"


def test_a_candidate_the_evidence_does_not_support_or_contradicts_is_reported_never_completed_away(world):
    path = candidates_path(world)
    items = lines(path)
    forged = __import__("json").loads(items[0])
    forged.update(candidate_id=forged["candidate_id"][:-4] + "ffff", url_key="https://www.diario-ejemplo.test/inventado")
    items.append(canonical.line_json(forged)[:-1])
    write(path, items)
    assert H.candidate_consistency(world.workspace)["unsupported"] == [forged["candidate_id"]]
    found = recovery.diagnose(world.workspace.root, world.root)
    assert found["classification"] == "DAMAGED" and found["candidates"]["unsupported"] == 1
    assert H.complete_candidates(world.workspace) == []                   # adds what is missing; judges nothing

    items = lines(path)[:-1]
    changed = __import__("json").loads(items[2])
    changed["fetch_url"] = "https://www.diario-ejemplo.test/otro"
    items[2] = canonical.line_json(changed)[:-1]
    write(path, items)
    assert H.candidate_consistency(world.workspace)["different"] == [changed["candidate_id"]]
    assert recovery.diagnose(world.workspace.root, world.root)["classification"] == "DAMAGED"


def test_an_interrupted_pass_between_event_and_candidate_leaves_a_candidate_from_the_first_event(world):
    """The row is derived from the first event that listed the candidate, however the pass went."""
    tables = H.discovery_tables(world.workspace)
    candidate = next(iter(tables.candidates))
    first = tables.first_event_of(candidate)
    assert tables.candidates[candidate]["first_event_id"] == first["event_id"]
    assert discovery.candidate_from_event(first) == {k: v for k, v in tables.candidates[candidate].items() if k != "schema"}


# --- identity tables: derived, rebuildable, compared -----------------------------------------------------


def identity_files(iworld):
    return {name: (iworld.workspace.identity / f"{name}.jsonl").read_bytes() for name in R.TABLES}


def verify(iworld, **kwargs):
    return R.verify(iworld.workspace, iworld.registry, preservation_root=iworld.root, **kwargs)


def tree(base):
    return {p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(base.rglob("*")) if p.is_file()}


def test_the_identity_tables_equal_a_rebuild_from_the_preserved_evidence_byte_for_byte(iworld):
    report = verify(iworld)
    assert report["status"] == R.CORRECT and report["exact"] is True and report["detail"] is None
    assert report["fetches_assigned"] >= 6 and report["differences"] == {"missing_from_existing": {}, "not_supported_by_evidence": {}}
    assert recovery.diagnose(iworld.workspace.root, iworld.root, registry=iworld.registry)["classification"] == "CLEAN"


def test_a_rebuild_is_deterministic_needs_no_network_and_writes_nothing_that_is_preserved(iworld, monkeypatch, tmp_path):
    before = {"root": tree(iworld.root), "layers": tree(iworld.workspace.layers), "packs": tree(iworld.workspace.packs)}

    def forbidden(*args, **kwargs):
        raise AssertionError("a rebuild opened a socket")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir(), second.mkdir()
    R.derive(iworld.workspace, iworld.registry, preservation_root=iworld.root, target=first)
    R.derive(iworld.workspace, iworld.registry, preservation_root=iworld.root, target=second)
    for name in R.TABLES:
        assert (first / f"{name}.jsonl").read_bytes() == (second / f"{name}.jsonl").read_bytes() == identity_files(iworld)[name]
    assert verify(iworld)["status"] == R.CORRECT
    assert before == {"root": tree(iworld.root), "layers": tree(iworld.workspace.layers), "packs": tree(iworld.workspace.packs)}
    with pytest.raises(R.RebuildRefused, match="already holds tables"):
        R.derive(iworld.workspace, iworld.registry, preservation_root=iworld.root, target=first)   # a rebuild writes a new store


def test_deleted_identity_tables_are_rebuilt_exactly_and_the_old_directory_is_kept_aside(iworld):
    expected = identity_files(iworld)
    os.replace(iworld.workspace.identity, iworld.base / "gone_by_accident")
    assert verify(iworld)["status"] == R.REBUILDABLE
    found = recovery.diagnose(iworld.workspace.root, iworld.root, registry=iworld.registry)
    assert found["classification"] == "INCOMPLETE_RESUMABLE" and found["identity_rebuild"]["status"] == R.REBUILDABLE
    report = R.adopt(iworld.workspace, iworld.registry, preservation_root=iworld.root)
    assert report["adopted"] is True and report["moved_aside"] is None and identity_files(iworld) == expected
    assert R.adopt(iworld.workspace, iworld.registry, preservation_root=iworld.root)["adopted"] is False   # the second time is a no-op
    assert recovery.diagnose(iworld.workspace.root, iworld.root, registry=iworld.registry)["classification"] == "CLEAN"


@pytest.mark.parametrize("table", ["documents", "observations", "versions", "relations"])
def test_a_missing_row_is_rebuildable_and_the_replaced_directory_is_not_deleted(iworld, table):
    expected = identity_files(iworld)
    path = iworld.workspace.identity / f"{table}.jsonl"
    items = lines(path)
    removed = items.pop(len(items) // 2)
    write(path, items)
    report = verify(iworld)
    assert report["status"] == R.REBUILDABLE and report["differences"]["missing_from_existing"][table] >= 1
    adopted = R.adopt(iworld.workspace, iworld.registry, preservation_root=iworld.root)
    assert adopted["moved_aside"] == "identity.replaced-0" and identity_files(iworld) == expected
    assert removed + b"\n" not in (iworld.workspace.root / "identity.replaced-0" / f"{table}.jsonl").read_bytes()   # kept as it was found
    assert recovery.diagnose(iworld.workspace.root, iworld.root, registry=iworld.registry)["classification"] == "CLEAN"


@pytest.mark.parametrize("table, damage", [
    ("observations", "bit"),            # a changed value in a readable row
    ("documents", "contradiction"),     # a second, different row for a known document
    ("relations", "wrong_relation"),    # a relation to the wrong document
    ("versions", "bit"),
])
def test_a_row_the_evidence_does_not_support_makes_the_tables_conflicting_and_a_person_decides(iworld, table, damage):
    expected = identity_files(iworld)
    path = iworld.workspace.identity / f"{table}.jsonl"
    items = lines(path)
    if damage == "bit":
        text = items[1].decode("utf-8")
        position = next(i for i in range(text.rindex('"schema"') - 1, 20, -1) if text[i] in "abcdef" and text[i - 1] != "\\")
        items[1] = (text[:position] + ("a" if text[position] != "a" else "b") + text[position + 1:]).encode("utf-8")
    elif damage == "contradiction":
        row = __import__("json").loads(items[0])
        row["url_key"] = "https://www.diario-ejemplo.test/otro"
        items.append(canonical.line_json(row)[:-1])
    else:
        row = __import__("json").loads(items[0])
        row["target_document_id"] = row["document_id"].replace("doc:", "doc:0")[:-1]
        items[0] = canonical.line_json(row)[:-1]
    write(path, items)
    report = verify(iworld)
    assert report["status"] == R.CONFLICTING and report["differences"]["not_supported_by_evidence"]
    found = recovery.diagnose(iworld.workspace.root, iworld.root, registry=iworld.registry)
    assert found["classification"] == "DAMAGED" and "conflict with the preserved evidence" in " ".join(found["damaged"])
    changed = identity_files(iworld)
    with pytest.raises(R.RebuildRefused, match="a person decides"):
        R.adopt(iworld.workspace, iworld.registry, preservation_root=iworld.root)
    assert identity_files(iworld) == changed                              # nothing happened
    adopted = R.adopt(iworld.workspace, iworld.registry, preservation_root=iworld.root, replace_conflicting=True)
    assert adopted["adopted"] is True and identity_files(iworld) == expected
    assert (iworld.workspace.root / "identity.replaced-0" / f"{table}.jsonl").read_bytes() == changed[table]   # the conflicting store is kept


def test_a_torn_identity_tail_is_unreadable_tables_and_both_ways_back_end_in_the_same_bytes(iworld):
    expected = identity_files(iworld)
    with open(iworld.workspace.identity / "versions.jsonl", "ab") as handle:
        handle.write(b'{"schema": "coprepan-document-vers')
    report = verify(iworld)
    assert report["status"] == R.REBUILDABLE and "unreadable" in report["detail"]
    found = recovery.diagnose(iworld.workspace.root, iworld.root, registry=iworld.registry)
    assert found["classification"] == "NEEDS_REPAIR"
    recovery.repair(iworld.workspace.root)                                # the cheap way: cut the tail …
    assert identity_files(iworld) == expected and verify(iworld)["status"] == R.CORRECT
    with open(iworld.workspace.identity / "versions.jsonl", "ab") as handle:
        handle.write(b'{"schema": "coprepan-document-vers')
    R.adopt(iworld.workspace, iworld.registry, preservation_root=iworld.root)   # … or the other: rebuild
    assert identity_files(iworld) == expected


@pytest.mark.parametrize("damage", ["pack_master", "index_master", "pack_manifest_gone", "index_manifest_gone"])
def test_with_damaged_source_evidence_nothing_is_rebuilt_and_no_success_is_claimed(iworld, damage):
    from coprepan import preservation as P
    manifests = {"pack_master": ("raw", True), "index_master": ("raw_index", True), "pack_manifest_gone": ("raw", False),
                 "index_manifest_gone": ("raw_index", False)}
    area, keep_manifest = manifests[damage]
    manifest = P.read_manifest(iworld.root, area, iworld.pack_id)
    if keep_manifest:
        data = bytearray((iworld.root / manifest["relative_path"]).read_bytes())
        data[len(data) // 2] ^= 0xFF
        (iworld.root / manifest["relative_path"]).write_bytes(bytes(data))
    else:
        os.replace(iworld.root / P.manifest_relative_path(area, iworld.pack_id), iworld.base / "manifest_moved_away.json")
    expected = identity_files(iworld)
    report = verify(iworld)
    assert report["status"] == R.SOURCE_EVIDENCE_DAMAGED and report["detail"]
    found = recovery.diagnose(iworld.workspace.root, iworld.root, registry=iworld.registry)
    assert found["classification"] == "DAMAGED" and "evidence is damaged" in " ".join(found["damaged"])
    for attempt in (lambda: R.adopt(iworld.workspace, iworld.registry, preservation_root=iworld.root),
                    lambda: R.adopt(iworld.workspace, iworld.registry, preservation_root=iworld.root, replace_conflicting=True)):
        with pytest.raises(R.RebuildRefused, match="does not verify"):
            attempt()
    assert identity_files(iworld) == expected and not list(iworld.workspace.root.glob("identity.*"))   # not even a staging directory


def test_identity_tables_deleted_and_the_evidence_damaged_is_not_rebuilt_either(iworld):
    from coprepan import preservation as P
    os.replace(iworld.workspace.identity, iworld.base / "identity_moved_away")
    manifest = P.read_manifest(iworld.root, "raw", iworld.pack_id)
    path = iworld.root / manifest["relative_path"]
    path.write_bytes(path.read_bytes()[:-30])
    with pytest.raises(R.RebuildRefused):
        R.adopt(iworld.workspace, iworld.registry, preservation_root=iworld.root)
    assert not iworld.workspace.identity.exists()


def test_a_rebuild_covers_what_is_preserved_and_leaves_out_a_fetch_the_ledger_has_not_yet_preserved(tmp_path):
    """The state of a workspace killed between the two halves of a promotion: not damage, not yet preserved."""
    kill_at("pipeline", tmp_path, "before_raw_preserved")
    found = child("diagnose_full", tmp_path)
    assert found["identity_rebuild"]["status"] == R.CORRECT and found["classification"] == "INCOMPLETE_RESUMABLE"
    assert found["identity_rebuild"]["fetches_assigned"] == 0                # nothing is RAW_PRESERVED yet: nothing to derive


# --- real kills during a rebuild ---------------------------------------------------------------------------


@pytest.fixture
def finished(tmp_path):
    child("pipeline", tmp_path)
    return tmp_path, child("state", tmp_path)


def test_a_rebuild_killed_half_way_changes_nothing_that_is_believed_and_is_completed_by_the_next_one(finished):
    base, reference = finished
    os.replace(base / "workspace" / "identity", base / "identity_moved_away")      # something to rebuild
    kill_at("adopt", base, "adopt_mid_derive@3")
    found = child("diagnose_full", base)
    assert found["damaged"] == [] and found["identity_rebuild"]["status"] == R.REBUILDABLE
    assert found["classification"] == "INCOMPLETE_RESUMABLE"
    leftovers = found["leftovers"]["identity_rebuilds"]
    assert leftovers and all(name.startswith("identity.rebuild-") for name in leftovers)   # named, never read as data
    assert child("verify", base)["status"] == R.REBUILDABLE                      # the half-built store is not mistaken for tables
    adopted = child("adopt", base)
    assert adopted["adopted"] is True
    again = child("state", base)
    assert {k: again[k] for k in ("ledger", "identity", "layers", "masters")} == {k: reference[k] for k in ("ledger", "identity", "layers", "masters")}
    assert child("adopt", base)["adopted"] is False
    final = child("diagnose_full", base)
    assert final["classification"] == "CLEAN" and final["identity_rebuild"]["exact"] is True


def test_an_identity_store_moved_aside_by_an_interrupted_adoption_is_found_again_by_the_next_one(finished):
    base, _ = finished
    items = lines(base / "workspace" / "identity" / "versions.jsonl")
    write(base / "workspace" / "identity" / "versions.jsonl", items[:-2])
    kill_at("adopt", base, "adopt_after_move_aside")
    assert not (base / "workspace" / "identity").exists() and (base / "workspace" / "identity.replaced-0").is_dir()
    assert child("verify", base)["status"] == R.REBUILDABLE
    assert child("adopt", base)["adopted"] is True
    assert (base / "workspace" / "identity.replaced-0").is_dir() and child("verify", base)["status"] == R.CORRECT


# --- the newest row: anchored by the heads recorded when a run closes -------------------------------------


def change_last_row(path):
    items = lines(path)
    text = items[-1].decode("utf-8")
    position = next(i for i in range(10, text.rindex('"schema"')) if text[i] in "0123456789")
    items[-1] = (text[:position] + str((int(text[position]) + 1) % 10) + text[position + 1:]).encode("utf-8")
    write(path, items)


def test_a_closed_run_records_the_head_of_every_chained_table_and_the_ledger(world):
    run = next((world.workspace.root / "runs").iterdir()).name
    result = __import__("coprepan.acquisition", fromlist=["x"]).read_run_result(world.workspace.root, run)
    assert result["schema"] == "coprepan-acquisition-run-result/v2"
    heads = result["evidence_heads"]
    assert set(heads) == {"ledgers/preservation.jsonl", "requests/requests.jsonl", "discovery/inputs.jsonl", "discovery/events.jsonl",
                          "discovery/qualifications.jsonl"}                  # labels were written after this run closed
    assert evidence.mismatches(world.workspace.root, heads) == []
    for relative, head in heads.items():
        assert head["rows"] == len(lines(world.workspace.root / relative))


@pytest.mark.parametrize("relative", ["ledgers/preservation.jsonl", "requests/requests.jsonl", "discovery/inputs.jsonl",
                                      "discovery/events.jsonl", "discovery/qualifications.jsonl"])
def test_a_change_to_the_newest_row_of_a_closed_run_is_detected_too(world, relative):
    change_last_row(world.workspace.root / relative)
    found = recovery.diagnose(world.workspace.root, world.root)
    assert found["classification"] == "DAMAGED"
    assert found["evidence_heads_that_do_not_hold"] or relative in found["chain_broken_or_unreadable"] or found["unreadable"]


@pytest.mark.parametrize("relative", ["requests/requests.jsonl", "discovery/events.jsonl", "ledgers/preservation.jsonl"])
def test_complete_rows_cut_from_the_end_of_a_closed_table_are_detected(world, relative):
    path = world.workspace.root / relative
    write(path, lines(path)[:-2])                                           # whole lines gone: the chain alone cannot tell
    found = recovery.diagnose(world.workspace.root, world.root)
    assert found["classification"] == "DAMAGED" and any(relative in line for line in found["evidence_heads_that_do_not_hold"])


def test_rows_appended_after_a_close_do_not_disturb_the_anchor_and_are_the_documented_unanchored_tail(world):
    labels = world.workspace.root / "admission" / "labels.jsonl"            # written after the run closed
    change_last_row(labels)
    assert recovery.diagnose(world.workspace.root, world.root)["classification"] == "CLEAN"   # not noticed until the next close …
    jsonl.append_chained(world.workspace.root / "requests" / "requests.jsonl", H.REQUEST_LOG_SCHEMA,
                         {"event": "FINISHED", "request_id": "rq1:later", "url": "https://www.diario-ejemplo.test/x", "fetch_kind": "item"})
    assert recovery.diagnose(world.workspace.root, world.root)["classification"] == "CLEAN"   # … and appending is not a violation
