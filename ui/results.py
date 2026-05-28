from __future__ import annotations

from typing import Any

import streamlit as st

from provenance import GenerationRecord, record_filename
from ui.helpers import format_size

from engine import BatchReportResult

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


_LIST_KEYS = ("lab_results", "drilling_waste", "storage_tanks")


def render_context_preview(context: dict[str, Any], *, max_rows: int = 15) -> None:
    rows = [
        {"key": k, "value": str(v)[:200]}
        for k, v in sorted(context.items())
        if k not in _LIST_KEYS
    ][:max_rows]
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    for key in _LIST_KEYS:
        data = context.get(key)
        if isinstance(data, list) and data:
            st.caption(f"{key}: {len(data)} row(s) (table loop data)")


def render_batch_download_section(batch: list[BatchReportResult] | None) -> None:
    if not batch:
        return
    from deliverable_pack import build_batch_reports_zip

    st.subheader(f"Batch output ({len(batch)} reports)")
    zip_entries: list[tuple[str, bytes, bytes | None]] = []
    all_warnings: list[str] = []
    for item in batch:
        zip_entries.append(
            (item.filename, item.docx_bytes, item.record.to_json_bytes())
        )
        all_warnings.extend(item.warnings)
    zip_bytes = build_batch_reports_zip(zip_entries)
    zip_name = f"esa_reports_batch_{len(batch)}.zip"
    st.download_button(
        label=f"Download all reports (.zip, {len(batch)} files)",
        data=zip_bytes,
        file_name=zip_name,
        mime="application/zip",
        type="primary",
        use_container_width=True,
    )
    if all_warnings:
        with st.expander("Batch warnings", expanded=False):
            for w in all_warnings[:40]:
                st.warning(w)
            if len(all_warnings) > 40:
                st.caption(f"... and {len(all_warnings) - 40} more")
    with st.expander("Individual reports", expanded=False):
        for item in batch:
            st.caption(item.row_label)
            st.download_button(
                label=f"Download {item.filename}",
                data=item.docx_bytes,
                file_name=item.filename,
                mime=DOCX_MIME,
                key=f"batch_dl_{item.project_row_index}_{item.filename}",
                use_container_width=True,
            )


def render_download_section(
    docx_bytes: bytes | None,
    filename: str | None,
    warnings: list[str],
    context: dict[str, Any] | None,
    generation_record: GenerationRecord | None = None,
) -> None:
    if warnings:
        with st.expander("Warnings (missing tags filled with blank)", expanded=True):
            for w in warnings:
                st.warning(w)

    if not docx_bytes:
        return

    st.download_button(
        label="Download Report (.docx)",
        data=docx_bytes,
        file_name=filename or "esa_report.docx",
        mime=DOCX_MIME,
        type="primary",
        use_container_width=True,
    )

    if generation_record:
        st.download_button(
            "Download generation manifest (JSON)",
            data=generation_record.to_json_bytes(),
            file_name=record_filename(filename),
            mime="application/json",
            use_container_width=True,
        )

    with st.expander("What was filled", expanded=False):
        if context:
            render_context_preview(context)
        st.caption(f"Output size: {format_size(len(docx_bytes))}")
        if generation_record:
            st.caption(
                f"Provenance: template v{generation_record.template_version or 'n/a'} · "
                f"{generation_record.matched_var_count}/{generation_record.template_var_count} tags matched"
            )
