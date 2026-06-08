"""
AER SED 002 Section 10 Phase 1 ESA compliance evaluation for pre-flight and exports.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from engine import DRILLING_WASTE_SHEET, PROJECT_SHEET, STORAGE_TANKS_SHEET

CHECKLIST_PATH = (
    Path(__file__).resolve().parent / "schemas" / "sed002_phase1_checklist.json"
)

PHASE1_SED_PROFILES = frozenset(
    {"phase1_alberta", "phase1_devon", "reclamation_certificate"}
)


@dataclass
class Sed002ItemResult:
    item_id: str
    section_id: str
    label: str
    requirement: str
    satisfied: bool
    detail: str = ""


@dataclass
class Sed002ComplianceResult:
    """SED 002 §10 checklist evaluation."""

    report_type: str
    total_items: int = 0
    satisfied_count: int = 0
    required_missing: list[Sed002ItemResult] = field(default_factory=list)
    recommended_missing: list[Sed002ItemResult] = field(default_factory=list)
    items: list[Sed002ItemResult] = field(default_factory=list)
    phase2_warnings: list[str] = field(default_factory=list)
    appendix_missing: list[str] = field(default_factory=list)

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


def _meta_value(meta: dict[str, str], field_name: str) -> Any:
    target = _norm_key(field_name)
    for key, val in meta.items():
        if _norm_key(key) == target and _has_value(val):
            return val
    return None


def _context_value(
    context: dict[str, Any],
    meta: dict[str, str],
    field_name: str,
) -> Any:
    meta_val = _meta_value(meta, field_name)
    if meta_val is not None:
        return meta_val
    target = _norm_key(field_name)
    for key, val in context.items():
        if _norm_key(key) == target:
            return val
    return None


def evaluate_sed002_compliance(
    context: dict[str, Any],
    meta: dict[str, str] | None,
    *,
    report_type: str = "phase1_alberta",
    sheet_row_counts: dict[str, int] | None = None,
    appendix_labels_present: set[str] | None = None,
) -> Sed002ComplianceResult | None:
    """Evaluate SED 002 checklist when profile is Phase I / reclamation."""
    rt = (report_type or "phase1_alberta").strip() or "phase1_alberta"
    data = load_checklist()
    allowed = set(data.get("profile_ids", [])) | PHASE1_SED_PROFILES
    if rt not in allowed:
        return None

    meta = meta or {}
    sheet_counts = sheet_row_counts or {}
    if not sheet_counts:
        sheet_counts = {
            "drilling_waste": len(context.get("drilling_waste") or []),
            "storage_tanks": len(context.get("storage_tanks") or []),
        }
    appendices = appendix_labels_present or set()
    appendix_missing: set[str] = set()

    result = Sed002ComplianceResult(report_type=rt)
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
                val = _context_value(context, meta, fld)
                satisfied = _has_value(val)
                if not satisfied:
                    detail = f"ProjectData.{fld} empty"
            elif source == "meta":
                fld = str(item.get("field", ""))
                satisfied = _has_value(_meta_value(meta, fld))
                if not satisfied:
                    detail = f"Sidebar/meta '{fld}' empty"
            elif source == "sheet":
                sheet = str(item.get("sheet", ""))
                min_rows = int(item.get("min_rows", 1))
                key = {
                    DRILLING_WASTE_SHEET: "drilling_waste",
                    STORAGE_TANKS_SHEET: "storage_tanks",
                    "DrillingWaste": "drilling_waste",
                    "StorageTanks": "storage_tanks",
                }.get(sheet, sheet.lower())
                count = sheet_counts.get(key, sheet_counts.get(sheet, 0))
                if min_rows == 0:
                    satisfied = True
                else:
                    satisfied = count >= min_rows
                if not satisfied:
                    detail = f"{sheet}: {count} row(s), need >={min_rows}"
            elif source == "appendix":
                label_key = str(item.get("appendix", ""))
                satisfied = label_key in appendices
                if not satisfied:
                    detail = f"Appendix {label_key} not uploaded"
                    appendix_missing.add(label_key)
            elif source == "manual":
                fld = str(item.get("field", ""))
                satisfied = _has_value(_context_value(context, meta, fld))
                if not satisfied:
                    detail = "Manual / optional field"

            ir = Sed002ItemResult(
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

    from phase1_decision import evaluate_phase2_triggers

    result.appendix_missing = sorted(appendix_missing)
    result.phase2_warnings = evaluate_phase2_triggers(context, meta)
    return result


def build_qp_review_checklist_markdown(compliance: Sed002ComplianceResult) -> str:
    lines = [
        "# SED 002 Phase 1 ESA — QP review checklist",
        "",
        f"Completeness: **{compliance.completeness_pct}%** "
        f"({compliance.satisfied_count}/{compliance.total_items} items)",
        "",
    ]
    if compliance.required_missing:
        lines.append("## Required — missing")
        for ir in compliance.required_missing:
            lines.append(f"- [ ] **{ir.section_id}** {ir.label} — {ir.detail}")
        lines.append("")
    if compliance.recommended_missing:
        lines.append("## Recommended — missing")
        for ir in compliance.recommended_missing[:25]:
            lines.append(f"- [ ] **{ir.section_id}** {ir.label} — {ir.detail}")
        if len(compliance.recommended_missing) > 25:
            lines.append(f"- ... and {len(compliance.recommended_missing) - 25} more")
        lines.append("")
    if compliance.phase2_warnings:
        lines.append("## Phase 2 trigger hints")
        for w in compliance.phase2_warnings:
            lines.append(f"- {w}")
        lines.append("")
    if compliance.appendix_missing:
        lines.append("## Appendices to attach")
        catalog = load_checklist().get("appendix_catalog", {})
        for key in sorted(set(compliance.appendix_missing)):
            desc = catalog.get(key, "")
            lines.append(f"- Appendix **{key}**: {desc}")
        lines.append("")
    lines.extend(
        [
            "## Reference",
            "- [AER reclamation certificate submissions](https://www.aer.ca/regulations-and-compliance-enforcement/site-closure-requirements/reclamation/oil-and-gas-sites/reclamation-certificate-application-submissions)",
            "- SED 002 (July 2025) — Phase 1 ESA Section 10",
            "",
            "_Generated by ESA Report Generator. QP must verify before OneStop submission._",
        ]
    )
    return "\n".join(lines)


def sed002_section_summary(compliance: Sed002ComplianceResult) -> dict[str, tuple[int, int]]:
    """Per-section (satisfied, total) counts."""
    sections: dict[str, list[bool]] = {}
    for ir in compliance.items:
        sections.setdefault(ir.section_id, []).append(ir.satisfied)
    return {sid: (sum(1 for x in vals if x), len(vals)) for sid, vals in sections.items()}
