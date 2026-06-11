from __future__ import annotations

from typing import Any

import streamlit as st

from provenance import GenerationRecord, record_filename
from ui.helpers import format_size

from engine import BatchReportResult

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _appendix_generation_warnings(warnings: list[str]) -> list[str]:
    return [w for w in warnings if "Appendix" in w and "not generated" in w]


def _render_appendix_warning_callout(warnings: list[str]) -> None:
    ap_warns = _appendix_generation_warnings(warnings)
    if ap_warns:
        for w in ap_warns:
            st.warning(w)


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


def render_batch_download_section(
    batch: list[BatchReportResult] | None,
    *,
    meta: dict[str, str] | None = None,
) -> None:
    if not batch:
        return
    from deliverable_pack import build_batch_deliverable_packages_zip, build_batch_reports_zip

    with st.container(border=True):
        st.markdown(f"### Batch package · {len(batch)} reports")
        zip_entries: list[tuple[str, bytes, bytes | None, list]] = []
        all_warnings: list[str] = []
        appendix_sites = 0
        for item in batch:
            zip_entries.append(
                (
                    item.filename,
                    item.docx_bytes,
                    item.record.to_json_bytes(),
                    item.appendices,
                )
            )
            if item.appendices:
                appendix_sites += 1
            all_warnings.extend(item.warnings)
        zip_bytes = build_batch_reports_zip(zip_entries)
        zip_name = f"esa_reports_batch_{len(batch)}.zip"
        cap = f"Download all as ZIP ({len(batch)} reports"
        if appendix_sites:
            cap += f", {appendix_sites} with appendices"
        cap += ")"
        st.download_button(
            label=cap,
            data=zip_bytes,
            file_name=zip_name,
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )
        deliverable_zip = build_batch_deliverable_packages_zip(batch, meta)
        st.download_button(
            label=f"Download all deliverable packages ({len(batch)} sites)",
            data=deliverable_zip,
            file_name=f"esa_deliverables_batch_{len(batch)}.zip",
            mime="application/zip",
            use_container_width=True,
        )
        st.caption(
            "Deliverable packages include report, manifest, auto-generated appendices, "
            "and OneStop export per site."
        )
        _render_appendix_warning_callout(all_warnings)
        if all_warnings:
            with st.expander("Batch warnings", expanded=False):
                for w in all_warnings[:40]:
                    st.warning(w)
                if len(all_warnings) > 40:
                    st.caption(f"... and {len(all_warnings) - 40} more")
        with st.expander("Individual reports", expanded=False):
            for item in batch:
                st.download_button(
                    label=item.filename,
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
    if not docx_bytes:
        return

    with st.container(border=True):
        st.markdown(f"### {filename or 'esa_report.docx'}")
        st.caption(f"Size: {format_size(len(docx_bytes))}")
        st.download_button(
            label="Download report (.docx)",
            data=docx_bytes,
            file_name=filename or "esa_report.docx",
            mime=DOCX_MIME,
            type="primary",
            use_container_width=True,
        )
        if generation_record:
            st.download_button(
                "Download manifest (.json)",
                data=generation_record.to_json_bytes(),
                file_name=record_filename(filename),
                mime="application/json",
                use_container_width=True,
            )
        if generation_record:
            st.caption(
                f"Tags matched: {generation_record.matched_var_count}/"
                f"{generation_record.template_var_count} · "
                f"template v{generation_record.template_version or 'n/a'}"
            )

    _render_appendix_warning_callout(warnings)
    if warnings:
        with st.expander(
            f"Warnings ({len(warnings)}) — review before client delivery",
            expanded=len(warnings) <= 3,
        ):
            for w in warnings:
                st.warning(w)

    with st.expander("What was filled (preview)", expanded=False):
        if context:
            render_context_preview(context)
