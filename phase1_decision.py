"""
Phase 2 ESA trigger heuristics aligned with AER SED 002 (insufficient information → Phase 2).
"""

from __future__ import annotations

from typing import Any


def _yes(val: Any) -> bool:
    s = str(val or "").strip().lower()
    return s in ("yes", "y", "true", "1", "required", "likely")


def _no(val: Any) -> bool:
    s = str(val or "").strip().lower()
    return s in ("no", "n", "false", "0", "not required", "unlikely")


def evaluate_phase2_triggers(
    context: dict[str, Any],
    meta: dict[str, str] | None = None,
) -> list[str]:
    """Return human-readable Phase 2 trigger warnings (non-blocking)."""
    meta = meta or {}
    warnings: list[str] = []

    phase2 = str(
        context.get("phase2_esa_required") or meta.get("phase2_esa_required") or ""
    ).strip()
    if _yes(phase2):
        warnings.append(
            "ProjectData indicates Phase II ESA is required — confirm scope before reclamation application."
        )

    site_visit = str(context.get("site_visit_completed") or "").strip().lower()
    if site_visit in ("no", "false", "0", "not completed", "deferred"):
        if _yes(context.get("investigations_recommended")) or "investigat" in str(
            context.get("conclusions_recommendations", "")
        ).lower():
            warnings.append(
                "Site visit not completed but conclusions recommend investigation — "
                "SED 002 may require site visit or Phase 2 for adequate assessment."
            )

    if _yes(context.get("phase2_drilling_waste_required")):
        warnings.append(
            "Drilling waste assessment may require Phase 2 ESA per compliance option checklist."
        )

    spills = str(context.get("spills_releases") or "").strip().lower()
    if spills and spills not in ("no", "none", "n/a", "not observed"):
        warnings.append(
            f"Spills/releases noted ({context.get('spills_releases')}) — verify Phase 2 need."
        )

    flare = str(context.get("flare_pit_used") or "").strip().lower()
    if flare in ("yes", "used", "y"):
        warnings.append(
            "Flare pit used — confirmatory sampling may be required (SED 002 §10.5.2)."
        )

    waste_rows = context.get("drilling_waste") or []
    if isinstance(waste_rows, list):
        for row in waste_rows:
            if not isinstance(row, dict):
                continue
            disp = str(row.get("disposal_type") or "").lower()
            if "unknown" in disp or not str(row.get("location") or "").strip():
                warnings.append(
                    "Drilling waste row has unknown disposal type or location — "
                    "exhaust reasonable avenues per SED 002 §10.4."
                )
                break

    auto = str(context.get("phase2_recommended") or "").strip()
    if _yes(auto):
        for reason in context.get("phase2_reasons") or []:
            if reason:
                warnings.append(f"Rule: {reason}")

    return warnings


def enrich_context_phase2_decision(context: dict[str, Any]) -> dict[str, Any]:
    """Add phase2_recommended and phase2_reasons[] to render context."""
    reasons: list[str] = []
    recommended = False

    if _yes(context.get("phase2_esa_required")):
        recommended = True
        reasons.append("phase2_esa_required is Yes in ProjectData")

    site_visit = str(context.get("site_visit_completed") or "").strip().lower()
    if site_visit in ("no", "false", "0", "not completed"):
        inv = str(context.get("investigations_recommended") or "").strip()
        if inv:
            recommended = True
            reasons.append("Site visit not completed with investigations recommended")

    if _yes(context.get("phase2_drilling_waste_required")):
        recommended = True
        reasons.append("Phase 2 indicated for drilling waste")

    out = dict(context)
    out["phase2_recommended"] = "Yes" if recommended else "No"
    out["phase2_reasons"] = reasons
    return out
