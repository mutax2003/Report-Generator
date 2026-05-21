from __future__ import annotations

from typing import Any

import streamlit as st

from provenance import GenerationRecord, record_filename
from ui.helpers import format_size

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
