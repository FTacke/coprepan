"""Promotion semantics and the outage spool, on temporary directories (Phase-1 gate, first half).

Covers: atomic promotion, idempotence, repair, identity conflict, duplicates, crash recovery, the
absence of a deletion path, and the spool's bounds and routing rules.
"""

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from coprepan import outage_spool as O
from coprepan import preservation as P
from coprepan.storage_roots import StorageRefusal, StorageRootUnreachable

NOW = datetime(2026, 10, 7, 19, 30, 0, tzinfo=timezone.utc)
AREA = "raw"
REL = "uy/uy_el_pais/pack-2026-10-07.warc.gz"
MASTER = Path("preservation") / "raw" / "uy" / "uy_el_pais" / "pack-2026-10-07.warc.gz"
SRC = Path(P.__file__).parent


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def root(tmp_path):
    path = tmp_path / "preservation_root"
    path.mkdir()
    return path


@pytest.fixture
def pack(tmp_path):
    path = tmp_path / "workspace" / "sealed.warc.gz"
    path.parent.mkdir()
    path.write_bytes(b"sealed pack bytes " * 1000)
    return path


def promote(source, root, object_id="pack-a", relative_path=REL, declared=None, **kwargs):
    declared = declared or sha(source.read_bytes())
    return P.promote(source, root=root, area=AREA, object_id=object_id, relative_path=relative_path,
                     declared_sha256=declared, now=NOW, **kwargs)


def tree(root):
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())


# --- promotion ------------------------------------------------------------------------------------


def test_promotion_lands_a_verified_master_and_a_manifest(root, pack):
    result = promote(pack, root, details={"outlet_id": "uy_el_pais"})
    data = pack.read_bytes()
    assert (result.action, result.state) == ("promoted", "RAW_PRESERVED")
    assert (root / MASTER).read_bytes() == data
    assert tree(root) == ["preservation/manifests/raw/pack-a.json", MASTER.as_posix()]
    assert json.loads(result.manifest_path.read_text(encoding="utf-8")) == {
        "schema": "coprepan-preservation-manifest/v1",
        "policy_version": "preservation/v1",
        "object_id": "pack-a",
        "area": "raw",
        "state": "RAW_PRESERVED",
        "relative_path": MASTER.as_posix(),
        "sha256": sha(data),
        "size_bytes": len(data),
        "data_class": "acquisition_source",
        "preserved_at": "2026-10-07T19:30:00.000000Z",
        "duplicate_of": None,
        "details": {"outlet_id": "uy_el_pais"},
    }
    assert P.verify_master(root, AREA, "pack-a")
    assert pack.exists()  # the source is copied, never moved


def test_a_completed_promotion_is_idempotent_and_writes_nothing(root, pack):
    promote(pack, root)
    before = {name: (root / name).stat().st_mtime_ns for name in tree(root)}
    again = promote(pack, root)
    assert again.action == "already_preserved"
    assert {name: (root / name).stat().st_mtime_ns for name in tree(root)} == before


def test_a_wrong_declared_hash_is_refused_before_anything_is_written(root, pack):
    with pytest.raises(P.HashMismatch):
        promote(pack, root, declared=sha(b"something else"))
    assert tree(root) == []


def test_the_same_identity_with_other_content_is_a_conflict_never_an_overwrite(root, pack, tmp_path):
    promote(pack, root)
    other = tmp_path / "other.warc.gz"
    other.write_bytes(b"different bytes")
    before = (root / MASTER).read_bytes()
    with pytest.raises(P.IdentityConflict):
        promote(other, root)
    assert (root / MASTER).read_bytes() == before and tree(root) == [
        "preservation/manifests/raw/pack-a.json", MASTER.as_posix()]


def test_a_destination_holding_other_bytes_without_a_manifest_is_a_conflict(root, pack):
    (root / MASTER).parent.mkdir(parents=True)
    (root / MASTER).write_bytes(b"unknown bytes")
    with pytest.raises(P.IdentityConflict):
        promote(pack, root)
    assert (root / MASTER).read_bytes() == b"unknown bytes"


def test_the_same_identity_offered_for_another_path_is_a_conflict(root, pack):
    promote(pack, root)
    (root / MASTER).write_bytes(b"damaged")  # so that the cheap "already preserved" answer is unavailable
    with pytest.raises(P.IdentityConflict):
        promote(pack, root, relative_path="uy/uy_el_pais/elsewhere.warc.gz")


