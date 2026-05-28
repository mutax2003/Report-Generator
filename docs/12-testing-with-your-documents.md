# 12 — Testing with your Excel and Word templates

Step-by-step guide to test the ESA Report Generator with bundled samples first, then your own `.xlsx` and `.docx` files.

## Prerequisites

```powershell
cd "c:\Users\Andrew Liu\Report Generator"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\create_samples.py
```

Optional one-command test pack:

```powershell
python scripts\prepare_user_test_pack.py
python scripts\test_with_your_documents.py
```

---

## Path A — Bundled samples (start here)

| Goal | Excel | Word template |
|------|-------|----------------|
| Quick demo | `samples/sample_data.xlsx` | `samples/sample_template.docx` |
| **Alberta Phase I (Ecoventure)** | `samples/phase1_alberta_data.xlsx` | `samples/phase1_alberta_template.docx` |
| **Devon Phase I (short, 2017 reference)** | `samples/phase1_devon_data.xlsx` | `samples/Devon phase 1 - short.docx` |
| **Phase I — 251106R (Base Element, WM 153)** | `samples/phase1_251106R_data.xlsx` | `samples/251106R - 15-20-049-10 W5M - Phase 1 ESA_Final_Secure-markup-upload.docx` (≤30 MB for app) |
| **Phase I — 260109R (Caltex Trilogy)** | `samples/phase1_260109R_data.xlsx` | `samples/260109R - 16-34-055-02W4M Phase 1 ESA_Final_Secure-markup-upload.docx` (≤30 MB for app) |
| Phase I — 260109R (full layout, CLI) | same Excel | `samples/260109R - 16-34-055-02W4M Phase 1 ESA_Final_Secure-markup.docx` |
| Phase II style | `samples/production_data.xlsx` | `samples/production_template.docx` |

### Phase 1 PDF → markup Word (new client templates)

Source PDFs in `samples/` are owner-encrypted with an **empty password** (requires `cryptography` in the venv). Convert and apply MVP Jinja tags (cover fields):

```powershell
pip install -r requirements.txt
$env:ESA_ALLOW_LARGE_TEMPLATE = "1"
python scripts\phase1_pdf_to_markup.py
python scripts\create_phase1_site_samples.py --ai-narratives
```

**AI + best practices (built into markup script):**

- MVP cover tags from PDF metadata (`client_name`, `uwi`, `company`, etc.)
- **AI template tagger** (`phase1_alberta` field allowlist from `schemas/report_profiles.json`)
- Writes `{pdf-stem}-tagging-guide.md` with suggestions and a Word checklist
- Flags: `--no-ai` (MVP only), `--suggest-only` (guide without auto-apply), `--no-llm` (rules only)
- **AI tab** in Streamlit: re-scan uploaded `-markup.docx` with Alberta Phase I profile selected

This writes `{pdf-stem}.docx`, `{pdf-stem}-markup.docx`, and per-site Excel workbooks. Re-run with `--skip-convert` after the first conversion.

**Large PDFs (e.g. 251106R ~44 MB):** Full conversion can hang on “Analyzing document”. Use a page limit for MVP markup (cover + executive summary):

```powershell
python scripts\phase1_pdf_to_markup.py "samples\251106R - 15-20-049-10 W5M - Phase 1 ESA_Final_Secure.pdf" --max-pages 20
```

PDFs over 25 MB auto-use 20 pages when `--max-pages` is omitted.

**Streamlit (30 MB cap):** Upload **`*-markup-upload.docx`**, not the full `*-markup.docx` or PDF:

```powershell
python scripts\phase1_pdf_to_markup.py --for-streamlit
```

This converts only enough pages (typically 12) to stay under 30 MB. Full-layout `*-markup.docx` files are for CLI only (`ESA_ALLOW_LARGE_TEMPLATE=1`).

**251106R PDF (~44 MB):** Too large for PDF upload in the app; always use the markup `.docx` from the script.

E2E both sites:

```powershell
$env:ESA_ALLOW_LARGE_TEMPLATE = "1"
python scripts\phase1_site_e2e.py
```

