"""Extract Areas of Potential Environmental Concern (APECs) from historical docs.

V1: text-extractable PDF and DOCX only. Scanned image PDFs / JPG need Phase 2 OCR
(see ai/ocr.py stub).
"""

from __future__ import annotations

import re
from typing import Any

from ai.client import complete_json, prompt_version
from ai.config import openai_model
from ai.docx_extract import extract_docx_full_text
from ai.lab_extract import extract_pdf_text, validate_pdf_upload
from ai.models import AiAudit, ApecExtractResult, ApecExtractRow
from security import SecurityError

CONCERN_TYPES = frozenset(
    {
        "spill",
        "drilling_waste",
        "storage_tank",
        "flare_pit",
        "unknown_disposal",
        "pipeline",
        "other",
    }
)
SOURCE_OF_CONCERN = frozenset(
    {
        "records",
        "air_photo",
        "interview",
        "site_visit",
        "historical_report",
    }
)

_CONCERN_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\bflare\s*pit\b", re.I), "flare_pit", "Flare pit"),
    (re.compile(r"\b(?:spill|release|abadata)\b", re.I), "spill", "Spill / release"),
    (
        re.compile(r"\b(?:drilling\s*waste|sump|cuttings)\b", re.I),
        "drilling_waste",
        "Drilling waste",
    ),
    (
        re.compile(r"\b(?:storage\s*tank|produced\s*water\s*tank|UST|AST)\b", re.I),
        "storage_tank",
        "Storage tank",
    ),
    (re.compile(r"\bpipeline\b", re.I), "pipeline", "Pipeline"),
    (
        re.compile(r"\b(?:unknown\s*disposal|unauthorized\s*disposal)\b", re.I),
        "unknown_disposal",
        "Unknown disposal",
    ),
    (
        re.compile(
            r"\bAPEC\b|areas?\s+of\s+potential\s+environmental\s+concern",
            re.I,
        ),
        "other",
        "APEC (unspecified)",
    ),
]

_PHASE2 = re.compile(
    r"phase\s*II\s+(?:ESA\s+)?(?:is\s+)?recommended|further\s+investigation",
    re.I,
)
_LOCATION = re.compile(
    r"(?:located|location|near|at|SW|SE|NW|NE|north|south|east|west)"
    r"[^\n.]{0,80}",
    re.I,
)


