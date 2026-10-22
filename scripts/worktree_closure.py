"""Close a run's worktree only when nothing can be lost (AGENTS §4; the classification of CO.RA.PAN's
``local_storage_audit_v1.py worktrees``, adapted, with the removal itself added).

    python scripts/worktree_closure.py status [--report docs/agent-runs/<file>.md]
    python scripts/worktree_closure.py remove <worktree path> --report docs/agent-runs/<file>.md [--min-idle-minutes 30]

``status`` classifies every linked worktree and changes nothing. ``remove`` removes **one** worktree, with
``git worktree remove`` and never ``--force``, and only when every check passes:

1. it is a linked worktree of this repository and not the main checkout (``ALREADY_REMOVED`` when it is gone);
2. it is not locked and no git operation is in progress in it (merge, rebase, cherry-pick, revert, bisect, ``index.lock``);
3. no tracked change and no untracked file; ignored content only caches (``__pycache__``, ``.pytest_cache`` …) — any
   other ignored file may be scratch evidence and keeps the worktree;
4. its HEAD is reachable from ``main`` (integrated) and from a remote-tracking ref (a copy beyond this disk);
5. the run's canonical report is in ``main``'s tree (``--report``);
6. nothing in it changed for ``--min-idle-minutes`` (default 30) and this process does not run inside it. The session
   that owns the worktree and has finished may pass 0; no check can see another session's open files.

The branch is never deleted, nothing runs in the background, and age alone never removes anything. A repeated call
finds the worktree gone and changes nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE_NAMES = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
IN_PROGRESS = ("MERGE_HEAD", "rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG", "index.lock")
SAFE, KEEP, GONE, MAIN = "SAFE_TO_REMOVE", "KEEP", "ALREADY_REMOVED", "MAIN_CHECKOUT"


def git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def worktrees(repo: Path) -> list[dict]:
    entries, current = [], None
    for line in git("worktree", "list", "--porcelain", cwd=repo).stdout.splitlines():
        if line.startswith("worktree "):
            current = {"path": Path(line[len("worktree "):]), "locked": False, "branch": None}
            entries.append(current)
        elif current is not None and line.startswith("branch "):
            current["branch"] = line[len("branch "):]
        elif current is not None and line.startswith("locked"):
            current["locked"] = True
    return entries


def _same(a: Path, b: Path) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _cache_only(path: str) -> bool:
    parts = path.rstrip("/").split("/")
    return any(part in CACHE_NAMES for part in parts) or parts[-1].endswith((".pyc", ".pyo"))


def _newest_change(path: Path) -> float:
    newest = 0.0
    for directory, names, files in os.walk(path):
        names[:] = [name for name in names if name != ".git" and name not in CACHE_NAMES]
        for name in files:
            try:
                newest = max(newest, os.stat(os.path.join(directory, name)).st_mtime)
            except OSError:
                pass
    return newest


def classify(path: Path, *, repo: Path = REPO, report: str | None = None, min_idle_minutes: float = 30,
             now: float | None = None) -> dict:
    entries = worktrees(repo)
    main_entry = next((e for e in entries if e["branch"] == "refs/heads/main"), entries[0] if entries else None)
    entry = next((e for e in entries if _same(e["path"], path)), None)
    if entry is None:
        return {"path": str(path), "verdict": GONE if not Path(path).exists() else KEEP,
                "reasons": [] if not Path(path).exists() else ["the directory exists but is not a worktree of this repository"]}
    if main_entry is not None and _same(entry["path"], main_entry["path"]):
        return {"path": str(path), "verdict": MAIN, "reasons": ["the main checkout is never removed"]}
    reasons = []
    if entry["locked"]:
        reasons.append("locked (git worktree lock)")
    gitdir = Path(git("rev-parse", "--absolute-git-dir", cwd=path).stdout.strip())
    reasons += [f"operation in progress: {name}" for name in IN_PROGRESS if (gitdir / name).exists()]
    state = git("status", "--porcelain=v1", "--untracked-files=all", "--ignored=matching", cwd=path)
    if state.returncode:
        reasons.append(f"git status failed: {state.stderr.strip()}")
    for line in state.stdout.splitlines():
        if line.startswith("!! "):
            if not _cache_only(line[3:]):
                reasons.append(f"ignored file that is not a cache (possible scratch evidence): {line[3:]}")
        else:
            reasons.append(f"uncommitted: {line}")
    head = git("rev-parse", "HEAD", cwd=path).stdout.strip()
    if git("merge-base", "--is-ancestor", head, "main", cwd=repo).returncode:
        reasons.append(f"HEAD {head[:9]} is not integrated in main")
    if not git("branch", "-r", "--contains", head, cwd=repo).stdout.strip():
        reasons.append(f"HEAD {head[:9]} is in no remote-tracking ref (no copy beyond this disk)")
    if report is None:
        reasons.append("no canonical report named (--report)")
    elif git("cat-file", "-e", f"main:{report}", cwd=repo).returncode:
        reasons.append(f"the canonical report {report} is not on main")
    idle = ((now or time.time()) - _newest_change(path)) / 60
    if idle < min_idle_minutes:
        reasons.append(f"changed {idle:.0f} min ago (< {min_idle_minutes} min idle)")
    cwd = Path.cwd()
    if _same(cwd, path) or any(_same(parent, path) for parent in cwd.parents):
        reasons.append("this process runs inside the worktree")
    return {"path": str(path), "branch": entry["branch"], "head": head, "verdict": KEEP if reasons else SAFE, "reasons": reasons}


def remove(path: Path, *, repo: Path = REPO, report: str | None, min_idle_minutes: float = 30) -> dict:
    result = classify(path, repo=repo, report=report, min_idle_minutes=min_idle_minutes)
    if result["verdict"] != SAFE:
        return {**result, "removed": False}
    done = git("worktree", "remove", str(path), cwd=repo)
    removed = done.returncode == 0 and not any(_same(e["path"], path) for e in worktrees(repo))
    return {**result, "removed": removed, **({} if removed else {"error": done.stderr.strip()})}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    status = commands.add_parser("status")
    status.add_argument("--report")
    status.add_argument("--min-idle-minutes", type=float, default=30)
    rm = commands.add_parser("remove")
    rm.add_argument("path")
    rm.add_argument("--report", required=True)
    rm.add_argument("--min-idle-minutes", type=float, default=30)
    arguments = parser.parse_args(argv)
    if arguments.command == "status":
        rows = [classify(e["path"], report=arguments.report, min_idle_minutes=arguments.min_idle_minutes)
                for e in worktrees(REPO)]
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    result = remove(Path(arguments.path), report=arguments.report, min_idle_minutes=arguments.min_idle_minutes)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("removed") or result["verdict"] == GONE else 1


if __name__ == "__main__":
    raise SystemExit(main())
