"""Ecoventure Inc. branding for Streamlit (colors from ecoventure.ca)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

COLOR_SLATE = "#2e3540"
COLOR_MAGENTA = "#b24292"
COLOR_MAGENTA_HOVER = "#9a3680"
COLOR_BG_SOFT = "#f4f6f8"
# Semantic earth tones (not brand magenta) — pass / review / fail
COLOR_MOSS = "#3d6b4f"
COLOR_MOSS_BG = "#e8f0eb"
COLOR_AMBER = "#8a6a28"
COLOR_AMBER_BG = "#f7f0e0"
COLOR_TERRACOTTA = "#9a4434"
COLOR_TERRACOTTA_BG = "#f6e8e4"
COLOR_MUTED = "#5c6670"

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "ecoventure"
LOGO_WHITE = ASSETS_DIR / "icon_white.png"
FAVICON = ASSETS_DIR / "favicon.ico"
SITE_URL = "https://www.ecoventure.ca"
COMPANY_NAME = "Ecoventure Inc."
AUTHOR_NAME = "Andrew Liu"
ATTRIBUTION_LINE = f"Created by {AUTHOR_NAME}, {COMPANY_NAME}, Copyright 2026"


def favicon_path() -> str | None:
    if FAVICON.is_file():
        return str(FAVICON)
    return None


def inject_ecoventure_styles() -> None:
    """Light global polish — primary actions, sidebar, workflow chrome."""
    st.markdown(
        f"""
