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


def render_workflow_stepper(current_step: int) -> None:
    """Horizontal 1–4 progress rail (read-only; CSS states via branding styles)."""
    labels = ("Inputs", "Pre-flight", "Generate", "Download")
    parts: list[str] = ['<div class="ev-stepper" role="list" aria-label="Workflow progress">']
    for i, label in enumerate(labels, start=1):
        if i < current_step:
            state = "ev-step-done"
            num = "✓"
        elif i == current_step:
            state = "ev-step-current"
            num = str(i)
        else:
            state = "ev-step-pending"
            num = str(i)
        parts.append(
            f'<div class="ev-step {state}" role="listitem">'
            f'<span class="ev-step-num">{num}</span>'
            f'<span class="ev-step-label">{i}. {label}</span>'
            f"</div>"
        )
        if i < len(labels):
            conn = "ev-step-conn-done" if i < current_step else ""
            parts.append(f'<div class="ev-step-conn {conn}" aria-hidden="true"></div>')
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def _html_escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_workflow_context_strip(
    *,
    mode_label: str,
    profile_label: str = "",
    excel_name: str = "",
    template_name: str = "",
    site_label: str = "",
) -> None:
    """SharePoint-style breadcrumb: workflow › profile › files."""
    bits: list[str] = [
        f'<span><span class="ev-context-muted">Workflow</span> '
        f"<strong>{_html_escape(mode_label)}</strong></span>"
    ]
    if profile_label:
        bits.append(
            f'<span><span class="ev-context-muted">Profile</span> '
            f"<strong>{_html_escape(profile_label)}</strong></span>"
        )
    if site_label:
        bits.append(
            f'<span><span class="ev-context-muted">Site</span> '
            f"<strong>{_html_escape(site_label)}</strong></span>"
        )
    if excel_name:
        bits.append(
            f'<span><span class="ev-context-muted">Excel</span> '
            f"<strong>{_html_escape(excel_name)}</strong></span>"
        )
    else:
        bits.append('<span class="ev-context-muted">Excel — not loaded</span>')
    if template_name:
        bits.append(
            f'<span><span class="ev-context-muted">Template</span> '
            f"<strong>{_html_escape(template_name)}</strong></span>"
        )
    else:
        bits.append('<span class="ev-context-muted">Template — not loaded</span>')
    st.markdown(
        f'<div class="ev-context">{"".join(bits)}</div>',
        unsafe_allow_html=True,
    )


def render_section_header(step: int, title: str, *, caption: str = "") -> None:
    st.subheader(f"{step}. {title}")
    if caption:
        st.caption(caption)


