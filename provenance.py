"""
Generation provenance and dry-run helpers (audit trail pattern used in document automation).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

ENGINE_VERSION = "1.0.0"
APP_NAME = "esa-report-generator"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class GenerationRecord:
    """JSON-serializable manifest for reproducibility and QA (similar to merge audit logs)."""

    generated_at: str
    app_name: str = APP_NAME
    engine_version: str = ENGINE_VERSION
    report_phase: str = ""
    prepared_by: str = ""
    template_version: str = ""
    excel_sha256: str = ""
    template_sha256: str = ""
    output_sha256: str | None = None
    excel_filename: str = ""
    template_filename: str = ""
    output_filename: str = ""
    template_var_count: int = 0
    matched_var_count: int = 0
    missing_var_count: int = 0
    lab_row_count: int = 0
    warning_count: int = 0
    missing_variables: list[str] = field(default_factory=list)
    report_type: str = ""
    template_source_format: str = ""
    appendix_files: list[dict[str, str]] = field(default_factory=list)
    generated_appendix_files: list[dict[str, str]] = field(default_factory=list)
    dry_run: bool = False
    ai_audit: list[dict[str, Any]] = field(default_factory=list)
    project_folder: str = ""
    ecoventure_contract_version: str = ""
    ecoventure_workbook_template_id: str = ""
    sed002_completeness_pct: float | None = None
    dwda_checklist_scope: str = ""
    appendix_labels_evaluated: list[str] = field(default_factory=list)
    phase2_reasons: list[str] = field(default_factory=list)
    dwda_calc_source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True).encode("utf-8")


def build_generation_record(
    *,
    excel_bytes: bytes,
    template_bytes: bytes,
    meta: dict[str, str] | None,
    coverage: Any | None,
    warnings: list[str],
    missing_variables: list[str],
    output_bytes: bytes | None = None,
    excel_filename: str = "",
    template_filename: str = "",
    output_filename: str = "",
    dry_run: bool = False,
    template_source_format: str = "",
    appendix_files: list[dict[str, str]] | None = None,
    context: dict[str, Any] | None = None,
) -> GenerationRecord:
    meta = meta or {}
    ctx = context or {}
    cov = coverage
    return GenerationRecord(
        generated_at=datetime.now(timezone.utc).isoformat(),
        report_phase=str(meta.get("report_phase", "")),
        report_type=str(meta.get("report_type", "")),
        prepared_by=str(meta.get("prepared_by", "")),
        template_version=str(meta.get("template_version", "")),
        template_source_format=template_source_format or "",
        appendix_files=list(appendix_files or []),
        excel_sha256=sha256_hex(excel_bytes),
        template_sha256=sha256_hex(template_bytes),
        output_sha256=sha256_hex(output_bytes) if output_bytes else None,
        excel_filename=excel_filename,
        template_filename=template_filename,
        output_filename=output_filename,
        template_var_count=len(cov.template_vars) if cov else 0,
        matched_var_count=len(cov.matched) if cov else 0,
        missing_var_count=len(cov.missing_in_data) if cov else len(missing_variables),
        lab_row_count=cov.lab_row_count if cov else 0,
        warning_count=len(warnings),
        missing_variables=list(missing_variables),
        dry_run=dry_run,
        ecoventure_contract_version=str(ctx.get("_ecoventure_contract_version", "")),
        ecoventure_workbook_template_id=str(ctx.get("_ecoventure_workbook_template_id", "")),
    )


def record_filename(docx_name: str | None) -> str:
    base = (docx_name or "esa_report.docx").rsplit(".", 1)[0]
    return f"{base}_manifest.json"


def apply_compliance_snapshot(
    record: GenerationRecord,
    context: dict[str, Any],
    appendix_labels: set[str] | frozenset[str] | None = None,
) -> None:
    """Persist compliance state at generation time for QP audit trail."""
    from compliance_helpers import resolved_appendix_labels, sorted_appendix_label_list

    record.appendix_labels_evaluated = sorted_appendix_label_list(
        resolved_appendix_labels(context, appendix_labels)
    )

    record.dwda_checklist_scope = str(context.get("dwda_checklist_scope") or "")
    record.dwda_calc_source = str(context.get("dwda_calc_source") or "")

    sed = context.get("_sed002_compliance")
    if sed is not None:
        record.sed002_completeness_pct = float(getattr(sed, "completeness_pct", 0) or 0)

    reasons = context.get("phase2_reasons")
    if isinstance(reasons, list):
        record.phase2_reasons = [str(r) for r in reasons if str(r).strip()]
