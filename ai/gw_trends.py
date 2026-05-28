"""Groundwater trend summaries from merge context (rules-based; optional LLM)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ai.client import complete_json, prompt_version
from ai.models import AiAudit


@dataclass
class GwTrendNote:
    well_id: str
    parameter: str
    message: str
    severity: str = "info"


def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip())


def _as_rows(ctx: dict[str, Any], key: str) -> list[dict[str, Any]]:
    raw = ctx.get(key)
    if not isinstance(raw, list):
        return []
    return [r for r in raw if isinstance(r, dict)]


def _float_val(val: Any) -> float | None:
    try:
        return float(re.sub(r"[^\d.\-eE+]", "", str(val)))
    except (TypeError, ValueError):
        return None


def _norm_well_id(raw: Any) -> str:
    from ai.well_log_extract import normalize_well_id

    return normalize_well_id(str(raw or ""))


def _sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        _norm(row.get("sample_date") or row.get("event_date") or row.get("measurement_date")),
        _norm(row.get("well_id")),
    )


def analyze_groundwater_trends(
    context: dict[str, Any],
    *,
    use_llm: bool = False,
) -> tuple[list[GwTrendNote], AiAudit]:
    """Rule-based trends on groundwater_results and water_levels."""
    notes: list[GwTrendNote] = []
    gw = _as_rows(context, "groundwater_results") or _as_rows(context, "lab_results")

    by_key: dict[tuple[str, str], list[tuple[str, float]]] = {}
    for row in sorted(gw, key=_sort_key):
        wid = _norm_well_id(row.get("well_id") or row.get("well"))
        analyte = _norm(row.get("analyte"))
        val = _float_val(row.get("result"))
        if not wid or not analyte or val is None:
            continue
        date = _norm(row.get("sample_date") or row.get("event_date") or "")
        by_key.setdefault((wid, analyte), []).append((date, val))

    for (wid, analyte), dated_vals in by_key.items():
        unique_dates = {d for d, _ in dated_vals if d}
        if len(dated_vals) < 2 or len(unique_dates) < 2:
            continue
        values = [v for _, v in dated_vals]
        first, last = values[0], values[-1]
        if first == 0:
            continue
        pct = ((last - first) / abs(first)) * 100
        if abs(pct) >= 25:
            direction = "increased" if pct > 0 else "decreased"
            notes.append(
                GwTrendNote(
                    well_id=wid,
                    parameter=analyte,
                    message=(
                        f"{analyte} at {wid} {direction} approximately "
                        f"{abs(pct):.0f}% from first to last reported value."
                    ),
                    severity="warning" if pct > 0 and "chloride" in analyte.lower() else "info",
                )
            )

    well_ids_wells = {
        _norm_well_id(r.get("well_id"))
        for r in _as_rows(context, "monitoring_wells")
        if _norm_well_id(r.get("well_id"))
    }
    well_ids_lab = {
        _norm_well_id(r.get("well_id"))
        for r in gw
        if _norm_well_id(r.get("well_id"))
    }
    orphan = well_ids_lab - well_ids_wells
    if orphan and well_ids_wells:
        notes.append(
            GwTrendNote(
                well_id=", ".join(sorted(orphan)[:5]),
                parameter="(well ID)",
                message="Lab results include well IDs not listed on MonitoringWells sheet.",
                severity="warning",
            )
        )

    audit = AiAudit(
        features=["gw_trends"],
        used_llm=False,
        prompt_version=prompt_version(),
    )

    if use_llm and notes:
        data = complete_json(
            system='Return JSON: {"summary": "one paragraph"} summarizing GW trends.',
            user="\n".join(n.message for n in notes[:15])[:8000],
        )
        if data and data.get("summary"):
            notes.insert(
                0,
                GwTrendNote(
                    well_id="(summary)",
                    parameter="",
                    message=str(data["summary"]),
                    severity="info",
                ),
            )
            audit.used_llm = True

    return notes, audit
