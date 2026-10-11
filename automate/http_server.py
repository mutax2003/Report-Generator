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
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
from esa_rate_limit import RateLimitExceeded, check_rate_limit, record_failed_auth  # noqa: E402
from security import MAX_HTTP_POST_BYTES, sanitize_download_filename, user_safe_error  # noqa: E402

logger = get_logger(__name__)

_LOCALHOST_BINDS = frozenset({"127.0.0.1", "localhost", "::1"})

_DEFAULT_SOCKET_TIMEOUT_SEC = 30.0
_DEFAULT_MAX_CONCURRENT_RENDERS = 4
# Early-reject paths read (and discard) the request body so the client can finish
# sending before we respond -- closing with unread data makes Windows send a TCP RST
# (WinError 10053/10054 on the client). Bounded by size cap and wall-clock deadline.
_DRAIN_DEADLINE_SEC = 10.0
_DRAIN_CHUNK = 64 * 1024
_MIN_RECOMMENDED_API_KEY_LEN = 24


def _env_float(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, "") or default)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, "") or default)
    except ValueError:
        return default
    return value if value > 0 else default


def socket_timeout_sec() -> float:
    """Per-connection socket timeout (``ESA_HTTP_SOCKET_TIMEOUT_SEC``, default 30 s)."""
    return _env_float("ESA_HTTP_SOCKET_TIMEOUT_SEC", _DEFAULT_SOCKET_TIMEOUT_SEC)


_render_slots_lock = threading.Lock()
_render_slots: threading.BoundedSemaphore | None = None


def _render_semaphore() -> threading.BoundedSemaphore:
    """Cap concurrent renders (``ESA_HTTP_MAX_CONCURRENT_RENDERS``, default 4)."""
    global _render_slots
    with _render_slots_lock:
        if _render_slots is None:
            _render_slots = threading.BoundedSemaphore(
                _env_int("ESA_HTTP_MAX_CONCURRENT_RENDERS", _DEFAULT_MAX_CONCURRENT_RENDERS)
            )
        return _render_slots


class RenderHTTPServer(ThreadingHTTPServer):
    """Thread-per-connection server so one stalled client cannot block every render."""

    daemon_threads = True

    def handle_error(self, request: Any, client_address: Any) -> None:
        """Log client disconnects (WinError 10053/10054, EPIPE) without a stderr traceback."""
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
            logger.info("Client %s disconnected: %s", client_address, type(exc).__name__)
            return
        super().handle_error(request, client_address)


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


def _warn_on_weak_api_key() -> None:
    key = os.environ.get("ESA_API_KEY", "").strip()
    if key and len(key) < _MIN_RECOMMENDED_API_KEY_LEN:
        print(
            "WARNING: ESA_API_KEY is shorter than "
            f"{_MIN_RECOMMENDED_API_KEY_LEN} characters. Failed-auth throttling is per IP "
            "and never blocks a valid key, so use a long random key "
            "(python -c 'import secrets; print(secrets.token_urlsafe(32))').",
            file=sys.stderr,
        )


def _api_key_rate_bucket(headers: dict[str, str]) -> str | None:
    hdrs = {k.lower(): v for k, v in headers.items()}
    api_key = hdrs.get("x-esa-api-key", "").strip()
    if not api_key:
        return None
    digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
    return f"key:{digest}"


