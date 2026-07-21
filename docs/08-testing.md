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
| `test_ai_config.py` | LLM provider presets (Gemini, Together, Ollama, Groq) |
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
| `test_verify_tier.py` | `verify_tier.py` tiers + pre-commit UX gate |
| `test_streamlit_smoke.py` | AppTest — workflow picker, sample load, welcome dismiss, next steps, folder load |
| `test_menubar.py` | Windows-style menus, F1 help pack builder, AppTest menu actions |
| `test_onboarding.py` | `compute_next_actions`, glossary |
| `test_appendix_helpers.py` | `first_missing_onestop_label` |
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
| `test_audit_trail.py` | Audit event append / file lock |
| `test_esa_auth.py` | API key auth; client `X-ESA-Roles` ignored |
| `test_esa_tenant.py` | Tenant isolation helpers |
| `test_esa_rate_limit.py` | IP + key-digest rate limits |
| `test_esa_observability.py` | Metrics / tracing hooks |
| `test_http_server.py` | Automate HTTP server auth, headers, multipart |
| `test_job_queue.py` | Async job queue |
| `test_qp_signature.py` | QP signature attestation |
| `test_records_retention.py` | Retention policy + purge helpers |
| `test_ai_apply.py` | Apply drafts to ProjectData; appendix manifest preference |
| `test_apec_extract.py` | APEC heuristics, Excel Apecs merge, profile mapping |

## Eighteen-step health check

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

Expected: **389 tests OK** (4 may skip; includes verify_tier/pre-commit, render-path batch parity, onboarding UX, AppTest sample load/welcome/next-steps, AI provider config, render-path parity, phase2 triggers, reclamation compliance, schema parity, compliance helpers, DWDA/Ecoventure calc + ingest, upload cache helpers, Streamlit AppTest smoke, folder picker, source PDF ingest, project folder, Phase I appendix generator, automate package smoke, Phase II/remediation verticals, SED 002 compliance, groundwater monitoring, phrase resolver, batch render, deliverable pack, smoke integration, production modules: audit trail, QP signature, auth/tenant/job queue/rate limit/observability, HTTP multipart parser).

Run `python scripts\count_tests.py` to verify the documented count matches `unittest discover`.

Optional slow tests (Devon full template render): `ESA_RUN_SLOW=1 python -m unittest discover -s tests -v`

Optional slow check: `ESA_RUN_HEALTH_CHECK=1 python -m unittest tests.test_smoke_integration.SmokeIntegrationTests.test_health_check_script`

### Skip conditions

Up to **4** tests may skip depending on env/fixtures (e.g. optional slow Devon template, health-check gated on `ESA_RUN_HEALTH_CHECK=1`, missing optional samples). Committed `samples/` prevent most skips in a normal checkout.

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
| `scripts/health_check.py` | 18-step regression (incl. test count parity + HTML help) | Yes |
| `scripts/phase2_alberta_e2e.py` | Alberta Phase II sample preflight + render | Yes |
| `scripts/groundwater_e2e.py` | Groundwater monitoring profile render | Yes |
| `scripts/create_phase2_project_folder.py` | Phase II test folder under `user_test/` | Yes |
| `scripts/ingest_project_folder.py --render` | Project folder CLI render | Yes |
| `scripts/streamlit_smoke.py` | Streamlit AppTest (workflow, sample load, UX onboarding) | Yes |
| `scripts/verify_tier.py` | Multi-agent verification tiers (unit / ux / profile / release) | Local |
| `scripts/pre_commit_check.py` | Pre-commit UX gate when Streamlit paths staged | Optional hook |
| `scripts/phase3_remediation_e2e.py` | Phase III remediation sample render | Yes |
| `scripts/reclamation_e2e.py` | Reclamation certificate sample render | Yes |
| `scripts/phase1_site_e2e.py` | Large site markup templates (251106R + 260109R) | Local |
| `scripts/prepare_user_test_pack.py` | Copy samples to `user_test/` (row 2 customized) | Local |

User workflow (your Excel + Word): [12-testing-with-your-documents.md](12-testing-with-your-documents.md)

Full local **test**/E2E chain (ubuntu CI matrix on 3.11). Prefer `python scripts\verify_tier.py --tier release` for pre-merge (adds quality gates: count_tests, build_help, ruff, mypy, validation_evidence, then this E2E chain):

