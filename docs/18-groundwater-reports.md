# 18 — Groundwater monitoring reports (Ecoventure)

Profile ID: **`groundwater_monitoring`** in [`schemas/report_profiles.json`](../schemas/report_profiles.json).

## When to use

- Annual or event groundwater monitoring at wellsites
- Baseline or compliance programs with monitoring wells, water levels, and laboratory COAs
- Reports that share analytical tables with Phase III / remediation (same `GroundwaterLab` sheet design)

## Sample files

```powershell
python scripts\create_samples.py
```

| File | Purpose |
|------|---------|
| `samples/groundwater_monitoring_data.xlsx` | Example workbook |
| `samples/groundwater_monitoring_template.docx` | Tagged Word template |

In Streamlit: sidebar **Profile** → **Groundwater monitoring (Ecoventure)**.

## Excel layout

### ProjectData (row 1 = headers, row 2+ = sites for batch)

| Column | Tag | Notes |
|--------|-----|--------|
| Site Name | `site_name` | |
| Client Name | `client_name` | |
| Project Number | `project_number` | |
| Monitoring Program | `monitoring_program` | e.g. annual compliance |
| Executive Summary | `executive_summary` | Leave blank for auto-draft |
| Hydrogeologic Setting | `hydrogeologic_setting` | Or use narrative AI tab |
| Hydrograph Image Path | `hydrograph_image_path` | Path or filename for figure embed — see [19-charts-and-gis-embed.md](19-charts-and-gis-embed.md) |
| Site Map Image Path | `site_map_image_path` | GIS / plan map PNG |

### MonitoringWells → `monitoring_wells`

| Column | Item field |
|--------|------------|
| Well ID | `well_id` |
| Easting / Northing | `easting`, `northing` |
| Screen top / bottom (m) | `screen_top_m`, `screen_bottom_m` |

### WaterLevels → `water_levels`

| Column | Item field |
|--------|------------|
| Well ID | `well_id` |
| Measurement Date | `measurement_date` |
| Depth to water (m) | `depth_to_water_m` |
| Water level (m asl) | `water_level_masl` |

### GroundwaterLab → `groundwater_results`

Uses the same exceedance styling as Phase II lab tables (`result_display` bold red when exceeded).

| Column | Notes |
|--------|--------|
| Well ID | Link to well network |
| Sample Date | `sample_date` |
| Analyte, Result, Unit | |
| Tier1 Limit / Background Limit | Mapped to criteria for exceedance |
| Exceedance | Y/N |

### FieldNotes → `field_events` (optional)

Purge volumes, field observations per well and date.

### PhraseCatalog / Standard phrases

Optional phrases: `gw_program_intro`, `gw_sampling_methods`, `gw_data_usability`, `gw_recommendations` — see [`schemas/phrase_catalog.json`](../schemas/phrase_catalog.json).

## Word template loops

```jinja2
{%tr for item in monitoring_wells %}
{{ item.well_id }} | {{ item.screen_top_m }} | ...
{%tr endfor %}
```

```jinja2
{%tr for item in groundwater_results %}
{{ item.analyte }} | {{ item.result_display }} | {{ item.exceedance_flag }}
{%tr endfor %}
```

## Auto-computed context fields

When `executive_summary` is empty, the engine may auto-fill from [`groundwater_narrative.py`](../groundwater_narrative.py):

- `well_count`, `monitoring_event_count`, `exceedance_summary`, `data_gap_note`

## AI assistant (Report → AI tab)

| Tool | Use |
|------|-----|
| Lab PDF → **GroundwaterLab** | Import COA PDF rows |
| Well log PDF → **MonitoringWells** | Extract MW-/BH- IDs from construction logs |
| Groundwater trend notes | Well ID cross-checks and % change notes |
| Narrative drafts | RAG from `rag_corpus/groundwater_*.txt` |

## Related

- [03-excel-data-guide.md](03-excel-data-guide.md) — batch rows, site linking
- [04-template-authoring.md](04-template-authoring.md) — phrases A–D
- [19-charts-and-gis-embed.md](19-charts-and-gis-embed.md) — hydrographs and maps
- [11-alberta-phase1-esa.md](11-alberta-phase1-esa.md) — reclamation / Schedule Two overlap
