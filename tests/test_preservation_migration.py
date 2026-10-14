"""The pre-copy of the PRESERVATION primary to its future root (CPD-0030; crosscorpus-storage/v1 §11.2) and the identity
check of the PRESERVATION root (§6 T1/T2). Every root is a ``tmp_path``; the environment is an explicit mapping.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from coprepan import preservation_migration as M
from coprepan import preservation_target as PT
from coprepan import storage_roots as S

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
MTIME = 1791963136891101800
FILES = {
    "preservation/raw/ar/ar_clarin/pk1-ar_clarin-20261009-000.warc.gz": b"warc-pack-one" * 50,
    "preservation/raw_index/ar/ar_clarin/pk1-ar_clarin-20261009-000.json": b'{"records": 3}',
    "preservation/manifests/packs/pk1-ar_clarin-20261009-000.json": b'{"state": "RAW_PRESERVED"}',
    "preservation/raw/uy/uy_el_pais/pk1-uy_el_pais-20261010-001.warc.gz": b"warc-pack-two" * 70,
}


@pytest.fixture()
def roots(tmp_path: Path) -> dict[str, Path]:
    source = tmp_path / "interim" / "preservation_interim"
    for path, data in FILES.items():
        f = source / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
        os.utime(f, ns=(MTIME, MTIME))
    PT.initialise_target(source, "coprepan-preservation-interim-d", operator="test", now=NOW)
    dest = tmp_path / "newfs" / "projects" / "panhispanic_media_corpora" / "coprepan"
    dest.mkdir(parents=True)
    PT.initialise_target(dest, "coprepan-preservation-newfs", operator="test", now=NOW)
    return {"source": source, "dest": dest}


def run(roots, entries, **kw):
    return M.copy(roots["source"], roots["dest"], entries, migration_id="m1", active_root=roots["source"], workers=2, **kw)


def test_the_baseline_holds_the_objects_not_the_marker(roots) -> None:
    base = M.baseline(roots["source"])
    assert sorted(e["path"] for e in base["objects"]) == sorted(FILES)
    assert base["source_target_id"] == "coprepan-preservation-interim-d" and base["files"] == 4


def test_the_copy_lands_every_object_with_its_digest_and_timestamp_and_never_the_source_identity(roots) -> None:
    base = M.baseline(roots["source"])
    result = run(roots, base["objects"])
    assert result["counts"] == {M.COPIED: 4} and not result["problems"]
    for path, data in FILES.items():
        f = roots["dest"] / path
        assert f.read_bytes() == data and f.stat().st_mtime_ns == MTIME
    assert PT.read_target(roots["dest"])["target_id"] == "coprepan-preservation-newfs"     # its own identity, untouched
    v = M.verify(roots["dest"], base["objects"])
    assert v["equal"] and v["objects"] == 4 and not v["temporary_files"]


def test_an_interrupted_copy_resumes_and_a_rerun_copies_nothing(roots, tmp_path) -> None:
    base = M.baseline(roots["source"])
    stop = tmp_path / "STOP"
    stop.write_text("")
    assert run(roots, base["objects"], stop_file=stop)["processed"] == 0
    stop.unlink()
    assert run(roots, base["objects"][:2])["counts"] == {M.COPIED: 2}
    assert run(roots, base["objects"])["counts"] == {M.SKIPPED: 2, M.COPIED: 2}
    assert run(roots, base["objects"])["counts"] == {M.SKIPPED: 4}


def test_an_existing_different_object_is_a_conflict_and_is_never_replaced(roots) -> None:
    base = M.baseline(roots["source"])
    path = next(iter(FILES))
    other = roots["dest"] / path
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_bytes(b"not the pack")
    assert run(roots, base["objects"])["counts"][M.CONFLICT] == 1 and other.read_bytes() == b"not the pack"


def test_a_source_that_changed_since_the_baseline_is_not_copied(roots) -> None:
    base = M.baseline(roots["source"])
    path = list(FILES)[1]
    (roots["source"] / path).write_bytes(b'{"records": 4}')
    assert run(roots, base["objects"])["counts"][M.SOURCE_CHANGED] == 1 and not (roots["dest"] / path).exists()


def test_the_destination_must_have_its_own_identity_and_must_not_be_in_use(roots, tmp_path) -> None:
    base = M.baseline(roots["source"])
    bare = tmp_path / "bare"
    bare.mkdir()
    with pytest.raises(M.MigrationError, match="never set up"):
        M.copy(roots["source"], bare, base["objects"], migration_id="m", active_root=roots["source"])
    with pytest.raises(M.MigrationError, match="in use today"):
        M.copy(roots["source"], roots["dest"], base["objects"], migration_id="m", active_root=roots["dest"])
    with pytest.raises(M.MigrationError, match="not an existing directory"):
        M.copy(roots["source"], tmp_path / "absent", base["objects"], migration_id="m", active_root=roots["source"])
    assert not (tmp_path / "absent").exists()


def test_sweep_removes_only_this_tools_own_temporary_files(roots) -> None:
    run(roots, M.baseline(roots["source"])["objects"])
    d = roots["dest"] / "preservation" / "raw" / "ar" / "ar_clarin"
    own = d / ("pk1-ar_clarin-20261009-000.warc.gz" + M.TEMP_TAG + "0123abcd")
    own.write_bytes(b"half")
    foreign = d / "pk1-ar_clarin-20261009-000.warc.gz.part-0123abcd"
    foreign.write_bytes(b"x")
    removed = M.sweep_temporary(roots["dest"], migration_id="m1", active_root=roots["source"])
    assert removed == [own.relative_to(roots["dest"]).as_posix()] and foreign.exists() and not own.exists()


def test_a_broken_journal_handle_is_reopened_and_a_torn_row_is_skipped(roots) -> None:
    """Regression (NEW_FS, 2026-10-14 17:03): a reset SMB session invalidated the open journal handle and killed the copy."""
    path = M.journal_path(roots["dest"], "m9")
    path.parent.mkdir(parents=True)
    journal = M._Journal(path, sleep=lambda s: None)
    journal.write(json.dumps({"path": "a", "status": M.COPIED, "sha256": "x"}) + "\n")

    class Broken:
        def write(self, text):
            raise OSError(22, "Invalid argument")

        def close(self):
            raise OSError(22, "Invalid argument")

    journal.handle = Broken()
    journal.write(json.dumps({"path": "b", "status": M.COPIED, "sha256": "y"}) + "\n")
    journal.close()
    with open(path, "a", encoding="utf-8") as handle:
        handle.write('{"path": "c", "sta')
    assert journal.reopened == 1 and sorted(M.load_journal(roots["dest"], "m9")) == ["a", "b"]


def test_a_lost_transport_stops_the_run_cleanly_and_it_resumes(roots, monkeypatch) -> None:
    base = M.baseline(roots["source"])
    monkeypatch.setattr(M, "migrate_one", lambda *a, **k: {"path": a[2]["path"], "status": M.FAILED, "error": "OSError: gone"})
    result = M.copy(roots["source"], roots["dest"], base["objects"], migration_id="m2", active_root=roots["source"], workers=1,
                    retries=1, retry_pause=0, network_failure_limit=2, sleep=lambda s: None)
    assert result["stopped"] and result["stop_reason"] == "NETWORK_UNAVAILABLE" and result["processed"] < 4
    monkeypatch.undo()
    again = M.copy(roots["source"], roots["dest"], base["objects"], migration_id="m2", active_root=roots["source"], workers=1)
    assert again["counts"] == {M.COPIED: 4}


def test_the_unbuffered_re_read_gives_the_digest_of_the_bytes(tmp_path) -> None:
    import hashlib
    f = tmp_path / "x.bin"
    data = os.urandom(5 * 1024 * 1024 + 17)
    f.write_bytes(data)
    assert M.sha256_uncached(f) == (hashlib.sha256(data).hexdigest(), len(data))


# --- the identity of the PRESERVATION root (T1/T2) -------------------------------------------------------------------------


def env_for(root: Path, expected: str | None = None) -> dict[str, str]:
    env = {"COPREPAN_PRESERVATION_ROOT": str(root)}
    if expected is not None:
        env[S.EXPECTED_IDENTITY_VARIABLE] = expected
    return env


def test_an_expected_identity_must_be_the_roots(roots) -> None:
    assert S.resolve_root("PRESERVATION", env=env_for(roots["dest"], "coprepan-preservation-newfs")) == roots["dest"]
    with pytest.raises(S.StorageTargetIdentityMismatch, match="expects"):
        S.resolve_root("PRESERVATION", env=env_for(roots["source"], "coprepan-preservation-newfs"))
    with pytest.raises(S.StorageTargetIdentityMismatch):                     # reading the wrong root is refused as well
        S.resolve_root("PRESERVATION", env=env_for(roots["source"], "coprepan-preservation-newfs"), writable=False)


def test_an_expected_identity_and_no_marker_is_a_mismatch(tmp_path) -> None:
    with pytest.raises(S.StorageTargetIdentityMismatch, match="carries no"):
        S.resolve_root("PRESERVATION", env=env_for(tmp_path, "coprepan-preservation-newfs"))


@pytest.mark.parametrize("name", ["corapan_preservation_target.json", "BACKUP_ROOT.json"])
def test_the_sister_corpus_primary_or_a_backup_root_is_never_taken_for_the_primary(tmp_path, name) -> None:
    (tmp_path / name).write_text("{}", encoding="utf-8")
    with pytest.raises(S.StorageTargetIdentityMismatch, match=name):
        S.resolve_root("PRESERVATION", env=env_for(tmp_path))


def test_an_unreadable_marker_is_a_mismatch(tmp_path) -> None:
    (tmp_path / PT.MARKER_NAME).write_text("{broken", encoding="utf-8")
    with pytest.raises(S.StorageTargetIdentityMismatch):
        S.resolve_root("PRESERVATION", env=env_for(tmp_path))


def test_without_an_expected_identity_a_root_without_marker_stays_usable(tmp_path) -> None:
    assert S.resolve_root("PRESERVATION", env=env_for(tmp_path)) == tmp_path
    assert S.preservation_identity(tmp_path, expected=None)["state"] == "IDENTITY_UNRECORDED"


def test_identity_is_measured_at_every_resolution(roots) -> None:
    env = env_for(roots["dest"], "coprepan-preservation-newfs")
    assert S.resolve_root("PRESERVATION", env=env) == roots["dest"]
    (roots["dest"] / PT.MARKER_NAME).unlink()
    with pytest.raises(S.StorageTargetIdentityMismatch):
        S.resolve_root("PRESERVATION", env=env)


def test_the_expected_identity_variable_is_an_identity_never_a_path() -> None:
    example = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    assert f"{S.EXPECTED_IDENTITY_VARIABLE}=\n" in example
