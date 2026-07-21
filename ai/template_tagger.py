"""Suggest Jinja2 tags for untagged production Word templates."""

from __future__ import annotations

import re
from typing import Any

from ai.client import complete_json, prompt_version
from ai.config import openai_model
from ai.docx_extract import extract_docx_full_text
from ai.models import AiAudit, TagSuggestion

# From PRODUCTION_TEMPLATE_GUIDE + common ESA placeholders
_BRACKET_MAP: dict[str, str] = {
    "company": "company",
    "company address": "company_address",
    "keywords": "keywords",
    "lab": "lab_name",
    "client full name": "client_name",
    "client name": "client_name",
}

_PHRASE_MAP: list[tuple[str, str]] = [
    ("Client Full Name", "client_name"),
    ("client full name", "client_name"),
    ("Company Address", "company_address"),
    ("[Company]", "company"),
    ("[Company Address]", "company_address"),
    ("[Keywords]", "keywords"),
    ("[LAB]", "lab_name"),
]

# Alberta Phase I ESA (Ecoventure) — common cover / narrative phrases
_PHASE1_PHRASE_MAP: list[tuple[str, str]] = [
    ("Ecoventure Inc.", "company"),
    ("Ecoventure Inc. (Ecoventure)", "consultant_name"),
    ("Phase 1 Environmental Site Assessment", "report_title"),
    ("Phase I Environmental Site Assessment", "report_title"),
]


def _allowed_keys(report_type: str | None = None) -> set[str]:
    from report_profile import get_recommended_fields

    rt = (report_type or "phase1_alberta").strip()
    keys = set(get_recommended_fields(rt))
    keys.update(
        {
            "prepared_by",
            "date_of_issue",
            "report_phase",
            "template_version",
            "executive_summary",
            "drilling_waste_intro",
            "site_recon_intro",
            "phase2_recommendation",
        }
    )
    return keys


def _rule_suggestions(text: str, *, report_type: str | None = None) -> list[TagSuggestion]:
    found: list[TagSuggestion] = []
    seen: set[str] = set()

    phrase_maps = list(_PHRASE_MAP)
    if report_type == "phase1_alberta":
        phrase_maps = _PHASE1_PHRASE_MAP + phrase_maps

    for m in re.finditer(r"\[([^\]]{1,80})\]", text):
        inner = m.group(1).strip()
        key = _BRACKET_MAP.get(inner.lower(), _norm_bracket_key(inner))
        tag = f"{{{{ {key} }}}}"
        orig = m.group(0)
        if orig not in seen:
            seen.add(orig)
            found.append(
                TagSuggestion(
                    original_text=orig,
                    jinja_tag=tag,
                    confidence=0.95 if inner.lower() in _BRACKET_MAP else 0.7,
                    source="rule",
                    notes="Replace bracket placeholder in Word with this tag (single run).",
                )
            )

    for phrase, key in phrase_maps:
        if phrase in text and phrase not in seen:
            seen.add(phrase)
            found.append(
                TagSuggestion(
                    original_text=phrase,
                    jinja_tag=f"{{{{ {key} }}}}",
                    confidence=0.85,
                    source="rule",
                    notes="Replace static phrase with Jinja tag.",
                )
            )

    # Existing jinja tags
    for m in re.finditer(r"\{\{\s*([A-Za-z_]\w*)\s*\}\}", text):
        key = m.group(1)
        if key not in seen:
            seen.add(key)
            found.append(
                TagSuggestion(
                    original_text=m.group(0),
                    jinja_tag=m.group(0),
                    confidence=1.0,
                    source="rule",
                    notes="Already tagged.",
                )
            )

    return found


def _norm_bracket_key(inner: str) -> str:
    s = re.sub(r"[^\w\s]", "", inner.strip().lower())
    return re.sub(r"\s+", "_", s)


def _llm_suggestions(
    text: str, allowed: set[str], *, system_extra: str = ""
) -> list[TagSuggestion]:
    payload = complete_json(
        system=(
            "You are an expert in docxtpl Word templates for environmental reports. "
            "Return JSON only: {\"suggestions\": [{\"original_text\": \"...\", "
            "\"jinja_key\": \"snake_case\", \"confidence\": 0.0-1.0, \"notes\": \"...\"}]}. "
            f"Only use jinja_key from this allowlist: {sorted(allowed)}."
            + system_extra
        ),
        user=f"Document excerpt:\n\n{text[:24_000]}",
    )
    if not payload or "suggestions" not in payload:
        return []
    out: list[TagSuggestion] = []
    for item in payload.get("suggestions", [])[:40]:
        if not isinstance(item, dict):
            continue
        key = str(item.get("jinja_key", "")).strip()
        if key not in allowed:
            continue
        out.append(
            TagSuggestion(
                original_text=str(item.get("original_text", ""))[:200],
                jinja_tag=f"{{{{ {key} }}}}",
                confidence=float(item.get("confidence", 0.6)),
                source="llm",
                notes=str(item.get("notes", ""))[:500],
            )
        )
    return out


def suggest_template_tags(
    template_bytes: bytes,
    *,
    use_llm: bool = True,
    report_type: str | None = None,
) -> tuple[list[TagSuggestion], AiAudit]:
    text = extract_docx_full_text(template_bytes)
    rt = (report_type or "phase1_alberta").strip() or "phase1_alberta"
    allowed = _allowed_keys(rt)
    suggestions = _rule_suggestions(text, report_type=rt)
    features = ["template_tagger", f"profile:{rt}"]
    if rt == "phase1_alberta":
        features.append("phase1_alberta")
    audit = AiAudit(
        features=features,
        prompt_version=prompt_version(),
    )

    existing_keys = {s.jinja_tag for s in suggestions if s.confidence >= 1.0}
    if use_llm:
        system_extra = ""
        if rt == "phase1_alberta":
            system_extra = (
                " This is an Alberta O&G Phase I ESA (AER Schedule Two style). "
                "Prioritize cover fields, executive_summary, conclusions_recommendations, "
                "well_name, uwi, drilling_waste_summary."
            )
        elif rt == "groundwater_monitoring":
            system_extra = (
                " This is a groundwater monitoring report. "
                "Prioritize well IDs, sampling dates, and trend narrative fields."
            )
        llm_rows = _llm_suggestions(text, allowed, system_extra=system_extra)
        audit.used_llm = bool(llm_rows)
        if llm_rows:
            audit.model = openai_model()
        for row in llm_rows:
            if row.jinja_tag not in existing_keys:
                suggestions.append(row)

    for s in suggestions:
        m = re.search(r"\{\{\s*(\w+)\s*\}\}", s.jinja_tag)
        if m and m.group(1) not in allowed:
            s.notes = (
                s.notes + " Warning: not in profile recommended_fields."
            ).strip()

    return suggestions, audit


def suggestions_to_markdown(suggestions: list[TagSuggestion]) -> str:
    lines = [
        "# Template tagging suggestions",
        "",
        "| Find in Word | Replace with | Confidence | Source | Notes |",
        "|--------------|--------------|------------|--------|-------|",
    ]
    for s in suggestions:
        lines.append(
            f"| {s.original_text} | `{s.jinja_tag}` | {s.confidence:.0%} | {s.source} | {s.notes} |"
        )
    lines.extend(
        [
            "",
            "## Table loop (lab results)",
            "",
            "Add a table with header row, then:",
            "- `{%tr for item in lab_results %}`",
            "- `{{ item.analyte }}`, `{{ item.result_display }}`, `{{ item.unit }}`, `{{ item.exceedance_flag }}`",
            "- `{%tr endfor %}`",
            "",
        ]
    )
    return "\n".join(lines)
