"""
Thin wrapper around ReportEngine for non-Streamlit callers.

Use from Power Automate (Run script), Azure Functions, or cron jobs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from appendix_generator import attach_appendices_to_record
from deliverable_pack import AppendixFile, build_deliverable_zip_bytes
from engine import ReportEngine
from provenance import GenerationRecord, sha256_hex
from template_attachments import prepare_template_upload_cached


def render_report_from_bytes(
    excel_bytes: bytes,
    template_bytes: bytes,
    *,
    meta: dict[str, str] | None = None,
    excel_filename: str = "data.xlsx",
    template_filename: str = "template.docx",
    include_appendices: bool = True,
    uploaded_appendices: list[AppendixFile] | None = None,
) -> tuple[bytes, list[str], dict[str, Any], GenerationRecord, list[AppendixFile]]:
    """Render a report; returns (docx_bytes, warnings, context, manifest record, appendices)."""
    prepared = prepare_template_upload_cached(template_bytes, template_filename)
    engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=prepared.docx_bytes)
    docx_bytes, warnings, context, record = engine.render(
        meta=meta,
        excel_filename=excel_filename,
        template_filename=template_filename,
    )
    all_warnings = list(prepared.warnings) + list(warnings)
    appendices: list[AppendixFile] = []
    if include_appendices:
        _generated, merged, ap_warnings = attach_appendices_to_record(
            record, context, meta, list(uploaded_appendices or [])
        )
        appendices = merged
        all_warnings.extend(ap_warnings)
    return docx_bytes, all_warnings, context, record, appendices


def render_deliverable_zip_from_bytes(
    excel_bytes: bytes,
    template_bytes: bytes,
    *,
    meta: dict[str, str] | None = None,
    excel_filename: str = "data.xlsx",
    template_filename: str = "template.docx",
    report_filename: str = "esa_report.docx",
    include_appendices: bool = True,
    uploaded_appendices: list[AppendixFile] | None = None,
) -> tuple[bytes, list[str], GenerationRecord]:
    """Render report + optional appendices into a deliverable zip."""
    docx_bytes, warnings, context, record, appendices = render_report_from_bytes(
        excel_bytes,
        template_bytes,
        meta=meta,
        excel_filename=excel_filename,
        template_filename=template_filename,
        include_appendices=include_appendices,
        uploaded_appendices=uploaded_appendices,
    )
    record.output_filename = report_filename
    record.output_sha256 = sha256_hex(docx_bytes)
    manifest_bytes = record.to_json_bytes()
    zip_bytes = build_deliverable_zip_bytes(
        docx_bytes,
        report_filename,
        context,
        meta,
        manifest_bytes,
        appendices,
    )
    return zip_bytes, warnings, record


def render_report_from_paths(
    excel_path: str | Path,
    template_path: str | Path,
    output_path: str | Path,
    *,
    meta: dict[str, str] | None = None,
    write_manifest: bool = True,
    include_appendices: bool = True,
    write_package: bool = False,
) -> tuple[list[str], GenerationRecord]:
    """Read paths, render, write .docx (and optional manifest / deliverable zip)."""
    excel_path = Path(excel_path)
    template_path = Path(template_path)
    output_path = Path(output_path)
    excel_bytes = excel_path.read_bytes()
    template_bytes = template_path.read_bytes()

    docx_bytes, warnings, context, record, appendices = render_report_from_bytes(
        excel_bytes,
        template_bytes,
        meta=meta,
        excel_filename=excel_path.name,
        template_filename=template_path.name,
        include_appendices=include_appendices,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(docx_bytes)
    record.output_filename = output_path.name
    record.output_sha256 = sha256_hex(docx_bytes)
    manifest_bytes = record.to_json_bytes()

    if write_manifest:
        manifest_path = output_path.with_name(output_path.stem + "_manifest.json")
        manifest_path.write_bytes(manifest_bytes)

    if write_package:
        zip_path = output_path.with_name(output_path.stem + "_package.zip")
        zip_path.write_bytes(
            build_deliverable_zip_bytes(
                docx_bytes,
                output_path.name,
                context,
                meta,
                manifest_bytes,
                appendices,
            )
        )

    return warnings, record
