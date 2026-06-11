# Agent index — ESA Report Generator

Start here when working in this repo with Cursor or other coding agents.

## Rules and docs

| Resource | Purpose |
|----------|---------|
| [`.cursor/rules/esa-report-generator-architecture.mdc`](.cursor/rules/esa-report-generator-architecture.mdc) | Always-on architecture, sheets, venv, UI checklist |
| [`.cursor/rules/esa-testing-ci.mdc`](.cursor/rules/esa-testing-ci.mdc) | unittest, E2E scripts, CI parity (`tests/`, `scripts/`, workflows) |
| [`.cursor/rules/esa-streamlit-ui.mdc`](.cursor/rules/esa-streamlit-ui.mdc) | `app.py` + `ui/` — Streamlit boundaries and module roles |
| [`.cursor/rules/esa-security-uploads.mdc`](.cursor/rules/esa-security-uploads.mdc) | Upload limits, safe errors, `ESA_VALIDATION_BYPASS` |
| [`.cursor/rules/esa-schemas-and-templates.mdc`](.cursor/rules/esa-schemas-and-templates.mdc) | `schemas/*.json`, profiles, Word/Excel authoring |
| [`docs/README.md`](docs/README.md) | Full documentation map (01–20) |
| [`docs/20-aer-sed002-phase1-esa.md`](docs/20-aer-sed002-phase1-esa.md) | AER SED 002 §10 checklist, OneStop export |
| [`docs/00-start-here.md`](docs/00-start-here.md) | Consultants — upload, profile, generate, appendices |
| [`docs/11-alberta-phase1-esa.md`](docs/11-alberta-phase1-esa.md) | Primary use case — Ecoventure Alberta Phase I |
| [`docs/12-testing-with-your-documents.md`](docs/12-testing-with-your-documents.md) | Test your Excel + Word pair |
| [`docs/13-flexible-report-profiles.md`](docs/13-flexible-report-profiles.md) | Custom report types + sheet mapping |
| [`docs/14-deployment.md`](docs/14-deployment.md) | Docker, Azure, production checklist |
| [`docs/15-power-automate-guide.md`](docs/15-power-automate-guide.md) | SharePoint → HTTP render flow |
| [`docs/16-team-rollout.md`](docs/16-team-rollout.md) | Team rollout (~50 users), SharePoint, pilot |
| [`docs/17-server-update-runbook.md`](docs/17-server-update-runbook.md) | Server deploy / update steps |
| [`sharepoint/PUBLISH_CHECKLIST.md`](sharepoint/PUBLISH_CHECKLIST.md) | SharePoint upload checklist |
| [`schemas/report_profiles.json`](schemas/report_profiles.json) | **Canonical** recommended fields per profile |
| [`schemas/sed002_phase1_checklist.json`](schemas/sed002_phase1_checklist.json) | SED 002 §10 preflight checklist |
| [`schemas/field_contract.json`](schemas/field_contract.json) | Legacy reference + AI tagger |

## Setup

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\create_samples.py
```

Or: `.\run.ps1 scripts\create_samples.py` (uses venv Python on Windows).

## Run

| Task | Command |
|------|---------|
| Web UI | `.\run.ps1 streamlit` or `streamlit run app.py` (templates: `.docx` or `.pdf`) |
| Quick merge test | `python scripts\test_with_your_documents.py` |
| Phase 1 PDF → markup + site Excel | `python scripts\phase1_pdf_to_markup.py` · `python scripts\create_phase1_site_samples.py` |
| Phase 1 site E2E (251106R + 260109R) | `$env:ESA_ALLOW_LARGE_TEMPLATE="1"; python scripts\phase1_site_e2e.py` |
| User test folder | `python scripts\prepare_user_test_pack.py` then edit `user_test/` |
| Regression | `python scripts\health_check.py` (**13 checks**, incl. Phase I appendices D/G) |
| Phase I E2E + deliverable zip | `python scripts\phase1_alberta_e2e.py` |
| Appendix templates (A/D/G) | `python scripts\create_appendix_templates.py` |
| CLI render + package | `python scripts\render_cli.py --package` (see `--report-type phase1_alberta`) |
| SharePoint bundle | `.\scripts\package_team_sharepoint.ps1` |
| Team Docker host | `docker compose up -d --build` (see [docs/14-deployment.md](docs/14-deployment.md)) |
| Unit tests | `python -m unittest discover -s tests -v` (**135 tests**; see [docs/08-testing.md](docs/08-testing.md)) |
| Devon sample pair | `python scripts\create_phase1_devon_pair.py` |
| Slow health in smoke test | `$env:ESA_RUN_HEALTH_CHECK="1"` then run `tests.test_smoke_integration` |

## Key modules

`app.py` · `engine.py` (`ReportEngine`, `render_batch`) · `appendix_generator.py` (Phase I appendices D/G) · `phrase_resolver.py` · `groundwater_narrative.py` · `phase1_narrative.py` · `phase1_decision.py` · `sed002_compliance.py` · `report_profile.py` (`read_excel_meta`) · `template_attachments.py` · `template_size.py` · `deliverable_pack.py` (OneStop export, deliverable zip) · `phase1_markup.py` · `phase1_pdf_text.py` · `template_tools.py` · `security.py` · `provenance.py` · `ui/` (`sidebar`, `phrase_panel`, `preflight`, `appendix_panel`, `results`, `helpers`) · `schemas/phrase_catalog.json` · `schemas/sed002_phase1_checklist.json` · `scripts/` (`create_appendix_templates.py`) · `automate/`

Do not put Streamlit imports in `engine.py`. Extend **`schemas/report_profiles.json`** `recommended_fields` when adding production fields; update `field_contract.json` if the AI tagger or legacy docs need the same names. For phrase fields, update **`schemas/phrase_catalog.json`** and [docs/04-template-authoring.md](docs/04-template-authoring.md). For multi-site Excel, use **`ProjectData` rows 3+** and batch mode or `render_cli.py --all-rows`.
