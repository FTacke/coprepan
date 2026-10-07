"""No false success: every state that claims something is attacked where the claim rests
(decision CPD-0009 §3).

    RAW_PRESERVED     ⇒ verified preserved bytes exist
    document version  ⇒ its preserved raw and its extraction layer exist and verify
    sealed            ⇒ the pack is structurally whole and manifest, index and pack agree
    promoted          ⇒ the target verifies; nothing else was overwritten
    304               ⇒ names a body that is preserved, with that hash
    replay            ⇒ every byte it used verified

Each test breaks the right-hand side on purpose and requires the system to refuse — never to
carry on with a quiet substitute. Also here: torn and corrupt files, simulated filesystem faults,
schema versions the code does not know, and generated sequences. In-process tests; the tests
with real process kills are in ``test_crash_recovery.py``.
"""

import errno
import json
import os
import random
from datetime import datetime, timedelta, timezone

import pytest

from coprepan import acquisition, analysis_contract, canonical, core_pipeline as C, discovery, document_identity, extraction
from coprepan import http_acquisition as H, identity, jsonl, layer_store, ledger as L, pack, preservation as P, recovery, schedule
from coprepan.registry import RegistryError, validate_registry
from support_http import LocalSite, Response
from test_core_pipeline import OUTLET, Canary
from test_offline_e2e import HTML, Pass, T0, fx, script
from test_refetch_e2e import ARTICLE_PATH, later, records_of

PACK = "pk1-uy_diario_ejemplo-20261007-000"
V1 = fx("canary/nota_v1.html")


@pytest.fixture
def done(tmp_path):
    return Canary(tmp_path).all()


@pytest.fixture
def site():
    with LocalSite() as server:
        script(server)
        yield server


def flip(path, offset=None):
    data = bytearray(path.read_bytes())
    position = len(data) // 2 if offset is None else offset
    data[position] ^= 0xFF
    path.write_bytes(bytes(data))


def master(canary, area="raw"):
    return canary.root / P.read_manifest(canary.root, area, PACK)["relative_path"]


def diagnose(canary):
    return recovery.diagnose(canary.workspace.root, canary.root)


# --- RAW_PRESERVED ⇒ verified preserved bytes --------------------------------------------------------


@pytest.mark.parametrize("damage", ["flip_pack", "flip_index", "truncate_pack", "manifest_gone"])
def test_a_preserved_fetch_whose_master_no_longer_verifies_is_never_read_as_preserved(done, damage):
    if damage == "flip_pack":
        flip(master(done))
    elif damage == "flip_index":
        flip(master(done, "raw_index"))
    elif damage == "truncate_pack":
        master(done).write_bytes(master(done).read_bytes()[:-40])
    else:
        os.replace(done.root / P.manifest_relative_path("raw", PACK), done.root / "moved_away.json")
    fetch = done.results[0]["fetch_id"]
    for attempt in (done.derive, lambda: C.replay_extraction(done.workspace, preservation_root=done.root, identifier=PACK, fetch_id=fetch),
                    lambda: C.open_preserved_pack(done.root, PACK)):
        with pytest.raises((P.PreservationError, C.NotPreserved)):
            attempt()
    found = diagnose(done)
    assert found["classification"] == "DAMAGED" and found["ledger_and_packs"]["preserved_but_master_does_not_verify"] == 8


def test_no_fetch_becomes_preserved_when_a_master_does_not_verify_after_promotion(tmp_path, monkeypatch):
    canary = Canary(tmp_path)
    canary.acquire()
    real = P.verify_master
    monkeypatch.setattr(P, "verify_master", lambda root, area, object_id: False if area == "raw_index" else real(root, area, object_id))
    with pytest.raises(P.PreservationError, match="raw_index master does not verify"):
        canary.preserve()
    assert set(canary.workspace.ledger().states().values()) == {"PRESERVATION_PENDING", "FETCH_FAILED"}   # pending is not preserved


def test_a_fetch_the_ledger_never_finished_blocks_nothing_and_is_reconciled_from_the_pack(tmp_path, monkeypatch):
    """Killed between the pack append and the ledger: the bytes are evidence, the ledger catches up."""
    canary = Canary(tmp_path)
    real, calls = L.Ledger.transition, []

    def dying(self, subject, new_state, **kwargs):
        if new_state == "FETCHED" and len(calls) == 2:
            raise KeyboardInterrupt("killed")
        calls.append(new_state) if new_state == "FETCHED" else None
        return real(self, subject, new_state, **kwargs)
    monkeypatch.setattr(L.Ledger, "transition", dying)
    with pytest.raises(KeyboardInterrupt):
        canary.acquire()
    monkeypatch.undo()
    assert diagnose(canary)["ledger_and_packs"]["in_pack_ledger_planned"] == 1
    canary.items = canary.items[:3]           # a real run cannot repeat the exchange: it is gone
    canary.preserve()
    states = canary.workspace.ledger().states()
    assert set(states.values()) == {"RAW_PRESERVED"} and len(states) == 3
    reconciled = [r for r in canary.workspace.ledger().records() if r.details.get("reconciled_from_pack")]
    assert len(reconciled) == 1 and reconciled[0].new_state == "FETCHED"
    assert len(canary.derive()) == 3          # one unfinished ledger entry no longer blocks the whole pack


