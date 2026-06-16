from __future__ import annotations

import logging
from typing import Any

import streamlit as st

from appendix_generator import attach_appendices_to_record
from deliverable_pack import build_batch_deliverable_packages_zip, build_batch_reports_zip
from engine import suggested_download_name
from security import (
    MAX_EXCEL_BYTES,
    _template_size_limit,
    user_safe_error,
)
from provenance import sha256_hex
from ui.ai_panel import render_ai_panel, render_ai_settings_sidebar
from ui.appendix_panel import render_appendix_uploader, render_deliverable_downloads
from ui.helpers import (
    cached_upload_bytes,
    get_cached_report_engine,
    render_template_analysis,
)
from ui.project_folder import get_folder_render_bytes, merge_folder_meta, render_project_folder_step
from ui.preflight import render_preflight_panel, run_preflight_check
from ui.preview import render_preview_panel
from ui.results import render_batch_download_section, render_download_section
from ui.phrase_panel import render_phrase_panel
from ui.sidebar import render_sidebar
from ui.branding import favicon_path, render_app_footer, render_app_header
from ui.workflow_mode import (
    WORKFLOW_FOLDER,
    get_workflow_mode,
    render_workflow_banner,
    render_workflow_hint,
    render_workflow_picker,
)
from ui.layout import (
    render_generate_cta,
    render_outputs_section_header,
    render_phrase_expander,
    render_upload_step,
    render_section_header,
)

logger = logging.getLogger(__name__)


