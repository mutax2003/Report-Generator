"""Plain-language notes for lab exceedances."""

from __future__ import annotations

from typing import Any

from ai.client import complete_json, prompt_version
from ai.config import openai_model
from ai.models import AiAudit, ExceedanceNote


def _rule_note(row: dict[str, Any]) -> ExceedanceNote:
    analyte = str(row.get("analyte", "Analyte"))
    result = row.get("result") or row.get("result_plain", "")
    criteria = row.get("criteria", "")
    unit = row.get("unit", "")
    flag = str(row.get("exceedance_flag", "")).upper()
    if flag not in ("Y", "YES"):
        return ExceedanceNote(
            analyte=analyte,
            note=f"{analyte}: {result} {unit} — within screening level ({criteria} {unit}).".strip(),
            confidence=0.9,
            source="rule",
        )
    return ExceedanceNote(
        analyte=analyte,
        note=(
            f"{analyte} result {result} {unit} exceeds screening level {criteria} {unit}. "
            "Confirm units and applicable standards; consider additional assessment if required."
        ).strip(),
        confidence=0.9,
        source="rule",
    )


def notes_for_lab_rows(
    lab_results: list[dict[str, Any]],
    *,
    site_name: str = "",
    use_llm: bool = True,
    max_rows: int = 50,
) -> tuple[list[ExceedanceNote], AiAudit]:
    audit = AiAudit(features=["exceedance_notes"], prompt_version=prompt_version())
    rows = [r for r in lab_results if isinstance(r, dict)][:max_rows]
    exc_rows = [
        r
        for r in rows
        if str(r.get("exceedance_flag", "")).upper() in ("Y", "YES")
    ]

    if use_llm and exc_rows:
        data = complete_json(
            system=(
                'Return JSON: {"notes": [{"analyte":"","note":"","confidence":0.0-1.0}]}. '
                "One concise sentence per exceedance for ESA reports. No invented regulations."
            ),
            user=str({"site": site_name, "rows": exc_rows[:25]}),
        )
        if data and data.get("notes"):
            audit.used_llm = True
            audit.model = openai_model()
            out = [
                ExceedanceNote(
                    analyte=str(n.get("analyte", "")),
                    note=str(n.get("note", ""))[:600],
                    confidence=float(n.get("confidence", 0.75)),
                    source="llm",
                )
                for n in data["notes"]
                if isinstance(n, dict)
            ]
            if out:
                return out, audit

    notes = [_rule_note(r) for r in rows]
    return notes, audit
