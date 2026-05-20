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
    dry_run: bool = False
    ai_audit: list[dict[str, Any]] = field(default_factory=list)

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
) -> GenerationRecord:
    meta = meta or {}
    cov = coverage
    return GenerationRecord(
        generated_at=datetime.now(timezone.utc).isoformat(),
        report_phase=str(meta.get("report_phase", "")),
        prepared_by=str(meta.get("prepared_by", "")),
        template_version=str(meta.get("template_version", "")),
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
    )


def record_filename(docx_name: str | None) -> str:
    base = (docx_name or "esa_report.docx").rsplit(".", 1)[0]
    return f"{base}_manifest.json"
