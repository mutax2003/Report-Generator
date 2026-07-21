"""
Thin wrapper around render_service for non-Streamlit callers.

Use from Power Automate (Run script), Azure Functions, or cron jobs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from deliverable_pack import AppendixFile, build_deliverable_zip_bytes
from provenance import GenerationRecord, sha256_hex
from render_service import RenderRequest, render_deliverable_package, render_report


def render_report_from_bytes(
    excel_bytes: bytes,
    template_bytes: bytes,
    *,
    meta: dict[str, str] | None = None,
    excel_filename: str = "data.xlsx",
    template_filename: str = "template.docx",
    include_appendices: bool = True,
    uploaded_appendices: list[AppendixFile] | None = None,
    appendix_labels_present: set[str] | None = None,
) -> tuple[bytes, list[str], dict[str, Any], GenerationRecord, list[AppendixFile]]:
    """Render a report; returns (docx_bytes, warnings, context, manifest record, appendices)."""
    result = render_report(
        RenderRequest(
            excel_bytes=excel_bytes,
            template_bytes=template_bytes,
            meta=meta,
            excel_filename=excel_filename,
            template_filename=template_filename,
            include_appendices=include_appendices,
            uploaded_appendices=list(uploaded_appendices or []),
            appendix_labels_present=appendix_labels_present,
        )
    )
    return (
        result.docx_bytes,
        result.warnings,
        result.context,
        result.record,
        result.appendices,
    )


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
    appendix_labels_present: set[str] | None = None,
) -> tuple[bytes, list[str], GenerationRecord]:
    """Render report + optional appendices into a deliverable zip."""
    result = render_deliverable_package(
        RenderRequest(
            excel_bytes=excel_bytes,
            template_bytes=template_bytes,
            meta=meta,
            excel_filename=excel_filename,
            template_filename=template_filename,
            include_appendices=include_appendices,
            uploaded_appendices=list(uploaded_appendices or []),
            appendix_labels_present=appendix_labels_present,
        ),
        report_filename=report_filename,
    )
    assert result.package_bytes is not None
    return result.package_bytes, result.warnings, result.record


def render_batch_from_bytes(
    excel_bytes: bytes,
    template_bytes: bytes,
    *,
    meta: dict[str, str] | None = None,
    excel_filename: str = "data.xlsx",
    template_filename: str = "template.docx",
    include_appendices: bool = True,
    uploaded_appendices: list[AppendixFile] | None = None,
    appendix_labels_present: set[str] | None = None,
) -> list[Any]:
    """Render one report per ProjectData row via render_service (appendix-aware batch)."""
    from render_service import RenderRequest, render_batch_reports

    return render_batch_reports(
        RenderRequest(
            excel_bytes=excel_bytes,
            template_bytes=template_bytes,
            meta=meta,
            excel_filename=excel_filename,
            template_filename=template_filename,
            include_appendices=include_appendices,
            uploaded_appendices=list(uploaded_appendices or []),
            appendix_labels_present=appendix_labels_present,
        )
    )


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
