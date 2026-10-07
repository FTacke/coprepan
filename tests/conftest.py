"""Test configuration: suites and guards.

Suites
    Every ``tests/test_*.py`` belongs to exactly one manifest under ``tests/suites/`` (one file
    name per line, ``#`` comments). ``python -m pytest --suite <name> tests`` runs one suite;
    without ``--suite`` everything runs. Membership is checked by
    ``tests/test_repository_contract.py``.

Guards (autouse)
    * no network: a test that opens a socket connection to anything but a literal loopback
      address fails (AGENTS.md §7);
    * no storage root: every ``COPREPAN_*_ROOT`` is removed from the environment, so a test can
      never reach a real preservation or workspace target (AGENTS.md §15).
"""

from __future__ import annotations

import ipaddress
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


def is_loopback(address) -> bool:
    """Whether a socket address is a literal loopback address. Names are never resolved here:
    ``localhost`` is refused, because what a name resolves to is not this guard's to trust.
    """
    host = address[0] if isinstance(address, tuple) and address else None
    if not isinstance(host, str):
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Refuse every connection that leaves this machine.

    A connection to a literal loopback address is allowed, so that a test can exercise the real
    HTTP stack against a server it started itself (AGENTS.md §7). Everything else — any name, any
    non-loopback address — raises before a packet is sent.
    """
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex
    real_create_connection = socket.create_connection

    def refuse(address):
        raise NetworkAccessInTest(
            f"tests must not touch the network (tried {address!r}); only a literal loopback "
            "address of a server the test started is allowed (AGENTS.md §7)"
        )

    def connect(self, address):
        return real_connect(self, address) if is_loopback(address) else refuse(address)

    def connect_ex(self, address):
        return real_connect_ex(self, address) if is_loopback(address) else refuse(address)

    def create_connection(address, *args, **kwargs):
        return real_create_connection(address, *args, **kwargs) if is_loopback(address) else refuse(address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "create_connection", create_connection)


@pytest.fixture(autouse=True)
def no_storage_roots(monkeypatch):
    for name in list(os.environ):
        if name.startswith("COPREPAN_") and name.endswith("_ROOT"):
            monkeypatch.delenv(name)
