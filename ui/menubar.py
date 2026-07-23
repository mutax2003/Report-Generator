"""Windows-style application menu bar (Streamlit) with shortcut labels.

Streamlit runs in the browser — this is a desktop-like menubar, not a native
Win32 menu. Accelerators are shown beside items; F1 opens packaged HTML help.
"""

from __future__ import annotations

import os
import webbrowser
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
HELP_INDEX = ROOT / "help" / "index.html"

# Only F1 is hooked in the browser. Other labels are menu-only (honest accelerators).
SHORTCUTS: dict[str, str] = {
    "file_open_folder": "",
    "file_load_sample": "",
    "file_clear_outputs": "",
    "edit_simple_mode": "",
    "view_glossary": "",
    "help_contents": "F1",
    "help_shortcuts": "",
    "help_about": "",
}


def help_index_path() -> Path:
    return HELP_INDEX


def help_index_uri() -> str | None:
    path = help_index_path()
    if not path.is_file():
        return None
    return path.resolve().as_uri()


def open_help_contents(*, anchor: str = "") -> bool:
    """Open packaged HTML help in the default browser (Windows-friendly).

    On Streamlit Community Cloud / hosted servers, ``file://`` URIs point at the
    remote container and do not open for the tester — callers should show the
    in-app Help expander hint instead (see ``process_menubar_actions``).
    """
    from ui.workflow_mode import hosted_mode_enabled

    if hosted_mode_enabled():
        return False
    uri = help_index_uri()
    if not uri:
        return False
    if anchor:
        uri = f"{uri}#{anchor.lstrip('#')}"
    try:
        webbrowser.open(uri)
        return True
    except Exception:
        try:
            if os.name == "nt":
                os.startfile(str(help_index_path()))  # type: ignore[attr-defined]
                return True
        except OSError:
            return False
    return False


