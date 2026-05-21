"""
Prepare report templates from Word (.docx) or PDF (.pdf) uploads.

PDF files are converted to .docx for docxtpl merging. Add Jinja2 tags in Word after
conversion, or upload an already-tagged .docx template.
"""

from __future__ import annotations

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


def convert_pdf_to_docx(pdf_bytes: bytes) -> bytes:
    """Convert PDF to Word using pdf2docx (layout preserved approximately)."""
    try:
        from pdf2docx import Converter
    except ImportError as e:
        raise SecurityError(
            "PDF template support requires pdf2docx. "
            "Run: pip install pdf2docx"
        ) from e

    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "upload.pdf"
        docx_path = Path(tmp) / "converted.docx"
        pdf_path.write_bytes(pdf_bytes)
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
        return docx_path.read_bytes()


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
