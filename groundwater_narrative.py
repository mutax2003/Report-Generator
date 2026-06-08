"""
Groundwater monitoring report helpers — summary stats and optional executive summary.

Ecoventure Inc. voice; used when narrative_profile is groundwater_monitoring.
"""

from __future__ import annotations

from typing import Any

ECOVENTURE_CONSULTANT = "Ecoventure Inc."


def _norm_well_id(value: Any) -> str:
    from ai.well_log_extract import normalize_well_id

    raw = _s(value)
    return normalize_well_id(raw) if raw else ""


def _s(value: Any) -> str:
    if value is None:
        return ""
    t = str(value).strip()
    if t.lower() in ("nan", "none"):
        return ""
    return t


def _as_list(ctx: dict[str, Any], key: str) -> list[dict[str, Any]]:
    raw = ctx.get(key)
    if not isinstance(raw, list):
        return []
    return [r for r in raw if isinstance(r, dict)]


def enrich_groundwater_context(ctx: dict[str, Any]) -> None:
    """Add computed scalar fields for templates (well counts, exceedances)."""
    wells = _as_list(ctx, "monitoring_wells")
    levels = _as_list(ctx, "water_levels")
    gw_lab = _as_list(ctx, "groundwater_results") or _as_list(ctx, "lab_results")

    ctx["well_count"] = str(len(wells))
    event_dates = {_s(r.get("sample_date") or r.get("event_date")) for r in gw_lab}
    event_dates.discard("")
    ctx["monitoring_event_count"] = str(len(event_dates) or len(levels))

    exc_params: list[str] = []
    for row in gw_lab:
        flag = _s(row.get("exceedance_flag")).upper()
        if flag in ("Y", "YES"):
            analyte = _s(row.get("analyte"))
            if analyte:
                exc_params.append(analyte)
    unique_exc = sorted(set(exc_params))
    if unique_exc:
        ctx["exceedance_summary"] = (
            f"{len(unique_exc)} parameter(s) exceeded applicable guidelines: "
            + ", ".join(unique_exc[:8])
            + ("..." if len(unique_exc) > 8 else "")
        )
    else:
        ctx["exceedance_summary"] = (
            "No groundwater analytical results exceeded applicable screening guidelines "
            "for the parameters evaluated."
        )

    well_ids = {_norm_well_id(r.get("well_id")) for r in wells if _norm_well_id(r.get("well_id"))}
    level_ids = {_norm_well_id(r.get("well_id")) for r in levels if _norm_well_id(r.get("well_id"))}
    missing_levels = well_ids - level_ids
    if missing_levels and well_ids:
        ctx["data_gap_note"] = (
            f"Water level measurements were not available for: "
            f"{', '.join(sorted(missing_levels)[:6])}."
        )
    else:
        ctx["data_gap_note"] = ""

    try:
        from ai.gw_trends import analyze_groundwater_trends

        trend_notes, _audit = analyze_groundwater_trends(ctx, use_llm=False)
        if trend_notes:
            ctx["gw_trend_summary"] = " ".join(n.message for n in trend_notes[:5])
        else:
            ctx["gw_trend_summary"] = ""
    except Exception:
        ctx["gw_trend_summary"] = ""


def build_groundwater_executive_summary(ctx: dict[str, Any]) -> str:
    """Draft executive summary when ProjectData executive_summary is empty."""
    consultant = _s(ctx.get("consultant_name")) or ECOVENTURE_CONSULTANT
    client = _s(ctx.get("client_name")) or "the client"
    site = _s(ctx.get("site_name")) or "the subject site"
    program = _s(ctx.get("monitoring_program")) or "groundwater monitoring program"
    well_count = _s(ctx.get("well_count")) or "0"
    event_count = _s(ctx.get("monitoring_event_count")) or "0"
    exc = _s(ctx.get("exceedance_summary"))
    gap = _s(ctx.get("data_gap_note"))

    parts = [
        f"{consultant} prepared this report for {client} to summarize results of the "
        f"{program} at {site}.",
        f"The monitoring network comprises {well_count} monitoring well(s) "
        f"with {event_count} sampling event(s) represented in the attached tables.",
    ]
    if exc:
        parts.append(exc + ".")
    if gap:
        parts.append(gap)
    intro = _s(ctx.get("gw_program_intro"))
    if intro:
        parts.insert(1, intro)
    trends = _s(ctx.get("gw_trend_summary"))
    if trends:
        parts.append(trends)
    return "\n\n".join(parts)
