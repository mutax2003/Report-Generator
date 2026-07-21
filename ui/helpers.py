from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import streamlit as st

from engine import (
    ReportEngine,
    generate_groundwater_monitoring_excel,
    generate_groundwater_monitoring_template_docx,
    generate_phase1_alberta_excel,
    generate_phase1_alberta_template_docx,
    generate_phase2_alberta_excel,
    generate_phase2_alberta_template_docx,
    generate_phase3_remediation_excel,
    generate_phase3_remediation_template_docx,
    generate_production_excel,
    generate_production_starter_template_docx,
    generate_production_template_docx,
    generate_reclamation_certificate_excel,
    generate_reclamation_certificate_template_docx,
    generate_sample_excel,
    generate_sample_template_docx,
)
from template_attachments import PreparedTemplate, prepare_template_upload_cached
from template_tools import scan_template

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_XLSX = ROOT / "samples" / "sample_data.xlsx"
SAMPLE_DOCX = ROOT / "samples" / "sample_template.docx"
PRODUCTION_XLSX = ROOT / "samples" / "production_data.xlsx"
PRODUCTION_STARTER_DOCX = ROOT / "samples" / "production_starter_template.docx"
PRODUCTION_TEMPLATE_DOCX = ROOT / "samples" / "production_template.docx"
PHASE1_ALBERTA_XLSX = ROOT / "samples" / "phase1_alberta_data.xlsx"
PHASE1_ALBERTA_DOCX = ROOT / "samples" / "phase1_alberta_template.docx"
GW_MONITORING_XLSX = ROOT / "samples" / "groundwater_monitoring_data.xlsx"
GW_MONITORING_DOCX = ROOT / "samples" / "groundwater_monitoring_template.docx"
PHASE2_ALBERTA_XLSX = ROOT / "samples" / "phase2_alberta_data.xlsx"
PHASE2_ALBERTA_DOCX = ROOT / "samples" / "phase2_alberta_template.docx"
PHASE3_XLSX = ROOT / "samples" / "phase3_remediation_data.xlsx"
PHASE3_DOCX = ROOT / "samples" / "phase3_remediation_template.docx"
RECLAMATION_XLSX = ROOT / "samples" / "reclamation_certificate_data.xlsx"
RECLAMATION_DOCX = ROOT / "samples" / "reclamation_certificate_template.docx"


class BytesUpload:
    """Minimal file-like object for session-loaded sample bytes."""

    def __init__(self, name: str, data: bytes) -> None:
        self.name = name
        self.size = len(data)
        self._data = data

    def getvalue(self) -> bytes:
        return self._data


def clear_session_sample_bytes() -> None:
    for key in (
        "session_excel_bytes",
        "session_excel_name",
        "session_template_bytes",
        "session_template_name",
    ):
        st.session_state.pop(key, None)


def load_phase1_alberta_sample_into_session() -> bool:
    """Load Alberta Phase I sample pair into session for upload workflow."""
    _ensure_samples()
    excel = _sample_bytes(PHASE1_ALBERTA_XLSX)
    tpl = _sample_bytes(PHASE1_ALBERTA_DOCX)
    if not excel or not tpl:
        return False
    st.session_state.session_excel_bytes = excel
    st.session_state.session_excel_name = "phase1_alberta_data.xlsx"
    st.session_state.session_template_bytes = tpl
    st.session_state.session_template_name = "phase1_alberta_template.docx"
    box = st.session_state.setdefault("_upload_bytes_cache", {})
    box["excel"] = (
        ("phase1_alberta_data.xlsx", _upload_content_fingerprint(excel)),
        excel,
    )
    box["template"] = (
        ("phase1_alberta_template.docx", _upload_content_fingerprint(tpl)),
        tpl,
    )
    st.session_state.pop("_preflight_result_cache", None)
    st.session_state.pop("_report_engine_cache", None)
    return True


def resolve_session_excel_file(uploaded: Any) -> Any:
    if uploaded is not None:
        return uploaded
    data = st.session_state.get("session_excel_bytes")
    if data:
        name = st.session_state.get("session_excel_name", "data.xlsx")
        return BytesUpload(name, data)
    return None


def resolve_session_template_file(uploaded: Any) -> Any:
    if uploaded is not None:
        return uploaded
    data = st.session_state.get("session_template_bytes")
    if data:
        name = st.session_state.get("session_template_name", "template.docx")
        return BytesUpload(name, data)
    return None


def session_loaded_file_names() -> tuple[str | None, str | None]:
    excel = st.session_state.get("session_excel_name")
    tpl = st.session_state.get("session_template_name")
    return excel, tpl


