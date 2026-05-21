# 13 — Flexible report types (profiles)

Generate **different report types** from the same engine by combining:

1. **Word template** — `{{ field }}` markups and `{%tr for item in table_var %}` table loops  
2. **Excel workbook** — scalar fields on a primary sheet + optional table sheets  
3. **Report profile** — rules for which sheets map to which template variables  

## Report profiles (sidebar)

| Profile ID | Use when |
|------------|----------|
| `phase1_alberta` | Alberta Phase I ESA (Ecoventure); `DrillingWaste`, `StorageTanks` optional |
| `phase2_esa` | Phase II with required `LabResults` / `lab_results` loop |
| `template_driven` | **Your** template + Excel: auto-map sheets to loop variables |

Catalog: [`schemas/report_profiles.json`](../schemas/report_profiles.json)

## Excel layout

### Primary sheet (default `ProjectData`)

- Row 1: headers → Jinja keys (`Site Name` → `site_name`)  
- Row 2: values used for the report  

### Table sheets

Any extra sheet can feed a **list** in Word:

| Excel sheet | Word loop |
|-------------|-----------|
| `LabResults` | `{%tr for item in lab_results %}` |
| `Observations` | `{%tr for item in observations %}` (if template uses that loop name) |

With **template_driven**, sheet `Observations` maps to context key `observations` when the template loops `observations`.

### Optional `ReportConfig` sheet

Two columns: **key** | **value** (headers in row 1).

| Key | Example value |
|-----|----------------|
| `report_type` | `template_driven` |
| `primary_sheet` | `ProjectData` |
| `map_LabResults` | `lab_results` |
| `map_Observations` | `observations` |

`map_<SheetName>` sets Excel sheet → template loop variable.

## Workflow

1. Sidebar: choose **Profile** (or set `report_type` in `ReportConfig`).  
2. Upload Excel + tagged Word template.  
3. Pre-flight shows report type, matched tags, and **table row counts** per loop.  
4. Generate — missing scalar tags warn and render empty; missing table data yields empty tables.  

## Custom demo pair

```powershell
python scripts\create_samples.py
```

- `samples/custom_demo_data.xlsx` — `ProjectData` + `Observations` + `ReportConfig`  
- `samples/custom_demo_template.docx` — `{{ report_title }}` + `observations` table loop  

```powershell
python scripts\render_cli.py --excel samples\custom_demo_data.xlsx --template samples\custom_demo_template.docx --phase "Phase 1" --out out\custom.docx
```

Set sidebar/profile to **Custom — match template tags to Excel sheets**.

## Adding a new built-in profile

Edit [`schemas/report_profiles.json`](../schemas/report_profiles.json): define `sheet_mappings`, `required_sheets`, and `default_phase`. No Python change required unless you add special lab exceedance handling for a new loop name (today only `lab_results` uses RichText exceedance logic).

## Related

- [03-excel-data-guide.md](03-excel-data-guide.md)  
- [04-template-authoring.md](04-template-authoring.md)  
- [12-testing-with-your-documents.md](12-testing-with-your-documents.md)  
