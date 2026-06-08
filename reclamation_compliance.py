"""Reclamation certificate preflight checklist (extends Phase I SED workflow)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

CHECKLIST_PATH = (
    Path(__file__).resolve().parent / "schemas" / "reclamation_checklist.json"
)
RECLAMATION_PROFILES = frozenset({"reclamation_certificate"})

SHEET_KEYS = {
    "ReclamationTasks": "reclamation_tasks",
    "SoilPlacement": "soil_placement",
    "Vegetation": "vegetation",
}


@dataclass
class ReclamationItemResult:
    item_id: str
    section_id: str
    label: str
    requirement: str
    satisfied: bool
    detail: str = ""


@dataclass
class ReclamationComplianceResult:
    report_type: str
    total_items: int = 0
    satisfied_count: int = 0
    required_missing: list[ReclamationItemResult] = field(default_factory=list)
    recommended_missing: list[ReclamationItemResult] = field(default_factory=list)
    items: list[ReclamationItemResult] = field(default_factory=list)

    @property
    def completeness_pct(self) -> float:
        if self.total_items == 0:
            return 100.0
        return round(100.0 * self.satisfied_count / self.total_items, 1)

    @property
    def ready_for_qp_review(self) -> bool:
        return len(self.required_missing) == 0


def _norm_key(name: str) -> str:
    return re.sub(r"\s+", "_", str(name).strip()).lower()


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


def evaluate_reclamation_compliance(
    context: dict[str, Any],
    meta: dict[str, str] | None,
    *,
    report_type: str = "reclamation_certificate",
    sheet_row_counts: dict[str, int] | None = None,
) -> ReclamationComplianceResult | None:
    rt = (report_type or "reclamation_certificate").strip()
    data = load_checklist()
    if rt not in set(data.get("profile_ids", [])) | RECLAMATION_PROFILES:
        return None

    meta = meta or {}
    sheet_counts = sheet_row_counts or {}
    result = ReclamationComplianceResult(report_type=rt)

    for section in data.get("sections", []):
        sec_id = str(section.get("id", ""))
        for item in section.get("items", []):
            req = str(item.get("requirement", "recommended"))
            item_id = str(item.get("id", ""))
            label = str(item.get("label", item_id))
            source = str(item.get("source", ""))
            satisfied = False
            detail = ""
            min_rows = int(item.get("min_rows", 1))

            if source == "projectdata":
                fld = str(item.get("field", ""))
                satisfied = _has_value(_context_value(context, meta, fld))
                if not satisfied:
                    detail = f"ProjectData.{fld} empty"
            elif source == "sheet":
                sheet = str(item.get("sheet", ""))
                key = SHEET_KEYS.get(sheet, sheet.lower())
                count = sheet_counts.get(key, sheet_counts.get(sheet, 0))
                if min_rows == 0:
                    satisfied = True
                else:
                    satisfied = count >= min_rows
                if not satisfied:
                    detail = f"{sheet}: {count} row(s), need >={min_rows}"

            ir = ReclamationItemResult(
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

    return result