def _rate_limit_key(ctx: AuthContext | None, headers: dict[str, str], peer: str) -> str:
    """Authenticated render-quota bucket: API-key digest (not spoofable user_id), else IP.

    Only called after successful auth; unauthenticated failures are throttled separately
    per IP by ``record_failed_auth`` so they never consume a valid client's quota.
    """
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
    # StreamRequestHandler.setup() applies this as the socket timeout, so a slowloris
    # client (partial headers / stalled body) is dropped instead of pinning a thread.
    timeout: float | None = _DEFAULT_SOCKET_TIMEOUT_SEC

    def setup(self) -> None:
        self.timeout = socket_timeout_sec()
        super().setup()

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
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if 0 < length <= MAX_HTTP_POST_BYTES:
                self._drain_request_body(length)
            self.send_error(404)
            return

        peer = self.client_address[0]
        header_map = {k: v for k, v in self.headers.items()}

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json_error(400, "Invalid Content-Length", close=True)
            return
        if content_length < 0:
            self._json_error(400, "Invalid Content-Length", close=True)
            return
        if content_length > MAX_HTTP_POST_BYTES:
            self._json_error(413, "Request body too large", close=True)
            return

        # Auth first: valid credentials are never blocked by someone else's garbage
        # from the same IP / NAT. Failed attempts are throttled per IP separately.
        try:
            ctx = auth_from_headers(header_map)
            require_role(ctx, Role.AUTHOR)
        except AuthError as exc:
            try:
                record_failed_auth(f"ip:{peer}")
            except RateLimitExceeded as limited:
                # Flooding client: reject cheaply without reading the body.
                self._json_error(429, str(limited), close=True, retry_after=True)
                return
            self._reject_before_body(401, user_safe_error(exc), content_length)
            return

        # Authenticated render quota: per API-key digest (or IP when auth is off).
        try:
            check_rate_limit(_rate_limit_key(ctx, header_map, peer))
        except RateLimitExceeded as exc:
            self._reject_before_body(429, str(exc), content_length, retry_after=True)
            return

        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            self._reject_before_body(
                400, "Expected multipart/form-data with excel and template files", content_length
            )
            return

        try:
            body = read_limited_body(self.rfile, content_length, max_bytes=MAX_HTTP_POST_BYTES)
            form = parse_multipart_form(body, ctype)
        except MultipartParseError as exc:
            self._json_error(400, user_safe_error(exc), close=True)
            return
        except OSError:
            # Client stalled past the socket timeout or vanished mid-body; drop quietly.
            self.close_connection = True
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

        slots = _render_semaphore()
        if not slots.acquire(blocking=False):
            self._json_error(503, "Server busy; retry later.", retry_after=True)
            return
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
        finally:
            slots.release()

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

    def _drain_request_body(self, content_length: int) -> None:
        """Read and discard up to content_length bytes (size cap + wall-clock deadline)."""
        remaining = min(max(content_length, 0), MAX_HTTP_POST_BYTES)
        deadline = time.monotonic() + _DRAIN_DEADLINE_SEC
        read_some = getattr(self.rfile, "read1", self.rfile.read)
        try:
            while remaining > 0 and time.monotonic() < deadline:
                chunk = read_some(min(_DRAIN_CHUNK, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
        except OSError:
            pass

    def _reject_before_body(
        self,
        code: int,
        message: str,
        content_length: int,
        *,
        retry_after: bool = False,
    ) -> None:
        """Error response before the body was read: drain it, then close the connection.

        Draining lets clients that send the whole body before reading the response
        (http.client, Power Automate) see the status instead of a connection reset, and
        closing prevents leftover body bytes being parsed as a pipelined request.
        """
        self._drain_request_body(content_length)
        self._json_error(code, message, close=True, retry_after=retry_after)

    def _json_error(
        self,
        code: int,
        message: str,
        *,
        close: bool = False,
        retry_after: bool = False,
    ) -> None:
        body = json.dumps({"error": message}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if retry_after:
            self.send_header("Retry-After", "60")
        if close:
            self.send_header("Connection", "close")
            self.close_connection = True
        _security_headers(self)
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            self.close_connection = True


def main() -> int:
    parser = argparse.ArgumentParser(description="ESA report render HTTP service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    _require_api_key_for_remote_bind(args.host)
    _warn_on_weak_api_key()
    server = RenderHTTPServer((args.host, args.port), RenderHandler)
    print(f"ESA render service http://{args.host}:{args.port}/render (health: /health)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
