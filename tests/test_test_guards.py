"""The guards of tests/conftest.py are exercised, not just declared."""

import os
import socket

import pytest

from conftest import NetworkAccessInTest


def test_socket_connect_is_refused():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with pytest.raises(NetworkAccessInTest):
            sock.connect(("127.0.0.1", 9))


def test_create_connection_is_refused():
    with pytest.raises(NetworkAccessInTest):
        socket.create_connection(("127.0.0.1", 9), timeout=1)


def test_no_storage_root_reaches_a_test():
    assert [name for name in os.environ if name.startswith("COPREPAN_") and name.endswith("_ROOT")] == []
