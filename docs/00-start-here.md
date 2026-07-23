# Start here — consultants

One-page path for **Ecoventure** staff generating Alberta Phase I or Phase II ESA reports. No Python knowledge required.

## 1. Open the app

**Desktop (local):**

```powershell
cd "Report Generator"
.\run.ps1 streamlit
```

Or manually:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

Browser: http://localhost:8501

**Streamlit Community Cloud (pilot):** Open the shared `*.streamlit.app` URL. Use **Excel + Word template** only — **sample / synthetic data only** (no client-confidential uploads). Project-folder workflow is unavailable on Cloud. See [14-deployment.md](14-deployment.md).

## 2. Choose your workflow

On first open (desktop), pick one path:

| Choice | When to use |
|--------|-------------|
| **Project folder + AI** | Local desktop only — site folder (`project_data.xlsx`, `template.docx`, `source/`, `appendices/`, …). Optional AI drafts go to `ai_drafts/`. |
| **Excel + Word template** | Upload `.xlsx` + `.docx`/`.pdf` — **recommended for first report** and **required on Cloud**. |

Use **Change** in the blue banner to switch workflows later (desktop). A **Welcome** card appears on first use — click **Got it** when you are ready.

**Menus:** Use the **File / Edit / View / Tools / Help** bar under the header. On desktop, press **F1** for HTML help. On Cloud, **F1** does not open local help — use the Report tab **Help & documentation** expander (or this guide on SharePoint).

**First time?** In the sidebar, open **Sample templates** and click **Load Alberta Phase I sample into session**, then open the **Report** tab.

### Excel + template path

| Upload | File |
|--------|------|
| **Excel Data Source** | Your `.xlsx` with sheet **`ProjectData`** (row 1 = headers, **row 2+** = one site per row) |
| **Report template** | Your `.docx` (preferred) or `.pdf` layout |

### Project folder path

Enter the folder path (e.g. `C:\Projects\260109R`), click **Browse…** to pick a folder (loads immediately), or paste the path and click **Load folder**. Optional: **Analyze folder** for AI drafts. See [22-project-folder-workflow.md](22-project-folder-workflow.md).

Optional (both paths): **Standard phrases** — preset paragraphs for tagged fields (see [04-template-authoring.md](04-template-authoring.md)).

## 3. Sidebar settings

| Setting | Phase I typical value |
|---------|------------------------|
| **Simple mode** | On (recommended) — hides advanced options |
| **Report phase** | Phase 1 |
| **Profile** | Alberta Phase I ESA (Ecoventure) |
| **Prepared by** | Your name |
| **Date of issue** | Today |
| **Template version** | e.g. `2.1` (optional; auto-filled from filename if it contains `v2.1`) |

Optional (turn off Simple mode): **Override executive summary** — replaces Excel / auto-generated text.

**Advanced — AI options** (sidebar): optional LLM for narratives, lab PDF parse, and folder analysis. Default is **offline** (no API key). For **free local** use, set `AI_PROVIDER=ollama` in `.streamlit/secrets.toml`; for **free cloud**, try `gemini` or `groq` — see [09-ai-assistant.md](09-ai-assistant.md). Keep cloud LLM off for strictly confidential site files.

The sidebar **Getting started** checklist tracks your progress through load → pre-flight → generate → download.

## 4. Pre-flight

The **Report** tab shows **Your next steps** at the top — fix red items first. Expand **Regulatory checklist (SED 002)** or **Drilling waste compliance (DWDA)** for details.

Fix any **red errors** before generating. Yellow warnings are OK for a draft.

Use **Download missing-fields checklist** or **Download ReportConfig sheet** if you are building a new Excel file.

See **Glossary** under pre-flight or **Advanced** for OneStop, SED 002, and DWDA definitions.

## 5. Generate and download

1. On the Report tab, **Generate report** sits above the **Appendices** expander. Optional: upload B/C/E/F/H PDFs there before you click Generate (or upload after and Generate again).
2. Choose **Single site** (pick a `ProjectData` row) or **All N sites (batch zip)** if Excel has multiple sites on `ProjectData`
3. **Generate report**
4. **Download deliverable package (.zip)** — **primary output** (report + manifest + appendices + OneStop export + QP checklists)
5. Follow the **Before OneStop upload** checklist on screen (review warnings, export generated D/G to PDF, confirm appendices)
6. **Advanced downloads** expander — individual `.docx`, manifest JSON, generated appendices

For batch runs, use **Download all deliverable packages** as the primary button.

Export to client PDF in Word if needed; the app does not merge appendices into one PDF automatically.

## 6. More help

| Topic | Doc |
|-------|-----|
| Full Streamlit workflow | [02-user-guide.md](02-user-guide.md) |
| Alberta Phase I fields | [11-alberta-phase1-esa.md](11-alberta-phase1-esa.md) |
| DWDA / Directive 050 | [21-dwda-directive-050-compliance.md](21-dwda-directive-050-compliance.md) |
| Excel columns | [03-excel-data-guide.md](03-excel-data-guide.md) |
| Word tags | [04-template-authoring.md](04-template-authoring.md) |
| FAQ | [10-glossary-faq.md](10-glossary-faq.md) |

**Developers / IT:** [README.md](../README.md) · [AGENTS.md](../AGENTS.md)
