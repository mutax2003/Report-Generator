"""Alberta environmental imagery from samples/ (project photos)."""

from __future__ import annotations

import base64
import datetime as dt
import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT / "samples"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
HERO_IMAGE = "lake.jpg"


def _load_manifest(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(rows, dict):
            return {k: v for k, v in rows.items() if isinstance(v, dict)}
        return {
            r["file"]: r
            for r in rows
            if isinstance(r, dict) and r.get("file")
        }
    except (json.JSONDecodeError, OSError):
        return {}


def _manifest() -> dict[str, dict[str, str]]:
    return _load_manifest(SAMPLES_DIR / "imagery_manifest.json")


def _image_paths() -> list[Path]:
    if not SAMPLES_DIR.is_dir():
        return []
    manifest = _manifest()
    if manifest:
        paths = []
        for name in sorted(manifest):
            p = SAMPLES_DIR / name
            if p.is_file():
                paths.append(p)
        return paths
    return sorted(
        p
        for p in SAMPLES_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )


def hero_lake_path() -> Path:
    return SAMPLES_DIR / HERO_IMAGE


def ensure_hero_lake_cached() -> None:
    """Cache lake.jpg in session state so reruns after Generate keep the same image."""
    path = hero_lake_path()
    if not path.is_file():
        return
    mtime = path.stat().st_mtime
    if (
        st.session_state.get("hero_lake_mtime") == mtime
        and st.session_state.get("hero_lake_bytes")
    ):
        return
    st.session_state.hero_lake_bytes = path.read_bytes()
    st.session_state.hero_lake_mtime = mtime


def hero_lake_data_uri() -> str:
    ensure_hero_lake_cached()
    raw = st.session_state.get("hero_lake_bytes")
    if not raw:
        return ""
    encoded = base64.b64encode(raw).decode("ascii")
    mime = "image/jpeg" if HERO_IMAGE.lower().endswith(".jpg") else "image/png"
    return f"data:{mime};base64,{encoded}"


def _index_for_today(count: int) -> int:
    if count <= 0:
        return 0
    return dt.date.today().toordinal() % count


def pick_image(*, variant: str = "hero") -> Path | None:
    if variant == "hero":
        path = hero_lake_path()
        return path if path.is_file() else None
    images = _image_paths()
    if not images:
        return None
    offset = {"sidebar": 1, "empty": 2}.get(variant, 0)
    idx = (_index_for_today(len(images)) + offset) % len(images)
    return images[idx]


def render_hero_image() -> None:
    """Fallback widget hero (prefer embedded header in branding.py)."""
    ensure_hero_lake_cached()
    raw = st.session_state.get("hero_lake_bytes")
    if not raw:
        return
    st.image(raw, use_container_width=True)


def render_sidebar_accent() -> None:
    path = pick_image(variant="sidebar")
    if not path:
        return
    with st.sidebar.expander("Alberta landscapes", expanded=False):
        st.image(str(path), use_container_width=True)


def render_empty_state_banner() -> None:
    """Use lake.jpg for welcome banner too (consistent with header)."""
    ensure_hero_lake_cached()
    raw = st.session_state.get("hero_lake_bytes")
    if raw:
        st.image(raw, use_container_width=True)
        return
    path = pick_image(variant="empty")
    if path:
        st.image(str(path), use_container_width=True)


def has_alberta_images() -> bool:
    return hero_lake_path().is_file() or bool(_image_paths())
