"""
Minimal HTTP render service for local automation (Power Automate desktop / testing).

POST /render with multipart: excel, template; optional JSON meta fields.
Response: application/vnd...wordprocessingml.document

Run: python -m automate.http_server --port 8765
Bind localhost only by default. Non-localhost bind requires ESA_API_KEY.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automate.multipart import (  # noqa: E402
    MultipartParseError,
    parse_multipart_form,
    read_limited_body,
)
from automate.render import render_report_from_bytes  # noqa: E402
from esa_auth import AuthContext, AuthError, Role, auth_from_headers, require_role  # noqa: E402
from esa_logging import get_logger, log_event  # noqa: E402
from esa_observability import capture_exception, increment, observe_duration  # noqa: E402
from esa_rate_limit import RateLimitExceeded, check_rate_limit  # noqa: E402
from security import MAX_HTTP_POST_BYTES, sanitize_download_filename, user_safe_error  # noqa: E402

logger = get_logger(__name__)

_LOCALHOST_BINDS = frozenset({"127.0.0.1", "localhost", "::1"})


def _is_localhost_bind(host: str) -> bool:
    normalized = host.strip().lower()
    if normalized in _LOCALHOST_BINDS:
        return True
    if normalized.startswith("127."):
        return True
    return False


def _require_api_key_for_remote_bind(host: str) -> None:
    if _is_localhost_bind(host):
        return
    if not os.environ.get("ESA_API_KEY", "").strip():
        print(
            "ERROR: Binding to a non-localhost address requires ESA_API_KEY to be set.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def _api_key_rate_bucket(headers: dict[str, str]) -> str | None:
    hdrs = {k.lower(): v for k, v in headers.items()}
    api_key = hdrs.get("x-esa-api-key", "").strip()
    if not api_key:
        return None
    digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
    return f"key:{digest}"


def _rate_limit_key(ctx: AuthContext | None, headers: dict[str, str], peer: str) -> str:
    """Bucket by API-key digest (not spoofable user_id), else peer IP."""
    key_bucket = _api_key_rate_bucket(headers)
    if key_bucket:
        return key_bucket
    if ctx is not None and ctx.user_id:
        return f"user:{ctx.user_id}"
    return f"ip:{peer}"


def _meta_with_audit_identity(
    meta: dict[str, str] | None,
    ctx: AuthContext | None,
) -> dict[str, str] | None:
    if ctx is None:
        return meta
    out = dict(meta or {})
    out["audit_actor"] = ctx.user_id
    out["tenant_id"] = ctx.tenant_id
    out.setdefault("prepared_by", ctx.user_id)
    return out


def _security_headers(handler: BaseHTTPRequestHandler) -> None:
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Frame-Options", "DENY")


class RenderHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write(f"{self.address_string()} - {format % args}\n")

    def do_GET(self) -> None:
        if self.path in ("/", "/health"):
            body = b'{"status":"ok","service":"esa-report-render"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            _security_headers(self)
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path != "/render":
            self.send_error(404)
            return

        peer = self.client_address[0]
        header_map = {k: v for k, v in self.headers.items()}

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json_error(400, "Invalid Content-Length", close=True)
            return
        if content_length > MAX_HTTP_POST_BYTES:
            self._json_error(413, "Request body too large", close=True)
            return

        # Brute-force / flood protection before auth (shared IP bucket).
        try:
            check_rate_limit(f"ip:{peer}")
        except RateLimitExceeded as exc:
            self._json_error(429, str(exc), close=True)
            return

        try:
            ctx = auth_from_headers(header_map)
            require_role(ctx, Role.AUTHOR)
        except AuthError as exc:
            self._json_error(401, user_safe_error(exc), close=True)
            return

        # Per-credential bucket after successful auth.
        try:
            check_rate_limit(_rate_limit_key(ctx, header_map, peer))
        except RateLimitExceeded as exc:
            self._json_error(429, str(exc), close=True)
            return

        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            self._json_error(400, "Expected multipart/form-data with excel and template files")
            return

        try:
            body = read_limited_body(self.rfile, content_length, max_bytes=MAX_HTTP_POST_BYTES)
            form = parse_multipart_form(body, ctype)
        except MultipartParseError as exc:
            self._json_error(400, user_safe_error(exc))
            return

        excel_field = form.get("excel")
        template_field = form.get("template")
        if (
            excel_field is None
            or template_field is None
            or not excel_field.data
            or not template_field.data
        ):
            self._json_error(400, "Missing excel or template file fields")
            return

        excel_bytes = excel_field.data
        template_bytes = template_field.data
        meta_field = form.get("meta")
        meta: dict[str, str] | None = None
        if meta_field and meta_field.data:
            try:
                loaded = json.loads(meta_field.data.decode("utf-8"))
                if not isinstance(loaded, dict):
                    self._json_error(400, "meta must be a JSON object")
                    return
                meta = {str(k): str(v) for k, v in loaded.items()}
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._json_error(400, "meta must be valid JSON")
                return

        meta = _meta_with_audit_identity(meta, ctx)

        try:
            with observe_duration("http.render"):
                docx_bytes, warnings, _ctx, _record, _appendices = render_report_from_bytes(
                    excel_bytes,
                    template_bytes,
                    meta=meta,
                    excel_filename=excel_field.filename or "upload.xlsx",
                    template_filename=template_field.filename or "upload.docx",
                )
            increment("http.render.success")
            log_event(logger, "http.render.success", client=peer)
        except Exception as e:
            capture_exception(e, context={"path": self.path})
            self._json_error(500, user_safe_error(e))
            return

        filename = sanitize_download_filename("esa_report.docx")
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.send_header("Content-Length", str(len(docx_bytes)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        _security_headers(self)
        if warnings:
            self.send_header("X-ESA-Warnings", json.dumps(warnings)[:2000])
        self.end_headers()
        self.wfile.write(docx_bytes)

    def _json_error(self, code: int, message: str, *, close: bool = False) -> None:
        body = json.dumps({"error": message}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if close:
            self.send_header("Connection", "close")
        _security_headers(self)
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="ESA report render HTTP service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    _require_api_key_for_remote_bind(args.host)
    server = HTTPServer((args.host, args.port), RenderHandler)
    print(f"ESA render service http://{args.host}:{args.port}/render (health: /health)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
