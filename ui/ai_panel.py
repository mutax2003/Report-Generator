"""Streamlit UI for Tier 1 & 2 AI features."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from ai import ai_status_message
from ai.config import ai_available
from ai.consistency import check_consistency
from ai.copilot import explain_preflight
from ai.exceedance_notes import notes_for_lab_rows
from ai.excel_builder import lab_rows_to_groundwater_xlsx_bytes, lab_rows_to_xlsx_bytes
from ai.gw_trends import analyze_groundwater_trends
from ai.lab_extract import extract_lab_from_pdf
from ai.well_log_extract import extract_wells_from_pdf
from ai.models import AiAudit
from ai.narrative import draft_narratives
from ai.template_tagger import suggest_template_tags, suggestions_to_markdown
from engine import ReportEngine
from security import user_safe_error
from template_tools import PreflightResult, run_preflight


def _step1_input_hint(folder_mode: bool) -> str:
    return "Load folder on **step 1**" if folder_mode else "Upload on **step 1**"


def _use_llm() -> bool:
    return st.session_state.get("ai_use_llm", ai_available())


def _merge_audit(audit: AiAudit) -> None:
    existing: list[dict[str, Any]] = st.session_state.get("ai_audit_log") or []
    existing.append(audit.to_dict())
    st.session_state["ai_audit_log"] = existing[-20:]


def _build_context_from_excel(excel_bytes: bytes, meta: dict[str, str]) -> dict[str, Any] | None:
    """Build context using a minimal valid template stub."""
    import os
    import tempfile
    from pathlib import Path

    from engine import generate_sample_template_docx
    from security import clamp_context

    path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            path = tmp.name
            generate_sample_template_docx(path)
            tpl = Path(path).read_bytes()
        engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=tpl)
        ctx = engine.build_context(meta)
        ctx, _ = clamp_context(ctx)
        return ctx
    except Exception:
        return None
    finally:
        if path and os.path.isfile(path):
            try:
                os.unlink(path)
            except OSError:
                pass


def render_ai_settings_sidebar(*, folder_mode: bool = False) -> None:
    with st.sidebar.expander("AI options", expanded=folder_mode):
        st.caption(ai_status_message())
        st.session_state.setdefault("ai_use_llm", ai_available())
        st.checkbox(
            "Use cloud LLM when available",
            key="ai_use_llm",
            help="Requires OPENAI_API_KEY. Offline rules used otherwise.",
        )
        if folder_mode:
            st.caption(
                "Turn off for offline heuristics only when using **Analyze folder**."
            )


def render_ai_panel(
    *,
    excel_bytes: bytes | None,
    template_bytes: bytes | None,
    meta: dict[str, str],
    preflight: PreflightResult | None,
    folder_mode: bool = False,
) -> None:
    st.subheader("AI drafts & tools" if folder_mode else "AI tools")
    if folder_mode:
        st.info(
            "Use **Analyze folder** on step 1 to write inventory, narratives, and appendix "
            "suggestions to `ai_drafts/` on disk. Tools below work on the loaded Excel + "
            "template. **All AI output requires QP review** before client delivery."
        )
    else:
        st.info(
            "Optional helpers for tagging, lab PDF import, narratives, and QA. "
            "**All AI output requires QP review** before client delivery."
        )

    t1, t2 = st.tabs(["Data & templates", "QA & narratives"])

    if folder_mode:
        _tab_folder_drafts()
        st.divider()

    with t1:
        _tab_template_tagger(template_bytes, folder_mode=folder_mode)
        st.divider()
        _tab_lab_pdf(excel_bytes, meta, folder_mode=folder_mode)
        st.divider()
        _tab_well_log_pdf(excel_bytes, folder_mode=folder_mode)
        st.divider()
        _tab_narratives(excel_bytes, meta, folder_mode=folder_mode)

    with t2:
        _tab_copilot(preflight, meta, folder_mode=folder_mode)
        st.divider()
        _tab_gw_trends(excel_bytes, meta, folder_mode=folder_mode)
        st.divider()
        _tab_quality(excel_bytes, template_bytes, meta, folder_mode=folder_mode)


def _tab_folder_drafts() -> None:
    """Review on-disk ai_drafts/ from the loaded project folder."""
    st.subheader("Folder AI drafts (on disk)")
    root = st.session_state.get("project_folder_resolved")
    if not root:
        st.info("Load a project folder on step 1 to review `ai_drafts/` here.")
        return
    drafts_dir = Path(root) / "ai_drafts"
    if not drafts_dir.is_dir():
        st.info(
            "No `ai_drafts/` folder yet — run **Analyze folder** on step 1 to create drafts."
        )
        return

    review_files = (
        ("inventory.md", "markdown"),
        ("preflight_report.md", "markdown"),
        ("source_summaries.json", "json"),
        ("narratives.json", "json"),
        ("excel_field_suggestions.json", "json"),
        ("appendix_labels.json", "json"),
    )
    shown = 0
    for name, kind in review_files:
        path = drafts_dir / name
        if not path.is_file():
            continue
        shown += 1
        with st.expander(name, expanded=name in ("preflight_report.md", "narratives.json")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as e:
                st.error(user_safe_error(e))
                continue
            if kind == "json":
                try:
                    st.json(json.loads(text))
                except json.JSONDecodeError:
                    st.code(text)
            else:
                st.markdown(text)

    if shown == 0:
        st.caption("Run **Analyze folder** to populate inventory, preflight, and narratives.")
    else:
        st.caption(f"Files live under `{drafts_dir}` — edit on disk or copy into Excel as needed.")


def _tab_template_tagger(template_bytes: bytes | None, *, folder_mode: bool = False) -> None:
    st.subheader("1. Template tagger")
    st.markdown(
        "Suggests `{{ jinja }}` replacements for bracket placeholders and common phrases. "
        "Apply changes manually in Word (single formatting run per tag)."
    )
    report_type = st.session_state.get("report_type_sel", "") or st.session_state.get(
        "report_type", ""
    )
    use_phase1 = report_type == "phase1_alberta"
    use_gw = report_type == "groundwater_monitoring"
    if use_phase1:
        st.caption(
            "**Alberta Phase I:** Uses `schemas/report_profiles.json` fields. "
            "For PDF layouts, run `python scripts\\phase1_pdf_to_markup.py` locally, "
            "then upload the `-markup.docx`."
        )
    if not template_bytes:
        st.info(f"Load a Word template on {_step1_input_hint(folder_mode)} to analyze.")
        return
    if st.button("Analyze template tags", key="ai_tag_btn", width="stretch"):
        with st.spinner("Scanning document..."):
            try:
                suggestions, audit = suggest_template_tags(
                    template_bytes,
                    use_llm=_use_llm(),
                    report_type=report_type if (use_phase1 or use_gw) else None,
                )
                st.session_state["tag_suggestions"] = suggestions
                _merge_audit(audit)
            except Exception as e:
                st.error(user_safe_error(e))

    suggestions = st.session_state.get("tag_suggestions")
    if not suggestions:
        return
    st.success(f"{len(suggestions)} suggestion(s)")
    md = suggestions_to_markdown(suggestions)
    st.download_button(
        "Download tagging guide (.md)",
        data=md.encode("utf-8"),
        file_name="template_tagging_suggestions.md",
        mime="text/markdown",
        width="stretch",
    )
    with st.expander("Preview suggestions", expanded=True):
        for s in suggestions[:30]:
            st.markdown(f"- **{s.original_text}** → `{s.jinja_tag}` ({s.confidence:.0%}, {s.source})")
            if s.notes:
                st.caption(s.notes)


def _tab_lab_pdf(
    excel_bytes: bytes | None,
    meta: dict[str, str],
    *,
    folder_mode: bool = False,
) -> None:
    st.subheader("2. Lab PDF → Excel (LabResults / GroundwaterLab)")
    target = st.radio(
        "Target sheet",
        ["LabResults (Phase II)", "GroundwaterLab (monitoring)"],
        horizontal=True,
        key="ai_lab_target_sheet",
    )

    pdf_bytes: bytes | None = None
    pdf_label = ""
    if folder_mode:
        root = st.session_state.get("project_folder_resolved")
        if root:
            source_dir = Path(root) / "source"
            folder_pdfs = sorted(source_dir.glob("*.pdf")) if source_dir.is_dir() else []
            if folder_pdfs:
                pick = st.selectbox(
                    "Pick lab PDF from folder `source/`",
                    options=["(upload instead)"] + [p.name for p in folder_pdfs],
                    key="ai_lab_folder_pdf",
                )
                if pick != "(upload instead)":
                    pdf_label = pick
                    pdf_bytes = (source_dir / pick).read_bytes()

    pdf = st.file_uploader("Lab certificate / COA (PDF)", type=["pdf"], key="ai_lab_pdf")
    if pdf is not None:
        pdf_bytes = pdf.getvalue()
        pdf_label = pdf.name or "uploaded.pdf"

    if pdf_bytes and st.button("Extract lab table", key="ai_lab_extract", width="stretch"):
        with st.spinner(f"Parsing PDF{' ' + pdf_label if pdf_label else ''}..."):
            try:
                result = extract_lab_from_pdf(pdf_bytes, use_llm=_use_llm())
                st.session_state["lab_extract"] = result
                _merge_audit(
                    AiAudit(
                        features=["lab_pdf_extract"],
                        used_llm=result.source == "llm",
                    )
                )
            except Exception as e:
                st.error(user_safe_error(e))

    result = st.session_state.get("lab_extract")
    if not result:
        return
    for w in result.warnings:
        st.warning(w)
    if result.rows:
        st.dataframe(
            [r.to_excel_dict() for r in result.rows],
            width="stretch",
            hide_index=True,
        )
        if target.startswith("Groundwater"):
            xlsx = lab_rows_to_groundwater_xlsx_bytes(
                result.rows,
                existing_excel=excel_bytes,
            )
            dl_name = "gw_lab_import.xlsx"
            dl_label = "Download Excel with GroundwaterLab"
        else:
            xlsx = lab_rows_to_xlsx_bytes(
                result.rows,
                existing_excel=excel_bytes,
            )
            dl_name = "lab_import.xlsx"
            dl_label = "Download Excel with LabResults"
        st.download_button(
            dl_label,
            data=xlsx,
            file_name=dl_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    with st.expander("PDF text preview"):
        st.text(result.raw_text_preview or "(empty)")


def _tab_well_log_pdf(excel_bytes: bytes | None, *, folder_mode: bool = False) -> None:
    st.subheader("3. Well log PDF → MonitoringWells")
    pdf = st.file_uploader(
        "Borehole / well construction PDF",
        type=["pdf"],
        key="ai_well_log_pdf",
    )
    if pdf and st.button("Extract monitoring wells", key="ai_well_extract", width="stretch"):
        with st.spinner("Parsing well log..."):
            try:
                rows, warnings, audit = extract_wells_from_pdf(
                    pdf.getvalue(), use_llm=_use_llm()
                )
                st.session_state["well_extract_rows"] = rows
                st.session_state["well_extract_warnings"] = warnings
                _merge_audit(audit)
            except Exception as e:
                st.error(user_safe_error(e))

    rows = st.session_state.get("well_extract_rows")
    if not rows:
        return
    for w in st.session_state.get("well_extract_warnings") or []:
        st.warning(w)
    st.dataframe(
        [r.to_excel_dict() for r in rows],
        width="stretch",
        hide_index=True,
    )
    from engine import MONITORING_WELLS_SHEET, PROJECT_SHEET

    well_dicts = [r.to_excel_dict() for r in rows]
    sheets: dict = {
        PROJECT_SHEET: pd.DataFrame([{}]),
        MONITORING_WELLS_SHEET: pd.DataFrame(well_dicts),
    }
    if excel_bytes:
        bio = io.BytesIO(excel_bytes)
        with pd.ExcelFile(bio, engine="openpyxl") as xl:
            for name in xl.sheet_names:
                if name != MONITORING_WELLS_SHEET:
                    sheets[name] = xl.parse(name)
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        for name, df in sheets.items():
            df.to_excel(w, sheet_name=name, index=False)
    st.download_button(
        "Download Excel with MonitoringWells",
        data=out.getvalue(),
        file_name="monitoring_wells_import.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )


def _tab_gw_trends(
    excel_bytes: bytes | None, meta: dict[str, str], *, folder_mode: bool = False
) -> None:
    st.subheader("2. Groundwater trend notes")
    ctx = st.session_state.get("last_context") or (
        _build_context_from_excel(excel_bytes, meta) if excel_bytes else None
    )
    if not ctx:
        st.info(
            f"Load groundwater Excel on {_step1_input_hint(folder_mode)} "
            "or generate a report first."
        )
        return
    if st.button("Analyze trends", key="ai_gw_trends_btn", width="stretch"):
        notes, audit = analyze_groundwater_trends(ctx, use_llm=_use_llm())
        st.session_state["gw_trend_notes"] = notes
        _merge_audit(audit)
    for note in st.session_state.get("gw_trend_notes") or []:
        if note.severity == "warning":
            st.warning(note.message)
        else:
            st.info(note.message)


def _tab_narratives(
    excel_bytes: bytes | None, meta: dict[str, str], *, folder_mode: bool = False
) -> None:
    st.subheader("4. Narrative drafts (RAG-assisted)")
    ctx = st.session_state.get("last_context") or (
        _build_context_from_excel(excel_bytes, meta) if excel_bytes else None
    )
    if not ctx:
        st.info(
            f"Load Excel on {_step1_input_hint(folder_mode)} "
            "(or generate once) to draft narratives."
        )
        return

    sections = st.multiselect(
        "Sections",
        options=["executive_summary", "site_description", "conclusions_limitations"],
        default=["executive_summary", "conclusions_limitations"],
    )
    if st.button("Draft narratives", key="ai_narrative_btn", width="stretch"):
        with st.spinner("Drafting..."):
            drafts, audit = draft_narratives(ctx, sections=sections, use_llm=_use_llm())
            st.session_state["narrative_drafts"] = drafts
            _merge_audit(audit)

    for draft in st.session_state.get("narrative_drafts") or []:
        st.markdown(f"**{draft.section.replace('_', ' ').title()}**")
        st.caption(draft.disclaimer)
        if draft.sources:
            st.caption(f"RAG sources: {', '.join(draft.sources)}")
        st.text_area(
            label=draft.section,
            value=draft.text,
            height=160,
            key=f"narrative_{draft.section}",
            label_visibility="collapsed",
        )


def _tab_copilot(
    preflight: PreflightResult | None,
    meta: dict[str, str],
    *,
    folder_mode: bool = False,
) -> None:
    st.subheader("1. Pre-flight copilot")
    if not preflight:
        st.info(
            f"Load Excel + template on {_step1_input_hint(folder_mode)} "
            "to run pre-flight first."
        )
        return
    if st.button("Explain pre-flight", key="ai_copilot_btn", width="stretch"):
        advice, audit = explain_preflight(preflight, meta, use_llm=_use_llm())
        st.session_state["copilot_advice"] = advice
        _merge_audit(audit)

    advice = st.session_state.get("copilot_advice")
    if not advice:
        return
    st.markdown(advice.summary)
    for i, step in enumerate(advice.steps, 1):
        st.markdown(f"{i}. {step}")
    if advice.excel_columns_to_add:
        st.markdown("**Add ProjectData columns:**")
        st.code(", ".join(advice.excel_columns_to_add))


def _tab_quality(
    excel_bytes: bytes | None,
    template_bytes: bytes | None,
    meta: dict[str, str],
    *,
    folder_mode: bool = False,
) -> None:
    st.subheader("3. Consistency & exceedance notes")
    ctx = st.session_state.get("last_context") or (
        _build_context_from_excel(excel_bytes, meta) if excel_bytes else None
    )
    if not ctx:
        st.info(
            f"Need Excel context — load files on {_step1_input_hint(folder_mode)} "
            "or generate a report first."
        )
    elif st.button("Run consistency check", key="ai_consistency_btn", width="stretch"):
        findings, audit = check_consistency(
            ctx,
            template_bytes=template_bytes,
            use_llm=_use_llm() and ai_available(),
        )
        st.session_state["consistency_findings"] = findings
        _merge_audit(audit)

    for f in st.session_state.get("consistency_findings") or []:
        if f.severity == "error":
            st.error(f.message)
        elif f.severity == "warning":
            st.warning(f.message)
        else:
            st.info(f.message)
        if f.suggestion:
            st.caption(f"→ {f.suggestion}")

    st.divider()
    st.markdown("**Exceedance notes**")
    lab = (ctx or {}).get("lab_results") if ctx else None
    if not isinstance(lab, list) or not lab:
        st.info("No lab_results in context.")
        return
    if st.button("Generate exceedance notes", key="ai_exc_btn", width="stretch"):
        notes, audit = notes_for_lab_rows(
            lab,
            site_name=str((ctx or {}).get("site_name", "")),
            use_llm=_use_llm(),
        )
        st.session_state["exceedance_notes"] = notes
        _merge_audit(audit)

    for n in st.session_state.get("exceedance_notes") or []:
        st.markdown(f"**{n.analyte}** ({n.confidence:.0%}, {n.source}): {n.note}")

    if st.session_state.get("ai_audit_log"):
        with st.expander("AI audit log (session)"):
            st.json(st.session_state["ai_audit_log"])
