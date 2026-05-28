"""Ecoventure Inc. branding for Streamlit (colors from ecoventure.ca)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

COLOR_SLATE = "#2e3540"
COLOR_MAGENTA = "#b24292"
COLOR_MAGENTA_HOVER = "#9a3680"
COLOR_BG_SOFT = "#f4f6f8"

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
    """Light global polish — primary actions, sidebar, spacing."""
    st.markdown(
        f"""
<style>
  .block-container {{
    padding-top: 1.25rem;
    padding-bottom: 2rem;
    max-width: 1100px;
  }}
  .ev-app-header {{
    position: sticky;
    top: 0;
    z-index: 999;
    background: #ffffff;
    padding-bottom: 0.35rem;
    margin-bottom: 0.5rem;
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
    border-radius: 0.5rem;
    padding: 0.25rem;
  }}
  section[data-testid="stSidebar"] [data-testid="stImage"] img {{
    border-radius: 0.5rem;
    object-fit: cover;
    max-height: 140px;
  }}
</style>
""",
        unsafe_allow_html=True,
    )


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
    """Sticky header: Ecoventure band + lake.jpg embedded (survives Generate reruns)."""
    inject_ecoventure_styles()
    from ui.alberta_imagery import ensure_hero_lake_cached, hero_lake_data_uri

    ensure_hero_lake_cached()
    logo_uri = _logo_data_uri()
    lake_uri = hero_lake_data_uri()

    logo_html = ""
    if logo_uri:
        logo_html = (
            f'<img src="{logo_uri}" alt="{COMPANY_NAME}" '
            f'style="height:56px;width:auto;display:block;" />'
        )

    lake_html = ""
    if lake_uri:
        lake_html = (
            f'<img src="{lake_uri}" alt="" '
            f'style="width:100%;height:100%;min-height:120px;max-height:180px;'
            f'object-fit:cover;border-radius:0.5rem;display:block;" />'
        )

    st.markdown(
        f"""
<div class="ev-app-header">
  <div style="display:flex;gap:1rem;align-items:stretch;">
    <div style="flex:3;background:linear-gradient(135deg,{COLOR_SLATE} 0%,#3d4654 100%);
      border-radius:0.5rem;padding:0.85rem 1.25rem;border-left:4px solid {COLOR_MAGENTA};
      display:flex;align-items:center;gap:1rem;">
      <div style="flex-shrink:0;">{logo_html}</div>
      <div>
        <div style="color:#ffffff;font-size:1.4rem;font-weight:700;line-height:1.2;">
          {COMPANY_NAME}
        </div>
        <div style="color:#c8cdd4;font-size:1rem;margin-top:0.2rem;">
          ESA Report Generator
        </div>
        <div style="color:#9aa3ad;font-size:0.85rem;margin-top:0.35rem;">
          Alberta Phase I/II ESA &amp; groundwater ·
          <a href="{SITE_URL}" style="color:#e8b8d9;text-decoration:none;">ecoventure.ca</a>
        </div>
      </div>
    </div>
    <div style="flex:2;min-width:200px;">{lake_html}</div>
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
