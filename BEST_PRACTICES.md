# Best practices (ESA Report Generator)

Full documentation: [docs/README.md](docs/README.md) · User workflow: [docs/02-user-guide.md](docs/02-user-guide.md)

Patterns adopted from **mail merge**, **legal/document automation**, and **docxtpl**-based tools (HotDocs-style separation of template vs data, Docassemble-style interviews + manifests, enterprise merge audit trails).

## 1. Separate template, data, and engine

| Layer | What to version | What not to version |
|--------|-----------------|---------------------|
| **Word template** | `.docx` with Jinja tags in Git | Rendered client deliverables |
| **Excel contract** | `samples/production_data.xlsx`, `schemas/report_profiles.json` | One-off client workbooks (unless archived per project) |
| **Engine** | `engine.py`, `security.py` | — |

Non-developers maintain Word design; developers maintain the merge engine. Same split as Word Mail Merge, Carbone, and docxtpl production setups.

## 2. Schema-first data (report profiles)

- Document recommended fields in **`schemas/report_profiles.json`** per profile (`phase1_alberta`, `phase2_esa`, `template_driven`). Update **`schemas/field_contract.json`** only if the AI tagger or legacy docs need the same names.
- List layout in [EXCEL_LAYOUT.txt](EXCEL_LAYOUT.txt).
- **Row 1** of `ProjectData` = headers → normalized keys (`Site Name` → `site_name`).
- **Row 2+** = one project per row; use batch mode in the app or `render_cli.py --all-rows` for multiple reports.
- Phase 2: require **`LabResults`** with analyte rows; loop in Word with `{%tr for item in lab_results %}`.

The app warns when **recommended** contract fields are empty; pre-flight warns when **template** tags lack Excel/sidebar values.

## 3. Pre-flight before every production run

Similar to “validate merge” in Word and QA gates in automation platforms:

1. Upload Excel + template.
2. Review **Pre-flight checks** (sheets, matched/missing tags, split-tag lint).
3. Optional **Preview data (dry run)** — builds context and manifest **without** rendering Word.
4. **Generate Report** only when hard errors are clear.

Missing template variables do **not** block generate (warning + blank), but split tags and invalid files **do** block.

## 4. Template authoring (Word)

- Type each `{{ variable }}` in **one** formatting run (no bold/color in the middle of a tag).
- Table: **static header row**, then loop row, then `{%tr endfor %}` — see [JINJA2_CHEATSHEET.txt](JINJA2_CHEATSHEET.txt).
- Use **`result_display`** in tables for exceedances (RichText); **`result_plain`** for plain text.
- **Semantic versioning**: set **Template version** in the sidebar (e.g. `2.1.0`) so manifests record which template was used.

## 5. Generation manifest (audit trail)

After generate (or dry-run preview), download **`_manifest.json`**:

- UTC timestamp, phase, prepared-by, template version  
- SHA-256 of Excel, template, and output  
- Tag match counts and missing variable list  

Store manifests with issued reports for reproducibility and disputes (common in regulated / legal automation).

CLI also writes a manifest next to the output:

```powershell
python scripts\render_cli.py --out samples\rendered_output.docx
# creates samples\rendered_output_manifest.json
```

## 6. Security (untrusted uploads)

Follow [README.md](README.md#security-and-limits): size caps, zip-bomb guards, sandboxed Jinja, formula-injection prefix in Excel cells, localhost deployment.

Templates are **trusted code** (Jinja can loop/logic). Only authors with template access should edit `.docx` files.

## 7. Testing workflow

```powershell
python -m unittest discover -s tests -v
python scripts\create_samples.py
python scripts\render_cli.py
```

Before changing a production template:

1. Run `python scripts\inventory_template.py your_template.docx`
2. Update `production_data.xlsx` columns
3. Dry-run in UI or CLI
4. Spot-check PDF export from Word if required for delivery

## 8. AI assistant (Tier 1 & 2)

See [AI_FEATURES.md](AI_FEATURES.md). Use **AI assistant** tab for template tagging, lab PDF import, narratives, copilot, and QA. Disable cloud LLM in the sidebar to stay fully offline.

## 9. Roadmap alignment (Power Automate / M365)

Keep **`ReportEngine`** free of Streamlit. Later automation passes `excel_bytes` + `template_bytes` and writes manifest to SharePoint/Dataverse — same as n8n/Carbone “headless merge” patterns.

## Quick reference

| Task | Where |
|------|--------|
| Field list / contract | `schemas/report_profiles.json` (canonical) |
| Tag inventory | Sidebar downloads + **Analyze uploaded Word template** |
| Missing columns checklist | Pre-flight → **Download missing-fields checklist** (profile-aware) |
| ReportConfig starter | Pre-flight → **Download ReportConfig sheet (Excel)** |
| Preview without Word | **Preview data (dry run)** |
| Provenance | **Download generation manifest (JSON)** |
| Deliverable zip | **Download deliverable package (.zip)** after generate |
