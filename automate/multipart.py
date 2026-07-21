"""
Minimal multipart/form-data parser (stdlib-only replacement for deprecated cgi.FieldStorage).

Supports file fields and simple text fields used by automate/http_server.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import BinaryIO


@dataclass(frozen=True)
class MultipartField:
    name: str
    filename: str | None
    data: bytes


class MultipartParseError(ValueError):
    """Invalid or unsupported multipart payload."""


def _parse_boundary(content_type: str) -> str:
    match = re.search(r"boundary=([^;\s]+)", content_type, flags=re.IGNORECASE)
    if not match:
        raise MultipartParseError("Missing multipart boundary")
    boundary = match.group(1).strip().strip('"')
    if not boundary:
        raise MultipartParseError("Empty multipart boundary")
    return boundary


def parse_multipart_form(
    body: bytes,
    content_type: str,
    *,
    max_fields: int = 32,
) -> dict[str, MultipartField]:
    """Parse multipart/form-data into a name -> field mapping (last wins)."""
    if not body:
        raise MultipartParseError("Empty multipart body")
    boundary = _parse_boundary(content_type)
    delimiter = ("--" + boundary).encode("ascii")
    parts = body.split(delimiter)
    if len(parts) < 2:
        raise MultipartParseError("Malformed multipart body")

    fields: dict[str, MultipartField] = {}
    for raw_part in parts[1:]:
        chunk = raw_part.strip(b"\r\n")
        if not chunk or chunk == b"--":
            continue
        if len(fields) >= max_fields:
            raise MultipartParseError("Too many multipart fields")

        header_blob, _, payload = chunk.partition(b"\r\n\r\n")
        if not header_blob:
            raise MultipartParseError("Missing multipart headers")
        payload = payload.rstrip(b"\r\n")
        if payload.endswith(b"--"):
            payload = payload[:-2].rstrip(b"\r\n")

        headers = header_blob.decode("utf-8", errors="replace").split("\r\n")
        disposition = next((h for h in headers if h.lower().startswith("content-disposition:")), "")
        name_match = re.search(r'name="([^"]+)"', disposition)
        if not name_match:
            continue
        name = name_match.group(1)
        file_match = re.search(r'filename="([^"]*)"', disposition)
        filename = file_match.group(1) if file_match else None
        fields[name] = MultipartField(name=name, filename=filename or None, data=payload)

    if not fields:
        raise MultipartParseError("No multipart fields found")
    return fields


def read_limited_body(source: BinaryIO, content_length: int, *, max_bytes: int) -> bytes:
    """Read exactly content_length bytes, enforcing max_bytes."""
    if content_length < 0:
        raise MultipartParseError("Invalid Content-Length")
    if content_length > max_bytes:
        raise MultipartParseError(f"Request body exceeds limit ({max_bytes} bytes)")
    data = source.read(content_length)
    if len(data) != content_length:
        raise MultipartParseError("Unexpected end of request body")
    return data
