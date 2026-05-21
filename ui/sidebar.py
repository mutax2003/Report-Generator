from __future__ import annotations

import datetime as dt

import streamlit as st

from security import MAX_META_VALUE_LEN, sanitize_meta
from report_profile import get_profile_default_phase, list_report_profiles
from ui.helpers import render_download_helpers


def _on_phase_change() -> None:
    phase = st.session_state.get("report_phase_sel", "Phase 1")
    current = st.session_state.get("report_type_sel", "phase1_alberta")
    if phase == "Phase 2":
        st.session_state.report_type_sel = "phase2_esa"
    elif phase == "Phase 1" and current == "phase2_esa":
        st.session_state.report_type_sel = "phase1_alberta"


def _on_profile_change() -> None:
    pid = st.session_state.get("report_type_sel", "phase1_alberta")
    st.session_state.report_phase_sel = get_profile_default_phase(pid)


def render_sidebar() -> dict[str, str]:
    render_download_helpers()

    st.sidebar.header("Report type")
    profiles = list_report_profiles()
    profile_ids = [p[0] for p in profiles]
    profile_labels = {p[0]: p[1] for p in profiles}
    if "report_type_sel" not in st.session_state:
        st.session_state.report_type_sel = (
            "phase1_alberta" if "phase1_alberta" in profile_ids else profile_ids[0]
        )
    if "report_phase_sel" not in st.session_state:
        st.session_state.report_phase_sel = get_profile_default_phase(
            st.session_state.report_type_sel
        )

    phase = st.sidebar.selectbox(
        "Report phase",
        options=["Phase 1", "Phase 2"],
        key="report_phase_sel",
        on_change=_on_phase_change,
        help="Phase II auto-selects the Phase II profile.",
    )
    report_type = st.sidebar.selectbox(
        "Profile",
        options=profile_ids,
        format_func=lambda x: profile_labels.get(x, x),
        key="report_type_sel",
        on_change=_on_profile_change,
        help="Maps Excel sheets to Word template fields. Use 'Custom' for your own tagged template.",
    )
    if phase != get_profile_default_phase(report_type) and report_type != "template_driven":
        st.sidebar.caption(
            f"Profile **{profile_labels.get(report_type, report_type)}** "
            f"typically uses **{get_profile_default_phase(report_type)}**."
        )
    st.sidebar.caption(
        "Optional: add a **ReportConfig** sheet in Excel (columns key, value) to override "
        "`report_type` and sheet-to-loop mappings (`map_LabResults` = lab_results)."
    )

    st.sidebar.header("Project meta-data")
    prepared_by = st.sidebar.text_input(
        "Prepared by", value="", max_chars=MAX_META_VALUE_LEN
    )
    date_of_issue = st.sidebar.date_input("Date of issue", value=dt.date.today())
    st.sidebar.caption("Phase 1 skips required LabResults sheet.")
    template_version = st.sidebar.text_input(
        "Template version (optional)",
        value=st.session_state.get("suggested_template_version", ""),
        max_chars=32,
        help="Semantic version of the Word file, e.g. 2.1.0 — recorded in the generation manifest.",
    )

    st.sidebar.header("Executive summary (optional)")
    executive_summary = st.sidebar.text_area(
        "Override executive summary",
        value="",
        height=120,
        help="Replaces Excel and auto-generated Phase I text when filled.",
    )

    return sanitize_meta(
        {
            "prepared_by": prepared_by,
            "date_of_issue": date_of_issue.isoformat(),
            "report_phase": phase,
            "report_type": report_type,
            "template_version": template_version,
            "executive_summary": executive_summary.strip(),
        }
    )
