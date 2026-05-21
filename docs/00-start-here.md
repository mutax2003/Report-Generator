# Start here — consultants

One-page path for **Ecoventure** staff generating Alberta Phase I or Phase II ESA reports. No Python knowledge required.

## 1. Open the app

```powershell
cd "Report Generator"
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

Browser: http://localhost:8501

## 2. Upload files

| Upload | File |
|--------|------|
| **Excel Data Source** | Your `.xlsx` with sheet **`ProjectData`** (row 1 = headers, row 2 = values) |
| **Report template** | Your `.docx` (preferred) or `.pdf` layout |

**First time?** Use sidebar **Download Alberta Phase I Excel** and **Download Alberta Phase I template**.

## 3. Sidebar settings

| Setting | Phase I typical value |
|---------|------------------------|
| **Report phase** | Phase 1 |
| **Profile** | Alberta Phase I ESA (Ecoventure) |
| **Prepared by** | Your name |
| **Date of issue** | Today |
| **Template version** | e.g. `2.1` (optional; auto-filled from filename if it contains `v2.1`) |

Optional: **Override executive summary** — replaces Excel / auto-generated text.

## 4. Pre-flight

Fix any **red errors** before generating. Yellow warnings are OK for a draft.

Use **Download missing-fields checklist** or **Download ReportConfig sheet** if you are building a new Excel file.

## 5. Generate and download

1. **Generate Report**
2. **Download Report (.docx)**
3. **Download generation manifest (JSON)** — save with the report on SharePoint
4. Upload appendix PDFs **A–F** (air photos, ABADATA, land title, …) if applicable
5. **Download deliverable package (.zip)** — report + manifest + appendices folder

Export to client PDF in Word if needed; the app does not merge appendices into one PDF automatically.

## 6. More help

| Topic | Doc |
|-------|-----|
| Full Streamlit workflow | [02-user-guide.md](02-user-guide.md) |
| Alberta Phase I fields | [11-alberta-phase1-esa.md](11-alberta-phase1-esa.md) |
| Excel columns | [03-excel-data-guide.md](03-excel-data-guide.md) |
| Word tags | [04-template-authoring.md](04-template-authoring.md) |
| FAQ | [10-glossary-faq.md](10-glossary-faq.md) |

**Developers / IT:** [README.md](../README.md) · [AGENTS.md](../AGENTS.md)
