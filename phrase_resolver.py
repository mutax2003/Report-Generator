"""
Resolve multiple-choice standard phrases from JSON catalog, Excel PhraseCatalog sheet,
and Streamlit UI selections into merge context keys.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

PHRASE_CATALOG_SHEET = "PhraseCatalog"
SELECTED_SUFFIX = "_selected"
_CATALOG_JSON = Path(__file__).resolve().parent / "schemas" / "phrase_catalog.json"
_cached_json: dict[str, Any] | None = None
_cached_definitions: dict[str, dict[str, Any]] | None = None


def _norm_key(name: str) -> str:
    s = str(name).strip()
    s = re.sub(r"\s+", "_", s)
    return s.lower()


def load_phrase_catalog_json() -> dict[str, Any]:
    """Return parsed phrase_catalog.json (phrases dict)."""
    global _cached_json
    if _cached_json is None:
        with _CATALOG_JSON.open(encoding="utf-8") as f:
            _cached_json = json.load(f)
    return _cached_json


def list_phrase_definitions() -> dict[str, dict[str, Any]]:
    """phrase_key -> {label, options: [{id, label, text}, ...]}."""
    global _cached_definitions
    if _cached_definitions is None:
        data = load_phrase_catalog_json()
        raw = data.get("phrases", {})
        _cached_definitions = {str(k): dict(v) for k, v in raw.items()}
    return _cached_definitions


@lru_cache(maxsize=16)
def _read_phrase_catalog_sheet_cached(
    excel_digest: str, excel_bytes: bytes
) -> tuple[tuple[str, str, str], ...]:
    """Immutable cache key for PhraseCatalog sheet rows."""
    if not excel_bytes or len(excel_bytes) < 100:
        return ()
    bio = io.BytesIO(excel_bytes)
    try:
        xl = pd.ExcelFile(bio, engine="openpyxl")
    except Exception:
        return ()
    with xl:
        if PHRASE_CATALOG_SHEET not in xl.sheet_names:
            return ()
        df = xl.parse(PHRASE_CATALOG_SHEET, header=0)
    if df.empty or len(df.columns) < 3:
        return ()
    rows: list[tuple[str, str, str]] = []
    for row in df.itertuples(index=False, name=None):
        key = _norm_key(row[0])
        opt = str(row[1]).strip() if row[1] is not None else ""
        text = str(row[2]).strip() if row[2] is not None else ""
        if key and opt and text:
            rows.append((key, opt, text))
    return tuple(rows)


def read_phrase_catalog_sheet(excel_bytes: bytes) -> dict[tuple[str, str], str]:
    """
    Load PhraseCatalog sheet: columns phrase_key, option_id, text.
    Returns {(phrase_key, option_id): text}.
    """
    digest = hashlib.sha256(excel_bytes).hexdigest() if excel_bytes else ""
    rows = _read_phrase_catalog_sheet_cached(digest, excel_bytes)
    return {(k, o): t for k, o, t in rows}


def extract_selection_ids_from_project(project: dict[str, Any]) -> dict[str, str]:
    """
    ProjectData columns named ``{phrase_key}_selected`` hold option_id values.
    """
    out: dict[str, str] = {}
    for col, val in project.items():
        nk = _norm_key(str(col))
        if not nk.endswith(SELECTED_SUFFIX):
            continue
        phrase_key = nk[: -len(SELECTED_SUFFIX)]
        if not phrase_key:
            continue
        opt = str(val).strip() if val is not None else ""
        if opt:
            out[phrase_key] = opt
    return out


def resolve_phrase_text(
    phrase_key: str,
    option_id: str,
    *,
    excel_lookup: dict[tuple[str, str], str] | None = None,
) -> str | None:
    """Resolve option_id to full text using Excel catalog then JSON catalog."""
    pk = _norm_key(phrase_key)
    oid = str(option_id).strip()
    if not pk or not oid:
        return None
    if excel_lookup and (pk, oid) in excel_lookup:
        return excel_lookup[(pk, oid)]
    defs = list_phrase_definitions()
    spec = defs.get(pk)
    if not spec:
        return None
    for opt in spec.get("options", []):
        if str(opt.get("id", "")).strip() == oid:
            return str(opt.get("text", "")).strip() or None
    return None


def apply_phrase_resolution(
    context: dict[str, Any],
    project: dict[str, Any],
    excel_bytes: bytes,
    meta: dict[str, str] | None = None,
    *,
    excel_lookup: dict[tuple[str, str], str] | None = None,
) -> list[str]:
    """
    Set context[phrase_key] from Excel selections and UI meta (meta wins for phrase keys).
    Returns warnings for unknown option ids.
    """
    warnings: list[str] = []
    if excel_lookup is None:
        excel_lookup = read_phrase_catalog_sheet(excel_bytes)
    selections = extract_selection_ids_from_project(project)
    defs = list_phrase_definitions()
    phrase_keys = set(defs) | {k for k, _ in excel_lookup}

    for phrase_key, option_id in selections.items():
        text = resolve_phrase_text(
            phrase_key, option_id, excel_lookup=excel_lookup
        )
        if text:
            context[phrase_key] = text
            context[f"{phrase_key}_option_id"] = option_id
        else:
            warnings.append(
                f"Phrase '{phrase_key}': unknown option_id '{option_id}' "
                f"(check PhraseCatalog sheet or schemas/phrase_catalog.json)."
            )

    meta = meta or {}
    for phrase_key in defs:
        if phrase_key in meta and str(meta[phrase_key]).strip():
            context[phrase_key] = str(meta[phrase_key]).strip()
            opt_meta = meta.get(f"{phrase_key}_option_id") or meta.get(
                f"{phrase_key}{SELECTED_SUFFIX}"
            )
            if opt_meta:
                context[f"{phrase_key}_option_id"] = str(opt_meta).strip()

    return warnings


def build_phrase_catalog_workbook_bytes() -> bytes:
    """Sample PhraseCatalog sheet from JSON definitions."""
    import io

    from openpyxl import Workbook

    defs = list_phrase_definitions()
    wb = Workbook()
    ws = wb.active
    ws.title = PHRASE_CATALOG_SHEET
    ws.append(["phrase_key", "option_id", "text"])
    for phrase_key, spec in sorted(defs.items()):
        for opt in spec.get("options", []):
            ws.append(
                [
                    phrase_key,
                    str(opt.get("id", "")),
                    str(opt.get("text", "")),
                ]
            )
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()
