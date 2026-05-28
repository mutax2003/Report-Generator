"""Build or update Excel workbooks from AI extraction results."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd

from ai.models import LabExtractRow
from engine import GROUNDWATER_LAB_SHEET, LAB_SHEET, MONITORING_WELLS_SHEET, PROJECT_SHEET


def lab_rows_to_xlsx_bytes(
    rows: list[LabExtractRow],
    *,
    project_row: dict[str, Any] | None = None,
    existing_excel: bytes | None = None,
) -> bytes:
    lab_df = pd.DataFrame([r.to_excel_dict() for r in rows])

    if existing_excel:
        bio = io.BytesIO(existing_excel)
        with pd.ExcelFile(bio, engine="openpyxl") as xl:
            sheets = {name: xl.parse(name) for name in xl.sheet_names}
        if PROJECT_SHEET not in sheets:
            sheets[PROJECT_SHEET] = pd.DataFrame([project_row or {}])
        elif project_row:
            sheets[PROJECT_SHEET] = pd.DataFrame([project_row])
        sheets[LAB_SHEET] = lab_df
    else:
        sheets = {
            PROJECT_SHEET: pd.DataFrame([project_row or {}]),
            LAB_SHEET: lab_df,
        }

    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        for name, df in sheets.items():
            df.to_excel(w, sheet_name=name, index=False)
    return out.getvalue()


def lab_rows_to_groundwater_xlsx_bytes(
    rows: list[LabExtractRow],
    *,
    project_row: dict[str, Any] | None = None,
    existing_excel: bytes | None = None,
    well_rows: list[dict[str, str]] | None = None,
) -> bytes:
    """Merge lab rows into GroundwaterLab sheet (and optional MonitoringWells)."""
    lab_df = pd.DataFrame([r.to_excel_dict() for r in rows])
    if existing_excel:
        bio = io.BytesIO(existing_excel)
        with pd.ExcelFile(bio, engine="openpyxl") as xl:
            sheets = {name: xl.parse(name) for name in xl.sheet_names}
        if PROJECT_SHEET not in sheets:
            sheets[PROJECT_SHEET] = pd.DataFrame([project_row or {}])
        elif project_row:
            sheets[PROJECT_SHEET] = pd.DataFrame([project_row])
        sheets[GROUNDWATER_LAB_SHEET] = lab_df
        if well_rows:
            sheets[MONITORING_WELLS_SHEET] = pd.DataFrame(well_rows)
    else:
        sheets = {
            PROJECT_SHEET: pd.DataFrame([project_row or {}]),
            GROUNDWATER_LAB_SHEET: lab_df,
        }
        if well_rows:
            sheets[MONITORING_WELLS_SHEET] = pd.DataFrame(well_rows)

    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        for name, df in sheets.items():
            df.to_excel(w, sheet_name=name, index=False)
    return out.getvalue()
