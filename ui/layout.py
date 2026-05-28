"""Streamlit layout — sections, upload, generate (native widgets only)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from ui.helpers import (
    parse_template_version_from_filename,
    prepare_uploaded_template,
    render_converted_template_download,
    show_upload_status,
)


def compute_workflow_step(
    *,
    has_excel: bool,
    has_template: bool,
    preflight_ok: bool | None,
    has_output: bool,
) -> int:
    if has_output:
        return 4
    if preflight_ok is True and has_excel and has_template:
        return 3
    if has_excel and has_template:
        return 2
    return 1


def render_workflow_hint() -> None:
    """One-line orientation (replaces removed HTML stepper)."""
    st.markdown(
        "**Workflow:** Sidebar setup → upload files → **Report** tab (pre-flight & generate) "
        "→ download · **AI tools** tab optional"
    )


def render_section_header(step: int, title: str, *, caption: str = "") -> None:
    st.subheader(f"{step}. {title}")
    if caption:
        st.caption(caption)


def render_upload_empty_state() -> None:
    from ui.alberta_imagery import has_alberta_images, render_empty_state_banner

    if has_alberta_images():
        render_empty_state_banner()
    st.info(
        "**Getting started** — In the sidebar, choose your report profile and enter "
        "*Prepared by* / *Date of issue*. Then upload your Excel and Word template below. "
        "Open the **Report** tab to review pre-flight and generate."
    )


def render_upload_step() -> tuple[Any, Any, Any, list[str]]:
    render_section_header(
        1,
        "Upload your files",
        caption="Required: Excel (.xlsx) and report template (.docx or .pdf).",
    )

    col1, col2 = st.columns(2, gap="large")
    excel_file = None
    template_file = None
    prepared_tpl = None
    template_prep_warnings: list[str] = []

    with col1:
        with st.container(border=True):
            st.markdown("**Excel**")
            st.caption("`ProjectData` sheet required · `LabResults` for Phase II")
            excel_file = st.file_uploader(
                "Excel data source",
                type=["xlsx"],
                accept_multiple_files=False,
                key="upload_excel",
                label_visibility="collapsed",
            )
            show_upload_status("Excel", excel_file)

    with col2:
        with st.container(border=True):
            st.markdown("**Word template**")
            st.caption("Jinja tags in `.docx` · PDF auto-converts to Word")
            template_file = st.file_uploader(
                "Report template",
                type=["docx", "pdf"],
                accept_multiple_files=False,
                key="upload_template",
                label_visibility="collapsed",
            )
            prepared_tpl, template_prep_warnings = _prepare_template_from_upload(
                template_file
            )
            tpl_extra = ""
            if prepared_tpl and prepared_tpl.source_format == "pdf":
                tpl_extra = "PDF → Word"
            show_upload_status("Template", template_file, extra=tpl_extra)
            for w in template_prep_warnings:
                st.info(w)
            render_converted_template_download(prepared_tpl)

    if not excel_file and not template_file:
        render_upload_empty_state()

    return excel_file, template_file, prepared_tpl, template_prep_warnings


def _prepare_template_from_upload(template_file: Any) -> tuple[Any, list[str]]:
    if template_file is None:
        return None, []
    try:
        prepared_tpl = prepare_uploaded_template(template_file)
        ver = parse_template_version_from_filename(template_file.name or "")
        if ver:
            st.session_state.suggested_template_version = ver
        return prepared_tpl, list(prepared_tpl.warnings)
    except Exception as e:
        from security import user_safe_error

        st.error(user_safe_error(e))
        return None, []


def render_phrase_expander(render_fn: Any) -> dict[str, str]:
    with st.expander("Standard phrases (optional)", expanded=False):
        return render_fn(compact=True)


def render_generate_cta(
    *,
    can_generate: bool,
    rendering: bool,
    has_excel: bool,
    has_template: bool,
    project_row_count: int,
    project_row_labels: list[str],
) -> tuple[bool, bool, int]:
    render_section_header(
        3,
        "Generate report",
        caption="Green pre-flight above means you can merge and download.",
    )

    batch_mode = False
    project_row_index = 0

    with st.container(border=True):
        if project_row_count > 1:
            st.caption(
                f"**{project_row_count} sites** on `ProjectData` "
                "(row 1 = headers; each row 2+ = one report)."
            )
            gen_mode = st.radio(
                "Generation mode",
                ["Single site", f"All {project_row_count} sites (batch zip)"],
                horizontal=True,
                key="projectdata_gen_mode",
            )
            batch_mode = gen_mode.startswith("All")
            if not batch_mode:
                project_row_index = st.selectbox(
                    "Which site?",
                    options=list(range(project_row_count)),
                    format_func=lambda i: (
                        project_row_labels[i]
                        if i < len(project_row_labels)
                        else f"Excel row {i + 2}"
                    ),
                    key="projectdata_row_select",
                )
        else:
            st.caption("One site per run (row 2 on `ProjectData`). Add rows for batch.")

        generate_disabled = (
            rendering or not has_excel or not has_template or not can_generate
        )
        if generate_disabled:
            hints: list[str] = []
            if not has_excel:
                hints.append("upload Excel")
            if not has_template:
                hints.append("upload template")
            if has_excel and has_template and not can_generate:
                hints.append("fix pre-flight errors")
            if rendering:
                hints.append("wait for current run")
            if hints:
                st.caption("To enable: " + ", ".join(hints))

        btn_label = (
            f"Generate {project_row_count} reports"
            if batch_mode and project_row_count > 1
            else "Generate report"
        )
        generate_clicked = st.button(
            btn_label,
            type="primary",
            use_container_width=True,
            disabled=generate_disabled,
            key="generate_report_btn",
        )

    return generate_clicked, batch_mode, project_row_index


def render_outputs_section_header() -> None:
    render_section_header(
        4,
        "Download deliverables",
        caption="Word report, JSON manifest, and optional zip with appendices.",
    )
