"""Streamlit project folder loader (local desktop paths)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from ui.helpers import show_upload_status
from ui.layout import render_section_header

FolderLoadResult = tuple[Any, Any, Any, list[str]]


def _format_folder_error(exc: Exception) -> str:
    """Map resolve/load failures to consultant-friendly guidance."""
    msg = str(exc)
    if isinstance(exc, FileNotFoundError):
        if "Project folder not found" in msg:
            return (
                f"{msg}\n\nCheck the path spelling and that this PC can read the folder."
            )
        if "No Excel file" in msg:
            return (
                f"{msg}\n\nAdd **`project_data.xlsx`** (or `data.xlsx`) at the folder root. "
                "See docs/22-project-folder-workflow.md."
            )
        if "No template" in msg:
            return (
                f"{msg}\n\nAdd **`template.docx`** or **`template.pdf`** at the folder root."
            )
    if isinstance(exc, ValueError) and "Could not prepare template" in msg:
        return (
            f"{msg}\n\nTry converting a large PDF offline or use a `.docx` template."
        )
    return msg


def _ai_drafts_last_analyzed(root: str | None) -> str | None:
    if not root:
        return None
    drafts = Path(root) / "ai_drafts"
    if not drafts.is_dir():
        return None
    newest: float | None = None
    for path in drafts.rglob("*"):
        if path.is_file():
            mtime = path.stat().st_mtime
            if newest is None or mtime > newest:
                newest = mtime
    if newest is None:
        return None
    return datetime.fromtimestamp(newest).strftime("%Y-%m-%d %H:%M")


@dataclass(frozen=True)
class FolderLoadBundle:
    """Loaded folder files for Streamlit session (avoids tuple/session corruption)."""

    excel_file: Any
    template_file: Any
    prepared_tpl: Any
    warnings: list[str]

    def as_tuple(self) -> FolderLoadResult:
        return self.excel_file, self.template_file, self.prepared_tpl, self.warnings


def _coerce_folder_load(raw: Any) -> FolderLoadBundle | None:
    """Accept current bundle, legacy 4-tuple, or clear invalid session values."""
    if raw is None:
        return None
    if isinstance(raw, FolderLoadBundle):
        return raw
    if isinstance(raw, tuple) and len(raw) == 4:
        return FolderLoadBundle(*raw)
    return None


FOLDER_SESSION_KEYS = (
    "project_folder_loaded",
    "project_folder_path",
    "project_folder_path_input",
    "project_folder_path_pending",
    "project_folder_core_sig",
    "folder_appendix_sig",
    "project_folder_meta",
    "project_folder_resolved",
    "project_folder_inventory",
    "folder_browse_success",
    "project_folder_excel_bytes",
    "project_folder_template_bytes",
)


@dataclass
class _PathUpload:
    """Minimal UploadedFile-like wrapper for bytes loaded from disk."""

    name: str
    _data: bytes
    type: str = ""

    @property
    def size(self) -> int:
        return len(self._data)

    def getvalue(self) -> bytes:
        return self._data


def clear_folder_session() -> None:
    store = st.session_state.get("appendix_files") or {}
    for label in st.session_state.get("folder_appendix_labels") or []:
        store.pop(label, None)
    st.session_state.pop("folder_appendix_labels", None)
    for key in FOLDER_SESSION_KEYS:
        st.session_state.pop(key, None)


def _invalidate_folder_load() -> None:
    """Drop loaded folder bytes/bundle when path edits; keep path text input."""
    store = st.session_state.get("appendix_files") or {}
    for label in st.session_state.get("folder_appendix_labels") or []:
        store.pop(label, None)
    st.session_state.pop("folder_appendix_labels", None)
    for key in (
        "project_folder_loaded",
        "project_folder_core_sig",
        "folder_appendix_sig",
        "project_folder_meta",
        "project_folder_resolved",
        "project_folder_inventory",
        "project_folder_excel_bytes",
        "project_folder_template_bytes",
        "folder_browse_success",
    ):
        st.session_state.pop(key, None)


def _folder_core_sig(resolved: Any) -> tuple[str, int, int]:
    ep, tp = resolved.excel_path, resolved.template_path
    return (str(resolved.root), ep.stat().st_mtime_ns, tp.stat().st_mtime_ns)


def _folder_appendix_sig(resolved: Any) -> tuple[str, tuple[tuple[str, int], ...], int]:
    root = str(resolved.root)
    pdfs = getattr(resolved.inventory, "appendix_pdfs", None) or []
    manifest = Path(resolved.root) / "ai_drafts" / "appendix_manifest.json"
    manifest_mtime = manifest.stat().st_mtime_ns if manifest.is_file() else 0
    return (root, tuple((str(p), p.stat().st_mtime_ns) for p in pdfs), manifest_mtime)


def _reuse_folder_load_if_current(sig: tuple[str, int, int]) -> FolderLoadBundle | None:
    if st.session_state.get("project_folder_core_sig") != sig:
        return None
    return _coerce_folder_load(st.session_state.get("project_folder_loaded"))


def _clear_folder_session() -> None:
    """Backward-compatible alias."""
    clear_folder_session()


def _render_folder_controls() -> FolderLoadResult | None:
    """Folder path input, load/analyze/clear — shared by step and legacy expander."""
    pending_path = st.session_state.pop("project_folder_path_pending", None)
    if pending_path:
        st.session_state.project_folder_path_input = pending_path

    default_path = st.session_state.get("project_folder_path", "")
    if default_path and "project_folder_path_input" not in st.session_state:
        st.session_state.project_folder_path_input = default_path

    if st.session_state.pop("menu_highlight_folder_path", False):
        st.info("Enter or browse to your project folder path below, then **Load folder**.")

    path_col, browse_col = st.columns([5, 1])
    with path_col:
        folder_str = st.text_input(
            "Project folder path",
            placeholder=r"C:\Projects\260109R",
            key="project_folder_path_input",
            help="Local path on this PC — not uploaded to the server.",
        )
    with browse_col:
        st.markdown("<div style='height:1.6rem'></div>", unsafe_allow_html=True)
        browse_clicked = st.button(
            "Browse…",
            width="stretch",
            key="browse_project_folder",
            help="Open a folder picker (local desktop).",
        )

    if browse_clicked:
        _handle_browse_folder(default_path)

    folder_path = folder_str.strip()
    last_analyzed = _ai_drafts_last_analyzed(
        st.session_state.get("project_folder_resolved") or folder_path or None
    )
    if last_analyzed:
        st.caption(f"Last analyzed (ai_drafts/): **{last_analyzed}**")

    loaded_path = st.session_state.get("project_folder_path", "")
    path_changed = bool(
        folder_path and loaded_path and folder_path != loaded_path
    )
    if path_changed:
        st.warning("Path changed — click **Load folder** to refresh loaded files.")

    st.caption(
        "**Browse…** loads the folder immediately. Or paste a path and click **Load folder**. "
        "On servers without a desktop, paste the path only."
    )

    col1, col2, col3 = st.columns(3)
    load_clicked = col1.button(
        "Load folder", width="stretch", key="load_project_folder"
    )
    analyze_clicked = col2.button(
        "Analyze folder (AI drafts)",
        width="stretch",
        key="analyze_project_folder",
        disabled=not folder_path,
        help="Writes inventory, preflight, copilot advice, narratives to ai_drafts/",
    )
    if col3.button("Clear", width="stretch", key="clear_project_folder"):
        clear_folder_session()
        st.rerun()

    if analyze_clicked and folder_path:
        _run_folder_analyze(folder_path)

    loaded_path = st.session_state.get("project_folder_path", "")
    if path_changed and not load_clicked and not analyze_clicked:
        _invalidate_folder_load()

    if load_clicked and folder_path:
        try:
            loaded = _load_folder(folder_path)
        except (FileNotFoundError, ValueError, OSError, TypeError) as e:
            st.error(_format_folder_error(e))
            return None
        st.session_state.project_folder_path = folder_path
        st.session_state.project_folder_loaded = loaded
        _show_folder_inventory(st.session_state.get("project_folder_inventory"))
        st.success(f"Loaded from `{folder_path}`")
        return loaded.as_tuple()

    loaded = _coerce_folder_load(st.session_state.get("project_folder_loaded"))
    if loaded:
        if st.session_state.pop("folder_browse_success", None):
            st.success(
                f"Loaded from `{st.session_state.get('project_folder_path', '')}`"
            )
        with st.container(border=True):
            st.markdown("**Loaded files**")
            show_upload_status("Excel", loaded.excel_file)
            show_upload_status("Template", loaded.template_file)
            _show_folder_inventory(st.session_state.get("project_folder_inventory"))
        return loaded.as_tuple()

    stale = st.session_state.get("project_folder_loaded")
    if stale is not None:
        clear_folder_session()
        st.warning("Folder session was invalid — please load the folder again.")

    _render_folder_idle_state()
    return None


def _render_folder_idle_state() -> None:
    from ui.alberta_imagery import has_alberta_images, render_empty_state_banner

    if has_alberta_images():
        render_empty_state_banner()
    st.info(
        "Click **Browse…** to choose a folder (loads immediately), or paste a path and "
        "click **Load folder**. Use **Analyze folder** first if you want AI drafts in "
        "`ai_drafts/` before generating."
    )


def _handle_browse_folder(fallback_initial: str) -> None:
    from ui.folder_picker import folder_picker_available, pick_local_folder

    if not folder_picker_available():
        st.warning(
            "Folder picker is not available here (headless/server). Paste the path manually."
        )
        return

    initial = (
        st.session_state.get("project_folder_path_input", "")
        or fallback_initial
        or ""
    )
    picked = pick_local_folder(initial=initial, title="Select project folder")
    if not picked:
        return

    st.session_state.project_folder_path_pending = picked
    try:
        loaded = _load_folder(picked)
    except (FileNotFoundError, ValueError, OSError, TypeError) as e:
        st.error(_format_folder_error(e))
        return
    st.session_state.project_folder_path = picked
    st.session_state.project_folder_loaded = loaded
    st.session_state.folder_browse_success = True
    st.rerun()


def render_project_folder_step() -> FolderLoadResult | None:
    """
    Primary step UI for project-folder workflow (not hidden in an expander).
    Returns (excel_file, template_file, prepared_tpl, warnings) or None.
    """
    render_section_header(
        1,
        "Select project folder",
        caption=(
            "Folder must contain `project_data.xlsx` and `template.docx` (or `.pdf`). "
            "Optional: `source/`, `appendices/`, `rag/`, `project.json`. "
            "On Docker/Linux servers, paste the path (Browse is unavailable)."
        ),
    )
    return _render_folder_controls()


def render_project_folder_loader() -> FolderLoadResult | None:
    """Legacy expander loader (kept for compatibility)."""
    with st.expander("Load from project folder (local path)", expanded=False):
        st.caption(
            "Point to a folder with `project_data.xlsx` and `template.docx`. "
            "See docs/22-project-folder-workflow.md."
        )
        return _render_folder_controls()


def _load_folder(
    folder_str: str,
    *,
    resolved: Any | None = None,
    core_files: tuple[bytes, bytes] | None = None,
) -> FolderLoadBundle:
    from project_folder import resolve_project_folder

    resolved = resolved or resolve_project_folder(Path(folder_str))
    sig = _folder_core_sig(resolved)
    reused = _reuse_folder_load_if_current(sig)
    if reused is not None:
        return reused
    return _load_folder_from_resolved(resolved, core_files=core_files, sig=sig)


def _load_folder_from_resolved(
    resolved: Any,
    *,
    core_files: tuple[bytes, bytes] | None = None,
    sig: tuple[str, int, int] | None = None,
) -> FolderLoadBundle:
    from ui.helpers import parse_template_version_from_filename, prepare_uploaded_template

    sig = sig or _folder_core_sig(resolved)
    excel_bytes, template_bytes = core_files or resolved.read_core_files()
    from project_folder import effective_excel_bytes_for_folder

    excel_bytes, eco_warnings = effective_excel_bytes_for_folder(resolved, excel_bytes)
    excel_file = _PathUpload(resolved.excel_path.name, excel_bytes)
    template_file = _PathUpload(
        resolved.template_path.name,
        template_bytes,
        type=(
            "application/pdf"
            if resolved.template_path.suffix.lower() == ".pdf"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )
    prepared_tpl = prepare_uploaded_template(
        template_file, digest_slot="folder_template"
    )
    if prepared_tpl is None:
        raise ValueError(
            f"Could not prepare template `{resolved.template_path.name}` for rendering."
        )
    ver = parse_template_version_from_filename(template_file.name)
    if ver:
        st.session_state.suggested_template_version = ver
    warnings = list(prepared_tpl.warnings) + eco_warnings
    inv = resolved.inventory
    summaries_path = resolved.root / "ai_drafts" / "source_summaries.json"
    st.session_state.project_folder_meta = dict(resolved.meta)
    st.session_state.project_folder_resolved = str(resolved.root)
    st.session_state.project_folder_inventory = {
        "warnings": list(inv.warnings),
        "appendix_count": len(inv.appendix_pdfs),
        "source_pdf_count": len(inv.source_pdfs),
        "excel_name": inv.excel_path.name,
        "template_name": inv.template_path.name,
        "profile": inv.meta.get("report_type", ""),
        "has_source_summaries": summaries_path.is_file(),
    }
    _apply_folder_appendices(resolved)
    st.session_state.project_folder_excel_bytes = excel_bytes
    st.session_state.project_folder_template_bytes = prepared_tpl.docx_bytes
    st.session_state.project_folder_core_sig = sig
    return FolderLoadBundle(excel_file, template_file, prepared_tpl, warnings)


def _apply_folder_appendices(resolved: Any) -> None:
    from project_folder import appendix_label_conflicts, load_manual_appendices

    ap_sig = _folder_appendix_sig(resolved)
    if st.session_state.get("folder_appendix_sig") == ap_sig:
        return

    manual = load_manual_appendices(resolved)
    if "appendix_files" not in st.session_state:
        st.session_state.appendix_files = {}
    for label in st.session_state.get("folder_appendix_labels") or []:
        st.session_state.appendix_files.pop(label, None)
    labels: list[str] = []
    for ap in manual:
        st.session_state.appendix_files[ap.label] = ap
        labels.append(ap.label)
    st.session_state.folder_appendix_labels = labels
    st.session_state.folder_appendix_sig = ap_sig
    st.session_state.folder_appendix_conflicts = appendix_label_conflicts(resolved)


def _show_folder_inventory(snapshot: dict[str, Any] | None) -> None:
    if not snapshot:
        return
    for w in snapshot.get("warnings") or []:
        st.warning(w)
    for note in st.session_state.get("folder_appendix_conflicts") or []:
        st.warning(note)
    lines: list[str] = []
    if snapshot.get("excel_name"):
        lines.append(f"Excel: `{snapshot['excel_name']}`")
    if snapshot.get("template_name"):
        lines.append(f"Template: `{snapshot['template_name']}`")
    if snapshot.get("profile"):
        lines.append(f"Profile: `{snapshot['profile']}`")
    src = int(snapshot.get("source_pdf_count") or 0)
    app = int(snapshot.get("appendix_count") or 0)
    if src:
        lines.append(f"{src} PDF(s) in `source/`")
    if app:
        lines.append(f"{app} appendix PDF(s) in `appendices/`")
    drafts = st.session_state.get("project_folder_resolved")
    if drafts and src and not snapshot.get("has_source_summaries"):
        lines.append("_Run **Analyze folder** to ingest source PDFs into `ai_drafts/`_")
    if lines:
        st.caption(" · ".join(lines))


def _run_folder_analyze(folder_str: str) -> None:
    from project_folder import enrich_project_folder, resolve_project_folder

    try:
        with st.spinner("Analyzing project folder..."):
            resolved = resolve_project_folder(Path(folder_str), create_subdirs=True)
            paths = enrich_project_folder(
                resolved,
                use_llm=_use_llm(),
                modes=("inventory", "source-ingest", "narratives", "appendix-classify"),
            )
    except (FileNotFoundError, ValueError, OSError) as e:
        st.error(_format_folder_error(e))
        return
    st.session_state.project_folder_path = folder_str
    pdf_n = 0
    index_path = resolved.ai_drafts_dir / "source_index.json"
    if index_path.is_file():
        try:
            idx = json.loads(index_path.read_text(encoding="utf-8"))
            pdf_n = int(idx.get("pdf_count") or 0)
        except (json.JSONDecodeError, OSError, TypeError):
            pdf_n = 0
    if pdf_n or (resolved.ai_drafts_dir / "source_summaries.json").is_file():
        inv = st.session_state.get("project_folder_inventory") or {}
        if isinstance(inv, dict):
            inv = dict(inv)
            inv["has_source_summaries"] = True
            st.session_state.project_folder_inventory = inv
    sugg_path = resolved.ai_drafts_dir / "excel_field_suggestions.json"
    msg = f"Wrote {len(paths)} draft file(s) to `{resolved.ai_drafts_dir}`"
    if pdf_n:
        msg += f" (ingested {pdf_n} source PDF(s))"
    st.success(msg)
    for p in paths:
        st.caption(f"• {p.name}")
    if sugg_path.is_file():
        st.caption("• Review `excel_field_suggestions.json` — apply from the **AI tools** tab")
    _sync_folder_after_analyze(folder_str, resolved=resolved)
    from ai.models import AiAudit

    existing: list = st.session_state.get("ai_audit_log") or []
    existing.append(
        AiAudit(features=["folder_analyze"], used_llm=_use_llm()).to_dict()
    )
    st.session_state["ai_audit_log"] = existing[-20:]
    st.info(
        "Review drafts in `ai_drafts/` (AI tools tab) or apply narratives/field suggestions "
        "into Excel with **Apply** buttons. Then generate on the **Report** tab."
    )


def _sync_folder_after_analyze(
    folder_str: str,
    *,
    resolved: Any | None = None,
) -> None:
    """Load folder into session after analyze so Report tab can generate immediately."""
    if (
        st.session_state.get("project_folder_path") == folder_str
        and st.session_state.get("project_folder_core_sig")
        and _reuse_folder_load_if_current(st.session_state.project_folder_core_sig)
    ):
        return

    from project_folder import resolve_project_folder

    resolved = resolved or resolve_project_folder(Path(folder_str))
    sig = _folder_core_sig(resolved)
    if (
        st.session_state.get("project_folder_path") == folder_str
        and _reuse_folder_load_if_current(sig)
    ):
        return
    try:
        st.session_state.project_folder_loaded = _load_folder(
            folder_str,
            resolved=resolved,
            core_files=resolved.read_core_files(),
        )
    except (FileNotFoundError, ValueError, OSError) as e:
        st.warning(
            f"Drafts saved to disk, but folder could not be loaded for generate: {e}"
        )
        return
    st.session_state.project_folder_path = folder_str


def get_folder_render_bytes() -> tuple[bytes | None, bytes | None]:
    """Cached Excel + prepared template bytes after folder load (skip re-read on reruns)."""
    if not _coerce_folder_load(st.session_state.get("project_folder_loaded")):
        return None, None
    return (
        st.session_state.get("project_folder_excel_bytes"),
        st.session_state.get("project_folder_template_bytes"),
    )


def merge_folder_meta(sidebar_meta: dict[str, str]) -> dict[str, str]:
    """Overlay project.json meta from loaded folder onto sidebar meta."""
    folder_meta = st.session_state.get("project_folder_meta") or {}
    if not folder_meta:
        return sidebar_meta
    merged = dict(sidebar_meta)
    for key in (
        "report_type",
        "report_phase",
        "prepared_by",
        "date_of_issue",
        "template_version",
    ):
        if folder_meta.get(key):
            merged[key] = folder_meta[key]
    return merged


def _use_llm() -> bool:
    return bool(st.session_state.get("ai_use_llm", True))
