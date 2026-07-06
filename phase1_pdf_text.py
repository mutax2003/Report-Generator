"""Extract text and cover metadata from Phase 1 ESA PDFs (owner-password empty)."""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from pathlib import Path

_PYPDF_LOGGER = logging.getLogger("pypdf")


@dataclass
class Phase1PdfMeta:
    """Cover-level fields parsed from a Phase 1 ESA PDF."""

    project_number: str
    client_name: str
    well_name: str
    site_name: str
    uwi: str
    report_title: str
    report_month_year: str
    lsd_from_filename: str


def extract_pdf_text_local(pdf_bytes: bytes, max_pages: int = 12) -> str:
    """Read PDF text; decrypt with empty password when encrypted."""
    if not pdf_bytes or not pdf_bytes.lstrip().startswith(b"%PDF"):
        return ""
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError, PdfStreamError
    except ImportError as e:
        raise RuntimeError("pypdf required. Run: pip install pypdf cryptography") from e

    try:
        prev_level = _PYPDF_LOGGER.level
        _PYPDF_LOGGER.setLevel(logging.ERROR)
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes), strict=False)
        finally:
            _PYPDF_LOGGER.setLevel(prev_level)
    except (PdfReadError, PdfStreamError, ValueError):
        return ""
    if reader.is_encrypted:
        try:
            status = reader.decrypt("")
        except (PdfReadError, PdfStreamError, ValueError):
            return ""
        if status == 0:
            return ""
    pages: list[str] = []
    try:
        for page in reader.pages[:max_pages]:
            t = page.extract_text() or ""
            if t.strip():
                pages.append(t)
    except (PdfReadError, PdfStreamError, ValueError, IndexError):
        return "\n".join(pages)
    return "\n".join(pages)


def _first_match(patterns: list[str], text: str) -> str:
    for pat in patterns:
        m = re.search(pat, text, re.I | re.M)
        if m:
            return m.group(1).strip()
    return ""


def parse_phase1_pdf_meta(pdf_path: Path, pdf_text: str | None = None) -> Phase1PdfMeta:
    """Parse client, site, and report id from filename and cover pages."""
    stem = pdf_path.stem
    project_number = ""
    m_proj = re.match(r"^(\d{6}R)", stem)
    if m_proj:
        project_number = m_proj.group(1)

    lsd_from_filename = ""
    m_lsd = re.search(
        r"(\d{1,2}-\d{1,2}-\d{2,3}-\d{2}\s*W\dM)",
        stem,
        re.I,
    )
    if m_lsd:
        lsd_from_filename = re.sub(r"\s+", " ", m_lsd.group(1))

    text = pdf_text if pdf_text is not None else extract_pdf_text_local(pdf_path.read_bytes())

    client_name = _first_match(
        [
            r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\s*\n+\s*([^\n]+(?:Inc\.|Ltd\.|Corp\.|LP|LLC))",
            r"^([A-Z][^\n]{5,80}(?:Inc\.|Ltd\.|Corp\.|LP))\s*$",
        ],
        text,
    )
    if not client_name:
        client_name = _first_match([r"contracted by ([^\n(]+?)\s*\("], text)

    report_title = _first_match(
        [r"(\d{4}\s+Phase\s+1\s+Environmental\s+Site\s+Assessment[^\n]{0,80})"],
        text,
    )
    if not report_title:
        report_title = "Phase I Environmental Site Assessment"

    report_month_year = _first_match(
        [
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})",
        ],
        text,
    )

    uwi = _first_match(
        [
            r"(\d{2}/\d{2}-\d{2}-\d{3}-\d{2}W\dM/\d)",
            r"(\d{2,3}/\d{2}-\d{2}-\d{3}-\d{2}\s*W\dM)",
            r"within\s+(\d{1,2}-\d{1,2}-\d{2,3}-\d{2}\s*W\dM)",
            r"(\d{1,2}-\d{1,2}-\d{2,3}-\d{2}\s*W\dM)",
        ],
        text,
    )
    if not uwi and lsd_from_filename:
        uwi = lsd_from_filename

    site_name = _first_match(
        [
            r"Phase\s+1\s+Environmental\s+Site\s+Assessment\s+([^\n]{8,120})",
            r"Re:\s*[^\n]+?(\d{1,2}[-/]\d{1,2}[-/]\d{2,3}[-/]\d{2}\s*W\dM[^\n]{0,80})",
        ],
        text,
    )
    if not site_name and lsd_from_filename:
        site_name = lsd_from_filename

    well_name = site_name
    m_well = re.search(r"known as ([^\n(]+)", text, re.I)
    if m_well:
        well_name = m_well.group(1).strip()
    elif lsd_from_filename:
        well_name = lsd_from_filename

    return Phase1PdfMeta(
        project_number=project_number,
        client_name=client_name.strip(),
        well_name=well_name.strip(),
        site_name=site_name.strip(),
        uwi=uwi.strip(),
        report_title=report_title.strip(),
        report_month_year=report_month_year.strip(),
        lsd_from_filename=lsd_from_filename.strip(),
    )


def build_mvp_tag_replacements(meta: Phase1PdfMeta) -> dict[str, str]:
    """
    Map literal cover/narrative strings to Jinja tags (longest keys first).
    Only include non-empty source strings.
    """
    ecoventure = "Ecoventure Inc."
    pairs: list[tuple[str, str]] = [
        (meta.client_name, "{{ client_name }}"),
        (meta.site_name, "{{ site_name }}"),
        (meta.well_name, "{{ well_name }}"),
        (meta.uwi, "{{ uwi }}"),
        (meta.report_title, "{{ report_title }}"),
        (meta.report_month_year, "{{ report_month_year }}"),
        (ecoventure, "{{ company }}"),
        ("Ecoventure Inc. (Ecoventure)", "{{ consultant_name }} (Ecoventure)"),
    ]
    if meta.uwi and "/" in meta.uwi:
        pairs.append((meta.uwi.split()[0], "{{ uwi }}"))
    out: dict[str, str] = {}
    for old, new in sorted(pairs, key=lambda x: -len(x[0])):
        if old and old not in out and old != new:
            out[old] = new
    return out
