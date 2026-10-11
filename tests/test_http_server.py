"""Tests for multipart parser and HTTP server helpers."""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _encode_multipart(fields: list[tuple[str, str, bytes, str | None]]) -> tuple[bytes, str]:
    boundary = "----ESAFormBoundary7MA4YWxkTrZu0gW"
    parts: list[bytes] = []
    for name, filename, data, content_type in fields:
        disposition = f'Content-Disposition: form-data; name="{name}"'
        if filename:
            disposition += f'; filename="{filename}"'
        header_lines = [disposition]
        if content_type:
            header_lines.append(f"Content-Type: {content_type}")
        parts.append(
            f"--{boundary}\r\n".encode("ascii")
            + "\r\n".join(header_lines).encode("utf-8")
            + b"\r\n\r\n"
            + data
            + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode("ascii"))
    body = b"".join(parts)
    content_type = f"multipart/form-data; boundary={boundary}"
    return body, content_type


class MultipartParserTests(unittest.TestCase):
    def test_parse_excel_and_template_fields(self) -> None:
        from automate.multipart import parse_multipart_form

        body, ctype = _encode_multipart(
            [
                ("excel", "data.xlsx", b"excel-bytes", "application/vnd.ms-excel"),
                (
                    "template",
                    "tpl.docx",
                    b"docx-bytes",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
                ("meta", "", b'{"prepared_by":"Test"}', "application/json"),
            ]
        )
        form = parse_multipart_form(body, ctype)
        self.assertEqual(form["excel"].data, b"excel-bytes")
        self.assertEqual(form["excel"].filename, "data.xlsx")
        self.assertEqual(form["template"].data, b"docx-bytes")
        self.assertEqual(form["meta"].data, b'{"prepared_by":"Test"}')

    def test_read_limited_body_enforces_cap(self) -> None:
        from automate.multipart import MultipartParseError, read_limited_body

        source = io.BytesIO(b"x" * 20)
        with self.assertRaises(MultipartParseError):
            read_limited_body(source, 20, max_bytes=10)


class HttpServerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.xlsx = ROOT / "samples" / "sample_data.xlsx"
        cls.tpl = ROOT / "samples" / "sample_template.docx"
        if not cls.xlsx.is_file() or not cls.tpl.is_file():
            raise unittest.SkipTest("Run scripts/create_samples.py first")

    def setUp(self) -> None:
        from esa_rate_limit import reset_rate_limits

        reset_rate_limits()

    def test_multipart_render_handler(self) -> None:
        import json
        import threading
        from http.client import HTTPConnection

        from automate.http_server import RenderHandler, RenderHTTPServer

        body, ctype = _encode_multipart(
            [
                ("excel", self.xlsx.name, self.xlsx.read_bytes(), "application/vnd.ms-excel"),
                (
                    "template",
                    self.tpl.name,
                    self.tpl.read_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
                (
                    "meta",
                    "",
                    json.dumps({"report_phase": "Phase 2", "prepared_by": "HTTP"}).encode("utf-8"),
                    "application/json",
                ),
            ]
        )

        server = RenderHTTPServer(("127.0.0.1", 0), RenderHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=30)
            conn.request(
                "POST",
                "/render",
                body=body,
                headers={"Content-Type": ctype, "Content-Length": str(len(body))},
            )
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)
            payload = resp.read()
            self.assertTrue(payload.startswith(b"PK"))
        finally:
            server.shutdown()
            server.server_close()

    def test_remote_bind_requires_api_key(self) -> None:
        import os
        from unittest.mock import patch

        from automate import http_server

        prev = os.environ.pop("ESA_API_KEY", None)
        try:
            with patch.object(sys, "argv", ["http_server", "--host", "0.0.0.0"]):
                with self.assertRaises(SystemExit) as ctx:
                    http_server.main()
                self.assertEqual(ctx.exception.code, 2)
        finally:
            if prev is not None:
                os.environ["ESA_API_KEY"] = prev

    def test_rate_limit_key_prefers_api_key_digest(self) -> None:
        from automate.http_server import _rate_limit_key
        from esa_auth import AuthContext, Role

        ctx = AuthContext(user_id="alice", tenant_id="t1", roles=(Role.AUTHOR,))
        key = _rate_limit_key(ctx, {"X-ESA-API-Key": "secret"}, "10.0.0.1")
        self.assertTrue(key.startswith("key:"))
        # Spoofable user_id must not be the bucket when an API key is present.
        self.assertNotEqual(key, "user:alice")

    def test_rate_limit_key_falls_back_to_ip(self) -> None:
        from automate.http_server import _rate_limit_key

        self.assertEqual(_rate_limit_key(None, {}, "10.0.0.9"), "ip:10.0.0.9")

    def test_render_rejects_missing_api_key_with_401(self) -> None:
        import json
        import os
        import threading
        from http.client import HTTPConnection
        from automate.http_server import RenderHandler, RenderHTTPServer

        body, ctype = _encode_multipart(
            [
                ("excel", self.xlsx.name, self.xlsx.read_bytes(), "application/vnd.ms-excel"),
                (
                    "template",
                    self.tpl.name,
                    self.tpl.read_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            ]
        )

        prev = os.environ.get("ESA_API_KEY")
        os.environ["ESA_API_KEY"] = "test-secret-key"
        server = RenderHTTPServer(("127.0.0.1", 0), RenderHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=15)
            conn.request(
                "POST",
                "/render",
                body=body,
                headers={"Content-Type": ctype, "Content-Length": str(len(body))},
            )
            resp = conn.getresponse()
            payload = resp.read().decode("utf-8")
            self.assertEqual(resp.status, 401)
            data = json.loads(payload)
            self.assertIn("error", data)
            self.assertNotIn("traceback", payload.lower())
            self.assertNotIn("C:\\", payload)
        finally:
            server.shutdown()
            server.server_close()
            if prev is None:
                os.environ.pop("ESA_API_KEY", None)
            else:
                os.environ["ESA_API_KEY"] = prev

    def test_meta_with_audit_identity_binds_actor(self) -> None:
        from automate.http_server import _meta_with_audit_identity
        from esa_auth import AuthContext, Role

        ctx = AuthContext(user_id="bob", tenant_id="tenant-a", roles=(Role.AUTHOR,))
        meta = _meta_with_audit_identity({"prepared_by": "spoofed"}, ctx)
        assert meta is not None
        self.assertEqual(meta["audit_actor"], "bob")
        self.assertEqual(meta["tenant_id"], "tenant-a")
        self.assertEqual(meta["prepared_by"], "spoofed")


class _ServerFixture:
    """Run RenderHTTPServer on an ephemeral localhost port for one test."""

    def __init__(self) -> None:
        import threading

        from automate.http_server import RenderHandler, RenderHTTPServer

        self.server = RenderHTTPServer(("127.0.0.1", 0), RenderHandler)
        self.port = self.server.server_address[1]
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 15,
    ) -> tuple[int, dict[str, str], bytes]:
        from http.client import HTTPConnection

        conn = HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            return resp.status, dict(resp.getheaders()), resp.read()
        finally:
            conn.close()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


class HttpServerHardeningTests(unittest.TestCase):
    """Slowloris resistance, clean early rejects, and auth-vs-quota rate limiting."""

    _ENV_KEYS = (
        "ESA_API_KEY",
        "ESA_REQUIRE_API_KEY",
        "ESA_DISABLE_RATE_LIMIT",
        "ESA_RATE_LIMIT_MAX",
        "ESA_RATE_LIMIT_WINDOW_SEC",
        "ESA_AUTH_FAIL_MAX",
        "ESA_AUTH_FAIL_WINDOW_SEC",
        "ESA_HTTP_SOCKET_TIMEOUT_SEC",
    )

    def setUp(self) -> None:
        import os

        from esa_rate_limit import reset_rate_limits

        self._prev_env = {k: os.environ.get(k) for k in self._ENV_KEYS}
        for key in self._ENV_KEYS:
            os.environ.pop(key, None)
        reset_rate_limits()
        self.fixture: _ServerFixture | None = None

    def tearDown(self) -> None:
        import os

        from esa_rate_limit import reset_rate_limits

        if self.fixture is not None:
            self.fixture.close()
        for key, val in self._prev_env.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        reset_rate_limits()

    def _start(self, **env: str) -> _ServerFixture:
        import os

        os.environ.update(env)
        self.fixture = _ServerFixture()
        return self.fixture

    def test_server_is_threaded_with_daemon_threads(self) -> None:
        from http.server import ThreadingHTTPServer

        from automate.http_server import RenderHandler, RenderHTTPServer, socket_timeout_sec

        self.assertTrue(issubclass(RenderHTTPServer, ThreadingHTTPServer))
        self.assertTrue(RenderHTTPServer.daemon_threads)
        self.assertIsNotNone(RenderHandler.timeout)
        self.assertGreater(socket_timeout_sec(), 0)

    def test_stalled_connection_does_not_block_other_clients(self) -> None:
        import socket
        import time

        fx = self._start(ESA_HTTP_SOCKET_TIMEOUT_SEC="2")
        stall = socket.create_connection(("127.0.0.1", fx.port), timeout=10)
        try:
            stall.sendall(b"GET /health HTTP/1.1\r\nHost: x\r\nX-Slow: ")  # never finished
            t0 = time.monotonic()
            status, _headers, _body = fx.request("GET", "/health", timeout=10)
            self.assertEqual(status, 200)
            self.assertLess(time.monotonic() - t0, 5.0)
            # The server drops the stalled client after its socket timeout.
            stall.settimeout(15)
            try:
                leftover = stall.recv(1024)
            except (ConnectionResetError, ConnectionAbortedError):
                leftover = b""
            self.assertNotIn(b"200 OK", leftover)
        finally:
            stall.close()

    def test_unauthenticated_flood_does_not_lock_out_valid_key(self) -> None:
        key = "valid-test-key-0123456789abcdef"
        fx = self._start(
            ESA_API_KEY=key,
            ESA_AUTH_FAIL_MAX="3",
            ESA_RATE_LIMIT_MAX="2",
        )
        body = b"x" * 1024
        bad = {"X-ESA-API-Key": "wrong", "Content-Type": "text/plain"}
        statuses = [fx.request("POST", "/render", body=body, headers=bad)[0] for _ in range(5)]
        self.assertEqual(statuses[:3], [401, 401, 401])
        self.assertEqual(statuses[3:], [429, 429])

        good = {"X-ESA-API-Key": key, "Content-Type": "text/plain"}
        # Valid key from the same IP is not blocked by the failed-auth bucket; text/plain
        # is rejected with 400 after auth, but it still counts against the render quota.
        first = fx.request("POST", "/render", body=body, headers=good)[0]
        second = fx.request("POST", "/render", body=body, headers=good)[0]
        third, headers, _ = fx.request("POST", "/render", body=body, headers=good)
        self.assertEqual((first, second), (400, 400))
        self.assertEqual(third, 429)
        self.assertIn("Retry-After", headers)

    def test_early_reject_reads_body_and_closes_cleanly(self) -> None:
        """401 with a sizeable body must be readable (no WinError 10053 reset)."""
        fx = self._start(ESA_API_KEY="valid-test-key-0123456789abcdef")
        body = b"y" * (512 * 1024)
        for _ in range(5):
            status, headers, payload = fx.request(
                "POST",
                "/render",
                body=body,
                headers={"Content-Type": "multipart/form-data; boundary=zzz"},
            )
            self.assertEqual(status, 401)
            self.assertEqual(headers.get("Connection", "").lower(), "close")
            self.assertIn(b"error", payload)

    def test_negative_content_length_rejected(self) -> None:
        import socket

        fx = self._start()
        with socket.create_connection(("127.0.0.1", fx.port), timeout=10) as sock:
            sock.sendall(
                b"POST /render HTTP/1.1\r\nHost: x\r\nContent-Length: -5\r\n\r\n"
            )
            first_line = sock.recv(200).split(b"\r\n")[0]
        self.assertIn(b"400", first_line)


if __name__ == "__main__":
    unittest.main()
