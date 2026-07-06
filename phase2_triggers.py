"""
Unified Phase II trigger collection for SED 002, DWDA, OneStop, and narrative context.
"""

from __future__ import annotations

from typing import Any

from compliance_helpers import yes_value


def collect_phase2_reasons(
    context: dict[str, Any],
    meta: dict[str, str] | None = None,
    *,
    dwda_compliance: Any | None = None,
    dwda_calc: Any | None = None,
) -> tuple[bool, list[str]]:
    """Return (phase2_likely, deduplicated human-readable reasons)."""
    meta = meta or {}
    reasons: list[str] = []
    seen: set[str] = set()

    def add(reason: str) -> None:
        key = reason.strip().lower()
        if key and key not in seen:
            seen.add(key)
            reasons.append(reason)

    if yes_value(context.get("phase2_esa_required")) or yes_value(
        meta.get("phase2_esa_required")
    ):
        add("ProjectData indicates Phase II ESA is required")

    site_visit = str(context.get("site_visit_completed") or "").strip().lower()
    if site_visit in ("no", "false", "0", "not completed", "deferred"):
        inv = str(context.get("investigations_recommended") or "").strip()
        if inv or "investigat" in str(context.get("conclusions_recommendations", "")).lower():
            add("Site visit not completed with investigations recommended")

    for key in (
        "phase2_drilling_waste_required",
        "dwda_phase2_required",
        "dwda_calc_phase2_required",
    ):
        if yes_value(context.get(key)) or yes_value(meta.get(key)):
            add(f"{key.replace('_', ' ')} is Yes")
            break

    spills = str(context.get("spills_releases") or "").strip().lower()
    if spills and spills not in ("no", "none", "n/a", "not observed"):
        add(f"Spills/releases noted ({context.get('spills_releases')})")

    flare = str(context.get("flare_pit_used") or "").strip().lower()
    if flare in ("yes", "used", "y"):
        add("Flare pit used — confirmatory sampling may be required")

    waste_rows = context.get("drilling_waste") or []
    if isinstance(waste_rows, list):
        for row in waste_rows:
            if not isinstance(row, dict):
                continue
            disp = str(row.get("disposal_type") or "").lower()
            if "unknown" in disp or not str(row.get("location") or "").strip():
                add("Drilling waste row has unknown disposal type or location")
                break

    if dwda_compliance is not None:
        for reason in getattr(dwda_compliance, "phase2_reasons", []) or []:
            add(str(reason))

    if dwda_calc is not None and getattr(dwda_calc, "phase2_required", False):
        add("DWDA calculations indicate Phase II may be required")

    likely = bool(reasons) or yes_value(context.get("phase2_recommended"))
    return likely, reasons


def is_phase2_likely(
    context: dict[str, Any],
    meta: dict[str, str] | None = None,
) -> bool:
    likely, _ = collect_phase2_reasons(context, meta)
    return likely
