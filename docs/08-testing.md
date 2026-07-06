# 08 — Testing

## Test suite overview

Location: [`tests/`](../tests/)

Framework: Python `unittest` (stdlib).

| Module | Focus |
|--------|-------|
| `test_edge_cases.py` | Excel edge cases, exceedances, security, render warnings |
| `test_render_e2e.py` | Full sample render to `samples/e2e_output.docx` |
| `test_security.py` | Upload rejection, safe errors, sample render |
| `test_template_tools.py` | Preflight, coverage, missing vars |
| `test_template_attachments.py` | PDF→DOCX prepare cache |
| `test_provenance.py` | Manifest, contract warnings, dry run |
| `test_production_starter.py` | Production starter template render |
| `test_production_template.py` | Full production template render |
| `test_ai_features.py` | AI offline paths, RAG, heuristics |
| `test_phase1_alberta.py` | Alberta Phase I Ecoventure samples render + context |
| `test_phase1_narrative.py` | Signum-style executive summary builder + auto-fill |
| `test_phase1_devon.py` | Devon profile (optional slow full template) |
| `test_phrase_resolver.py` | Phrase catalog, Excel `PhraseCatalog`, UI meta merge |
| `test_batch_render.py` | Multi-row `ProjectData` batch render |
| `test_phase1_markup.py` | Phase I markup / tag repair helpers |
| `test_phase1_pdf_text.py` | PDF text extraction for markup pipeline |
| `test_groundwater_monitoring.py` | Groundwater profile render + context |
| `test_groundwater_narrative.py` | GW executive summary enrichment |
| `test_gw_trends.py` | Groundwater trend notes |
| `test_well_log_extract.py` | Well log PDF heuristics |
| `test_sed002_compliance.py` | SED 002 §10 checklist evaluation |
| `test_appendix_generator.py` | Phase I appendices A/D/G generation |
| `test_deliverable_pack.py` | Deliverable zip, OneStop export |
| `test_automate_render.py` | `automate/render.py` smoke |
| `test_project_folder.py` | Folder resolve, enrich, render to `delivered/` |
| `test_folder_picker.py` | Native folder picker + UI load bundle |
| `test_source_ingest.py` | Source PDF ingest → `ai_drafts/` |
| `test_workflow_mode.py` | Startup workflow picker labels |
| `test_upload_helpers.py` | Upload digest + session byte cache |
| `test_streamlit_smoke.py` | AppTest — workflow picker + folder load |
| `test_phase2_vertical.py` | Phase II / remediation / reclamation verticals |
| `test_report_profiles.py` | Profile resolution and exports |
| `test_report_profile_export.py` | ReportConfig workbook export |
| `test_layout.py` | Layout / workflow step helpers |
| `test_branding.py` | App header branding |
| `test_alberta_imagery.py` | Hero imagery cache |
| `test_smoke_integration.py` | Optional slow health script path |
| `test_render_path_parity.py` | Engine vs automate vs project-folder DWDA parity |
| `test_schema_parity.py` | field_contract vs report_profiles parity |
| `test_compliance_helpers.py` | Appendix label normalization, `yes_value`, `resolved_appendix_labels` |
| `test_phase2_triggers.py` | Unified Phase II trigger collection |
| `test_reclamation_compliance.py` | Reclamation certificate checklist evaluation |
| `test_dwda_calculations.py` | DWDA metal/salt/DST calculation engine |
| `test_ecoventure_workbook.py` | Ecoventure cell contract ingest + merge |
| `test_dwda_compliance.py` | DWDA compliance evaluation + enrichment |
| `test_dwda_edge_cases.py` | DWDA / Ecoventure ingest edge cases |

## Seventeen-step health check

Quick regression pass (imports, Phase I Ecoventure render, appendices A/D/G, project folder ingest with Ecoventure merge, source PDF ingest, security, batch, groundwater, DWDA merge):

```powershell
python scripts\health_check.py
```

## Running tests

```powershell
cd "c:\Users\Andrew Liu\Report Generator"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\create_samples.py
python -m unittest discover -s tests -v
```

Expected: **284 tests OK** (3 may skip; includes render-path parity, phase2 triggers, reclamation compliance, schema parity, compliance helpers, DWDA/Ecoventure calc + ingest, upload cache helpers, Streamlit AppTest smoke, folder picker, source PDF ingest, project folder, Phase I appendix generator, automate package smoke, Phase II/remediation verticals, SED 002 compliance, groundwater monitoring, phrase resolver, batch render, deliverable pack, smoke integration).

Run `python scripts\count_tests.py` to verify the documented count matches `unittest discover`.

Optional slow tests (Devon full template render): `ESA_RUN_SLOW=1 python -m unittest discover -s tests -v`

Optional slow check: `ESA_RUN_HEALTH_CHECK=1 python -m unittest tests.test_smoke_integration.SmokeIntegrationTests.test_health_check_script`

### Skip conditions

Some tests skip if `samples/` missing — committed samples in repo prevent skips.

## End-to-end scripts (no UI)

