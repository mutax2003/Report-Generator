"""
Upload validation, zip-bomb guards, and safe defaults for untrusted user files.
"""

from __future__ import annotations

import io
import logging
import os
import re
import zipfile
from contextlib import contextmanager
from typing import Any, Iterator

logger = logging.getLogger(__name__)

# --- Size limits (tune for your largest legitimate reports) ---
MAX_EXCEL_BYTES = 15 * 1024 * 1024
MAX_TEMPLATE_BYTES = 30 * 1024 * 1024
MAX_APPENDIX_PDF_BYTES = 25 * 1024 * 1024
MAX_RENDERED_DOCX_BYTES = 50 * 1024 * 1024
MAX_HTTP_POST_BYTES = MAX_EXCEL_BYTES + MAX_TEMPLATE_BYTES + 512 * 1024

MAX_ZIP_MEMBERS = 5_000
MAX_ZIP_UNCOMPRESSED_BYTES = 120 * 1024 * 1024
MAX_SINGLE_ZIP_MEMBER_BYTES = 60 * 1024 * 1024
MAX_ZIP_COMPRESSION_RATIO = 80
_ZIP_READ_CHUNK = 64 * 1024

MAX_LAB_ROWS = 10_000
MAX_PROJECT_COLUMNS = 300
MAX_PROJECT_ROWS = 100
MAX_BATCH_REPORTS = 50
MAX_CONTEXT_STRING_LEN = 32_768
MAX_META_VALUE_LEN = 500
MAX_DOWNLOAD_NAME_LEN = 200

# OOXML magic: ZIP local file header
_ZIP_MAGIC = b"PK\x03\x04"
_XLSX_SPREADSHEET_MARKERS = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml",
    "xl/workbook.xml",
)
_DOCX_REQUIRED_PART = "word/document.xml"

# ValueError messages safe to show in the UI (prefix or exact match).
_SAFE_VALUE_ERROR_PREFIXES = (
    "Missing sheet '",
    "Sheet '",
    "Template rendering failed.",
    "Too many ProjectData rows",
    "ProjectData row index",
    "Could not read the Excel file.",
)
_SAFE_VALUE_ERROR_EXACT = frozenset(
    {
        "Excel file is empty.",
        "Template file is empty.",
    }
)


class SecurityError(ValueError):
    """User-facing validation failure (safe to show in UI)."""


class ZipReadBudget:
    """Tracks actual decompressed bytes read from a zip archive."""

    def __init__(self, limit: int = MAX_ZIP_UNCOMPRESSED_BYTES) -> None:
        self.limit = limit
        self.total = 0

    def add(self, n: int) -> None:
        self.total += n
        if self.total > self.limit:
            raise SecurityError("Archive decompressed size exceeds limit (possible zip bomb).")


def _is_safe_zip_member(name: str) -> bool:
    if not name or name.startswith("/") or name.startswith("\\"):
        return False
    parts = name.replace("\\", "/").split("/")
    return ".." not in parts


def _is_encrypted(info: zipfile.ZipInfo) -> bool:
    return bool(info.flag_bits & 0x1)


def _check_zip_member_metadata(info: zipfile.ZipInfo) -> None:
    if not _is_safe_zip_member(info.filename):
        raise SecurityError("Archive contains an unsafe path.")
    if _is_encrypted(info):
        raise SecurityError(f"Encrypted archive entries are not supported ({info.filename}).")
    member_cap = _zip_single_member_limit()
    if info.file_size > member_cap:
        raise SecurityError(
            f"Archive entry '{info.filename}' exceeds size limit "
            f"({info.file_size // (1024 * 1024)} MB)."
        )
    if info.compress_size > 0:
        ratio = info.file_size / max(info.compress_size, 1)
        if ratio > MAX_ZIP_COMPRESSION_RATIO:
            raise SecurityError("Archive looks like a zip bomb (compression ratio too high).")


def read_zip_member(
    zf: zipfile.ZipFile,
    name: str,
    budget: ZipReadBudget,
    *,
    max_member_bytes: int | None = None,
) -> bytes:
    """
    Read one zip member with a global decompressed-byte budget.
    Uses actual bytes read, not ZipInfo.file_size alone.
    """
    cap = max_member_bytes if max_member_bytes is not None else _zip_single_member_limit()
    info = zf.getinfo(name)
    _check_zip_member_metadata(info)

    reader = zf.open(name, "r")
    chunks: list[bytes] = []
    member_read = 0
    try:
        while True:
            chunk = reader.read(_ZIP_READ_CHUNK)
            if not chunk:
                break
            member_read += len(chunk)
            budget.add(len(chunk))
            if member_read > cap:
                raise SecurityError(f"Archive entry '{name}' exceeds size limit while reading.")
            chunks.append(chunk)
    finally:
        reader.close()

    return b"".join(chunks)