Or per site:

```powershell
python scripts\test_with_your_documents.py --excel samples\phase1_260109R_data.xlsx --template "samples\260109R - 16-34-055-02W4M Phase 1 ESA_Final_Secure-markup.docx" --out out\phase1_260109R_rendered.docx
```

### CLI

```powershell
python scripts\test_with_your_documents.py
```

Or explicitly:

```powershell
python scripts\render_cli.py --excel samples\phase1_alberta_data.xlsx --template samples\phase1_alberta_template.docx --phase "Phase 1" --prepared-by "Your Name" --out out\test_phase1.docx
```

Open the output `.docx` in Word.

### Streamlit

```powershell
streamlit run app.py
```

1. Open http://localhost:8501
2. Sidebar: **Phase 1**, **Prepared by**, date
3. Upload `samples/phase1_alberta_data.xlsx` and `samples/phase1_alberta_template.docx` (or use sidebar downloads, then re-upload)
4. **Report generation** → pre-flight → **Preview data (dry run)** → **Generate Report** → download

---

## Path B — Your own Excel + Word

### Step 1 — Prepare Excel

**Required sheet:** `ProjectData` (exact name)

| Row | Content |
|-----|---------|
| 1 | Headers → Jinja keys (`Site Name` → `site_name`) |
| 2 | **Only row used** for the report |

**Phase 1:** `LabResults` not required. Optional: `DrillingWaste`, `StorageTanks`.

**Phase 2:** `LabResults` required.

Copy and edit:

```powershell
python scripts\prepare_user_test_pack.py
```

Then edit `user_test/my_project_data.xlsx` row 2 (keep sheet names). Set `consultant_name` and `company` to **Ecoventure Inc.**

See [03-excel-data-guide.md](03-excel-data-guide.md).

### Step 2 — Prepare Word template

Use Jinja tags matching Excel headers:

```jinja2
{{ client_name }}
{{ well_name }}
{{ uwi }}
{{ executive_summary }}
{{ prepared_by }}
{{ date_of_issue }}
```

Table loops — [JINJA2_CHEATSHEET.txt](../JINJA2_CHEATSHEET.txt):

| Sheet | Word loop |
|-------|-----------|
| `LabResults` | `{%tr for item in lab_results %}` … `{%tr endfor %}` |
| `DrillingWaste` | `{%tr for item in drilling_waste %}` |
| `StorageTanks` | `{%tr for item in storage_tanks %}` |

Start from `user_test/my_template.docx` (copy of the Alberta sample) or tag your own `.docx`.

List tags:

```powershell
python scripts\inventory_template.py user_test\my_template.docx
```

### Step 3 — Align tags

Every `{{ variable }}` in Word needs a value from Excel row 2 or the sidebar. Sidebar overrides Excel on name collision.

### Step 4 — Test in the app

| Step | Action |
|------|--------|
| 1 | Upload your Excel + template |
| 2 | **Analyze uploaded Word template** |
| 3 | **Pre-flight checks** — fix red errors before generate |
| 4 | **Download missing-fields checklist** if needed |
| 5 | **Preview data (dry run)** |
| 6 | **Generate Report** → download `.docx` + manifest |

### Step 5 — CLI on your files

```powershell
python scripts\test_with_your_documents.py --excel user_test\my_project_data.xlsx --template user_test\my_template.docx --phase "Phase 1"
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Generate disabled | Fix pre-flight **errors** (sheet names, invalid files) |
| Blank fields | Match Excel headers to `{{ tags }}`; see **Missing** in pre-flight |
| Template render failed | Re-type split Jinja tags in one Word run |
| Lab header repeats | Static header row above `{%tr for item in lab_results %}` |
| Wrong consultant | `consultant_name` / `company` = Ecoventure Inc. |

---

## Related

- [02-user-guide.md](02-user-guide.md)
- [11-alberta-phase1-esa.md](11-alberta-phase1-esa.md)
- [08-testing.md](08-testing.md)
