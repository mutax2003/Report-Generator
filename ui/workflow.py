"""Guided workflow steps (pattern from wizard-style merge tools)."""

from __future__ import annotations

import streamlit as st


def render_workflow_step(
    *,
    has_excel: bool,
    has_template: bool,
    preflight_ok: bool | None,
    has_output: bool,
) -> int:
    """
    Show 1–4 progress. Returns current step index (1-based).
    """
    if has_output:
        step = 4
    elif preflight_ok is True and has_excel and has_template:
        step = 3
    elif has_excel and has_template:
        step = 2
    else:
        step = 1

    labels = [
        "1. Upload Excel + Word template",
        "2. Pre-flight review",
        "3. Generate report",
        "4. Download + manifest",
    ]
    st.progress(step / 4, text=labels[step - 1])
    return step
