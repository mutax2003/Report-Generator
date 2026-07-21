from __future__ import annotations

from typing import Any

import streamlit as st

from provenance import GenerationRecord, record_filename
from ui.appendix_panel import (
    AUTO_GENERATED_LABELS,
    PHASE1_ONESTOP_APPENDIX_LABELS,
    all_appendices_from_session,
    appendix_package_caption,
    build_deliverable_zip_for_session,
    generated_appendix_labels,
    render_generated_appendix_downloads,
    _mark_deliverable_download,
)
from ui.helpers import format_size

from engine import BatchReportResult

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ZIP_MIME = "application/zip"


def _appendix_generation_warnings(warnings: list[str]) -> list[str]:
    return [w for w in warnings if "Appendix" in w and "not generated" in w]


def _render_appendix_warning_callout(warnings: list[str]) -> None:
    for w in _appendix_generation_warnings(warnings):
        st.warning(w)


def _render_checklist(title: str, items: list[str]) -> None:
    st.markdown(f"**{title}**")
    for item in items:
        st.markdown(f"- ☐ {item}")


_LIST_KEYS = ("lab_results", "drilling_waste", "storage_tanks")


def render_context_preview(context: dict[str, Any], *, max_rows: int = 15) -> None:
    rows = [
        {"key": k, "value": str(v)[:200]}
        for k, v in sorted(context.items())
        if k not in _LIST_KEYS
    ][:max_rows]
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    for key in _LIST_KEYS:
        data = context.get(key)
        if isinstance(data, list) and data:
            st.caption(f"{key}: {len(data)} row(s) (table loop data)")


def _onestop_checklist_items(
    *,
    warnings: list[str],
    report_phase: str = "Phase 1",
) -> list[str]:
    items: list[str] = []
    if warnings:
        items.append(f"Review {len(warnings)} generation warning(s) listed below.")
    items.append("Open the report in Word and review any generation warnings.")
    for label in sorted(generated_appendix_labels() & AUTO_GENERATED_LABELS):
        items.append(f"Export Appendix {label} to PDF in Word before OneStop upload.")
    if report_phase.strip() == "Phase 1":
        present = {a.label.upper() for a in all_appendices_from_session()}
        missing = [lb for lb in PHASE1_ONESTOP_APPENDIX_LABELS if lb not in present]
        if missing:
            items.append(
                f"Confirm appendices {', '.join(missing)} are PDFs in the package (upload if missing)."
            )
        else:
            items.append(
                f"Confirm appendices {', '.join(PHASE1_ONESTOP_APPENDIX_LABELS)} are in the zip as PDFs."
            )
    items.append("Upload package contents to AER OneStop when QP review is complete.")
    return items


def render_deliverable_success(
    docx_bytes: bytes | None,
    filename: str | None,
    warnings: list[str],
    context: dict[str, Any] | None,
    generation_record: GenerationRecord | None = None,
    *,
    prepared_template: Any = None,
    render_meta: dict[str, str] | None = None,
    report_phase: str = "Phase 1",
) -> None:
    """Unified step-4 download: primary zip, OneStop checklist, advanced downloads."""
    if not docx_bytes:
        return

    zip_bytes = st.session_state.get("deliverable_zip_bytes")
    if zip_bytes:
        zip_name = (filename or "esa_report").rsplit(".", 1)[0] + "_package.zip"
    else:
        zip_bytes, zip_name = build_deliverable_zip_for_session(
            docx_bytes,
            filename,
            generation_record,
            prepared_template=prepared_template,
            render_context=context,
            render_meta=render_meta,
        )

    with st.container(border=True):
        st.markdown("### Your report is ready")
        st.caption(f"**{filename or 'esa_report.docx'}** · {format_size(len(docx_bytes))}")
        st.download_button(
            label="Download deliverable package (.zip)",
            data=zip_bytes,
            file_name=zip_name,
            mime=ZIP_MIME,
            type="primary",
            width="stretch",
            help="Report .docx, manifest JSON, appendices/, and OneStop export.",
            on_click=_mark_deliverable_download,
        )
        st.info(
            "**First:** open the zip and review the Word report. "
            "Then complete the OneStop checklist below before upload."
        )
        _render_checklist(
            "Before OneStop upload",
            _onestop_checklist_items(warnings=warnings, report_phase=report_phase),
        )
        if cap := appendix_package_caption():
            st.caption(cap)

    _render_appendix_warning_callout(warnings)
    if warnings:
        with st.expander(
            f"Warnings ({len(warnings)}) — review before client delivery",
            expanded=len(warnings) <= 3,
        ):
            for w in warnings:
                st.warning(w)

    with st.expander("Advanced downloads", expanded=False):
        st.download_button(
            label="Download report (.docx)",
            data=docx_bytes,
            file_name=filename or "esa_report.docx",
            mime=DOCX_MIME,
            width="stretch",
        )
        if generation_record:
            manifest_bytes = st.session_state.get("enriched_manifest_bytes")
            if manifest_bytes is None:
                manifest_bytes = generation_record.to_json_bytes()
            st.download_button(
                "Download manifest (.json)",
                data=manifest_bytes,
                file_name=record_filename(filename),
                mime="application/json",
                width="stretch",
            )
            st.caption(
                f"Tags matched: {generation_record.matched_var_count}/"
                f"{generation_record.template_var_count} · "
                f"template v{generation_record.template_version or 'n/a'}"
            )
        render_generated_appendix_downloads()
        if context:
            st.divider()
            st.markdown("**What was filled (preview)**")
            render_context_preview(context)


