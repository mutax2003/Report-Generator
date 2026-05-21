"""
Create user_test/ working copies of Alberta Phase I samples for editing.

Copies phase1_alberta_data.xlsx -> user_test/my_project_data.xlsx
Copies phase1_alberta_template.docx -> user_test/my_template.docx
Writes user_test/README.txt with next steps.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._deps import require_project_deps  # noqa: E402

require_project_deps(ROOT)

import pandas as pd

from engine import generate_phase1_alberta_excel, generate_phase1_alberta_template_docx  # noqa: E402

SAMPLES = ROOT / "samples"
USER_TEST = ROOT / "user_test"
MY_XLSX = USER_TEST / "my_project_data.xlsx"
MY_DOCX = USER_TEST / "my_template.docx"

README = """\
ESA Report Generator — your test folder
========================================

Files in this folder are COPIES of the Alberta Phase I Ecoventure samples.
Edit them, then test without changing files under samples/.

  my_project_data.xlsx  — Edit row 2 on ProjectData; optional DrillingWaste rows
  my_template.docx      — Edit layout/tags; keep {{ tag }} names matching Excel headers

Setup (once per machine):
  .\\.venv\\Scripts\\Activate.ps1
  pip install -r requirements.txt

Quick test (CLI):
  python scripts\\test_with_your_documents.py --excel user_test\\my_project_data.xlsx --template user_test\\my_template.docx

Quick test (browser):
  streamlit run app.py
  Upload my_project_data.xlsx + my_template.docx

List Word tags:
  python scripts\\inventory_template.py user_test\\my_template.docx

Full guide: docs\\12-testing-with-your-documents.md
"""


def main() -> int:
    USER_TEST.mkdir(parents=True, exist_ok=True)

    src_xlsx = SAMPLES / "phase1_alberta_data.xlsx"
    src_docx = SAMPLES / "phase1_alberta_template.docx"
    if not src_xlsx.is_file():
        generate_phase1_alberta_excel(str(src_xlsx))
    if not src_docx.is_file():
        generate_phase1_alberta_template_docx(str(src_docx))

    shutil.copy2(src_xlsx, MY_XLSX)
    shutil.copy2(src_docx, MY_DOCX)

    # Customize ProjectData row 2 so user_test/ is clearly "your" copy (not samples/).
    with pd.ExcelFile(MY_XLSX) as book:
        sheets = {name: pd.read_excel(book, sheet_name=name) for name in book.sheet_names}
    if "ProjectData" in sheets and not sheets["ProjectData"].empty:
        if "client_name" in sheets["ProjectData"].columns:
            sheets["ProjectData"].iloc[0, sheets["ProjectData"].columns.get_loc("client_name")] = (
                "My Test Client Ltd."
            )
        with pd.ExcelWriter(MY_XLSX, engine="openpyxl") as writer:
            for name, frame in sheets.items():
                frame.to_excel(writer, sheet_name=name, index=False)
    (USER_TEST / "README.txt").write_text(README, encoding="utf-8")

    print(f"Wrote: {MY_XLSX}")
    print(f"Wrote: {MY_DOCX}")
    print(f"Wrote: {USER_TEST / 'README.txt'}")
    print("\nNext: edit row 2 in Excel, then run:")
    print("  python scripts\\test_with_your_documents.py --excel user_test\\my_project_data.xlsx --template user_test\\my_template.docx")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