def ensure_help_built() -> Path | None:
    """Build help pack if missing; return index path or None.

    Skips work when the pack is already present and marked ready in session.
    """
    if HELP_INDEX.is_file() and st.session_state.get("_help_pack_ready"):
        return HELP_INDEX
    if HELP_INDEX.is_file():
        st.session_state["_help_pack_ready"] = True
        return HELP_INDEX
    try:
        import importlib.util

        path = ROOT / "scripts" / "build_help.py"
        spec = importlib.util.spec_from_file_location("esa_build_help", path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out = mod.build_help(ROOT)
        if out and Path(out).is_file():
            st.session_state["_help_pack_ready"] = True
        return out
    except Exception:
        return HELP_INDEX if HELP_INDEX.is_file() else None


def _pending(key: str) -> bool:
    return bool(st.session_state.pop(key, False))


def process_menubar_actions() -> None:
    """Apply deferred menu actions early in the page (before main widgets)."""
    from ui.workflow_mode import hosted_mode_enabled

    hosted = hosted_mode_enabled()

    if _pending("menu_open_help"):
        if hosted:
            st.session_state["menu_help_hosted"] = True
        else:
            ensure_help_built()
            if not open_help_contents():
                st.session_state["menu_help_missing"] = True

    if _pending("menu_show_shortcuts"):
        st.session_state["menu_shortcuts_open"] = True

    if _pending("menu_show_about"):
        st.session_state["menu_about_open"] = True

    if _pending("menu_show_glossary"):
        st.session_state["menu_glossary_open"] = True

    if _pending("menu_load_sample"):
        from ui.helpers import load_phase1_alberta_sample_into_session

        if load_phase1_alberta_sample_into_session():
            st.session_state["workflow_mode"] = st.session_state.get(
                "workflow_mode"
            ) or "upload"
            st.session_state["menu_action_toast"] = (
                "Alberta Phase I sample loaded — open the Report tab."
            )
        else:
            st.session_state["menu_action_toast"] = (
                "Sample files missing — run scripts/create_samples.py."
            )

    if _pending("menu_clear_outputs"):
        from ui.workflow_mode import clear_generation_session

        clear_generation_session()
        st.session_state["menu_action_toast"] = "Cleared generated outputs."

    if _pending("menu_toggle_simple"):
        from ui.onboarding import is_simple_mode

        cur = is_simple_mode()
        st.session_state["ux_simple_mode"] = not cur
        st.session_state["menu_action_toast"] = (
            "Simple mode " + ("on" if not cur else "off") + "."
        )

    if _pending("menu_change_workflow"):
        from ui.workflow_mode import reset_workflow_session

        reset_workflow_session()
        st.session_state["menu_action_toast"] = "Choose a workflow to continue."
        # No st.rerun() — caller processes actions before reading workflow mode.

    if _pending("menu_focus_folder"):
        if hosted:
            st.session_state["menu_action_toast"] = (
                "Project folder is unavailable on this hosted server — use Excel + template upload."
            )
        else:
            st.session_state["workflow_mode"] = "folder"
            st.session_state["menu_highlight_folder_path"] = True
            st.session_state["menu_action_toast"] = (
                "Switched to project folder — paste a path or click Browse…"
            )

    if _pending("menu_restore_checklist"):
        st.session_state["ux_checklist_dismissed"] = False
        st.session_state["ux_checklist_force_show"] = True
        st.session_state["menu_action_toast"] = "Checklist restored in sidebar."


def _menu_item(label: str, shortcut: str, pending_key: str, *, key: str) -> None:
    caption = f"{label}  {shortcut}" if shortcut else label
    if st.button(caption, key=key, width="stretch"):
        st.session_state[pending_key] = True
        st.rerun()


def render_menubar(*, folder_mode: bool = False) -> None:
    """Render File / Edit / View / Tools / Help menubar under the app header."""
    from ui.workflow_mode import hosted_mode_enabled

    hosted = hosted_mode_enabled()

    # Cheap: mark ready if help exists; build only when Help is opened or F1 needs URI.
    if HELP_INDEX.is_file():
        st.session_state["_help_pack_ready"] = True
    elif not hosted and not st.session_state.get("_help_build_attempted"):
        st.session_state["_help_build_attempted"] = True
        ensure_help_built()

    toast = st.session_state.pop("menu_action_toast", None)
    if toast:
        st.toast(toast)

    if st.session_state.pop("menu_help_hosted", False):
        st.info(
            "**F1 / Help → Contents** opens local `file://` help on the server, which "
            "does not work in Streamlit Community Cloud. Use the in-app "
            "**Help & documentation** expander on the Report tab instead."
        )

    if st.session_state.pop("menu_help_missing", False):
        st.warning(
            "Help files not found. Run `python scripts/build_help.py` "
            "or reopen after deploy includes the `help/` folder."
        )

    st.markdown('<div class="ev-menubar">', unsafe_allow_html=True)
    c_file, c_edit, c_view, c_tools, c_help, c_spacer = st.columns(
        [1, 1, 1, 1, 1, 4], gap="small"
    )

    with c_file:
        with st.popover("File", use_container_width=True):
            st.caption("File")
            # Local folder paths are unavailable on Cloud / Docker hosted mode.
            if not hosted:
                if not folder_mode:
                    _menu_item(
                        "Open project folder…",
                        SHORTCUTS["file_open_folder"],
                        "menu_focus_folder",
                        key="menu_file_open_folder",
                    )
                else:
                    _menu_item(
                        "Focus folder path",
                        SHORTCUTS["file_open_folder"],
                        "menu_focus_folder",
                        key="menu_file_focus_folder",
                    )
            _menu_item(
                "Load Alberta Phase I sample",
                SHORTCUTS["file_load_sample"],
                "menu_load_sample",
                key="menu_file_sample",
            )
            st.divider()
            _menu_item(
                "Clear generated outputs",
                SHORTCUTS["file_clear_outputs"],
                "menu_clear_outputs",
                key="menu_file_clear",
            )
            if not hosted:
                _menu_item(
                    "Change workflow…",
                    "",
                    "menu_change_workflow",
                    key="menu_file_workflow",
                )

    with c_edit:
        with st.popover("Edit", use_container_width=True):
            st.caption("Edit")
            _menu_item(
                "Toggle Simple mode",
                SHORTCUTS["edit_simple_mode"],
                "menu_toggle_simple",
                key="menu_edit_simple",
            )

    with c_view:
        with st.popover("View", use_container_width=True):
            st.caption("View")
            _menu_item(
                "Glossary",
                SHORTCUTS["view_glossary"],
                "menu_show_glossary",
                key="menu_view_glossary",
            )
            _menu_item(
                "Getting started checklist",
                "",
                "menu_restore_checklist",
                key="menu_view_checklist",
            )

    with c_tools:
        with st.popover("Tools", use_container_width=True):
            st.caption("Tools")
            if st.button("Go to AI tools tab", key="menu_tools_ai_tab", width="stretch"):
                st.session_state["menu_action_toast"] = (
                    'Open the **AI tools** tab above for tagger, lab/APEC extract, and Apply drafts.'
                )
                st.rerun()
            if not hosted:
                st.caption("Analyze folder is on the project-folder step.")

    with c_help:
        with st.popover("Help", use_container_width=True):
            st.caption("Help")
            _menu_item(
                "Contents",
                SHORTCUTS["help_contents"],
                "menu_open_help",
                key="menu_help_contents",
            )
            _menu_item(
                "Keyboard shortcuts",
                SHORTCUTS["help_shortcuts"],
                "menu_show_shortcuts",
                key="menu_help_shortcuts",
            )
            _menu_item(
                "About ESA Report Generator",
                SHORTCUTS["help_about"],
                "menu_show_about",
                key="menu_help_about",
            )

    st.markdown("</div>", unsafe_allow_html=True)

    _inject_f1_help_listener(hosted=hosted)
    _render_menu_dialogs(hosted=hosted)


def _inject_f1_help_listener(*, hosted: bool = False) -> None:
    """F1 opens packaged help locally; on hosted Cloud, show an in-browser tip instead."""
    if hosted:
        st.html(
            """
<script>
(function() {
  const handler = function(e) {
    if (e.key === 'F1') {
      e.preventDefault();
      window.alert(
        'F1 local help is not available on Streamlit Community Cloud. ' +
        'Open the Help & documentation expander on the Report tab.'
      );
    }
  };
  const doc = window.parent.document;
  doc.removeEventListener('keydown', window.__esaF1Help);
  window.__esaF1Help = handler;
  doc.addEventListener('keydown', handler);
})();
</script>
""",
            unsafe_allow_javascript=True,
        )
        return

    uri = help_index_uri() or ""
    safe = uri.replace("\\", "\\\\").replace("'", "\\'")
    st.html(
        f"""
<script>
(function() {{
  const helpUri = '{safe}';
  const handler = function(e) {{
    if (e.key === 'F1') {{
      e.preventDefault();
      if (helpUri) {{
        window.open(helpUri, '_blank');
      }}
    }}
  }};
  const doc = window.parent.document;
  doc.removeEventListener('keydown', window.__esaF1Help);
  window.__esaF1Help = handler;
  doc.addEventListener('keydown', handler);
}})();
</script>
""",
        unsafe_allow_javascript=True,
    )


def _render_menu_dialogs(*, hosted: bool = False) -> None:
    if st.session_state.pop("menu_shortcuts_open", False):
        folder_row = (
            ""
            if hosted
            else "| Open / focus project folder | **File** menu |\n"
        )
        help_row = (
            "| Help contents | In-app **Help & documentation** expander "
            "(F1 `file://` help is unavailable on Cloud) |"
            if hosted
            else "| Help contents | **F1** (global) or **Help → Contents** |"
        )
        with st.expander("Keyboard shortcuts", expanded=True):
            st.markdown(
                f"""
| Action | How |
|--------|-----|
{help_row}
{folder_row}| Load Alberta Phase I sample | **File** menu |
| Clear generated outputs | **File** menu |
| Toggle Simple mode | **Edit** menu |
| Glossary | **View** menu |

Only **F1** is hooked in the browser. Other actions are menu-driven (Streamlit does not
own a native OS menu bar).
"""
            )

    if st.session_state.pop("menu_about_open", False):
        from ui.branding import ATTRIBUTION_LINE, COMPANY_NAME, SITE_URL

        with st.expander("About", expanded=True):
            st.markdown(
                f"""
### ESA Report Generator
**{COMPANY_NAME}** — Alberta Phase I/II ESA & groundwater reporting.

{ATTRIBUTION_LINE}

Website: [{SITE_URL}]({SITE_URL})

AI features are advisory; QP review is required before client delivery.
"""
            )

    if st.session_state.pop("menu_glossary_open", False):
        from ui.onboarding import render_glossary_expander

        render_glossary_expander(expanded=True)


def menubar_smoke_labels() -> list[str]:
    """Labels for AppTest assertions."""
    return ["File", "Edit", "View", "Tools", "Help"]
