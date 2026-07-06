"""Startup workflow choice: project folder + AI vs Excel + template upload."""

from __future__ import annotations

from typing import Literal

import streamlit as st

from ui.project_folder import clear_folder_session

WorkflowMode = Literal["folder", "upload"]

WORKFLOW_FOLDER: WorkflowMode = "folder"
WORKFLOW_UPLOAD: WorkflowMode = "upload"

_LABELS = {
    WORKFLOW_FOLDER: "Project folder + AI",
    WORKFLOW_UPLOAD: "Excel + Word template",
}


def get_workflow_mode() -> WorkflowMode | None:
    mode = st.session_state.get("workflow_mode")
    if mode in (WORKFLOW_FOLDER, WORKFLOW_UPLOAD):
        return mode
    return None


def workflow_label(mode: WorkflowMode) -> str:
    return _LABELS[mode]


def render_workflow_picker() -> None:
    """Full-width choice screen shown before the main app workflow."""
    st.subheader("How do you want to generate your report?")
    st.caption(
        "Pick one path to start. You can switch later — loaded files will be cleared."
    )

    col_folder, col_upload = st.columns(2, gap="large")

    with col_folder:
        with st.container(border=True):
            st.markdown("#### Project folder + AI")
            st.markdown(
                "Work from a **local site folder** on your PC. The app reads "
                "`project_data.xlsx`, `template.docx`, and PDFs in `source/` and "
                "`appendices/`, then can draft narratives and checklists with AI "
                "into `ai_drafts/` before you generate the final Word report."
            )
            st.markdown(
                "- Best for **full site packages** (260109R-style folders)\n"
                "- **Browse…** to pick a folder on your PC\n"
                "- Optional **LLM** for inventory, narratives, appendix labels\n"
                "- Outputs can go to `delivered/` on disk"
            )
            if st.button(
                "Use project folder workflow",
                type="primary",
                width="stretch",
                key="pick_workflow_folder",
            ):
                _set_workflow(WORKFLOW_FOLDER)

    with col_upload:
        with st.container(border=True):
            st.markdown("#### Excel + Word template")
            st.markdown(
                "Upload an **Excel data file** and a **Word or PDF template** "
                "directly in the browser. The engine merges Jinja tags — no folder "
                "layout required. Use standard phrases, appendices, and pre-flight "
                "as today."
            )
            st.markdown(
                "- Best for **quick one-off** merges and testing\n"
                "- Supports **batch** when Excel has multiple `ProjectData` rows\n"
                "- PDF templates auto-convert to Word"
            )
            if st.button(
                "Use Excel + template workflow",
                type="primary",
                width="stretch",
                key="pick_workflow_upload",
            ):
                _set_workflow(WORKFLOW_UPLOAD)

    with st.expander("Not sure which to pick?", expanded=False):
        st.markdown(
            """
| Situation | Recommended |
|-----------|-------------|
| You already have a project folder with `source/`, `appendices/`, etc. | **Project folder + AI** |
| You only have one `.xlsx` and one `.docx` to merge | **Excel + Word template** |
| You want AI narrative drafts saved under `ai_drafts/` | **Project folder + AI** |
| You are testing a new template tag layout | **Excel + Word template** |

See [docs/22-project-folder-workflow.md](docs/22-project-folder-workflow.md) for folder layout.
"""
        )


def _has_generated_report() -> bool:
    return bool(
        st.session_state.get("generated_docx")
        or st.session_state.get("generated_batch")
        or st.session_state.get("batch_deliverable_zip")
        or st.session_state.get("batch_reports_zip")
    )


def _has_loaded_inputs() -> bool:
    if st.session_state.get("project_folder_loaded"):
        return True
    if st.session_state.get("project_folder_excel_bytes"):
        return True
    if st.session_state.get("upload_excel") or st.session_state.get("upload_template"):
        return True
    return False


def _needs_workflow_change_confirm() -> bool:
    return _has_generated_report() or _has_loaded_inputs()


def render_workflow_banner(mode: WorkflowMode) -> None:
    """Compact reminder of the active workflow with a switch control."""
    if st.session_state.get("confirm_workflow_change"):
        if _has_generated_report():
            st.warning(
                "You have a generated report in this session. Switching workflows clears "
                "uploads, folder state, and download buttons."
            )
        else:
            st.warning(
                "You have loaded files in this session. Switching workflows clears "
                "uploads, folder state, and sidebar progress."
            )
        yes, no = st.columns(2)
        if yes.button("Yes, switch workflow", type="primary", key="confirm_workflow_yes"):
            st.session_state.pop("confirm_workflow_change", None)
            _reset_workflow_session()
            st.rerun()
        if no.button("Cancel", key="confirm_workflow_no"):
            st.session_state.pop("confirm_workflow_change", None)
            st.rerun()
        return

    left, right = st.columns([5, 1])
    with left:
        if mode == WORKFLOW_FOLDER:
            path = st.session_state.get("project_folder_path") or ""
            extra = f" · `{path}`" if path else ""
            st.info(f"**{workflow_label(mode)}**{extra}")
        else:
            st.info(f"**{workflow_label(mode)}** — upload Excel and template below")
    with right:
        if st.button("Change", width="stretch", key="change_workflow_mode"):
            if _needs_workflow_change_confirm():
                st.session_state.confirm_workflow_change = True
            else:
                _reset_workflow_session()
            st.rerun()


def render_workflow_hint(mode: WorkflowMode) -> None:
    if mode == WORKFLOW_FOLDER:
        st.markdown(
            "**Steps:** Sidebar settings → **Browse…** (loads immediately) or paste path + "
            "**Load folder** → optional **Analyze folder** → **Report** tab → download"
        )
    else:
        st.markdown(
            "**Steps:** Sidebar settings → **upload Excel + template** → **Report** tab "
            "(pre-flight & generate) → download · **AI tools** tab optional"
        )


def _set_workflow(mode: WorkflowMode) -> None:
    _reset_workflow_session()
    st.session_state.workflow_mode = mode
    st.rerun()


def _clear_upload_session() -> None:
    for key in ("upload_excel", "upload_template"):
        st.session_state.pop(key, None)
    for key in list(st.session_state.keys()):
        if isinstance(key, str) and key.startswith("tpl_"):
            st.session_state.pop(key, None)
    st.session_state.pop("last_prepared_template", None)
    st.session_state.pop("suggested_template_version", None)


def _clear_generation_session() -> None:
    for key in (
        "generated_docx",
        "generated_filename",
        "warnings",
        "last_context",
        "generation_record",
        "generated_batch",
        "generated_appendices",
        "batch_reports_zip",
        "batch_deliverable_zip",
        "rendering",
    ):
        st.session_state.pop(key, None)


def _reset_workflow_session() -> None:
    clear_folder_session()
    _clear_upload_session()
    _clear_generation_session()
    st.session_state.pop("workflow_mode", None)
    st.session_state.pop("_preflight_result_cache", None)
    st.session_state.pop("_report_engine_cache", None)
    st.session_state.pop("_upload_digest_cache", None)
    st.session_state.pop("_upload_bytes_cache", None)
    st.session_state.pop("_template_analysis_cache", None)
    st.session_state.pop("confirm_workflow_change", None)