def inspect_zip_archive(data: bytes, *, purpose: str) -> list[str]:
    """
    Validate ZIP by reading members with a decompressed-byte budget.
    purpose: 'xlsx' | 'docx'
    """
    if len(data) < 4 or not data.startswith(_ZIP_MAGIC):
        raise SecurityError(f"Not a valid {purpose.upper()} file (expected ZIP archive).")

    try:
        zf = zipfile.ZipFile(io.BytesIO(data), "r")
    except zipfile.BadZipFile as e:
        raise SecurityError(f"Corrupt or invalid {purpose.upper()} archive.") from e

    budget = ZipReadBudget(limit=_zip_uncompressed_limit())
    with zf:
        names = zf.namelist()
        if len(names) > MAX_ZIP_MEMBERS:
            raise SecurityError(
                f"Archive has too many entries ({len(names)}; max {MAX_ZIP_MEMBERS})."
            )

        for info in zf.infolist():
            _check_zip_member_metadata(info)

        if purpose == "docx":
            if not any(n.lower() == _DOCX_REQUIRED_PART for n in names):
                raise SecurityError(
                    "File is not a Word document (.docx): missing word/document.xml."
                )
        elif purpose == "xlsx":
            if not any(n.endswith("[Content_Types].xml") for n in names):
                raise SecurityError("File is not an Excel workbook (.xlsx): invalid package.")
            # Prefer Content_Types + workbook.xml — avoid reading every xl/* part.
            probe_names = [
                n
                for n in names
                if n.endswith("[Content_Types].xml") or n.lower().endswith("xl/workbook.xml")
            ]
            if not probe_names:
                probe_names = [n for n in names if n.startswith("xl/")][:3]
            blob = b""
            for n in probe_names:
                try:
                    part = read_zip_member(zf, n, budget, max_member_bytes=65536)
                    blob += part[:65536]
                    if any(m.encode() in blob for m in _XLSX_SPREADSHEET_MARKERS):
                        break
                except KeyError:
                    continue
            if not any(m.encode() in blob for m in _XLSX_SPREADSHEET_MARKERS):
                raise SecurityError(
                    "File is not an Excel workbook (.xlsx): unexpected content type."
                )
        else:
            raise ValueError(f"Unknown purpose: {purpose}")

        return names


def validate_excel_upload(data: bytes, filename: str = "") -> None:
    del filename  # extension checked in app; magic bytes are authoritative
    if not data:
        raise SecurityError("Excel file is empty.")
    if len(data) > MAX_EXCEL_BYTES:
        mb = MAX_EXCEL_BYTES // (1024 * 1024)
        raise SecurityError(f"Excel file too large (max {mb} MB).")
    inspect_zip_archive(data, purpose="xlsx")


MAX_PDF_TEMPLATE_PAGES = 500
MAX_APPENDIX_PDF_PAGES = 200


def validate_appendix_pdf_upload(data: bytes, filename: str = "") -> None:
    """Validate appendix PDF before zip merge (size + basic PDF structure)."""
    del filename
    if not data:
        raise SecurityError("Appendix PDF is empty.")
    if len(data) > MAX_APPENDIX_PDF_BYTES:
        mb = MAX_APPENDIX_PDF_BYTES // (1024 * 1024)
        raise SecurityError(f"Appendix PDF too large (max {mb} MB).")
    if not data.startswith(b"%PDF"):
        raise SecurityError("Not a valid PDF file (missing %PDF header).")
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise SecurityError("PDF support requires pypdf.") from e
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as e:
        raise SecurityError("Could not read appendix PDF.") from e
    if getattr(reader, "is_encrypted", False):
        try:
            if reader.is_encrypted:
                raise SecurityError("Encrypted appendix PDFs are not supported.")
        except Exception:
            raise SecurityError("Encrypted appendix PDFs are not supported.") from e
    pages = len(reader.pages)
    if pages == 0:
        raise SecurityError("Appendix PDF has no pages.")
    if pages > MAX_APPENDIX_PDF_PAGES:
        raise SecurityError(
            f"Appendix PDF has too many pages ({pages}; max {MAX_APPENDIX_PDF_PAGES})."
        )


