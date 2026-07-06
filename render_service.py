"""
Unified headless render pipeline for Streamlit, CLI, project folder, and automation.

Derives appendix labels before Word merge so DWDA/SED enrichment matches uploaded appendices.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from appendix_generator import attach_appendices_to_record
from compliance_helpers import normalize_appendix_labels, resolved_appendix_labels
from deliverable_pack import AppendixFile, build_deliverable_zip_bytes
from engine import BatchReportResult, ReportEngine
from provenance import GenerationRecord, apply_compliance_snapshot, sha256_hex
from template_attachments import PreparedTemplate, prepare_template_upload_cached


def appendix_labels_from_uploads(uploaded: list[AppendixFile] | None) -> frozenset[str]:
    return normalize_appendix_labels(a.label for a in (uploaded or []))


@dataclass
class RenderRequest:
    excel_bytes: bytes
    template_bytes: bytes
    meta: dict[str, str] | None = None
    excel_filename: str = "data.xlsx"
    template_filename: str = "template.docx"
    project_row_index: int = 0
    uploaded_appendices: list[AppendixFile] = field(default_factory=list)
    appendix_labels_present: set[str] | frozenset[str] | None = None
    include_appendices: bool = True
    include_coverage: bool = True


@dataclass
class RenderResult:
    docx_bytes: bytes
    context: dict[str, Any]
    record: GenerationRecord
    appendices: list[AppendixFile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    package_bytes: bytes | None = None


def resolve_request_labels(req: RenderRequest) -> frozenset[str]:
    if req.appendix_labels_present is not None:
        return normalize_appendix_labels(req.appendix_labels_present)
    return appendix_labels_from_uploads(req.uploaded_appendices)


def _prepare_engine(req: RenderRequest) -> tuple[dict[str, str], PreparedTemplate, frozenset[str], ReportEngine]:
    meta = req.meta or {}
    prepared = prepare_template_upload_cached(req.template_bytes, req.template_filename)
    labels = resolve_request_labels(req)
    engine = ReportEngine(
        excel_bytes=req.excel_bytes,
        template_bytes=prepared.docx_bytes,
    )
    return meta, prepared, labels, engine


def _finalize_render(
    req: RenderRequest,
    record: GenerationRecord,
    context: dict[str, Any],
    labels: frozenset[str],
    base_warnings: list[str],
) -> tuple[list[AppendixFile], list[str]]:
    apply_compliance_snapshot(record, context, resolved_appendix_labels(context, labels))
    warnings = list(base_warnings)
    appendices: list[AppendixFile] = []
    if req.include_appendices:
        _generated, merged, ap_warnings = attach_appendices_to_record(
            record, context, req.meta or {}, req.uploaded_appendices
        )
        appendices = merged
        warnings.extend(ap_warnings)
    return appendices, warnings


def render_report(req: RenderRequest) -> RenderResult:
    """Render report with appendix-aware DWDA/SED context; optionally attach appendices."""
    meta, prepared, labels, engine = _prepare_engine(req)
    docx_bytes, warnings, context, record = engine.render(
        meta=meta,
        excel_filename=req.excel_filename,
        template_filename=req.template_filename,
        project_row_index=req.project_row_index,
        include_coverage=req.include_coverage,
        appendix_labels_present=labels,
    )
    appendices, all_warnings = _finalize_render(
        req, record, context, labels, list(prepared.warnings) + list(warnings)
    )
    return RenderResult(
        docx_bytes=docx_bytes,
        context=context,
        record=record,
        appendices=appendices,
        warnings=all_warnings,
    )


def render_batch_reports(req: RenderRequest) -> list[BatchReportResult]:
    """Render one report per ProjectData row with appendix-aware compliance on each manifest.

    Uses the same uploaded appendix set for every row (batch limitation).
    """
    meta, prepared, labels, engine = _prepare_engine(req)
    batch = engine.render_batch(
        meta=meta,
        excel_filename=req.excel_filename,
        template_filename=req.template_filename,
        appendix_labels_present=labels,
    )
    prefix_warnings = list(prepared.warnings)
    for item in batch:
        appendices, all_warnings = _finalize_render(
            req, item.record, item.context, labels, prefix_warnings + list(item.warnings)
        )
        item.appendices = appendices
        item.warnings = all_warnings
    return batch


def render_deliverable_package(req: RenderRequest, *, report_filename: str) -> RenderResult:
    """Render report + appendices and build deliverable zip bytes."""
    result = render_report(req)
    record = result.record
    record.output_filename = report_filename
    record.output_sha256 = sha256_hex(result.docx_bytes)
    manifest_bytes = record.to_json_bytes()
    result.package_bytes = build_deliverable_zip_bytes(
        result.docx_bytes,
        report_filename,
        result.context,
        req.meta,
        manifest_bytes,
        result.appendices,
    )
    return result
