"""Draft narrative sections from project context + RAG snippets."""

from __future__ import annotations

import json
from typing import Any

from ai.client import complete_text, prompt_version
from ai.config import openai_model
from ai.models import AiAudit, NarrativeDraft
from ai.rag import retrieve

DEFAULT_SECTIONS = [
    "executive_summary",
    "site_description",
    "conclusions_limitations",
]


def _rule_section(section: str, context: dict[str, Any]) -> str:
    site = context.get("site_name") or context.get("site_address") or "the subject site"
    client = context.get("client_name") or "the client"
    phase = context.get("report_phase") or "Phase 2"
    lab = context.get("lab_results") or []
    exc = sum(
        1
        for r in lab
        if isinstance(r, dict)
        and str(r.get("exceedance_flag", "")).upper() in ("Y", "YES")
    )

    if section == "executive_summary":
        return (
            f"This {phase} Environmental Site Assessment was prepared for {client} "
            f"regarding {site}. Laboratory results comprised {len(lab)} analyte(s); "
            f"{exc} exceedance(s) were identified where applicable screening levels apply. "
            "Detailed findings are presented in the body of the report."
        )
    if section == "site_description":
        addr = context.get("site_address") or context.get("address") or ""
        return (
            f"The subject property ({site}) is located at {addr or '[address from field data]'}. "
            "Site conditions were assessed in accordance with applicable guidance."
        )
    return (
        "Conclusions and limitations should be confirmed by the qualified person. "
        "This draft is based on structured field data only and does not replace "
        "professional judgment or regulatory review."
    )


def draft_narratives(
    context: dict[str, Any],
    *,
    sections: list[str] | None = None,
    use_llm: bool = True,
) -> tuple[list[NarrativeDraft], AiAudit]:
    sections = sections or DEFAULT_SECTIONS
    audit = AiAudit(features=["narrative_draft"], prompt_version=prompt_version())
    drafts: list[NarrativeDraft] = []

    query_parts = [
        str(context.get("site_name", "")),
        str(context.get("report_phase", "")),
        "environmental site assessment",
    ]
    rag_hits = retrieve(" ".join(query_parts))
    rag_context = "\n\n".join(f"[{src}]\n{chunk}" for src, chunk, _ in rag_hits)

    for section in sections:
        if use_llm:
            llm_text = complete_text(
                system=(
                    "You draft professional ESA report prose for Canadian consulting firms. "
                    "Use only facts from the JSON context and reference snippets. "
                    "Do not invent regulatory citations or sample results. "
                    "Mark uncertainty. 2-4 short paragraphs max."
                ),
                user=json.dumps(
                    {
                        "section": section,
                        "context": {
                            k: v
                            for k, v in context.items()
                            if k != "lab_results"
                        },
                        "lab_summary": {
                            "row_count": len(context.get("lab_results") or []),
                            "exceedances": sum(
                                1
                                for r in (context.get("lab_results") or [])
                                if isinstance(r, dict)
                                and str(r.get("exceedance_flag", "")).upper()
                                in ("Y", "YES")
                            ),
                        },
                        "reference_snippets": rag_context[:8000],
                    },
                    default=str,
                )[:20_000],
            )
            if llm_text:
                audit.used_llm = True
                audit.model = openai_model()
                drafts.append(
                    NarrativeDraft(
                        section=section,
                        text=llm_text,
                        sources=[s for s, _, _ in rag_hits],
                    )
                )
                continue

        drafts.append(
            NarrativeDraft(
                section=section,
                text=_rule_section(section, context),
                sources=[s for s, _, _ in rag_hits] if rag_hits else [],
            )
        )

    return drafts, audit
