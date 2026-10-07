"""Test support: a scriptable HTTP server on a loopback address, and a clock that does not wait.

The server speaks real HTTP/1.1 over a real socket, so the transport code under test is the code
that would run against a real site — but nothing leaves the machine (``tests/conftest.py`` allows
literal loopback addresses only). Responses carry no ``Date`` or ``Server`` header, so the same
script always produces the same bytes.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass
class Response:
    status: int = 200
    headers: list[tuple[str, str]] = field(default_factory=list)
    body: bytes = b""
    declared_length: int | None = None   # lie about Content-Length (truncated body)
    chunked: bool = False
    cut_chunked: bool = False            # end a chunked body without its terminating chunk
    delay_seconds: float = 0.0
    no_length: bool = False              # no Content-Length: the body ends when the connection closes


class LocalSite:
    """Routes are ``path?query`` → a :class:`Response` or a list of them (served in turn; the last
    one repeats). Every request is logged with its headers.
    """

    def __init__(self) -> None:
        self.routes: dict[str, Response | list[Response]] = {}
        self.requests: list[tuple[str, dict[str, str]]] = []
        self._served: dict[str, int] = {}
        site = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:  # noqa: N802 - http.server naming
                site.requests.append((self.path, {k.lower(): v for k, v in self.headers.items()}))
                route = site.routes.get(self.path)
                if route is None:
                    response = Response(404, [("Content-Type", "text/html; charset=utf-8")], b"<html><body><p>No existe.</p></body></html>")
                elif isinstance(route, list):
                    index = min(site._served.get(self.path, 0), len(route) - 1)
                    site._served[self.path] = site._served.get(self.path, 0) + 1
                    response = route[index]
                else:
                    response = route
                if response.delay_seconds:
                    time.sleep(response.delay_seconds)
                try:
                    self.send_response_only(response.status)
                    for name, value in response.headers:
                        self.send_header(name, value)
                    if response.chunked:
                        self.send_header("Transfer-Encoding", "chunked")
                    elif not response.no_length:
                        self.send_header("Content-Length", str(len(response.body) if response.declared_length is None else response.declared_length))
                    self.send_header("Connection", "close")
                    self.end_headers()
                    if response.chunked:
                        half = max(1, len(response.body) // 2)
                        for part in (response.body[:half], response.body[half:]):
                            if part:
                                self.wfile.write(f"{len(part):x}\r\n".encode("ascii") + part + b"\r\n")
                        if not response.cut_chunked:
                            self.wfile.write(b"0\r\n\r\n")
                    else:
                        self.wfile.write(response.body)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionError):
                    pass  # the client gave up (timeout or size limit): that is the test
                self.close_connection = True

            def log_message(self, *args) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)

    def __enter__(self) -> "LocalSite":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def paths(self) -> list[str]:
        return [path for path, _ in self.requests]


class FakeClock:
    """A clock that advances one second per reading and jumps instead of sleeping."""

    def __init__(self, start: datetime = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)) -> None:
        self.now = start
        self.slept: list[float] = []

    def __call__(self) -> datetime:
        current = self.now
        self.now += timedelta(seconds=1)
        return current

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += timedelta(seconds=seconds)
