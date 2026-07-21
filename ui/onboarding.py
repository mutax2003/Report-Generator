"""First-run welcome, next-action cards, glossary, and sidebar checklist."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import streamlit as st

from template_tools import PreflightResult
from ui.appendix_panel import (
    appendix_labels_from_session,
    first_missing_onestop_label,
    generated_appendix_labels,
)
from ui.workflow_mode import WORKFLOW_FOLDER, WorkflowMode

ActionPriority = Literal["error", "warning", "info", "ready"]

GLOSSARY: dict[str, str] = {
    "OneStop": (
        "Alberta Energy Regulator (AER) online portal for submitting Phase I ESA "
        "reports and supporting documents."
    ),
    "SED 002": (
        "AER Standard for Environmental Due Diligence — Section 10 checklist items "
        "that must be satisfied before QP sign-off on a Phase I report."
    ),
    "DWDA": (
        "Drilling Waste Disposal Area — compliance with Directive 050 for on-lease "
        "drilling waste and cuttings volumes."
    ),
    "Deliverable package": (
        "ZIP file containing the Word report, manifest JSON, appendices folder, "
        "and OneStop export summary — use this for client delivery and AER upload prep."
    ),
}

_GETTING_STARTED_STEPS: tuple[tuple[str, str], ...] = (
    ("workflow", "Choose workflow"),
    ("prepared_by", "Set Prepared by"),
    ("files", "Load Excel + template"),
    ("preflight", "Pre-flight passes"),
    ("generate", "Generate report"),
    ("download", "Download deliverable zip"),
)


@dataclass(frozen=True)
class NextAction:
    priority: ActionPriority
    title: str
    detail: str
    action_hint: str = ""


def is_simple_mode() -> bool:
    """Simple mode defaults on until the user dismisses welcome or toggles off."""
    if "ux_simple_mode" not in st.session_state:
        return not st.session_state.get("ux_welcome_dismissed", False)
    return bool(st.session_state.ux_simple_mode)


def render_welcome_card(mode: WorkflowMode) -> None:
    """Dismissible first-visit banner after workflow pick."""
    if st.session_state.get("ux_welcome_dismissed"):
        return
    if not st.session_state.get("show_welcome", True):
        return

    if mode == WORKFLOW_FOLDER:
        bullets = (
            "Enter your **project folder path** and click **Load folder**.",
            "Open the **Report** tab — review pre-flight, then **Generate report**.",
            "Download the **deliverable package (.zip)** when ready for OneStop prep.",
        )
    else:
        bullets = (
            "Set **Prepared by** in the sidebar (or use **Load Alberta Phase I sample**).",
            "Upload Excel + Word template, then open the **Report** tab.",
            "Download the **deliverable package (.zip)** — your primary output.",
        )

    with st.container(border=True):
        st.markdown("#### Welcome — quick start")
        for b in bullets:
            st.markdown(f"- {b}")
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("Got it", type="primary", key="ux_welcome_dismiss"):
                st.session_state.ux_welcome_dismissed = True
                st.session_state.show_welcome = False
                st.rerun()


def compute_next_actions(
    preflight: PreflightResult | None,
    *,
    has_excel: bool,
    has_template: bool,
    has_output: bool,
    report_phase: str = "Phase 1",
    report_type: str = "",
    prepared_by: str | None = None,
) -> list[NextAction]:
    """Ordered plain-language actions (errors first, max 5 returned)."""
    actions: list[NextAction] = []

    if not has_excel:
        actions.append(
            NextAction(
                "error",
                "Load Excel data",
                "Upload a `.xlsx` file with a `ProjectData` sheet, or load a project folder.",
                "Step 1 — Excel column",
            )
        )
    if not has_template:
        actions.append(
            NextAction(
                "error",
                "Load Word template",
                "Upload a tagged `.docx` or `.pdf` template.",
                "Step 1 — Template column",
            )
        )
    if not has_excel or not has_template:
        return actions[:5]

    if prepared_by is None:
        try:
            prepared_by = str(st.session_state.get("sidebar_prepared_by") or "")
        except Exception:
            prepared_by = ""
    if not (prepared_by or "").strip():
        actions.append(
            NextAction(
                "warning",
                "Set Prepared by",
                "Author name is empty — enter it under **Project metadata** in the sidebar.",
                "Sidebar → Project metadata",
            )
        )

    if preflight is None:
        actions.append(
            NextAction(
                "info",
                "Waiting for pre-flight",
                "Files loaded — pre-flight will run automatically.",
            )
        )
        return actions[:5]

    for err in preflight.errors[:3]:
        actions.append(
            NextAction(
                "error",
                "Fix pre-flight error",
                err,
                "Step 2 — Pre-flight",
            )
        )
    if preflight.errors:
        return actions[:5]

    cov = preflight.coverage
    missing_n = len(cov.missing_in_data) if cov else 0
    if missing_n:
        actions.append(
            NextAction(
                "warning",
                f"{missing_n} template tag(s) missing in Excel",
                "These fields will be blank in the report. Download the missing-fields checklist.",
                "Step 2 — Pre-flight → Review recommended",
            )
        )

    if preflight.split_tag_issues:
        actions.append(
            NextAction(
                "warning",
                "Split Jinja tags in Word template",
                f"{len(preflight.split_tag_issues)} tag(s) may not merge correctly — re-type each tag as one piece in Word.",
                "Step 2 — Pre-flight",
            )
        )

    if report_phase.strip() == "Phase 1" and report_type == "phase1_alberta":
        missing = first_missing_onestop_label(
            appendix_labels_from_session(),
            preflight.predicted_appendix_labels,
        )
        if missing:
            actions.append(
                NextAction(
                    "warning",
                    f"Appendix {missing} not uploaded",
                    "Phase I OneStop packages typically need PDFs for B, C, E, F, and H.",
                    "Step 2b — Appendices",
                )
            )

    sed = preflight.sed002
    if sed and not sed.ready_for_qp_review:
        actions.append(
            NextAction(
                "warning",
                "SED 002 checklist incomplete",
                f"{sed.satisfied_count}/{sed.total_items} items satisfied — review before QP sign-off.",
                "Step 2 — Regulatory checklist (SED 002)",
            )
        )

    dwda = getattr(preflight, "dwda", None)
    if dwda and report_phase.strip() == "Phase 1" and dwda.phase2_required:
        actions.append(
            NextAction(
                "warning",
                "Phase II may be required (DWDA)",
                "Drilling waste compliance flagged Phase II triggers — review DWDA panel.",
                "Step 2 — Drilling waste compliance (DWDA)",
            )
        )

    if has_output:
        generated = generated_appendix_labels()
        for label in ("D", "G"):
            if label in generated:
                actions.append(
                    NextAction(
                        "info",
                        f"Export Appendix {label} to PDF",
                        "Auto-generated appendices are Word files — export to PDF before OneStop upload.",
                        "Step 4 — Download",
                    )
                )
                break
        actions.append(
            NextAction(
                "ready",
                "Download deliverable package",
                "Use the primary zip button below — it includes report, manifest, appendices, and OneStop export.",
                "Step 4 — Download",
            )
        )
    elif not actions:
        actions.append(
            NextAction(
                "ready",
                "Ready to generate",
                "Pre-flight passed with no blocking errors. Click **Generate report**. Optional appendix PDFs: use **Appendices** below the button before generating (or generate again after upload).",
                "Step 3 — Generate",
            )
        )

    return actions[:5]


def render_next_actions_card(actions: list[NextAction]) -> None:
    """Top-of-Report-tab summary of what to do next (authoritative status rail)."""
    if not actions:
        return
    from ui.branding import status_badge_html

    with st.container(border=True):
        st.markdown("**Your next steps**")
        for act in actions:
            kind = {
                "error": "err",
                "warning": "warn",
                "ready": "ok",
                "info": "info",
            }.get(act.priority, "muted")
            badge = status_badge_html(kind, act.title)
            line = f"{badge} — {act.detail}"
            if act.action_hint:
                line += f' <span class="ev-context-muted">({act.action_hint})</span>'
            st.markdown(line, unsafe_allow_html=True)


def render_glossary_expander(*, expanded: bool = False) -> None:
    with st.expander("Glossary (OneStop, SED 002, DWDA)", expanded=expanded):
        for term, definition in GLOSSARY.items():
            st.markdown(f"**{term}** — {definition}")


def _files_loaded() -> bool:
    if st.session_state.get("project_folder_excel_bytes"):
        return bool(st.session_state.get("project_folder_template_bytes"))
    if st.session_state.get("session_excel_bytes"):
        return bool(st.session_state.get("session_template_bytes"))
    return bool(st.session_state.get("upload_excel")) and bool(
        st.session_state.get("upload_template")
    )


def _preflight_passed() -> bool:
    for result in (st.session_state.get("_preflight_result_cache") or {}).values():
        if getattr(result, "can_generate", False):
            return True
    return False


def _step_complete(step_id: str) -> bool:
    if step_id == "workflow":
        return bool(st.session_state.get("workflow_mode"))
    if step_id == "prepared_by":
        return bool((st.session_state.get("sidebar_prepared_by") or "").strip())
    if step_id == "files":
        return _files_loaded()
    if step_id == "preflight":
        return _preflight_passed()
    if step_id == "generate":
        return bool(
            st.session_state.get("generated_docx")
            or st.session_state.get("generated_batch")
        )
    if step_id == "download":
        return bool(st.session_state.get("ux_deliverable_download_clicked"))
    return False


def render_getting_started_checklist() -> None:
    """Sidebar checklist until dismissed or all steps complete."""
    force_show = bool(st.session_state.pop("ux_checklist_force_show", False))
    if st.session_state.get("ux_checklist_dismissed") and not force_show:
        return

    steps_done = {step_id: _step_complete(step_id) for step_id, _ in _GETTING_STARTED_STEPS}
    done_count = sum(steps_done.values())
    if done_count >= len(_GETTING_STARTED_STEPS) and not force_show:
        return

    with st.sidebar.expander(
        "Getting started",
        expanded=force_show or done_count < 3,
    ):
        for step_id, label in _GETTING_STARTED_STEPS:
            mark = "✓" if steps_done[step_id] else "○"
            st.markdown(f"{mark} {label}")
        if force_show and done_count >= len(_GETTING_STARTED_STEPS):
            st.caption("All steps complete — checklist restored for review.")
        if st.button("Dismiss checklist", key="ux_checklist_dismiss", width="stretch"):
            st.session_state.ux_checklist_dismissed = True
            st.rerun()


def render_input_status_chips(*, has_excel: bool, has_template: bool) -> None:
    """Compact step-1 file status with recovery hints (uses shared status badges)."""
    from ui.branding import status_badge_html
    from ui.helpers import session_loaded_file_names

    ex_name, tpl_name = session_loaded_file_names()
    c1, c2 = st.columns(2)
    with c1:
        if has_excel:
            label = ex_name or "loaded"
            st.markdown(
                f"Excel {status_badge_html('ok', label)}",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"Excel {status_badge_html('err', 'missing')}",
                unsafe_allow_html=True,
            )
            st.caption("Upload above or **Load Alberta Phase I sample**.")
    with c2:
        if has_template:
            label = tpl_name or "loaded"
            st.markdown(
                f"Template {status_badge_html('ok', label)}",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"Template {status_badge_html('err', 'missing')}",
                unsafe_allow_html=True,
            )
            st.caption("Upload a tagged `.docx` / `.pdf`, or load the sample.")
