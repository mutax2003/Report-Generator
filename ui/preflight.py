from __future__ import annotations

from typing import Any

import streamlit as st

from phrase_resolver import build_phrase_catalog_workbook_bytes
from report_profile import build_report_config_workbook_bytes
from sed002_compliance import build_qp_review_checklist_markdown, sed002_section_summary
from template_tools import PreflightResult, missing_fields_checklist, run_preflight
from ui.appendix_panel import all_appendix_labels_from_session
from ui.helpers import get_cached_report_engine, stable_upload_digest
from ui.onboarding import is_simple_mode


_PREFLIGHT_CACHE_MAX = 16
# Meta fields that affect preflight/SED/DWDA — exclude phrases & long free-text to avoid
# cache busts on every keystroke.
_PREFLIGHT_META_KEYS = (
    "report_type",
    "report_phase",
    "template_version",
    "prepared_by",
    "date_of_issue",
)


def run_preflight_check(
    excel_bytes: bytes | None,
    template_bytes: bytes | None,
    meta: dict[str, str],
) -> PreflightResult | None:
    if not excel_bytes or not template_bytes:
        return None

    appendix_labels = sorted(all_appendix_labels_from_session())
    meta_key = tuple((k, str(meta.get(k, ""))) for k in _PREFLIGHT_META_KEYS)
    cache_key = (
        stable_upload_digest("excel", "excel.xlsx", excel_bytes),
        stable_upload_digest("template", "template.docx", template_bytes),
        meta_key,
        tuple(appendix_labels),
    )
    box = st.session_state.setdefault("_preflight_result_cache", {})
    cached = box.get(cache_key)
    if cached is not None:
        return cached

    engine = get_cached_report_engine(excel_bytes, template_bytes)
    result = run_preflight(
        excel_bytes,
        template_bytes,
        meta,
        appendix_labels_present=set(appendix_labels),
        engine=engine,
    )
    if len(box) >= _PREFLIGHT_CACHE_MAX:
        box.pop(next(iter(box)))
    box[cache_key] = result
    return result


def preflight_allows_generate(preflight: PreflightResult | None) -> bool:
    """True when pre-flight ran and has no blocking errors."""
    return bool(preflight and preflight.can_generate)


def regulatory_compliance_warnings(preflight: PreflightResult | None) -> list[str]:
    """Hard warnings for SED/DWDA required gaps (does not block Generate)."""
    if preflight is None:
        return []
    messages: list[str] = []
    sed = preflight.sed002
    if sed and getattr(sed, "required_missing", None):
        n = len(sed.required_missing)
        messages.append(
            f"SED 002 §10: **{n}** required item(s) missing — "
            "deliverable may not pass QP / OneStop review."
        )
    dwda = getattr(preflight, "dwda", None)
    if dwda and getattr(dwda, "required_missing", None):
        n = len(dwda.required_missing)
        messages.append(
            f"DWDA Directive 050: **{n}** required item(s) missing — "
            "appendices or ProjectData may be incomplete."
        )
    if dwda and getattr(dwda, "phase2_required", False):
        messages.append(
            "DWDA: Phase II drilling waste assessment may be required before submission."
        )
    return messages


def preflight_review_state(preflight: PreflightResult) -> tuple[int, int, list[str], bool]:
    cov = preflight.coverage
    missing_n = len(cov.missing_in_data) if cov else 0
    split_n = len(preflight.split_tag_issues)
    other_warnings = [
        w
        for w in preflight.warnings
        if not w.startswith("Possible broken tag:")
    ]
    has_review = missing_n > 0 or split_n > 0 or bool(other_warnings)
    return missing_n, split_n, other_warnings, has_review


def preflight_summary_text(preflight: PreflightResult) -> str:
    if preflight.errors:
        n = len(preflight.errors)
        return f"Fix **{n}** error{'s' if n != 1 else ''} before generating"
    missing_n, split_n, other_warnings, _ = preflight_review_state(preflight)
    review_n = missing_n + split_n + len(other_warnings)
    if review_n:
        return (
            f"Ready to generate — **{review_n}** item{'s' if review_n != 1 else ''} "
            "to review (warnings do not block Generate)"
        )
    return "Ready to generate"