def test_the_same_bytes_under_another_identity_are_recorded_not_copied_twice(root, pack):
    promote(pack, root)
    duplicate = promote(pack, root, object_id="pack-b", relative_path="uy/uy_el_pais/pack-b.warc.gz")
    assert (duplicate.action, duplicate.duplicate_of) == ("duplicate_recorded", "pack-a")
    assert duplicate.relative_path == MASTER.as_posix()
    assert tree(root) == [
        "preservation/manifests/raw/pack-a.json", "preservation/manifests/raw/pack-b.json", MASTER.as_posix()]
    assert P.verify_master(root, AREA, "pack-b")
    assert promote(pack, root, object_id="pack-b", relative_path="uy/uy_el_pais/pack-b.warc.gz").action == "already_preserved"
    third = promote(pack, root, object_id="pack-c", relative_path="uy/uy_el_pais/pack-c.warc.gz")
    assert third.duplicate_of == "pack-a"  # a duplicate points at the holder, not at another duplicate


@pytest.mark.parametrize("damage", ["missing", "mismatched"])
def test_a_missing_or_mismatched_master_is_repaired_and_reported(root, pack, damage):
    promote(pack, root)
    if damage == "missing":
        (root / MASTER).rename(root / "moved-away")
    else:
        (root / MASTER).write_bytes(b"bit rot")
    assert not P.verify_master(root, AREA, "pack-a")
    assert promote(pack, root).action == "repaired"
    assert P.verify_master(root, AREA, "pack-a")


@pytest.mark.parametrize(
    "object_id, relative_path",
    [("../escape", REL), ("a/b", REL), ("", REL), ("x.part-1", REL), ("pack-a", "../outside"),
     ("pack-a", "/absolute"), ("pack-a", "a\\b"), ("pack-a", "a//b"), ("pack-a", "a/x.part-9"), ("pack-a", "")],
)
def test_unsafe_identities_and_paths_are_refused(root, pack, object_id, relative_path):
    with pytest.raises(P.PreservationError):
        promote(pack, root, object_id=object_id, relative_path=relative_path)
    assert tree(root) == []


def test_an_area_cannot_shadow_the_manifests(root, pack):
    with pytest.raises(P.PreservationError):
        P.promote(pack, root=root, area="manifests", object_id="a", relative_path="a", declared_sha256=sha(pack.read_bytes()))


def test_a_tampered_manifest_is_reported_not_trusted(root, pack):
    result = promote(pack, root)
    result.manifest_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(P.PreservationError):
        promote(pack, root)


# --- crash recovery (robustness) ------------------------------------------------------------------


def test_a_failed_copy_leaves_no_master_no_manifest_and_no_part_file(root, pack, monkeypatch):
    def interrupted(reader, writer, length=0):
        writer.write(reader.read(100))
        raise OSError("connection to the share lost")

    monkeypatch.setattr(P.shutil, "copyfileobj", interrupted)
    with pytest.raises(P.PreservationError) as caught:
        promote(pack, root)
    assert isinstance(caught.value.__cause__, OSError) and not isinstance(caught.value, P.ContentRefusal)
    assert tree(root) == []


def test_bytes_that_land_differently_are_never_renamed_into_place(root, pack, monkeypatch):
    def corrupting(reader, writer, length=0):
        writer.write(b"x" + reader.read()[1:])

    monkeypatch.setattr(P.shutil, "copyfileobj", corrupting)
    with pytest.raises(P.HashMismatch):
        promote(pack, root)
    assert tree(root) == []


def test_a_crash_between_master_and_manifest_is_completed_as_a_repair(root, pack, monkeypatch):
    def crash(*args, **kwargs):
        raise OSError("power lost before the manifest")

    with monkeypatch.context() as patched:
        patched.setattr(P, "write_bytes_atomic", crash)
        with pytest.raises(P.PreservationError):
            promote(pack, root)
    assert tree(root) == [MASTER.as_posix()] and not P.verify_master(root, AREA, "pack-a")
    assert promote(pack, root).action == "repaired"
    assert P.verify_master(root, AREA, "pack-a")


def test_a_stale_part_file_is_never_a_master_and_does_not_block_promotion(root, pack):
    stale = root / MASTER.parent / (MASTER.name + ".part-deadbeef")
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"half a pack")
    assert promote(pack, root).action == "promoted"
    assert stale.read_bytes() == b"half a pack"  # an unknown file is left alone, not tidied away
    assert P.verify_master(root, AREA, "pack-a")


