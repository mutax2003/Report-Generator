# Agent index — ESA Report Generator

Start here when working in this repo with Cursor or other coding agents.

## Rules and docs

| Resource | Purpose |
|----------|---------|
| [`.cursor/rules/esa-report-generator-architecture.mdc`](.cursor/rules/esa-report-generator-architecture.mdc) | Always-on architecture, sheets, venv, UI checklist |
| [`docs/README.md`](docs/README.md) | Full documentation map (01–15) |
| [`docs/00-start-here.md`](docs/00-start-here.md) | Consultants — upload, profile, generate, appendices |
| [`docs/11-alberta-phase1-esa.md`](docs/11-alberta-phase1-esa.md) | Primary use case — Ecoventure Alberta Phase I |
| [`docs/12-testing-with-your-documents.md`](docs/12-testing-with-your-documents.md) | Test your Excel + Word pair |
| [`docs/13-flexible-report-profiles.md`](docs/13-flexible-report-profiles.md) | Custom report types + sheet mapping |
| [`docs/14-deployment.md`](docs/14-deployment.md) | Docker, Azure, production checklist |
| [`docs/15-power-automate-guide.md`](docs/15-power-automate-guide.md) | SharePoint → HTTP render flow |
| [`schemas/report_profiles.json`](schemas/report_profiles.json) | **Canonical** recommended fields per profile |
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
| Web UI | `streamlit run app.py` (templates: `.docx` or `.pdf`) |
| Quick merge test | `python scripts\test_with_your_documents.py` |
| User test folder | `python scripts\prepare_user_test_pack.py` then edit `user_test/` |
| Regression | `python scripts\health_check.py` |
| Unit tests | `python -m unittest discover -s tests -v` (75 tests) |
| Slow health in smoke test | `$env:ESA_RUN_HEALTH_CHECK="1"` then run `tests.test_smoke_integration` |

## Key modules

`app.py` · `engine.py` (`ReportEngine`) · `report_profile.py` · `template_attachments.py` · `deliverable_pack.py` · `phase1_narrative.py` · `template_tools.py` · `security.py` · `provenance.py` · `ui/` (`sidebar`, `preflight`, `appendix_panel`, `helpers`) · `scripts/` · `automate/`

Do not put Streamlit imports in `engine.py`. Extend **`schemas/report_profiles.json`** `recommended_fields` when adding production fields; update `field_contract.json` if the AI tagger or legacy docs need the same names.