def validate_pdf_template_upload(data: bytes, filename: str = "") -> None:
    """Validate PDF before conversion to Word for merge."""
    del filename
    if not data:
        raise SecurityError("Template file is empty.")
    if len(data) > MAX_TEMPLATE_BYTES:
        mb = MAX_TEMPLATE_BYTES // (1024 * 1024)
        raise SecurityError(f"PDF template too large (max {mb} MB).")
    if not data.startswith(b"%PDF"):
        raise SecurityError("Not a valid PDF file (missing %PDF header).")
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise SecurityError("PDF support requires pypdf.") from e
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as e:
        raise SecurityError("Could not read PDF template.") from e
    if getattr(reader, "is_encrypted", False):
        try:
            if reader.is_encrypted:
                raise SecurityError("Encrypted PDF templates are not supported.")
        except Exception:
            raise SecurityError("Encrypted PDF templates are not supported.") from e
    pages = len(reader.pages)
    if pages == 0:
        raise SecurityError("PDF template has no pages.")
    if pages > MAX_PDF_TEMPLATE_PAGES:
        raise SecurityError(
            f"PDF template has too many pages ({pages}; max {MAX_PDF_TEMPLATE_PAGES})."
        )


def _large_template_mode() -> bool:
    return os.environ.get("ESA_ALLOW_LARGE_TEMPLATE") == "1"


def _template_size_limit() -> int:
    """Effective max template bytes (local Phase 1 PDF conversions may exceed default)."""
    limit = MAX_TEMPLATE_BYTES
    if _large_template_mode():
        limit = max(limit, 160 * 1024 * 1024)
    return limit


def _zip_uncompressed_limit() -> int:
    if _large_template_mode():
        return 300 * 1024 * 1024
    return MAX_ZIP_UNCOMPRESSED_BYTES


def _zip_single_member_limit() -> int:
    if _large_template_mode():
        return 160 * 1024 * 1024
    return MAX_SINGLE_ZIP_MEMBER_BYTES


def validate_template_upload(data: bytes, filename: str = "") -> None:
    del filename
    if not data:
        raise SecurityError("Template file is empty.")
    limit = _template_size_limit()
    if len(data) > limit:
        mb = limit // (1024 * 1024)
        raise SecurityError(f"Template file too large (max {mb} MB).")
    inspect_zip_archive(data, purpose="docx")


def validate_rendered_output(data: bytes) -> None:
    limit = MAX_RENDERED_DOCX_BYTES
    if _large_template_mode():
        limit = max(limit, 160 * 1024 * 1024)
    if len(data) > limit:
        raise SecurityError("Generated report exceeds maximum allowed size.")
    # Re-validate structure and zip budget on generated output
    inspect_zip_archive(data, purpose="docx")


@contextmanager
def open_docx_zip(data: bytes) -> Iterator[zipfile.ZipFile]:
    """Open a validated .docx as ZIP for read-only scanning."""
    validate_template_upload(data)
    zf = zipfile.ZipFile(io.BytesIO(data), "r")
    try:
        yield zf
    finally:
        zf.close()


def read_docx_xml_member(zf: zipfile.ZipFile, name: str, budget: ZipReadBudget) -> str:
    """Read a word/*.xml member as text under the shared byte budget."""
    raw = read_zip_member(zf, name, budget)
    return raw.decode("utf-8", errors="ignore")


def validation_bypass_enabled() -> bool:
    """Only for local tests: set ESA_SKIP_VALIDATION=1 or ESA_VALIDATION_BYPASS=1.

    Ignored when hosted mode or ESA_API_KEY is configured (production/shared hosts).
    """
    if os.environ.get("ESA_API_KEY", "").strip():
        return False
    for hosted in ("ESA_HOSTED_MODE", "ESA_DISABLE_FOLDER_WORKFLOW"):
        if os.environ.get(hosted, "").strip().lower() in ("1", "true", "yes"):
            return False
    for name in ("ESA_SKIP_VALIDATION", "ESA_VALIDATION_BYPASS"):
        if os.environ.get(name, "").strip().lower() in ("1", "true", "yes"):
            return True
    return False


