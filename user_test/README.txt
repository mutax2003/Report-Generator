ESA Report Generator — your test folder
========================================

Files in this folder are COPIES of the Alberta Phase I Ecoventure samples.
Edit them, then test without changing files under samples/.

  my_project_data.xlsx  — Edit row 2 on ProjectData; optional DrillingWaste rows
  my_template.docx      — Edit layout/tags; keep {{ tag }} names matching Excel headers

Phase II test folder (full project layout):
  python scripts\create_phase2_project_folder.py
  -> user_test\phase2_alberta\  (ProjectData + LabResults, template, source/, rag/)

Setup (once per machine):
  .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt

Quick test (CLI):
  python scripts\test_with_your_documents.py --excel user_test\my_project_data.xlsx --template user_test\my_template.docx

Quick test (browser):
  streamlit run app.py
  Upload my_project_data.xlsx + my_template.docx

List Word tags:
  python scripts\inventory_template.py user_test\my_template.docx

Full guide: docs\12-testing-with-your-documents.md