def render_batch_deliverable_success(
    batch: list[BatchReportResult] | None,
    *,
    meta: dict[str, str] | None = None,
    warnings: list[str] | None = None,
) -> None:
    if not batch:
        return
    from deliverable_pack import build_batch_deliverable_packages_zip, build_batch_reports_zip

    all_warnings = warnings if warnings is not None else [
        w for item in batch for w in item.warnings
    ]

    with st.container(border=True):
        st.markdown(f"### Batch package · {len(batch)} reports ready")
        deliverable_zip = st.session_state.get("batch_deliverable_zip")
        if deliverable_zip is None:
            deliverable_zip = build_batch_deliverable_packages_zip(batch, meta)
        st.download_button(
            label=f"Download all deliverable packages ({len(batch)} sites)",
            data=deliverable_zip,
            file_name=f"esa_deliverables_batch_{len(batch)}.zip",
            mime=ZIP_MIME,
            type="primary",
            width="stretch",
            on_click=_mark_deliverable_download,
        )
        st.caption(
            "Each site folder includes report, manifest, appendices, and OneStop export."
        )
        _render_checklist("Before OneStop upload", _onestop_checklist_items(warnings=all_warnings))

    with st.expander("Advanced batch downloads", expanded=False):
        zip_bytes = st.session_state.get("batch_reports_zip")
        if zip_bytes is None:
            zip_entries = [
                (item.filename, item.docx_bytes, item.record.to_json_bytes(), item.appendices)
                for item in batch
            ]
            zip_bytes = build_batch_reports_zip(zip_entries)
        st.download_button(
            label=f"Download reports only (.docx zip, {len(batch)} files)",
            data=zip_bytes,
            file_name=f"esa_reports_batch_{len(batch)}.zip",
            mime=ZIP_MIME,
            width="stretch",
        )
        with st.expander("Individual reports", expanded=False):
            for item in batch:
                st.download_button(
                    label=item.filename,
                    data=item.docx_bytes,
                    file_name=item.filename,
                    mime=DOCX_MIME,
                    key=f"batch_dl_{item.project_row_index}_{item.filename}",
                    width="stretch",
                )

    _render_appendix_warning_callout(all_warnings)
    if all_warnings:
        with st.expander("Batch warnings", expanded=False):
            for w in all_warnings[:40]:
                st.warning(w)
            if len(all_warnings) > 40:
                st.caption(f"... and {len(all_warnings) - 40} more")


# Legacy aliases for external callers / docs
render_batch_download_section = render_batch_deliverable_success


def render_download_section(
    docx_bytes: bytes | None,
    filename: str | None,
    warnings: list[str],
    context: dict[str, Any] | None,
    generation_record: GenerationRecord | None = None,
    **kwargs: Any,
) -> None:
    render_deliverable_success(
        docx_bytes,
        filename,
        warnings,
        context,
        generation_record,
        **kwargs,
    )
