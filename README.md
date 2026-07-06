# ESA Report Generator

Web application for generating **Phase 1** and **Phase 2 Environmental Site Assessment (ESA)** reports from an Excel data file and a Word template ([docxtpl](https://docxtpl.readthedocs.io/) / Jinja2).

## Documentation

**Full documentation:** **[docs/README.md](docs/README.md)** — start here.  
**Agents / Cursor:** **[AGENTS.md](AGENTS.md)** — rules, setup, quick commands.

| Guide | Audience |
|-------|----------|
| [docs/11-alberta-phase1-esa.md](docs/11-alberta-phase1-esa.md) | **Alberta O&G Phase I (Ecoventure)** — primary use case |
| [docs/01-overview.md](docs/01-overview.md) | Architecture and data flow |
| [docs/02-user-guide.md](docs/02-user-guide.md) | Streamlit workflow (upload or project folder → pre-flight → generate) |
| [docs/03-excel-data-guide.md](docs/03-excel-data-guide.md) | Excel sheets, columns, exceedances |
| [docs/04-template-authoring.md](docs/04-template-authoring.md) | Word Jinja2 tags and lab tables |
| [docs/05-developer-guide.md](docs/05-developer-guide.md) | Codebase modules and extension |
| [docs/06-api-reference.md](docs/06-api-reference.md) | CLI, HTTP, `ReportEngine`, automation |
| [docs/07-security-and-deployment.md](docs/07-security-and-deployment.md) | Limits, deployment, hardening |
| [docs/08-testing.md](docs/08-testing.md) | Tests and E2E scripts |
| [docs/09-ai-assistant.md](docs/09-ai-assistant.md) | Optional AI tab |
| [docs/10-glossary-faq.md](docs/10-glossary-faq.md) | Terms and FAQ |
| [docs/12-testing-with-your-documents.md](docs/12-testing-with-your-documents.md) | **Test with your Excel + Word templates** |
| [docs/13-flexible-report-profiles.md](docs/13-flexible-report-profiles.md) | Report profiles and `ReportConfig` sheet |
| [docs/14-deployment.md](docs/14-deployment.md) | Docker and production deployment |
| [docs/15-power-automate-guide.md](docs/15-power-automate-guide.md) | M365 / Power Automate integration |
| [docs/16-team-rollout.md](docs/16-team-rollout.md) | **Sharing with coworkers** (~50 users, SharePoint + internal app) |
| [docs/17-server-update-runbook.md](docs/17-server-update-runbook.md) | Server release updates |
| [docs/18-groundwater-reports.md](docs/18-groundwater-reports.md) | Groundwater monitoring (Ecoventure) |
| [docs/19-charts-and-gis-embed.md](docs/19-charts-and-gis-embed.md) | Hydrographs and GIS maps workflow |
| [docs/20-aer-sed002-phase1-esa.md](docs/20-aer-sed002-phase1-esa.md) | AER SED 002 §10 checklist, OneStop export |
| [docs/21-dwda-directive-050-compliance.md](docs/21-dwda-directive-050-compliance.md) | **DWDA / Directive 050** — appendices D/G, calc ingest |
| [docs/22-project-folder-workflow.md](docs/22-project-folder-workflow.md) | **Project folder** — local CLI + AI enrich + render |
| [docs/23-excel-calculation-workbook-integration.md](docs/23-excel-calculation-workbook-integration.md) | Ecoventure Excel calc workbook hybrid ingest |

**Consultants (non-developer):** [docs/00-start-here.md](docs/00-start-here.md)

Quick references: [EXCEL_LAYOUT.txt](EXCEL_LAYOUT.txt) · [JINJA2_CHEATSHEET.txt](JINJA2_CHEATSHEET.txt) · [BEST_PRACTICES.md](BEST_PRACTICES.md) · [CHANGELOG.md](CHANGELOG.md)

## Requirements

- Python 3.10+
- Windows, macOS, or Linux

## Setup

```powershell
cd "c:\Users\Andrew Liu\Report Generator"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the app

```powershell
.\run.ps1 streamlit
```

On first open, choose **Project folder + AI** or **Excel + Word template**.

**Excel + template**

1. Upload **Excel** (`.xlsx`) and **report template** (`.docx` or `.pdf`; PDF is converted to Word for merge).
2. Review **Pre-flight checks**.
3. Fill **sidebar** fields; download samples from the sidebar if needed.
4. Click **Generate Report**, then **Download Report** (optional: appendix PDFs A–H, **Download deliverable package (.zip)**).

**Project folder + AI** (local desktop)

1. **Browse…** or paste a folder path (e.g. `user_test\phase2_alberta` after `python scripts\create_phase2_project_folder.py`).
2. **Load folder** (optional **Analyze folder** for AI drafts in `ai_drafts/`).
3. **Report** tab → pre-flight → Generate.

See [docs/02-user-guide.md](docs/02-user-guide.md) and [docs/22-project-folder-workflow.md](docs/22-project-folder-workflow.md).

## Sample files

```powershell
python scripts\create_samples.py
```

| File | Purpose |
|------|---------|
| `samples/sample_data.xlsx` | Minimal demo data |
| `samples/sample_template.docx` | Tagged demo template with lab table |
| `samples/production_data.xlsx` | Production-aligned fields |
| `samples/production_template.docx` | Tagged production reference |
| `samples/production_starter_template.docx` | Minimal production starter |
| `samples/phase1_alberta_data.xlsx` | Alberta Phase I data (Ecoventure Inc.) |
| `samples/phase1_alberta_template.docx` | Alberta Phase I Word template (Ecoventure) |

**Demo:** `samples/sample_data.xlsx` + `samples/sample_template.docx`  
**Alberta Phase I:** `samples/phase1_alberta_data.xlsx` + `samples/phase1_alberta_template.docx` (Ecoventure Inc.)

### Test with your own files

```powershell
python scripts\prepare_user_test_pack.py
python scripts\test_with_your_documents.py --excel user_test\my_project_data.xlsx --template user_test\my_template.docx
```

See [docs/12-testing-with-your-documents.md](docs/12-testing-with-your-documents.md).

## Scripts

| Command | Purpose |
|---------|---------|
| `python scripts\render_cli.py` | Headless demo render |
| `python scripts\production_e2e.py` | Production preflight + render |
| `python scripts\tag_production_template.py` | Tag merge doc or generate reference template |
| `python scripts\inventory_template.py template.docx` | List Jinja tags |
| `python scripts\prepare_user_test_pack.py` | Copy Alberta samples to `user_test/` for editing |
| `python scripts\test_with_your_documents.py` | Pre-flight + dry run + render (no browser) |
| `python scripts\ingest_project_folder.py --folder <path> --render` | Project folder CLI render to `delivered/` |
| `python scripts\dwda_workflow_e2e.py` | DWDA preflight + appendix H + D/G + OneStop zip |
| `python scripts\ingest_ecoventure_workbook.py` | Merge Ecoventure calc workbook into engine Excel |
| `python scripts\create_phase2_project_folder.py` | Phase II test folder under `user_test/phase2_alberta` |
| `python scripts\health_check.py` | 17-step regression (imports, render, folder ingest, Ecoventure DWDA, test count) |
| `.\scripts\build_windows_deploy.ps1 -BuildExe` | Windows portable folder + `ESA-Report-Generator.exe` |
| `.\run.ps1 scripts\test_with_your_documents.py` | Same, via venv Python (Windows) |
| `.\scripts\package_team_sharepoint.ps1` | Build `dist\team-sharepoint\` for SharePoint upload |
| `python -m unittest discover -s tests -v` | Full test suite (**284 tests**, 3 may skip) |
| `python scripts\streamlit_smoke.py` | Streamlit AppTest smoke (workflow + folder load) |

## Automation

[docs/06-api-reference.md](docs/06-api-reference.md) · [AUTOMATE.md](AUTOMATE.md)

```powershell
python -m automate.http_server --port 8765
```

## AI assistant

[docs/09-ai-assistant.md](docs/09-ai-assistant.md) · [AI_FEATURES.md](AI_FEATURES.md) — optional; works offline without API key.

## Project layout

```
app.py                  Streamlit UI (workflow picker + upload or folder)
render_service.py       Unified headless render (appendix-aware DWDA/SED)
engine.py               ReportEngine (Excel → docxtpl → .docx)
project_folder.py       Local folder resolve, AI enrich, render to delivered/
ecoventure_workbook.py  Ecoventure xltm/xlsx ingest + cell contract merge
dwda_compliance.py      Directive 050 / DWDA checklist enrichment
dwda_calculations.py    Metal/salt/DST calc parity
appendix_generator.py   Auto appendices A/D/G
deliverable_pack.py     Zip deliverable + OneStop + qp_checklists/
report_profile.py       Profile resolution, ReportConfig export
template_attachments.py PDF → DOCX for templates
phase1_narrative.py     Signum-style executive summary (Phase I)
security.py             Upload validation
template_tools.py       Pre-flight and template scan
provenance.py           Generation manifest + compliance snapshot
ui/                     Streamlit (workflow_mode, project_folder, preflight, …)
ai/                     Optional AI helpers
automate/               Headless render API
scripts/                CLI utilities
schemas/                report_profiles.json, field_contract.json, DWDA checklists
samples/                Demo and production fixtures
templates/ecoventure_dwda/  QP xltm/dotm templates (shipped in deliverable zip)
docs/                   Full documentation
tests/                  Unit and integration tests (284 tests)
Dockerfile              Container image for Streamlit
```

See [AGENTS.md](AGENTS.md) for the full module index.

## Sharing with your team

For ~50 Phase I/II authors, use **one internal app** + **SharePoint** for templates (easiest to maintain). See [docs/16-team-rollout.md](docs/16-team-rollout.md).

```powershell
.\scripts\package_team_sharepoint.ps1   # build dist\team-sharepoint\ for upload
```

Checklist: [sharepoint/PUBLISH_CHECKLIST.md](sharepoint/PUBLISH_CHECKLIST.md) · Deploy: [docs/14-deployment.md](docs/14-deployment.md) · Updates: [docs/17-server-update-runbook.md](docs/17-server-update-runbook.md)

## Security

Run on **localhost** for single-user dev. For team hosting, use HTTPS + Entra ID ([docs/14-deployment.md](docs/14-deployment.md)). See [docs/07-security-and-deployment.md](docs/07-security-and-deployment.md) for limits (15 MB Excel, 30 MB template, zip-bomb guards, sandboxed Jinja).

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Missing sheet errors | [docs/03-excel-data-guide.md](docs/03-excel-data-guide.md) |
| Template render failed | [docs/04-template-authoring.md](docs/04-template-authoring.md) — split tags |
| More questions | [docs/10-glossary-faq.md](docs/10-glossary-faq.md) |
