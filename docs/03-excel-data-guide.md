# 03 — Excel data guide

The merge engine reads structured data from an Excel workbook (`.xlsx`). This document defines sheet names, column conventions, normalization rules, and the published field contract.

## Workbook structure

### Required sheet names (exact)

| Sheet | Phase 1 | Phase 2 | Purpose |
|-------|---------|---------|---------|
| `ProjectData` | Required | Required | Single project record → flat template variables |
| `LabResults` | Optional | **Required** | One row per analyte → `lab_results` list in Jinja |
| `DrillingWaste` | Optional | Optional | One row per mud/disposal record → `drilling_waste` (Alberta Phase I) |
| `StorageTanks` | Optional | Optional | One row per tank → `storage_tanks` (Alberta Phase I) |
| `ReportConfig` | Optional | Optional | key/value overrides for profile and `map_SheetName` → loop variable |

Sheet names are **case-sensitive** and must match exactly (not “first sheet” or “Sheet1”).

Alberta Phase I detail: [11-alberta-phase1-esa.md](11-alberta-phase1-esa.md) · field list: [../samples/phase1_alberta_inventory.md](../samples/phase1_alberta_inventory.md).

### ProjectData layout

```
Row 1:  | site_name      | client_name    | project_number | ...
Row 2:  | 123 Example Rd | Demo Client    | ESA-2026-001   | ...
Row 3+: (ignored by engine)
```

- **Row 1** — Column headers (become Jinja keys after normalization).
- **Row 2** — **Only row used** for the report (single-report mode).
- **Row 3+** — Ignored. For multiple sites, run the tool multiple times or extend the engine (not supported in V1).

Empty `ProjectData` (headers only) produces a pre-flight / render error.

### LabResults layout

```
Row 1:  | Analyte  | Result | Unit  | Criteria | Exceedance |
Row 2:  | Benzene  | 0.8    | ug/L  | 5.0      | N          |
Row 3:  | TCE      | 12.5   | ug/L  | 5.0      | Y          |
```

Each data row becomes one element in `lab_results` for Word table loops.

### DrillingWaste layout (optional)

```
Row 1:  | mud_type   | volume_m3 | disposal_method | location |
Row 2+: | Surface    | 110       | LWD             | SW1/4... |
```

Each data row → `drilling_waste` list. Word loop: `{%tr for item in drilling_waste %}` … `{%tr endfor %}`.

Typical columns (any subset; extras pass through): `mud_type`, `volume_m3`, `disposal_method`, `location`.

### StorageTanks layout (optional)

```
Row 1:  | tank_type | content      | location | capacity_m3 |
Row 2+: | Production| Crude oil    | Berm     | 50          |
```

Each data row → `storage_tanks` list. Word loop: `{%tr for item in storage_tanks %}`.

## Header normalization

Headers are converted to context keys:

| Excel header | Context key |
|--------------|-------------|
| `Site Name` | `site_name` |
| `Client Name` | `client_name` |
| `PROJECT_NUMBER` | `project_number` |

Rules:

1. Trim whitespace.
2. Replace spaces with `_`.
3. Lowercase entire key.

Extra columns are passed through (string values) and available as `{{ column_name }}` if referenced in the template.

## Lab column aliases

The engine maps common header variants:

| Logical field | Accepted headers (normalized) |
|---------------|------------------------------|
| Analyte | `analyte`, `parameter`, `constituent` |
| Result | `result`, `value` |
| Unit | `unit`, `units` |
| Criteria | `criteria`, `standard`, `screening_level` |
| Exceedance flag | `exceedance`, `exceeds`, `flag` |

Every original column is also copied into each row dict under its normalized header name.

## Engine-computed lab fields

Each lab row dict always includes:

| Key | Description |
|-----|-------------|
| `analyte`, `result`, `unit`, `criteria` | From Excel (string) |
| `exceedance_flag` | `"Yes"` or `"No"` |
| `result_plain` | Result as plain string |
| `result_display` | Plain string, or **RichText** (bold red) when exceedance |