def render_preflight_panel(
    preflight: PreflightResult | None,
    *,
    report_phase: str = "Phase 2",
    report_type: str = "",
    meta: dict[str, str] | None = None,
    excel_bytes: bytes | None = None,
    template_bytes: bytes | None = None,
) -> bool:
    """Pre-flight checklist. Returns True if Generate should be allowed."""
    if preflight is None:
        st.info("Load Excel and template in **step 1** to run pre-flight.")
        return False

    st.markdown(preflight_summary_text(preflight))

    if preflight.errors:
        with st.status("Pre-flight failed — errors block Generate", expanded=True, state="error"):
            for err in preflight.errors:
                st.error(err)
        with st.expander("Optional AI help", expanded=False):
            st.caption("Advisory only — does not change Generate.")
            _render_preflight_copilot(preflight, meta or {"report_phase": report_phase})
        return False

    cov = preflight.coverage
    missing_n, split_n, other_warnings, has_review = preflight_review_state(preflight)
    sed = preflight.sed002

    status_label = (
        "Pre-flight passed"
        if not has_review
        else "Pre-flight passed with warnings"
    )

    with st.expander(status_label, expanded=False):
        if preflight.sheet_names:
            st.write("**Sheets:** " + ", ".join(preflight.sheet_names))
        if missing_n == 0 and cov:
            st.write("All template tags have data from Excel or the sidebar.")
        elif missing_n:
            st.write(
                f"**{missing_n}** tag(s) will render empty — **you can still generate**."
            )

        predicted = sorted(getattr(preflight, "predicted_appendix_labels", set()) or set())
        if predicted and report_phase.strip() == "Phase 1":
            labels = ", ".join(predicted)
            st.info(f"Will auto-generate appendices: **{labels}** (included in deliverable package)")

        with st.expander("Tag and table metrics", expanded=False):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Tags", preflight.template_var_count)
            with col2:
                st.metric("Matched", len(cov.matched) if cov else 0)
            with col3:
                st.metric("Missing", missing_n)
            with col4:
                if cov and cov.table_row_counts:
                    parts = [
                        f"{k}: {n}"
                        for k, n in sorted(cov.table_row_counts.items())
                        if n > 0
                    ]
                    st.metric("Table rows", ", ".join(parts) if parts else "0")
                elif report_phase.strip() == "Phase 1" and cov:
                    st.metric(
                        "Drill / tanks",
                        f"{cov.drilling_waste_row_count} / {cov.storage_tanks_row_count}",
                    )
                else:
                    st.metric("Lab rows", cov.lab_row_count if cov else 0)

    if has_review:
        with st.expander("Review recommended", expanded=missing_n > 0 or split_n > 0):
            if cov and cov.missing_in_data:
                st.markdown("**Missing variables (will be blank in the report)**")
                st.code(", ".join(cov.missing_in_data), language=None)
                rt = report_type or "phase1_alberta"
                d1, d2, d3 = st.columns(3)
                with d1:
                    st.download_button(
                        "Missing-fields checklist",
                        data=missing_fields_checklist(cov, report_type=rt),
                        file_name="missing_excel_columns.txt",
                        mime="text/plain",
                        width="stretch",
                    )
                with d2:
                    st.download_button(
                        "ReportConfig sheet",
                        data=build_report_config_workbook_bytes(rt),
                        file_name=f"report_config_{rt}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        width="stretch",
                    )
                with d3:
                    st.download_button(
                        "PhraseCatalog sheet",
                        data=build_phrase_catalog_workbook_bytes(),
                        file_name="phrase_catalog.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        width="stretch",
                    )
            if preflight.split_tag_issues:
                st.markdown("**Split Jinja tags — fix in Word**")
                for issue in preflight.split_tag_issues:
                    st.text(issue)
            for w in other_warnings:
                st.warning(w)

    if not is_simple_mode():
        with st.expander("Optional AI help", expanded=False):
            st.caption("Advisory only — does not block Generate. Full tools are on the **AI tools** tab.")
            _render_preflight_copilot(preflight, meta or {"report_phase": report_phase})
            _render_report_ai_cues(excel_bytes, template_bytes, meta or {"report_phase": report_phase})

    if sed:
        sed_fail = not sed.ready_for_qp_review
        with st.expander(
            f"Regulatory checklist (SED 002) — {sed.satisfied_count}/{sed.total_items}",
            expanded=sed_fail,
        ):
            st.metric(
                "SED 002 §10",
                f"{sed.satisfied_count}/{sed.total_items} complete",
                f"{sed.completeness_pct}%",
                help="Section 10 checklist items satisfied",
            )
            for sec_id, (ok, total) in sorted(sed002_section_summary(sed).items()):
                st.write(f"**{sec_id}**: {ok}/{total}")
            if sed.required_missing:
                st.caption("Required gaps:")
                for ir in sed.required_missing[:12]:
                    st.text(f"• {ir.section_id}: {ir.label}")
            st.download_button(
                "QP review checklist (SED 002)",
                data=build_qp_review_checklist_markdown(sed),
                file_name="sed002_qp_review_checklist.md",
                mime="text/markdown",
                width="stretch",
            )
    elif preflight.phase2:
        with st.expander(
            f"Phase II checklist — {preflight.phase2.satisfied_count}/{preflight.phase2.total_items}",
            expanded=False,
        ):
            st.metric(
                "Phase II",
                f"{preflight.phase2.satisfied_count}/{preflight.phase2.total_items} complete",
                f"{preflight.phase2.completeness_pct}%",
            )
    elif preflight.groundwater:
        with st.expander(
            f"Groundwater checklist — {preflight.groundwater.satisfied_count}/{preflight.groundwater.total_items}",
            expanded=False,
        ):
            st.metric(
                "GW",
                f"{preflight.groundwater.satisfied_count}/{preflight.groundwater.total_items} complete",
                f"{preflight.groundwater.completeness_pct}%",
            )
    elif preflight.reclamation:
        with st.expander(
            f"Reclamation checklist — {preflight.reclamation.satisfied_count}/{preflight.reclamation.total_items}",
            expanded=False,
        ):
            st.metric(
                "Reclamation",
                f"{preflight.reclamation.satisfied_count}/{preflight.reclamation.total_items} complete",
                f"{preflight.reclamation.completeness_pct}%",
            )

    if cov:
        if cov.matched:
            with st.expander("Matched variables", expanded=False):
                st.write(", ".join(cov.matched))
        if cov.unused_in_template:
            with st.expander("Excel columns not used in template", expanded=False):
                st.caption(", ".join(cov.unused_in_template))

    dwda = getattr(preflight, "dwda", None)
    if dwda and report_phase.strip() == "Phase 1":
        _render_dwda_panel(dwda, getattr(preflight, "dwda_calc", None))

    return True


