"""Structured results for AI features."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Severity = Literal["error", "warning", "info"]


@dataclass
class TagSuggestion:
    original_text: str
    jinja_tag: str
    confidence: float
    source: str  # "rule" | "llm"
    notes: str = ""


@dataclass
class LabExtractRow:
    analyte: str
    result: str
    unit: str
    criteria: str
    exceedance: str
    confidence: float = 1.0

    def to_excel_dict(self) -> dict[str, str]:
        return {
            "Analyte": self.analyte,
            "Result": self.result,
            "Unit": self.unit,
            "Criteria": self.criteria,
            "Exceedance": self.exceedance,
        }


@dataclass
class LabExtractResult:
    rows: list[LabExtractRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source: str = "heuristic"
    raw_text_preview: str = ""


@dataclass
class ConsistencyFinding:
    severity: Severity
    code: str
    message: str
    suggestion: str = ""


@dataclass
class ExceedanceNote:
    analyte: str
    note: str
    confidence: float
    source: str = "rule"


@dataclass
class CopilotAdvice:
    summary: str
    steps: list[str] = field(default_factory=list)
    excel_columns_to_add: list[str] = field(default_factory=list)
    source: str = "rule"


@dataclass
class NarrativeDraft:
    section: str
    text: str
    sources: list[str] = field(default_factory=list)
    disclaimer: str = (
        "AI-assisted draft — review and edit before including in a client report."
    )


@dataclass
class ApecExtractRow:
    apec_id: str
    apec_name: str
    location_description: str = ""
    concern_type: str = "other"
    source_of_concern: str = "historical_report"
    evidence_summary: str = ""
    source_document: str = ""
    phase2_recommended: str = "N"
    notes: str = ""
    confidence: float = 0.6

    def to_excel_dict(self) -> dict[str, str]:
        return {
            "apec_id": self.apec_id,
            "apec_name": self.apec_name,
            "location_description": self.location_description,
            "concern_type": self.concern_type,
            "source_of_concern": self.source_of_concern,
            "evidence_summary": self.evidence_summary,
            "source_document": self.source_document,
            "phase2_recommended": self.phase2_recommended,
            "notes": self.notes,
        }


@dataclass
class ApecExtractResult:
    rows: list[ApecExtractRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source: str = "heuristic"
    raw_text_preview: str = ""
    disclaimer: str = (
        "AI-suggested APECs — QP review required before client delivery."
    )


@dataclass
class AiAudit:
    features: list[str] = field(default_factory=list)
    model: str = ""
    prompt_version: str = ""
    used_llm: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "features": self.features,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "used_llm": self.used_llm,
        }
