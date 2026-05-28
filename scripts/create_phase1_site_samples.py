"""Create per-site Phase 1 Excel workbooks for new PDF template samples."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import ECOVENTURE_CONSULTANT, generate_phase1_alberta_excel  # noqa: E402
from phase1_markup import excel_row_from_meta  # noqa: E402
from phase1_pdf_text import extract_pdf_text_local, parse_phase1_pdf_meta  # noqa: E402

SITES = [
    {
        "pdf": ROOT
        / "samples"
        / "251106R - 15-20-049-10 W5M - Phase 1 ESA_Final_Secure.pdf",
        "xlsx": ROOT / "samples" / "phase1_251106R_data.xlsx",
        "overrides": {
            "well_name": "15-20-049-10 W5M Cynthia Waste Management Facility (WM 153)",
            "site_name": "15-20-049-10 W5M Cynthia Waste Management Facility (WM 153)",
            "uwi": "15-20-049-10 W5M",
            "project_number": "251106R",
            "report_month_year": "November 6, 2025",
            "client_name": "Base Element Energy Inc.",
        },
    },
    {
        "pdf": ROOT
        / "samples"
        / "260109R - 16-34-055-02W4M Phase 1 ESA_Final_Secure.pdf",
        "xlsx": ROOT / "samples" / "phase1_260109R_data.xlsx",
        "overrides": {
            "well_name": "CALTEX TRILOGY LIND 7-34-55-2",
            "site_name": "100/07-34-055-02 W4M",
            "uwi": "100/07-34-055-02 W4M",
            "project_number": "260109R",
            "report_month_year": "January 9, 2026",
            "client_name": "Caltex Trilogy Inc.",
        },
    },
    {
        "pdf": ROOT
        / "samples"
        / "00_04-04-049-04W4M Phase I report - Devon 2017.pdf",
        "xlsx": ROOT / "samples" / "phase1_devon_data.xlsx",
        "skip_pdf": True,
        "overrides": {
            "client_name": "Example Energy Ltd.",
            "well_name": "Example 4D Windy 4-4-49-4",
            "site_name": "Example 4D Windy 4-4-49-4",
            "uwi": "00/04-04-049-04W4/0",
            "project_number": "ESA-P1-2017-001",
            "report_month_year": "March 2017",
            "report_title": "Phase I Environmental Site Assessment",
            "client_short": "Example Energy",
        },
    },
]


def _patch_xlsx(path: Path, overrides: dict[str, str]) -> None:
    import pandas as pd
    from engine import PROJECT_SHEET

    xl = pd.ExcelFile(path)
    sheets = {name: pd.read_excel(xl, sheet_name=name) for name in xl.sheet_names}
    project = sheets[PROJECT_SHEET]
    if project.empty:
        raise ValueError(f"No rows in {PROJECT_SHEET}")
    for key, val in overrides.items():
        if key in project.columns:
            project.at[0, key] = val
        else:
            project[key] = ""
            project.at[0, key] = val
    project.at[0, "consultant_name"] = ECOVENTURE_CONSULTANT
    project.at[0, "company"] = ECOVENTURE_CONSULTANT
    from phase1_narrative import build_phase1_executive_summary

    row = {str(c): project.at[0, c] for c in project.columns}
    row["executive_summary"] = build_phase1_executive_summary(row)
    for k, v in row.items():
        project.at[0, k] = v
    sheets[PROJECT_SHEET] = project
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        for name, df in sheets.items():
            df.to_excel(w, sheet_name=name, index=False)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Create per-site Phase 1 Excel samples.")
    parser.add_argument(
        "--ai-narratives",
        action="store_true",
        help="Draft conclusions via offline AI narrative helper (review before use)",
    )
    args = parser.parse_args()

    samples = ROOT / "samples"
    samples.mkdir(parents=True, exist_ok=True)
    baseline = samples / "phase1_alberta_data.xlsx"
    generate_phase1_alberta_excel(str(baseline))

    for spec in SITES:
        pdf_path: Path = spec["pdf"]
        xlsx_path: Path = spec["xlsx"]
        overrides = copy.deepcopy(spec["overrides"])

        if pdf_path.is_file() and not spec.get("skip_pdf"):
            try:
                text = extract_pdf_text_local(pdf_path.read_bytes())
                meta = parse_phase1_pdf_meta(pdf_path, text)
                ai_row = excel_row_from_meta(
                    meta, draft_narratives=args.ai_narratives
                )
                overrides.update({k: v for k, v in ai_row.items() if v})
            except RuntimeError as e:
                print(f"WARN: {pdf_path.name}: {e} — using defaults")

        import shutil

        try:
            shutil.copy2(baseline, xlsx_path)
        except PermissionError:
            print(
                f"WARN: Could not write {xlsx_path.name} (file open in Excel?). "
                "Close the workbook and re-run.",
                file=sys.stderr,
            )
            continue
        _patch_xlsx(xlsx_path, overrides)
        print(f"Wrote: {xlsx_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
