"""Fail-closed storage-root resolution. Every root here is a ``tmp_path``; the environment is an
explicit mapping, so no test can reach a configured root.
"""

from pathlib import Path

import pytest

from coprepan import storage_roots as S

REPO = Path(__file__).resolve().parents[1]
ROLE_VARIABLES = {
    "RUNTIME": "COPREPAN_WORKSPACE_ROOT",
    "PRESERVATION": "COPREPAN_PRESERVATION_ROOT",
    "SPOOL": "COPREPAN_SPOOL_ROOT",
    "DISTRIBUTION": "COPREPAN_DISTRIBUTION_ROOT",
    "EXCHANGE": "COPREPAN_EXCHANGE_ROOT",
}


def write_targets(tmp_path, body):
    path = tmp_path / "storage_targets.yml"
    path.write_text(body, encoding="utf-8")
    return path


# --- tracked configuration ------------------------------------------------------------------------


def test_tracked_targets_declare_the_roles_and_their_variables():
    targets = S.load_storage_targets()
    assert {role: target.variable for role, target in targets.items()} == ROLE_VARIABLES
    assert [role for role, target in targets.items() if target.authoritative] == ["PRESERVATION"]
    assert S.CHECKOUT == REPO


def test_repository_and_backup_have_no_root_to_resolve():
    for role in ("REPOSITORY", "BACKUP"):
        with pytest.raises(S.StorageRootNotConfigured):
            S.resolve_root(role, env={})


@pytest.mark.parametrize(
    "body",
    [
        "targets:\n  RUNTIME:\n    root: ${COPREPAN_WORKSPACE_ROOT}\n    purpose: p\n    authoritative: false\n",
        "schema: coprepan-storage-targets/v2\ntargets:\n  RUNTIME:\n    root: ${COPREPAN_WORKSPACE_ROOT}\n    purpose: p\n    authoritative: false\n",
        "schema: coprepan-storage-targets/v1\ntargets:\n",
        "schema: coprepan-storage-targets/v1\ntargets:\n  RUNTIME:\n    root: /srv/data\n    purpose: p\n    authoritative: false\n",
        "schema: coprepan-storage-targets/v1\ntargets:\n  RUNTIME:\n    root: ${HOME}\n    purpose: p\n    authoritative: false\n",
        "schema: coprepan-storage-targets/v1\ntargets:\n  RUNTIME:\n    root: ${COPREPAN_WORKSPACE_ROOT}/sub\n    purpose: p\n    authoritative: false\n",
        "schema: coprepan-storage-targets/v1\ntargets:\n  RUNTIME:\n    root: ${COPREPAN_WORKSPACE_ROOT}\n    purpose: p\n",
        "schema: coprepan-storage-targets/v1\ntargets:\n  RUNTIME:\n    root: ${COPREPAN_WORKSPACE_ROOT}\n    purpose: p\n    authoritative: maybe\n",
        "schema: coprepan-storage-targets/v1\ntargets:\n  RUNTIME:\n    root: ${COPREPAN_WORKSPACE_ROOT}\n    purpose: p\n    authoritative: false\n    default: ./data\n",
        "schema: coprepan-storage-targets/v1\ntargets:\n  ARCHIVE:\n    root: ${COPREPAN_ARCHIVE_ROOT}\n    purpose: p\n    authoritative: false\n",
        "schema: coprepan-storage-targets/v1\ntargets:\n  REPOSITORY:\n    root: ${COPREPAN_REPOSITORY_ROOT}\n    purpose: p\n    authoritative: false\n",
        "schema: coprepan-storage-targets/v1\ntargets:\n  RUNTIME:\n    root: ${COPREPAN_X_ROOT}\n    purpose: p\n    authoritative: false\n  SPOOL:\n    root: ${COPREPAN_X_ROOT}\n    purpose: p\n    authoritative: false\n",
        "schema: coprepan-storage-targets/v1\ntargets:\n  RUNTIME: {root: x}\n",
        "schema: coprepan-storage-targets/v1\nfallback: local\ntargets:\n",
    ],
)
def test_configuration_outside_the_contract_is_refused(tmp_path, body):
    with pytest.raises(S.StorageConfigError):
        S.load_storage_targets(write_targets(tmp_path, body))


def test_a_missing_configuration_file_is_a_refusal(tmp_path):
    with pytest.raises(S.StorageConfigError):
        S.load_storage_targets(tmp_path / "absent.yml")


# --- resolution -----------------------------------------------------------------------------------


@pytest.mark.parametrize("role", sorted(ROLE_VARIABLES))
def test_a_configured_reachable_writable_root_resolves(tmp_path, role):
    assert S.resolve_root(role, env={ROLE_VARIABLES[role]: str(tmp_path)}) == tmp_path
    assert list(tmp_path.iterdir()) == []  # the write probe left nothing behind


def test_resolution_is_deterministic_and_normalises_lexically(tmp_path):
    untidy = str(tmp_path / "a" / ".." / "root")
    (tmp_path / "root").mkdir()
    env = {"COPREPAN_WORKSPACE_ROOT": untidy}
    assert S.resolve_root("RUNTIME", env=env) == S.resolve_root("RUNTIME", env=env) == tmp_path / "root"


