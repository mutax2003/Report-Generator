from __future__ import annotations

import hashlib

import streamlit as st

from phrase_resolver import build_phrase_catalog_workbook_bytes
from report_profile import build_report_config_workbook_bytes
from sed002_compliance import build_qp_review_checklist_markdown, sed002_section_summary
from template_tools import PreflightResult, missing_fields_checklist, run_preflight
from ui.appendix_panel import all_appendix_labels_from_session, appendix_labels_from_session
from ui.helpers import get_cached_report_engine


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_preflight_check(
    excel_bytes: bytes | None,
    template_bytes: bytes | None,
    meta: dict[str, str],
) -> PreflightResult | None:
    if not excel_bytes or not template_bytes:
        return None
    import json

    appendix_labels = sorted(all_appendix_labels_from_session())
    cache_key = (
        _digest(excel_bytes),
        _digest(template_bytes),
        json.dumps(meta, sort_keys=True),
        json.dumps(appendix_labels),
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
    box[cache_key] = result
    return result


def render_preflight_panel(
    preflight: PreflightResult | None,
    *,
    report_phase: str = "Phase 2",
    report_type: str = "",
) -> bool:
    """Pre-flight checklist. Returns True if Generate should be allowed."""
    if preflight is None:
        st.info("Upload both files in **step 1** to run pre-flight.")
        return False

    if preflight.errors:
        with st.status("Pre-flight failed", expanded=True, state="error"):
            for err in preflight.errors:
                st.error(err)
        return False

    cov = preflight.coverage
    missing_n = len(cov.missing_in_data) if cov else 0
    status_label = "Pre-flight passed" if missing_n == 0 else "Pre-flight passed with warnings"
    status_state = "complete" if missing_n == 0 else "warning"

    with st.status(status_label, expanded=missing_n > 0, state=status_state):
        if preflight.sheet_names:
            st.write("**Sheets:** " + ", ".join(preflight.sheet_names))
        if missing_n == 0 and cov:
            st.write("All template tags have data from Excel or the sidebar.")
        elif missing_n:
            st.write(
                f"**{missing_n}** tag(s) will render empty — you can still generate."
            )

        sed = preflight.sed002
        if sed:
            st.metric(
                "SED 002 §10",
                f"{sed.completeness_pct}%",
                help=f"{sed.satisfied_count}/{sed.total_items} checklist items",
            )
        elif preflight.phase2:
            st.metric(
                "Phase II checklist",
                f"{preflight.phase2.completeness_pct}%",
                help=f"{preflight.phase2.satisfied_count}/{preflight.phase2.total_items} items",
            )
        elif preflight.groundwater:
            st.metric(
                "GW checklist",
                f"{preflight.groundwater.completeness_pct}%",
                help=f"{preflight.groundwater.satisfied_count}/{preflight.groundwater.total_items} items",
            )
        elif preflight.reclamation:
            st.metric(
                "Reclamation checklist",
                f"{preflight.reclamation.completeness_pct}%",
                help=f"{preflight.reclamation.satisfied_count}/{preflight.reclamation.total_items} items",
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

    sed = preflight.sed002
    if sed:
        with st.expander("SED 002 Section 10 completeness", expanded=not sed.ready_for_qp_review):
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
                use_container_width=True,
            )

    if cov:
        if cov.matched:
            with st.expander("Matched variables", expanded=False):
                st.write(", ".join(cov.matched))
        if cov.missing_in_data:
            with st.expander("Missing variables (will be blank)", expanded=False):
                st.code(", ".join(cov.missing_in_data), language=None)
            rt = report_type or "phase1_alberta"
            d1, d2, d3 = st.columns(3)
            with d1:
                st.download_button(
                    "Missing-fields checklist",
                    data=missing_fields_checklist(cov, report_type=rt),
                    file_name="missing_excel_columns.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
            with d2:
                st.download_button(
                    "ReportConfig sheet",
                    data=build_report_config_workbook_bytes(rt),
                    file_name=f"report_config_{rt}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            with d3:
                st.download_button(
                    "PhraseCatalog sheet",
                    data=build_phrase_catalog_workbook_bytes(),
                    file_name="phrase_catalog.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
        if cov.unused_in_template:
            with st.expander("Excel columns not used in template", expanded=False):
                st.caption(", ".join(cov.unused_in_template))

    if preflight.split_tag_issues:
        with st.expander("Split Jinja tags — fix in Word", expanded=True):
            for issue in preflight.split_tag_issues:
                st.text(issue)

    other_warnings = [
        w
        for w in preflight.warnings
        if not w.startswith("Possible broken tag:")
    ]
    for w in other_warnings:
        st.warning(w)

    return True
