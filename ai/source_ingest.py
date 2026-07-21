"""Ingest source/ PDFs: extract text, route lab/ESA, optional LLM summaries → ai_drafts/."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ai.client import complete_text, prompt_version
from ai.config import MAX_PDF_BYTES, openai_model
from ai.lab_extract import extract_lab_from_pdf
from ai.models import AiAudit
from phase1_pdf_text import extract_pdf_text_local, parse_phase1_pdf_meta
from project_folder import _read_pdf_bytes

LAB_FILENAME = re.compile(r"coa|certificate|cert\.?of|anal(?:ytical)?|lab.?report", re.I)
ESA_FILENAME = re.compile(r"phase\s*1|phase\s*i|\besa\b|environmental", re.I)
APEC_FILENAME = re.compile(
    r"abadata|spill|release|air.?photo|historical|records.?review|apec",
    re.I,
)

MAX_EXTRACT_CHARS = 24_000
CHUNK_SIZE = 4000
MAX_SUMMARY_PROMPT_CHARS = 8000
MAX_NARRATIVE_SUMMARIES_CHARS = 10_000

_META_TO_EXCEL: dict[str, str] = {
    "project_number": "project_number",
    "client_name": "client_name",
    "well_name": "well_name",
    "site_name": "site_name",
    "uwi": "uwi",
    "report_title": "report_title",
    "report_month_year": "report_month_year",
}


@dataclass
class SourcePdfRecord:
    filename: str
    route: str
    size_bytes: int
    char_count: int
    warnings: list[str] = field(default_factory=list)
    esa_meta: dict[str, str] | None = None
    lab_row_count: int | None = None
    summary: str = ""
    extract_file: str = ""


def classify_pdf_route(filename: str) -> str:
    name = filename.lower()
    if LAB_FILENAME.search(name):
        return "lab"
    if ESA_FILENAME.search(name):
        return "esa"
    if APEC_FILENAME.search(name):
        return "apec"
    return "generic"


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - 200
    return chunks


def _offline_summary(filename: str, text: str, route: str) -> str:
    preview = text[:1200].strip()
    if not preview:
        return f"{filename}: no extractable text (scanned PDF may need OCR)."
    return (
        f"Source: {filename} ({route}). "
        f"Extract preview ({len(text)} chars total):\n{preview}"
    )


def summarize_pdf_text(
    filename: str,
    text: str,
    route: str,
    *,
    use_llm: bool,
) -> tuple[str, bool]:
    if not text.strip():
        return _offline_summary(filename, text, route), False
    if not use_llm:
        return _offline_summary(filename, text, route), False
    prompt_text = text[:MAX_SUMMARY_PROMPT_CHARS]
    raw = complete_text(
        system=(
            "Summarize Alberta oil & gas environmental site assessment source documents. "
            "List only facts present in the text: site identifiers (UWI/LSD), client, dates, "
            "findings, recommendations, waste/spill mentions. No invented data. "
            "3-8 bullet points max."
        ),
        user=json.dumps(
            {"filename": filename, "document_type": route, "text": prompt_text},
            default=str,
        ),
    )
    if raw:
        return raw.strip(), True
    return _offline_summary(filename, text, route), False


def _esa_meta_dict(meta: Any) -> dict[str, str]:
    raw = asdict(meta)
    return {k: str(v).strip() for k, v in raw.items() if v and str(v).strip()}


def _merge_excel_suggestions(entries: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in entries:
        meta = entry.get("esa_meta") or {}
        for src_key, excel_col in _META_TO_EXCEL.items():
            val = str(meta.get(src_key, "")).strip()
            if val and excel_col not in out:
                out[excel_col] = val
    return out


def _valid_pdf_bytes(data: bytes) -> bool:
    return bool(data) and data[:5].startswith(b"%PDF")


def ingest_source_pdfs(
    source_pdfs: list[Path],
    drafts_dir: Path,
    *,
    use_llm: bool = True,
    write_rag_snippets: bool = True,
    rag_dir: Path | None = None,
) -> tuple[list[Path], list[dict[str, str]], AiAudit]:
    """
    Process PDFs from source/; write ai_drafts artifacts.

    Returns (written paths, summary dicts for narrative context, audit).
    """
    audit = AiAudit(features=["source_ingest"], prompt_version=prompt_version())
    pdfs = sorted(p for p in source_pdfs if p.is_file() and p.suffix.lower() == ".pdf")
    if not pdfs:
        return [], [], audit

    drafts_dir.mkdir(parents=True, exist_ok=True)
    extracts_dir = drafts_dir / "source_extracts"
    extracts_dir.mkdir(exist_ok=True)
    rag_ingested = (rag_dir / "ingested") if rag_dir else None
    if write_rag_snippets and rag_ingested is not None:
        rag_ingested.mkdir(parents=True, exist_ok=True)

    records: list[SourcePdfRecord] = []
    summaries_for_narrative: list[dict[str, str]] = []
    written: list[Path] = []
    index_entries: list[dict[str, Any]] = []
    all_apec_rows: list[dict[str, str]] = []

    for pdf in pdfs:
        route = classify_pdf_route(pdf.name)
        warnings: list[str] = []
        record = SourcePdfRecord(
            filename=pdf.name,
            route=route,
            size_bytes=pdf.stat().st_size,
            char_count=0,
        )

        if record.size_bytes > MAX_PDF_BYTES:
            warnings.append(
                f"Skipped: exceeds {MAX_PDF_BYTES // (1024 * 1024)} MB limit"
            )
            record.warnings = warnings
            index_entries.append(
                {
                    "filename": record.filename,
                    "route": record.route,
                    "size_bytes": record.size_bytes,
                    "char_count": 0,
                    "warnings": warnings,
                    "esa_meta": None,
                    "lab_row_count": None,
                    "extract_file": "",
                }
            )
            continue

        pdf_bytes = _read_pdf_bytes(pdf)
        if not _valid_pdf_bytes(pdf_bytes):
            warnings.append("Not a valid PDF header")
            record.warnings = warnings
            index_entries.append(
                {
                    "filename": record.filename,
                    "route": record.route,
                    "size_bytes": record.size_bytes,
                    "char_count": 0,
                    "warnings": warnings,
                    "esa_meta": None,
                    "lab_row_count": None,
                    "extract_file": "",
                }
            )
            continue

        text = ""
        try:
            text = extract_pdf_text_local(pdf_bytes, max_pages=50)
        except Exception as e:
            warnings.append(f"Text extract failed: {e}")

        if len(text.strip()) < 40:
            warnings.append("Little or no text — scanned PDF may need OCR")

        text = text[:MAX_EXTRACT_CHARS]
        record.char_count = len(text)
        record.warnings = warnings

        extract_path = extracts_dir / f"{pdf.stem}.txt"
        extract_path.write_text(text or "(no extractable text)\n", encoding="utf-8")
        record.extract_file = extract_path.name

        if route == "lab":
            try:
                lab_result = extract_lab_from_pdf(pdf_bytes, use_llm=use_llm)
                record.lab_row_count = len(lab_result.rows)
                lab_path = drafts_dir / f"lab_extract_{pdf.stem}.json"
                lab_path.write_text(
                    json.dumps(
                        {
                            "source_pdf": pdf.name,
                            "row_count": len(lab_result.rows),
                            "source": lab_result.source,
                            "warnings": lab_result.warnings,
                            "rows": [r.to_excel_dict() for r in lab_result.rows],
                        },
                        indent=2,
                        default=str,
                    ),
                    encoding="utf-8",
                )
                written.append(lab_path)
                if lab_result.source == "llm":
                    audit.used_llm = True
                    audit.model = openai_model()
            except Exception as e:
                warnings.append(f"Lab extract failed: {e}")

        if route == "esa" and text.strip():
            try:
                meta = parse_phase1_pdf_meta(pdf, text)
                record.esa_meta = _esa_meta_dict(meta)
            except Exception as e:
                warnings.append(f"ESA metadata parse failed: {e}")

        apec_row_count = None
        if route in ("esa", "apec", "generic") and text.strip():
            try:
                from ai.apec_extract import extract_apecs_from_text

                apec_result, apec_audit = extract_apecs_from_text(
                    text, source_document=pdf.name, use_llm=use_llm
                )
                apec_row_count = len(apec_result.rows)
                if apec_result.rows:
                    apec_path = drafts_dir / f"apec_extract_{pdf.stem}.json"
                    apec_path.write_text(
                        json.dumps(
                            {
                                "disclaimer": apec_result.disclaimer,
                                "source_pdf": pdf.name,
                                "row_count": len(apec_result.rows),
                                "source": apec_result.source,
                                "warnings": apec_result.warnings,
                                "rows": [r.to_excel_dict() for r in apec_result.rows],
                            },
                            indent=2,
                            default=str,
                        ),
                        encoding="utf-8",
                    )
                    written.append(apec_path)
                    all_apec_rows.extend(r.to_excel_dict() for r in apec_result.rows)
                if apec_audit.used_llm:
                    audit.used_llm = True
                    audit.model = openai_model() or apec_audit.model
            except Exception as e:
                warnings.append(f"APEC extract failed: {e}")

        summary, used_llm = summarize_pdf_text(
            pdf.name, text, route, use_llm=use_llm
        )
        record.summary = summary
        if used_llm:
            audit.used_llm = True
            audit.model = openai_model()

        summaries_for_narrative.append(
            {"filename": pdf.name, "route": route, "summary": summary}
        )

        if write_rag_snippets and rag_ingested is not None and summary:
            snippet_path = rag_ingested / f"{pdf.stem}.txt"
            snippet_path.write_text(
                f"Source PDF: {pdf.name}\n---\n{summary}\n", encoding="utf-8"
            )

        records.append(record)
        index_entries.append(
            {
                "filename": record.filename,
                "route": record.route,
                "size_bytes": record.size_bytes,
                "char_count": record.char_count,
                "warnings": record.warnings,
                "esa_meta": record.esa_meta,
                "lab_row_count": record.lab_row_count,
                "apec_row_count": apec_row_count,
                "extract_file": record.extract_file,
            }
        )

    index_path = drafts_dir / "source_index.json"
    index_path.write_text(
        json.dumps(
            {
                "disclaimer": "Source PDF index — review extracts before using in reports.",
                "pdf_count": len(index_entries),
                "items": index_entries,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    written.append(index_path)

    summaries_path = drafts_dir / "source_summaries.json"
    summaries_path.write_text(
        json.dumps(
            {
                "disclaimer": "AI summaries of source/ PDFs — QP review required.",
                "items": summaries_for_narrative,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    written.append(summaries_path)

    suggestions = _merge_excel_suggestions(index_entries)
    if suggestions:
        sugg_path = drafts_dir / "excel_field_suggestions.json"
        sugg_path.write_text(
            json.dumps(
                {
                    "disclaimer": (
                        "Suggested ProjectData fields from source PDFs — "
                        "review then Apply from the AI tools tab (not auto-applied)."
                    ),
                    "fields": suggestions,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        written.append(sugg_path)

    if all_apec_rows:
        from ai.apec_extract import merge_apec_results
        from ai.models import ApecExtractResult, ApecExtractRow

        # Renumber via merge helper
        fake = ApecExtractResult(
            rows=[
                ApecExtractRow(
                    apec_id=str(r.get("apec_id", "")),
                    apec_name=str(r.get("apec_name", "")),
                    location_description=str(r.get("location_description", "")),
                    concern_type=str(r.get("concern_type", "other")),
                    source_of_concern=str(r.get("source_of_concern", "historical_report")),
                    evidence_summary=str(r.get("evidence_summary", "")),
                    source_document=str(r.get("source_document", "")),
                    phase2_recommended=str(r.get("phase2_recommended", "N")),
                    notes=str(r.get("notes", "")),
                )
                for r in all_apec_rows
            ]
        )
        merged = merge_apec_results([fake])
        cand_path = drafts_dir / "apecs_candidates.json"
        cand_path.write_text(
            json.dumps(
                {
                    "disclaimer": (
                        "AI-suggested APECs from source/ PDFs — QP review required. "
                        "Apply from the AI tools tab (not auto-written to Excel)."
                    ),
                    "row_count": len(merged.rows),
                    "rows": [r.to_excel_dict() for r in merged.rows],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        written.append(cand_path)
        audit.features = list(audit.features) + ["apec_extract"]

    return written, summaries_for_narrative, audit


def load_summaries_for_narrative(drafts_dir: Path) -> list[dict[str, str]]:
    """Load source_summaries.json for narrative context (truncated)."""
    path = drafts_dir / "source_summaries.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    items = data.get("items") or []
    if not isinstance(items, list):
        return []
    out: list[dict[str, str]] = []
    total = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        summary = str(item.get("summary", "")).strip()
        if not summary:
            continue
        if total + len(summary) > MAX_NARRATIVE_SUMMARIES_CHARS:
            break
        out.append(
            {
                "filename": str(item.get("filename", "")),
                "route": str(item.get("route", "")),
                "summary": summary,
            }
        )
        total += len(summary)
    return out


def format_summaries_for_prompt(summaries: list[dict[str, str]]) -> str:
    if not summaries:
        return ""
    parts: list[str] = []
    total = 0
    for item in summaries:
        block = f"[{item.get('filename', 'source')}] {item.get('summary', '')}"
        if total + len(block) > MAX_NARRATIVE_SUMMARIES_CHARS:
            break
        parts.append(block)
        total += len(block)
    return "\n\n".join(parts)
