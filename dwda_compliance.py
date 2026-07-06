"""
DWDA / AER Directive 050 compliance evaluation for Phase I preflight and appendices.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from compliance_helpers import (
    context_value as _context_value,
    has_value as _has_value,
    norm_key as _norm_key,
    normalize_appendix_labels,
    parse_float as _parse_float,
    yes_value as _yes,
)

CHECKLIST_PATH = (
    Path(__file__).resolve().parent / "schemas" / "dwda_compliance_checklist.json"
)

PHASE1_DWDA_PROFILES = frozenset(
    {"phase1_alberta", "phase1_devon", "reclamation_certificate"}
)

LWD_CUTTINGS_THRESHOLD_M3 = 50.0

ON_LEASE_MARKERS = (
    "on-lease",
    "on lease",
    "onlease",
    "lwd",
    "landspray",
    "landspread",
    "sump",
    "well centre",
    "well center",
    "onsite",
    "on-site",
    "on site",
)
REMOTE_MARKERS = ("remote", "off-lease", "off lease", "offlease", "haul")


@dataclass
class DwdaItemResult:
    item_id: str
    section: str
    label: str
    requirement: str
    satisfied: bool
    response: str = ""
    detail: str = ""


@dataclass
class DwdaComplianceResult:
    """DWDA / Directive 050 checklist evaluation."""

    report_type: str
    compliance_option: str = ""
    checklist_scope: str = "none"
    cuttings_volume_on_lease_m3: float | None = None
    total_items: int = 0
    satisfied_count: int = 0
    required_missing: list[DwdaItemResult] = field(default_factory=list)
    recommended_missing: list[DwdaItemResult] = field(default_factory=list)
    items: list[DwdaItemResult] = field(default_factory=list)
    phase2_required: bool = False
    phase2_reasons: list[str] = field(default_factory=list)
    guideline_summary: str = ""
    checklist_results: list[dict[str, str]] = field(default_factory=list)

    @property
    def completeness_pct(self) -> float:
        if self.total_items == 0:
            return 100.0
        return round(100.0 * self.satisfied_count / self.total_items, 1)

    @property
    def ready_for_qp_review(self) -> bool:
        return len(self.required_missing) == 0 and not self.phase2_required

    @property
    def checklist_complete(self) -> bool:
        if not self.checklist_results:
            return False
        applicable = [
            r
            for r in self.checklist_results
            if str(r.get("applies", "")).lower() == "yes"
        ]
        if not applicable:
            return True
        return all(
            str(r.get("response", "")).strip().lower() in ("yes", "y", "n/a", "na")
            for r in applicable
        )


@lru_cache(maxsize=1)
def load_dwda_checklist() -> dict[str, Any]:
    return json.loads(CHECKLIST_PATH.read_text(encoding="utf-8"))


def normalize_compliance_option(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if not s or s in ("nan", "none"):
        return ""
    if "approved" in s and "facilit" in s:
        return "approved_facility"
    if "no" in s and "waste" in s:
        return "no_on_site_waste"
    if "option 3" in s or "option_3" in s or s == "3":
        return "option_3"
    if "option 2" in s or "option_2" in s or s == "2":
        return "option_2"
    if "option 1" in s or "option_1" in s or s == "1":
        return "option_1"
    if "option" in s:
        return "option_1"
    return s.replace(" ", "_")


def _row_text(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("disposal_type", "")),
        str(row.get("disposal_method", "")),
        str(row.get("location", "")),
    ]
    return " ".join(parts).lower()


def _is_on_lease_row(row: dict[str, Any]) -> bool:
    text = _row_text(row)
    if any(m in text for m in REMOTE_MARKERS) and "on-lease" not in text:
        if "off-lease" in text or "remote" in text or "haul" in text:
            return False
    return any(m in text for m in ON_LEASE_MARKERS)


def _is_remote_row(row: dict[str, Any]) -> bool:
    text = _row_text(row)
    return any(m in text for m in REMOTE_MARKERS)


def _has_lwd_on_lease(waste_rows: list[dict[str, Any]]) -> bool:
    for row in waste_rows:
        if not isinstance(row, dict):
            continue
        text = _row_text(row)
        if "lwd" in text and _is_on_lease_row(row):
            return True
    return False


def _has_off_lease_disposal(waste_rows: list[dict[str, Any]]) -> bool:
    for row in waste_rows:
        if isinstance(row, dict) and _is_remote_row(row):
            return True
    return False


def _no_waste_on_site(context: dict[str, Any]) -> bool:
    val = str(context.get("no_drilling_waste_on_site") or "").strip().lower()
    return val in ("y", "yes", "true", "1")


def derive_cuttings_volume_on_lease_m3(
    waste_rows: list[dict[str, Any]],
) -> float | None:
    """Sum DrillingWaste volume_m3 for on-lease rows when ProjectData field is empty."""
    total = 0.0
    found = False
    for row in waste_rows:
        if not isinstance(row, dict) or not _is_on_lease_row(row):
            continue
        vol = _parse_float(row.get("volume_m3"))
        if vol is not None:
            total += vol
            found = True
    return total if found else None


def determine_checklist_scope(
    context: dict[str, Any],
    meta: dict[str, str] | None = None,
) -> tuple[str, str, float | None]:
    """
    Return (normalized_option, checklist_scope, cuttings_m3).
    checklist_scope: option_1_minimal | option_1_full | option_2 | option_3 |
                     approved_facility | none
    """
    meta = meta or {}
    raw_option = _context_value(context, meta, "aer_waste_compliance_option")
    option = normalize_compliance_option(raw_option)

    if _no_waste_on_site(context) and not (context.get("drilling_waste") or []):
        return option or "no_on_site_waste", "none", None

    if option == "approved_facility":
        return option, "approved_facility", None
    if option == "option_3":
        return option, "option_3", None
    if option == "option_2":
        return option, "option_2", None

    cuttings = _parse_float(
        _context_value(context, meta, "cuttings_volume_on_lease_m3")
    )
    waste_rows = [
        r for r in (context.get("drilling_waste") or []) if isinstance(r, dict)
    ]
    if cuttings is None:
        cuttings = derive_cuttings_volume_on_lease_m3(waste_rows)
    off_lease = _has_off_lease_disposal(waste_rows)
    lwd_on_lease = _has_lwd_on_lease(waste_rows)

    if option in ("", "option_1"):
        option = "option_1"
        if cuttings is not None and cuttings > LWD_CUTTINGS_THRESHOLD_M3:
            return option, "option_1_full", cuttings
        if lwd_on_lease and cuttings is not None and cuttings > LWD_CUTTINGS_THRESHOLD_M3:
            return option, "option_1_full", cuttings
        if lwd_on_lease and not off_lease:
            return option, "option_1_full", cuttings
        if off_lease and (cuttings is None or cuttings <= LWD_CUTTINGS_THRESHOLD_M3):
            return option, "option_1_minimal", cuttings
        if waste_rows:
            return option, "option_1_full", cuttings
        return option, "option_1_minimal", cuttings

    return option, "option_1_minimal", cuttings


def _dwda_checklist_map(context: dict[str, Any]) -> dict[str, dict[str, str]]:
    rows = context.get("dwda_checklist") or []
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        item_id = str(row.get("checklist_item_id") or row.get("item_id") or "").strip()
        if item_id:
            out[item_id] = {
                "response": str(row.get("response", "")).strip(),
                "notes": str(row.get("notes", "")).strip(),
            }
    return out


def _waste_field_satisfied(
    waste_rows: list[dict[str, Any]],
    field: str,
    *,
    when_on_lease: bool = False,
    when_remote: bool = False,
) -> tuple[bool, str]:
    if not waste_rows:
        return False, "No DrillingWaste rows"
    target_rows = waste_rows
    if when_on_lease:
        target_rows = [r for r in waste_rows if _is_on_lease_row(r)]
        if not target_rows:
            return True, "No on-lease disposal rows (N/A)"
    if when_remote:
        target_rows = [r for r in waste_rows if _is_remote_row(r)]
        if not target_rows:
            return True, "No remote disposal rows (N/A)"
    for row in target_rows:
        if _has_value(row.get(field)):
            return True, ""
    return False, f"No {field} in applicable DrillingWaste row(s)"


def _waste_fields_satisfied(
    waste_rows: list[dict[str, Any]],
    fields: list[str],
    *,
    when_on_lease: bool = False,
) -> tuple[bool, str]:
    for fld in fields:
        ok, detail = _waste_field_satisfied(
            waste_rows, fld, when_on_lease=when_on_lease
        )
        if not ok:
            return False, detail
    return True, ""


def evaluate_dwda_compliance(
    context: dict[str, Any],
    meta: dict[str, str] | None,
    *,
    report_type: str = "phase1_alberta",
    appendix_labels_present: set[str] | None = None,
) -> DwdaComplianceResult | None:
    rt = (report_type or "phase1_alberta").strip() or "phase1_alberta"
    data = load_dwda_checklist()
    if rt not in set(data.get("profile_ids", [])) | PHASE1_DWDA_PROFILES:
        return None

    meta = meta or {}
    appendices = appendix_labels_present or set()
    waste_rows = [
        r for r in (context.get("drilling_waste") or []) if isinstance(r, dict)
    ]
    option, scope, cuttings = determine_checklist_scope(context, meta)

    result = DwdaComplianceResult(
        report_type=rt,
        compliance_option=option,
        checklist_scope=scope,
        cuttings_volume_on_lease_m3=cuttings,
        guideline_summary=(
            "Salinity within DWDA: Equivalent Salinity Guidelines. "
            "Other COPCs in DWDA and remainder of lease: Alberta Tier 1/2."
        ),
    )

    if scope == "none":
        result.guideline_summary = "No on-site drilling waste disposal documented."
        return result

    checklist_map = _dwda_checklist_map(context)

    for item in data.get("items", []):
        applies_when = item.get("applies_when") or []
        if scope not in applies_when:
            continue

        item_id = str(item.get("id", ""))
        label = str(item.get("label", item_id))
        section = str(item.get("section", ""))
        req = str(item.get("requirement", "recommended"))
        source = str(item.get("source", ""))
        satisfied = False
        detail = ""
        response = checklist_map.get(item_id, {}).get("response", "")

        if source == "projectdata":
            fld = str(item.get("field", ""))
            satisfied = _has_value(_context_value(context, meta, fld))
            if not satisfied:
                detail = f"ProjectData.{fld} empty"
        elif source == "drilling_waste":
            min_rows = int(item.get("min_rows", 1))
            satisfied = len(waste_rows) >= min_rows
            if not satisfied:
                detail = f"DrillingWaste: {len(waste_rows)} row(s), need >={min_rows}"
        elif source == "drilling_waste_field":
            fld = item.get("field")
            fields = item.get("fields")
            when_on = bool(item.get("when_on_lease"))
            when_remote = bool(item.get("when_remote"))
            if fields:
                satisfied, detail = _waste_fields_satisfied(
                    waste_rows, list(fields), when_on_lease=when_on
                )
            elif fld:
                satisfied, detail = _waste_field_satisfied(
                    waste_rows,
                    str(fld),
                    when_on_lease=when_on,
                    when_remote=when_remote,
                )
        elif source == "appendix":
            key = str(item.get("appendix", ""))
            satisfied = key in appendices
            if not satisfied:
                detail = f"Appendix {key} not uploaded or auto-generated"
        elif source == "dwda_checklist_complete":
            satisfied = bool(checklist_map) and all(
                str(v.get("response", "")).lower() in ("yes", "y", "n/a", "na", "")
                or not str(v.get("response", "")).strip()
                for v in checklist_map.values()
            )
            if not checklist_map:
                satisfied = False
                detail = "DwdaChecklist sheet empty"

        if response:
            resp_lower = response.lower()
            if resp_lower in ("yes", "y", "n/a", "na"):
                satisfied = True
                detail = response
            elif resp_lower in ("no", "unknown", ""):
                if req == "required":
                    satisfied = False
                    detail = f"DwdaChecklist response: {response or 'blank'}"

        ir = DwdaItemResult(
            item_id=item_id,
            section=section,
            label=label,
            requirement=req,
            satisfied=satisfied,
            response=response,
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

        result.checklist_results.append(
            {
                "item_id": item_id,
                "section": section,
                "label": label,
                "requirement": req,
                "applies": "yes",
                "response": response or ("Yes" if satisfied else ""),
                "status": "pass" if satisfied else "review",
                "detail": detail,
            }
        )

    from phase1_decision import evaluate_phase2_triggers

    existing = context.get("phase2_reasons")
    if isinstance(existing, list) and existing:
        phase2_hints = [str(r) for r in existing if str(r).strip()]
    else:
        phase2_hints = evaluate_phase2_triggers(context, meta)
    explicit = _yes(
        _context_value(context, meta, "dwda_phase2_required")
        or _context_value(context, meta, "phase2_drilling_waste_required")
    )
    reasons: list[str] = list(phase2_hints)
    if result.required_missing:
        reasons.append(
            f"{len(result.required_missing)} required DWDA checklist item(s) incomplete"
        )
    for row in waste_rows:
        disp = str(row.get("disposal_type") or "").lower()
        loc = str(row.get("location") or "").strip()
        if "unknown" in disp or not loc:
            reasons.append(
                "Unknown drilling waste disposal location — Phase II may be required"
            )
            break
    if explicit:
        reasons.insert(0, "QP flagged dwda_phase2_required / phase2_drilling_waste_required")

    result.phase2_reasons = list(dict.fromkeys(reasons))
    result.phase2_required = explicit
    if not explicit:
        if result.required_missing and any(
            "unknown" in r.lower() or "location" in r.lower()
            for r in result.phase2_reasons
        ):
            result.phase2_required = True
        elif result.required_missing:
            for ir in result.required_missing:
                if ir.item_id in ("d050.gps_on_lease", "d050.waste_table"):
                    result.phase2_required = True
                    break

    return result


def _merge_calc_phase2(
    compliance: DwdaComplianceResult,
    calc_result: Any,
) -> None:
    if calc_result is None:
        return
    extra = getattr(calc_result, "phase2_reasons", None) or ()
    if extra:
        compliance.phase2_reasons = list(
            dict.fromkeys((*compliance.phase2_reasons, *extra))
        )
    if getattr(calc_result, "phase2_required", False):
        compliance.phase2_required = True


def appendix_labels_key(labels: set[str] | frozenset[str] | None) -> frozenset[str]:
    return normalize_appendix_labels(labels)


def resolve_dwda_appendix_labels(
    context: dict[str, Any],
    meta: dict[str, str] | None,
    *,
    extra_labels: set[str] | None = None,
    report_type: str = "",
) -> frozenset[str]:
    """Uploaded appendix labels plus auto-generated A/D/G predicted from context."""
    from appendix_generator import predicted_appendix_labels

    rt = (report_type or str(context.get("_report_type") or "")).strip()
    labels = appendix_labels_key(extra_labels)
    labels |= appendix_labels_key(predicted_appendix_labels(context, meta, report_type=rt))
    return labels


def _apply_dwda_fields(
    out: dict[str, Any], compliance: DwdaComplianceResult
) -> dict[str, Any]:
    out["dwda_compliance_option"] = compliance.compliance_option
    out["dwda_checklist_scope"] = compliance.checklist_scope
    out["dwda_compliance_summary"] = (
        f"DWDA scope: {compliance.checklist_scope.replace('_', ' ')}; "
        f"{compliance.completeness_pct}% complete "
        f"({compliance.satisfied_count}/{compliance.total_items} items). "
        f"{compliance.guideline_summary}"
    )
    out["dwda_guideline_summary"] = compliance.guideline_summary
    out["dwda_checklist_results"] = list(compliance.checklist_results)
    out["dwda_phase2_required"] = "Yes" if compliance.phase2_required else "No"
    out["dwda_checklist_complete"] = "Yes" if compliance.checklist_complete else "No"
    calc_result = out.get("_dwda_calc_result")
    if calc_result is not None and getattr(calc_result, "summary", ""):
        out["dwda_compliance_summary"] += f" Calculations: {calc_result.summary}."
    if compliance.cuttings_volume_on_lease_m3 is not None:
        out["cuttings_volume_on_lease_m3"] = compliance.cuttings_volume_on_lease_m3
    else:
        waste_rows = [
            r for r in (out.get("drilling_waste") or []) if isinstance(r, dict)
        ]
        derived = derive_cuttings_volume_on_lease_m3(waste_rows)
        if derived is not None and not _has_value(out.get("cuttings_volume_on_lease_m3")):
            out["cuttings_volume_on_lease_m3"] = derived
    if compliance.phase2_required and not _yes(out.get("phase2_drilling_waste_required")):
        out["phase2_drilling_waste_required"] = "Yes"
    out["_dwda_compliance"] = compliance
    return out


def _finalize_dwda_enrichment(
    context: dict[str, Any],
    compliance: DwdaComplianceResult,
    labels_key: frozenset[str],
) -> dict[str, Any]:
    from dwda_calculations import apply_dwda_calc_to_context

    out = apply_dwda_calc_to_context(
        context,
        compliance_option=compliance.compliance_option,
    )
    _merge_calc_phase2(compliance, out.get("_dwda_calc_result"))
    if compliance.phase2_required and not _yes(out.get("phase2_drilling_waste_required")):
        out["phase2_drilling_waste_required"] = "Yes"
    out["_dwda_appendix_labels_evaluated"] = labels_key
    return _apply_dwda_fields(out, compliance)


def enrich_dwda_context(
    context: dict[str, Any],
    meta: dict[str, str] | None = None,
    *,
    appendix_labels_present: set[str] | None = None,
) -> dict[str, Any]:
    """Merge DWDA evaluation fields into render context (Phase I)."""
    rt = str(context.get("_report_type") or "phase1_alberta")
    if rt not in PHASE1_DWDA_PROFILES:
        return context

    labels_key = appendix_labels_key(appendix_labels_present)
    cached = context.get("_dwda_compliance")
    if cached is not None and context.get("_dwda_appendix_labels_evaluated") == labels_key:
        out = dict(context)
        if out.get("_dwda_calc_result") is None:
            return _finalize_dwda_enrichment(out, cached, labels_key)
        out["_dwda_appendix_labels_evaluated"] = labels_key
        return _apply_dwda_fields(out, cached)

    compliance = evaluate_dwda_compliance(
        context,
        meta,
        report_type=rt,
        appendix_labels_present=set(labels_key),
    )
    if compliance is None:
        return context

    return _finalize_dwda_enrichment(context, compliance, labels_key)


def build_dwda_qp_checklist_markdown(
    compliance: DwdaComplianceResult,
    *,
    calc_result: Any | None = None,
) -> str:
    data = load_dwda_checklist()
    lines = [
        "# DWDA / Directive 050 — QP review checklist",
        "",
        f"Compliance option: **{compliance.compliance_option or 'not set'}**",
        f"Checklist scope: **{compliance.checklist_scope}**",
        f"Completeness: **{compliance.completeness_pct}%** "
        f"({compliance.satisfied_count}/{compliance.total_items} items)",
        "",
        f"_{compliance.guideline_summary}_",
        "",
    ]
    if calc_result is not None and getattr(calc_result, "summary", ""):
        lines.extend(["## Calculations (metal / salt / DST)", "", f"_{calc_result.summary}_", ""])
        for label, passed in (
            ("Metal", getattr(calc_result, "metal_pass", None)),
            ("Salt", getattr(calc_result, "salt_pass", None)),
            ("DST", getattr(calc_result, "dst_pass", None)),
        ):
            if passed is not None:
                lines.append(f"- {label}: **{'Pass' if passed else 'FAIL'}**")
        for w in getattr(calc_result, "cross_check_warnings", []) or []:
            lines.append(f"- Cross-check: {w}")
        lines.append("")
    if compliance.required_missing:
        lines.append("## Required — missing")
        for ir in compliance.required_missing:
            lines.append(f"- [ ] **{ir.section}** {ir.label} — {ir.detail}")
        lines.append("")
    if compliance.recommended_missing:
        lines.append("## Recommended — review")
        for ir in compliance.recommended_missing[:20]:
            lines.append(f"- [ ] **{ir.section}** {ir.label} — {ir.detail}")
        lines.append("")
    if compliance.phase2_reasons:
        lines.append("## Phase II triggers")
        for r in compliance.phase2_reasons:
            lines.append(f"- {r}")
        lines.append("")
    lines.extend(["## Regulatory notes", ""])
    for note in data.get("regulatory_notes", []):
        lines.append(f"- {note}")
    lines.extend(
        [
            "",
            "## Reference",
            "- [AER Directive 050](https://www.aer.ca/regulations-and-compliance-enforcement/rules-and-regulations/directives/directive-050)",
            "- [Reclamation certificate submissions](https://www.aer.ca/node/124)",
            "- [Assessing DWDA (Open Government)](https://open.alberta.ca/publications/0778539806)",
            "",
            "_Generated by ESA Report Generator. QP must verify before OneStop submission._",
        ]
    )
    return "\n".join(lines)
