"""Appendix PDF uploads and deliverable package download."""

from __future__ import annotations

from typing import Any

import streamlit as st

from deliverable_pack import AppendixFile, DeliverablePackage, build_deliverable_zip
from deliverable_pack import enrich_manifest_dict
from provenance import GenerationRecord, record_filename

APPENDIX_LABELS = ("A", "B", "C", "D", "E", "F")
PDF_MIME = "application/pdf"
ZIP_MIME = "application/zip"


def _init_appendix_state() -> None:
    if "appendix_files" not in st.session_state:
        st.session_state.appendix_files = {}


def render_appendix_uploader() -> list[AppendixFile]:
    """Collect labeled appendix PDFs from session state."""
    _init_appendix_state()
    st.subheader("Appendices (optional)")
    st.caption(
        "Upload PDF appendices A–F (Alberta Phase I). Included in the deliverable zip; "
        "optional combined PDF merges report + appendices when report is PDF."
    )
    store: dict[str, AppendixFile] = st.session_state.appendix_files
    for label in APPENDIX_LABELS:
        uploaded = st.file_uploader(
            f"Appendix {label} (PDF)",
            type=["pdf"],
            key=f"appendix_upload_{label}",
            accept_multiple_files=False,
        )
        if uploaded is not None:
            data = uploaded.getvalue()
            store[label] = AppendixFile(
                label=label,
                data=data,
                filename=uploaded.name or f"appendix_{label}.pdf",
            )
        elif label in store and f"appendix_upload_{label}" not in st.session_state:
            pass
    if st.button("Clear all appendices", use_container_width=True):
        st.session_state.appendix_files = {}
        st.rerun()
    return list(store.values())


def render_deliverable_downloads(
    docx_bytes: bytes | None,
    filename: str | None,
    generation_record: GenerationRecord | None,
    *,
    prepared_template: Any = None,
) -> None:
    if not docx_bytes:
        return

    appendices = list(st.session_state.get("appendix_files", {}).values())
    if not appendices and not generation_record:
        return

    st.subheader("Deliverable package")
    manifest_bytes = None
    manifest_name = record_filename(filename)
    if generation_record:
        rec_dict = generation_record.to_dict()
        fmt = ""
        if prepared_template is not None:
            fmt = getattr(prepared_template, "source_format", "") or ""
        rec_dict = enrich_manifest_dict(
            rec_dict,
            template_source_format=fmt,
            appendices=appendices,
        )
        import json

        manifest_bytes = json.dumps(rec_dict, indent=2, sort_keys=True).encode("utf-8")

    pkg = DeliverablePackage(
        report_docx=docx_bytes,
        report_filename=filename or "esa_report.docx",
        manifest_bytes=manifest_bytes,
        manifest_filename=manifest_name,
        appendices=appendices,
        converted_template_docx=(
            prepared_template.docx_bytes if prepared_template and prepared_template.source_format == "pdf" else None
        ),
        converted_template_name=(
            (prepared_template.source_filename or "converted.docx").rsplit(".", 1)[0] + "_converted.docx"
            if prepared_template and prepared_template.source_format == "pdf"
            else None
        ),
    )
    zip_bytes = build_deliverable_zip(pkg)
    st.download_button(
        "Download deliverable package (.zip)",
        data=zip_bytes,
        file_name=(filename or "esa_report").rsplit(".", 1)[0] + "_package.zip",
        mime=ZIP_MIME,
        use_container_width=True,
        help="Contains report .docx, manifest JSON, and appendices/ folder.",
    )

    if appendices:
        st.caption(
            f"{len(appendices)} appendix PDF(s) in package. "
            "Export the Word report to PDF separately to build a single merged PDF."
        )
