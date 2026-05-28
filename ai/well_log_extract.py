"""Extract monitoring well rows from borehole / well construction PDF text."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ai.lab_extract import extract_pdf_text, validate_pdf_upload
from ai.models import AiAudit


@dataclass
class WellExtractRow:
    well_id: str
    screen_top_m: str = ""
    screen_bottom_m: str = ""
    construction_notes: str = ""
    confidence: float = 0.6

    def to_excel_dict(self) -> dict[str, str]:
        return {
            "Well ID": self.well_id,
            "Screen top (m)": self.screen_top_m,
            "Screen bottom (m)": self.screen_bottom_m,
            "Construction notes": self.construction_notes,
        }


_WELL_ID = re.compile(
    r"\b(MW[-\s]?\d+|BH[-\s]?\d+|MW\d+|Well\s*#?\s*\d+)\b",
    re.IGNORECASE,
)
_DEPTH_PAIR = re.compile(
    r"(?:screen|interval)[^\d]{0,20}(\d+(?:\.\d+)?)\s*(?:to|-|–)\s*(\d+(?:\.\d+)?)\s*m?",
    re.IGNORECASE,
)


def normalize_well_id(raw: str) -> str:
    """Canonical well ID for Excel merge (e.g. mw-1 -> MW-1)."""
    s = str(raw).strip().upper()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"-+", "-", s)
    m = re.match(r"^(MW|BH)-?(\d+)$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.match(r"^(MW|BH)(\d+)$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return s


def _heuristic_wells(text: str) -> list[WellExtractRow]:
    rows: list[WellExtractRow] = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 4:
            continue
        for m in _WELL_ID.finditer(line):
            wid = normalize_well_id(m.group(1))
            if wid in seen:
                continue
            seen.add(wid)
            top, bottom = "", ""
            dm = _DEPTH_PAIR.search(line)
            if dm:
                top, bottom = dm.group(1), dm.group(2)
            rows.append(
                WellExtractRow(
                    well_id=wid,
                    screen_top_m=top,
                    screen_bottom_m=bottom,
                    construction_notes=line[:200],
                    confidence=0.65 if top else 0.55,
                )
            )
    return rows[:50]


def extract_wells_from_pdf(
    pdf_bytes: bytes,
    *,
    use_llm: bool = False,
) -> tuple[list[WellExtractRow], list[str], AiAudit]:
    """Parse well IDs and optional screen intervals from PDF text."""
    validate_pdf_upload(pdf_bytes)
    text = extract_pdf_text(pdf_bytes)
    warnings: list[str] = []
    rows = _heuristic_wells(text)
    if not rows:
        warnings.append(
            "No monitoring well IDs detected (expected patterns like MW-1, BH-2)."
        )
    if use_llm and len(rows) < 2:
        warnings.append(
            "LLM well-log parsing not enabled in offline mode; review PDF manually."
        )
    audit = AiAudit(features=["well_log_extract"], used_llm=False)
    return rows, warnings, audit