<style>
  .block-container {{
    padding-top: 0.85rem;
    padding-bottom: 2rem;
    max-width: 1100px;
  }}
  .ev-app-header {{
    position: sticky;
    top: 0;
    z-index: 999;
    background: #ffffff;
    padding-bottom: 0.25rem;
    margin-bottom: 0.35rem;
  }}
  div.stButton > button[kind="primary"],
  div.stButton > button[data-testid="stBaseButton-primary"] {{
    background-color: {COLOR_MAGENTA} !important;
    border-color: {COLOR_MAGENTA} !important;
    font-weight: 600;
  }}
  div.stButton > button[kind="primary"]:hover,
  div.stButton > button[data-testid="stBaseButton-primary"]:hover {{
    background-color: {COLOR_MAGENTA_HOVER} !important;
    border-color: {COLOR_MAGENTA_HOVER} !important;
  }}
  section[data-testid="stSidebar"] > div:first-child {{
    background-color: {COLOR_SLATE};
  }}
  section[data-testid="stSidebar"] label[data-testid="stWidgetLabel"] p,
  section[data-testid="stSidebar"] .stMarkdown p,
  section[data-testid="stSidebar"] .stCaption,
  section[data-testid="stSidebar"] h1,
  section[data-testid="stSidebar"] h2,
  section[data-testid="stSidebar"] h3 {{
    color: #e8eaed !important;
  }}
  section[data-testid="stSidebar"] .stMarkdown a {{
    color: #e8b8d9 !important;
  }}
  section[data-testid="stSidebar"] hr {{
    border-color: #4a5563;
  }}
  .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {{
    border-bottom-color: {COLOR_MAGENTA} !important;
    color: {COLOR_MAGENTA} !important;
    font-weight: 600;
  }}
  [data-testid="stFileUploader"] {{
    background: {COLOR_BG_SOFT};
    border-radius: 0.35rem;
    padding: 0.25rem;
  }}
  section[data-testid="stSidebar"] [data-testid="stImage"] img {{
    border-radius: 0.35rem;
    object-fit: cover;
    max-height: 120px;
  }}
  /* Windows-style menubar */
  .ev-menubar {{
    margin: 0.1rem 0 0.45rem 0;
    padding: 0.1rem 0.2rem;
    background: linear-gradient(180deg, #f7f8fa 0%, #eef1f4 100%);
    border: 1px solid #d5dae0;
    border-radius: 0.2rem;
  }}
  .ev-menubar [data-testid="stPopover"] button {{
    background: transparent !important;
    border: none !important;
    color: {COLOR_SLATE} !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    padding: 0.18rem 0.5rem !important;
    box-shadow: none !important;
  }}
  .ev-menubar [data-testid="stPopover"] button:hover {{
    background: rgba(178, 66, 146, 0.12) !important;
    color: {COLOR_MAGENTA} !important;
  }}
  /* Workflow stepper rail */
  .ev-stepper {{
    display: flex;
    align-items: center;
    gap: 0;
    margin: 0.35rem 0 0.85rem 0;
    padding: 0.55rem 0.75rem;
    background: {COLOR_BG_SOFT};
    border: 1px solid #d5dae0;
    border-radius: 0.35rem;
  }}
  .ev-step {{
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex: 0 1 auto;
    min-width: 0;
  }}
  .ev-step-num {{
    width: 1.55rem;
    height: 1.55rem;
    border-radius: 999px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 700;
    border: 2px solid #c5cbd3;
    color: {COLOR_MUTED};
    background: #fff;
    flex-shrink: 0;
  }}
  .ev-step-label {{
    font-size: 0.85rem;
    color: {COLOR_MUTED};
    white-space: nowrap;
  }}
  .ev-step-conn {{
    flex: 1 1 1.25rem;
    height: 2px;
    margin: 0 0.45rem;
    background: #c5cbd3;
    min-width: 0.75rem;
  }}
  .ev-step-done .ev-step-num {{
    background: {COLOR_MOSS};
    border-color: {COLOR_MOSS};
    color: #fff;
  }}
  .ev-step-done .ev-step-label {{
    color: {COLOR_MOSS};
    font-weight: 600;
  }}
  .ev-step-conn-done {{
    background: {COLOR_MOSS};
  }}
  .ev-step-current .ev-step-num {{
    background: {COLOR_MAGENTA};
    border-color: {COLOR_MAGENTA};
    color: #fff;
  }}
  .ev-step-current .ev-step-label {{
    color: {COLOR_SLATE};
    font-weight: 700;
  }}
  /* Status badges */
  .ev-badge {{
    display: inline-block;
    padding: 0.12rem 0.5rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    line-height: 1.4;
    border: 1px solid transparent;
    white-space: nowrap;
  }}
  .ev-badge-ok {{
    background: {COLOR_MOSS_BG};
    color: {COLOR_MOSS};
    border-color: #b9d0c2;
  }}
  .ev-badge-warn {{
    background: {COLOR_AMBER_BG};
    color: {COLOR_AMBER};
    border-color: #e2d4a8;
  }}
  .ev-badge-err {{
    background: {COLOR_TERRACOTTA_BG};
    color: {COLOR_TERRACOTTA};
    border-color: #e0bdb5;
  }}
  .ev-badge-muted {{
    background: #eef1f4;
    color: {COLOR_MUTED};
    border-color: #d5dae0;
  }}
  .ev-badge-info {{
    background: #e8eef6;
    color: #3a5678;
    border-color: #c5d3e5;
  }}
  /* Context / breadcrumb strip */
  .ev-context {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem 1rem;
    align-items: center;
    margin: 0 0 0.65rem 0;
    padding: 0.4rem 0.7rem;
    background: #fff;
    border: 1px solid #d5dae0;
    border-left: 3px solid {COLOR_MAGENTA};
    border-radius: 0.25rem;
    font-size: 0.85rem;
    color: {COLOR_SLATE};
  }}
  .ev-context-muted {{
    color: {COLOR_MUTED};
  }}
  .ev-context strong {{
    font-weight: 600;
  }}
  /* Next-steps / CTA emphasis cards */
  .ev-card-primary {{
    border-left: 3px solid {COLOR_MAGENTA} !important;
  }}
  .ev-sticky-cta {{
    position: sticky;
    bottom: 0;
    z-index: 50;
    background: rgba(255,255,255,0.96);
    padding: 0.35rem 0 0.15rem 0;
    margin-top: 0.25rem;
    border-top: 1px solid #e5e8ec;
  }}
  .ev-empty-panel {{
    padding: 0.85rem 1rem;
    background: {COLOR_BG_SOFT};
    border: 1px dashed #c5cbd3;
    border-radius: 0.35rem;
    color: {COLOR_MUTED};
    font-size: 0.9rem;
    margin: 0.35rem 0 0.75rem 0;
  }}