def render_upload_empty_state() -> None:
    from ui.alberta_imagery import has_alberta_images, render_empty_state_banner
    from ui.helpers import load_phase1_alberta_sample_into_session

    if has_alberta_images():
        render_empty_state_banner()
    st.markdown(
        '<div class="ev-empty-panel">'
        "<strong>Getting started</strong> — Set <em>Prepared by</em> in the sidebar, "
        "then upload Excel + Word below — or load the Alberta Phase I sample to try "
        "the full flow."
        "</div>",
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns([2, 3])
    with c1:
        if st.button(
            "Load Alberta Phase I sample",
            type="primary",
            width="stretch",
            key="load_phase1_alberta_sample_empty",
            help="Loads starter Excel + Word into this session (same as sidebar).",
        ):
            if load_phase1_alberta_sample_into_session():
                st.session_state.sample_load_toast = True
                st.rerun()
            else:
                st.error("Sample files missing — run scripts/create_samples.py first.")
    with c2:
        st.caption("Or upload your own `.xlsx` and `.docx` / `.pdf` in the columns above.")


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
            with st.expander("Optional: Ecoventure Phase I + DWDA workbook", expanded=False):
                st.caption(
                    "Upload a filled `.xlsx` saved from the Ecoventure xltm to merge "
                    "ProjectData, DrillingWaste, and calculation outputs."
                )
                eco_file = st.file_uploader(
                    "Ecoventure workbook",
                    type=["xlsx", "xlsm"],
                    accept_multiple_files=False,
                    key="upload_ecoventure_workbook",
                    label_visibility="collapsed",
                )
                if eco_file is not None:
                    from security import SecurityError, user_safe_error, validate_excel_upload

                    eco_bytes = eco_file.getvalue()
                    try:
                        validate_excel_upload(eco_bytes, eco_file.name or "")
                    except SecurityError as exc:
                        st.error(user_safe_error(exc))
                        st.session_state.pop("ecoventure_workbook_bytes", None)
                    else:
                        st.session_state["ecoventure_workbook_bytes"] = eco_bytes

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

    if excel_file and not template_file:
        st.info("Upload your **Word or PDF template** in the column on the right.")
    elif template_file and not excel_file:
        st.info("Upload your **Excel** file (.xlsx) in the column on the left.")

    if not excel_file and not template_file:
        from ui.helpers import session_loaded_file_names

        ex_name, tpl_name = session_loaded_file_names()
        if ex_name and tpl_name:
            st.success(
                f"Sample loaded: **{ex_name}** + **{tpl_name}** — open the **Report** tab."
            )
        else:
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


from security import MAX_BATCH_REPORTS

_LARGE_TEMPLATE_BYTES = 10 * 1024 * 1024


def generate_blockers(
    *,
    rendering: bool,
    has_excel: bool,
    has_template: bool,
    can_generate: bool,
) -> list[str]:
    if rendering:
        return []
    blockers: list[str] = []
    if not has_excel:
        blockers.append("Excel not loaded (step 1)")
    if not has_template:
        blockers.append("Template not loaded (step 1)")
    if has_excel and has_template and not can_generate:
        blockers.append("Fix pre-flight **errors** (step 2)")
    return blockers


def render_phrase_expander(render_fn: Any) -> dict[str, str]:
    with st.expander("Standard phrases (optional)", expanded=False):
        st.caption(
            "Optional wording for tagged Phase I fields — leave as default unless your "
            "template uses these phrases."
        )
        return render_fn(compact=True)


def render_generate_cta(
    *,
    can_generate: bool,
    rendering: bool,
    has_excel: bool,
    has_template: bool,
    project_row_count: int,
    project_row_labels: list[str],
    template_bytes: bytes | None = None,
    prepared_by: str = "",
) -> tuple[bool, bool, int]:
    render_section_header(
        3,
        "Generate report",
        caption="Pre-flight must pass with no blocking errors (warnings are OK).",
    )

    batch_mode = False
    project_row_index = 0

    with st.container(border=True):
        st.markdown(
            '<div class="ev-sticky-cta" aria-label="Generate report actions">',
            unsafe_allow_html=True,
        )
        if rendering:
            st.info("Generating report — please wait.")
        elif template_bytes and len(template_bytes) > _LARGE_TEMPLATE_BYTES:
            st.caption(
                "Large template — generation may take **30–60 seconds**."
            )

        if has_excel and has_template and can_generate and not (prepared_by or "").strip():
            st.warning(
                "**Prepared by** is empty — set it in the sidebar before client delivery."
            )

        if project_row_count > 1:
            st.caption(
                f"**{project_row_count} sites** on `ProjectData` "
                "(row 1 = headers; each row 2+ = one report)."
            )
            if project_row_count > MAX_BATCH_REPORTS:
                st.warning(
                    f"Batch zip supports at most **{MAX_BATCH_REPORTS}** sites per run "
                    f"({project_row_count} rows). Use single-site mode or split the workbook."
                )
                gen_mode = "Single site"
            else:
                gen_mode = st.radio(
                    "Generation mode",
                    ["Single site", f"All {project_row_count} sites (batch zip)"],
                    horizontal=True,
                    key="projectdata_gen_mode",
                )
            batch_mode = isinstance(gen_mode, str) and gen_mode.startswith("All")
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
        blockers = generate_blockers(
            rendering=rendering,
            has_excel=has_excel,
            has_template=has_template,
            can_generate=can_generate,
        )
        if blockers:
            st.markdown("**To enable Generate:**")
            for b in blockers:
                st.markdown(f"- {b}")

        btn_label = (
            f"Generate {project_row_count} reports"
            if batch_mode and project_row_count > 1
            else "Generate report"
        )
        generate_clicked = st.button(
            btn_label,
            type="primary",
            width="stretch",
            disabled=generate_disabled,
            key="generate_report_btn",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    return generate_clicked, batch_mode, project_row_index

def render_outputs_section_header() -> None:
    render_section_header(
        4,
        "Download deliverables",
        caption="Primary download is the **deliverable package (.zip)** — Word report, manifest, and appendices.",
    )
