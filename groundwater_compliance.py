"""Groundwater monitoring preflight checklist."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

CHECKLIST_PATH = (
    Path(__file__).resolve().parent / "schemas" / "groundwater_checklist.json"
)
GW_PROFILES = frozenset({"groundwater_monitoring", "phase3_remediation"})

SHEET_KEYS = {
    "MonitoringWells": "monitoring_wells",
    "WaterLevels": "water_levels",
    "GroundwaterLab": "groundwater_results",
}


@dataclass
class GwChecklistItemResult:
    item_id: str
    section_id: str
    label: str
    requirement: str
    satisfied: bool
    detail: str = ""


@dataclass
class GroundwaterComplianceResult:
    report_type: str
    total_items: int = 0
    satisfied_count: int = 0
    required_missing: list[GwChecklistItemResult] = field(default_factory=list)
    recommended_missing: list[GwChecklistItemResult] = field(default_factory=list)
    items: list[GwChecklistItemResult] = field(default_factory=list)
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
    return re.sub(r"\s+", "_", s).lower()


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


def evaluate_groundwater_compliance(
    context: dict[str, Any],
    meta: dict[str, str] | None,
    *,
    report_type: str = "groundwater_monitoring",
    sheet_row_counts: dict[str, int] | None = None,
) -> GroundwaterComplianceResult | None:
    rt = (report_type or "groundwater_monitoring").strip()
    data = load_checklist()
    if rt not in set(data.get("profile_ids", [])) | GW_PROFILES:
        return None

    meta = meta or {}
    sheet_counts = sheet_row_counts or {}
    result = GroundwaterComplianceResult(report_type=rt)

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
            elif source == "sheet":
                sheet = str(item.get("sheet", ""))
                min_rows = int(item.get("min_rows", 1))
                key = SHEET_KEYS.get(sheet, sheet.lower())
                count = sheet_counts.get(key, sheet_counts.get(sheet, 0))
                satisfied = count >= min_rows if min_rows else True
                if not satisfied:
                    detail = f"{sheet}: {count} row(s), need >={min_rows}"

            ir = GwChecklistItemResult(
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

    for phrase in ("gw_program_intro", "gw_sampling_methods", "gw_recommendations"):
        if not _has_value(context.get(phrase)):
            result.warnings.append(
                f"Phrase '{phrase}' empty — set PhraseCatalog / Standard phrases panel."
            )

    return result