def test_the_ledger_claiming_bytes_no_pack_holds_is_reported_as_lost_evidence(tmp_path):
    canary = Canary(tmp_path)
    canary.acquire()
    book = canary.workspace.ledger()
    ghost = identity.fetch_id("https://www.diario-ejemplo.test/fantasma", T0, "0" * 64)
    for state in ("DISCOVERED", "FETCH_PLANNED", "FETCHED"):
        book.transition(ghost, state, at=T0)
    found = diagnose(canary)
    assert found["classification"] == "DAMAGED" and found["ledger_and_packs"]["ledger_claims_bytes_no_pack_has"] == 1
    assert any("EVIDENCE LOST" in line for line in found["damaged"])


# --- document version ⇒ preserved raw and verifying extraction layer ---------------------------------


@pytest.mark.parametrize("damage", ["payload_changed", "payload_gone", "manifest_changed", "marker_gone"])
def test_a_version_whose_extraction_layer_is_damaged_is_reported_and_not_silently_rebuilt(done, damage):
    version = sorted(document_identity.IdentityTables(done.workspace.identity).versions.values(), key=lambda r: r["document_version_id"])[0]
    slot = done.workspace.layers / "extraction" / version["extraction_fingerprint"][:2] / version["extraction_fingerprint"]
    artifact = next(slot.iterdir())
    if damage == "payload_changed":
        flip(artifact / "payload")
    elif damage == "payload_gone":
        os.replace(artifact / "payload", done.workspace.root / "payload_moved_away")
    elif damage == "manifest_changed":
        flip(artifact / "manifest.json")
    else:
        os.replace(artifact / "PROMOTED", done.workspace.root / "marker_moved_away")   # bytes and metadata, no marker: not an answer
    found = diagnose(done)
    assert found["classification"] == "DAMAGED"
    assert version["document_version_id"] in found["identity"]["versions_without_verifying_extraction"]
    before = sorted(str(p.relative_to(slot)) for p in slot.rglob("*"))
    with pytest.raises(layer_store.LayerStoreError):
        done.derive()                         # refused: a damaged answer is neither used nor quietly replaced
    assert sorted(str(p.relative_to(slot)) for p in slot.rglob("*")) == before


def test_a_stored_extraction_of_another_schema_or_extractor_is_not_reinterpreted(done, monkeypatch):
    monkeypatch.setattr(extraction, "EXTRACTION_SCHEMA", "coprepan-extraction/v2")   # the code moved on; the stored layer did not
    with pytest.raises(layer_store.LayerStoreError, match="not reinterpreted"):
        done.derive()


# --- sealed ⇒ structurally whole; manifest, index and pack agree --------------------------------------


def rewrite_index(directory, mutate):
    index, manifest = directory / f"{PACK}.index.jsonl", directory / f"{PACK}.pack.json"
    rows = [json.loads(line) for line in index.read_bytes().split(b"\n")[:-1]]
    data = b"".join(canonical.line_json(row) for row in mutate(rows))
    index.write_bytes(data)
    record = json.loads(manifest.read_text(encoding="utf-8"))
    record["index_sha256"] = canonical.sha256_bytes(data)       # the attacker keeps the manifest consistent with the index
    manifest.write_bytes(canonical.record_json(record))


@pytest.mark.parametrize("mutate, message", [
    (lambda rows: rows[:-1], "does not fit the pack"),                                             # an entry missing
    (lambda rows: rows + [dict(rows[0], fetch_id="ft1:" + "0" * 64)], "does not fit the pack"),    # an entry too many
    (lambda rows: [dict(rows[0], response_offset=rows[0]["response_offset"] + 1)] + rows[1:], "does not fit the pack"),
    (lambda rows: [dict(rows[0], response_length=rows[0]["response_length"] - 5)] + rows[1:], "does not fit the pack"),
    (lambda rows: [dict(rows[0], body_sha256="f" * 64)] + rows[1:], "does not fit the pack"),
    (lambda rows: list(reversed(rows)), "does not fit the pack"),
])
def test_an_index_that_does_not_fit_its_pack_is_refused_even_with_a_consistent_manifest(tmp_path, mutate, message):
    canary = Canary(tmp_path)
    canary.acquire()
    pack.seal(canary.workspace.packs, PACK, sealed_at=T0)
    rewrite_index(canary.workspace.packs, mutate)
    with pytest.raises(pack.PackError, match=message):
        pack.verify_sealed(canary.workspace.packs, PACK)
    with pytest.raises(pack.PackError):
        canary.preserve()                                           # sealing again re-verifies; nothing is promoted
    assert list(canary.root.rglob("*.warc.gz")) == []