def prepare_session_template() -> tuple[Any, list[str]]:
    """Prepare template from session-loaded sample bytes."""
    data = st.session_state.get("session_template_bytes")
    if not data:
        return None, []
    name = st.session_state.get("session_template_name", "template.docx")
    try:
        prepared_tpl = prepare_uploaded_template(BytesUpload(name, data))
        ver = parse_template_version_from_filename(name)
        if ver:
            st.session_state.suggested_template_version = ver
        return prepared_tpl, list(prepared_tpl.warnings)
    except Exception as e:
        from security import user_safe_error

        st.error(user_safe_error(e))
        return None, []


@lru_cache(maxsize=32)
def _sample_file_bytes(path_str: str, mtime_ns: int) -> bytes:
    return Path(path_str).read_bytes()


def _sample_bytes(path: Path) -> bytes:
    if not path.is_file():
        return b""
    return _sample_file_bytes(str(path.resolve()), path.stat().st_mtime_ns)


def format_size(num_bytes: int | None) -> str:
    if num_bytes is None:
        return "unknown size"
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"


def show_upload_status(label: str, uploaded: Any, *, extra: str = "") -> None:
    from ui.branding import status_badge_html

    if uploaded is None:
        st.markdown(
            f"{label} {status_badge_html('muted', 'not selected')}",
            unsafe_allow_html=True,
        )
        return
    suffix = f" · {extra}" if extra else ""
    name = getattr(uploaded, "name", "file") or "file"
    size = format_size(getattr(uploaded, "size", 0) or 0)
    st.markdown(
        f"{status_badge_html('ok', name)} <span class='ev-context-muted'>({size}{suffix})</span>",
        unsafe_allow_html=True,
    )


def _upload_content_fingerprint(data: bytes) -> tuple[int, bytes, bytes]:
    """Size plus head/tail bytes — catches same-size file swaps without full re-read."""
    n = len(data)
    if n == 0:
        return (0, b"", b"")
    head = data[:8]
    tail = data[-8:] if n > 8 else data
    return (n, head, tail)


def stable_upload_digest(slot: str, filename: str, data: bytes) -> str:
    """
    SHA-256 of upload bytes, cached in Streamlit session by (slot, name, fingerprint).

    Avoids re-hashing large templates on every rerun when the upload is unchanged.
    """
    sig = (filename or "", _upload_content_fingerprint(data))
    box = st.session_state.setdefault("_upload_digest_cache", {})
    entry = box.get(slot)
    if entry and entry[0] == sig:
        return entry[1]
    digest = hashlib.sha256(data).hexdigest()
    box[slot] = (sig, digest)
    return digest


def _template_cache_key(data: bytes, filename: str, *, digest_slot: str = "template") -> str:
    digest = stable_upload_digest(digest_slot, filename, data)
    return f"tpl_{digest}_{filename}"


def cached_upload_bytes(uploaded: Any, *, slot: str = "default") -> bytes | None:
    """
    Return upload bytes; cache in session by (slot, name, file_id or fingerprint).

    Avoids re-copying large Excel/template uploads on every Streamlit rerun.
    """
    if uploaded is None:
        return None
    name = getattr(uploaded, "name", None) or ""
    file_id = getattr(uploaded, "file_id", None)
    box = st.session_state.setdefault("_upload_bytes_cache", {})
    entry = box.get(slot)
    if entry and file_id:
        stored_sig, stored_data = entry
        if stored_sig == (name, file_id):
            return stored_data
    data = uploaded.getvalue()
    sig: tuple[str, str] | tuple[str, tuple[int, bytes, bytes]]
    if file_id:
        sig = (name, str(file_id))
    else:
        sig = (name, _upload_content_fingerprint(data))
    if entry and not file_id:
        stored_sig, stored_data = entry
        if stored_sig == sig:
            return stored_data
    box[slot] = (sig, data)
    return data


def merge_ecoventure_workbook_bytes(
    base_excel_bytes: bytes,
    ecoventure_bytes: bytes | None,
) -> bytes:
    """Merge optional Ecoventure Phase I workbook into engine Excel bytes."""
    if not ecoventure_bytes:
        return base_excel_bytes
    from ecoventure_workbook import merge_into_engine_excel

    return merge_into_engine_excel(base_excel_bytes, ecoventure_bytes)


