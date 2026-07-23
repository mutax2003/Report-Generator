from __future__ import annotations

import logging
from typing import Any

import streamlit as st

from compliance_helpers import normalize_appendix_labels
from deliverable_pack import build_batch_deliverable_packages_zip, build_batch_reports_zip
from engine import suggested_download_name
from provenance import GenerationRecord, sha256_hex
from render_service import (
    RenderRequest,
    finalize_deliverable_package,
    render_batch_reports,
    render_report,
)
from security import MAX_BATCH_REPORTS, MAX_EXCEL_BYTES, _template_size_limit, user_safe_error
from ui.ai_panel import render_ai_panel, render_ai_settings_sidebar
from ui.appendix_panel import render_appendix_step
from ui.helpers import (
    cached_upload_bytes,
    effective_excel_bytes,
    get_cached_report_engine,
    prepare_session_template,
    render_template_analysis,
    resolve_session_excel_file,
    resolve_session_template_file,
    session_loaded_file_names,
)
from ui.onboarding import (
    compute_next_actions,
    render_glossary_expander,
    render_input_status_chips,
    render_next_actions_card,
    render_welcome_card,
)
from ui.project_folder import get_folder_render_bytes, merge_folder_meta, render_project_folder_step
from ui.preflight import (
    render_preflight_panel,
    regulatory_compliance_warnings,
    run_preflight_check,
)
from ui.preview import render_preview_panel
from ui.results import render_batch_deliverable_success, render_deliverable_success
from ui.phrase_panel import render_phrase_panel
from ui.sidebar import render_sidebar
from ui.branding import favicon_path, render_app_footer, render_app_header
from ui.menubar import process_menubar_actions, render_menubar
from ui.workflow_mode import (
    WORKFLOW_FOLDER,
    WORKFLOW_UPLOAD,
    get_workflow_mode,
    hosted_mode_enabled,
    render_workflow_banner,
    render_workflow_hint,
    render_workflow_picker,
    workflow_label,
)
from ui.layout import (
    compute_workflow_step,
    render_generate_cta,
    render_outputs_section_header,
    render_phrase_expander,
    render_upload_step,
    render_section_header,
    render_workflow_context_strip,
    render_workflow_stepper,
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
        "deliverable_zip_bytes": None,
        "enriched_manifest_bytes": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _file_ext_ok(name: str, ext: str) -> bool:
    return name.lower().endswith(ext)


def _has_generated_output() -> bool:
    return bool(st.session_state.get("generated_docx") or st.session_state.get("generated_batch"))


def _project_row_info(
    preflight: Any,
    excel_bytes: bytes | None,
    template_bytes: bytes | None,
    meta_render: dict[str, str],
) -> tuple[int, list[str]]:
    if preflight and preflight.project_row_count > 0:
        return preflight.project_row_count, list(preflight.project_row_labels)
    if excel_bytes and template_bytes:
        try:
            engine = get_cached_report_engine(excel_bytes, template_bytes)
            return (
                engine.project_row_count(meta_render),
                engine.project_row_labels(meta_render),
            )
        except Exception:
            pass
    return 1, []


def main() -> None:
    from esa_logging import configure_logging

    configure_logging()
    _icon = favicon_path()
    st.set_page_config(
        page_title="ESA Report Generator | Ecoventure",
        page_icon=_icon or "📄",
        layout="wide",
    )
    _init_state()
    render_app_header()

    # Apply menu actions before reading workflow mode (avoids stale-mode + extra rerun).
    process_menubar_actions()
    mode = get_workflow_mode()
    render_menubar(folder_mode=(mode == WORKFLOW_FOLDER))

    if mode is None:
        render_workflow_picker()
        render_app_footer()
        return

    if hosted_mode_enabled() and mode == WORKFLOW_FOLDER:
        st.warning(
            "Project folder workflow is disabled on this hosted server. "
            "Switch to Excel + template upload."
        )
        st.session_state.workflow_mode = WORKFLOW_UPLOAD
        mode = WORKFLOW_UPLOAD
        st.rerun()

    render_workflow_banner(mode)
    render_workflow_hint(mode)
    render_welcome_card(mode)

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
        excel_file = resolve_session_excel_file(excel_file)
        template_file = resolve_session_template_file(template_file)
        if template_file and prepared_tpl is None:
            prepared_tpl, extra_warn = prepare_session_template()
            template_prep_warnings = list(extra_warn)

    folder_excel_bytes, folder_template_bytes = (
        get_folder_render_bytes() if mode == WORKFLOW_FOLDER else (None, None)
    )
    excel_bytes = folder_excel_bytes or (
        cached_upload_bytes(excel_file, slot="excel") if excel_file else None
    )
    excel_bytes = effective_excel_bytes(excel_bytes)
    template_bytes = folder_template_bytes or (prepared_tpl.docx_bytes if prepared_tpl else None)
    if not template_bytes and template_file:
        template_bytes = cached_upload_bytes(template_file, slot="template")

    has_excel = bool(excel_bytes)
    has_template = bool(template_bytes)

    meta_render = dict(meta)
    if prepared_tpl:
        meta_render["template_source_format"] = prepared_tpl.source_format
    if has_excel and has_template:
        phrase_meta = render_phrase_expander(render_phrase_panel)
        meta_render.update(phrase_meta)

    preflight = run_preflight_check(excel_bytes, template_bytes, meta_render)

    ex_name, tpl_name = session_loaded_file_names()
    profile_label = str(
        (meta_render or {}).get("report_type")
        or meta.get("report_type")
        or st.session_state.get("report_type_sel")
        or ""
    )
    site_label = str(
        (meta_render or {}).get("project_name")
        or (meta_render or {}).get("site_name")
        or meta.get("project_name")
        or ""
    )
    render_workflow_context_strip(
        mode_label=workflow_label(mode),
        profile_label=profile_label.replace("_", " ") if profile_label else "",
        excel_name=ex_name or "",
        template_name=tpl_name or "",
        site_label=site_label,
    )
    render_workflow_stepper(
        compute_workflow_step(
            has_excel=has_excel,
            has_template=has_template,
            preflight_ok=None if preflight is None else preflight.can_generate,
            has_output=_has_generated_output(),
        )
    )

    tab_labels = (
        ["Report", "AI drafts & tools"] if mode == WORKFLOW_FOLDER else ["Report", "AI tools"]
    )
    tab_report, tab_ai = st.tabs(tab_labels)

    with tab_report:
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
    report_phase = meta.get("report_phase", "Phase 1")
    report_type = meta.get("report_type", "")
    has_excel = bool(excel_bytes)
    has_template = bool(template_bytes)
    has_output = _has_generated_output()

    render_input_status_chips(has_excel=has_excel, has_template=has_template)
    render_next_actions_card(
        compute_next_actions(
            preflight,
            has_excel=has_excel,
            has_template=has_template,
            has_output=has_output,
            report_phase=report_phase,
            report_type=report_type,
            prepared_by=meta.get("prepared_by", ""),
        )
    )

    st.divider()
    render_section_header(
        2,
        "Review pre-flight",
        caption=(
            "**Errors** block Generate. **Warnings** (missing tags, regulatory gaps) "
            "allow Generate — review recommended."
        ),
    )
    can_generate = render_preflight_panel(
        preflight,
        report_phase=report_phase,
        report_type=report_type,
        meta=meta_render,
        excel_bytes=excel_bytes,
        template_bytes=template_bytes,
    )

    project_row_count, project_row_labels = _project_row_info(
        preflight, excel_bytes, template_bytes, meta_render
    )

    generate_clicked, batch_mode, project_row_index = render_generate_cta(
        can_generate=can_generate,
        rendering=st.session_state.rendering,
        has_excel=has_excel,
        has_template=has_template,
        project_row_count=project_row_count,
        project_row_labels=project_row_labels,
        template_bytes=template_bytes,
        prepared_by=meta.get("prepared_by", ""),
    )

    from ui.onboarding import is_simple_mode

    # Appendices after Generate so the primary CTA is not buried (collapsed in Simple mode).
    appendix_expanded = False if is_simple_mode() else None
    render_appendix_step(
        report_type=report_type,
        show_header=False,
        expanded=appendix_expanded,
    )
    st.caption(
        "Optional: expand **Appendices** for OneStop PDFs (B/C/E/F/H). "
        "A/D/G auto-generate when you Generate."
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
            preflight=preflight,
        )

    if _has_generated_output():
        st.divider()
        render_outputs_section_header()
        render_batch_deliverable_success(
            st.session_state.get("generated_batch"),
            meta=meta_render,
            warnings=st.session_state.warnings,
        )
        render_deliverable_success(
            st.session_state.generated_docx,
            st.session_state.generated_filename,
            st.session_state.warnings,
            st.session_state.last_context,
            st.session_state.generation_record,
            prepared_template=prepared_tpl or st.session_state.get("last_prepared_template"),
            render_meta=meta_render,
            report_phase=report_phase,
        )

    with st.expander("Advanced", expanded=False):
        render_preview_panel(
            excel_bytes,
            template_bytes,
            meta_render,
            excel_name=excel_file.name if excel_file else "",
            template_name=template_file.name if template_file else "",
        )
        st.divider()
        render_template_analysis(template_bytes)
        render_glossary_expander()

    with st.expander("Help & documentation", expanded=False):
        from ui.workflow_mode import hosted_mode_enabled

        if hosted_mode_enabled():
            st.caption(
                "On Streamlit Community Cloud, **F1 / Help → Contents** cannot open local "
                "`file://` help. Use the links below (or SharePoint Guides)."
            )
        folder_doc = (
            "| Project folder | [docs/22-project-folder-workflow.md](docs/22-project-folder-workflow.md) |\n"
            if folder_mode and not hosted_mode_enabled()
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


def _streamlit_render_request(
    *,
    excel_bytes: bytes | None,
    template_bytes: bytes | None,
    meta_render: dict[str, str],
    excel_filename: str,
    template_filename: str,
    uploaded_appendices: list[Any],
    uploaded_labels: frozenset[str],
    project_row_index: int = 0,
    emit_audit: bool = True,
) -> RenderRequest:
    engine = None
    if excel_bytes and template_bytes:
        try:
            engine = get_cached_report_engine(excel_bytes, template_bytes)
        except Exception:
            engine = None
    return RenderRequest(
        excel_bytes=excel_bytes or b"",
        template_bytes=template_bytes or b"",
        meta=meta_render,
        excel_filename=excel_filename,
        template_filename=template_filename,
        project_row_index=project_row_index,
        uploaded_appendices=uploaded_appendices,
        appendix_labels_present=uploaded_labels,
        engine=engine,
        emit_audit=emit_audit,
    )


def _stamp_generation_record(
    record: GenerationRecord,
    docx_bytes: bytes,
    *,
    prepared_tpl: Any,
    folder_path: str,
    ai_audit: list[Any],
    output_filename: str | None = None,
) -> None:
    if output_filename:
        record.output_filename = output_filename
    record.output_sha256 = sha256_hex(docx_bytes)
    record.template_source_format = prepared_tpl.source_format if prepared_tpl else ""
    if folder_path:
        record.project_folder = folder_path
    record.ai_audit = ai_audit


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
    preflight: Any = None,
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
    st.session_state.deliverable_zip_bytes = None
    st.session_state.enriched_manifest_bytes = None

    for msg in regulatory_compliance_warnings(preflight):
        st.warning(msg)

    if batch_mode and project_row_count > MAX_BATCH_REPORTS:
        st.error(
            f"Batch mode supports at most **{MAX_BATCH_REPORTS}** sites per run "
            f"({project_row_count} rows on ProjectData). Use single-site mode or split the Excel file."
        )
        return

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
        uploaded_appendices = list(st.session_state.get("appendix_files", {}).values())
        ai_audit = list(st.session_state.get("ai_audit_log") or [])
        uploaded_labels = normalize_appendix_labels(ap.label for ap in uploaded_appendices)
        folder_path = st.session_state.get("project_folder_resolved") or ""
        render_req = _streamlit_render_request(
            excel_bytes=excel_bytes,
            template_bytes=template_bytes,
            meta_render=meta_render,
            excel_filename=excel_file.name,
            template_filename=template_file.name,
            uploaded_appendices=uploaded_appendices,
            uploaded_labels=uploaded_labels,
            project_row_index=project_row_index,
            # Single-site path audits once in finalize_deliverable_package.
            emit_audit=bool(batch_mode and project_row_count > 1),
        )

        if batch_mode and project_row_count > 1:
            with st.spinner(f"Rendering {project_row_count} reports..."):
                batch = render_batch_reports(render_req)
            for item in batch:
                _stamp_generation_record(
                    item.record,
                    item.docx_bytes,
                    prepared_tpl=prepared_tpl,
                    folder_path=folder_path,
                    ai_audit=ai_audit,
                )
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
            st.session_state.batch_deliverable_zip = build_batch_deliverable_packages_zip(
                batch, meta_render
            )
            st.session_state.warnings = [w for item in batch for w in item.warnings]
            n_warn = len(template_prep_warnings) + len(st.session_state.warnings)
            st.success(
                f"**{len(batch)}** reports ready — download the **deliverable package (.zip)** below "
                f"({n_warn} warning(s))."
            )
            logger.info("Batch rendered %d reports", len(batch))
        else:
            with st.spinner("Rendering report..."):
                result = render_report(render_req)
            out_name = suggested_download_name(result.context, meta_render)
            tpl_fmt = getattr(prepared_tpl, "source_format", "") or ""
            result = finalize_deliverable_package(
                result,
                render_req,
                report_filename=out_name,
                template_source_format=tpl_fmt,
            )
            _stamp_generation_record(
                result.record,
                result.docx_bytes,
                prepared_tpl=prepared_tpl,
                folder_path=folder_path,
                ai_audit=ai_audit,
                output_filename=out_name,
            )
            st.session_state.generated_appendices = [
                ap for ap in result.appendices if ap.source == "generated"
            ]
            st.session_state.generated_batch = None
            st.session_state.batch_reports_zip = None
            st.session_state.batch_deliverable_zip = None
            st.session_state.generated_docx = result.docx_bytes
            st.session_state.warnings = list(result.warnings)
            st.session_state.last_context = result.context
            st.session_state.generation_record = result.record
            st.session_state.generated_filename = out_name
            st.session_state.deliverable_zip_bytes = result.package_bytes
            st.session_state.enriched_manifest_bytes = result.enriched_manifest_bytes
            n_warn = len(template_prep_warnings) + len(result.warnings)
            st.success(
                f"**{out_name}** is ready — download the **deliverable package (.zip)** below "
                f"({n_warn} warning(s))."
            )
            logger.info("Rendered %s with %d warnings", out_name, len(result.warnings))
    except Exception as e:
        logger.exception("Report generation failed")
        st.error(user_safe_error(e))
        with st.expander("Common fixes", expanded=True):
            st.markdown(
                """
**Fix Excel columns or Word tags, then Generate again.**

- Add `ProjectData` (and `LabResults` for Phase II)
- Re-type split `{{ tags }}` in Word as one piece
- Match Excel column headers to template variable names
"""
            )
            cov = getattr(preflight, "coverage", None) if preflight is not None else None
            if cov is not None and getattr(cov, "missing_in_data", None):
                from report_profile import build_report_config_workbook_bytes
                from template_tools import missing_fields_checklist

                rt = (meta_render or {}).get("report_type") or "phase1_alberta"
                d1, d2 = st.columns(2)
                with d1:
                    st.download_button(
                        "Missing-fields checklist",
                        data=missing_fields_checklist(cov, report_type=rt),
                        file_name="missing_excel_columns.txt",
                        mime="text/plain",
                        width="stretch",
                        key="gen_fail_missing_checklist",
                    )
                with d2:
                    st.download_button(
                        "ReportConfig sheet",
                        data=build_report_config_workbook_bytes(rt),
                        file_name=f"report_config_{rt}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        width="stretch",
                        key="gen_fail_report_config",
                    )
            st.caption("Optional: use the **AI tools** tab for tagger / copilot help.")
    finally:
        st.session_state.rendering = False


if __name__ == "__main__":
    main()
