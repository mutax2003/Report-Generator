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

PHASE1_SECTIONS = [
    "executive_summary",
    "drilling_waste",
    "site_reconnaissance",
    "conclusions_recommendations",
]


GW_SECTIONS = [
    "executive_summary",
    "hydrogeologic_setting",
    "conclusions_recommendations",
]


def sections_for_phase(report_phase: str, report_type: str = "") -> list[str]:
    if report_type == "groundwater_monitoring":
        return list(GW_SECTIONS)
    if str(report_phase).strip() == "Phase 1":
        return list(PHASE1_SECTIONS)
    return list(DEFAULT_SECTIONS)


def _rule_section(section: str, context: dict[str, Any]) -> str:
    site = (
        context.get("well_name")
        or context.get("site_name")
        or context.get("site_address")
        or "the subject site"
    )
    client = context.get("client_name") or "the client"
    consultant = context.get("consultant_name") or "Ecoventure Inc."
    phase = context.get("report_phase") or "Phase 2"
    uwi = context.get("uwi") or ""
    lab = context.get("lab_results") or []
    exc = sum(
        1
        for r in lab
        if isinstance(r, dict)
        and str(r.get("exceedance_flag", "")).upper() in ("Y", "YES")
    )

    if section == "executive_summary":
        existing = str(context.get("executive_summary", "")).strip()
        if existing:
            return existing
        if str(context.get("_report_type", "")) == "groundwater_monitoring":
            from groundwater_narrative import (
                build_groundwater_executive_summary,
                enrich_groundwater_context,
            )

            ctx_copy = dict(context)
            enrich_groundwater_context(ctx_copy)
            return build_groundwater_executive_summary(ctx_copy)
        if phase == "Phase 1":
            from phase1_narrative import build_phase1_executive_summary

            return build_phase1_executive_summary(context)
        return (
            f"This {phase} Environmental Site Assessment was prepared by {consultant} "
            f"for {client} regarding {site}. Laboratory results comprised {len(lab)} "
            f"analyte(s); {exc} exceedance(s) were identified where applicable screening "
            "levels apply. Detailed findings are presented in the body of the report."
        )
    if section == "drilling_waste":
        summary = context.get("drilling_waste_summary") or ""
        option = context.get("aer_waste_compliance_option") or "AER compliance option"
        return (
            f"Drilling waste was managed under {option}. {summary or '[Add drilling_waste_summary in Excel]'}"
        )
    if section == "site_reconnaissance":
        visit = context.get("site_visit_completed") or "unknown"
        infra = context.get("infrastructure_summary") or ""
        return (
            f"Site visit completed: {visit}. "
            f"{infra or 'Infrastructure details from file review and site reconnaissance as applicable.'}"
        )
    if section == "site_description":
        addr = context.get("site_address") or context.get("address") or ""
        return (
            f"The subject property ({site}) is located at {addr or '[address from field data]'}. "
            "Site conditions were assessed in accordance with applicable Alberta guidance."
        )
    if section == "hydrogeologic_setting":
        existing = str(context.get("hydrogeologic_setting", "")).strip()
        if existing:
            return existing
        program = context.get("monitoring_program") or "groundwater monitoring"
        return (
            f"The subject area ({site}) was assessed in the context of a {program}. "
            "Hydrostratigraphic units and local groundwater flow are described based on "
            "available borehole logs, monitoring well construction, and regional mapping. "
            "[Complete with site-specific geology from field files.]"
        )
    if section == "conclusions_recommendations":
        existing = str(context.get("conclusions_recommendations", "")).strip()
        if existing:
            return existing
    return (
        "Conclusions and limitations should be confirmed by the Ecoventure qualified person. "
        "This draft is based on structured field data only and does not replace "
        "professional judgment or regulatory review."
    )


def _context_for_narrative_prompt(context: dict[str, Any]) -> dict[str, Any]:
    skip = frozenset({"lab_results", "drilling_waste", "storage_tanks"})
    return {
        k: v
        for k, v in context.items()
        if k not in skip and not str(k).startswith("_")
    }


def _narrative_source_names(context: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in context.get("_source_summaries") or []:
        if isinstance(item, dict) and item.get("filename"):
            names.append(f"source/{item['filename']}")
    return names


def draft_narratives(
    context: dict[str, Any],
    *,
    sections: list[str] | None = None,
    use_llm: bool = True,
) -> tuple[list[NarrativeDraft], AiAudit]:
    sections = sections or sections_for_phase(
        str(context.get("report_phase", "")),
        str(context.get("_report_type", "")),
    )
    audit = AiAudit(features=["narrative_draft"], prompt_version=prompt_version())
    drafts: list[NarrativeDraft] = []

    query_parts = [
        str(context.get("site_name", "")),
        str(context.get("report_phase", "")),
        "environmental site assessment",
    ]
    extra_dirs: tuple[Path, ...] = ()
    rag_dir = context.get("_project_rag_dir")
    if rag_dir:
        from pathlib import Path

        extra_dirs = (Path(str(rag_dir)),)
    rag_hits = retrieve(" ".join(query_parts), extra_dirs=extra_dirs)
    rag_context = "\n\n".join(f"[{src}]\n{chunk}" for src, chunk, _ in rag_hits)
    draft_sources = [s for s, _, _ in rag_hits] + _narrative_source_names(context)

    for section in sections:
        if use_llm:
            llm_text = complete_text(
                system=(
                    "You draft professional ESA report prose for Ecoventure Inc. (Alberta oil and gas). "
                    "Use only facts from the JSON context and reference snippets. "
                    "Do not invent regulatory citations or sample results. "
                    "Mark uncertainty. 2-4 short paragraphs max."
                ),
                user=json.dumps(
                    {
                        "section": section,
                        "context": _context_for_narrative_prompt(context),
                        "table_row_counts": {
                            "lab_results": len(context.get("lab_results") or []),
                            "drilling_waste": len(
                                context.get("drilling_waste") or []
                            ),
                            "storage_tanks": len(
                                context.get("storage_tanks") or []
                            ),
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
                        "source_document_summaries": context.get("_source_summaries")
                        or [],
                        "source_summaries_text": str(
                            context.get("_source_summaries_text") or ""
                        )[:10_000],
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
                        sources=draft_sources,
                    )
                )
                continue

        drafts.append(
            NarrativeDraft(
                section=section,
                text=_rule_section(section, context),
                sources=draft_sources if draft_sources else [],
            )
        )

    return drafts, audit
