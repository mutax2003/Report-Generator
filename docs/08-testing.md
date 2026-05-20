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

## Running tests

```powershell
cd "c:\Users\Andrew Liu\Report Generator"
pip install -r requirements.txt
python scripts\create_samples.py
python -m unittest discover -s tests -v
```

Expected: **56 tests OK** (count may increase with new tests).

### Skip conditions

Some tests skip if `samples/` missing — committed samples in repo prevent skips.

## End-to-end scripts (no UI)

| Script | Validates |
|--------|-----------|
| `scripts/render_cli.py` | Demo sample merge + manifest |
| `scripts/tag_production_template.py` | Production template tagging |
| `scripts/production_e2e.py` | Production data + template preflight + render |

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
