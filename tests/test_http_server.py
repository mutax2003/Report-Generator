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

    def test_multipart_render_handler(self) -> None:
        import json
        import threading
        from http.client import HTTPConnection

        from automate.http_server import RenderHandler
        from http.server import HTTPServer

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

        server = HTTPServer(("127.0.0.1", 0), RenderHandler)
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
        from http.server import HTTPServer

        from automate.http_server import RenderHandler

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
        server = HTTPServer(("127.0.0.1", 0), RenderHandler)
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


if __name__ == "__main__":
    unittest.main()