def _init_state() -> None:
    defaults: dict[str, Any] = {
        "generated_docx": None,
        "generated_filename": None,
        "warnings": [],
        "rendering": False,
        "last_context": None,
        "generation_record": None,
        "ai_audit_log": [],
        "template_prep_warnings": [],
        "last_prepared_template": None,
        "generated_batch": None,
        "generated_appendices": [],
        "batch_reports_zip": None,
        "batch_deliverable_zip": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _file_ext_ok(name: str, ext: str) -> bool:
    return name.lower().endswith(ext)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _icon = favicon_path()
    st.set_page_config(
        page_title="ESA Report Generator | Ecoventure",
        page_icon=_icon or "📄",
        layout="wide",
    )
    _init_state()
    render_app_header()

    mode = get_workflow_mode()
    if mode is None:
        render_workflow_picker()
        render_app_footer()
        return

    render_workflow_banner(mode)
    render_workflow_hint(mode)

    render_ai_settings_sidebar(folder_mode=(mode == WORKFLOW_FOLDER))
    meta = render_sidebar()

    if mode == WORKFLOW_FOLDER:
        folder_files = render_project_folder_step()
        meta = merge_folder_meta(meta)
        if folder_files:
            excel_file, template_file, prepared_tpl, template_prep_warnings = folder_files
        else:
            excel_file, template_file, prepared_tpl, template_prep_warnings = (
                None,
                None,
                None,
                [],
            )
    else:
        excel_file, template_file, prepared_tpl, template_prep_warnings = render_upload_step()

    folder_excel_bytes, folder_template_bytes = (
        get_folder_render_bytes() if mode == WORKFLOW_FOLDER else (None, None)
    )
    excel_bytes = folder_excel_bytes or (
        cached_upload_bytes(excel_file, slot="excel") if excel_file else None
    )
    template_bytes = folder_template_bytes or (
        prepared_tpl.docx_bytes if prepared_tpl else None
    )

    tab_labels = (
        ["Report", "AI drafts & tools"]
        if mode == WORKFLOW_FOLDER
        else ["Report", "AI tools"]
    )
    tab_report, tab_ai = st.tabs(tab_labels)

    meta_render = dict(meta)
    preflight = None

    with tab_report:
        phrase_meta = render_phrase_expander(render_phrase_panel)
        meta_render = {**meta, **phrase_meta}
        if prepared_tpl:
            meta_render["template_source_format"] = prepared_tpl.source_format
        preflight = run_preflight_check(excel_bytes, template_bytes, meta_render)

        _render_report_tab(
            meta,
            meta_render=meta_render,
            excel_file=excel_file,
            template_file=template_file,
            excel_bytes=excel_bytes,
            template_bytes=template_bytes,
            prepared_tpl=prepared_tpl,
            preflight=preflight,
            template_prep_warnings=template_prep_warnings,
            folder_mode=(mode == WORKFLOW_FOLDER),
        )

    with tab_ai:
        if mode == WORKFLOW_FOLDER and not excel_bytes:
            st.info(
                "Load a project folder above first. Use **Analyze folder** for AI drafts "
                "saved to `ai_drafts/`, or use the tools here after loading Excel + template."
            )
        render_ai_panel(
            excel_bytes=excel_bytes,
            template_bytes=template_bytes,
            meta=meta_render,
            preflight=preflight,
            folder_mode=(mode == WORKFLOW_FOLDER),
        )

    render_app_footer()


def _render_report_tab(
    meta: dict[str, str],
    *,
    meta_render: dict[str, str],
    excel_file: Any,
    template_file: Any,
    excel_bytes: bytes | None,
    template_bytes: bytes | None,
    prepared_tpl: Any,
    preflight: Any,
    template_prep_warnings: list[str],
    folder_mode: bool = False,
) -> None:
    st.divider()
    render_section_header(
        2,
        "Review pre-flight",
        caption="Blocking errors must be fixed before generate is enabled.",
    )
    can_generate = render_preflight_panel(
        preflight,
        report_phase=meta.get("report_phase", "Phase 1"),
        report_type=meta.get("report_type", ""),
    )

    project_row_count = 1
    project_row_labels: list[str] = []
    if preflight and preflight.project_row_count > 0:
        project_row_count = preflight.project_row_count
        project_row_labels = list(preflight.project_row_labels)
    elif excel_bytes and template_bytes and preflight is None:
        try:
            _row_engine = get_cached_report_engine(excel_bytes, template_bytes)
            project_row_count = _row_engine.project_row_count(meta_render)
            project_row_labels = _row_engine.project_row_labels(meta_render)
        except Exception:
            project_row_count = 1
            project_row_labels = []

    generate_clicked, batch_mode, project_row_index = render_generate_cta(
        can_generate=can_generate,
        rendering=st.session_state.rendering,
        has_excel=excel_file is not None,
        has_template=template_file is not None,
        project_row_count=project_row_count,
        project_row_labels=project_row_labels,
    )

    if generate_clicked:
        _run_generation(
            meta_render=meta_render,
            excel_file=excel_file,
            template_file=template_file,
            excel_bytes=excel_bytes,
            template_bytes=template_bytes,
            prepared_tpl=prepared_tpl,
            template_prep_warnings=template_prep_warnings,
            batch_mode=batch_mode,
            project_row_count=project_row_count,
            project_row_index=project_row_index,
        )

    if st.session_state.generated_docx or st.session_state.get("generated_batch"):
        st.divider()
        render_outputs_section_header()

    render_batch_download_section(st.session_state.get("generated_batch"), meta=meta_render)
    render_download_section(
        st.session_state.generated_docx,
        st.session_state.generated_filename,
        st.session_state.warnings,
        st.session_state.last_context,
        st.session_state.generation_record,
    )
    render_deliverable_downloads(
        st.session_state.generated_docx,
        st.session_state.generated_filename,
        st.session_state.generation_record,
        prepared_template=prepared_tpl or st.session_state.get("last_prepared_template"),
        render_context=st.session_state.get("last_context"),
        render_meta=meta_render,
    )

    with st.expander("Optional tools", expanded=False):
        render_preview_panel(
            excel_bytes,
            template_bytes,
            meta_render,
            excel_name=excel_file.name if excel_file else "",
            template_name=template_file.name if template_file else "",
        )
        st.divider()
        render_appendix_uploader()
        st.divider()
        render_template_analysis(template_bytes)

    with st.expander("Help & documentation", expanded=False):
        folder_doc = (
            "| Project folder | [docs/22-project-folder-workflow.md](docs/22-project-folder-workflow.md) |\n"
            if folder_mode
            else ""
        )
        st.markdown(
            f"""
| Topic | Guide |
|-------|--------|
| Workflow | [docs/02-user-guide.md](docs/02-user-guide.md) |
{folder_doc}| Excel layout | [docs/03-excel-data-guide.md](docs/03-excel-data-guide.md) |
| Word templates | [docs/04-template-authoring.md](docs/04-template-authoring.md) |
| Phase I Alberta | [docs/11-alberta-phase1-esa.md](docs/11-alberta-phase1-esa.md) |
"""
        )


def _run_generation(
    *,
    meta_render: dict[str, str],
    excel_file: Any,
    template_file: Any,
    excel_bytes: bytes | None,
    template_bytes: bytes | None,
    prepared_tpl: Any,
    template_prep_warnings: list[str],
    batch_mode: bool,
    project_row_count: int,
    project_row_index: int,
) -> None:
    if st.session_state.rendering:
        st.warning("A report is already being generated. Please wait.")
        st.stop()

    st.session_state.generated_docx = None
    st.session_state.generated_filename = None
    st.session_state.warnings = []
    st.session_state.last_context = None
    st.session_state.generation_record = None
    st.session_state.generated_batch = None
    st.session_state.generated_appendices = []

    if not _file_ext_ok(excel_file.name, ".xlsx"):
        st.error("Excel file must have a .xlsx extension.")
        st.stop()
    if not template_bytes:
        st.error("Template could not be prepared. Check file type (.docx or .pdf).")
        st.stop()

    if getattr(excel_file, "size", None) and excel_file.size > MAX_EXCEL_BYTES:
        st.error(f"Excel file too large (max {MAX_EXCEL_BYTES // (1024 * 1024)} MB).")
        st.stop()
    tpl_limit = _template_size_limit()
    prepared_size = len(template_bytes) if template_bytes else 0
    upload_size = getattr(template_file, "size", None) or prepared_size
    if prepared_size > tpl_limit or upload_size > tpl_limit:
        shown_mb = max(prepared_size, upload_size) / (1024 * 1024)
        st.error(
            f"Template too large (max {tpl_limit // (1024 * 1024)} MB). "
            f"Prepared Word file is {shown_mb:.1f} MB."
        )
        st.info(
            "Use `python scripts\\phase1_pdf_to_markup.py --for-streamlit` "
            "and upload the `*-markup-upload.docx` file."
        )
        st.stop()

    st.session_state.rendering = True
    try:
        engine = get_cached_report_engine(
            excel_bytes or b"",
            template_bytes or b"",
        )
        uploaded_appendices = list(st.session_state.get("appendix_files", {}).values())
        ai_audit = list(st.session_state.get("ai_audit_log") or [])

        if batch_mode and project_row_count > 1:
            with st.spinner(f"Rendering {project_row_count} reports..."):
                batch = engine.render_batch(
                    meta=meta_render,
                    excel_filename=excel_file.name,
                    template_filename=template_file.name,
                )
            folder_path = st.session_state.get("project_folder_resolved") or ""
            for item in batch:
                item.record.output_sha256 = sha256_hex(item.docx_bytes)
                item.record.template_source_format = (
                    prepared_tpl.source_format if prepared_tpl else ""
                )
                if folder_path:
                    item.record.project_folder = folder_path
                generated, merged, ap_warnings = attach_appendices_to_record(
                    item.record, item.context, meta_render, uploaded_appendices
                )
                item.appendices = merged
                item.warnings.extend(ap_warnings)
                item.record.ai_audit = ai_audit
            st.session_state.generated_batch = batch
            st.session_state.generated_appendices = []
            st.session_state.generated_docx = None
            st.session_state.generated_filename = None
            st.session_state.generation_record = None
            zip_entries = [
                (
                    item.filename,
                    item.docx_bytes,
                    item.record.to_json_bytes(),
                    item.appendices,
                )
                for item in batch
            ]
            st.session_state.batch_reports_zip = build_batch_reports_zip(zip_entries)
            st.session_state.batch_deliverable_zip = (
                build_batch_deliverable_packages_zip(batch, meta_render)
            )
            st.session_state.warnings = [w for item in batch for w in item.warnings]
            n_warn = len(template_prep_warnings) + len(st.session_state.warnings)
            st.success(
                f"**{len(batch)}** reports ready — download the ZIP in step 4 below "
                f"({n_warn} warning(s))."
            )
            logger.info("Batch rendered %d reports", len(batch))
        else:
            with st.spinner("Rendering report..."):
                docx_bytes, warnings, context, record = engine.render(
                    meta=meta_render,
                    excel_filename=excel_file.name,
                    template_filename=template_file.name,
                    project_row_index=project_row_index,
                )
            out_name = suggested_download_name(context, meta_render)
            record.output_filename = out_name
            record.output_sha256 = sha256_hex(docx_bytes)
            record.template_source_format = (
                prepared_tpl.source_format if prepared_tpl else ""
            )
            if st.session_state.get("project_folder_resolved"):
                record.project_folder = st.session_state.project_folder_resolved
            generated, merged, ap_warnings = attach_appendices_to_record(
                record, context, meta_render, uploaded_appendices
            )
            st.session_state.generated_appendices = generated
            st.session_state.generated_batch = None
            st.session_state.batch_reports_zip = None
            st.session_state.batch_deliverable_zip = None
            warnings = list(warnings) + ap_warnings
            record.ai_audit = ai_audit
            st.session_state.generated_docx = docx_bytes
            st.session_state.warnings = warnings
            st.session_state.last_context = context
            st.session_state.generation_record = record
            st.session_state.generated_filename = out_name
            n_warn = len(template_prep_warnings) + len(warnings)
            st.success(
                f"**{out_name}** is ready — download in step 4 below "
                f"({n_warn} warning(s))."
            )
            logger.info("Rendered %s with %d warnings", out_name, len(warnings))
    except Exception as e:
        logger.exception("Report generation failed")
        st.error(user_safe_error(e))
        with st.expander("Common fixes"):
            st.markdown(
                """
- Add `ProjectData` (and `LabResults` for Phase II)
- Re-type split `{{ tags }}` in Word as one piece
- Match Excel column headers to template variable names
- Use **Optional tools** or the **AI tools** tab for help
"""
            )
    finally:
        st.session_state.rendering = False


if __name__ == "__main__":
    main()
