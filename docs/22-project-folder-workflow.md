# 22 — Project folder workflow (local CLI + AI)

Consultants can organize one site per **project folder** on disk, run AI enrichment into `ai_drafts/`, then render to `delivered/` using the same deterministic engine as Streamlit.

## Folder layout

```
C:\Projects\260109R\
  project_data.xlsx           # Required — ProjectData + optional sheets
  template.docx               # Required — Jinja Word template (or template.pdf)
  ecoventure_workbook.xlsx    # Optional — Ecoventure Phase I + DWDA calcs (Save As from xltm)
  project.json                # Optional — profile + sidebar meta (see schemas/project_folder.json)
  source\                # Raw PDFs (lab COA, ABADATA, legacy report)
  figures\               # PNG/JPG for manual Word paste or path columns
  appendices\            # Manual PDFs B/C/E/F/H (A/D/G auto-generated at render)
  rag\                   # Optional project-local RAG snippets (*.txt)
  ai_drafts\             # AI outputs — review before editing Excel
  delivered\             # Render output (.docx, manifest, package zip)
```

Run `python scripts\prepare_user_test_pack.py` then copy `user_test\` to a project folder, or:

```powershell
python scripts\ingest_project_folder.py --init-sample --folder C:\Projects\demo_site
```

## project.json (optional)

| Field | Example |
|-------|---------|
| `report_type` | `phase1_alberta` |
| `report_phase` | `Phase 1` |
| `prepared_by` | Ecoventure QP name |
| `date_of_issue` | `2026-06-10` |
| `template_version` | `2.1` |
| `excel_filename` | Override default Excel name |
| `template_filename` | Override default template name |
| `ecoventure_workbook_filename` | Override default `ecoventure_workbook.xlsx` |

Schema: [`schemas/project_folder.json`](../schemas/project_folder.json)

**AI drafts:** `--ai enrich` writes advisory text to `ai_drafts/` only. Render uses `project_data.xlsx` + sidebar meta. In Streamlit, open the **AI drafts & tools** tab → **Folder AI drafts** and use **Apply to Excel** (or executive summary override) after review — nothing is auto-merged into `ReportEngine`.

## CLI commands

```powershell
.\.venv\Scripts\Activate.ps1

# Scan + preflight + copilot advice (no LLM required)
python scripts\ingest_project_folder.py --folder C:\Projects\260109R --ai inventory

# Source PDF text + summaries (no LLM required for extract-only)
python scripts\ingest_project_folder.py --folder C:\Projects\260109R --ai source-ingest --no-llm

# Full AI enrich: inventory + source PDF ingest + narratives + appendix classification
python scripts\ingest_project_folder.py --folder C:\Projects\260109R --ai enrich

# Narrative drafts only (uses rag/ if present)
python scripts\ingest_project_folder.py --folder C:\Projects\260109R --ai narratives

# Lab COA PDF → ai_drafts/lab_extract_*.json (optional Excel backup in ai_drafts/)
python scripts\ingest_project_folder.py --folder C:\Projects\260109R --ai lab-pdf --lab-pdf source\lab_coa.pdf

# Render + deliverable package
python scripts\ingest_project_folder.py --folder C:\Projects\260109R --render --package
```

Review files under `ai_drafts\` before changing `project_data.xlsx`. AI does **not** write Excel automatically unless you use `--write-lab-excel` with `--ai lab-pdf`, or click **Apply** / **Merge into current workbook** in the Streamlit **AI drafts & tools** tab (folder workflow; upload workflow uses **AI tools**).

## Streamlit (local desktop)

Choose **Project folder + AI** at startup, click **Browse…** to pick a folder (or paste a path), then **Load folder**. Use **Analyze folder** to run source PDF ingest + AI drafts into `ai_drafts/` — the app loads the folder into the Report tab automatically after analyze.

**Browse…** requires a local Windows desktop with a display. On Docker/Linux servers or headless hosts, paste the full folder path instead — the picker is unavailable there.

Requires local/desktop Streamlit (not multi-tenant hosted).

## AI outputs in ai_drafts/

| File | Source |
|------|--------|
| `inventory.md` | Folder scan |
| `preflight_report.md` | `template_tools.run_preflight` |
| `missing_excel_columns.txt` | Profile-aware checklist |
| `copilot_advice.md` | Rule-based pre-flight copilot |
| `source_index.json` | `ai/source_ingest.py` — PDF index |
| `source_extracts/*.txt` | Raw text from `source/` PDFs |
| `source_summaries.json` | LLM or offline summaries per PDF |
| `excel_field_suggestions.json` | Suggested ProjectData fields — Apply from **AI drafts & tools** |
| `narratives.json` | `ai/narrative.py` + `rag/` + source summaries — Apply from **AI drafts & tools** |
| `apecs_candidates.json` | Combined APEC rows from source PDFs — Apply from **AI drafts & tools** |
| `apec_extract_*.json` | Per-PDF APEC extract |
| `appendix_manifest.json` | Preferred labels when loading `appendices/` (vs filename heuristics) |
| `lab_extract_*.json` | `ai/lab_extract.py` or source-ingest lab route |

## Safety

- Deterministic merge unchanged — AI populates drafts only.
- Manifest records optional `project_folder` path for audit.
- Offline mode works without `OPENAI_API_KEY` (heuristics + rule narratives).

## Related docs

- [23-excel-calculation-workbook-integration.md](23-excel-calculation-workbook-integration.md) — optional `ecoventure_workbook.xlsx` hybrid ingest
- [00-start-here.md](00-start-here.md) — consultant Streamlit path
- [09-ai-assistant.md](09-ai-assistant.md) — AI tab features
- [15-power-automate-guide.md](15-power-automate-guide.md) — SharePoint (future same layout)
