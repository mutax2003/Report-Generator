"""
Phase II ESA preflight checklist evaluation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from engine import LAB_SHEET, PROJECT_SHEET

CHECKLIST_PATH = Path(__file__).resolve().parent / "schemas" / "phase2_esa_checklist.json"
PHASE2_PROFILES = frozenset({"phase2_esa"})


@dataclass
class ChecklistItemResult:
    item_id: str
    section_id: str
    label: str
    requirement: str
    satisfied: bool
    detail: str = ""


@dataclass
class Phase2ComplianceResult:
    report_type: str
    total_items: int = 0
    satisfied_count: int = 0
    required_missing: list[ChecklistItemResult] = field(default_factory=list)
    recommended_missing: list[ChecklistItemResult] = field(default_factory=list)
    items: list[ChecklistItemResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def completeness_pct(self) -> float:
        if self.total_items == 0:
            return 100.0
        return round(100.0 * self.satisfied_count / self.total_items, 1)

    @property
    def ready_for_qp_review(self) -> bool:
        return len(self.required_missing) == 0


def _norm_key(name: str) -> str:
    s = str(name).strip()
    s = re.sub(r"\s+", "_", s)
    return s.lower()


@lru_cache(maxsize=1)
def load_checklist() -> dict[str, Any]:
    return json.loads(CHECKLIST_PATH.read_text(encoding="utf-8"))


def _has_value(val: Any) -> bool:
    if val is None:
        return False
    s = str(val).strip()
    return bool(s) and s.lower() not in ("nan", "none", "n/a", "")


def _context_value(
    context: dict[str, Any], meta: dict[str, str], field_name: str
) -> Any:
    target = _norm_key(field_name)
    for key, val in meta.items():
        if _norm_key(key) == target and _has_value(val):
            return val
    for key, val in context.items():
        if _norm_key(key) == target:
            return val
    return None


def evaluate_phase2_compliance(
    context: dict[str, Any],
    meta: dict[str, str] | None,
    *,
    report_type: str = "phase2_esa",
    sheet_row_counts: dict[str, int] | None = None,
) -> Phase2ComplianceResult | None:
    rt = (report_type or "phase2_esa").strip()
    data = load_checklist()
    if rt not in set(data.get("profile_ids", [])) | PHASE2_PROFILES:
        return None

    meta = meta or {}
    sheet_counts = sheet_row_counts or {}
    if not sheet_counts:
        sheet_counts = {"lab_results": len(context.get("lab_results") or [])}

    result = Phase2ComplianceResult(report_type=rt)
    for section in data.get("sections", []):
        sec_id = str(section.get("id", ""))
        for item in section.get("items", []):
            req = str(item.get("requirement", "recommended"))
            item_id = str(item.get("id", ""))
            label = str(item.get("label", item_id))
            source = str(item.get("source", ""))
            satisfied = False
            detail = ""

            if source == "projectdata":
                fld = str(item.get("field", ""))
                satisfied = _has_value(_context_value(context, meta, fld))
                if not satisfied:
                    detail = f"ProjectData.{fld} empty"
            elif source == "meta":
                fld = str(item.get("field", ""))
                target = _norm_key(fld)
                satisfied = any(
                    _norm_key(k) == target and _has_value(v) for k, v in meta.items()
                )
                if not satisfied:
                    detail = f"Sidebar/meta '{fld}' empty"
            elif source == "sheet":
                sheet = str(item.get("sheet", ""))
                min_rows = int(item.get("min_rows", 1))
                key = {LAB_SHEET: "lab_results", "LabResults": "lab_results"}.get(
                    sheet, sheet.lower()
                )
                count = sheet_counts.get(key, sheet_counts.get(sheet, 0))
                satisfied = count >= min_rows if min_rows else True
                if not satisfied:
                    detail = f"{sheet}: {count} row(s), need >={min_rows}"

            ir = ChecklistItemResult(
                item_id=item_id,
                section_id=sec_id,
                label=label,
                requirement=req,
                satisfied=satisfied,
                detail=detail,
            )
            result.items.append(ir)
            result.total_items += 1
            if satisfied:
                result.satisfied_count += 1
            elif req == "required":
                result.required_missing.append(ir)
            else:
                result.recommended_missing.append(ir)

    lab_rows = context.get("lab_results") or []
    if isinstance(lab_rows, list):
        exc_without_criteria = 0
        for row in lab_rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("exceedance_flag", "")).upper() in ("Y", "YES"):
                if not _has_value(row.get("criteria")):
                    exc_without_criteria += 1
        if exc_without_criteria:
            result.warnings.append(
                f"{exc_without_criteria} exceedance row(s) lack criteria values — "
                "verify screening levels in LabResults."
            )

    return result