@pytest.mark.parametrize("env", [{}, {"COPREPAN_PRESERVATION_ROOT": ""}, {"COPREPAN_PRESERVATION_ROOT": "   "}])
def test_unset_is_a_refusal_not_a_default(env):
    with pytest.raises(S.StorageRootNotConfigured):
        S.resolve_root("PRESERVATION", env=env)


def test_another_roles_root_is_never_a_fallback(tmp_path):
    env = {"COPREPAN_WORKSPACE_ROOT": str(tmp_path), "COPREPAN_SPOOL_ROOT": str(tmp_path)}
    with pytest.raises(S.StorageRootNotConfigured):
        S.resolve_root("PRESERVATION", env=env)


def test_the_process_environment_is_the_default_and_tests_see_none(tmp_path):
    with pytest.raises(S.StorageRootNotConfigured):
        S.resolve_root("PRESERVATION")


def test_unreachable_is_a_refusal_and_nothing_is_created(tmp_path):
    missing = tmp_path / "not-mounted"
    with pytest.raises(S.StorageRootUnreachable):
        S.resolve_root("PRESERVATION", env={"COPREPAN_PRESERVATION_ROOT": str(missing)})
    assert not missing.exists()


def test_a_file_is_not_a_root(tmp_path):
    file = tmp_path / "file"
    file.write_bytes(b"")
    with pytest.raises(S.StorageRootUnreachable):
        S.resolve_root("PRESERVATION", env={"COPREPAN_PRESERVATION_ROOT": str(file)})


def test_an_unreachable_root_reports_unknown_usage_not_zero(tmp_path):
    assert S.probe(tmp_path / "not-mounted") == S.RootProbe(False, None, None)
    reachable = S.probe(tmp_path)
    assert reachable.reachable and reachable.free_bytes > 0 and reachable.total_bytes > 0


def test_read_only_is_a_refusal(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "_writable", lambda root: False)
    env = {"COPREPAN_PRESERVATION_ROOT": str(tmp_path)}
    with pytest.raises(S.StorageRootReadOnly):
        S.resolve_root("PRESERVATION", env=env)
    assert S.resolve_root("PRESERVATION", env=env, writable=False) == tmp_path


def test_the_write_probe_reports_a_directory_it_cannot_write_to(tmp_path):
    assert S._writable(tmp_path) is True
    assert S._writable(tmp_path / "absent") is False


@pytest.mark.parametrize("value", ["relative/root", "./data", "data"])
def test_a_relative_root_is_refused(value):
    with pytest.raises(S.StorageRootUnusable):
        S.resolve_root("RUNTIME", env={"COPREPAN_WORKSPACE_ROOT": value})


def test_a_filesystem_root_is_refused():
    with pytest.raises(S.StorageRootUnusable):
        S.resolve_root("RUNTIME", env={"COPREPAN_WORKSPACE_ROOT": Path(REPO.anchor).as_posix()})


@pytest.mark.parametrize("inside", [REPO, REPO / "data", REPO / "tests" / ".." / "workspace"])
def test_a_root_inside_the_checkout_is_refused(inside):
    with pytest.raises(S.StorageRootUnusable):
        S.resolve_root("RUNTIME", env={"COPREPAN_WORKSPACE_ROOT": str(inside)})


def test_a_sibling_whose_name_starts_like_the_checkout_is_not_inside_it(tmp_path):
    assert S.is_inside(REPO / "src", REPO) and S.is_inside(REPO, REPO)
    assert not S.is_inside(REPO.with_name(REPO.name + "_workspace"), REPO)
    assert not S.is_inside(tmp_path, REPO)


def test_every_refusal_is_a_storage_refusal():
    for refusal in (S.StorageConfigError, S.StorageRootNotConfigured, S.StorageRootUnusable,
                    S.StorageRootUnreachable, S.StorageRootReadOnly):
        assert issubclass(refusal, S.StorageRefusal)


# --- workstation .env -----------------------------------------------------------------------------


def test_env_file_is_parsed_and_feeds_resolution(tmp_path):
    root = tmp_path / "preservation"
    root.mkdir()
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"# workstation\n\nCOPREPAN_PRESERVATION_ROOT={root}\nCOPREPAN_SPOOL_ROOT=\nQUOTED='a b'\n", encoding="utf-8"
    )
    env = S.read_env_file(env_file)
    assert env == {"COPREPAN_PRESERVATION_ROOT": str(root), "COPREPAN_SPOOL_ROOT": "", "QUOTED": "a b"}
    assert S.resolve_root("PRESERVATION", env=env) == root
    with pytest.raises(S.StorageRootNotConfigured):
        S.resolve_root("SPOOL", env=env)


def test_a_malformed_env_file_is_refused(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("export COPREPAN_PRESERVATION_ROOT=x\n", encoding="utf-8")
    with pytest.raises(S.StorageConfigError):
        S.read_env_file(env_file)
