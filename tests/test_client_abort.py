"""Aborted clients must never print a server traceback.

Browsers abort in-flight requests on navigation, reload and HMR, and pages
that poll (health, library, jobs) keep several in flight at once. On Windows
the aborted write surfaces as ``ConnectionAbortedError`` (WinError 10053),
which ``_json`` did not catch — so every cancelled poll printed an
"Exception occurred during processing of request" traceback. These tests pin
the tolerant behavior at both levels: the unit (a dead socket is swallowed)
and the socket (an abort leaves no traceback and the server keeps serving).
"""
import io
import json
import socket
import threading
from contextlib import redirect_stderr
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest


@pytest.fixture
def live_server():
    """Real Handler on an ephemeral port. Closes cleanly after each test."""
    from app.web import Handler

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def _dead_handler(write_error):
    """A Handler whose socket dies on write, with the rest stubbed."""
    from app.web import Handler

    handler = Handler.__new__(Handler)
    handler.send_response = lambda *args: None
    handler.send_header = lambda *args: None
    handler.end_headers = lambda: None

    class DeadSocket(io.RawIOBase):
        def write(self, _data):
            raise write_error

    handler.wfile = DeadSocket()  # type: ignore[assignment]
    return handler


@pytest.mark.parametrize(
    "error",
    [BrokenPipeError(), ConnectionResetError(), ConnectionAbortedError()],
)
def test_json_swallow_client_abort(error):
    """_json drops the response instead of raising when the reader is gone."""
    assert _dead_handler(error)._json({"ok": True}) is None


def test_send_file_swallows_client_abort(tmp_path):
    """A cancelled download stops the stream instead of tracebacks."""
    from app.web import Handler

    target = tmp_path / "download.bin"
    target.write_bytes(b"x" * 65536)
    handler = Handler.__new__(Handler)
    handler.send_response = lambda *args: None
    handler.send_header = lambda *args: None
    handler.end_headers = lambda: None

    class DeadSocket(io.RawIOBase):
        def write(self, _data):
            raise ConnectionAbortedError()

    handler.wfile = DeadSocket()  # type: ignore[assignment]
    assert handler._send_file(target, "application/octet-stream") is None


def test_json_still_writes_to_a_live_socket():
    """The guard only swallows disconnects — normal responses are intact."""
    from app.web import Handler

    handler = Handler.__new__(Handler)
    handler.send_response = lambda *args: None
    handler.send_header = lambda *args: None
    handler.end_headers = lambda: None
    handler.wfile = io.BytesIO()  # type: ignore[assignment]
    handler._json({"ok": True})
    assert json.loads(handler.wfile.getvalue()) == {"ok": True}  # type: ignore[union-attr]


def _raw_get_nowait(base, path):
    """Send one request and close without reading — a cancelled poll."""
    import urllib.parse

    parsed = urllib.parse.urlparse(base)
    head = (
        f"GET {path} HTTP/1.1\r\nHost: {parsed.hostname}:{parsed.port}\r\n"
        "Connection: close\r\n\r\n"
    ).encode()
    sock = socket.create_connection((parsed.hostname, parsed.port), timeout=5)
    try:
        sock.sendall(head)
    finally:
        sock.close()


def _raw_get(base, path):
    """Read one response over a raw socket (urllib honors the OS proxy here)."""
    import urllib.parse

    parsed = urllib.parse.urlparse(base)
    head = (
        f"GET {path} HTTP/1.1\r\nHost: {parsed.hostname}:{parsed.port}\r\n"
        "Connection: close\r\n\r\n"
    ).encode()
    with socket.create_connection((parsed.hostname, parsed.port), timeout=10) as sock:
        sock.sendall(head)
        chunks = []
        while True:
            data = sock.recv(65536)
            if not data:
                break
            chunks.append(data)
    head_text, _, body = b"".join(chunks).partition(b"\r\n\r\n")
    status = int(head_text.decode("latin-1").splitlines()[0].split()[1])
    return status, json.loads(body or b"{}")


def test_aborted_poll_leaves_no_traceback_and_server_serves(live_server):
    """Cancel several polls, then prove the server is alive and quiet."""
    captured = io.StringIO()
    with redirect_stderr(captured):
        for _ in range(5):
            _raw_get_nowait(live_server, "/api/library")
            _raw_get_nowait(live_server, "/api/health")
        # The handler threads must finish (and would print) inside the
        # redirect — a bare abort returns fast, 1s is ample on loopback.
        import time

        deadline = time.time() + 10
        status, payload = None, {}
        while time.time() < deadline:
            try:
                status, payload = _raw_get(live_server, "/api/library")
                break
            except OSError:
                time.sleep(0.05)
        import time as _time

        _time.sleep(1.0)
    assert "Traceback" not in captured.getvalue()
    assert status == 200
    assert "total" in payload


def test_aborted_download_leaves_no_traceback(live_server, tmp_path):
    """A cover that nobody waits for must not print either."""
    from app.web import COVERS_DIR

    cover = Path(str(COVERS_DIR)) / "0.png"
    cover.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 1024)
    try:
        captured = io.StringIO()
        with redirect_stderr(captured):
            _raw_get_nowait(live_server, "/covers/0.png")
            import time as _time

            _time.sleep(1.0)
        assert "Traceback" not in captured.getvalue()
    finally:
        cover.unlink(missing_ok=True)