def test_reading_through_a_wrong_index_entry_never_returns_another_fetchs_bytes(done):
    preserved = C.open_preserved_pack(done.root, PACK)
    first, second = [entry for entry in preserved.entries.values() if entry.body_sha256][:2]
    crossed = pack.PackEntry(**{**first.__dict__, "response_offset": second.response_offset, "response_length": second.response_length})
    with pytest.raises(pack.PackError, match="does not fit the bytes"):
        pack.read_body(preserved.path, crossed)
    crossed = pack.PackEntry(**{**first.__dict__, "metadata_offset": second.metadata_offset, "metadata_length": second.metadata_length})
    with pytest.raises(pack.PackError, match="points at another record"):
        pack.read_fetch_record(preserved.path, crossed)


def test_a_pack_that_changes_while_it_is_sealed_is_not_given_a_manifest(tmp_path, monkeypatch):
    canary = Canary(tmp_path)
    canary.acquire()
    real = pack.write_bytes_atomic

    def tampering(final, data):
        real(final, data)
        if str(final).endswith(".index.jsonl"):                      # between the scan and the manifest
            with open(canary.workspace.packs / f"{PACK}.warc.gz", "ab") as handle:
                handle.write(b"\x00" * 16)
    monkeypatch.setattr(pack, "write_bytes_atomic", tampering)
    with pytest.raises(pack.PackError):
        pack.seal(canary.workspace.packs, PACK, sealed_at=T0)
    assert not (canary.workspace.packs / f"{PACK}.pack.json").exists()


@pytest.mark.parametrize("tail", [b"\x1f\x8b\x08\x00garbage-that-is-not-a-member", b"plain garbage", b"\x00" * 64])
def test_an_open_pack_with_a_valid_prefix_and_a_garbage_tail_is_cut_back_and_loses_nothing(tmp_path, tail):
    canary = Canary(tmp_path)
    canary.acquire()
    path = canary.workspace.packs / f"{PACK}.warc.gz.open"
    whole = path.read_bytes()
    with open(path, "ab") as handle:
        handle.write(tail)
    with pytest.raises(pack.PackTornTail):
        pack.scan(path, PACK)
    assert recovery.diagnose(canary.workspace.root)["packs"][PACK]["state"] == "OPEN_TORN_TAIL"
    moved = recovery.repair(canary.workspace.root)["moved_aside"]
    assert moved == [f"packs/{PACK}.warc.gz.open.torn-0"]
    assert path.read_bytes() == whole and (canary.workspace.root / moved[0]).read_bytes() == tail
    assert len(pack.scan(path, PACK)) == 9


# --- promoted ⇒ the target verifies; nothing else was overwritten ------------------------------------


def source_and_root(tmp_path, content=b"sealed pack bytes " * 500):
    source, root = tmp_path / "source.bin", tmp_path / "root"
    source.write_bytes(content)
    root.mkdir()
    return source, root, canonical.sha256_bytes(content)


def promote(source, root, sha256, object_id="obj"):
    return P.promote(source, root=root, area="raw", object_id=object_id, relative_path=f"uy/{object_id}.bin", declared_sha256=sha256, now=T0)


def test_a_source_that_changes_after_it_was_validated_is_not_promoted(tmp_path, monkeypatch):
    source, root, sha256 = source_and_root(tmp_path)
    real, seen = P.sha256_file, []

    def hashing(path):
        result = real(path)
        if path == source and not seen:
            seen.append(1)
            source.write_bytes(source.read_bytes()[:-1] + b"X")       # changed between validation and copy
        return result
    monkeypatch.setattr(P, "sha256_file", hashing)
    with pytest.raises(P.HashMismatch, match="landed bytes"):
        promote(source, root, sha256)
    assert [p for p in root.rglob("*") if p.is_file()] == []           # no master, no manifest, no staging file


def test_a_master_that_appears_during_the_promotion_is_never_overwritten(tmp_path, monkeypatch):
    source, root, sha256 = source_and_root(tmp_path)
    destination = root / "preservation" / "raw" / "uy" / "obj.bin"
    real = P.publish_exclusive

    def somebody_else_first(staging, final):
        final.write_bytes(b"another process's different artefact")      # lands between the check and the rename
        return real(staging, final)
    monkeypatch.setattr(P, "publish_exclusive", somebody_else_first)
    with pytest.raises(P.IdentityConflict, match="taken by other bytes"):
        promote(source, root, sha256)
    assert destination.read_bytes() == b"another process's different artefact"   # theirs stands
    assert P.read_manifest(root, "raw", "obj") is None and list(root.rglob("*.part-*")) == []


