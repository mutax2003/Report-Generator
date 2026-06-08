"""
Phase II ESA executive summary and context enrichment (Ecoventure).
"""

from __future__ import annotations

from typing import Any

ECOVENTURE_CONSULTANT = "Ecoventure Inc."


def _s(value: Any) -> str:
    if value is None:
        return ""
    t = str(value).strip()
    if t.lower() in ("nan", "none"):
        return ""
    return t


def _as_lab(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    raw = ctx.get("lab_results")
    if not isinstance(raw, list):
        return []
    return [r for r in raw if isinstance(r, dict)]


def enrich_phase2_context(ctx: dict[str, Any]) -> None:
    """Add exceedance stats and sample counts for Phase II templates."""
    rows = _as_lab(ctx)
    ctx["lab_row_count"] = str(len(rows))
    exc: list[str] = []
    matrices: set[str] = set()
    locations: set[str] = set()
    for row in rows:
        flag = _s(row.get("exceedance_flag")).upper()
        if flag in ("Y", "YES"):
            analyte = _s(row.get("analyte"))
            if analyte:
                exc.append(analyte)
        matrix = _s(row.get("matrix"))
        if matrix:
            matrices.add(matrix)
        loc = _s(row.get("location") or row.get("sample_id"))
        if loc:
            locations.add(loc)
    unique_exc = sorted(set(exc))
    ctx["exceedance_count"] = str(len(unique_exc))
    if unique_exc:
        ctx["exceedance_summary"] = (
            f"{len(unique_exc)} parameter(s) exceeded applicable criteria: "
            + ", ".join(unique_exc[:10])
            + ("..." if len(unique_exc) > 10 else "")
        )
    else:
        ctx["exceedance_summary"] = (
            "No analytical results exceeded applicable screening criteria "
            "for the parameters evaluated."
        )
    ctx["matrices_sampled"] = ", ".join(sorted(matrices)) if matrices else ""
    ctx["sample_location_count"] = str(len(locations) or len(rows))


def build_phase2_executive_summary(ctx: dict[str, Any]) -> str:
    """Draft Phase II executive summary when ProjectData field is empty."""
    enrich_phase2_context(ctx)
    consultant = _s(ctx.get("consultant_name")) or ECOVENTURE_CONSULTANT
    client = _s(ctx.get("client_name")) or "the client"
    site = _s(ctx.get("site_name")) or _s(ctx.get("site_address")) or "the subject site"
    program = _s(ctx.get("investigation_scope")) or "Phase II Environmental Site Assessment"
    lab_count = _s(ctx.get("lab_row_count")) or "0"
    exc = _s(ctx.get("exceedance_summary"))
    matrices = _s(ctx.get("matrices_sampled"))

    parts = [
        f"{consultant} prepared this {program} report for {client} at {site}.",
        f"Laboratory analytical results for {lab_count} sample result row(s) are "
        f"summarized in the tables below.",
    ]
    if matrices:
        parts.append(f"Sample matrices evaluated include: {matrices}.")
    if exc:
        parts.append(exc + ".")
    conclusions = _s(ctx.get("conclusions_recommendations"))
    if conclusions:
        parts.append(conclusions)
    return "\n\n".join(parts)
