"""The run-closure tools against a real temporary git repository with a bare remote (AGENTS §4, §16):
``scripts/publish_run_report.py`` (a report on main, documentation only) and ``scripts/worktree_closure.py``
(a worktree removed only when nothing can be lost). Nothing here reads this checkout's git state.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P = load("publish_run_report")
W = load("worktree_closure")
NAME = "2026-10-22_some-run.md"
REPORT = f"docs/agent-runs/{NAME}"
TEXT = "# Some run\n\n- **Status: `PARTIAL`.** What it does not claim.\n- `EXTERNAL_API_USAGE = NONE`\n"


@pytest.fixture(autouse=True)
def identity(monkeypatch, tmp_path):
    for key, value in {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
                       "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_CONFIG_NOSYSTEM": "1"}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    (tmp_path / "gitconfig").write_text("[core]\n\tautocrlf = false\n[init]\n\tdefaultBranch = main\n", encoding="utf-8")


def run(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


@pytest.fixture
def repos(tmp_path):
    """A main checkout with a bare remote, and a run's worktree on its own branch with a report and a code change."""
    main, remote, worktree = tmp_path / "main", tmp_path / "remote.git", tmp_path / "worktrees" / "run"
    run("init", "--bare", "-b", "main", str(remote), cwd=tmp_path)
    run("init", "-b", "main", str(main), cwd=tmp_path)
    write(main / "docs" / "agent-runs" / "README.md", "conventions\n")
    write(main / "src" / "code.py", "x = 1\n")
    run("add", "--", "docs", "src", cwd=main)
    run("commit", "-m", "start", cwd=main)
    run("remote", "add", "origin", str(remote), cwd=main)
    run("push", "-u", "origin", "main", cwd=main)
    run("worktree", "add", "-b", "run/branch", str(worktree), "main", cwd=main)
    write(worktree / REPORT, TEXT)
    write(worktree / "src" / "code.py", "x = 2\n")
    run("add", "--", REPORT, "src/code.py", cwd=worktree)
    run("commit", "-m", "the run", cwd=worktree)
    return main, worktree


def changed_paths(main: Path) -> list[str]:
    return sorted(run("diff", "--name-only", "HEAD~1", "HEAD", cwd=main).splitlines())


# --- publication ----------------------------------------------------------------------------------


def test_a_report_reaches_main_alone_and_the_checkout_stays_in_step(repos):
    main, worktree = repos
    result = P.publish(REPORT, "PARTIAL", repo=worktree)
    assert result["result"] == "PUBLISHED"
    assert changed_paths(main) == sorted([P.INDEX, REPORT])                                 # no code of the branch
    assert (main / "src" / "code.py").read_text(encoding="utf-8") == "x = 1\n"
    assert run("status", "--porcelain=v1", cwd=main) == ""                                 # index and tree match HEAD
    assert run("rev-list", "--count", "HEAD", cwd=main) == "2" and "Published-By: publish_run_report" in run("log", "-1", "--format=%B", cwd=main)
    index = (main / P.INDEX).read_text(encoding="utf-8")
    assert f"[{NAME}]({NAME}) | Some run | PARTIAL | `run/branch` @ `{result['source'][:9]}`" in index


def test_publishing_the_same_bytes_again_changes_nothing(repos):
    main, worktree = repos
    P.publish(REPORT, "PARTIAL", repo=worktree)
    head = run("rev-parse", "HEAD", cwd=main)
    assert P.publish(REPORT, "PARTIAL", repo=worktree)["result"] == "NO_CHANGE"
    assert run("rev-parse", "HEAD", cwd=main) == head


def test_a_different_report_on_main_is_replaced_only_with_update(repos):
    main, worktree = repos
    P.publish(REPORT, "PARTIAL", repo=worktree)
    write(worktree / REPORT, TEXT.replace("What it does not claim.", "Closing note."))
    run("commit", "-am", "later state", cwd=worktree)
    with pytest.raises(P.PublishError, match="--update"):
        P.publish(REPORT, "PARTIAL", repo=worktree)
    assert P.publish(REPORT, "PARTIAL", repo=worktree, update=True)["result"] == "PUBLISHED"
    assert "Closing note." in (main / REPORT).read_text(encoding="utf-8")
    assert (main / P.INDEX).read_text(encoding="utf-8").count(f"[{NAME}]") == 1              # one row, never two


@pytest.mark.parametrize("path, status, message", [
    ("src/code.py", "PARTIAL", "not a run report path"),
    ("docs/agent-runs/INDEX.md", "PARTIAL", "not a run report path"),
    (REPORT, "PASS", "the report says PARTIAL"),
])
def test_what_is_not_a_report_or_not_its_status_is_refused(repos, path, status, message):
    main, worktree = repos
    head = run("rev-parse", "HEAD", cwd=main)
    with pytest.raises(P.PublishError, match=message):
        P.publish(path, status, repo=worktree)
    assert run("rev-parse", "HEAD", cwd=main) == head


