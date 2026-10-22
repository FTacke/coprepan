"""The storage qualification tool stays inside this corpus's own directory (consistency audit 2026-10-22, F-22).

Its spool-failover probe used to write and remove under ``preservation_root.parent/_qualification/``; since the
cutover that parent is the umbrella both corpora share (``crosscorpus-storage/v1`` §5.2). Every root here is a
``tmp_path``; the environment is an explicit mapping, never the workstation ``.env``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("qualify_storage_roots_under_test", REPO / "scripts" / "qualify_storage_roots.py")
Q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(Q)


def snapshot(directory: Path) -> list[str]:
    return sorted(path.relative_to(directory).as_posix() for path in directory.rglob("*"))


def test_the_failover_refuses_when_the_parent_is_the_shared_umbrella(tmp_path):
    umbrella = tmp_path / "projects" / "panhispanic_media_corpora"
    root, sister, spool = umbrella / "coprepan", umbrella / "corapan", tmp_path / "local" / "coprepan_storage"
    for directory in (root, sister / "data", spool):
        directory.mkdir(parents=True)
    before = snapshot(tmp_path)
    env = {"COPREPAN_PRESERVATION_ROOT": str(root), "COPREPAN_SPOOL_ROOT": str(spool)}
    with pytest.raises(Q.QualificationRefused, match="umbrella"):
        Q.spool_failover(env)
    assert snapshot(tmp_path) == before                                                    # nothing written, nothing removed


def test_the_failover_runs_beside_a_sub_root_inside_the_corpus_directory_and_leaves_nothing(tmp_path):
    corpus = tmp_path / "projects" / "panhispanic_media_corpora" / "coprepan"
    root, spool = corpus / "preservation_interim", tmp_path / "local" / "coprepan_storage"
    root.mkdir(parents=True)
    spool.mkdir(parents=True)
    (corpus.parent / "corapan").mkdir()
    before = snapshot(tmp_path)
    result = Q.spool_failover({"COPREPAN_PRESERVATION_ROOT": str(root), "COPREPAN_SPOOL_ROOT": str(spool)})
    assert result["status"] == "PASS" and result["cleaned_up"] is True
    assert snapshot(tmp_path) == before                                                    # its own directories only, all gone


def test_a_reserved_segment_is_never_the_corpus_directory(tmp_path):
    root = tmp_path / "projects" / "panhispanic_media_corpora" / "legacy" / "coprepan" / "tree"
    with pytest.raises(Q.QualificationRefused, match="reserved"):
        Q.qualification_area(root, {}, "20261022T000000Z")


def test_the_probe_area_never_meets_a_configured_root(tmp_path):
    corpus = tmp_path / "coprepan"
    root = corpus / "preservation_interim"
    assert Q.qualification_area(root, {"PRESERVATION": root}, "s") == corpus / "_qualification" / "qualification-s"
    for clash in (corpus / "_qualification", corpus / "_qualification" / "backup", corpus):
        with pytest.raises(Q.QualificationRefused, match="BACKUP"):
            Q.qualification_area(root, {"PRESERVATION": root, "BACKUP": clash}, "s")