</style>
""",
        unsafe_allow_html=True,
    )


def status_badge_html(kind: str, label: str) -> str:
    """Return HTML for a status pill. kind: ok | warn | err | muted | info."""
    cls = {
        "ok": "ev-badge-ok",
        "warn": "ev-badge-warn",
        "err": "ev-badge-err",
        "muted": "ev-badge-muted",
        "info": "ev-badge-info",
    }.get(kind, "ev-badge-muted")
    safe = (
        label.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return f'<span class="ev-badge {cls}">{safe}</span>'


def render_status_badge(kind: str, label: str) -> None:
    st.markdown(status_badge_html(kind, label), unsafe_allow_html=True)


def _logo_data_uri() -> str:
    if not LOGO_WHITE.is_file():
        return ""
    import base64

    encoded = base64.b64encode(LOGO_WHITE.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def render_sidebar_branding() -> None:
    """Logo and company name at top of sidebar."""
    if LOGO_WHITE.is_file():
        st.sidebar.image(str(LOGO_WHITE), width=88)
    st.sidebar.markdown(f"### {COMPANY_NAME}")
    st.sidebar.caption("Environmental Management Services")
    from ui.alberta_imagery import render_sidebar_accent

    render_sidebar_accent()


def render_app_header() -> None:
    """Sticky compact header: brand band + optional lake strip (console, not splash)."""
    inject_ecoventure_styles()
    from ui.alberta_imagery import ensure_hero_lake_cached, hero_lake_data_uri

    ensure_hero_lake_cached()
    logo_uri = _logo_data_uri()
    lake_uri = hero_lake_data_uri()

    logo_html = ""
    if logo_uri:
        logo_html = (
            f'<img src="{logo_uri}" alt="{COMPANY_NAME}" '
            f'style="height:40px;width:auto;display:block;" />'
        )

    lake_html = ""
    if lake_uri:
        lake_html = (
            f'<img src="{lake_uri}" alt="" '
            f'style="width:100%;height:100%;min-height:64px;max-height:72px;'
            f'object-fit:cover;border-radius:0.35rem;display:block;" />'
        )

    st.markdown(
        f"""
<div class="ev-app-header">
  <div style="display:flex;gap:0.75rem;align-items:stretch;">
    <div style="flex:4;background:linear-gradient(135deg,{COLOR_SLATE} 0%,#3d4654 100%);
      border-radius:0.35rem;padding:0.55rem 1rem;border-left:4px solid {COLOR_MAGENTA};
      display:flex;align-items:center;gap:0.85rem;">
      <div style="flex-shrink:0;">{logo_html}</div>
      <div>
        <div style="color:#ffffff;font-size:1.15rem;font-weight:700;line-height:1.2;">
          {COMPANY_NAME}
        </div>
        <div style="color:#c8cdd4;font-size:0.92rem;margin-top:0.1rem;">
          ESA Report Generator
        </div>
        <div style="color:#9aa3ad;font-size:0.78rem;margin-top:0.2rem;">
          Alberta Phase I/II ESA &amp; groundwater ·
          <a href="{SITE_URL}" style="color:#e8b8d9;text-decoration:none;">ecoventure.ca</a>
        </div>
      </div>
    </div>
    <div style="flex:1.35;min-width:140px;max-width:220px;">{lake_html}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_app_footer() -> None:
    """Copyright and company attribution."""
    st.divider()
    st.caption(
        f"{ATTRIBUTION_LINE} · Internal report generation tool · "
        f"[{SITE_URL.replace('https://', '')}]({SITE_URL})"
    )
