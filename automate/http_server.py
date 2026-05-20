"""
Minimal HTTP render service for local automation (Power Automate desktop / testing).

POST /render with multipart: excel, template; optional JSON meta fields.
Response: application/vnd...wordprocessingml.document

Run: python -m automate.http_server --port 8765
Bind localhost only by default.
"""

from __future__ import annotations

import argparse
import cgi
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automate.render import render_report_from_bytes  # noqa: E402
from security import user_safe_error  # noqa: E402


class RenderHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    def do_GET(self) -> None:
        if self.path in ("/", "/health"):
            body = b'{"status":"ok","service":"esa-report-render"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path != "/render":
            self.send_error(404)
            return

        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            self._json_error(400, "Expected multipart/form-data with excel and template files")
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": ctype,
            },
        )
        excel_field = form.get("excel")
        template_field = form.get("template")
        if excel_field is None or template_field is None or not excel_field.file or not template_field.file:
            self._json_error(400, "Missing excel or template file fields")
            return

        excel_bytes = excel_field.file.read()
        template_bytes = template_field.file.read()
        meta_raw = form.getvalue("meta")
        meta: dict[str, str] | None = None
        if meta_raw:
            try:
                meta = json.loads(meta_raw)
            except json.JSONDecodeError:
                self._json_error(400, "meta must be valid JSON")
                return

        try:
            docx_bytes, warnings, _ctx, _record = render_report_from_bytes(
                excel_bytes,
                template_bytes,
                meta=meta,
                excel_filename=getattr(excel_field, "filename", None) or "upload.xlsx",
                template_filename=getattr(template_field, "filename", None) or "upload.docx",
            )
        except Exception as e:
            self._json_error(500, user_safe_error(e))
            return

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.send_header("Content-Length", str(len(docx_bytes)))
        if warnings:
            self.send_header("X-ESA-Warnings", json.dumps(warnings)[:2000])
        self.end_headers()
        self.wfile.write(docx_bytes)

    def _json_error(self, code: int, message: str) -> None:
        body = json.dumps({"error": message}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="ESA report render HTTP service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = HTTPServer((args.host, args.port), RenderHandler)
    print(f"ESA render service http://{args.host}:{args.port}/render (health: /health)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