def test_an_uncommitted_report_and_one_without_an_api_statement_are_refused(repos):
    main, worktree = repos
    other = "docs/agent-runs/2026-10-22_not-committed.md"
    write(worktree / other, TEXT)
    with pytest.raises(P.PublishError, match="not committed"):
        P.publish(other, "PARTIAL", repo=worktree)
    write(worktree / REPORT, TEXT.replace("- `EXTERNAL_API_USAGE = NONE`\n", ""))
    run("commit", "-m", "no statement", "--", REPORT, cwd=worktree)
    with pytest.raises(P.PublishError, match="EXTERNAL_API_USAGE"):
        P.publish(REPORT, "PARTIAL", repo=worktree)


def test_someones_change_in_the_main_checkout_is_never_taken_or_overwritten(repos):
    main, worktree = repos
    write(main / P.INDEX, "someone's draft\n")                                             # untracked, other bytes
    head = run("rev-parse", "HEAD", cwd=main)
    with pytest.raises(P.PublishError, match="not this publication"):
        P.publish(REPORT, "PARTIAL", repo=worktree)
    assert run("rev-parse", "HEAD", cwd=main) == head
    assert (main / P.INDEX).read_text(encoding="utf-8") == "someone's draft\n"


def test_main_moved_meanwhile_means_nothing_is_published(repos):
    main, worktree = repos
    old = run("rev-parse", "HEAD", cwd=main)
    write(main / "other.txt", "another session\n")
    run("add", "--", "other.txt", cwd=main)
    run("commit", "-m", "another session", cwd=main)
    moved = run("rev-parse", "HEAD", cwd=main)
    with pytest.raises(P.PublishError, match="update-ref"):
        P.commit_on_main(main, old, {REPORT: TEXT.encode("utf-8")}, "stale")              # compare-and-swap from a stale main
    assert run("rev-parse", "HEAD", cwd=main) == moved


def test_check_lists_reports_of_a_branch_that_main_lacks(repos):
    main, worktree = repos
    assert P.check(repo=worktree) == [f"MISSING_ON_MAIN {REPORT}"]
    P.publish(REPORT, "PARTIAL", repo=worktree)
    assert P.check(repo=worktree) == []


# --- worktree closure -----------------------------------------------------------------------------


def integrate(main: Path, worktree: Path, *, push: bool = True) -> None:
    P.publish(REPORT, "PARTIAL", repo=worktree)
    run("merge", "--no-ff", "-m", "merge", "run/branch", cwd=main)
    if push:
        run("push", "origin", "run/branch", cwd=worktree)
    old = time.time() - 3600
    for directory, _, files in os.walk(worktree):
        for name in files:
            os.utime(os.path.join(directory, name), (old, old))


def test_an_integrated_pushed_clean_worktree_is_removed_and_a_second_call_changes_nothing(repos):
    main, worktree = repos
    integrate(main, worktree)
    result = W.remove(worktree, repo=main, report=REPORT)
    assert result["removed"] is True and not worktree.exists()
    assert "run/branch" in run("branch", "--list", "run/branch", cwd=main)                   # the branch stays
    again = W.remove(worktree, repo=main, report=REPORT)
    assert again["verdict"] == W.GONE and again["removed"] is False


def test_the_main_checkout_is_never_removed(repos):
    main, _ = repos
    assert W.classify(main, repo=main, report=REPORT)["verdict"] == W.MAIN


@pytest.mark.parametrize("case, expected", [
    ("unmerged", "not integrated in main"),
    ("uncommitted", "uncommitted"),
    ("scratch", "possible scratch evidence"),
    ("no_report", "not on main"),
    ("not_pushed", "no remote-tracking ref"),
    ("locked", "locked"),
    ("in_progress", "operation in progress"),
    ("recent", "min idle"),
])
def test_every_unproven_condition_keeps_the_worktree(repos, case, expected):
    main, worktree = repos
    if case != "unmerged":
        integrate(main, worktree, push=case != "not_pushed")
    report = "docs/agent-runs/2026-10-22_other-run.md" if case == "no_report" else REPORT
    if case == "uncommitted":
        write(worktree / "src" / "code.py", "x = 3\n")
    elif case == "scratch":
        write(worktree / ".gitignore", "*.log\n")
        run("add", "--", ".gitignore", cwd=worktree)
        run("commit", "-m", "ignore", cwd=worktree)
        run("merge", "-m", "again", "run/branch", cwd=main)
        run("push", "origin", "run/branch", cwd=worktree)
        write(worktree / "evidence.log", "the only copy\n")
    elif case == "locked":
        run("worktree", "lock", "--reason", "a session works here", str(worktree), cwd=main)
    elif case == "in_progress":
        gitdir = Path(run("rev-parse", "--absolute-git-dir", cwd=worktree))
        (gitdir / "index.lock").write_bytes(b"")
    elif case == "recent":
        write(worktree / "note.txt", "touched now\n")
        run("add", "--", "note.txt", cwd=worktree)
        run("commit", "-m", "touched", cwd=worktree)
        run("merge", "-m", "again", "run/branch", cwd=main)
        run("push", "origin", "run/branch", cwd=worktree)
    result = W.remove(worktree, repo=main, report=report, min_idle_minutes=0 if case == "scratch" else 30)
    assert result["removed"] is False and worktree.exists()
    assert any(expected in reason for reason in result["reasons"]), result["reasons"]
