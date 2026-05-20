"""Pre-flight copilot: explain issues and suggest Excel fixes."""

from __future__ import annotations

import json
from typing import Any

from ai.client import complete_text, prompt_version
from ai.config import openai_model
from ai.models import AiAudit, CopilotAdvice
from template_tools import PreflightResult


def _rule_advice(preflight: PreflightResult, meta: dict[str, str]) -> CopilotAdvice:
    steps: list[str] = []
    cols: list[str] = []

    if preflight.errors:
        steps.append("Fix **errors** first — generation is blocked until these are resolved.")
        for e in preflight.errors:
            if "ProjectData" in e:
                steps.append(
                    "Add a sheet named `ProjectData` with headers in row 1 and values in row 2."
                )
            if "LabResults" in e:
                steps.append(
                    "Add sheet `LabResults` or select **Phase 1** in the sidebar if no lab data."
                )

    cov = preflight.coverage
    if cov and cov.missing_in_data:
        cols = list(cov.missing_in_data)
        steps.append(
            f"Add {len(cols)} column(s) to **ProjectData** row 1 (headers must match template tags)."
        )
        steps.append("Download the missing-fields checklist from pre-flight for copy-paste names.")

    if preflight.split_tag_issues:
        steps.append(
            "Re-type each broken `{{ tag }}` in Word as plain text in one formatting run."
        )

    phase = meta.get("report_phase", "Phase 2")
    summary = (
        f"Pre-flight for **{phase}**: "
        f"{len(preflight.errors)} error(s), {len(preflight.warnings)} warning(s)."
    )
    if cov:
        summary += (
            f" {len(cov.matched)} tag(s) matched, {len(cov.missing_in_data)} missing."
        )

    return CopilotAdvice(
        summary=summary,
        steps=steps or ["Uploads look ready — run dry-run preview, then generate."],
        excel_columns_to_add=cols,
        source="rule",
    )


def explain_preflight(
    preflight: PreflightResult,
    meta: dict[str, str],
    *,
    use_llm: bool = True,
) -> tuple[CopilotAdvice, AiAudit]:
    audit = AiAudit(features=["preflight_copilot"], prompt_version=prompt_version())
    base = _rule_advice(preflight, meta)

    if not use_llm:
        return base, audit

    payload = {
        "errors": preflight.errors,
        "warnings": preflight.warnings[:20],
        "split_tags": preflight.split_tag_issues[:10],
        "missing_vars": (
            list(preflight.coverage.missing_in_data) if preflight.coverage else []
        ),
        "phase": meta.get("report_phase"),
    }
    llm = complete_text(
        system=(
            "You help environmental consultants fix Excel/Word merge issues. "
            "Return markdown: brief summary, numbered steps, and a bullet list of Excel columns to add."
        ),
        user=json.dumps(payload, default=str),
    )
    if llm:
        audit.used_llm = True
        audit.model = openai_model()
        steps = [s.strip() for s in llm.split("\n") if s.strip()][:15]
        return CopilotAdvice(
            summary=base.summary,
            steps=steps,
            excel_columns_to_add=base.excel_columns_to_add,
            source="llm",
        ), audit

    return base, audit
