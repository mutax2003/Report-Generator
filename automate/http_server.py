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
import io
import json
import os
import socket
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
# Total wall-clock budget for reading one request (line + headers + body). The socket
# timeout above is per read, so a client trickling one byte per interval would never
# hit it; this deadline bounds how long any request can pin a handler thread.
_DEFAULT_REQUEST_DEADLINE_SEC = 60.0
_DEFAULT_MAX_CONNECTIONS = 32
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


def request_deadline_sec() -> float:
    """Overall read deadline per request (``ESA_HTTP_REQUEST_DEADLINE_SEC``, default 60 s)."""
    return _env_float("ESA_HTTP_REQUEST_DEADLINE_SEC", _DEFAULT_REQUEST_DEADLINE_SEC)


def max_connections() -> int:
    """Cap on concurrently open connections (``ESA_HTTP_MAX_CONNECTIONS``, default 32)."""
    return _env_int("ESA_HTTP_MAX_CONNECTIONS", _DEFAULT_MAX_CONNECTIONS)


class _DeadlineSocketReader(io.RawIOBase):
    """Raw socket reader that enforces an overall deadline on top of the per-read timeout.

    Each ``recv`` waits at most ``min(per_read_timeout, time left)``; once the handler's
    deadline has passed, reads raise ``TimeoutError`` (an ``OSError``), which
    ``BaseHTTPRequestHandler`` and the body readers treat as a dropped client. The socket
    timeout is restored after every read so response writes keep the normal timeout.
    """

    def __init__(self, sock: socket.socket, handler: RenderHandler) -> None:
        super().__init__()
        self._sock = sock
        self._handler = handler

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        per_read = self._handler.per_read_timeout
        deadline = self._handler.read_deadline
        if deadline is None:
            return self._sock.recv_into(buffer)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("request read deadline exceeded")
        wait = min(per_read, remaining)
        self._sock.settimeout(wait)
        try:
            return self._sock.recv_into(buffer)
        finally:
            self._sock.settimeout(per_read)


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


_BUSY_BODY = b'{"error": "Too many open connections; retry later."}'
_BUSY_RESPONSE = (
    b"HTTP/1.1 503 Service Unavailable\r\n"
    b"Content-Type: application/json\r\n"
    b"Content-Length: " + str(len(_BUSY_BODY)).encode("ascii") + b"\r\n"
    b"Retry-After: 5\r\n"
    b"Connection: close\r\n\r\n" + _BUSY_BODY
)


class RenderHTTPServer(ThreadingHTTPServer):
    """Thread-per-connection server so one stalled client cannot block every render.

    Open connections are capped (``ESA_HTTP_MAX_CONNECTIONS``); over the cap a client gets
    an immediate 503 and is closed instead of spawning another handler thread.
    """

    daemon_threads = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._connection_slots = threading.BoundedSemaphore(max_connections())
        super().__init__(*args, **kwargs)

    def process_request(self, request: Any, client_address: Any) -> None:
        if not self._connection_slots.acquire(blocking=False):
            logger.warning("Connection cap reached; rejecting %s", client_address)
            try:
                request.settimeout(1.0)
                request.sendall(_BUSY_RESPONSE)
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._connection_slots.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._connection_slots.release()

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
    timeout = _DEFAULT_SOCKET_TIMEOUT_SEC
    # Per-read socket timeout for this connection (``ESA_HTTP_SOCKET_TIMEOUT_SEC``).
    per_read_timeout: float = _DEFAULT_SOCKET_TIMEOUT_SEC
    # Wall-clock deadline for reads of the current request (None between requests).
    read_deadline: float | None = None

    def setup(self) -> None:
        super().setup()
        self.per_read_timeout = socket_timeout_sec()
        self.connection.settimeout(self.per_read_timeout)
        # Swap the stock buffered reader for one that also enforces the overall deadline.
        self.rfile.close()
        self.rfile = io.BufferedReader(_DeadlineSocketReader(self.connection, self))

    def handle_one_request(self) -> None:
        # Covers the request line, headers and body (including idle keep-alive waits).
        self.read_deadline = time.monotonic() + request_deadline_sec()
        try:
            super().handle_one_request()
        finally:
            self.read_deadline = None

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
                # Still drain (bounded by size cap + deadlines) so the client sees the 429
                # rather than a connection reset.
                self._reject_before_body(429, str(limited), content_length, retry_after=True)
                return
            self._reject_before_body(401, user_safe_error(exc), content_length)
            return

        # Take a render slot *before* reading the body so concurrent callers never hold
        # body + parsed copies while waiting, and a 503 does not cost the caller quota.
        slots = _render_semaphore()
        if not slots.acquire(blocking=False):
            self._reject_before_body(
                503, "Server busy; retry later.", content_length, retry_after=True
            )
            return
        try:
            result = self._read_and_render(ctx, header_map, peer, content_length)
        finally:
            slots.release()
        if result is None:
            return
        docx_bytes, warnings = result

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

    def _read_and_render(
        self,
        ctx: AuthContext,
        header_map: dict[str, str],
        peer: str,
        content_length: int,
    ) -> tuple[bytes, list[str]] | None:
        """Quota check, body read/parse and render while holding a render slot.

        Returns ``(docx_bytes, warnings)``, or ``None`` after an error response was sent.
        """
        # Authenticated render quota: per API-key digest (or IP when auth is off).
        try:
            check_rate_limit(_rate_limit_key(ctx, header_map, peer))
        except RateLimitExceeded as exc:
            self._reject_before_body(429, str(exc), content_length, retry_after=True)
            return None

        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            self._reject_before_body(
                400, "Expected multipart/form-data with excel and template files", content_length
            )
            return None

        try:
            body = read_limited_body(self.rfile, content_length, max_bytes=MAX_HTTP_POST_BYTES)
            form = parse_multipart_form(body, ctype)
        except MultipartParseError as exc:
            self._json_error(400, user_safe_error(exc), close=True)
            return None
        except OSError:
            # Client stalled past the read deadline or vanished mid-body; drop quietly.
            self.close_connection = True
            return None
        del body

        excel_field = form.get("excel")
        template_field = form.get("template")
        if (
            excel_field is None
            or template_field is None
            or not excel_field.data
            or not template_field.data
        ):
            self._json_error(400, "Missing excel or template file fields")
            return None

        excel_bytes = excel_field.data
        template_bytes = template_field.data
        meta_field = form.get("meta")
        meta: dict[str, str] | None = None
        if meta_field and meta_field.data:
            try:
                loaded = json.loads(meta_field.data.decode("utf-8"))
                if not isinstance(loaded, dict):
                    self._json_error(400, "meta must be a JSON object")
                    return None
                meta = {str(k): str(v) for k, v in loaded.items()}
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._json_error(400, "meta must be valid JSON")
                return None

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
            return None
        return docx_bytes, list(warnings)

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
