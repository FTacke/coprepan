"""Storage drift guard (CPD-0014): the roles stay apart, nothing falls back, and a root can be switched.

The storage semantics are the ones CO.RA.PAN 3.0 uses (separate roles, named roots, fail-closed,
no address in an identity). This module guards them for this repository alone: it reads nothing of
the CO.RA.PAN checkout and needs none. Every root here is under ``tmp_path``.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from coprepan import core_pipeline as C
from coprepan import preservation_target as PT
from coprepan import release_contract as RC
from coprepan import storage_roots as S
from test_core_pipeline import Canary, T0

REPO = Path(__file__).resolve().parents[1]
ENV_NAMES = {"RUNTIME": "COPREPAN_WORKSPACE_ROOT", "PRESERVATION": "COPREPAN_PRESERVATION_ROOT", "SPOOL": "COPREPAN_SPOOL_ROOT",
             "BACKUP": "COPREPAN_BACKUP_ROOT", "DISTRIBUTION": "COPREPAN_DISTRIBUTION_ROOT", "EXCHANGE": "COPREPAN_EXCHANGE_ROOT"}


def make_roots(tmp_path, *roles):
    roots = {}
    for role in roles:
        roots[role] = tmp_path / role.lower()
        roots[role].mkdir()
    return roots


def environment(roots):
    return {ENV_NAMES[role]: str(root) for role, root in roots.items()}


# --- the roles ---------------------------------------------------------------------------------------


def test_the_tracked_roles_are_the_shared_ones_and_only_preservation_is_authoritative():
    targets = S.load_storage_targets()
    assert {role: target.variable for role, target in targets.items()} == ENV_NAMES
    assert [role for role, target in targets.items() if target.authoritative] == ["PRESERVATION"]
    assert set(S.ROLES) == {"REPOSITORY", *ENV_NAMES}


def test_the_tracked_files_hold_no_machine_location():
    """Roles, variables and layout are tracked; where a disk is mounted is not (the path scan of
    the repository contract covers `src/`, `config/`, `scripts/` and `tests/`; this adds the examples).
    """
    example = (REPO / ".env.example").read_text(encoding="utf-8")
    assert {line.split("=")[0] for line in example.splitlines() if line and not line.startswith("#")} == set(ENV_NAMES.values())
    assert all(line.endswith("=") for line in example.splitlines() if line and not line.startswith("#"))


# --- separation --------------------------------------------------------------------------------------


@pytest.mark.parametrize("first, second", [("RUNTIME", "SPOOL"), ("SPOOL", "PRESERVATION"), ("RUNTIME", "PRESERVATION")])
def test_two_roles_never_share_a_root_nor_nest(tmp_path, first, second):
    outer = tmp_path / "outer"
    (outer / "inner").mkdir(parents=True)
    S.validate_role_separation({first: tmp_path / "alone", second: tmp_path / "elsewhere"})  # distinct paths are fine
    with pytest.raises(S.StorageRootUnusable):
        S.validate_role_separation({first: outer, second: outer})
    with pytest.raises(S.StorageRootUnusable):
        S.validate_role_separation({first: outer, second: outer / "inner"})
    with pytest.raises(S.StorageRootUnusable):
        S.validate_role_separation({first: outer / "inner", second: outer})


def test_the_repository_is_a_role_too(tmp_path):
    with pytest.raises(S.StorageRootUnusable):
        S.validate_role_separation({"RUNTIME": REPO.parent}, checkout=REPO)       # the checkout lies inside the runtime root
    with pytest.raises(S.StorageRootUnusable):
        S.validate_role_separation({"RUNTIME": REPO / "work"}, checkout=REPO)     # the runtime lies inside the checkout
    S.validate_role_separation({"RUNTIME": tmp_path / "coprepan_workspace"}, checkout=tmp_path / "coprepan")  # siblings, even with a shared prefix


def test_a_backup_on_the_volume_of_the_primary_is_not_a_backup(tmp_path):
    roots = make_roots(tmp_path, "PRESERVATION", "BACKUP")
    with pytest.raises(S.StorageRootUnusable, match="not an independent copy"):
        S.validate_role_separation(roots)
    with pytest.raises(S.StorageRootUnusable):
        S.resolve_configured_roles(env=environment(roots))


def test_a_backup_on_another_volume_is_accepted_and_an_unknown_volume_is_refused(tmp_path, monkeypatch):
    roots = make_roots(tmp_path, "PRESERVATION", "BACKUP")
    volumes = {roots["PRESERVATION"]: 1, roots["BACKUP"]: 2}
    monkeypatch.setattr(S, "volume_of", lambda root: volumes[Path(root)])
    S.validate_role_separation(roots)

    def unknown(root):
        raise S.StorageRootUnreachable("no volume identity")

    monkeypatch.setattr(S, "volume_of", unknown)
    with pytest.raises(S.StorageRootUnreachable):
        S.validate_role_separation(roots)                                    # never guessed


def test_an_unconfigured_role_is_a_statement_and_never_falls_back(tmp_path):
    roots = make_roots(tmp_path, "PRESERVATION")
    resolved = S.resolve_configured_roles(env=environment(roots))
    assert resolved["PRESERVATION"] == roots["PRESERVATION"]
    assert {role for role, root in resolved.items() if root is None} == {"RUNTIME", "SPOOL", "BACKUP", "DISTRIBUTION", "EXCHANGE"}
    for role in ("BACKUP", "DISTRIBUTION", "EXCHANGE", "SPOOL", "RUNTIME"):
        with pytest.raises(S.StorageRootNotConfigured):
            S.resolve_root(role, env=environment(roots))                      # another role's root is not a fallback
    assert S.resolve_configured_roles(env={}) == dict.fromkeys(ENV_NAMES)


def test_a_configured_but_unreachable_role_is_a_refusal_not_none(tmp_path):
    with pytest.raises(S.StorageRootUnreachable):
        S.resolve_configured_roles(env={"COPREPAN_PRESERVATION_ROOT": str(tmp_path / "not-mounted")})


def test_the_workstation_file_only_configures_coprepan_roots_and_the_process_wins(tmp_path):
    (tmp_path / ".env").write_text("COPREPAN_SPOOL_ROOT=/from/file\nPATH=/evil\nCOPREPAN_WORKSPACE_ROOT=/from/file\n", encoding="utf-8")
    values = S.workstation_environment(tmp_path, {"COPREPAN_WORKSPACE_ROOT": "/from/process"})
    assert values["COPREPAN_WORKSPACE_ROOT"] == "/from/process" and values["COPREPAN_SPOOL_ROOT"] == "/from/file"
    assert "PATH" not in values
    assert S.workstation_environment(tmp_path / "no-env-file", {}) == {}


# --- a drive letter is not an identity; a root can be switched -----------------------------------------


def test_a_preserved_pack_is_the_same_object_on_another_root(tmp_path):
    """The planned move from the interim root to a new file system, in miniature: copy, verify, switch.

    Nothing the pipeline stores names the root. The same fetch ids, document ids, version ids and
    bytes are read from the copy; replay needs neither the old root nor the network.
    """
    canary = Canary(tmp_path / "run").all()
    old_root = canary.root
    PT.initialise_target(old_root, "coprepan-preservation-interim", operator="test", now=T0)
    new_root = tmp_path / "new" / "elsewhere" / "preservation"
    shutil.copytree(old_root, new_root)                                    # the migration copy
    assert RC.tree_digest(new_root) == RC.tree_digest(old_root)            # verified: every path, size and SHA-256
    assert PT.read_target(new_root) == PT.read_target(old_root)            # the logical root identity moved with the data

    before = C.open_preserved_pack(old_root, canary.pack_id)
    shutil.rmtree(old_root)                                                # the old root is gone: only the new one answers
    after = C.open_preserved_pack(new_root, canary.pack_id)
    assert sorted(after.entries) == sorted(before.entries) and len(after.entries) == len(canary.fetch_ids())
    held = [fetch_id for fetch_id, entry in after.entries.items() if entry.body_sha256 is not None]
    assert len(held) == len(canary.fetch_ids()) - 1                       # all but the one request that never got an answer
    for fetch_id in after.entries:
        assert after.fetch_record(fetch_id)["fetch_id"] == fetch_id
    for fetch_id in held:
        assert hashlib.sha256(after.body(fetch_id)).hexdigest() == after.entries[fetch_id].body_sha256
    first = next(result for result in canary.results if result.get("extraction_fingerprint"))
    replay = C.replay_extraction(canary.workspace, preservation_root=new_root, identifier=canary.pack_id, fetch_id=first["fetch_id"])
    assert replay["status"] == "ALREADY_STORED" and replay["artifact_id"] == first["extraction_artifact_id"]


def test_nothing_stored_names_the_machine_the_root_or_a_drive(tmp_path):
    canary = Canary(tmp_path / "run").all()
    roots = {str(canary.root), canary.root.as_posix(), str(canary.workspace.root), canary.workspace.root.as_posix()}
    offenders = []
    for base in (canary.root, canary.workspace.root):
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in (".json", ".jsonl"):
                text = path.read_text(encoding="utf-8", errors="replace")
                if any(root in text for root in roots):
                    offenders.append(path.relative_to(base).as_posix())
    assert offenders == []


def test_the_interim_marker_is_not_a_drive_and_a_second_identity_is_refused(tmp_path):
    root = tmp_path / "preservation"
    root.mkdir()
    marker = PT.initialise_target(root, "coprepan-preservation-interim-d", operator="test", now=T0)
    assert json.loads((root / PT.MARKER_NAME).read_text(encoding="utf-8")) == marker
    assert tmp_path.name not in json.dumps(marker) and ":" not in marker["target_id"]
    with pytest.raises(PT.TargetError):
        PT.initialise_target(root, "another-id", operator="test", now=T0)           # an identity is never re-issued
