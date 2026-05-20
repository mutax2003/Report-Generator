"""Extract LabResults rows from lab PDF / COA text."""

from __future__ import annotations

import io
import re
from typing import Any

from ai.client import complete_json, prompt_version
from ai.config import MAX_PDF_BYTES
from ai.models import AiAudit, LabExtractResult, LabExtractRow
from security import SecurityError

_NUM = re.compile(r"^[\d.]+$")
_ROW_HEURISTIC = re.compile(
    r"^([A-Za-z][\w\s\-\(\)/\.]{1,60}?)\s+([\d.]+(?:\s*[<>]?\s*[\d.]*)?)\s+(\S+)\s+([\d.]+)?",
)


def validate_pdf_upload(data: bytes) -> None:
    if not data:
        raise SecurityError("PDF file is empty.")
    if len(data) > MAX_PDF_BYTES:
        raise SecurityError(f"PDF file too large (max {MAX_PDF_BYTES // (1024 * 1024)} MB).")
    if not data[:5].startswith(b"%PDF"):
        raise SecurityError("File does not look like a PDF.")


def extract_pdf_text(pdf_bytes: bytes) -> str:
    validate_pdf_upload(pdf_bytes)
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise SecurityError(
            "PDF support requires pypdf. Run: pip install pypdf"
        ) from e

    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages: list[str] = []
    for page in reader.pages[:50]:
        t = page.extract_text() or ""
        if t.strip():
            pages.append(t)
    return "\n".join(pages)


def _heuristic_rows(text: str) -> list[LabExtractRow]:
    rows: list[LabExtractRow] = []
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 8 or len(line) > 200:
            continue
        m = _ROW_HEURISTIC.match(line)
        if not m:
            continue
        analyte, result, unit, criteria = m.group(1), m.group(2), m.group(3), m.group(4) or ""
        exc = "Y" if _exceeds(result, criteria) else "N"
        rows.append(
            LabExtractRow(
                analyte=analyte.strip(),
                result=result.strip(),
                unit=unit.strip(),
                criteria=criteria.strip(),
                exceedance=exc,
                confidence=0.65,
            )
        )
    return rows[:500]


def _exceeds(result: str, criteria: str) -> bool:
    try:
        r = float(re.sub(r"[^\d.]", "", result))
        c = float(criteria)
        return r > c
    except (TypeError, ValueError):
        return False


def _llm_rows(text: str) -> list[LabExtractRow]:
    data = complete_json(
        system=(
            'Return JSON: {"rows": [{"analyte":"","result":"","unit":"","criteria":"",'
            '"exceedance":"Y|N","confidence":0.0-1.0}]}. '
            "Parse environmental lab certificate tables. Max 200 rows."
        ),
        user=text[:30_000],
    )
    if not data:
        return []
    out: list[LabExtractRow] = []
    for item in data.get("rows", [])[:200]:
        if not isinstance(item, dict):
            continue
        out.append(
            LabExtractRow(
                analyte=str(item.get("analyte", ""))[:120],
                result=str(item.get("result", ""))[:64],
                unit=str(item.get("unit", ""))[:32],
                criteria=str(item.get("criteria", ""))[:64],
                exceedance=(
                    "Y"
                    if str(item.get("exceedance", "N")).strip().upper()[:1] == "Y"
                    else "N"
                ),
                confidence=float(item.get("confidence", 0.75)),
            )
        )
    return out


def extract_lab_from_pdf(
    pdf_bytes: bytes,
    *,
    use_llm: bool = True,
) -> LabExtractResult:
    text = extract_pdf_text(pdf_bytes)
    preview = text[:2000]
    warnings: list[str] = []

    rows = _heuristic_rows(text)
    source = "heuristic"
    audit_used_llm = False

    if use_llm and (len(rows) < 3 or max((r.confidence for r in rows), default=0) < 0.7):
        llm_rows = _llm_rows(text)
        if llm_rows:
            rows = llm_rows
            source = "llm"
            audit_used_llm = True

    if not rows:
        warnings.append(
            "No lab rows detected. Try a clearer PDF or enable OPENAI_API_KEY for LLM parsing."
        )

    low = [r for r in rows if r.confidence < 0.6]
    if low:
        warnings.append(f"{len(low)} row(s) have low confidence — review before merge.")

    return LabExtractResult(
        rows=rows,
        warnings=warnings,
        source=source,
        raw_text_preview=preview,
    )
