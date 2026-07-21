from __future__ import annotations

import datetime as dt

import streamlit as st

from security import MAX_META_VALUE_LEN, sanitize_meta
from report_profile import get_profile_default_phase, list_report_profiles
from ui.branding import render_sidebar_branding
from ui.helpers import load_phase1_alberta_sample_into_session, render_download_helpers
from ui.onboarding import is_simple_mode, render_getting_started_checklist


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
    render_sidebar_branding()
    render_getting_started_checklist()
    st.sidebar.divider()
    st.sidebar.subheader("Settings")

    st.session_state.setdefault(
        "ux_simple_mode",
        not st.session_state.get("ux_welcome_dismissed", False),
    )
    st.sidebar.checkbox(
        "Simple mode (recommended for new users)",
        key="ux_simple_mode",
        help="Hides advanced options like executive summary override and AI settings.",
    )
    simple = is_simple_mode()

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

    with st.sidebar.expander("Report profile", expanded=not simple):
        phase = st.selectbox(
            "Report phase",
            options=["Phase 1", "Phase 2"],
            key="report_phase_sel",
            on_change=_on_phase_change,
            help="Phase II selects the Phase II profile automatically.",
        )
        report_type = st.selectbox(
            "Profile",
            options=profile_ids,
            format_func=lambda x: profile_labels.get(x, x),
            key="report_type_sel",
            on_change=_on_profile_change,
        )
        if (
            not simple
            and phase != get_profile_default_phase(report_type)
            and report_type != "template_driven"
        ):
            st.caption(
                f"Tip: **{profile_labels.get(report_type, report_type)}** is usually "
                f"**{get_profile_default_phase(report_type)}**."
            )

    with st.sidebar.expander("Project metadata", expanded=True):
        prepared_by = st.text_input(
            "Prepared by *",
            value="",
            max_chars=MAX_META_VALUE_LEN,
            key="sidebar_prepared_by",
            help="Author name on the cover / signature block (required for client delivery).",
        )
        if not (prepared_by or "").strip():
            st.caption("Enter your name before generating a client deliverable.")
        date_of_issue = st.date_input("Date of issue", value=dt.date.today())
        template_version = st.text_input(
            "Template version (optional)",
            value=st.session_state.get("suggested_template_version", ""),
            max_chars=32,
            help="Recorded in the generation manifest, e.g. 2.1.0",
        )

    executive_summary = ""
    pending_exec = st.session_state.pop("pending_executive_summary", None)
    if pending_exec is not None:
        st.session_state["exec_summary_override"] = pending_exec
    if not simple:
        with st.sidebar.expander("Executive summary override", expanded=bool(pending_exec)):
            executive_summary = st.text_area(
                "Custom executive summary",
                height=100,
                help="Replaces Excel and auto-generated Phase I text when filled.",
                label_visibility="collapsed",
                key="exec_summary_override",
            )
            st.caption("Leave blank to use Excel or auto-generated text.")
    else:
        executive_summary = str(st.session_state.get("exec_summary_override") or "")

    with st.sidebar.expander("Sample templates", expanded=simple):
        st.caption("Starter Excel/Word pairs for testing.")
        if st.button(
            "Load Alberta Phase I sample into session",
            width="stretch",
            key="load_phase1_alberta_sample",
        ):
            if load_phase1_alberta_sample_into_session():
                st.session_state.sample_load_toast = True
                st.rerun()
            else:
                st.error("Sample files could not be loaded. Run create_samples.py first.")
        if st.session_state.pop("sample_load_toast", False):
            st.success("Sample loaded — open the **Report** tab to pre-flight and generate.")
        render_download_helpers()

    return sanitize_meta(
        {
            "prepared_by": prepared_by,
            "date_of_issue": date_of_issue.isoformat(),
            "report_phase": phase,
            "report_type": report_type,
            "template_version": template_version,
            "executive_summary": (executive_summary or "").strip(),
        }
    )