def test_an_identity_bound_by_another_process_during_the_promotion_is_a_conflict_or_the_same_promotion(tmp_path, monkeypatch):
    source, root, sha256 = source_and_root(tmp_path)
    real = P.write_bytes_exclusive

    def bound_meanwhile(other_sha):
        def writer(final, data):
            record = json.loads(data)
            record["sha256"] = other_sha
            real(final, canonical.record_json(record))                 # the other process's manifest is there first
            return real(final, data)
        return writer
    monkeypatch.setattr(P, "write_bytes_exclusive", bound_meanwhile("e" * 64))
    with pytest.raises(P.IdentityConflict, match="bound to sha256 e"):
        promote(source, root, sha256)
    second = tmp_path / "second"
    second.mkdir()
    source2, root2, sha2 = source_and_root(second)
    monkeypatch.setattr(P, "write_bytes_exclusive", bound_meanwhile(sha2))
    assert promote(source2, root2, sha2).action == "already_preserved"  # the same content: the same promotion


@pytest.mark.parametrize("fault", [errno.ENOSPC, errno.EACCES, errno.EROFS])
def test_a_target_that_refuses_the_write_leaves_nothing_behind_and_a_retry_succeeds(tmp_path, monkeypatch, fault):
    source, root, sha256 = source_and_root(tmp_path)

    def refusing(reader, writer, length=0):
        writer.write(reader.read(64))
        raise OSError(fault, os.strerror(fault))
    with monkeypatch.context() as patched:
        patched.setattr(P.shutil, "copyfileobj", refusing)
        with pytest.raises(P.PreservationError) as caught:
            promote(source, root, sha256)
    assert caught.value.__cause__.errno == fault and not isinstance(caught.value, P.ContentRefusal)
    assert [p for p in root.rglob("*") if p.is_file()] == []
    assert promote(source, root, sha256).action == "promoted" and P.verify_master(root, "raw", "obj")


def test_a_refused_rename_and_a_vanished_source_are_io_failures_not_successes(tmp_path, monkeypatch):
    source, root, sha256 = source_and_root(tmp_path)
    with monkeypatch.context() as patched:
        patched.setattr(P, "publish_exclusive", lambda staging, final: (_ for _ in ()).throw(PermissionError("rename refused")))
        with pytest.raises(P.PreservationError):
            promote(source, root, sha256)
    assert [p for p in root.rglob("*") if p.is_file()] == []
    real = P.sha256_file

    def vanishing(path):
        result = real(path)
        if path == source:
            os.replace(source, tmp_path / "gone.bin")
        return result
    with monkeypatch.context() as patched:
        patched.setattr(P, "sha256_file", vanishing)
        with pytest.raises(P.PreservationError):
            promote(source, root, sha256)
    assert [p for p in root.rglob("*") if p.is_file()] == []


def test_a_manifest_cannot_claim_bytes_that_are_absent(done):
    os.replace(master(done), done.root / "master_moved_away.bin")
    assert P.verify_master(done.root, "raw", PACK) is False
    with pytest.raises(P.PreservationError, match="does not verify"):
        C.open_preserved_pack(done.root, PACK)
    assert done.preserve().action == "repaired"                         # the workspace still holds the sealed pack: landed again
    assert P.verify_master(done.root, "raw", PACK)


# --- 304 ⇒ a preserved body with that hash -----------------------------------------------------------


def test_a_304_is_believed_only_while_the_body_it_names_is_preserved_and_verifies(tmp_path, site):
    site.routes[ARTICLE_PATH] = Response(200, HTML, V1, etag='"v1"')
    first = Pass(tmp_path, site).all()
    site._served.clear()
    second = Pass(tmp_path, site, start=T0 + timedelta(days=8))
    second.acquire(), second.preserve()
    record = records_of(second, "Puerto-crecimiento")[0]
    assert record["response"]["status"] == 304
    held = first.root / P.read_manifest(first.root, "raw", first.pack_id)["relative_path"]
    flip(held)                                                           # the representation the 304 points at is damaged
    result = next(r for r in second.derive() if r["fetch_id"] == record["fetch_id"])
    assert result["identity"] == "revalidation_target_not_preserved" and result["document_version_id"] is None


def test_no_conditional_request_is_sent_for_a_body_that_was_never_preserved(tmp_path, site):
    site.routes[ARTICLE_PATH] = Response(200, HTML, V1, etag='"v1"')
    first = Pass(tmp_path, site)
    first.acquire()                                                      # answered, in an open pack, never preserved
    site._served.clear()
    site.requests.clear()
    second = Pass(tmp_path, site, start=T0 + timedelta(days=8))
    second.acquire()
    headers = [h for path, h in site.requests if path == ARTICLE_PATH][-1]
    assert "if-none-match" not in headers                                # the page is simply asked for again
    answered = [row for row in H.request_rows(second.workspace) if row["event"] == "FINISHED" and "Puerto-crecimiento" in row["url"]]
    assert [row["result"]["status"] for row in answered] == [200, 200] and answered[-1]["result"]["revalidates"] is None


