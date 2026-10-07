"""The legacy freeze manifest: builder, verifier, and the tracked manifest's internal consistency.

The builder and verifier are exercised on a synthetic tree in ``tmp_path``. **No test reads the
legacy repository.** The tracked manifest (the result of the real run of 2026-10-07) is checked
only against itself: its listing must be the one it names.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from coprepan import legacy_freeze as LF

REPO = Path(__file__).resolve().parents[1]
TRACKED = REPO / "docs" / "legacy" / "freeze" / "coprepan-legacy-2026-06"
NOW = datetime(2026, 10, 7, 21, 0, 0, tzinfo=timezone.utc)
HEAD = "3e6bdd3350913d55c07efe500036bf752de65cc2"


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "legacy_tree"
    files = {
        "README.md": b"legacy\n",
        "json_annotated/ARG/clarin/ARG_clarin_2026-01-01.ann.json": b'{"articles": []}',
        "json_raw/ARG/clarin/ARG_clarin_2026-01-01.json": b'{"articles": [1]}',
        "data/db/coprepan.sqlite": b"SQLite format 3\x00" + b"\x00" * 64,
        "data/db/coprepan.sqlite-wal": b"wal bytes",
        "src/coprepan/models.py": "# código\n".encode("utf-8"),
        "json_raw/PAN/la estrella de panamá/a.json": b"{}",
        ".git/HEAD": b"ref: refs/heads/main\n",
        ".git/index": b"index bytes that git may rewrite",
    }
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return root


def build(tree, out, status=""):
    return LF.build(tree, out, created_at=NOW, git_head=HEAD, git_status_porcelain=status, operator="test")


def test_manifest_lists_every_file_outside_git_with_size_and_digest(tree, tmp_path):
    manifest = build(tree, tmp_path / "out")
    _, rows = LF.read(tmp_path / "out")
    assert sorted(rows) == sorted(["README.md", "data/db/coprepan.sqlite", "data/db/coprepan.sqlite-wal",
                                   "json_annotated/ARG/clarin/ARG_clarin_2026-01-01.ann.json",
                                   "json_raw/ARG/clarin/ARG_clarin_2026-01-01.json",
                                   "json_raw/PAN/la estrella de panamá/a.json", "src/coprepan/models.py"])
    assert not any(path.startswith(".git/") for path in rows)
    row = rows["src/coprepan/models.py"]
    source = "# código\n".encode("utf-8")
    assert (row["size_bytes"], row["sha256"]) == (len(source), hashlib.sha256(source).hexdigest())
    assert manifest["freeze_id"] == "coprepan-legacy-2026-06" and manifest["schema"] == "coprepan-legacy-freeze-manifest/v1"
    assert manifest["state"] == "MANIFEST_ONLY"  # not the frozen release: no preservation copy, no restore check
    assert manifest["totals"] == {"files": 7, "bytes": sum(r["size_bytes"] for r in rows.values())}
    assert manifest["release_scope"]["files"] == 5  # the corpus stores and the databases
    assert manifest["legacy_repository"] == {"directory_name": "legacy_tree", "git_head": HEAD, "git_status_clean": True,
                                             "git_status_sha256": hashlib.sha256(b"").hexdigest()}
    assert manifest["tool"]["name"] == "legacy-freeze/1" and manifest["created_at"] == "2026-10-07T21:00:00.000000Z"
    assert manifest["areas"]["data"] == {"files": 2, "bytes": 89} and manifest["areas"]["(root)"]["files"] == 1


def test_listing_is_deterministic_and_bound_by_the_manifest(tree, tmp_path):
    first, second = build(tree, tmp_path / "a"), build(tree, tmp_path / "b")
    assert (tmp_path / "a" / "files.jsonl").read_bytes() == (tmp_path / "b" / "files.jsonl").read_bytes()
    assert first["listing"] == second["listing"]
    assert first["listing"]["sha256"] == hashlib.sha256((tmp_path / "a" / "files.jsonl").read_bytes()).hexdigest()
    (tmp_path / "a" / "files.jsonl").write_bytes((tmp_path / "a" / "files.jsonl").read_bytes().replace(b"README.md", b"README.mD"))
    with pytest.raises(LF.FreezeError):
        LF.read(tmp_path / "a")  # a listing that was edited is not the manifest's listing


def test_an_unchanged_tree_verifies_and_the_tree_is_not_touched(tree, tmp_path):
    before = {p.relative_to(tree).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns) for p in tree.rglob("*") if p.is_file()}
    build(tree, tmp_path / "out")
    report = LF.verify(tree, tmp_path / "out", git_head=HEAD)
    assert (report["status"], report["unchanged"], report["added"], report["removed"], report["changed"]) == ("VERIFIED", 7, [], [], [])
    assert report["git_head_matches"] is True
    assert {p.relative_to(tree).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns) for p in tree.rglob("*") if p.is_file()} == before


def test_a_modified_removed_or_added_file_is_reported(tree, tmp_path):
    build(tree, tmp_path / "out")
    (tree / "json_raw" / "ARG" / "clarin" / "ARG_clarin_2026-01-01.json").write_bytes(b'{"articles": [2]}')  # same size, other bytes
    (tree / "README.md").unlink()
    (tree / "json_annotated" / "nuevo.json").write_bytes(b"{}")
    report = LF.verify(tree, tmp_path / "out", git_head=HEAD)
    assert report["status"] == "DIFFERS"
    assert report["changed"] == ["json_raw/ARG/clarin/ARG_clarin_2026-01-01.json"]
    assert report["removed"] == ["README.md"] and report["added"] == ["json_annotated/nuevo.json"]
    assert (report["files_in_manifest"], report["files_in_tree"], report["unchanged"]) == (7, 7, 5)


def test_a_changed_timestamp_with_the_same_bytes_is_not_a_change(tree, tmp_path):
    build(tree, tmp_path / "out")
    target = tree / "json_annotated" / "ARG" / "clarin" / "ARG_clarin_2026-01-01.ann.json"
    os.utime(target, (1_600_000_000, 1_600_000_000))
    assert LF.verify(tree, tmp_path / "out")["status"] == "VERIFIED"  # fixity is bytes
    assert "mtime" not in (tmp_path / "out" / "files.jsonl").read_text(encoding="utf-8")


def test_git_metadata_is_bound_by_the_commit_not_by_bytes(tree, tmp_path):
    build(tree, tmp_path / "out")
    (tree / ".git" / "index").write_bytes(b"git rewrote its index while looking")
    assert LF.verify(tree, tmp_path / "out", git_head=HEAD)["status"] == "VERIFIED"
    moved = LF.verify(tree, tmp_path / "out", git_head="0" * 40)
    assert (moved["status"], moved["git_head_matches"]) == ("DIFFERS", False)
    assert build(tree, tmp_path / "dirty", status=" M README.md\n")["legacy_repository"]["git_status_clean"] is False


def test_the_manifest_is_written_outside_the_tree_and_never_overwritten(tree, tmp_path):
    with pytest.raises(LF.FreezeError):
        build(tree, tree / "freeze")
    assert not (tree / "freeze").exists()
    build(tree, tmp_path / "out")
    with pytest.raises(LF.FreezeError):
        build(tree, tmp_path / "out")
    with pytest.raises(LF.FreezeError):
        LF.scan(tmp_path / "absent").__next__()


def test_a_link_in_the_tree_is_refused(tree, tmp_path):
    try:
        os.symlink(tmp_path, tree / "enlace", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("this platform or account cannot create a symbolic link")
    with pytest.raises(LF.FreezeError):
        build(tree, tmp_path / "out")


def test_the_command_line_builds_and_verifies(tree, tmp_path, capsys):
    status = tmp_path / "status.txt"
    status.write_text("", encoding="utf-8")
    common = ["--root", str(tree), "--manifest-dir", str(tmp_path / "out"), "--git-head", HEAD]
    assert LF.main(["build", *common, "--git-status-file", str(status), "--operator", "test"]) == 0
    assert LF.main(["verify", *common]) == 0
    (tree / "README.md").write_bytes(b"changed\n")
    capsys.readouterr()
    assert LF.main(["verify", *common]) == 1
    assert json.loads(capsys.readouterr().out)["changed"] == ["README.md"]


# --- the tracked manifest of the real run -----------------------------------------------------------


def test_the_tracked_manifest_is_internally_consistent():
    manifest, rows = LF.read(TRACKED)  # raises unless the listing is the one the manifest names
    assert manifest["freeze_id"] == "coprepan-legacy-2026-06" and manifest["state"] == "MANIFEST_ONLY"
    assert manifest["totals"] == {"files": len(rows), "bytes": sum(row["size_bytes"] for row in rows.values())}
    assert manifest["legacy_repository"]["git_head"] == HEAD and manifest["legacy_repository"]["git_status_clean"] is True
    assert manifest["release_scope"]["files"] == sum(1 for path in rows if LF.in_release_scope(path))
    assert list(rows) == sorted(rows) and not any(path.startswith(".git/") for path in rows)
    assert all(len(row["sha256"]) == 64 for row in rows.values())
    assert sum(entry["files"] for entry in manifest["areas"].values()) == len(rows)
    # the databases and the three corpus stores are in the release scope
    assert "data/db/coprepan.sqlite" in rows and LF.in_release_scope("data/db/coprepan.sqlite")
    for store in ("json_annotated", "json_raw", "json_raw_extended"):
        assert manifest["areas"][store]["files"] > 0
