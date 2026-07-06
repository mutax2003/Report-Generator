"""
Prepare report templates from Word (.docx) or PDF (.pdf) uploads.

PDF files are converted to .docx for docxtpl merging. Add Jinja2 tags in Word after
conversion, or upload an already-tagged .docx template.
"""

from __future__ import annotations

import hashlib
import io
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from security import (
    SecurityError,
    validate_pdf_template_upload,
    validate_template_upload,
)

logger = logging.getLogger(__name__)

_PDF_MAGIC = b"%PDF"


@dataclass
class PreparedTemplate:
    """Normalized template ready for ReportEngine (always .docx bytes)."""

    docx_bytes: bytes
    source_filename: str
    source_format: str  # docx | pdf
    warnings: list[str] = field(default_factory=list)


def template_extension_ok(filename: str) -> bool:
    ext = Path(filename or "").suffix.lower()
    return ext in (".docx", ".pdf")


def detect_template_format(data: bytes, filename: str = "") -> str:
    """Return ``docx`` or ``pdf`` from magic bytes and filename."""
    name = (filename or "").lower()
    if name.endswith(".pdf") or data[:4] == _PDF_MAGIC:
        return "pdf"
    return "docx"


def truncate_pdf_bytes(pdf_bytes: bytes, max_pages: int | None) -> bytes:
    """Return first ``max_pages`` of a PDF (decrypt with empty password if needed)."""
    if not max_pages or max_pages < 1:
        return pdf_bytes
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError as e:
        raise SecurityError("PDF page trim requires pypdf.") from e

    reader = PdfReader(io.BytesIO(pdf_bytes))
    if reader.is_encrypted:
        if reader.decrypt("") == 0:
            raise SecurityError(
                "PDF is encrypted; re-export without password or supply --pdf-password."
            )
    n = min(max_pages, len(reader.pages))
    if n >= len(reader.pages):
        return pdf_bytes
    writer = PdfWriter()
    for i in range(n):
        writer.add_page(reader.pages[i])
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def convert_pdf_to_docx(pdf_bytes: bytes, *, max_pages: int | None = None) -> bytes:
    """Convert PDF to Word using pdf2docx (layout preserved approximately)."""
    try:
        from pdf2docx import Converter
    except ImportError as e:
        raise SecurityError(
            "PDF template support requires pdf2docx. "
            "Run: pip install pdf2docx"
        ) from e

    work_bytes = truncate_pdf_bytes(pdf_bytes, max_pages)

    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "upload.pdf"
        docx_path = Path(tmp) / "converted.docx"
        pdf_path.write_bytes(work_bytes)
        converter = Converter(str(pdf_path))
        try:
            converter.convert(str(docx_path))
        finally:
            converter.close()
        if not docx_path.is_file() or docx_path.stat().st_size < 100:
            raise SecurityError(
                "PDF could not be converted to Word. "
                "Try a simpler PDF or provide a .docx template with Jinja tags."
            )
        try:
            return docx_path.read_bytes()
        except OSError as e:
            raise SecurityError(
                "PDF conversion produced an invalid Word file. "
                "Try a simpler PDF or upload a .docx template."
            ) from e


def prepare_template_upload(data: bytes, filename: str = "") -> PreparedTemplate:
    """
    Validate and normalize a template upload to .docx bytes for the merge engine.
    """
    if not data:
        raise SecurityError("Template file is empty.")
    if not template_extension_ok(filename) and detect_template_format(data) == "docx":
        ext = Path(filename).suffix or "(unknown)"
        raise SecurityError(
            f"Unsupported template type '{ext}'. Upload a .docx or .pdf file."
        )

    fmt = detect_template_format(data, filename)
    name = filename or ("template.pdf" if fmt == "pdf" else "template.docx")

    if fmt == "pdf":
        validate_pdf_template_upload(data, filename)
        warnings = [
            "PDF template was converted to Word (.docx) for merging. "
            "Add `{{ field }}` tags and `{%tr for item in list %}` table loops in Word "
            "if the converted file has no Jinja markup yet (use pre-flight or AI template tagger)."
        ]
        try:
            docx_bytes = convert_pdf_to_docx(data)
        except SecurityError:
            raise
        except Exception as e:
            logger.exception("PDF to DOCX conversion failed")
            raise SecurityError(
                "PDF to Word conversion failed. Upload a .docx template with Jinja2 tags, "
                "or use a text-based PDF (not scanned images only)."
            ) from e
        validate_template_upload(docx_bytes, "converted.docx")
        return PreparedTemplate(
            docx_bytes=docx_bytes,
            source_filename=name,
            source_format="pdf",
            warnings=warnings,
        )

    validate_template_upload(data, name)
    return PreparedTemplate(
        docx_bytes=data,
        source_filename=name,
        source_format="docx",
        warnings=[],
    )


_PREPARED_CACHE_MAX = 16
_prepared_template_cache: dict[tuple[str, str], PreparedTemplate] = {}


def clear_prepared_template_cache() -> None:
    """Drop cached PDF→DOCX / docx normalizations (tests)."""
    _prepared_template_cache.clear()


def prepare_template_upload_cached(data: bytes, filename: str = "") -> PreparedTemplate:
    """Like prepare_template_upload but reuse results for identical bytes + filename."""
    digest = hashlib.sha256(data).hexdigest()
    key = (digest, (filename or "").lower())
    hit = _prepared_template_cache.get(key)
    if hit is not None:
        return hit
    result = prepare_template_upload(data, filename)
    if len(_prepared_template_cache) >= _PREPARED_CACHE_MAX:
        _prepared_template_cache.pop(next(iter(_prepared_template_cache)))
    _prepared_template_cache[key] = result
    return result