def test_a_304_naming_another_hash_than_the_preserved_body_assigns_nothing(tmp_path, site):
    site.routes[ARTICLE_PATH] = Response(200, HTML, V1, etag='"v1"')
    first = Pass(tmp_path, site).all()
    held = records_of(first, "Puerto-crecimiento")[0]
    book = first.workspace.ledger()
    assert C._holds_body(book, first.root, {"fetch_id": held["fetch_id"], "body_sha256": held["body_sha256"]}) is True
    assert C._holds_body(book, first.root, {"fetch_id": held["fetch_id"], "body_sha256": "a" * 64}) is False
    assert C._holds_body(book, first.root, {"fetch_id": "ft1:" + "0" * 64, "body_sha256": held["body_sha256"]}) is False


def test_a_newer_version_arriving_between_two_revalidations_is_kept_apart(tmp_path, site):
    """200 (v1) · 304 · 200 (v2, new ETag) · 304 of v2: each 304 confirms the body it names, not "the latest"."""
    site.routes[ARTICLE_PATH] = Response(200, HTML, V1, etag='"v1"')
    first = Pass(tmp_path, site).all()
    later(first, site, 8)
    site.routes[ARTICLE_PATH] = Response(200, HTML, fx("canary/nota_v2.html"), etag='"v2"')
    third = later(first, site, 30)
    fourth = later(first, site, 60)
    tables = document_identity.IdentityTables(first.workspace.identity)
    document = next(r for r in first.results if "Puerto-crecimiento" in r.get("url_key", ""))["document_id"]
    v1, v2 = tables.versions_of(document)
    last = records_of(fourth, "Puerto-crecimiento")[0]
    assert last["response"]["status"] == 304
    assert last["revalidates"]["fetch_id"] == records_of(third, "Puerto-crecimiento")[0]["fetch_id"]
    assert (v2, last["fetch_id"]) in tables.version_observations and (v1, last["fetch_id"]) not in tables.version_observations


# --- append-only files: torn, corrupt, contradictory --------------------------------------------------


def test_a_table_with_a_valid_prefix_and_garbage_is_refused_and_only_a_torn_tail_is_repairable(tmp_path):
    path = tmp_path / "workspace" / "identity" / "documents.jsonl"
    jsonl.append_row(path, "coprepan-x/v1", {"a": 1})
    whole = path.read_bytes()
    with open(path, "ab") as handle:
        handle.write(b'{"schema": "coprepan-x/v1", "a": ')                 # a line that never ended
    with pytest.raises(jsonl.TornTail):
        jsonl.read_rows(path, "coprepan-x/v1")
    with pytest.raises(jsonl.TornTail):
        jsonl.append_row(path, "coprepan-x/v1", {"a": 2})                  # nothing is appended behind a torn line
    assert recovery.repair(tmp_path / "workspace")["moved_aside"] == ["identity/documents.jsonl.torn-0"]
    assert path.read_bytes() == whole and jsonl.read_rows(path, "coprepan-x/v1") == [{"a": 1, "schema": "coprepan-x/v1"}]
    with open(path, "ab") as handle:
        handle.write(b"complete line of garbage\n")                        # whole line, not a record: not a torn tail
    with pytest.raises(jsonl.JsonlError):
        jsonl.read_rows(path, "coprepan-x/v1")
    assert recovery.repair(tmp_path / "workspace")["moved_aside"] == []    # repair does not judge content
    found = recovery.diagnose(tmp_path / "workspace")
    assert found["classification"] == "DAMAGED" and "identity/documents.jsonl" in " ".join(found["damaged"]) + " ".join(found["unreadable"])