# --- no deletion path (structural) ----------------------------------------------------------------

DELETING_CALLS = {"unlink", "remove", "rmtree", "rmdir", "removedirs", "truncate"}


def deleting_calls(module: str) -> list[tuple[str, str]]:
    found = []
    for function in ast.walk(ast.parse((SRC / module).read_text(encoding="utf-8"))):
        if isinstance(function, ast.FunctionDef):
            for node in ast.walk(function):
                if isinstance(node, ast.Call):
                    name = getattr(node.func, "attr", getattr(node.func, "id", None))
                    if name in DELETING_CALLS:
                        found.append((function.name, name))
    return found


def test_preservation_code_has_no_deletion_path():
    assert deleting_calls("preservation.py") == []
    assert [name for name in dir(P) if any(word in name.lower() for word in ("delete", "remove", "purge", "prune"))] == []


def test_the_only_removals_elsewhere_are_the_named_ones():
    assert deleting_calls("canonical.py") == [("_discard_staging", "unlink")]
    assert deleting_calls("layer_store.py") == []
    assert deleting_calls("outage_spool.py") == [("_release", "unlink"), ("_release", "unlink")]
    assert deleting_calls("storage_roots.py") == [("_writable", "unlink")]
    assert deleting_calls("ledger.py") == [("quarantine_torn_tail", "truncate")]


def test_the_staging_cleanup_refuses_anything_that_is_not_a_part_file(tmp_path):
    from coprepan.canonical import _discard_staging

    master = tmp_path / "master.warc.gz"
    master.write_bytes(b"x")
    with pytest.raises(ValueError):
        _discard_staging(master)
    assert master.exists()


# --- outage spool ---------------------------------------------------------------------------------

POLICY = O.SpoolPolicy(min_free_bytes=1_000, max_spool_bytes=100_000)


def unavailable():
    raise StorageRootUnreachable("PRESERVATION: not reachable")


def spool_call(source, preservation_root, spool_root, object_id="pack-a", relative_path=REL, policy=POLICY,
               free=10**9, declared=None):
    return O.preserve_or_spool(
        source, preservation_root=preservation_root, spool_root=spool_root, policy=policy, area=AREA,
        object_id=object_id, relative_path=relative_path,
        declared_sha256=declared or sha(source.read_bytes()), now=NOW, free_bytes=lambda path: free,
    )


@pytest.fixture
def spool(tmp_path):
    path = tmp_path / "spool_root"
    path.mkdir()
    return path


def test_with_the_target_available_nothing_is_spooled(root, pack, spool):
    outcome = spool_call(pack, lambda: root, spool)
    assert (outcome.route, outcome.state) == ("direct", "RAW_PRESERVED")
    assert tree(spool) == [] and P.verify_master(root, AREA, "pack-a")


def test_an_outage_spools_a_verified_copy_as_pending_not_preserved(root, pack, spool):
    outcome = spool_call(pack, unavailable, spool)
    assert (outcome.route, outcome.state) == ("spooled", "PRESERVATION_PENDING")
    assert tree(root) == []
    assert tree(spool) == ["preservation/pending/raw/uy/uy_el_pais/pack-2026-10-07.warc.gz", "state/pending/pack-a.json"]
    record = O.pending_records(spool)[0]
    assert record["schema"] == "coprepan-preservation-spool/v1" and record["state"] == "PRESERVATION_PENDING"
    assert record["sha256"] == sha(pack.read_bytes()) and record["target_relative_path"] == MASTER.as_posix()
    assert O.spooled_bytes(spool) == pack.stat().st_size
    assert spool_call(pack, unavailable, spool).route == "spooled"  # spooling again is a no-op
    assert len(O.pending_records(spool)) == 1


def test_an_io_failure_during_promotion_is_spooled(root, pack, spool, monkeypatch):
    def lost(*args, **kwargs):
        raise OSError("share went away mid-copy")

    monkeypatch.setattr(P, "_land", lost)
    assert spool_call(pack, lambda: root, spool).route == "spooled"


