from __future__ import annotations

import datetime as dt

import streamlit as st

from security import MAX_META_VALUE_LEN, sanitize_meta
from ui.helpers import render_download_helpers


def render_sidebar() -> dict[str, str]:
    render_download_helpers()

    st.sidebar.header("Project meta-data")
    prepared_by = st.sidebar.text_input(
        "Prepared by", value="", max_chars=MAX_META_VALUE_LEN
    )
    date_of_issue = st.sidebar.date_input("Date of issue", value=dt.date.today())
    phase = st.sidebar.selectbox(
        "Report phase", options=["Phase 1", "Phase 2"], index=1
    )
    st.sidebar.caption("Phase 1 skips required LabResults sheet.")
    template_version = st.sidebar.text_input(
        "Template version (optional)",
        value="",
        max_chars=32,
        help="Semantic version of the Word file, e.g. 2.1.0 — recorded in the generation manifest.",
    )

    return sanitize_meta(
        {
            "prepared_by": prepared_by,
            "date_of_issue": date_of_issue.isoformat(),
            "report_phase": phase,
            "template_version": template_version,
        }
    )