### Exceedance logic

Exceedance is **true** when either:

1. **Exceedance column** is truthy: `Y`, `Yes`, `TRUE`, `1`, `X`, `exceedance`, `exc` (case-insensitive), or
2. **Numeric compare** — both Result and Criteria parse as floats and `result > criteria`.

Use `{{ item.result_display }}` in Word tables for formatted exceedances; `{{ item.result_plain }}` for unformatted text.

## Sidebar merge behavior

Sidebar fields from the app are merged into the same context dict:

| Sidebar key | Typical use |
|-------------|-------------|
| `prepared_by` | Author |
| `date_of_issue` | ISO date string |
| `report_phase` | `Phase 1` / `Phase 2` |
| `report_type` | Profile id: `phase1_alberta`, `phase2_esa`, `template_driven` |
| `template_version` | Template semver for manifest |
| `executive_summary` | Optional override (sidebar) |

**Override rule:** If a sidebar key normalizes to the same name as an Excel column, **sidebar wins**.

### ReportConfig sheet (optional)

Two columns: **key**, **value** (row 1 headers). Examples:

| key | value |
|-----|-------|
| `report_type` | `template_driven` |
| `primary_sheet` | `ProjectData` |
| `map_LabResults` | `lab_results` |
| `map_Observations` | `observations` |

Excel `ReportConfig` overrides sidebar profile when `report_type` is set. Download a starter sheet from pre-flight. See [13-flexible-report-profiles.md](13-flexible-report-profiles.md).

## Field lists (profiles + legacy contract)

**Canonical recommended fields per report type:** [`schemas/report_profiles.json`](../schemas/report_profiles.json) → `recommended_fields` on each profile. Pre-flight warnings and missing-field checklists use these lists.

Legacy reference (AI tagger, older docs): [`schemas/field_contract.json`](../schemas/field_contract.json).

### Recommended fields — all phases

| Field | Description |
|-------|-------------|
| `site_name` | Site / project identifier line |
| `client_name` | Client legal or display name |
| `project_number` | Internal project code |
| `address` | Site or mailing address |
| `prepared_by` | Often from sidebar |
| `date_of_issue` | Often from sidebar |

### Additional recommended — Phase 2

| Field | Description |
|-------|-------------|
| `site_address` | Detailed site location |
| `report_title` | Report heading |
| `lab_name` | Analytical laboratory |
| `consultant_name` | Consulting firm contact |
| `company` | Company name (cover page) |

Empty recommended fields produce **warnings** only (generation still allowed).

## Sample workbooks

| File | Contents |
|------|----------|
| `samples/sample_data.xlsx` | Minimal demo project + 3 lab rows |
| `samples/phase1_alberta_data.xlsx` | Alberta Phase I — Ecoventure; `DrillingWaste` + `StorageTanks` |
| `samples/production_data.xlsx` | Fields aligned with production ESA template guide |

Regenerate:

```powershell
python scripts\create_samples.py
```

## Formula injection mitigation

Cell values starting with `=`, `+`, `-`, `@`, or tab are prefixed with `'` when converted to strings (reduces formula injection if Word tables are re-opened in Excel).

## Limits

| Limit | Value |
|-------|-------|
| Max lab rows | 10,000 (truncated with warning) |
| Max ProjectData columns | 300 |
| Max cell string length | 32,768 characters |
| Max Excel upload size | 15 MB |

See [07-security-and-deployment.md](07-security-and-deployment.md).

## Checklist for new projects

1. Copy `samples/production_data.xlsx` or build from contract fields.
2. Run app pre-flight with your template — download missing-fields checklist.
3. Fill row 2 of `ProjectData`; add all `LabResults` rows.
4. Dry-run preview — confirm `lab_row_count` and keys.
5. Generate and spot-check exceedance formatting in Word.

## Quick reference

See also [../EXCEL_LAYOUT.txt](../EXCEL_LAYOUT.txt).
