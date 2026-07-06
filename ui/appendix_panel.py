"""Appendix PDF uploads and deliverable package download."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from ui.helpers import cached_upload_bytes

from appendix_generator import merge_appendix_lists
from deliverable_pack import AppendixFile, DeliverablePackage, build_deliverable_zip
from deliverable_pack import enrich_manifest_dict
from provenance import GenerationRecord, record_filename, sha256_hex

APPENDIX_LABELS = ("A", "B", "C", "D", "E", "F", "G", "H")
PDF_MIME = "application/pdf"
DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
ZIP_MIME = "application/zip"


def appendix_labels_from_session() -> set[str]:
    """Labels of appendix PDFs currently uploaded in session state."""
    store = st.session_state.get("appendix_files") or {}
    return set(store.keys())


def all_appendix_labels_from_session() -> set[str]:
    """Uploaded + auto-generated appendix labels in session state."""
    labels = set(appendix_labels_from_session())
    for ap in st.session_state.get("generated_appendices") or []:
        labels.add(ap.label.upper())
    return labels


def all_appendices_from_session() -> list[AppendixFile]:
    """Merge generated appendices with uploads (upload wins on same label)."""
    generated = list(st.session_state.get("generated_appendices") or [])
    uploaded = list((st.session_state.get("appendix_files") or {}).values())
    return merge_appendix_lists(generated, uploaded)


def _init_appendix_state() -> None:
    if "appendix_files" not in st.session_state:
        st.session_state.appendix_files = {}
    if "generated_appendices" not in st.session_state:
        st.session_state.generated_appendices = []


def render_generated_appendix_downloads() -> None:
    """Download buttons for auto-generated appendix Word files."""
    generated: list[AppendixFile] = st.session_state.get("generated_appendices") or []
    if not generated:
        return
    st.subheader("Generated appendices")
    st.caption(
        "Appendices A, D, and G are rendered from Excel and sidebar data. "
        "Export each .docx to PDF in Word before OneStop submission."
    )
    for ap in generated:
        mime = DOCX_MIME if ap.format == "docx" else PDF_MIME
        st.download_button(
            f"Download Appendix {ap.label} ({ap.format.upper()})",
            data=ap.data,
            file_name=ap.filename,
            mime=mime,
            key=f"download_generated_appendix_{ap.label}",
            width="stretch",
        )


def render_appendix_step(
    *,
    report_type: str = "",
    expanded: bool | None = None,
    show_header: bool = False,
) -> list[AppendixFile]:
    """Step-level appendix uploader (Report tab main path)."""
    _init_appendix_state()
    if show_header:
        st.caption(
            "Upload PDF appendices for the deliverable package (Phase I: B, C, E, F, H). "
            "Auto-generated A, D, G are included when you generate."
        )
    store: dict[str, AppendixFile] = st.session_state.appendix_files
    has_uploads = bool(store)
    if expanded is None:
        expanded = report_type == "phase1_alberta" or has_uploads

    with st.expander("Appendices (PDF uploads)", expanded=expanded):
        st.caption(
            "Upload PDF appendices **B, C, E, F, H** (and others as needed). "
            "Appendices **A, D, and G** can be auto-generated from Excel when you generate. "
            "Included in the deliverable package at step 4."
        )
        for label in APPENDIX_LABELS:
            uploaded = st.file_uploader(
                f"Appendix {label} (PDF)"
                + (" — auto-generated if empty" if label in ("D", "G") else ""),
                type=["pdf"],
                key=f"appendix_upload_{label}",
                accept_multiple_files=False,
            )
            if uploaded is not None:
                data = cached_upload_bytes(uploaded, slot=f"appendix_{label}") or b""
                store[label] = AppendixFile(
                    label=label,
                    data=data,
                    filename=uploaded.name or f"appendix_{label}.pdf",
                    format="pdf",
                    source="uploaded",
                )
            elif label in store:
                del store[label]
        if st.button("Clear all appendices", width="stretch", key="clear_appendix_step"):
            st.session_state.appendix_files = {}
            st.rerun()
    return list(store.values())


def render_appendix_uploader() -> list[AppendixFile]:
    """Collect labeled appendix PDFs from session state (legacy / optional tools)."""
    return render_appendix_step(expanded=False)


def render_deliverable_downloads(
    docx_bytes: bytes | None,
    filename: str | None,
    generation_record: GenerationRecord | None,
    *,
    prepared_template: Any = None,
    render_context: dict | None = None,
    render_meta: dict | None = None,
) -> None:
    if not docx_bytes:
        return

    appendices = all_appendices_from_session()
    if not appendices and not generation_record:
        return

    render_generated_appendix_downloads()

    st.subheader("Deliverable package")
    manifest_bytes = None
    manifest_name = record_filename(filename)
    fmt = ""
    if prepared_template is not None:
        fmt = getattr(prepared_template, "source_format", "") or ""
    if generation_record:
        rec_dict = generation_record.to_dict()
        rec_dict = enrich_manifest_dict(
            rec_dict,
            template_source_format=fmt,
            appendices=appendices,
        )
        manifest_bytes = json.dumps(rec_dict, indent=2, sort_keys=True).encode("utf-8")

    pkg = DeliverablePackage(
        report_docx=docx_bytes,
        report_filename=filename or "esa_report.docx",
        manifest_bytes=manifest_bytes,
        manifest_filename=manifest_name,
        appendices=appendices,
        render_context=render_context,
        render_meta=render_meta,
        include_onestop_export=bool(render_context),
        converted_template_docx=(
            prepared_template.docx_bytes if prepared_template and prepared_template.source_format == "pdf" else None
        ),
        converted_template_name=(
            (prepared_template.source_filename or "converted.docx").rsplit(".", 1)[0] + "_converted.docx"
            if prepared_template and prepared_template.source_format == "pdf"
            else None
        ),
    )
    cache_key = (
        sha256_hex(docx_bytes),
        manifest_bytes and sha256_hex(manifest_bytes) or "",
        tuple(sorted((a.label, a.sha256) for a in appendices)),
        bool(render_context),
        fmt,
    )
    if st.session_state.get("_deliverable_zip_key") != cache_key:
        st.session_state._deliverable_zip_key = cache_key
        st.session_state._deliverable_zip_bytes = build_deliverable_zip(pkg)
    zip_bytes = st.session_state._deliverable_zip_bytes
    st.download_button(
        "Download deliverable package (.zip)",
        data=zip_bytes,
        file_name=(filename or "esa_report").rsplit(".", 1)[0] + "_package.zip",
        mime=ZIP_MIME,
        width="stretch",
        help="Contains report .docx, manifest JSON, appendices/, and onestop/ summary export.",
    )

    if appendices:
        gen_n = sum(1 for a in appendices if a.source == "generated")
        up_n = len(appendices) - gen_n
        parts = []
        if gen_n:
            parts.append(f"{gen_n} generated")
        if up_n:
            parts.append(f"{up_n} uploaded")
        st.caption(
            f"{len(appendices)} appendix file(s) in package ({', '.join(parts)}). "
            "Export generated .docx appendices to PDF in Word before OneStop upload."
        )
