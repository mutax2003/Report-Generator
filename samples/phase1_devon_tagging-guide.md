# Devon 2017 Phase I — template pairing guide

| File | Role |
|------|------|
| `phase1_devon_data.xlsx` | Excel data (ProjectData, DrillingWaste, StorageTanks) |
| `phase1_devon_template.docx` | Word template tagged from Devon 2017 reference |

**Sidebar profile:** Alberta Phase I ESA (Ecoventure) (`phase1_alberta`)

## Jinja tags applied automatically

- `{{ client_name }}`
- `{{ consultant_name }}`
- `{{ executive_summary }}`
- `{{ qp_names }}`
- `{{ report_month_year }}`
- `{{ uwi }}`
- `{{ well_name }}`

## Manual follow-up in Word

- Verify cover `{{ well_name }}` (replaces `4-4-49-4` token only).
- Add `{%tr for item in drilling_waste %}` table rows if you extend AER tables.
- Run pre-flight in the app before client delivery.

## Source

Local reference: `00_04-04-049-04W4M Phase I report - Devon 2017.docx` (not committed if gitignored).