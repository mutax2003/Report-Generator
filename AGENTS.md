# Agent index — ESA Report Generator

Start here when working in this repo with Cursor or other coding agents.

## Rules and docs

| Resource | Purpose |
|----------|---------|
| [`.cursor/rules/esa-report-generator-architecture.mdc`](.cursor/rules/esa-report-generator-architecture.mdc) | Always-on architecture, sheets, venv, V1 checklist |
| [`docs/README.md`](docs/README.md) | Full documentation map (01–12) |
| [`docs/11-alberta-phase1-esa.md`](docs/11-alberta-phase1-esa.md) | Primary use case — Ecoventure Alberta Phase I |
| [`docs/12-testing-with-your-documents.md`](docs/12-testing-with-your-documents.md) | Test your Excel + Word pair |
| [`schemas/field_contract.json`](schemas/field_contract.json) | Sheet names and recommended fields |

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
| Web UI | `streamlit run app.py` |
| Quick merge test | `python scripts\test_with_your_documents.py` |
| User test folder | `python scripts\prepare_user_test_pack.py` then edit `user_test/` |
| Regression | `python scripts\health_check.py` |
| Unit tests | `python -m unittest discover -s tests -v` |

## Key modules

`app.py` · `engine.py` (`ReportEngine`) · `template_tools.py` · `security.py` · `ui/` · `scripts/`

Do not put Streamlit imports in `engine.py`. Extend `field_contract.json` when adding production fields.
