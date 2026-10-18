"""The BACKUP of the PRESERVATION primary (coprepan.primary_backup; NEW_FS Phase D): produced from the primary, write-once, verified
against a fresh baseline, restorable, on its own root and another volume. Temporary directories only; volumes are simulated."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from coprepan import preservation_migration as M
from coprepan import preservation_target
from coprepan import primary_backup as B
from coprepan import storage_roots


@pytest.fixture()
def roots(tmp_path, monkeypatch):
    primary, backup = tmp_path / "newfs" / "coprepan", tmp_path / "d" / "backup"
    primary.mkdir(parents=True)
    preservation_target.initialise_target(primary, "coprepan-test-primary", operator="test", now=datetime.now(timezone.utc))
    for rel, data in (("packs/a/p1.warc.gz", b"pack one"), ("packs/a/p1.idx", b"index"), ("manifests/m1.json", b'{"m": 1}')):
        p = primary.joinpath(*rel.split("/"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    monkeypatch.setattr(storage_roots, "volume_of", lambda root: 1 if "newfs" in str(root) else 2)
    return primary, backup


def _run(primary, backup, tmp_path):
    base = M.baseline(primary)
    copied = B.copy(primary, backup, base)
    verification = B.verify(backup, base)
    restore = B.restore_test(backup, base, tmp_path / "scratch", samples=3)
    return base, copied, verification, restore


def test_a_backup_is_produced_from_the_primary_verified_and_restorable(roots, tmp_path) -> None:
    primary, backup = roots
    B.init_root(backup, primary=primary, operator="test")
    base, copied, verification, restore = _run(primary, backup, tmp_path)
    assert copied["ok"] and copied["counts"] == {"COPIED": 3} and verification["ok"] and restore["all_ok"]
    assert (backup / "packs/a/p1.warc.gz").read_bytes() == b"pack one"
    assert not (backup / preservation_target.MARKER_NAME).exists()                     # the primary's identity is not copied
    assert not any((tmp_path / "scratch").rglob("*.*"))                                # the restore test removed its own files
    B.write_receipt(backup, {"primary_target_id": base["source_target_id"], "produced_from_primary": True,
                             "verified_against_primary": True, "objects": base["files"], "bytes": base["bytes"],
                             "tree_sha256": base["tree_sha256"], "written_at": "now"})
    facts = B.receipt_status(backup, primary)
    assert facts["copy_exists"] and facts["produced_from_primary"] and facts["verified_against_primary"]
    again = B.copy(primary, backup, M.baseline(primary))
    assert again["counts"] == {"SKIPPED_JOURNALLED": 3}                                 # idempotent


def test_new_objects_of_the_primary_are_added_and_nothing_is_ever_removed(roots, tmp_path) -> None:
    primary, backup = roots
    B.init_root(backup, primary=primary, operator="test")
    _run(primary, backup, tmp_path)
    (primary / "packs" / "a" / "p2.warc.gz").write_bytes(b"pack two")
    base = M.baseline(primary)
    assert B.copy(primary, backup, base)["counts"] == {"SKIPPED_JOURNALLED": 3, "COPIED": 1}
    (primary / "manifests" / "m1.json").rename(primary / "manifests" / "m1.moved")      # an object vanishes at the primary
    v = B.verify(backup, M.baseline(primary))
    assert "manifests/m1.json" in v["only_in_backup"] and (backup / "manifests/m1.json").is_file()


def test_a_different_existing_object_is_a_conflict_and_is_kept(roots, tmp_path) -> None:
    primary, backup = roots
    B.init_root(backup, primary=primary, operator="test")
    (backup / "packs" / "a").mkdir(parents=True)
    (backup / "packs" / "a" / "p1.warc.gz").write_bytes(b"other bytes")
    copied = B.copy(primary, backup, M.baseline(primary))
    assert not copied["ok"] and copied["counts"].get("CONFLICT") == 1
    assert (backup / "packs/a/p1.warc.gz").read_bytes() == b"other bytes"


def test_a_damaged_copy_does_not_verify(roots, tmp_path) -> None:
    primary, backup = roots
    B.init_root(backup, primary=primary, operator="test")
    base, *_ = _run(primary, backup, tmp_path)
    (backup / "packs" / "a" / "p1.idx").write_bytes(b"INDEX")
    v = B.verify(backup, base)
    assert not v["ok"] and v["problems"][0]["problem"] == "DIFFERENT"


@pytest.mark.parametrize("case", ["same_volume", "not_empty", "primary_marker", "no_marker"])
def test_a_backup_root_is_only_a_backup_root(roots, tmp_path, case, monkeypatch) -> None:
    primary, backup = roots
    if case == "same_volume":
        monkeypatch.setattr(storage_roots, "volume_of", lambda root: 1)
        with pytest.raises(B.BackupError, match="primary's volume"):
            B.init_root(backup, primary=primary, operator="test")
    elif case == "not_empty":
        backup.mkdir(parents=True)
        (backup / "something").write_text("x")
        with pytest.raises(B.BackupError, match="not empty"):
            B.init_root(backup, primary=primary, operator="test")
    elif case == "primary_marker":
        B.init_root(backup, primary=primary, operator="test")
        preservation_target.initialise_target(backup, "a-primary", operator="test", now=datetime.now(timezone.utc))
        with pytest.raises(B.BackupError, match="never a backup"):
            B.copy(primary, backup, M.baseline(primary))
    else:
        backup.mkdir(parents=True)
        with pytest.raises(B.BackupError, match="carries no"):
            B.copy(primary, backup, M.baseline(primary))


def test_a_receipt_of_another_primary_is_no_backup_of_this_one(roots, tmp_path) -> None:
    primary, backup = roots
    B.init_root(backup, primary=primary, operator="test")
    B.write_receipt(backup, {"primary_target_id": "another-primary", "produced_from_primary": True, "verified_against_primary": True})
    facts = B.receipt_status(backup, primary)
    assert facts["copy_exists"] and not facts["produced_from_primary"] and not facts["verified_against_primary"]
    assert B.receipt_status(None, primary)["copy_exists"] is False


def test_the_restore_cleanup_refuses_anything_outside_its_scratch_directory(tmp_path) -> None:
    (tmp_path / "keep.txt").write_text("x")
    with pytest.raises(ValueError):
        B._discard_restored(tmp_path / "scratch", tmp_path / "keep.txt")
    assert (tmp_path / "keep.txt").is_file()