def _render_preflight_copilot(
    preflight: PreflightResult, meta: dict[str, str]
) -> None:
    from ai.config import ai_available
    from ai.copilot import explain_preflight

    if st.button("Explain pre-flight", key="report_copilot_btn", width="stretch"):
        use_llm = st.session_state.get("ai_use_llm", ai_available())
        advice, audit = explain_preflight(preflight, meta, use_llm=use_llm)
        st.session_state["copilot_advice"] = advice
        existing: list = st.session_state.get("ai_audit_log") or []
        existing.append(audit.to_dict())
        st.session_state["ai_audit_log"] = existing[-20:]
    advice = st.session_state.get("copilot_advice")
    if not advice:
        return
    st.markdown(advice.summary)
    for i, step in enumerate(advice.steps, 1):
        st.markdown(f"{i}. {step}")
    if advice.excel_columns_to_add:
        st.markdown("**Add ProjectData columns:**")
        st.code(", ".join(advice.excel_columns_to_add))


def _render_report_ai_cues(
    excel_bytes: bytes | None,
    template_bytes: bytes | None,
    meta: dict[str, str],
) -> None:
    """Lightweight consistency / exceedance cues on the Report tab."""
    if not excel_bytes:
        return
    from ai.config import ai_available
    from ai.consistency import check_consistency
    from ai.exceedance_notes import notes_for_lab_rows
    from engine import ReportEngine

    st.markdown("**Data QA cues**")
    ctx = st.session_state.get("last_context")
    if not ctx and template_bytes:
        try:
            ctx = ReportEngine(excel_bytes, template_bytes).build_context(meta)
        except Exception:
            ctx = None
    if not ctx:
        st.info("Load Excel + template to run data QA cues.")
        return
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Run consistency check", key="report_consistency_btn", width="stretch"):
            findings, audit = check_consistency(
                ctx,
                template_bytes=template_bytes,
                use_llm=False,
            )
            st.session_state["consistency_findings"] = findings
            existing: list = st.session_state.get("ai_audit_log") or []
            existing.append(audit.to_dict())
            st.session_state["ai_audit_log"] = existing[-20:]
    with c2:
        lab = ctx.get("lab_results") if isinstance(ctx.get("lab_results"), list) else []
        if lab and st.button(
            "Exceedance notes", key="report_exceedance_btn", width="stretch"
        ):
            notes, audit = notes_for_lab_rows(
                lab,
                site_name=str(ctx.get("site_name", "")),
                use_llm=st.session_state.get("ai_use_llm", ai_available()),
            )
            st.session_state["exceedance_notes"] = notes
            existing = st.session_state.get("ai_audit_log") or []
            existing.append(audit.to_dict())
            st.session_state["ai_audit_log"] = existing[-20:]

    findings = st.session_state.get("consistency_findings") or []
    for f in findings[:8]:
        if f.severity == "error":
            st.error(f.message)
        elif f.severity == "warning":
            st.warning(f.message)
        else:
            st.info(f.message)
    if len(findings) > 8:
        st.caption(f"…and {len(findings) - 8} more — see **AI tools** tab.")

    for n in (st.session_state.get("exceedance_notes") or [])[:5]:
        st.markdown(f"**{n.analyte}**: {n.note}")
    notes = st.session_state.get("exceedance_notes") or []
    if len(notes) > 5:
        st.caption(f"…and {len(notes) - 5} more — see **AI tools** tab.")


