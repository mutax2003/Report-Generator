from __future__ import annotations

from typing import Any

import streamlit as st

from phrase_resolver import build_phrase_catalog_workbook_bytes
from report_profile import build_report_config_workbook_bytes
from sed002_compliance import build_qp_review_checklist_markdown, sed002_section_summary
from template_tools import PreflightResult, missing_fields_checklist, run_preflight
from ui.appendix_panel import all_appendix_labels_from_session
from ui.helpers import get_cached_report_engine, stable_upload_digest


_PREFLIGHT_CACHE_MAX = 16


def run_preflight_check(
    excel_bytes: bytes | None,
    template_bytes: bytes | None,
    meta: dict[str, str],
) -> PreflightResult | None:
    if not excel_bytes or not template_bytes:
        return None

    appendix_labels = sorted(all_appendix_labels_from_session())
    cache_key = (
        stable_upload_digest("excel", "excel.xlsx", excel_bytes),
        stable_upload_digest("template", "template.docx", template_bytes),
        tuple(sorted(meta.items())),
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


def _preflight_review_state(preflight: PreflightResult) -> tuple[int, int, list[str], bool]:
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


def _preflight_summary(preflight: PreflightResult) -> str:
    if preflight.errors:
        n = len(preflight.errors)
        return f"Fix **{n}** error{'s' if n != 1 else ''} before generating"
    missing_n, split_n, other_warnings, _ = _preflight_review_state(preflight)
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
) -> bool:
    """Pre-flight checklist. Returns True if Generate should be allowed."""
    if preflight is None:
        st.info("Load Excel and template in **step 1** to run pre-flight.")
        return False

    st.markdown(_preflight_summary(preflight))

    if preflight.errors:
        with st.status("Pre-flight failed — errors block Generate", expanded=True, state="error"):
            with st.expander("Must fix", expanded=True):
                for err in preflight.errors:
                    st.error(err)
        return False

    cov = preflight.coverage
    missing_n, split_n, other_warnings, has_review = _preflight_review_state(preflight)
    sed = preflight.sed002

    status_label = (
        "Pre-flight passed"
        if not has_review
        else "Pre-flight passed with warnings"
    )

    with st.status(status_label, expanded=has_review, state="complete"):
        if preflight.sheet_names:
            st.write("**Sheets:** " + ", ".join(preflight.sheet_names))
        if missing_n == 0 and cov:
            st.write("All template tags have data from Excel or the sidebar.")
        elif missing_n:
            st.write(
                f"**{missing_n}** tag(s) will render empty — **you can still generate**."
            )

        if sed:
            st.metric(
                "SED 002 §10",
                f"{sed.satisfied_count}/{sed.total_items} complete",
                f"{sed.completeness_pct}%",
                help="Section 10 checklist items satisfied",
            )
        elif preflight.phase2:
            st.metric(
                "Phase II checklist",
                f"{preflight.phase2.satisfied_count}/{preflight.phase2.total_items} complete",
                f"{preflight.phase2.completeness_pct}%",
            )
        elif preflight.groundwater:
            st.metric(
                "GW checklist",
                f"{preflight.groundwater.satisfied_count}/{preflight.groundwater.total_items} complete",
                f"{preflight.groundwater.completeness_pct}%",
            )
        elif preflight.reclamation:
            st.metric(
                "Reclamation checklist",
                f"{preflight.reclamation.satisfied_count}/{preflight.reclamation.total_items} complete",
                f"{preflight.reclamation.completeness_pct}%",
            )

        predicted = sorted(getattr(preflight, "predicted_appendix_labels", set()) or set())
        if predicted and report_phase.strip() == "Phase 1":
            labels = ", ".join(predicted)
            st.info(f"Will auto-generate appendices: **{labels}** (included in deliverable package)")

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

    if sed:
        sed_fail = not sed.ready_for_qp_review
        with st.expander(
            f"SED 002 Section 10 completeness ({sed.satisfied_count}/{sed.total_items})",
            expanded=sed_fail,
        ):
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


def _render_dwda_panel(dwda: Any, dwda_calc: Any = None) -> None:
    from dwda_compliance import build_dwda_qp_checklist_markdown
    from ecoventure_workbook import cell_contract_provenance, list_qp_template_files, read_qp_template_bytes

    scope_label = str(dwda.checklist_scope or "none").replace("_", " ")
    summary = (
        f"**{dwda.completeness_pct}%** complete "
        f"({dwda.satisfied_count}/{dwda.total_items}) — scope: **{scope_label}**"
    )
    if dwda.phase2_required:
        st.warning(f"DWDA / Directive 050: Phase II may be required — {summary}")
    else:
        st.markdown(f"**DWDA / Directive 050:** {summary}")

    with st.expander("DWDA / Directive 050 details", expanded=dwda.phase2_required or bool(dwda.required_missing)):
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
