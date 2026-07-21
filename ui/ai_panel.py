"""Streamlit UI for Tier 1 & 2 AI features."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from ai import ai_status_message
from ai.config import ai_available, resolve_llm_settings
from ai.consistency import check_consistency
from ai.copilot import explain_preflight
from ai.exceedance_notes import notes_for_lab_rows
from ai.excel_builder import (
    apec_rows_to_xlsx_bytes,
    lab_rows_to_groundwater_xlsx_bytes,
    lab_rows_to_xlsx_bytes,
    well_rows_to_xlsx_bytes,
)
from ai.gw_trends import analyze_groundwater_trends
from ai.lab_extract import extract_lab_from_pdf
from ai.apec_extract import extract_apecs_from_bytes, merge_apec_results
from ai.well_log_extract import extract_wells_from_pdf
from ai.models import AiAudit, ApecExtractResult
from ai.narrative import draft_narratives
from ai.template_tagger import suggest_template_tags, suggestions_to_markdown
from engine import ReportEngine
from security import user_safe_error
from template_tools import PreflightResult, run_preflight


def _step1_input_hint(folder_mode: bool) -> str:
    return "Load folder on **step 1**" if folder_mode else "Upload on **step 1**"


def _use_llm() -> bool:
    return st.session_state.get("ai_use_llm", ai_available())


def _merge_audit(audit: AiAudit) -> None:
    existing: list[dict[str, Any]] = st.session_state.get("ai_audit_log") or []
    existing.append(audit.to_dict())
    st.session_state["ai_audit_log"] = existing[-20:]


def _set_session_excel_bytes(data: bytes, *, name: str | None = None) -> None:
    """Replace loaded Excel in session (upload or folder workflow) and clear caches."""
    st.session_state.session_excel_bytes = data
    if name:
        st.session_state.session_excel_name = name
    if st.session_state.get("project_folder_excel_bytes") is not None:
        st.session_state.project_folder_excel_bytes = data
    st.session_state.pop("_preflight_result_cache", None)
    st.session_state.pop("_report_engine_cache", None)
    box = st.session_state.setdefault("_upload_bytes_cache", {})
    box.pop("excel", None)


def _apply_fields_ui(
    excel_bytes: bytes | None,
    fields: dict[str, str],
    *,
    key_prefix: str,
    label: str = "Apply to Excel",
) -> None:
    """Confirm + patch ProjectData; optional sidebar executive_summary override."""
    from ai.apply_drafts import patch_project_data_fields, preview_project_data_patch

    if not fields:
        return
    if not excel_bytes:
        st.info("Load Excel first to apply fields into ProjectData.")
        return
    overwrite = st.checkbox(
        "Overwrite filled ProjectData cells",
        value=False,
        key=f"{key_prefix}_overwrite",
    )
    will_apply, will_skip, will_add = preview_project_data_patch(
        excel_bytes, fields, overwrite_filled=overwrite
    )
    if will_apply:
        st.caption(
            f"Will set: {', '.join(will_apply)}"
            + (f" (new columns: {', '.join(will_add)})" if will_add else "")
        )
    if will_skip:
        st.caption(f"Will skip (already filled): {', '.join(will_skip)}")
    c1, c2 = st.columns(2)
    with c1:
        if st.button(label, key=f"{key_prefix}_apply_excel", width="stretch"):
            new_bytes, applied, skipped = patch_project_data_fields(
                excel_bytes, fields, overwrite_filled=overwrite
            )
            _set_session_excel_bytes(new_bytes)
            _merge_audit(
                AiAudit(features=["apply_drafts_excel"], used_llm=False)
            )
            st.success(
                f"Applied {len(applied)} field(s)"
                + (f"; skipped {len(skipped)}" if skipped else "")
                + ". Re-run pre-flight on the Report tab."
            )
            st.rerun()
    with c2:
        exec_text = fields.get("executive_summary", "").strip()
        if exec_text and st.button(
            "Apply executive summary override",
            key=f"{key_prefix}_apply_exec",
            width="stretch",
        ):
            st.session_state["pending_executive_summary"] = exec_text
            _merge_audit(
                AiAudit(features=["apply_exec_summary_override"], used_llm=False)
            )
            st.success(
                "Executive summary queued for sidebar override "
                "(turn off Simple mode to edit)."
            )
            st.rerun()


def _ai_context_digest(excel_bytes: bytes, meta: dict[str, str]) -> str:
    from ui.helpers import stable_upload_digest

    meta_sig = "|".join(
        f"{k}={meta.get(k, '')}"
        for k in ("report_type", "report_phase", "prepared_by", "date_of_issue")
    )
    return f"{stable_upload_digest('ai_excel', 'excel.xlsx', excel_bytes)}|{meta_sig}"


def _resolve_ai_context(
    excel_bytes: bytes | None,
    meta: dict[str, str],
    *,
    build_key: str,
    folder_mode: bool = False,
) -> dict[str, Any] | None:
    """Return last_context or a session-cached build — never rebuild on every paint."""
    ctx = st.session_state.get("last_context")
    if isinstance(ctx, dict) and ctx:
        return ctx
    if not excel_bytes:
        st.info(
            f"Load Excel on {_step1_input_hint(folder_mode)} "
            "or generate a report first."
        )
        return None
    digest = _ai_context_digest(excel_bytes, meta)
    cached = st.session_state.get("_ai_excel_context_cache") or {}
    if cached.get("digest") == digest and isinstance(cached.get("ctx"), dict):
        return cached["ctx"]
    st.caption("Build Excel context once for AI tools (or generate a report first).")
    if st.button("Build context from Excel", key=build_key, width="stretch"):
        built = _build_context_from_excel(excel_bytes, meta)
        if built:
            st.session_state["_ai_excel_context_cache"] = {"digest": digest, "ctx": built}
            st.rerun()
        st.warning("Could not build context from Excel.")
    return None


def _build_context_from_excel(excel_bytes: bytes, meta: dict[str, str]) -> dict[str, Any] | None:
    """Build context using a minimal valid template stub."""
    import os
    import tempfile
    from pathlib import Path

    from engine import generate_sample_template_docx
    from security import clamp_context

    path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            path = tmp.name
            generate_sample_template_docx(path)
            tpl = Path(path).read_bytes()
        engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=tpl)
        ctx = engine.build_context(meta)
        ctx, _ = clamp_context(ctx)
        return ctx
    except Exception:
        return None
    finally:
        if path and os.path.isfile(path):
            try:
                os.unlink(path)
            except OSError:
                pass


def render_ai_settings_sidebar(*, folder_mode: bool = False) -> None:
    from ui.onboarding import is_simple_mode

    simple = is_simple_mode()
    expanded = folder_mode and not simple
    label = "Advanced — AI options" if simple else "AI options"
    with st.sidebar.expander(label, expanded=expanded):
        settings = resolve_llm_settings()
        st.caption(ai_status_message(settings))
        if settings.available:
            st.caption(f"Configured provider: **{settings.label}**")
        else:
            st.caption(
                "Free options: **Ollama** (local, confidential) · **Gemini** / **Groq** (cloud free tier). "
                "See [09-ai-assistant.md](docs/09-ai-assistant.md)."
            )
        st.session_state.setdefault("ai_use_llm", settings.available)
        st.checkbox(
            "Use free/local LLM when available",
            key="ai_use_llm",
            help=(
                "Prefers Ollama (local) or Gemini/Groq free tier from secrets. "
                "Turn off for offline heuristics only. LLM never writes the report "
                "until you Apply/Merge — see docs/09-ai-assistant.md."
            ),
        )
        if folder_mode:
            st.caption(
                "Turn off for offline heuristics only when using **Analyze folder**."
            )


def render_ai_panel(
    *,
    excel_bytes: bytes | None,
    template_bytes: bytes | None,
    meta: dict[str, str],
    preflight: PreflightResult | None,
    folder_mode: bool = False,
) -> None:
    st.subheader("AI drafts & tools" if folder_mode else "AI tools")
    if folder_mode:
        st.info(
            "Use **Analyze folder** on step 1 to write inventory, narratives, and appendix "
            "suggestions to `ai_drafts/` on disk. Tools below work on the loaded Excel + "
            "template. **All AI output requires QP review** before client delivery."
        )
    else:
        st.info(
            "Optional helpers for tagging, lab PDF import, narratives, and QA. "
            "**All AI output requires QP review** before client delivery."
        )

    t1, t2 = st.tabs(["Data & templates", "QA & narratives"])

    if folder_mode:
        _tab_folder_drafts()
        st.divider()

    with t1:
        _tab_template_tagger(template_bytes, folder_mode=folder_mode)
        st.divider()
        _tab_lab_pdf(excel_bytes, meta, folder_mode=folder_mode)
        st.divider()
        _tab_well_log_pdf(excel_bytes, folder_mode=folder_mode)
        st.divider()
        _tab_apec_extract(excel_bytes, folder_mode=folder_mode)
        st.divider()
        _tab_narratives(excel_bytes, meta, folder_mode=folder_mode)

    with t2:
        _tab_copilot(preflight, meta, folder_mode=folder_mode)
        st.divider()
        _tab_gw_trends(excel_bytes, meta, folder_mode=folder_mode)
        st.divider()
        _tab_quality(excel_bytes, template_bytes, meta, folder_mode=folder_mode)


def _tab_folder_drafts() -> None:
    """Review on-disk ai_drafts/ from the loaded project folder."""
    st.subheader("Folder AI drafts (on disk)")
    root = st.session_state.get("project_folder_resolved")
    if not root:
        st.info("Load a project folder on step 1 to review `ai_drafts/` here.")
        return
    drafts_dir = Path(root) / "ai_drafts"
    if not drafts_dir.is_dir():
        st.info(
            "No `ai_drafts/` folder yet — run **Analyze folder** on step 1 to create drafts."
        )
        return

    review_files = (
        ("inventory.md", "markdown"),
        ("preflight_report.md", "markdown"),
        ("source_summaries.json", "json"),
        ("narratives.json", "json"),
        ("excel_field_suggestions.json", "json"),
        ("apecs_candidates.json", "json"),
        ("appendix_manifest.json", "json"),
        ("appendix_labels.json", "json"),
    )
    shown = 0
    for name, kind in review_files:
        path = drafts_dir / name
        if not path.is_file():
            continue
        shown += 1
        with st.expander(name, expanded=name in ("preflight_report.md", "narratives.json")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as e:
                st.error(user_safe_error(e))
                continue
            if kind == "json":
                try:
                    st.json(json.loads(text))
                except json.JSONDecodeError:
                    st.code(text)
            else:
                st.markdown(text)

    if shown == 0:
        st.caption("Run **Analyze folder** to populate inventory, preflight, and narratives.")
        return

    st.caption(f"Files live under `{drafts_dir}` — use **Apply** below or edit on disk.")

    from ai.apply_drafts import load_field_suggestions, load_narratives_payload

    excel_bytes = (
        st.session_state.get("project_folder_excel_bytes")
        or st.session_state.get("session_excel_bytes")
    )
    fields: dict[str, str] = {}
    narr_path = drafts_dir / "narratives.json"
    if narr_path.is_file():
        try:
            fields.update(load_narratives_payload(narr_path))
        except (json.JSONDecodeError, OSError) as e:
            st.warning(user_safe_error(e))
    sugg_path = drafts_dir / "excel_field_suggestions.json"
    if sugg_path.is_file():
        try:
            fields.update(load_field_suggestions(sugg_path))
        except (json.JSONDecodeError, OSError) as e:
            st.warning(user_safe_error(e))
    if fields:
        st.markdown("**Apply drafts into ProjectData**")
        _apply_fields_ui(excel_bytes, fields, key_prefix="folder_drafts")

    apec_path = drafts_dir / "apecs_candidates.json"
    if apec_path.is_file() and excel_bytes:
        try:
            payload = json.loads(apec_path.read_text(encoding="utf-8"))
            rows = payload.get("rows") or []
        except (json.JSONDecodeError, OSError) as e:
            st.warning(user_safe_error(e))
            rows = []
        if rows:
            st.markdown("**Apply APEC candidates to Excel (`Apecs` sheet)**")
            mode = st.radio(
                "APEC merge mode",
                ["append", "replace"],
                horizontal=True,
                key="folder_apec_merge_mode",
                help="Append renumbers APEC-IDs; replace overwrites the Apecs sheet.",
            )
            st.checkbox(
                "Also mark Phase II recommended on ProjectData when any APEC is Y",
                value=False,
                key="folder_apec_mark_phase2",
            )
            if st.button("Apply APECs to Excel", key="folder_apec_apply", width="stretch"):
                xlsx = apec_rows_to_xlsx_bytes(
                    rows, existing_excel=excel_bytes, mode=mode
                )
                _set_session_excel_bytes(xlsx)
                _merge_audit(AiAudit(features=["apec_apply_folder"], used_llm=False))
                if st.session_state.get("folder_apec_mark_phase2") and any(
                    str(r.get("phase2_recommended", "")).upper().startswith("Y")
                    for r in rows
                ):
                    from ai.apply_drafts import patch_project_data_fields

                    xlsx2, _, _ = patch_project_data_fields(
                        xlsx,
                        {"phase2_recommended": "Yes", "phase2_esa_required": "Yes"},
                        overwrite_filled=True,
                    )
                    _set_session_excel_bytes(xlsx2)
                st.success(f"Applied {len(rows)} APEC row(s) ({mode}). Re-run pre-flight.")
                st.rerun()


def _tab_apec_extract(excel_bytes: bytes | None, *, folder_mode: bool = False) -> None:
    st.subheader("4. Historical docs → APECs")
    st.markdown(
        "Extract Areas of Potential Environmental Concern from historical **PDF** or "
        "**Word (.docx)** text. Scanned image PDFs and JPG are **not** supported yet "
        "(Phase 2 OCR). AI suggestions require QP review before client delivery."
    )
    uploads = st.file_uploader(
        "Historical documents (PDF / DOCX)",
        type=["pdf", "docx"],
        accept_multiple_files=True,
        key="ai_apec_uploads",
    )
    if folder_mode:
        root = st.session_state.get("project_folder_resolved")
        if root:
            source_dir = Path(root) / "source"
            folder_pdfs = sorted(source_dir.glob("*.pdf")) if source_dir.is_dir() else []
            if folder_pdfs and st.button(
                "Extract APECs from all folder source/ PDFs",
                key="ai_apec_folder_btn",
                width="stretch",
            ):
                with st.spinner("Extracting APECs from source/..."):
                    results: list[ApecExtractResult] = []
                    try:
                        for p in folder_pdfs:
                            res, audit = extract_apecs_from_bytes(
                                p.read_bytes(), p.name, use_llm=_use_llm()
                            )
                            results.append(res)
                            _merge_audit(audit)
                        merged = merge_apec_results(results)
                        st.session_state["apec_extract"] = merged
                    except Exception as e:
                        st.error(user_safe_error(e))

    if uploads and st.button("Extract APECs", key="ai_apec_extract_btn", width="stretch"):
        with st.spinner("Scanning documents for APECs..."):
            results = []
            try:
                for up in uploads:
                    res, audit = extract_apecs_from_bytes(
                        up.getvalue(), up.name or "upload.pdf", use_llm=_use_llm()
                    )
                    results.append(res)
                    _merge_audit(audit)
                st.session_state["apec_extract"] = merge_apec_results(results)
            except Exception as e:
                st.error(user_safe_error(e))

    result = st.session_state.get("apec_extract")
    if not result:
        return
    st.caption(result.disclaimer)
    for w in result.warnings:
        st.warning(w)
    if not result.rows:
        return
    st.dataframe(
        [r.to_excel_dict() for r in result.rows],
        width="stretch",
        hide_index=True,
    )
    row_dicts = [r.to_excel_dict() for r in result.rows]
    mode = st.radio(
        "Merge mode",
        ["append", "replace"],
        horizontal=True,
        key="ai_apec_merge_mode",
    )
    xlsx = apec_rows_to_xlsx_bytes(
        row_dicts, existing_excel=excel_bytes, mode=mode
    )
    st.download_button(
        "Download Excel with Apecs sheet",
        data=xlsx,
        file_name="apecs_import.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
    st.checkbox(
        "Also mark Phase II recommended on ProjectData when any APEC is Y",
        value=False,
        key="ai_apec_mark_phase2",
    )
    if excel_bytes and st.button(
        "Merge into current workbook",
        key="ai_apec_merge_session",
        width="stretch",
    ):
        _set_session_excel_bytes(xlsx, name="apecs_import.xlsx")
        _merge_audit(AiAudit(features=["apec_merge_session"], used_llm=False))
        if st.session_state.get("ai_apec_mark_phase2") and any(
            r.phase2_recommended == "Y" for r in result.rows
        ):
            from ai.apply_drafts import patch_project_data_fields

            xlsx2, _, _ = patch_project_data_fields(
                xlsx,
                {"phase2_recommended": "Yes", "phase2_esa_required": "Yes"},
                overwrite_filled=True,
            )
            _set_session_excel_bytes(xlsx2)
        st.success("Apecs sheet merged — re-run pre-flight on the Report tab.")
        st.rerun()
    with st.expander("Text preview"):
        st.text(result.raw_text_preview or "(empty)")


def _tab_template_tagger(template_bytes: bytes | None, *, folder_mode: bool = False) -> None:
    st.subheader("1. Template tagger")
    st.markdown(
        "Suggests `{{ jinja }}` replacements for bracket placeholders and common phrases. "
        "Apply changes manually in Word (single formatting run per tag)."
    )
    report_type = (
        st.session_state.get("report_type_sel", "")
        or st.session_state.get("report_type", "")
        or "phase1_alberta"
    )
    st.caption(
        f"**Profile:** `{report_type}` — suggestions use "
        "`schemas/report_profiles.json` recommended fields "
        "(legacy `field_contract.json` as fallback allowlist)."
    )
    if report_type == "phase1_alberta":
        st.caption(
            "For PDF layouts, run `python scripts\\phase1_pdf_to_markup.py` locally, "
            "then upload the `-markup.docx`."
        )
    if not template_bytes:
        st.info(f"Load a Word template on {_step1_input_hint(folder_mode)} to analyze.")
        return
    if st.button("Analyze template tags", key="ai_tag_btn", width="stretch"):
        with st.spinner("Scanning document..."):
            try:
                suggestions, audit = suggest_template_tags(
                    template_bytes,
                    use_llm=_use_llm(),
                    report_type=report_type,
                )
                st.session_state["tag_suggestions"] = suggestions
                _merge_audit(audit)
            except Exception as e:
                st.error(user_safe_error(e))

    suggestions = st.session_state.get("tag_suggestions")
    if not suggestions:
        return
    st.success(f"{len(suggestions)} suggestion(s)")
    md = suggestions_to_markdown(suggestions)
    st.download_button(
        "Download tagging guide (.md)",
        data=md.encode("utf-8"),
        file_name="template_tagging_suggestions.md",
        mime="text/markdown",
        width="stretch",
    )
    with st.expander("Preview suggestions", expanded=True):
        for s in suggestions[:30]:
            st.markdown(f"- **{s.original_text}** → `{s.jinja_tag}` ({s.confidence:.0%}, {s.source})")
            if s.notes:
                st.caption(s.notes)


def _tab_lab_pdf(
    excel_bytes: bytes | None,
    meta: dict[str, str],
    *,
    folder_mode: bool = False,
) -> None:
    st.subheader("2. Lab PDF → Excel (LabResults / GroundwaterLab)")
    target = st.radio(
        "Target sheet",
        ["LabResults (Phase II)", "GroundwaterLab (monitoring)"],
        horizontal=True,
        key="ai_lab_target_sheet",
    )

    pdf_bytes: bytes | None = None
    pdf_label = ""
    if folder_mode:
        root = st.session_state.get("project_folder_resolved")
        if root:
            source_dir = Path(root) / "source"
            folder_pdfs = sorted(source_dir.glob("*.pdf")) if source_dir.is_dir() else []
            if folder_pdfs:
                pick = st.selectbox(
                    "Pick lab PDF from folder `source/`",
                    options=["(upload instead)"] + [p.name for p in folder_pdfs],
                    key="ai_lab_folder_pdf",
                )
                if pick != "(upload instead)":
                    pdf_label = pick
                    pdf_bytes = (source_dir / pick).read_bytes()

    pdf = st.file_uploader("Lab certificate / COA (PDF)", type=["pdf"], key="ai_lab_pdf")
    if pdf is not None:
        pdf_bytes = pdf.getvalue()
        pdf_label = pdf.name or "uploaded.pdf"

    if pdf_bytes and st.button("Extract lab table", key="ai_lab_extract", width="stretch"):
        with st.spinner(f"Parsing PDF{' ' + pdf_label if pdf_label else ''}..."):
            try:
                result = extract_lab_from_pdf(pdf_bytes, use_llm=_use_llm())
                st.session_state["lab_extract"] = result
                _merge_audit(
                    AiAudit(
                        features=["lab_pdf_extract"],
                        used_llm=result.source == "llm",
                    )
                )
            except Exception as e:
                st.error(user_safe_error(e))

    result = st.session_state.get("lab_extract")
    if not result:
        return
    for w in result.warnings:
        st.warning(w)
    if result.rows:
        st.dataframe(
            [r.to_excel_dict() for r in result.rows],
            width="stretch",
            hide_index=True,
        )
        if target.startswith("Groundwater"):
            xlsx = lab_rows_to_groundwater_xlsx_bytes(
                result.rows,
                existing_excel=excel_bytes,
            )
            dl_name = "gw_lab_import.xlsx"
            dl_label = "Download Excel with GroundwaterLab"
        else:
            xlsx = lab_rows_to_xlsx_bytes(
                result.rows,
                existing_excel=excel_bytes,
            )
            dl_name = "lab_import.xlsx"
            dl_label = "Download Excel with LabResults"
        st.download_button(
            dl_label,
            data=xlsx,
            file_name=dl_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
        if excel_bytes and st.button(
            "Merge into current workbook",
            key="ai_lab_merge_session",
            width="stretch",
        ):
            _set_session_excel_bytes(xlsx, name=dl_name)
            _merge_audit(AiAudit(features=["lab_pdf_merge_session"], used_llm=False))
            st.success("Lab sheet merged into session Excel — re-run pre-flight.")
            st.rerun()
    with st.expander("PDF text preview"):
        st.text(result.raw_text_preview or "(empty)")


def _tab_well_log_pdf(excel_bytes: bytes | None, *, folder_mode: bool = False) -> None:
    st.subheader("3. Well log PDF → MonitoringWells")
    pdf = st.file_uploader(
        "Borehole / well construction PDF",
        type=["pdf"],
        key="ai_well_log_pdf",
    )
    if pdf and st.button("Extract monitoring wells", key="ai_well_extract", width="stretch"):
        with st.spinner("Parsing well log..."):
            try:
                rows, warnings, audit = extract_wells_from_pdf(
                    pdf.getvalue(), use_llm=_use_llm()
                )
                st.session_state["well_extract_rows"] = rows
                st.session_state["well_extract_warnings"] = warnings
                _merge_audit(audit)
            except Exception as e:
                st.error(user_safe_error(e))

    rows = st.session_state.get("well_extract_rows")
    if not rows:
        return
    for w in st.session_state.get("well_extract_warnings") or []:
        st.warning(w)
    st.dataframe(
        [r.to_excel_dict() for r in rows],
        width="stretch",
        hide_index=True,
    )
    well_dicts = [r.to_excel_dict() for r in rows]
    xlsx = well_rows_to_xlsx_bytes(well_dicts, existing_excel=excel_bytes)
    st.download_button(
        "Download Excel with MonitoringWells",
        data=xlsx,
        file_name="monitoring_wells_import.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
    if excel_bytes and st.button(
        "Merge into current workbook",
        key="ai_well_merge_session",
        width="stretch",
    ):
        _set_session_excel_bytes(xlsx, name="monitoring_wells_import.xlsx")
        _merge_audit(AiAudit(features=["well_log_merge_session"], used_llm=False))
        st.success("MonitoringWells merged into session Excel — re-run pre-flight.")
        st.rerun()


def _tab_gw_trends(
    excel_bytes: bytes | None, meta: dict[str, str], *, folder_mode: bool = False
) -> None:
    st.subheader("2. Groundwater trend notes")
    ctx = _resolve_ai_context(
        excel_bytes, meta, build_key="ai_gw_build_ctx", folder_mode=folder_mode
    )
    if not ctx:
        return
    if st.button("Analyze trends", key="ai_gw_trends_btn", width="stretch"):
        notes, audit = analyze_groundwater_trends(ctx, use_llm=_use_llm())
        st.session_state["gw_trend_notes"] = notes
        _merge_audit(audit)
    for note in st.session_state.get("gw_trend_notes") or []:
        if note.severity == "warning":
            st.warning(note.message)
        else:
            st.info(note.message)


def _tab_narratives(
    excel_bytes: bytes | None, meta: dict[str, str], *, folder_mode: bool = False
) -> None:
    st.subheader("5. Narrative drafts (RAG-assisted)")
    ctx = _resolve_ai_context(
        excel_bytes, meta, build_key="ai_narr_build_ctx", folder_mode=folder_mode
    )
    if not ctx:
        return

    sections = st.multiselect(
        "Sections",
        options=["executive_summary", "site_description", "conclusions_limitations"],
        default=["executive_summary", "conclusions_limitations"],
    )
    if st.button("Draft narratives", key="ai_narrative_btn", width="stretch"):
        with st.spinner("Drafting..."):
            drafts, audit = draft_narratives(ctx, sections=sections, use_llm=_use_llm())
            st.session_state["narrative_drafts"] = drafts
            _merge_audit(audit)

    for draft in st.session_state.get("narrative_drafts") or []:
        st.markdown(f"**{draft.section.replace('_', ' ').title()}**")
        st.caption(draft.disclaimer)
        if draft.sources:
            st.caption(f"RAG sources: {', '.join(draft.sources)}")
        st.text_area(
            label=draft.section,
            value=draft.text,
            height=160,
            key=f"narrative_{draft.section}",
            label_visibility="collapsed",
        )

    drafts = st.session_state.get("narrative_drafts") or []
    if drafts and excel_bytes:
        from ai.apply_drafts import narratives_from_session_drafts

        # Prefer edited text_area values when present
        fields = narratives_from_session_drafts(drafts)
        for section, field in (
            ("executive_summary", "executive_summary"),
            ("site_description", "site_description"),
            ("conclusions_limitations", "conclusions_recommendations"),
        ):
            edited = st.session_state.get(f"narrative_{section}")
            if isinstance(edited, str) and edited.strip():
                fields[field] = edited.strip()
        st.markdown("**Apply narrative drafts**")
        _apply_fields_ui(excel_bytes, fields, key_prefix="narrative_drafts")


def _tab_copilot(
    preflight: PreflightResult | None,
    meta: dict[str, str],
    *,
    folder_mode: bool = False,
) -> None:
    st.subheader("1. Pre-flight copilot")
    if not preflight:
        st.info(
            f"Load Excel + template on {_step1_input_hint(folder_mode)} "
            "to run pre-flight first."
        )
        return
    if st.button("Explain pre-flight", key="ai_copilot_btn", width="stretch"):
        advice, audit = explain_preflight(preflight, meta, use_llm=_use_llm())
        st.session_state["copilot_advice"] = advice
        _merge_audit(audit)

    advice = st.session_state.get("copilot_advice")
    if not advice:
        return
    st.markdown(advice.summary)
    for i, step in enumerate(advice.steps, 1):
        st.markdown(f"{i}. {step}")
    if advice.excel_columns_to_add:
        st.markdown("**Add ProjectData columns:**")
        st.code(", ".join(advice.excel_columns_to_add))


def _tab_quality(
    excel_bytes: bytes | None,
    template_bytes: bytes | None,
    meta: dict[str, str],
    *,
    folder_mode: bool = False,
) -> None:
    st.subheader("3. Consistency & exceedance notes")
    ctx = _resolve_ai_context(
        excel_bytes, meta, build_key="ai_qa_build_ctx", folder_mode=folder_mode
    )
    if not ctx:
        pass
    elif st.button("Run consistency check", key="ai_consistency_btn", width="stretch"):
        findings, audit = check_consistency(
            ctx,
            template_bytes=template_bytes,
            use_llm=_use_llm() and ai_available(),
        )
        st.session_state["consistency_findings"] = findings
        _merge_audit(audit)

    for f in st.session_state.get("consistency_findings") or []:
        if f.severity == "error":
            st.error(f.message)
        elif f.severity == "warning":
            st.warning(f.message)
        else:
            st.info(f.message)
        if f.suggestion:
            st.caption(f"→ {f.suggestion}")

    st.divider()
    st.markdown("**Exceedance notes**")
    lab = (ctx or {}).get("lab_results") if ctx else None
    if not isinstance(lab, list) or not lab:
        st.info("No lab_results in context.")
        return
    if st.button("Generate exceedance notes", key="ai_exc_btn", width="stretch"):
        notes, audit = notes_for_lab_rows(
            lab,
            site_name=str((ctx or {}).get("site_name", "")),
            use_llm=_use_llm(),
        )
        st.session_state["exceedance_notes"] = notes
        _merge_audit(audit)

    for n in st.session_state.get("exceedance_notes") or []:
        st.markdown(f"**{n.analyte}** ({n.confidence:.0%}, {n.source}): {n.note}")

    if st.session_state.get("ai_audit_log"):
        with st.expander("AI audit log (session)"):
            st.json(st.session_state["ai_audit_log"])
