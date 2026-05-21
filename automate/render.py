"""
Thin wrapper around ReportEngine for non-Streamlit callers.

Use from Power Automate (Run script), Azure Functions, or cron jobs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from engine import ReportEngine
from provenance import GenerationRecord, sha256_hex
from template_attachments import prepare_template_upload


def render_report_from_bytes(
    excel_bytes: bytes,
    template_bytes: bytes,
    *,
    meta: dict[str, str] | None = None,
    excel_filename: str = "data.xlsx",
    template_filename: str = "template.docx",
) -> tuple[bytes, list[str], dict[str, Any], GenerationRecord]:
    """Render a report; returns (docx_bytes, warnings, context, manifest record)."""
    prepared = prepare_template_upload(template_bytes, template_filename)
    engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=prepared.docx_bytes)
    docx_bytes, warnings, context, record = engine.render(
        meta=meta,
        excel_filename=excel_filename,
        template_filename=template_filename,
    )
    return docx_bytes, prepared.warnings + warnings, context, record


def render_report_from_paths(
    excel_path: str | Path,
    template_path: str | Path,
    output_path: str | Path,
    *,
    meta: dict[str, str] | None = None,
    write_manifest: bool = True,
) -> tuple[list[str], GenerationRecord]:
    """Read paths, render, write .docx (and optional *_manifest.json)."""
    excel_path = Path(excel_path)
    template_path = Path(template_path)
    output_path = Path(output_path)

    docx_bytes, warnings, _ctx, record = render_report_from_bytes(
        excel_path.read_bytes(),
        template_path.read_bytes(),
        meta=meta,
        excel_filename=excel_path.name,
        template_filename=template_path.name,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(docx_bytes)
    record.output_filename = output_path.name
    record.output_sha256 = sha256_hex(docx_bytes)

    if write_manifest:
        manifest_path = output_path.with_name(output_path.stem + "_manifest.json")
        manifest_path.write_bytes(record.to_json_bytes())

    return warnings, record
