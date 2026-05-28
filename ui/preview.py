"""Dry-run preview (context + manifest without rendering Word)."""

from __future__ import annotations

import streamlit as st

from provenance import GenerationRecord, record_filename
from security import user_safe_error
from ui.helpers import format_size, get_cached_report_engine
from ui.results import render_context_preview


def render_preview_panel(
    excel_bytes: bytes | None,
    template_bytes: bytes | None,
    meta: dict[str, str],
    excel_name: str = "",
    template_name: str = "",
) -> None:
    if not excel_bytes or not template_bytes:
        return

    if st.button("Preview data (dry run)", use_container_width=True):
        try:
            engine = get_cached_report_engine(excel_bytes, template_bytes)
            row_index = int(st.session_state.get("projectdata_row_select", 0))
            with st.spinner("Building context (no Word render)..."):
                context, warnings, record = engine.dry_run(
                    meta=meta,
                    excel_filename=excel_name,
                    template_filename=template_name,
                    project_row_index=row_index,
                )
            st.session_state["dry_run_context"] = context
            st.session_state["dry_run_warnings"] = warnings
            st.session_state["dry_run_record"] = record
            st.success("Dry run complete — review context and manifest below.")
        except Exception as e:
            st.error(user_safe_error(e))

    context = st.session_state.get("dry_run_context")
    record: GenerationRecord | None = st.session_state.get("dry_run_record")
    warnings: list[str] = st.session_state.get("dry_run_warnings") or []

    if not context and not record:
        return

    with st.expander("Dry-run: merge context preview", expanded=True):
        if warnings:
            for w in warnings:
                st.warning(w)
        scalar_keys = [
            k for k, v in (context or {}).items()
            if not str(k).startswith("_") and not isinstance(v, list)
        ]
        st.caption(f"Scalar fields: {len(scalar_keys)} · previewing top 10")
        render_context_preview(context or {}, max_rows=10)
        for key in ("lab_results", "drilling_waste", "storage_tanks"):
            data = (context or {}).get(key)
            if isinstance(data, list):
                st.metric(key, len(data))
        if record:
            st.caption(
                f"Excel SHA-256: `{record.excel_sha256[:16]}…` · "
                f"Template SHA-256: `{record.template_sha256[:16]}…`"
            )
            st.download_button(
                "Download generation manifest (JSON)",
                data=record.to_json_bytes(),
                file_name=record_filename("preview.docx"),
                mime="application/json",
                use_container_width=True,
            )
            with st.expander("Manifest JSON", expanded=False):
                st.json(record.to_dict())

