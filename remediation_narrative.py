"""
Phase III / remediation report narrative helpers (Ecoventure).
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


def _as_list(ctx: dict[str, Any], key: str) -> list[dict[str, Any]]:
    raw = ctx.get(key)
    if not isinstance(raw, list):
        return []
    return [r for r in raw if isinstance(r, dict)]


def enrich_remediation_context(ctx: dict[str, Any]) -> None:
    """Computed scalars for remediation templates."""
    objectives = _as_list(ctx, "remediation_objectives")
    treatments = _as_list(ctx, "treatment_events")
    confirmatory = _as_list(ctx, "confirmatory_sampling")
    ctx["objective_count"] = str(len(objectives))
    ctx["treatment_event_count"] = str(len(treatments))
    ctx["confirmatory_sample_count"] = str(len(confirmatory))

    exc = 0
    for row in confirmatory:
        flag = _s(row.get("exceedance_flag")).upper()
        if flag in ("Y", "YES"):
            exc += 1
    ctx["confirmatory_exceedance_count"] = str(exc)
    if confirmatory and exc == 0:
        ctx["confirmatory_status"] = "All confirmatory results within objectives"
    elif exc:
        ctx["confirmatory_status"] = (
            f"{exc} confirmatory result(s) exceeded remedial objectives"
        )
    else:
        ctx["confirmatory_status"] = ""


def build_remediation_executive_summary(ctx: dict[str, Any]) -> str:
    """Draft remediation executive summary when empty."""
    enrich_remediation_context(ctx)
    consultant = _s(ctx.get("consultant_name")) or ECOVENTURE_CONSULTANT
    client = _s(ctx.get("client_name")) or "the client"
    site = _s(ctx.get("site_name")) or "the subject site"
    rap = _s(ctx.get("rap_status"))
    status_phrase = _s(ctx.get("remediation_status"))

    parts = [
        f"{consultant} prepared this remediation summary report for {client} at {site}.",
    ]
    if status_phrase:
        parts.append(status_phrase)
    else:
        parts.append("This report documents remediation activities and confirmatory sampling.")
    if rap:
        parts.append(f"Remedial action plan status: {rap}.")
    conf = _s(ctx.get("confirmatory_status"))
    if conf:
        parts.append(conf + ".")
    conclusions = _s(ctx.get("conclusions_recommendations"))
    if conclusions:
        parts.append(conclusions)
    return "\n\n".join(parts)
