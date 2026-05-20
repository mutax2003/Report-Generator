# ESA Report Generator

Web app for generating Phase 1 / Phase 2 Environmental Site Assessment reports from an Excel data file and a Word template (Jinja2 via [docxtpl](https://docxtpl.readthedocs.io/)).

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
streamlit run app.py
```

1. Upload **Excel** (`.xlsx`) and **Word template** (`.docx`).
2. Review **Pre-flight checks** (matched/missing tags, sheet names).
3. Fill **sidebar** fields; download sample/production templates from the sidebar if needed.
4. Click **Generate Report**, then **Download Report**.

## Sample files

Generate or refresh samples:

```powershell
python scripts\create_samples.py
```

| File | Purpose |
|------|---------|
| `samples/sample_data.xlsx` | Minimal demo data |
| `samples/sample_template.docx` | Tagged demo template with lab table |
| `samples/production_data.xlsx` | Fields aligned with production ESA layout |
| `samples/production_template.docx` | Tagged production template (field guide) |
| `samples/production_starter_template.docx` | Minimal tagged starter |
| `samples/rendered_output.docx` | CLI output from sample render |

**Try the demo:** upload `samples/sample_data.xlsx` + `samples/sample_template.docx`.

## Production template

`22xxxxR Phase 2 ESA Full_merge.docx` is a full report without Jinja tags yet. See [PRODUCTION_TEMPLATE_GUIDE.txt](PRODUCTION_TEMPLATE_GUIDE.txt) for how to add `{{ placeholders }}` and use `samples/production_data.xlsx`.

List tags in any template:

```powershell
python scripts\inventory_template.py path\to\template.docx
```

## CLI smoke test (no UI)

```powershell
python scripts\render_cli.py
python scripts\render_cli.py --excel samples\production_data.xlsx --template "22xxxxR Phase 2 ESA Full_merge.docx" --out samples\production_rendered.docx
```

## AI assistant (Tier 1 & 2)

See **[AI_FEATURES.md](AI_FEATURES.md)** for template tagging, lab PDF import, narrative drafts, pre-flight copilot, consistency checks, and exceedance notes. Works offline without an API key; set `OPENAI_API_KEY` for enhanced LLM parsing.

## Best practices

See **[BEST_PRACTICES.md](BEST_PRACTICES.md)** for patterns from document-automation and mail-merge tools: field contract, pre-flight, dry-run preview, template versioning, and generation manifests (audit trail).

- **Field contract:** `schemas/field_contract.json`
- **Dry run:** **Preview data (dry run)** in the app (no Word render)
- **Manifest:** download JSON after generate or from CLI (`*_manifest.json`)

## Excel layout

See [EXCEL_LAYOUT.txt](EXCEL_LAYOUT.txt):

- Sheet **`ProjectData`** — headers row 1, first data row → template variables.
- Sheet **`LabResults`** — required for Phase 2; optional for Phase 1.

## Word templates

See [JINJA2_CHEATSHEET.txt](JINJA2_CHEATSHEET.txt) for `{{ variables }}` and `{%tr for item in lab_results %}` table loops.

## Project layout

```
app.py              Streamlit UI
engine.py           ReportEngine (Excel → docxtpl → .docx)
provenance.py       Generation manifest / SHA-256 audit fields
field_validation.py Recommended-field warnings vs field contract
schemas/            field_contract.json
security.py         Upload validation, zip safety, limits
ui/                 sidebar, preflight, preview, results, workflow
scripts/
  create_samples.py
  tag_production_template.py
  production_e2e.py
  render_cli.py
  inventory_template.py
automate/           Power Automate / HTTP ingress around ReportEngine
samples/            Test data and templates (binaries committed)
```

## Security and limits

Untrusted uploads are validated before rendering:

| Control | Limit / behavior |
|---------|------------------|
| Excel size | 15 MB max; must be real OOXML (ZIP + spreadsheet parts) |
| Template size | 30 MB max; must contain `word/document.xml` |
| Zip bombs | Actual bytes read capped; rejects encrypted entries; compression ratio limits |
| Zip paths | Rejects `..` and absolute paths inside archives |
| Jinja2 | `SandboxedEnvironment` + `StrictUndefined` — templates are trusted code |
| Lab rows | 10,000 max (truncated with warning) |
| Cell / meta text | Length caps on context and sidebar fields |
| Download filename | Sanitized (no path separators) |
| Errors | Internal/library errors redacted in UI; details logged server-side |
| Output | Generated `.docx` re-validated before download |

**Deployment:** Run on `localhost` for internal use. Do not expose Streamlit on `0.0.0.0` without VPN or an authenticated reverse proxy. Word templates should come from trusted authors only.

See [`security.py`](security.py) to adjust limits. Run checks:

```powershell
python -m unittest discover -s tests -v
python scripts\render_cli.py
.\scripts\run_security_checks.ps1
```

Edge-case coverage lives in `tests/test_edge_cases.py` (Excel sheets, Phase 1/2, exceedances, zip validation, warnings).

Dependency audit: `pip install pip-audit` then `pip-audit -r requirements.txt`.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Missing sheet errors | Add `ProjectData` / `LabResults` tabs per [EXCEL_LAYOUT.txt](EXCEL_LAYOUT.txt) |
| Lab table repeats headers | Use static header row *before* `{%tr for item in lab_results %}` |
| Template render failed | Check Jinja tags are not split across Word formatting runs |
| Streamlit won't start | `pip install -r requirements.txt` in `.venv` |
| Regenerate demo files | `python scripts\create_samples.py` |

## Automation (Power Automate / HTTP)

See **[AUTOMATE.md](AUTOMATE.md)** for `automate.render`, local HTTP service, and production E2E:

```powershell
python scripts\production_e2e.py
python -m automate.http_server --port 8765
```