def test_a_short_write_or_a_full_disk_is_never_reported_as_an_appended_record(tmp_path, monkeypatch):
    book = L.Ledger(tmp_path / "ledger.jsonl", L.PRESERVATION)
    book.transition("a", "DISCOVERED", at=T0)
    real = os.write
    with monkeypatch.context() as patched:
        patched.setattr(os, "write", lambda descriptor, data: real(descriptor, data[: len(data) // 2]))   # the system took half
        with pytest.raises(L.LedgerError):
            book.transition("b", "DISCOVERED", at=T0)
    assert book.state("b") is None                                           # the state did not run ahead of the ledger
    with pytest.raises(L.LedgerTornTail):
        L.Ledger(tmp_path / "ledger.jsonl", L.PRESERVATION)
    L.quarantine_torn_tail(tmp_path / "ledger.jsonl")
    book = L.Ledger(tmp_path / "ledger.jsonl", L.PRESERVATION)
    with monkeypatch.context() as patched:
        patched.setattr(os, "write", lambda descriptor, data: (_ for _ in ()).throw(OSError(errno.ENOSPC, "no space left")))
        with pytest.raises(OSError):
            book.transition("b", "DISCOVERED", at=T0)
    assert book.state("b") is None and len(L.Ledger(tmp_path / "ledger.jsonl", L.PRESERVATION)) == 1
    book.transition("b", "DISCOVERED", at=T0)                                # and the same object can go on afterwards
    assert len(L.Ledger(tmp_path / "ledger.jsonl", L.PRESERVATION)) == 2


def test_a_ledger_object_that_did_not_see_another_writers_record_is_refused(tmp_path):
    path = tmp_path / "ledger.jsonl"
    first, second = L.Ledger(path, L.PRESERVATION), L.Ledger(path, L.PRESERVATION)
    first.transition("a", "DISCOVERED", at=T0)
    with pytest.raises(L.LedgerError, match="another writer"):
        second.transition("b", "DISCOVERED", at=T0)                          # it would have written a second "seq 0"
    assert len(L.Ledger(path, L.PRESERVATION)) == 1


def test_tables_refuse_two_different_rows_under_one_key_and_tolerate_a_repeated_row(tmp_path):
    directory = tmp_path / "identity"
    row = {"document_id": "uy_diario_ejemplo:doc:0123456789abcdef", "outlet_id": OUTLET, "url_key": "https://x.test/a",
           "url_key_ruleset": "r", "outlet_url_rules_version": "v", "first_fetch_id": "ft1:" + "0" * 64}
    jsonl.append_row(directory / "documents.jsonl", document_identity.DOCUMENT_SCHEMA, row)
    jsonl.append_row(directory / "documents.jsonl", document_identity.DOCUMENT_SCHEMA, row)       # an append that was repeated
    assert len(document_identity.IdentityTables(directory).documents) == 1
    jsonl.append_row(directory / "documents.jsonl", document_identity.DOCUMENT_SCHEMA, {**row, "url_key": "https://x.test/b"})
    with pytest.raises(jsonl.JsonlError, match="two different rows"):
        document_identity.IdentityTables(directory)                                              # never "whichever came last"
    other = tmp_path / "other"
    jsonl.append_row(other / "documents.jsonl", document_identity.DOCUMENT_SCHEMA, row)
    jsonl.append_row(other / "documents.jsonl", document_identity.DOCUMENT_SCHEMA,
                     {**row, "document_id": "uy_diario_ejemplo:doc:fedcba9876543210"})
    with pytest.raises(document_identity.DocumentIdCollision, match="filed under two ids"):
        document_identity.IdentityTables(other)
    tables = tmp_path / "discovery"
    jsonl.append_row(tables / "candidates.jsonl", discovery.CANDIDATE_SCHEMA, {"candidate_id": "c", "url_key": "u1"})
    jsonl.append_row(tables / "candidates.jsonl", discovery.CANDIDATE_SCHEMA, {"candidate_id": "c", "url_key": "u2"})
    with pytest.raises(jsonl.JsonlError):
        discovery.DiscoveryTables(tables)


def test_relations_are_completed_when_the_rows_before_them_were_already_written(done, tmp_path):
    """The state a process leaves when it dies after a version row and before its relation."""
    relations = done.workspace.identity / "relations.jsonl"
    expected = relations.read_bytes()
    os.replace(relations, tmp_path / "relations_moved_away.jsonl")
    done.derive()
    triples = lambda rows: sorted((r["relation"], r["document_id"], r["target_document_id"]) for r in rows)  # noqa: E731
    before = triples(map(json.loads, expected.split(b"\n")[:-1]))
    assert len(before) == 2 and {relation for relation, _, _ in before} == {"duplicate_of", "moved_to"}
    assert triples(jsonl.read_rows(relations, document_identity.RELATION_SCHEMA)) == before


def test_a_run_record_is_whole_or_absent_and_a_half_written_result_is_not_a_result(tmp_path):
    canary = Canary(tmp_path)
    directory = acquisition.run_directory(canary.workspace.root, canary.run.run_id)
    directory.mkdir(parents=True)
    (directory / "run.json.part-deadbeef").write_bytes(b'{"half": ')          # what a kill during the write leaves
    assert acquisition.open_run(canary.workspace.root, canary.run) is True      # the run starts; the staging file is not a record
    assert acquisition.open_run(canary.workspace.root, canary.run) is False     # and resumes
    (directory / "result.json").write_bytes(b'{"schema": "coprepan-acquisition-run-result/v1", "run_')
    with pytest.raises(acquisition.RunStateError, match="not a readable"):
        acquisition.read_run_result(canary.workspace.root, canary.run.run_id)


def test_a_new_pack_whose_first_record_never_landed_can_still_be_used(tmp_path):
    packs = tmp_path / "packs"
    packs.mkdir()
    (packs / f"{PACK}.warc.gz.open").write_bytes(b"")                          # created, killed before the first byte
    assert recovery.diagnose(tmp_path)["packs"][PACK]["state"] == "OPEN_EMPTY"
    opened = pack.OpenPack(packs, PACK, opened_at=T0)
    assert pack.scan(opened.path, PACK) == []


def test_two_objects_on_one_open_pack_cannot_both_append(tmp_path):
    canary = Canary(tmp_path)
    canary.acquire()
    first = pack.OpenPack(canary.workspace.packs, PACK, opened_at=T0)
    second = pack.OpenPack(canary.workspace.packs, PACK, opened_at=T0)
    record = acquisition.build_fetch_record(canary.run, OUTLET, canary.items[0].__class__(
        requested_url="https://www.diario-ejemplo.test/otra", fetch_started_at=T0 + timedelta(minutes=30),
        fetch_finished_at=T0 + timedelta(minutes=31), status=200, response_headers=(), body=b"<html></html>"))
    first.append(record, b"<html></html>")
    with pytest.raises(pack.PackError, match="another writer"):
        second.append(record, b"<html></html>")                                 # it would have written the fetch twice
    assert len(pack.scan(first.path, PACK)) == 10


# --- diagnose never raises and never calls a damaged workspace clean ----------------------------------


def test_diagnose_survives_any_truncation_and_never_calls_it_clean(tmp_path):
    rng = random.Random(20261008)
    base = Canary(tmp_path / "base").all()
    files = sorted(p for p in base.workspace.root.rglob("*") if p.is_file() and p.stat().st_size > 8 and p.name != ".writer.lock")
    for number in range(25):
        victim = rng.choice(files)
        original = victim.read_bytes()
        victim.write_bytes(original[: rng.randrange(1, len(original))])
        try:
            found = recovery.diagnose(base.workspace.root, base.root)       # must not raise, whatever was cut
            assert found["classification"] in ("NEEDS_REPAIR", "DAMAGED", "INCOMPLETE_RESUMABLE"), (victim.name, found["classification"])
        finally:
            victim.write_bytes(original)
    assert recovery.diagnose(base.workspace.root, base.root)["classification"] == "CLEAN"


# --- a schema or component version the code does not know is refused, not read as the known one --------


def test_artefacts_of_an_unknown_schema_version_are_explicitly_unsupported(done, tmp_path):
    def bumped(path, key="schema"):
        record = json.loads(path.read_text(encoding="utf-8"))
        record[key] = record[key].replace("/v1", "/v2")
        path.write_bytes(canonical.record_json(record))

    table = tmp_path / "t.jsonl"
    jsonl.append_row(table, "coprepan-document-identity/v2", {"document_id": "x"})
    with pytest.raises(jsonl.JsonlError, match="schema 'coprepan-document-identity/v2'"):
        jsonl.read_rows(table, document_identity.DOCUMENT_SCHEMA)
    book = tmp_path / "ledger.jsonl"
    book.write_bytes(canonical.line_json({"schema": "coprepan-ledger-record/v3", "machine": "preservation", "seq": 0, "subject": "a",
                                          "previous_state": None, "new_state": "DISCOVERED", "at": "x", "details": {}}))
    with pytest.raises(L.LedgerError):
        L.Ledger(book, L.PRESERVATION)

    packs, fetch_record = done.workspace.packs, records(done)[0]
    bumped(packs / f"{PACK}.pack.json")
    with pytest.raises(pack.PackError, match="no readable pack manifest"):
        pack.read_index(packs, PACK)
    manifest = done.root / P.manifest_relative_path("raw", PACK)
    bumped(manifest)
    with pytest.raises(P.PreservationError, match="unreadable"):
        P.read_manifest(done.root, "raw", PACK)
    with pytest.raises(acquisition.AcquisitionError):
        acquisition.validate_fetch_record({**fetch_record, "schema": "coprepan-fetch-record/v2"})
    result = acquisition.run_directory(done.workspace.root, done.run.run_id) / "result.json"
    bumped(result)
    with pytest.raises(acquisition.RunStateError):
        acquisition.read_run_result(done.workspace.root, done.run.run_id)
    with pytest.raises(RegistryError):
        validate_registry({"schema": "coprepan-outlet-registry/v2", "outlets": []})
    with pytest.raises(schedule.ScheduleNotDecided):
        policy = tmp_path / "schedule.json"
        policy.write_text(json.dumps({"schema": "coprepan-schedule-policy/v2", "status": "DECIDED"}), encoding="utf-8")
        schedule.load_schedule_policy(policy)
    assert "release: contract is not crosscorpus-analysis/v1" in " ".join(
        analysis_contract.validate({"release": dict.fromkeys(
            ("corpus_id", "release_id", "release_kind", "fixture", "modality", "created_at", "annotator_contract", "anchors",
             "vocabularies", "selection_policy", "coverage_reference", "id_stability", "layers", "tables", "compatibility",
             "manifest_sha256"), "x") | {"contract": "crosscorpus-analysis/v2", "token_denominator": "x"}}))


def records(canary):
    preserved_path = canary.workspace.packs / f"{PACK}.warc.gz"
    return [pack.read_fetch_record(preserved_path, entry) for entry in pack.read_index(canary.workspace.packs, PACK)]


def test_the_layer_manifest_and_the_extractor_version_are_part_of_what_is_stored(done):
    version = next(iter(document_identity.IdentityTables(done.workspace.identity).versions.values()))
    store = done.workspace.layer_store()
    manifest = store.manifest(extraction.STAGE, version["extraction_fingerprint"])
    assert manifest["schema"] == "coprepan-layer-manifest/v1"
    newer = extraction.Extractor("baseline_html", "0.2.0", lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    record = records(done)[0]
    assert C.extraction_fingerprint(newer, record) != C.extraction_fingerprint(extraction.BASELINE, record)   # a new version is a new question


# --- generated sequences -------------------------------------------------------------------------------


def test_any_walk_of_the_state_machine_replays_to_the_same_states_and_any_edit_of_the_file_is_refused(tmp_path):
    rng = random.Random(7)
    for round_ in range(20):
        path = tmp_path / f"ledger{round_}.jsonl"
        book, expected = L.Ledger(path, L.PRESERVATION), {}
        for step in range(rng.randrange(5, 60)):
            subject = f"s{rng.randrange(6)}"
            current = expected.get(subject)
            options = [L.PRESERVATION.initial] if current is None else sorted(L.PRESERVATION.transitions[current])
            if not options:
                continue
            expected[subject] = rng.choice(options)
            book.transition(subject, expected[subject], at=T0 + timedelta(seconds=step))
            wrong = [s for s in L.PRESERVATION.states if s not in L.PRESERVATION.transitions[expected[subject]]]
            with pytest.raises(L.IllegalTransition):
                book.transition(subject, rng.choice(wrong), at=T0)       # an illegal step never reaches the file
        assert L.Ledger(path, L.PRESERVATION).states() == expected == book.states()
        lines = path.read_bytes().split(b"\n")[:-1]
        if len(lines) < 3:
            continue
        position = rng.randrange(1, len(lines) - 1)
        for edited in (lines[:position] + lines[position + 1:],                                   # a record removed
                       lines[:position] + [lines[position]] + lines[position:],                   # a record twice
                       lines[:position - 1] + [lines[position], lines[position - 1]] + lines[position + 1:]):   # two swapped
            path.write_bytes(b"\n".join(edited) + b"\n")
            with pytest.raises(L.LedgerError):
                L.Ledger(path, L.PRESERVATION)


def test_the_candidate_lifecycle_is_total_deterministic_and_never_drops_a_candidate():
    from test_offline_e2e import SCHEDULE
    rng = random.Random(11)
    kinds = [schedule.SUCCESS, schedule.NOT_MODIFIED, schedule.NOT_FOUND, schedule.GONE, schedule.TRANSIENT_FAILURE,
             schedule.REFUSED_BY_SERVER, schedule.REDIRECT_NOT_FOLLOWED, schedule.DENIED_BY_POLICY, schedule.DEFERRED_BY_POLICY,
             schedule.MOVED_PERMANENTLY]
    never_due = {schedule.SETTLED, schedule.RETIRED, schedule.MOVED}
    for _ in range(400):
        history, at = [], T0
        for _ in range(rng.randrange(0, 12)):
            at += timedelta(seconds=rng.randrange(1, 5_000_000))
            kind = rng.choice(kinds)
            history.append(schedule.Outcome(kind, at, body_sha256=rng.choice(["a" * 64, "b" * 64, None]), fetch_id="ft1:" + "0" * 64,
                                            etag=rng.choice([None, '"x"']), policy_version=rng.choice(["p1", "p2"]),
                                            not_before=rng.choice([None, at + timedelta(hours=3)]), moved_to="c2"))
        one = schedule.lifecycle("c", T0, history, SCHEDULE, current_policy_version="p1")
        assert one == schedule.lifecycle("c", T0, list(history), SCHEDULE, current_policy_version="p1")
        assert one.state in schedule.STATES and one.attempts == len(history)
        assert (one.due_at is None) == (one.state in never_due)
        if history and one.due_at is not None and one.state != schedule.NEVER_FETCHED:
            assert one.due_at >= history[-1].at or one.state == schedule.DENIED   # never due before its own last answer


def test_canonical_url_keys_are_fixed_points_and_fold_only_what_the_rules_name():
    rng = random.Random(3)
    rules = identity.OutletUrlRules(outlet_id=OUTLET, web_origins=("https://www.diario-ejemplo.test", "https://m.diario-ejemplo.test"),
                                    version="rules/1", significant_query_params=("id",), strip_path_prefixes=("/amp",), strip_path_suffixes=())
    for _ in range(300):
        path = "/" + "/".join(rng.choice(["Economia", "economia", "a-b", "x_y", "%C3%B1", "nota.html", "2026"]) for _ in range(rng.randrange(1, 5)))
        query = "&".join(rng.sample(["utm_source=rss", "id=7", "ref=x", "fbclid=1", "id=8"], rng.randrange(0, 4)))
        url = rng.choice(rules.web_origins) + rng.choice(["", "/amp"]) + path + ("?" + query if query else "") + rng.choice(["", "#top"])
        key = identity.canonical_url_key(rules, requested_url=url).key
        assert identity.canonical_url_key(rules, requested_url=key).key == key              # idempotent
        assert "#" not in key and "utm_source" not in key and "fbclid" not in key
        assert ("Economia" in key) == ("Economia" in path)                                  # the path's case is kept
        assert identity.document_id(OUTLET, key) == identity.document_id(OUTLET, identity.canonical_url_key(rules, requested_url=url).key)
