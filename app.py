from __future__ import annotations

import logging
from typing import Any

import streamlit as st

from engine import ReportEngine, suggested_download_name
from security import (
    MAX_EXCEL_BYTES,
    MAX_TEMPLATE_BYTES,
    user_safe_error,
)
from provenance import sha256_hex
from ui.ai_panel import render_ai_panel, render_ai_settings_sidebar
from ui.appendix_panel import render_appendix_uploader, render_deliverable_downloads
from ui.helpers import (
    parse_template_version_from_filename,
    prepare_uploaded_template,
    render_converted_template_download,
    render_template_analysis,
    show_upload_status,
)
from ui.preflight import render_preflight_panel, run_preflight_check
from ui.preview import render_preview_panel
from ui.results import render_download_section
from ui.sidebar import render_sidebar
from ui.workflow import render_workflow_step

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
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _file_ext_ok(name: str, ext: str) -> bool:
    return name.lower().endswith(ext)


def _prepare_template_from_upload(template_file: Any) -> tuple[Any, list[str]]:
    prepared_tpl = None
    template_bytes = None
    template_prep_warnings: list[str] = []
    if template_file is None:
        return None, template_prep_warnings
    try:
        prepared_tpl = prepare_uploaded_template(template_file)
        template_bytes = prepared_tpl.docx_bytes
        template_prep_warnings = list(prepared_tpl.warnings)
        st.session_state.last_prepared_template = prepared_tpl
        st.session_state.template_prep_warnings = template_prep_warnings
        ver = parse_template_version_from_filename(template_file.name or "")
        if ver:
            st.session_state.suggested_template_version = ver
    except Exception as e:
        st.error(user_safe_error(e))
    return prepared_tpl, template_prep_warnings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    st.set_page_config(page_title="ESA Report Generator", layout="wide")
    _init_state()

    st.title("ESA Report Generator")
    st.caption(
        "Ecoventure Inc. — Alberta O&G Phase I / II. Upload Excel + Word or PDF template "
        "(PDF is converted to Word for merging), review pre-flight, then generate."
    )

    render_ai_settings_sidebar()
    meta = render_sidebar()

    col1, col2 = st.columns(2)
    with col1:
        excel_file = st.file_uploader(
            "Excel Data Source (.xlsx)", type=["xlsx"], accept_multiple_files=False
        )
        show_upload_status("Excel", excel_file)
    with col2:
        template_file = st.file_uploader(
            "Report template (.docx or .pdf)",
            type=["docx", "pdf"],
            accept_multiple_files=False,
            help="Word (.docx) with Jinja2 tags is preferred. PDF is converted to Word for merge; add tags after conversion if needed.",
        )
        prepared_tpl, template_prep_warnings = _prepare_template_from_upload(template_file)
        template_bytes = prepared_tpl.docx_bytes if prepared_tpl else None
        tpl_extra = ""
        if prepared_tpl and prepared_tpl.source_format == "pdf":
            tpl_extra = "PDF → Word for merge"
        show_upload_status("Template", template_file, extra=tpl_extra)
        for w in template_prep_warnings:
            st.info(w)
        render_converted_template_download(prepared_tpl)

    excel_bytes = excel_file.getvalue() if excel_file else None
    meta_render = dict(meta)
    if prepared_tpl:
        meta_render["template_source_format"] = prepared_tpl.source_format
    preflight = run_preflight_check(excel_bytes, template_bytes, meta)

    tab_report, tab_ai = st.tabs(["Report generation", "AI assistant"])

    with tab_ai:
        render_ai_panel(
            excel_bytes=excel_bytes,
            template_bytes=template_bytes,
            meta=meta,
            preflight=preflight,
        )

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
        )


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
) -> None:
    render_template_analysis(template_bytes)
    can_generate = render_preflight_panel(
        preflight,
        report_phase=meta.get("report_phase", "Phase 1"),
        report_type=meta.get("report_type", ""),
    )

    render_workflow_step(
        has_excel=excel_file is not None,
        has_template=template_file is not None,
        preflight_ok=preflight.can_generate if preflight else None,
        has_output=st.session_state.generated_docx is not None,
    )

    render_preview_panel(
        excel_bytes,
        template_bytes,
        meta_render,
        excel_name=excel_file.name if excel_file else "",
        template_name=template_file.name if template_file else "",
    )

    render_appendix_uploader()

    st.divider()

    generate_disabled = (
        st.session_state.rendering
        or excel_file is None
        or template_file is None
        or not can_generate
    )

    generate_clicked = st.button(
        "Generate Report",
        type="primary",
        use_container_width=True,
        disabled=generate_disabled,
    )

    template_prep_warnings = st.session_state.get("template_prep_warnings") or []

    if generate_clicked:
        if st.session_state.rendering:
            st.warning("A report is already being generated. Please wait.")
            st.stop()

        st.session_state.generated_docx = None
        st.session_state.generated_filename = None
        st.session_state.warnings = []
        st.session_state.last_context = None
        st.session_state.generation_record = None

        if not _file_ext_ok(excel_file.name, ".xlsx"):
            st.error("Excel file must have a .xlsx extension.")
            st.stop()
        if not template_bytes:
            st.error("Template could not be prepared. Check file type (.docx or .pdf).")
            st.stop()

        if getattr(excel_file, "size", None) and excel_file.size > MAX_EXCEL_BYTES:
            st.error(f"Excel file too large (max {MAX_EXCEL_BYTES // (1024 * 1024)} MB).")
            st.stop()
        if getattr(template_file, "size", None) and template_file.size > MAX_TEMPLATE_BYTES:
            st.error(
                f"Template file too large (max {MAX_TEMPLATE_BYTES // (1024 * 1024)} MB)."
            )
            st.stop()

        st.session_state.rendering = True
        try:
            engine = ReportEngine(
                excel_bytes=excel_bytes or b"",
                template_bytes=template_bytes or b"",
            )
            with st.spinner("Rendering report..."):
                docx_bytes, warnings, context, record = engine.render(
                    meta=meta_render,
                    excel_filename=excel_file.name,
                    template_filename=template_file.name,
                )
            out_name = suggested_download_name(context, meta)
            record.output_filename = out_name
            record.output_sha256 = sha256_hex(docx_bytes)
            record.template_source_format = (
                prepared_tpl.source_format if prepared_tpl else ""
            )
            from deliverable_pack import appendix_manifest_entries

            appendices = list(st.session_state.get("appendix_files", {}).values())
            if appendices:
                record.appendix_files = appendix_manifest_entries(appendices)
            record.ai_audit = list(st.session_state.get("ai_audit_log") or [])
            st.session_state.generated_docx = docx_bytes
            st.session_state.warnings = warnings
            st.session_state.last_context = context
            st.session_state.generation_record = record
            st.session_state.generated_filename = out_name
            all_warnings = list(template_prep_warnings) + list(warnings)
            st.success(
                f"Report generated ({len(all_warnings)} warning(s)). "
                f"File: **{st.session_state.generated_filename}**"
            )
            logger.info(
                "Rendered %s with %d warnings",
                st.session_state.generated_filename,
                len(warnings),
            )
        except Exception as e:
            logger.exception("Report generation failed")
            st.error(user_safe_error(e))
            with st.expander("Common fixes"):
                st.markdown(
                    """
- Add sheets `ProjectData` and `LabResults` (Phase 2) per EXCEL_LAYOUT.txt
- Fix split `{{ tags }}` in Word (re-type each tag in one piece)
- Match Excel column headers to template variable names
- Use **Analyze uploaded Word template** above to list required tags
- Use the **AI assistant** tab for tagging help, lab PDF import, and QA
"""
                )
        finally:
            st.session_state.rendering = False

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
    )

    with st.expander("Documentation & template help"):
        st.markdown(
            """
**Full documentation:** [docs/README.md](docs/README.md) — user guide, Excel, Word templates, API, security, testing.

| Quick topic | Doc |
|-------------|-----|
| Streamlit workflow | [docs/02-user-guide.md](docs/02-user-guide.md) |
| Excel sheets | [docs/03-excel-data-guide.md](docs/03-excel-data-guide.md) |
| Word / Jinja2 | [docs/04-template-authoring.md](docs/04-template-authoring.md) |
| Deployment | [docs/14-deployment.md](docs/14-deployment.md) |
| Power Automate | [docs/15-power-automate-guide.md](docs/15-power-automate-guide.md) |
| FAQ | [docs/10-glossary-faq.md](docs/10-glossary-faq.md) |

**Excel** — `ProjectData` row 1 headers, row 2 values; `LabResults` for Phase 2.

**Table loop** — static header row, then `{%tr for item in lab_results %}`, data row, `{%tr endfor %}`.
"""
        )


if __name__ == "__main__":
    main()