def sanitize_meta(meta: dict[str, Any] | None) -> dict[str, str]:
    """Trim and cap sidebar / CLI metadata strings."""
    if not meta:
        return {}
    out: dict[str, str] = {}
    for k, v in meta.items():
        key = re.sub(r"\s+", "_", str(k).strip())[:128]
        if not key:
            continue
        s = "" if v is None else str(v).strip()
        cap = MAX_CONTEXT_STRING_LEN if key == "executive_summary" else MAX_META_VALUE_LEN
        if len(s) > cap:
            s = s[:cap]
        out[key] = s
    return out


def clamp_string(value: Any, *, max_len: int = MAX_CONTEXT_STRING_LEN) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and str(value) == "nan":
        return ""
    s = str(value).strip()
    if len(s) > max_len:
        return s[:max_len]
    return s


def strip_internal_context_keys(context: dict[str, Any]) -> dict[str, Any]:
    """Remove underscore-prefixed engine keys from exported / preview context."""
    return {k: v for k, v in context.items() if not str(k).startswith("_")}


def clamp_context(context: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """
    Enforce row/column/string limits on render context. Returns (context, warnings).
    """
    warnings: list[str] = []
    if len(context) > MAX_PROJECT_COLUMNS + 50:
        warnings.append(f"Very large context ({len(context)} keys); some keys may be ignored.")

    for key, val in list(context.items()):
        if isinstance(val, list) and not key.startswith("_"):
            if len(val) > MAX_LAB_ROWS:
                warnings.append(f"{key} truncated from {len(val)} to {MAX_LAB_ROWS} rows.")
                context[key] = val[:MAX_LAB_ROWS]
            for row in val:
                if not isinstance(row, dict):
                    continue
                for rk, rv in list(row.items()):
                    if isinstance(rv, str) and len(rv) > MAX_CONTEXT_STRING_LEN:
                        row[rk] = rv[:MAX_CONTEXT_STRING_LEN]
        elif isinstance(val, str) and len(val) > MAX_CONTEXT_STRING_LEN:
            context[key] = val[:MAX_CONTEXT_STRING_LEN]
            warnings.append(f"Value for '{key}' was truncated to fit size limits.")

    return context, warnings


def sanitize_download_filename(name: str) -> str:
    """Prevent path traversal and unsafe characters in download names."""
    base = (name or "esa_report.docx").strip()
    base = base.replace("\x00", "").replace("/", "_").replace("\\", "_")
    base = re.sub(r"[^\w.\- ]+", "_", base)
    base = base.strip("._ ") or "esa_report.docx"
    if not base.lower().endswith(".docx"):
        base = f"{base}.docx"
    if len(base) > MAX_DOWNLOAD_NAME_LEN:
        stem, ext = base.rsplit(".", 1) if "." in base else (base, "docx")
        base = stem[: MAX_DOWNLOAD_NAME_LEN - len(ext) - 2] + "." + ext
    return base


def _is_safe_value_error_message(msg: str) -> bool:
    if msg in _SAFE_VALUE_ERROR_EXACT:
        return True
    return any(msg.startswith(p) for p in _SAFE_VALUE_ERROR_PREFIXES)


def user_safe_error(exc: BaseException) -> str:
    """Map exceptions to messages safe to show in the UI."""
    if isinstance(exc, SecurityError):
        return str(exc)
    name = type(exc).__name__
    if name == "AuthError":
        msg = str(exc).strip()
        return msg or "Authentication failed."
    if name == "MultipartParseError":
        msg = str(exc).strip()
        return msg or "Invalid multipart request."
    if name == "TenantError":
        msg = str(exc).strip()
        return msg or "Tenant path validation failed."
    if isinstance(exc, PermissionError) and not isinstance(exc, SecurityError):
        # Avoid leaking OS paths from generic PermissionError; AuthError handled above.
        logger.warning("Permission error: %s", exc)
        return "Permission denied."
    if isinstance(exc, ValueError):
        msg = str(exc)
        if _is_safe_value_error_message(msg):
            return msg
        lower = msg.lower()
        if "openpyxl" in lower or "parser failed" in lower or "zip file" in lower:
            return (
                "Could not read the Excel file. It may be corrupt, password-protected, "
                "or not a valid .xlsx workbook."
            )
        logger.warning("Report generation failed: %s", msg)
        return (
            "Report generation failed. Check that your Excel and Word files are valid "
            "and that template tags match your data."
        )
    logger.exception("Unexpected report generation error", exc_info=exc)
    return (
        "Report generation failed. Check that your Excel and Word files are valid "
        "and that template tags match your data. If the problem persists, contact support."
    )
