"""
Validate Excel context against the published field contract (warnings only).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CONTRACT_PATH = Path(__file__).resolve().parent / "schemas" / "field_contract.json"
_cached: dict[str, Any] | None = None


def load_field_contract() -> dict[str, Any]:
    global _cached
    if _cached is None:
        with _CONTRACT_PATH.open(encoding="utf-8") as f:
            _cached = json.load(f)
    return _cached


def contract_warnings(
    context: dict[str, Any], *, report_phase: str = "Phase 2"
) -> list[str]:
    """Non-blocking recommendations (pattern from schema-first document systems)."""
    contract = load_field_contract()
    sheets = contract.get("sheets", {})
    project = sheets.get("ProjectData", {})
    recommended = list(project.get("recommended_all_phases", []))
    if report_phase.strip() == "Phase 1":
        recommended.extend(project.get("recommended_phase_1_alberta_og", []))
    else:
        recommended.extend(project.get("recommended_phase_2", []))

    warnings: list[str] = []
    keys = {str(k).lower() for k in context}
    for field_name in recommended:
        if field_name not in keys or not str(context.get(field_name, "")).strip():
            warnings.append(
                f"Recommended field '{field_name}' is empty or missing in ProjectData/sidebar."
            )

    lab = context.get("lab_results")
    if report_phase.strip() != "Phase 1" and isinstance(lab, list) and len(lab) == 0:
        warnings.append(
            "Phase 2 reports should include LabResults rows; table may render empty."
        )
    return warnings
