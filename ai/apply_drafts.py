"""Apply AI drafts into ProjectData Excel with explicit user confirmation.

Never called from ReportEngine — UI/CLI must invoke after review.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from engine import PROJECT_SHEET, _norm_key

# Narrative draft section → ProjectData field key
NARRATIVE_SECTION_TO_FIELD: dict[str, str] = {
    "executive_summary": "executive_summary",
    "site_description": "site_description",
    "conclusions_limitations": "conclusions_recommendations",
    "conclusions_recommendations": "conclusions_recommendations",
}


def load_narratives_payload(path_or_data: Path | dict[str, Any] | str) -> dict[str, str]:
    """Map narrative section → text from narratives.json or in-memory payload."""
    if isinstance(path_or_data, Path):
        data = json.loads(path_or_data.read_text(encoding="utf-8"))
    elif isinstance(path_or_data, str):
        data = json.loads(path_or_data)
    else:
        data = path_or_data
    out: dict[str, str] = {}
    for item in data.get("sections") or []:
        if not isinstance(item, dict):
            continue
        section = str(item.get("section", "")).strip()
        text = str(item.get("text", "")).strip()
        field = NARRATIVE_SECTION_TO_FIELD.get(section, section)
        if field and text:
            out[field] = text
    return out


def load_field_suggestions(path_or_data: Path | dict[str, Any] | str) -> dict[str, str]:
    """Load excel_field_suggestions.json ``fields`` map."""
    if isinstance(path_or_data, Path):
        data = json.loads(path_or_data.read_text(encoding="utf-8"))
    elif isinstance(path_or_data, str):
        data = json.loads(path_or_data)
    else:
        data = path_or_data
    fields = data.get("fields") or {}
    if not isinstance(fields, dict):
        return {}
    return {
        str(k).strip(): str(v).strip()
        for k, v in fields.items()
        if str(k).strip() and str(v).strip()
    }


def narratives_from_session_drafts(drafts: list[Any]) -> dict[str, str]:
    """Convert NarrativeDraft objects (or dicts) to field → text."""
    out: dict[str, str] = {}
    for d in drafts or []:
        if isinstance(d, dict):
            section = str(d.get("section", "")).strip()
            text = str(d.get("text", "")).strip()
        else:
            section = str(getattr(d, "section", "")).strip()
            text = str(getattr(d, "text", "")).strip()
        field = NARRATIVE_SECTION_TO_FIELD.get(section, section)
        if field and text:
            out[field] = text
    return out


def preview_project_data_patch(
    excel_bytes: bytes,
    fields: dict[str, str],
    *,
    overwrite_filled: bool = False,
    row_index: int = 0,
) -> tuple[list[str], list[str], list[str]]:
    """Return (will_apply, will_skip_filled, will_add_columns) without writing."""
    if not fields:
        return [], [], []
    bio = io.BytesIO(excel_bytes)
    with pd.ExcelFile(bio, engine="openpyxl") as xl:
        if PROJECT_SHEET not in xl.sheet_names:
            return [], [], list(fields.keys())
        df = xl.parse(PROJECT_SHEET)
    if df.empty:
        df = pd.DataFrame([{}])
    if row_index < 0 or row_index >= max(len(df), 1):
        row_index = 0

    col_by_key = {_norm_key(c): c for c in df.columns}
    will_apply: list[str] = []
    will_skip: list[str] = []
    will_add: list[str] = []
    for key, value in fields.items():
        nk = _norm_key(key)
        if not nk or not str(value).strip():
            continue
        if nk not in col_by_key:
            will_add.append(nk)
            will_apply.append(nk)
            continue
        col = col_by_key[nk]
        if len(df) == 0:
            will_apply.append(nk)
            continue
        existing = df.iloc[row_index][col] if row_index < len(df) else ""
        if pd.isna(existing) or str(existing).strip() == "":
            will_apply.append(nk)
        elif overwrite_filled:
            will_apply.append(nk)
        else:
            will_skip.append(nk)
    return will_apply, will_skip, will_add


def patch_project_data_fields(
    excel_bytes: bytes,
    fields: dict[str, str],
    *,
    overwrite_filled: bool = False,
    row_index: int = 0,
) -> tuple[bytes, list[str], list[str]]:
    """Patch ProjectData row with field values.

    Returns (new_excel_bytes, applied_keys, skipped_keys).
    """
    if not fields:
        return excel_bytes, [], []

    bio = io.BytesIO(excel_bytes)
    with pd.ExcelFile(bio, engine="openpyxl") as xl:
        sheets = {name: xl.parse(name) for name in xl.sheet_names}

    if PROJECT_SHEET not in sheets:
        sheets[PROJECT_SHEET] = pd.DataFrame([{}])
    df = sheets[PROJECT_SHEET]
    if df.empty:
        df = pd.DataFrame([{}])
        sheets[PROJECT_SHEET] = df

    while len(df) <= row_index:
        df.loc[len(df)] = {c: "" for c in df.columns}

    col_by_key = {_norm_key(c): c for c in df.columns}
    applied: list[str] = []
    skipped: list[str] = []

    for key, value in fields.items():
        nk = _norm_key(key)
        val = str(value).strip()
        if not nk or not val:
            continue
        if nk not in col_by_key:
            df[nk] = ""
            col_by_key[nk] = nk
        col = col_by_key[nk]
        existing = df.at[row_index, col]
        filled = not (pd.isna(existing) or str(existing).strip() == "")
        if filled and not overwrite_filled:
            skipped.append(nk)
            continue
        if df[col].dtype != object:
            df[col] = df[col].astype(object)
        df.at[row_index, col] = val
        applied.append(nk)

    sheets[PROJECT_SHEET] = df
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        for name, sdf in sheets.items():
            sdf.to_excel(w, sheet_name=name, index=False)
    return out.getvalue(), applied, skipped


def load_appendix_manifest_labels(drafts_dir: Path) -> dict[str, str]:
    """filename → label from ai_drafts/appendix_manifest.json."""
    path = drafts_dir / "appendix_manifest.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    items = data.get("items") or []
    out: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        fname = str(item.get("filename", "")).strip()
        label = str(item.get("label", "")).strip().upper()[:1]
        if fname and label and re.fullmatch(r"[A-H]", label):
            out[fname] = label
    return out
