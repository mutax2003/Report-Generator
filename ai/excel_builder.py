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


def well_rows_to_xlsx_bytes(
    well_rows: list[dict[str, str]],
    *,
    project_row: dict[str, Any] | None = None,
    existing_excel: bytes | None = None,
) -> bytes:
    """Merge MonitoringWells rows into a workbook (replace sheet)."""
    wells_df = pd.DataFrame(well_rows)
    if existing_excel:
        bio = io.BytesIO(existing_excel)
        with pd.ExcelFile(bio, engine="openpyxl") as xl:
            sheets = {name: xl.parse(name) for name in xl.sheet_names}
        if PROJECT_SHEET not in sheets:
            sheets[PROJECT_SHEET] = pd.DataFrame([project_row or {}])
        elif project_row:
            sheets[PROJECT_SHEET] = pd.DataFrame([project_row])
        sheets[MONITORING_WELLS_SHEET] = wells_df
    else:
        sheets = {
            PROJECT_SHEET: pd.DataFrame([project_row or {}]),
            MONITORING_WELLS_SHEET: wells_df,
        }

    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        for name, df in sheets.items():
            df.to_excel(w, sheet_name=name, index=False)
    return out.getvalue()


def apec_rows_to_xlsx_bytes(
    rows: list[dict[str, str]],
    *,
    project_row: dict[str, Any] | None = None,
    existing_excel: bytes | None = None,
    mode: str = "replace",
) -> bytes:
    """Write Apecs sheet. mode=replace replaces sheet; mode=append concatenates rows."""
    from engine import APECS_SHEET

    new_df = pd.DataFrame(rows)
    if existing_excel:
        bio = io.BytesIO(existing_excel)
        with pd.ExcelFile(bio, engine="openpyxl") as xl:
            sheets = {name: xl.parse(name) for name in xl.sheet_names}
        if PROJECT_SHEET not in sheets:
            sheets[PROJECT_SHEET] = pd.DataFrame([project_row or {}])
        elif project_row:
            sheets[PROJECT_SHEET] = pd.DataFrame([project_row])
        if mode == "append" and APECS_SHEET in sheets and not sheets[APECS_SHEET].empty:
            combined = pd.concat([sheets[APECS_SHEET], new_df], ignore_index=True)
            if "apec_id" in combined.columns:
                combined["apec_id"] = [f"APEC-{i}" for i in range(1, len(combined) + 1)]
            sheets[APECS_SHEET] = combined
        else:
            sheets[APECS_SHEET] = new_df
    else:
        sheets = {
            PROJECT_SHEET: pd.DataFrame([project_row or {}]),
            APECS_SHEET: new_df,
        }

    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        for name, df in sheets.items():
            df.to_excel(w, sheet_name=name, index=False)
    return out.getvalue()
