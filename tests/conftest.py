"""Test configuration: suites and guards.

Suites
    Every ``tests/test_*.py`` belongs to exactly one manifest under ``tests/suites/`` (one file
    name per line, ``#`` comments). ``python -m pytest --suite <name> tests`` runs one suite;
    without ``--suite`` everything runs. Membership is checked by
    ``tests/test_repository_contract.py``.

Guards (autouse)
    * no network: a test that opens a socket connection fails (AGENTS.md §7);
    * no storage root: every ``COPREPAN_*_ROOT`` is removed from the environment, so a test can
      never reach a real preservation or workspace target (AGENTS.md §15).
"""

from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest

SUITES_DIR = Path(__file__).parent / "suites"
SUITE_NAMES = tuple(sorted(path.stem for path in SUITES_DIR.glob("*.txt")))


class NetworkAccessInTest(RuntimeError):
    """A test tried to reach the network."""


def suite_members(name: str) -> list[str]:
    members = []
    for line in (SUITES_DIR / f"{name}.txt").read_text(encoding="utf-8").splitlines():
        entry = line.split("#", 1)[0].strip()
        if entry:
            members.append(entry)
    return members


def pytest_addoption(parser):
    parser.addoption(
        "--suite",
        action="append",
        choices=SUITE_NAMES,
        default=None,
        help="run only the named suite (repeatable); see tests/suites/",
    )


def pytest_collection_modifyitems(config, items):
    wanted = config.getoption("--suite")
    if not wanted:
        return
    members = {member for name in wanted for member in suite_members(name)}
    selected = [item for item in items if Path(str(item.fspath)).name in members]
    deselected = [item for item in items if item not in selected]
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise NetworkAccessInTest(
            "tests must not touch the network; replay a fixture instead (AGENTS.md §7)"
        )

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture(autouse=True)
def no_storage_roots(monkeypatch):
    for name in list(os.environ):
        if name.startswith("COPREPAN_") and name.endswith("_ROOT"):
            monkeypatch.delenv(name)