def test_a_content_refusal_is_never_rerouted_into_the_spool(root, pack, spool, tmp_path):
    with pytest.raises(P.HashMismatch):
        spool_call(pack, lambda: root, spool, declared=sha(b"other"))
    spool_call(pack, lambda: root, spool)
    other = tmp_path / "other.warc.gz"
    other.write_bytes(b"different bytes")
    with pytest.raises(P.IdentityConflict):
        spool_call(other, lambda: root, spool)
    assert tree(spool) == []


def test_without_a_spool_an_outage_is_a_refusal(pack):
    with pytest.raises(StorageRefusal):
        spool_call(pack, unavailable, None)


def test_the_spool_has_no_default_bounds(pack, spool):
    with pytest.raises(StorageRefusal):
        spool_call(pack, unavailable, spool, policy=None)
    with pytest.raises(ValueError):
        O.SpoolPolicy(min_free_bytes=-1, max_spool_bytes=10)


def test_the_spool_is_bounded_by_free_space_and_by_its_ceiling(pack, spool):
    size = pack.stat().st_size
    with pytest.raises(O.SpoolCapacityExceeded):
        spool_call(pack, unavailable, spool, free=size + 999)          # would leave less than min_free_bytes
    with pytest.raises(O.SpoolCapacityExceeded):
        spool_call(pack, unavailable, spool, free=None)                # unknown free space is not "enough"
    with pytest.raises(O.SpoolCapacityExceeded):
        spool_call(pack, unavailable, spool, policy=O.SpoolPolicy(0, size - 1))
    assert tree(spool) == []
    assert spool_call(pack, unavailable, spool, free=size + 1_000, policy=O.SpoolPolicy(1_000, size)).route == "spooled"
    with pytest.raises(O.SpoolCapacityExceeded):                        # the ceiling counts what is already held
        spool_call(pack, unavailable, spool, object_id="pack-b", relative_path="uy/uy_el_pais/b.warc.gz",
                   policy=O.SpoolPolicy(1_000, size))


def test_a_spooled_identity_offered_with_other_content_is_a_conflict(pack, spool, tmp_path):
    spool_call(pack, unavailable, spool)
    other = tmp_path / "other.warc.gz"
    other.write_bytes(b"different bytes")
    with pytest.raises(P.IdentityConflict):
        spool_call(other, unavailable, spool)


def test_drain_promotes_with_the_same_function_and_only_then_releases(root, pack, spool):
    spool_call(pack, unavailable, spool)
    assert [(r.object_id, r.action) for r in O.drain(spool, preservation_root=unavailable)] == [("pack-a", "target_unavailable")]
    assert len(O.pending_records(spool)) == 1 and tree(root) == []  # still pending, still not preserved

    results = O.drain(spool, preservation_root=lambda: root, now=NOW)
    assert [(r.object_id, r.action) for r in results] == [("pack-a", "preserved")]
    assert P.verify_master(root, AREA, "pack-a") and tree(spool) == []
    assert (root / MASTER).read_bytes() == pack.read_bytes()
    assert O.drain(spool, preservation_root=lambda: root) == []


def test_drain_keeps_a_refused_object_in_the_spool(root, pack, spool, tmp_path):
    spool_call(pack, unavailable, spool)
    other = tmp_path / "other.warc.gz"
    other.write_bytes(b"what the target already holds under this identity")
    promote(other, root)
    results = O.drain(spool, preservation_root=lambda: root)
    assert [(r.object_id, r.action) for r in results] == [("pack-a", "refused")]
    assert len(O.pending_records(spool)) == 1 and O.spooled_bytes(spool) == pack.stat().st_size


def test_drain_runs_oldest_first_and_stops_at_an_outage(root, spool, tmp_path):
    for index, name in enumerate(("pack-b", "pack-a", "pack-c")):
        source = tmp_path / f"{name}.warc.gz"
        source.write_bytes(name.encode("ascii"))
        O.preserve_or_spool(
            source, preservation_root=unavailable, spool_root=spool, policy=POLICY, area=AREA, object_id=name,
            relative_path=f"uy/uy_el_pais/{name}.warc.gz", declared_sha256=sha(name.encode("ascii")),
            now=NOW.replace(minute=index), free_bytes=lambda path: 10**9,
        )
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) > 1:
            raise StorageRootUnreachable("gone again")
        return root

    results = O.drain(spool, preservation_root=flaky)
    assert [(r.object_id, r.action) for r in results] == [("pack-b", "preserved"), ("pack-a", "target_unavailable")]
    assert [record["object_id"] for record in O.pending_records(spool)] == ["pack-a", "pack-c"]
