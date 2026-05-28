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
| **Excel Data Source** | Your `.xlsx` with sheet **`ProjectData`** (row 1 = headers, **row 2+** = one site per row) |
| **Report template** | Your `.docx` (preferred) or `.pdf` layout |

Optional: **Standard phrases** on the Report tab — preset paragraphs for tagged fields (see [04-template-authoring.md](04-template-authoring.md)).

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

1. Choose **Single report** (row 2) or **All N reports (batch)** if Excel has multiple sites on `ProjectData`
2. **Generate Report**
3. **Download Report (.docx)** — or batch zip when multiple sites were generated
4. **Download generation manifest (JSON)** — save with the report on SharePoint
5. Upload appendix PDFs **A–F** (air photos, ABADATA, land title, …) if applicable
6. **Download deliverable package (.zip)** — report + manifest + appendices folder

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