def _norm_concern(raw: str) -> str:
    s = str(raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    return s if s in CONCERN_TYPES else "other"


def _norm_source(raw: str) -> str:
    s = str(raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    return s if s in SOURCE_OF_CONCERN else "historical_report"


def _yn(raw: Any) -> str:
    s = str(raw or "").strip().upper()[:1]
    return "Y" if s == "Y" else "N"


def extract_text_from_upload(
    data: bytes,
    filename: str,
) -> tuple[str, list[str]]:
    """Return (text, warnings). Supports .pdf and .docx only in V1."""
    warnings: list[str] = []
    name = (filename or "").lower()
    if name.endswith(".docx"):
        text = extract_docx_full_text(data)
        if not text.strip():
            warnings.append("DOCX had no extractable text.")
        return text, warnings
    if name.endswith(".pdf") or data[:5].startswith(b"%PDF"):
        validate_pdf_upload(data)
        text = extract_pdf_text(data)
        if not text.strip():
            warnings.append(
                "No text extracted from PDF — may be scanned. "
                "OCR / image support is planned (Phase 2); use a text PDF or DOCX for now."
            )
        return text, warnings
    if name.endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff")):
        raise SecurityError(
            "Image files (JPG/PNG) are not supported in V1 APEC extract. "
            "Use a text PDF or Word (.docx). Scanned/image OCR is planned for Phase 2."
        )
    raise SecurityError("APEC extract accepts .pdf or .docx only (V1).")


def _heuristic_apecs(
    text: str,
    *,
    source_document: str = "",
) -> list[ApecExtractRow]:
    rows: list[ApecExtractRow] = []
    seen: set[str] = set()
    phase2_doc = bool(_PHASE2.search(text))
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 12 or len(line) > 400:
            continue
        for pattern, concern, default_name in _CONCERN_PATTERNS:
            if not pattern.search(line):
                continue
            key = f"{concern}:{line[:80].lower()}"
            if key in seen:
                continue
            seen.add(key)
            loc_m = _LOCATION.search(line)
            location = (loc_m.group(0).strip()[:120] if loc_m else "")
            phase2 = "Y" if phase2_doc or _PHASE2.search(line) else "N"
            n = len(rows) + 1
            rows.append(
                ApecExtractRow(
                    apec_id=f"APEC-{n}",
                    apec_name=default_name,
                    location_description=location,
                    concern_type=concern,
                    source_of_concern="historical_report",
                    evidence_summary=line[:300],
                    source_document=source_document,
                    phase2_recommended=phase2,
                    notes="",
                    confidence=0.62 if location else 0.55,
                )
            )
            break
    return rows[:40]


def _llm_apecs(text: str, *, source_document: str = "") -> list[ApecExtractRow]:
    payload = complete_json(
        system=(
            "Extract Areas of Potential Environmental Concern (APECs) for an Alberta "
            "Phase I ESA from historical document text. Prefer under-extraction — "
            "only include rows with clear evidence. Return JSON: "
            '{"apecs":[{"apec_id":"APEC-1","apec_name":"...","location_description":"...",'
            '"concern_type":"spill|drilling_waste|storage_tank|flare_pit|unknown_disposal|'
            'pipeline|other","source_of_concern":"records|air_photo|interview|site_visit|'
            'historical_report","evidence_summary":"...","phase2_recommended":"Y|N",'
            '"notes":"...","confidence":0.0-1.0}]}'
        ),
        user=f"Source document: {source_document}\n\nText:\n{text[:20_000]}",
    )
    if not payload or "apecs" not in payload:
        return []
    out: list[ApecExtractRow] = []
    for i, item in enumerate(payload.get("apecs") or [], start=1):
        if not isinstance(item, dict):
            continue
        name = str(item.get("apec_name", "")).strip()
        evidence = str(item.get("evidence_summary", "")).strip()
        if not name and not evidence:
            continue
        out.append(
            ApecExtractRow(
                apec_id=str(item.get("apec_id") or f"APEC-{i}").strip()[:32],
                apec_name=(name or "APEC")[:120],
                location_description=str(item.get("location_description", ""))[:200],
                concern_type=_norm_concern(str(item.get("concern_type", "other"))),
                source_of_concern=_norm_source(
                    str(item.get("source_of_concern", "historical_report"))
                ),
                evidence_summary=evidence[:500],
                source_document=source_document,
                phase2_recommended=_yn(item.get("phase2_recommended")),
                notes=str(item.get("notes", ""))[:300],
                confidence=float(item.get("confidence", 0.7)),
            )
        )
    return out[:40]


def _dedupe_rows(rows: list[ApecExtractRow]) -> list[ApecExtractRow]:
    seen: set[str] = set()
    out: list[ApecExtractRow] = []
    for r in rows:
        key = (
            f"{r.concern_type}|{r.apec_name.lower()}|"
            f"{r.location_description.lower()[:40]}|{r.evidence_summary[:60].lower()}"
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    for i, r in enumerate(out, start=1):
        if not re.match(r"^APEC-\d+$", r.apec_id, re.I):
            r.apec_id = f"APEC-{i}"
        else:
            r.apec_id = f"APEC-{i}"
    return out


def extract_apecs_from_text(
    text: str,
    *,
    source_document: str = "",
    use_llm: bool = True,
) -> tuple[ApecExtractResult, AiAudit]:
    audit = AiAudit(features=["apec_extract"], prompt_version=prompt_version())
    warnings: list[str] = []
    rows = _heuristic_apecs(text, source_document=source_document)
    source = "heuristic"
    if use_llm:
        llm_rows = _llm_apecs(text, source_document=source_document)
        if llm_rows:
            rows = _dedupe_rows(llm_rows + rows)
            source = "llm"
            audit.used_llm = True
            audit.model = openai_model()
        else:
            rows = _dedupe_rows(rows)
    else:
        rows = _dedupe_rows(rows)

    if not rows:
        warnings.append(
            "No APEC candidates detected. Review the document manually or enable cloud LLM."
        )
    low = [r for r in rows if r.confidence < 0.6]
    if low:
        warnings.append(f"{len(low)} APEC row(s) have low confidence — review before merge.")

    result = ApecExtractResult(
        rows=rows,
        warnings=warnings,
        source=source,
        raw_text_preview=text[:2000],
    )
    return result, audit


def extract_apecs_from_bytes(
    data: bytes,
    filename: str,
    *,
    use_llm: bool = True,
) -> tuple[ApecExtractResult, AiAudit]:
    text, warn = extract_text_from_upload(data, filename)
    result, audit = extract_apecs_from_text(
        text, source_document=filename, use_llm=use_llm
    )
    result.warnings = list(warn) + list(result.warnings)
    return result, audit


def merge_apec_results(results: list[ApecExtractResult]) -> ApecExtractResult:
    """Combine multi-file extracts; renumber APEC IDs."""
    rows: list[ApecExtractRow] = []
    warnings: list[str] = []
    sources: set[str] = set()
    for r in results:
        rows.extend(r.rows)
        warnings.extend(r.warnings)
        sources.add(r.source)
    rows = _dedupe_rows(rows)
    return ApecExtractResult(
        rows=rows,
        warnings=warnings,
        source="llm" if "llm" in sources else "heuristic",
        raw_text_preview=results[0].raw_text_preview if results else "",
    )
