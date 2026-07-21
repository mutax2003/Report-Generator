"""Startup workflow choice: project folder + AI vs Excel + template upload."""

from __future__ import annotations

from typing import Literal

import os

import streamlit as st

from ui.project_folder import clear_folder_session

WorkflowMode = Literal["folder", "upload"]

WORKFLOW_FOLDER: WorkflowMode = "folder"
WORKFLOW_UPLOAD: WorkflowMode = "upload"

_LABELS = {
    WORKFLOW_FOLDER: "Project folder + AI",
    WORKFLOW_UPLOAD: "Excel + Word template",
}


def hosted_mode_enabled() -> bool:
    """True on shared/docker/Streamlit Cloud hosts where local folder paths are unavailable."""
    for key in ("ESA_HOSTED_MODE", "ESA_DISABLE_FOLDER_WORKFLOW"):
        if os.environ.get(key, "").strip().lower() in ("1", "true", "yes"):
            return True
        try:
            if key in st.secrets and str(st.secrets[key]).strip().lower() in (
                "1",
                "true",
                "yes",
            ):
                return True
        except Exception:
            # No secrets.toml / Streamlit secrets not configured
            pass
    return False


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

    if hosted_mode_enabled():
        st.caption(
            "This server uses the **Excel + Word template** workflow. "
            "Upload your `.xlsx` and `.docx` (or PDF template) in the browser."
        )
        with st.container(border=True):
            st.markdown("#### Excel + Word template")
            st.markdown(
                "Upload **Excel** and a **Word or PDF template**, review pre-flight, "
                "then download a **deliverable package (.zip)**."
            )
            if st.button(
                "Continue with Excel + template",
                type="primary",
                width="stretch",
                key="pick_workflow_upload",
            ):
                _set_workflow(WORKFLOW_UPLOAD)
        return

    st.caption(
        "Pick one path to start. You can switch later — loaded files will be cleared."
    )

    col_folder, col_upload = st.columns(2, gap="large")

    with col_folder:
        with st.container(border=True):
            st.markdown("#### Project folder + AI")
            st.markdown(
                "Work from a **local site folder** with `project_data.xlsx`, "
                "`template.docx`, and PDFs in `source/` and `appendices/`. "
                "Optional AI drafts save to `ai_drafts/` before you generate."
            )
            st.caption(
                "Best for full site packages (260109R-style folders). "
                "See [project folder workflow](docs/22-project-folder-workflow.md)."
            )
            if st.button(
                "Use project folder workflow",
                type="secondary",
                width="stretch",
                key="pick_workflow_folder",
            ):
                _set_workflow(WORKFLOW_FOLDER)

    with col_upload:
        with st.container(border=True):
            st.markdown("#### Excel + Word template  ·  *Recommended for first report*")
            st.markdown(
                "Upload **Excel** and a **Word or PDF template** in the browser. "
                "Review pre-flight, generate, and download a **deliverable package (.zip)**."
            )
            st.caption(
                "Best for one-off merges, testing, and batch runs when Excel has multiple sites."
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
| First time using the app | **Excel + Word template** — try **Load Alberta Phase I sample** in the sidebar |
| You have a project folder with `source/`, `appendices/`, etc. | **Project folder + AI** |
| You only have one `.xlsx` and one `.docx` to merge | **Excel + Word template** |
| You want AI narrative drafts saved under `ai_drafts/` | **Project folder + AI** |

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
    if st.session_state.get("session_excel_bytes"):
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
    """One-line path reminder after the welcome card is dismissed."""
    if not st.session_state.get("ux_welcome_dismissed"):
        return
    if mode == WORKFLOW_FOLDER:
        st.caption(
            "Path: Settings → **Load folder** → **Report** tab → download **deliverable package (.zip)**"
        )
    else:
        st.caption(
            "Path: upload Excel + template → **Report** tab → download **deliverable package (.zip)**"
        )


def _set_workflow(mode: WorkflowMode) -> None:
    _reset_workflow_session()
    st.session_state.workflow_mode = mode
    st.session_state.show_welcome = True
    st.rerun()


def _clear_upload_session() -> None:
    for key in ("upload_excel", "upload_template"):
        st.session_state.pop(key, None)
    for key in list(st.session_state.keys()):
        if isinstance(key, str) and key.startswith("tpl_"):
            st.session_state.pop(key, None)
    st.session_state.pop("last_prepared_template", None)
    st.session_state.pop("suggested_template_version", None)
    from ui.helpers import clear_session_sample_bytes

    clear_session_sample_bytes()


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
        "deliverable_zip_bytes",
        "enriched_manifest_bytes",
        "ux_deliverable_download_clicked",
    ):
        st.session_state.pop(key, None)
    st.session_state["rendering"] = False


def clear_generation_session() -> None:
    """Public alias for menu / external callers."""
    _clear_generation_session()


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
    st.session_state.pop("_ecoventure_merged_cache", None)
    st.session_state.pop("_ai_excel_context_cache", None)


def reset_workflow_session() -> None:
    """Public alias for menu / external callers."""
    _reset_workflow_session()