```powershell
python scripts\build_help.py
python scripts\create_samples.py
python scripts\create_appendix_templates.py
python scripts\tag_production_template.py
python -m unittest discover -s tests -v
python scripts\streamlit_smoke.py
python scripts\render_cli.py
python scripts\phase1_package_smoke.py
python scripts\production_e2e.py
python scripts\phase1_alberta_e2e.py
python scripts\phase2_alberta_e2e.py
python scripts\groundwater_e2e.py
python scripts\create_phase2_project_folder.py
python scripts\ingest_project_folder.py --folder user_test\phase2_alberta --render --no-llm
python scripts\test_with_your_documents.py
python scripts\create_ecoventure_dwda_fixture.py
python scripts\dwda_workflow_e2e.py
python scripts\phase3_remediation_e2e.py
python scripts\reclamation_e2e.py
python scripts\health_check.py
```

`release` = quality gates (minus coverage) **plus** full E2E above. Hand-rolling only the E2E list skips ruff/mypy/`build_help`.

Outputs:

- `samples/rendered_output.docx` + manifest (demo)
- `samples/production_rendered.docx` + manifest (production, gitignored docx)
- `user_test/phase2_alberta/delivered/*.docx` (project folder CLI)

## Verification tiers (multi-agent)

Run the tier that matches your change (see [AGENTS.md](../AGENTS.md#multi-agent-workflow-cursor)):

```powershell
python scripts\verify_tier.py --tier unit
python scripts\verify_tier.py --tier ux
python scripts\verify_tier.py --tier profile --playbook b
python scripts\verify_tier.py --tier release
```

| Tier | Steps |
|------|-------|
| **unit** | `count_tests.py` → `unittest discover` |
| **ux** | `build_help.py` → **unit** → `streamlit_smoke.py` |
| **profile** | **ux** → playbook E2E (+ `health_check.py` for playbooks b/c/d) |
| **release** | Full `RELEASE_STEPS` (quality gates minus coverage + ubuntu E2E) |

`release` approximates CI **quality** gates (ruff / mypy / `build_help` / `validation_evidence.py`, **minus coverage**) plus the ubuntu **test** matrix E2E chain. It does **not** run **windows-smoke**.

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

On push/PR to `main` or `master`, three jobs:

### `quality` (ubuntu, Python 3.11)

1. `pip install -r requirements.txt` + `requirements-dev.txt`
2. Ruff lint + format check (production modules)
3. Mypy (production modules)
4. `python scripts/build_help.py` → `help/index.html`
5. `coverage run -m unittest discover` + `coverage report --fail-under=50`
6. `python scripts/validation_evidence.py`

### `test` (ubuntu, Python 3.11–3.13 matrix)

On every matrix version:

1. `pip install -r requirements.txt`
2. `python scripts/create_samples.py`
3. `python scripts/create_appendix_templates.py`
4. `python scripts/build_help.py`
5. `python scripts/tag_production_template.py`
6. `python -m unittest discover -s tests -v`
7. `python scripts/streamlit_smoke.py`

**Full E2E chain on Python 3.11 only:**

8. `python scripts/render_cli.py`
9. `python scripts/phase1_package_smoke.py`
10. `python scripts/production_e2e.py`
11. `python scripts/phase1_alberta_e2e.py`
12. `python scripts/phase2_alberta_e2e.py`
13. `python scripts/groundwater_e2e.py`
14. `python scripts/create_phase2_project_folder.py`
15. `python scripts/ingest_project_folder.py --folder user_test/phase2_alberta --render --no-llm`
16. `python scripts/test_with_your_documents.py`
17. `python scripts/create_ecoventure_dwda_fixture.py`
18. `python scripts/dwda_workflow_e2e.py`
19. `python scripts/phase3_remediation_e2e.py`
20. `python scripts/reclamation_e2e.py`
21. `python scripts/health_check.py` (18-step regression)

Unit tests include `tests/test_streamlit_smoke.py` (AppTest workflow + folder load) and `tests/test_render_path_parity.py` (appendix-aware render paths).

### `windows-smoke` (windows-latest, on PRs/pushes)

1. `.\scripts\build_windows_deploy.ps1 -SkipExe`
2. Assert `dist\ESA-Report-Generator\help\index.html` exists
3. Bundled-venv `health_check.py` + `streamlit_smoke.py`

**Local pre-release only:** `phase1_site_e2e.py` (large templates), `playwright_smoke.py`.

**`verify_tier.py --tier release`:** quality gates minus coverage + ubuntu E2E (includes `build_help`); does **not** run windows-smoke.

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
