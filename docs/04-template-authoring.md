# 04 — Word template authoring

Word templates are ordinary `.docx` files with **Jinja2** syntax interpreted by [docxtpl](https://docxtpl.readthedocs.io/). Authors maintain templates; the engine supplies data from Excel and the sidebar.

## Supported template formats

| Format | Upload | Merge behavior |
|--------|--------|----------------|
| **.docx** | Yes | Direct merge with docxtpl (preferred) |
| **.pdf** | Yes | Converted to .docx on upload, then merge |

PDF conversion preserves layout approximately; **Jinja2 tags are not created automatically**. Open the converted file in Word, add `{{ fields }}` and table loops, save as `.docx`, and re-upload—or tag before export to PDF.

Maximum template size: 30 MB (see [07-security-and-deployment.md](07-security-and-deployment.md)).

## Principles

1. **One tag, one run** — Type each `{{ variable }}` without applying bold/italic/color in the middle of the tag. Split runs are the #1 render failure (pre-flight lints these).
2. **Static table headers** — Header row is normal Word text; only data rows use `{%tr %}` loops.
3. **Match Excel keys** — Root placeholders use snake_case matching normalized Excel headers.
4. **Version templates** — Record **Template version** in the app sidebar; store `.docx` templates in Git, not rendered client files.

## Scalar placeholders

Replace static text with:

```jinja2
{{ site_name }}
{{ client_name }}
{{ prepared_by }}
{{ date_of_issue }}
```

Production bracket placeholders (from full merge documents):

| Bracket (legacy) | Jinja tag |
|------------------|-----------|
| `[Company]` | `{{ company }}` |
| `[Company Address]` | `{{ company_address }}` |
| `[Keywords]` | `{{ keywords }}` |
| `[LAB]` | `{{ lab_name }}` |
| Client Full Name (text) | `{{ client_full_name }}` or `{{ client_name }}` |

Automated tagging when merge file exists:

```powershell
python scripts\tag_production_template.py --source "22xxxxR Phase 2 ESA Full_merge.docx" --out samples\production_template.docx
```

Without the merge file, the script generates `samples/production_template.docx` from the field guide.

## Laboratory results table (docxtpl)

Use a **4-row pattern** in one table:

| Row | Content |
|-----|---------|
| 1 | Static headers: Analyte \| Result \| Unit \| Exceedance |
| 2 (merged) | `{%tr for item in lab_results %}` |
| 3 | `{{ item.analyte }}` \| `{{ item.result_display }}` \| `{{ item.unit }}` \| `{{ item.exceedance_flag }}` |
| 4 (merged) | `{%tr endfor %}` |

In Word: merge cells on row 2 and 4 across columns so loop tags sit in one cell.

**Important:** Do not put column headers inside the loop row — they will repeat per analyte.

### RichText exceedances

- `{{ item.result_display }}` — Bold red when exceedance (engine sets RichText).
- `{{ item.result_plain }}` — Always plain text.

## Conditionals and loops (non-table)

```jinja2
{% if show_appendix %}
Appendix content here.
{% endif %}

{% for note in notes %}
{{ note }}
{% endfor %}
```

Only use variables present in Excel, sidebar, or added by custom engine changes.

## Multiple-choice phrases

Consultants can insert **one of several standard paragraphs** into a tagged slot. The engine resolves the chosen text into a single context key (e.g. `{{ drilling_waste_intro }}`). Three supported patterns:

### Approach A — Excel column holds the final text (no extra code)

1. Tag the Word slot: `{{ drilling_waste_summary }}` or a dedicated key `{{ drilling_waste_intro }}`.
2. In `ProjectData` row 2, paste the **full paragraph** the QP selected.
3. Generate.

Use when each project needs custom wording or phrases are maintained in a shared Excel cheat sheet.

### Approach B — Excel `PhraseCatalog` sheet + selection column

**Sheet `PhraseCatalog`** (optional):

| phrase_key | option_id | text |
|------------|-----------|------|
| `drilling_waste_intro` | `option_1_aer` | Full paragraph A… |
| `drilling_waste_intro` | `option_2` | Full paragraph B… |

**`ProjectData`** row 2 includes selection columns:

| drilling_waste_intro_selected | site_recon_intro_selected |
|-----------------------------|---------------------------|
| `option_1_aer` | `not_completed` |

The engine sets `{{ drilling_waste_intro }}` from the catalog. Sample workbook includes this sheet (run `python scripts\create_samples.py`).

Definitions are also in [`schemas/phrase_catalog.json`](../schemas/phrase_catalog.json).

### Approach C — Streamlit “Standard phrases” pickers

On the **Report generation** tab, use the **Standard phrases** selectboxes (from `phrase_catalog.json`). Choices override Excel for the same keys and are merged into the report like sidebar fields.

Pre-flight may warn if a phrase `option_id` in Excel does not match the catalog.

### Approach D — Fixed variants in Word (`{% if %}`)

Keep all variants in the template; Excel only stores a **flag** that must match the `{% if %}` test exactly:

```jinja2
{% if aer_waste_compliance_option == "Option 1 (AER, 2014)" %}
Drilling waste was disposed of via LWD to the well centre...
{% elif aer_waste_compliance_option == "Option 2" %}
Alternative paragraph text.
{% else %}
Not applicable.
{% endif %}
```

Alberta Phase I samples already use `aer_waste_compliance_option` this way. Prefer **one** `{{ paragraph_key }}` when you have long text; use `{% if %}` only for short branches.

### Tips

- Type each `{{ tag }}` and `{% if %}` in **one** Word formatting run.
- Sidebar **Override executive summary** is the same pattern for a single long field.
- See [03-excel-data-guide.md](03-excel-data-guide.md) for sheet names.

## Jinja filters (optional)

```jinja2
{{ value | default("N/A") }}
{{ text | upper }}
```

## Template inventory

List all tags in a document:

```powershell
python scripts\inventory_template.py path\to\template.docx
```

Or use **Analyze uploaded Word template** in the Streamlit app.

## Production template files

| File | Role |
|------|------|
| `22xxxxR Phase 2 ESA Full_merge.docx` | Full client report (local, gitignored) — tag manually or via `tag_production_template.py` |
| `samples/production_template.docx` | Committed tagged reference with guide fields + lab table |
| `samples/production_starter_template.docx` | Minimal tagged starter for learning |
| `samples/sample_template.docx` | Demo template |

See [../PRODUCTION_TEMPLATE_GUIDE.txt](../PRODUCTION_TEMPLATE_GUIDE.txt).

## Authoring workflow for full reports

1. Copy production merge `.docx` to a working copy.
2. Replace bracket placeholders and static labels with `{{ tags }}` per mapping table above.
3. Identify lab summary table → apply `{%tr for item in lab_results %}` pattern.
4. Run `inventory_template.py` — compare to `production_data.xlsx` columns.
5. Upload in app → pre-flight → dry run → generate test PDF from Word if required.
6. Bump template version in sidebar; archive manifest with deliverable.

## Common failures

| Failure | Cause | Fix |
|---------|-------|-----|
| `Template rendering failed` | Syntax error, split tag, invalid `{%tr %}` | Pre-flight split lint; re-type tags |
| Blank `{{ field }}` | Key not in Excel/sidebar | Add column or fix spelling |
| `lab_results` undefined | Phase 2 template but Phase 1 data | Add sheet or use Phase 1 |
| Table duplicates headers | Header inside loop | Move headers above `{%tr for %}` |
| Red text missing | Wrong placeholder | Use `result_display` |

## docxtpl resources

- Documentation: https://docxtpl.readthedocs.io/
- Table rows: search docs for `{%tr` tag
- Quick syntax: [../JINJA2_CHEATSHEET.txt](../JINJA2_CHEATSHEET.txt)

## Trust model

Templates contain Jinja2 logic (loops, conditionals). Treat `.docx` templates as **trusted author code**. Only staff who may edit report layouts should hold template write access.
