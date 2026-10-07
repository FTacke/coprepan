"""The guards of tests/conftest.py are exercised, not just declared."""

import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from conftest import NetworkAccessInTest, is_loopback

# TEST-NET-1 (RFC 5737): reserved for documentation, never routed. The guard must refuse before
# anything is sent, so nothing leaves the machine even if the guard were broken.
OUTSIDE = ("192.0.2.1", 9)


def test_socket_connect_outside_this_machine_is_refused():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with pytest.raises(NetworkAccessInTest):
            sock.connect(OUTSIDE)
        with pytest.raises(NetworkAccessInTest):
            sock.connect_ex(OUTSIDE)


def test_create_connection_outside_this_machine_is_refused():
    with pytest.raises(NetworkAccessInTest):
        socket.create_connection(OUTSIDE, timeout=1)


@pytest.mark.parametrize("name", ["localhost", "example.org", "www.diario-ejemplo.test", ""])
def test_names_are_refused_without_being_resolved(name):
    with pytest.raises(NetworkAccessInTest):
        socket.create_connection((name, 80), timeout=1)


def test_only_literal_loopback_addresses_count_as_loopback():
    assert is_loopback(("127.0.0.1", 80)) and is_loopback(("127.5.6.7", 1)) and is_loopback(("::1", 80, 0, 0))
    for address in (("localhost", 80), ("10.0.0.1", 80), ("0.0.0.0", 80), ("192.0.2.1", 9), ("", 80), None, "127.0.0.1"):
        assert not is_loopback(address)


def test_a_server_started_by_the_test_is_reachable_on_loopback():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(204)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    try:
        with socket.create_connection(("127.0.0.1", server.server_address[1]), timeout=5) as sock:
            sock.sendall(b"GET / HTTP/1.0\r\n\r\n")
            assert sock.recv(64).startswith(b"HTTP/1.0 204")
    finally:
        thread.join(timeout=5)
        server.server_close()


def test_no_storage_root_reaches_a_test():
    assert [name for name in os.environ if name.startswith("COPREPAN_") and name.endswith("_ROOT")] == []
