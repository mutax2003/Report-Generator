# 10 — Glossary and FAQ

## Glossary

| Term | Definition |
|------|------------|
| **Context** | Python dict passed to Jinja2: ProjectData fields + sidebar + `lab_results` list |
| **docxtpl** | Library that renders Jinja2 inside Word `.docx` files |
| **Dry run** | Build context and manifest without creating Word output |
| **Report profile** | `phase1_alberta`, `phase2_esa`, `template_driven` — sheet mapping and recommended fields in `schemas/report_profiles.json` |
| **Field contract** | Legacy reference in `schemas/field_contract.json`; pre-flight warnings use **report profiles** first |
| **Generation manifest** | JSON audit file with SHA-256 hashes and tag statistics |
| **Jinja2** | Template language: `{{ var }}`, `{% if %}`, `{% for %}` |
| **LabResults** | Required Excel sheet name for Phase 2 lab data |
| **Merge** | Combining template + data into one `.docx` |
| **Pre-flight** | Validation before render: sheets, tags, split-run lint |
| **ProjectData** | Required Excel sheet for project-level fields |
| **RichText** | docxtpl formatted text (bold red exceedances) |
| **`{%tr %}`** | docxtpl table-row loop tag for repeating lab rows |
| **Root variable** | Top-level `{{ name }}` without dots (e.g. `site_name`, not `item.x`) |
| **Split tag** | Jinja split across multiple Word XML runs — breaks render |
| **Sidebar meta** | User inputs: prepared by, date, phase, template version |

### Consultant terms (also in-app Glossary)

These match the **Glossary** expander on the Report tab ([`ui/onboarding.py`](../ui/onboarding.py)):

| Term | Definition |
|------|------------|
| **OneStop** | Alberta Energy Regulator (AER) online portal for submitting Phase I ESA reports and supporting documents |
| **SED 002** | AER Standard for Environmental Due Diligence — Section 10 checklist items for QP sign-off on Phase I |
| **DWDA** | Drilling Waste Disposal Area — compliance with Directive 050 for on-lease drilling waste and cuttings |
| **Deliverable package** | ZIP with Word report, manifest JSON, appendices folder, and OneStop export summary — primary download in the app |

See also [21-dwda-directive-050-compliance.md](21-dwda-directive-050-compliance.md) and [20-aer-sed002-phase1-esa.md](20-aer-sed002-phase1-esa.md).

## Frequently asked questions

### General

**Q: What file types are supported?**  
A: Input: `.xlsx` and `.docx`. Output: `.docx` only.

**Q: Can I generate PDF directly?**  
A: No. Open the `.docx` in Word and export to PDF if needed.

**Q: Can one Excel file produce multiple reports?**  
A: Yes. Put one site per row on `ProjectData` (row 1 = headers). In Streamlit choose **All N sites (batch zip)** or use `python scripts\render_cli.py --all-rows`. Optional: add `site_name` or `project_number` on `LabResults` / `DrillingWaste` rows to link table data per site.

**Q: Phase 1 vs Phase 2?**  
A: Phase 2 requires `LabResults`. Phase 1 does not.

### Excel

**Q: Why is my sheet ignored?**  
A: Sheet must be named exactly `ProjectData` or `LabResults`.

**Q: Column header `Site Name` — what tag in Word?**  
A: `{{ site_name }}` (normalized).

**Q: Extra columns in LabResults?**  
A: Passed through as `{{ item.column_name }}` in loops if you add placeholders.

### Word templates

**Q: Render failed but tags look correct?**  
A: Likely split runs. Re-type each `{{ tag }}` without formatting breaks. Check pre-flight split lint.

**Q: Lab table shows headers on every row?**  
A: Move headers outside the `{%tr for item in lab_results %}` row.

**Q: How do I tag a 200-page report?**  
A: Incrementally replace static/bracket text; use `tag_production_template.py` for brackets; use production starter as reference for lab table.

### Application

**Q: Missing variable warning but I want blank?**  
A: Warnings are OK — field renders empty. Fix warnings for production reports.

**Q: Where is the audit JSON?**  
A: Download after generate, or `{output_stem}_manifest.json` from CLI.

**Q: Can I run without Streamlit?**  
A: Yes — `scripts/render_cli.py`, `automate.render`, or HTTP server. See [06-api-reference.md](06-api-reference.md).

### Security

**Q: Is it safe to expose on the internet?**  
A: No for default config. Use localhost or secured internal network. See [07-security-and-deployment.md](07-security-and-deployment.md).

**Q: Are templates safe from users?**  
A: Upload Excel is untrusted (validated). Templates are trusted author code.

### AI

**Q: Does AI change my report automatically?**  
A: No for merge. AI suggests text/files for you to review and upload manually.

**Q: Work without internet?**  
A: Yes — disable cloud LLM; offline fallbacks run.

## Getting help

| Issue type | Resource |
|------------|----------|
| Excel structure | [03-excel-data-guide.md](03-excel-data-guide.md) |
| Word tags | [04-template-authoring.md](04-template-authoring.md) |
| Streamlit steps | [02-user-guide.md](02-user-guide.md) |
| Code / API | [05-developer-guide.md](05-developer-guide.md), [06-api-reference.md](06-api-reference.md) |
| Errors in CI | [08-testing.md](08-testing.md) |
