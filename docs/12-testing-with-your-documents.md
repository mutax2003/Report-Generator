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
| Phase II style | `samples/production_data.xlsx` | `samples/production_template.docx` |

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
