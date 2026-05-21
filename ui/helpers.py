from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import streamlit as st

from engine import (
    generate_phase1_alberta_excel,
    generate_phase1_alberta_template_docx,
    generate_production_excel,
    generate_production_starter_template_docx,
    generate_production_template_docx,
    generate_sample_excel,
    generate_sample_template_docx,
)
from template_attachments import PreparedTemplate, prepare_template_upload
from template_tools import scan_template

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_XLSX = ROOT / "samples" / "sample_data.xlsx"
SAMPLE_DOCX = ROOT / "samples" / "sample_template.docx"
PRODUCTION_XLSX = ROOT / "samples" / "production_data.xlsx"
PRODUCTION_STARTER_DOCX = ROOT / "samples" / "production_starter_template.docx"
PRODUCTION_TEMPLATE_DOCX = ROOT / "samples" / "production_template.docx"
PHASE1_ALBERTA_XLSX = ROOT / "samples" / "phase1_alberta_data.xlsx"
PHASE1_ALBERTA_DOCX = ROOT / "samples" / "phase1_alberta_template.docx"


def format_size(num_bytes: int | None) -> str:
    if num_bytes is None:
        return "unknown size"
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"


def show_upload_status(label: str, uploaded: Any, *, extra: str = "") -> None:
    if uploaded is None:
        st.caption(f"{label}: not selected")
        return
    suffix = f" — {extra}" if extra else ""
    st.caption(f"{label}: **{uploaded.name}** ({format_size(uploaded.size)}){suffix}")


def _template_cache_key(data: bytes, filename: str) -> str:
    digest = hashlib.sha256(data).hexdigest()
    return f"tpl_{digest}_{filename}"


def prepare_uploaded_template(uploaded: Any) -> PreparedTemplate | None:
    """Convert PDF→DOCX if needed; cache by file hash to avoid re-conversion on reruns."""
    if uploaded is None:
        return None
    data = uploaded.getvalue()
    name = uploaded.name or ""
    key = _template_cache_key(data, name)
    if key in st.session_state:
        return st.session_state[key]
    prepared = prepare_template_upload(data, name)
    st.session_state[key] = prepared
    st.session_state["last_prepared_template"] = prepared
    return prepared


def parse_template_version_from_filename(filename: str) -> str:
    """Extract semantic version from template name, e.g. phase1_ecoventure_v2.1.docx → 2.1."""
    m = re.search(r"[vV](\d+(?:\.\d+)+)", filename or "")
    return m.group(1) if m else ""


def render_converted_template_download(prepared: PreparedTemplate | None) -> None:
    if prepared is None or prepared.source_format != "pdf":
        return
    base = Path(prepared.source_filename).stem
    st.download_button(
        "Download converted Word template (.docx)",
        data=prepared.docx_bytes,
        file_name=f"{base}_converted.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True,
        help="Add Jinja2 tags in Word, then re-upload the .docx template.",
    )


def _ensure_samples() -> None:
    samples = ROOT / "samples"
    samples.mkdir(parents=True, exist_ok=True)
    if not SAMPLE_XLSX.is_file():
        generate_sample_excel(str(SAMPLE_XLSX))
    if not PRODUCTION_XLSX.is_file():
        generate_production_excel(str(PRODUCTION_XLSX))
    if not SAMPLE_DOCX.is_file():
        generate_sample_template_docx(str(SAMPLE_DOCX))
    if not PRODUCTION_STARTER_DOCX.is_file():
        generate_production_starter_template_docx(str(PRODUCTION_STARTER_DOCX))
    if not PRODUCTION_TEMPLATE_DOCX.is_file():
        generate_production_template_docx(str(PRODUCTION_TEMPLATE_DOCX))
    if not PHASE1_ALBERTA_XLSX.is_file():
        generate_phase1_alberta_excel(str(PHASE1_ALBERTA_XLSX))
    if not PHASE1_ALBERTA_DOCX.is_file():
        generate_phase1_alberta_template_docx(str(PHASE1_ALBERTA_DOCX))


def render_download_helpers() -> None:
    st.sidebar.header("Templates")
    _ensure_samples()

    if SAMPLE_XLSX.is_file():
        st.sidebar.download_button(
            "Download sample Excel",
            data=SAMPLE_XLSX.read_bytes(),
            file_name="sample_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    if PRODUCTION_XLSX.is_file():
        st.sidebar.download_button(
            "Download production Excel layout",
            data=PRODUCTION_XLSX.read_bytes(),
            file_name="production_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    if SAMPLE_DOCX.is_file():
        st.sidebar.download_button(
            "Download sample Word template",
            data=SAMPLE_DOCX.read_bytes(),
            file_name="sample_template.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    if PRODUCTION_STARTER_DOCX.is_file():
        st.sidebar.download_button(
            "Download production starter template",
            data=PRODUCTION_STARTER_DOCX.read_bytes(),
            file_name="production_starter_template.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    if PRODUCTION_TEMPLATE_DOCX.is_file():
        st.sidebar.download_button(
            "Download production template (tagged)",
            data=PRODUCTION_TEMPLATE_DOCX.read_bytes(),
            file_name="production_template.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    if PHASE1_ALBERTA_XLSX.is_file():
        st.sidebar.download_button(
            "Download Alberta Phase I Excel (Ecoventure)",
            data=PHASE1_ALBERTA_XLSX.read_bytes(),
            file_name="phase1_alberta_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    if PHASE1_ALBERTA_DOCX.is_file():
        st.sidebar.download_button(
            "Download Alberta Phase I template (Ecoventure)",
            data=PHASE1_ALBERTA_DOCX.read_bytes(),
            file_name="phase1_alberta_template.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )


def render_template_analysis(template_bytes: bytes | None) -> None:
    if not template_bytes:
        return
    with st.expander("Analyze uploaded Word template"):
        try:
            scan = scan_template(template_bytes)
            st.write(f"**Root variables** ({len(scan.root_vars)}):")
            st.code(", ".join(sorted(scan.root_vars)) or "(none)")
            if scan.block_tags:
                st.write(f"**Block tags** ({len(scan.block_tags)}):")
                st.code("\n".join(sorted(scan.block_tags)[:40]))
            if scan.split_issues:
                st.warning(f"{len(scan.split_issues)} possible split-tag issue(s).")
        except Exception as e:
            st.error(f"Analysis failed: {e}")
