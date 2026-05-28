from __future__ import annotations

import hashlib

import streamlit as st

from phrase_resolver import build_phrase_catalog_workbook_bytes
from report_profile import build_report_config_workbook_bytes
from template_tools import PreflightResult, missing_fields_checklist, run_preflight


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@st.cache_data(show_spinner=False)
def cached_preflight(
    excel_digest: str,
    template_digest: str,
    meta_json: str,
    excel_bytes: bytes,
    template_bytes: bytes,
) -> PreflightResult:
    import json

    meta = json.loads(meta_json)
    return run_preflight(excel_bytes, template_bytes, meta)


def run_preflight_check(
    excel_bytes: bytes | None,
    template_bytes: bytes | None,
    meta: dict[str, str],
) -> PreflightResult | None:
    if not excel_bytes or not template_bytes:
        return None
    import json

    return cached_preflight(
        _digest(excel_bytes),
        _digest(template_bytes),
        json.dumps(meta, sort_keys=True),
        excel_bytes,
        template_bytes,
    )


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