| Script | Validates | CI |
|--------|-----------|-----|
| `scripts/render_cli.py` | Demo sample merge + manifest | Yes |
| `scripts/phase1_package_smoke.py` | Deliverable package zip (appendix D) | Yes |
| `scripts/tag_production_template.py` | Production template tagging | Yes |
| `scripts/production_e2e.py` | Production data + template preflight + render | Yes |
| `scripts/phase1_alberta_e2e.py` | Alberta Phase I Ecoventure preflight + render | Yes |
| `scripts/dwda_workflow_e2e.py` | DWDA calculate + preflight + appendix H + D/G + OneStop zip | Yes |
| `scripts/test_with_your_documents.py` | Pre-flight, dry run, render for any Excel + template pair | Yes |
| `scripts/health_check.py` | 17-step regression (incl. test count parity) | Yes |
| `scripts/phase2_alberta_e2e.py` | Alberta Phase II sample preflight + render | Yes |
| `scripts/groundwater_e2e.py` | Groundwater monitoring profile render | Yes |
| `scripts/create_phase2_project_folder.py` | Phase II test folder under `user_test/` | Yes |
| `scripts/ingest_project_folder.py --render` | Project folder CLI render | Yes |
| `scripts/streamlit_smoke.py` | Streamlit AppTest smoke (workflow + folder load) | Yes (via unittest) |
| `scripts/phase3_remediation_e2e.py` | Phase III remediation sample render | Local |
| `scripts/reclamation_e2e.py` | Reclamation certificate sample render | Local |
| `scripts/phase1_site_e2e.py` | Large site markup templates (251106R + 260109R) | Local |
| `scripts/prepare_user_test_pack.py` | Copy samples to `user_test/` (row 2 customized) | Local |

User workflow (your Excel + Word): [12-testing-with-your-documents.md](12-testing-with-your-documents.md)

Full local E2E chain:

```powershell
python scripts\create_samples.py
python scripts\create_appendix_templates.py
python scripts\tag_production_template.py
python scripts\render_cli.py
python scripts\production_e2e.py
python scripts\phase1_alberta_e2e.py
python scripts\phase2_alberta_e2e.py
python scripts\groundwater_e2e.py
python -m unittest discover -s tests -v
python scripts\health_check.py
python scripts\create_phase2_project_folder.py
python scripts\ingest_project_folder.py --folder user_test\phase2_alberta --render --no-llm
```

Outputs:

- `samples/rendered_output.docx` + manifest (demo)
- `samples/production_rendered.docx` + manifest (production, gitignored docx)
- `user_test/phase2_alberta/delivered/*.docx` (project folder CLI)

## Streamlit smoke test

Automated (no browser):

```powershell
python scripts\streamlit_smoke.py
# or: python -m unittest tests.test_streamlit_smoke -v
```

Optional local browser smoke (`pip install -r requirements-dev.txt` then `playwright install chromium`):

```powershell
python scripts\playwright_smoke.py
```

Manual:

1. `streamlit run app.py` or `.\run.ps1 streamlit`
2. **Excel + template:** upload `samples/sample_data.xlsx` + `samples/sample_template.docx`
3. **Project folder:** choose **Project folder + AI** → Browse → `user_test\phase2_alberta` → Load folder
4. Pre-flight green → Generate → Download
5. Open Word — verify fields and tables

Automated import check:

```powershell
python -c "import app; print('ok')"
```

## CI (GitHub Actions)

Workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

On push/PR to `main` or `master`:

1. Python 3.11
2. `pip install -r requirements.txt`
3. `python scripts/create_samples.py`
4. `python scripts/create_appendix_templates.py`
5. `python scripts/tag_production_template.py`
6. `python -m unittest discover -s tests -v`
7. `python scripts/render_cli.py`
8. `python scripts/phase1_package_smoke.py`
9. `python scripts/production_e2e.py`
10. `python scripts/phase1_alberta_e2e.py`
11. `python scripts/phase2_alberta_e2e.py`
12. `python scripts/groundwater_e2e.py`
13. `python scripts/create_phase2_project_folder.py`
14. `python scripts/ingest_project_folder.py --folder user_test/phase2_alberta --render --no-llm`
15. `python scripts/test_with_your_documents.py`
16. `python scripts/create_ecoventure_dwda_fixture.py`
17. `python scripts/dwda_workflow_e2e.py`
18. `python scripts/health_check.py` (17-step regression)

Unit tests include `tests/test_streamlit_smoke.py` (AppTest workflow + folder load) and `tests/test_render_path_parity.py` (appendix-aware render paths).

**Local pre-release only:** `phase3_remediation_e2e.py`, `reclamation_e2e.py`, `phase1_site_e2e.py` (large templates), `playwright_smoke.py`.

## Test environment bypass

`ESA_VALIDATION_BYPASS=1` disables upload validation for unit tests constructing minimal ZIP fixtures. **Never set in production.**

## Adding tests

1. Prefer real fixtures in `samples/` over inline ZIP bytes when possible.
2. Use `unittest.SkipTest` if optional large files absent.
3. Cover warning vs error paths separately.
4. Run full suite before PR.

## Coverage gaps (known)

- Streamlit UI not browser-automated (optional `playwright_smoke.py` locally)
- Full 100+ page production merge doc not in CI (local gitignored file)
- OpenAI API paths tested in offline mode only in CI
- `phase1_site_e2e.py` requires `ESA_ALLOW_LARGE_TEMPLATE=1` (local)