def effective_excel_bytes(
    base_excel_bytes: bytes | None,
    ecoventure_bytes: bytes | None = None,
) -> bytes | None:
    """Return Excel bytes with Ecoventure workbook merged when provided."""
    if not base_excel_bytes:
        return None
    base_digest = stable_upload_digest("excel", "excel.xlsx", base_excel_bytes)
    if base_digest != st.session_state.get("_ecoventure_base_excel_digest"):
        st.session_state.pop("ecoventure_workbook_bytes", None)
        st.session_state.pop("_ecoventure_merged_cache", None)
        st.session_state["_ecoventure_base_excel_digest"] = base_digest
    eco = ecoventure_bytes or st.session_state.get("ecoventure_workbook_bytes")
    if not eco:
        return base_excel_bytes
    eco_digest = stable_upload_digest("ecoventure", "ecoventure_workbook.xlsx", eco)
    cache_key = (base_digest, eco_digest)
    cached = st.session_state.get("_ecoventure_merged_cache")
    if isinstance(cached, tuple) and len(cached) == 2 and cached[0] == cache_key:
        return cached[1]
    try:
        merged = merge_ecoventure_workbook_bytes(base_excel_bytes, eco)
    except ValueError as e:
        st.warning(str(e))
        return base_excel_bytes
    st.session_state["_ecoventure_merged_cache"] = (cache_key, merged)
    return merged


def get_cached_report_engine(excel_bytes: bytes, template_bytes: bytes) -> ReportEngine:
    """Reuse ReportEngine across Streamlit reruns when uploads are unchanged.

    Appendix uploads do not affect ReportEngine construction — they belong on the
    preflight cache key only.
    """
    eco_sig = stable_upload_digest(
        "ecoventure",
        "ecoventure_workbook.xlsx",
        st.session_state.get("ecoventure_workbook_bytes") or b"",
    )
    key = (
        stable_upload_digest("excel", "excel.xlsx", excel_bytes),
        stable_upload_digest("template", "template.docx", template_bytes),
        eco_sig,
    )
    cache = st.session_state.setdefault("_report_engine_cache", {})
    if cache.get("key") != key:
        cache["key"] = key
        cache["engine"] = ReportEngine(excel_bytes, template_bytes)
    return cache["engine"]


def prepare_uploaded_template(
    uploaded: Any, *, digest_slot: str = "template"
) -> PreparedTemplate | None:
    """Convert PDF→DOCX if needed; cache by file hash to avoid re-conversion on reruns."""
    if uploaded is None:
        return None
    data = cached_upload_bytes(uploaded, slot=digest_slot)
    if data is None:
        return None
    name = uploaded.name or ""
    key = _template_cache_key(data, name, digest_slot=digest_slot)
    if key in st.session_state:
        return st.session_state[key]
    prepared = prepare_template_upload_cached(data, name)
    from security import MAX_TEMPLATE_BYTES, _template_size_limit

    limit = _template_size_limit()
    if len(prepared.docx_bytes) > limit:
        st.warning(
            f"Prepared Word template is {len(prepared.docx_bytes) / (1024 * 1024):.1f} MB "
            f"(limit {limit // (1024 * 1024)} MB). Generation will be blocked until you "
            "upload a smaller file or use `*-markup-upload.docx` from "
            "`scripts\\phase1_pdf_to_markup.py --for-streamlit`."
        )
    elif prepared.source_format == "pdf" and len(prepared.docx_bytes) > MAX_TEMPLATE_BYTES:
        st.info(
            f"PDF converted to {len(prepared.docx_bytes) / (1024 * 1024):.1f} MB Word file. "
            "For Streamlit, prefer a pre-trimmed `*-markup-upload.docx`."
        )
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
        width="stretch",
        help="Add Jinja2 tags in Word, then re-upload the .docx template.",
    )
    st.caption(
        "Tip: run `python scripts\\phase1_pdf_to_markup.py --for-streamlit` for a "
        "`*-markup-upload.docx` under 30 MB (required for upload). Full layouts stay in "
        "`*-markup.docx` for CLI only."
    )


def _ensure_samples() -> None:
    if st.session_state.get("_samples_ensured"):
        return
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
    if not GW_MONITORING_XLSX.is_file():
        generate_groundwater_monitoring_excel(str(GW_MONITORING_XLSX))
    if not GW_MONITORING_DOCX.is_file():
        generate_groundwater_monitoring_template_docx(str(GW_MONITORING_DOCX))
    if not PHASE2_ALBERTA_XLSX.is_file():
        generate_phase2_alberta_excel(str(PHASE2_ALBERTA_XLSX))
    if not PHASE2_ALBERTA_DOCX.is_file():
        generate_phase2_alberta_template_docx(str(PHASE2_ALBERTA_DOCX))
    if not PHASE3_XLSX.is_file():
        generate_phase3_remediation_excel(str(PHASE3_XLSX))
    if not PHASE3_DOCX.is_file():
        generate_phase3_remediation_template_docx(str(PHASE3_DOCX))
    if not RECLAMATION_XLSX.is_file():
        generate_reclamation_certificate_excel(str(RECLAMATION_XLSX))
    if not RECLAMATION_DOCX.is_file():
        generate_reclamation_certificate_template_docx(str(RECLAMATION_DOCX))
    st.session_state["_samples_ensured"] = True