def _render_dwda_panel(dwda: Any, dwda_calc: Any = None) -> None:
    from dwda_compliance import build_dwda_qp_checklist_markdown
    from ecoventure_workbook import cell_contract_provenance, list_qp_template_files, read_qp_template_bytes

    scope_label = str(dwda.checklist_scope or "none").replace("_", " ")
    summary = (
        f"**{dwda.completeness_pct}%** complete "
        f"({dwda.satisfied_count}/{dwda.total_items}) — scope: **{scope_label}**"
    )
    if dwda.phase2_required:
        st.warning(f"Drilling waste compliance: Phase II may be required — {summary}")
    else:
        st.markdown(f"**Drilling waste compliance (DWDA):** {summary}")

    with st.expander(
        "Drilling waste compliance (DWDA) — details",
        expanded=dwda.phase2_required or bool(dwda.required_missing),
    ):
        st.caption(dwda.guideline_summary)
        if dwda.cuttings_volume_on_lease_m3 is not None:
            st.write(
                f"On-lease cuttings volume: **{dwda.cuttings_volume_on_lease_m3} m³** "
                f"(>50 m³ triggers full Option 1 checklist when LWD on lease)"
            )
        if dwda_calc is not None and getattr(dwda_calc, "summary", ""):
            st.markdown(f"**Calculations:** {dwda_calc.summary}")
            cols = st.columns(3)
            if dwda_calc.metal_pass is not None:
                cols[0].metric(
                    "Metal (sacks/m)",
                    f"{dwda_calc.metal_sacks_per_metre:.4f}" if dwda_calc.metal_sacks_per_metre else "—",
                    "Pass" if dwda_calc.metal_pass else "Fail",
                )
            if dwda_calc.salt_pass is not None:
                cols[1].metric(
                    "Salt (sacks/m³)",
                    f"{dwda_calc.salt_sacks_per_m3:.4f}" if dwda_calc.salt_sacks_per_m3 else "—",
                    "Pass" if dwda_calc.salt_pass else "Fail",
                )
            if dwda_calc.dst_resistivity_sacks_total or dwda_calc.dst_chloride_sacks_total:
                dst_val = dwda_calc.dst_resistivity_sacks_total or dwda_calc.dst_chloride_sacks_total
                cols[2].metric("DST sacks", f"{dst_val:.2f}" if dst_val else "—", "OK")
            for w in getattr(dwda_calc, "cross_check_warnings", []) or []:
                st.warning(w)
        with st.expander("QP templates (Ecoventure)", expanded=False):
            prov = cell_contract_provenance()
            tpl_id = prov.get("workbook_template_id", "")
            contract_ver = prov.get("contract_version", "")
            if tpl_id or contract_ver:
                st.caption(
                    f"Cell contract: {tpl_id or 'ecoventure'} "
                    f"v{contract_ver or '—'}"
                )
            for zip_name, path in list_qp_template_files():
                mime = (
                    "application/vnd.ms-excel.sheet.macroEnabled.12"
                    if path.suffix.lower() == ".xltm"
                    else "application/vnd.ms-word.document.macroEnabled.12"
                )
                st.download_button(
                    f"Download {zip_name}",
                    data=read_qp_template_bytes(str(path)),
                    file_name=zip_name,
                    mime=mime,
                    width="stretch",
                    key=f"dwda_qp_tpl_{zip_name}",
                )
        if dwda.required_missing:
            st.markdown("**Must fix**")
            for ir in dwda.required_missing:
                st.error(f"{ir.section} — {ir.label}: {ir.detail}")
        if dwda.recommended_missing:
            st.markdown("**Review recommended**")
            for ir in dwda.recommended_missing[:10]:
                st.info(f"{ir.section} — {ir.label}: {ir.detail}")
        if dwda.phase2_reasons:
            st.markdown("**Phase II triggers**")
            for r in dwda.phase2_reasons:
                st.warning(r)
        st.download_button(
            "DWDA QP review checklist (Directive 050)",
            data=build_dwda_qp_checklist_markdown(dwda, calc_result=dwda_calc),
            file_name="dwda_directive050_qp_checklist.md",
            mime="text/markdown",
            width="stretch",
        )
