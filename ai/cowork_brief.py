"""Build paste-ready Claude Max / Cowork task briefs for a project folder.

Advisory only — does not call LLMs or touch ReportEngine.
"""

from __future__ import annotations

from pathlib import Path

from ai.prompts import agent_brief, agent_task_prompt

_PROFILE_DRAFT_HINTS: dict[str, str] = {
    "phase1_alberta": (
        "Draft to ai_drafts/:\n"
        "  narratives.json — sections: executive_summary, drilling_waste, "
        "site_reconnaissance, conclusions_recommendations\n"
        "  apecs_candidates.json — APEC rows from source PDFs (if found)\n"
        "  excel_field_suggestions.json — scalar ProjectData fields only"
    ),
    "phase1_devon": (
        "Draft to ai_drafts/:\n"
        "  narratives.json — sections: executive_summary, drilling_waste, "
        "site_reconnaissance, conclusions_recommendations\n"
        "  apecs_candidates.json — APEC rows from source PDFs (if found)"
    ),
    "phase2_esa": (
        "IMPORTANT: LabResults in project_data.xlsx must be populated BEFORE conclusions.\n"
        "Draft to ai_drafts/:\n"
        "  narratives.json — sections: executive_summary, site_description, "
        "conclusions_limitations"
    ),
    "groundwater_monitoring": (
        "Well IDs must match across MonitoringWells, WaterLevels, and GroundwaterLab.\n"
        "Draft to ai_drafts/:\n"
        "  narratives.json — sections: executive_summary, hydrogeologic_setting, "
        "conclusions_recommendations"
    ),
}


def build_site_cowork_brief(
    folder: Path | str,
    *,
    report_type: str = "phase1_alberta",
) -> str:
    """Return a Claude Max / Cowork paste brief for one site folder."""
    root = Path(folder).expanduser().resolve()
    rt = (report_type or "phase1_alberta").strip() or "phase1_alberta"
    draft_hint = _PROFILE_DRAFT_HINTS.get(rt) or (
        f"Draft narratives.json under ai_drafts/ for profile `{rt}` "
        "using only facts from source/ PDFs."
    )
    brief = agent_brief(rt) or "Alberta ESA advisory draft for Ecoventure."
    review_task = agent_task_prompt("adversarial_review") or (
        "Challenge every claim against source/ PDFs before Apply."
    )
    lines = [
        "ESA Report Generator — Claude Max / Cowork brief (this site)",
        "=" * 56,
        "",
        f"Folder: {root}",
        f"Profile: {rt}",
        "Attach: project.json, source/ PDFs (and LabResults context for Phase II)",
        "",
        "SHARED RULES",
        "-" * 12,
        "Allowed outputs: ai_drafts/*.json ONLY — do not edit project_data.xlsx directly",
        "Cite source PDF filenames in each section; mark gaps [confirm]",
        "NEVER invent lab concentrations, exceedances, UWIs, or certificate numbers",
        "Do not modify engine.py",
        "",
        "AGENT BRIEF",
        "-" * 11,
        brief,
        "",
        "DRAFT TARGETS",
        "-" * 13,
        draft_hint,
        "",
        "AFTER DRAFTS (in Streamlit or CLI)",
        "-" * 30,
        "1) Streamlit: Project folder step → Run adversarial review",
        "   (or: python scripts/agent_folder_report.py --folder <path> --mode review)",
        "2) Claude Max OR Cursor: open ai_drafts/adversarial_review.md and challenge",
        "   claims vs source/ PDFs (you do NOT need Cursor Pro for this step).",
        "3) Streamlit AI tab: Apply drafts → Report tab: Generate → deliverable zip",
        "4) QP review before client delivery",
        "",
        "ADVERSARIAL REVIEW PROMPT (paste into Claude Max when reviewing)",
        "-" * 60,
        review_task,
        "",
    ]
    return "\n".join(lines)