def render_download_helpers() -> None:
    """Sample downloads (render inside sidebar expander).

    Phase I pair is always shown. Extra samples are gated so Streamlit does not
    re-bind multi-MB payloads on every sidebar paint.
    """
    from ui.onboarding import is_simple_mode

    _ensure_samples()

    if PHASE1_ALBERTA_XLSX.is_file():
        st.sidebar.download_button(
            "Download Alberta Phase I Excel (Ecoventure)",
            data=_sample_bytes(PHASE1_ALBERTA_XLSX),
            file_name="phase1_alberta_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
            key="dl_phase1_xlsx",
        )
    if PHASE1_ALBERTA_DOCX.is_file():
        st.sidebar.download_button(
            "Download Alberta Phase I template (Ecoventure)",
            data=_sample_bytes(PHASE1_ALBERTA_DOCX),
            file_name="phase1_alberta_template.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            width="stretch",
            key="dl_phase1_docx",
        )

    show_all = st.sidebar.checkbox(
        "Show all sample downloads",
        value=False,
        key="ux_show_all_sample_downloads",
        help="Extra sample pairs (Phase II, GW, etc.) — keep off for faster reruns.",
    )
    if is_simple_mode() and not show_all:
        st.sidebar.caption("Turn on **Show all sample downloads** for other profiles.")
        return
    if not show_all:
        return

    pairs = [
        (SAMPLE_XLSX, "Download sample Excel", "sample_data.xlsx", "xlsx"),
        (PRODUCTION_XLSX, "Download production Excel layout", "production_data.xlsx", "xlsx"),
        (SAMPLE_DOCX, "Download sample Word template", "sample_template.docx", "docx"),
        (
            PRODUCTION_STARTER_DOCX,
            "Download production starter template",
            "production_starter_template.docx",
            "docx",
        ),
        (
            PRODUCTION_TEMPLATE_DOCX,
            "Download production template (tagged)",
            "production_template.docx",
            "docx",
        ),
        (
            GW_MONITORING_XLSX,
            "Download groundwater monitoring Excel",
            "groundwater_monitoring_data.xlsx",
            "xlsx",
        ),
        (
            GW_MONITORING_DOCX,
            "Download groundwater monitoring template",
            "groundwater_monitoring_template.docx",
            "docx",
        ),
        (
            PHASE2_ALBERTA_XLSX,
            "Download Alberta Phase II Excel",
            "phase2_alberta_data.xlsx",
            "xlsx",
        ),
        (
            PHASE2_ALBERTA_DOCX,
            "Download Alberta Phase II template",
            "phase2_alberta_template.docx",
            "docx",
        ),
        (
            PHASE3_XLSX,
            "Download Phase III remediation Excel",
            "phase3_remediation_data.xlsx",
            "xlsx",
        ),
        (
            PHASE3_DOCX,
            "Download Phase III remediation template",
            "phase3_remediation_template.docx",
            "docx",
        ),
        (
            RECLAMATION_XLSX,
            "Download reclamation certificate Excel",
            "reclamation_certificate_data.xlsx",
            "xlsx",
        ),
        (
            RECLAMATION_DOCX,
            "Download reclamation certificate template",
            "reclamation_certificate_template.docx",
            "docx",
        ),
    ]
    xlsx_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    docx_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    for path, label, filename, kind in pairs:
        if not path.is_file():
            continue
        st.sidebar.download_button(
            label,
            data=_sample_bytes(path),
            file_name=filename,
            mime=xlsx_mime if kind == "xlsx" else docx_mime,
            width="stretch",
            key=f"dl_extra_{filename}",
        )


def render_template_analysis(template_bytes: bytes | None) -> None:
    if not template_bytes:
        return
    with st.expander("Analyze uploaded Word template"):
        try:
            digest = stable_upload_digest("template_analysis", "template.docx", template_bytes)
            box = st.session_state.setdefault("_template_analysis_cache", {})
            scan = box.get(digest)
            if scan is None:
                scan = scan_template(template_bytes)
                if len(box) >= 16:
                    box.pop(next(iter(box)))
                box[digest] = scan
            st.write(f"**Root variables** ({len(scan.root_vars)}):")
            st.code(", ".join(sorted(scan.root_vars)) or "(none)")
            if scan.block_tags:
                st.write(f"**Block tags** ({len(scan.block_tags)}):")
                st.code("\n".join(sorted(scan.block_tags)[:40]))
            if scan.split_issues:
                st.warning(f"{len(scan.split_issues)} possible split-tag issue(s).")
        except Exception as e:
            from security import user_safe_error

            st.error(f"Analysis failed: {user_safe_error(e)}")
