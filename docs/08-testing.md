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
| `test_provenance.py` | Manifest, contract warnings, dry run |
| `test_production_starter.py` | Production starter template render |
| `test_production_template.py` | Full production template render |
| `test_ai_features.py` | AI offline paths, RAG, heuristics |
| `test_phase1_alberta.py` | Alberta Phase I Ecoventure samples render + context |
| `test_phase1_narrative.py` | Signum-style executive summary builder + auto-fill |
| `test_phrase_resolver.py` | Phrase catalog, Excel `PhraseCatalog`, UI meta merge |
| `test_batch_render.py` | Multi-row `ProjectData` batch render |
| `test_phase1_markup.py` | Phase I markup / tag repair helpers |
| `test_phase1_pdf_text.py` | PDF text extraction for markup pipeline |
| `test_groundwater_monitoring.py` | Groundwater profile render + context |
| `test_groundwater_narrative.py` | GW executive summary enrichment |
| `test_gw_trends.py` | Groundwater trend notes |
| `test_well_log_extract.py` | Well log PDF heuristics |

## Thirteen-step health check

Quick regression pass (imports, Phase I Ecoventure render, appendices A/D/G, security, full unittest):

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

Expected: **136+ tests OK** (includes Phase I appendix generator, automate package smoke, Phase II/remediation verticals, SED 002 compliance, groundwater monitoring, phrase resolver, batch render, deliverable pack, smoke integration).

Optional slow tests (Devon full template render): `ESA_RUN_SLOW=1 python -m unittest discover -s tests -v`

Optional slow check: `ESA_RUN_HEALTH_CHECK=1 python -m unittest tests.test_smoke_integration.SmokeIntegrationTests.test_health_check_script`

### Skip conditions

Some tests skip if `samples/` missing — committed samples in repo prevent skips.

## End-to-end scripts (no UI)

| Script | Validates |
|--------|-----------|
| `scripts/render_cli.py` | Demo sample merge + manifest |
| `scripts/tag_production_template.py` | Production template tagging |
| `scripts/production_e2e.py` | Production data + template preflight + render |
| `scripts/phase1_alberta_e2e.py` | Alberta Phase I Ecoventure preflight + render |
| `scripts/phase2_alberta_e2e.py` | Alberta Phase II sample preflight + render |
| `scripts/phase3_remediation_e2e.py` | Phase III remediation sample render |
| `scripts/reclamation_e2e.py` | Reclamation certificate sample render |
| `scripts/prepare_user_test_pack.py` | Copy samples to `user_test/` (row 2 customized) |
| `scripts/test_with_your_documents.py` | Pre-flight, dry run, render for any Excel + template pair |

User workflow (your Excel + Word): [12-testing-with-your-documents.md](12-testing-with-your-documents.md)

Full local E2E chain:

```powershell
python scripts\create_samples.py
python scripts\tag_production_template.py
python scripts\render_cli.py
python scripts\production_e2e.py
python -m unittest discover -s tests -v
```

Outputs:

- `samples/rendered_output.docx` + manifest (demo)
- `samples/production_rendered.docx` + manifest (production, gitignored docx)

## Streamlit smoke test

Manual:

1. `streamlit run app.py`
2. Upload `samples/sample_data.xlsx` + `samples/sample_template.docx`
3. Pre-flight green → Generate → Download
4. Open Word — verify site name and red TCE exceedance

Automated import check:

```powershell
python -c "import app; print('ok')"
```

## CI (GitHub Actions)

Workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

On push/PR to `main` or `master`:

1. Python 3.11
2. `pip install -r requirements.txt`
3. `create_samples.py`
4. `tag_production_template.py`
5. `unittest discover`
6. `render_cli.py`
7. `production_e2e.py`
8. `phase1_alberta_e2e.py`
9. `health_check.py` (13-step regression, incl. Phase I appendices D/G, groundwater + phrases)
10. `scripts/groundwater_e2e.py` (groundwater profile preflight + render)
11. `test_with_your_documents.py` (default Alberta sample pair)

## Test environment bypass

`ESA_VALIDATION_BYPASS=1` disables upload validation for unit tests constructing minimal ZIP fixtures. **Never set in production.**

## Adding tests

1. Prefer real fixtures in `samples/` over inline ZIP bytes when possible.
2. Use `unittest.SkipTest` if optional large files absent.
3. Cover warning vs error paths separately.
4. Run full suite before PR.

## Coverage gaps (known)

- Streamlit UI not browser-automated
- Full 100+ page production merge doc not in CI (local gitignored file)
- OpenAI API paths tested in offline mode only in CI
