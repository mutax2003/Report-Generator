"""
Phase 2 ESA trigger heuristics aligned with AER SED 002 (insufficient information → Phase 2).
"""

from __future__ import annotations

from typing import Any

from compliance_helpers import yes_value as _yes


def evaluate_phase2_triggers(
    context: dict[str, Any],
    meta: dict[str, str] | None = None,
) -> list[str]:
    """Return human-readable Phase 2 trigger warnings (non-blocking, SED-formatted)."""
    from phase2_triggers import collect_phase2_reasons

    meta = meta or {}
    _, reasons = collect_phase2_reasons(context, meta)
    reason_text = " ".join(reasons).lower()
    warnings: list[str] = []

    if _yes(context.get("phase2_esa_required") or meta.get("phase2_esa_required")) or (
        "phase ii" in reason_text
    ):
        warnings.append(
            "ProjectData indicates Phase II ESA is required — confirm scope before reclamation application."
        )

    site_visit = str(context.get("site_visit_completed") or "").strip().lower()
    if site_visit in ("no", "false", "0", "not completed", "deferred"):
        if _yes(context.get("investigations_recommended")) or "investigat" in str(
            context.get("conclusions_recommendations", "")
        ).lower() or "site visit" in reason_text:
            warnings.append(
                "Site visit not completed but conclusions recommend investigation — "
                "SED 002 may require site visit or Phase 2 for adequate assessment."
            )

    if _yes(context.get("phase2_drilling_waste_required")) or "drilling waste" in reason_text:
        warnings.append(
            "Drilling waste assessment may require Phase 2 ESA per compliance option checklist."
        )

    spills = str(context.get("spills_releases") or "").strip().lower()
    if (spills and spills not in ("no", "none", "n/a", "not observed")) or "spills" in reason_text:
        warnings.append(
            f"Spills/releases noted ({context.get('spills_releases') or 'see records'}) — verify Phase 2 need."
        )

    flare = str(context.get("flare_pit_used") or "").strip().lower()
    if flare in ("yes", "used", "y") or "flare pit" in reason_text:
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
    elif "unknown disposal" in reason_text or "disposal type or location" in reason_text:
        warnings.append(
            "Drilling waste row has unknown disposal type or location — "
            "exhaust reasonable avenues per SED 002 §10.4."
        )

    return list(dict.fromkeys(warnings))


def enrich_context_phase2_decision(context: dict[str, Any]) -> dict[str, Any]:
    """Add phase2_recommended and phase2_reasons[] to render context."""
    from phase2_triggers import collect_phase2_reasons

    likely, reasons = collect_phase2_reasons(context)
    context["phase2_recommended"] = "Yes" if likely else "No"
    context["phase2_reasons"] = reasons
    return context


def enrich_phase1_alberta_context(
    context: dict[str, Any],
    meta: dict[str, str] | None,
    *,
    appendix_labels_present: set[str] | frozenset[str] | None,
    report_type: str,
) -> dict[str, Any]:
    """Phase II hints, DWDA enrichment, and SED 002 evaluation for Phase I render."""
    from dwda_compliance import enrich_dwda_context, resolve_dwda_appendix_labels
    from sed002_compliance import PHASE1_SED_PROFILES, evaluate_sed002_compliance

    ctx = enrich_context_phase2_decision(context)
    labels = resolve_dwda_appendix_labels(
        ctx,
        meta,
        extra_labels=appendix_labels_present,
        report_type=report_type,
    )
    label_set = set(labels)
    ctx = enrich_dwda_context(ctx, meta, appendix_labels_present=label_set)
    if report_type in PHASE1_SED_PROFILES:
        sed = evaluate_sed002_compliance(
            ctx,
            meta,
            report_type=report_type,
            appendix_labels_present=label_set,
        )
        if sed is not None:
            ctx["_sed002_compliance"] = sed
    return ctx