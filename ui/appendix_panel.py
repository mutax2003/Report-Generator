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
PHASE1_ONESTOP_APPENDIX_LABELS = ("B", "C", "E", "F", "H")
AUTO_GENERATED_LABELS = frozenset({"A", "D", "G"})
PDF_MIME = "application/pdf"
DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
ZIP_MIME = "application/zip"


def _mark_deliverable_download() -> None:
    st.session_state.ux_deliverable_download_clicked = True


def generated_appendix_labels() -> set[str]:
    """Uppercase labels of auto-generated appendices in session."""
    return {
        ap.label.upper()
        for ap in (st.session_state.get("generated_appendices") or [])
        if getattr(ap, "source", "") == "generated"
    }


def first_missing_onestop_label(
    uploaded: set[str],
    predicted: set[str],
) -> str | None:
    """First B/C/E/F/H label not uploaded and not auto-generated."""
    for label in PHASE1_ONESTOP_APPENDIX_LABELS:
        if label not in uploaded and label not in predicted:
            return label
    return None


def appendix_package_caption() -> str | None:
    """Summary line for deliverable package appendix counts."""
    appendices = all_appendices_from_session()
    if not appendices:
        return None
    gen_n = sum(1 for a in appendices if a.source == "generated")
    up_n = len(appendices) - gen_n
    parts: list[str] = []
    if gen_n:
        parts.append(f"{gen_n} generated")
    if up_n:
        parts.append(f"{up_n} uploaded")
    return f"{len(appendices)} appendix file(s) in package ({', '.join(parts)})."


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
        render_section_header(
            "For OneStop, you typically need **B, C, E, F, H** as PDFs. "
            "**A, D, G** are auto-generated from Excel when you generate."
        )
    store: dict[str, AppendixFile] = st.session_state.appendix_files
    has_uploads = bool(store)
    generated_labels = {
        ap.label.upper() for ap in (st.session_state.get("generated_appendices") or [])
    }
    if expanded is None:
        expanded = report_type == "phase1_alberta" or has_uploads

    with st.expander("Appendices (optional PDF uploads)", expanded=expanded):
        _render_appendix_checklist_row(store, generated_labels)
        st.divider()
        for label in APPENDIX_LABELS:
            kind, short = _appendix_status(label, store, generated_labels)
            hint = ""
            if label in AUTO_GENERATED_LABELS:
                hint = " — auto-generated from Excel if empty"
            with st.expander(f"Appendix {label} — {short}{hint}", expanded=False):
                uploaded = st.file_uploader(
                    f"Upload Appendix {label} (PDF)",
                    type=["pdf"],
                    key=f"appendix_upload_{label}",
                    accept_multiple_files=False,
                    label_visibility="collapsed",
                )
                if uploaded is not None:
                    data = cached_upload_bytes(uploaded, slot=f"appendix_{label}") or b""
                    from security import SecurityError, user_safe_error, validate_appendix_pdf_upload

                    try:
                        validate_appendix_pdf_upload(
                            data, uploaded.name or f"appendix_{label}.pdf"
                        )
                    except SecurityError as exc:
                        st.error(user_safe_error(exc))
                        if label in store:
                            del store[label]
                    else:
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


def render_section_header(caption: str) -> None:
    st.caption(caption)


def _appendix_status(
    label: str,
    store: dict[str, AppendixFile],
    generated_labels: set[str],
) -> tuple[str, str]:
    """Return (badge_kind, short_label) for OneStop appendix status."""
    if label in store:
        return "ok", "uploaded"
    if label in generated_labels:
        return "ok", "generated"
    if label in AUTO_GENERATED_LABELS:
        return "info", "auto on Generate"
    if label in PHASE1_ONESTOP_APPENDIX_LABELS:
        return "warn", "missing"
    return "muted", "optional"


def _render_appendix_checklist_row(
    store: dict[str, AppendixFile],
    generated_labels: set[str],
) -> None:
    """OneStop-focused status row for B, C, E, F, H."""
    from ui.branding import status_badge_html

    st.markdown("**OneStop appendices**")
    cols = st.columns(len(PHASE1_ONESTOP_APPENDIX_LABELS))
    for col, label in zip(cols, PHASE1_ONESTOP_APPENDIX_LABELS):
        with col:
            kind, short = _appendix_status(label, store, generated_labels)
            st.markdown(
                f"**{label}**  \n{status_badge_html(kind, short)}",
                unsafe_allow_html=True,
            )
    st.caption("A, D, G: auto-generated at Generate (expand individual rows to upload overrides).")


def render_appendix_uploader() -> list[AppendixFile]:
    """Collect labeled appendix PDFs from session state (legacy / optional tools)."""
    return render_appendix_step(expanded=False)


def build_deliverable_zip_for_session(
    docx_bytes: bytes,
    filename: str | None,
    generation_record: GenerationRecord | None,
    *,
    prepared_template: Any = None,
    render_context: dict | None = None,
    render_meta: dict | None = None,
) -> tuple[bytes, str]:
    """Build (or retrieve cached) deliverable zip bytes and download filename."""
    appendices = all_appendices_from_session()
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
            prepared_template.docx_bytes
            if prepared_template and prepared_template.source_format == "pdf"
            else None
        ),
        converted_template_name=(
            (prepared_template.source_filename or "converted.docx").rsplit(".", 1)[0]
            + "_converted.docx"
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
    zip_name = (filename or "esa_report").rsplit(".", 1)[0] + "_package.zip"
    return st.session_state._deliverable_zip_bytes, zip_name
