# 19 — Charts and GIS figures in Word reports

The merge engine fills **text and tables** from Excel. **Hydrographs, plume maps, and cross-sections** are usually prepared in specialist tools, then referenced in the report.

## Recommended workflow (Ecoventure)

```mermaid
flowchart LR
  data[Excel monitoring data]
  pbi[Power BI or Excel chart]
  gis[QGIS or ArcGIS]
  png[Export PNG]
  word[Word template path or paste]
  app[Report Generator merge]
  data --> pbi
  data --> gis
  pbi --> png
  gis --> png
  png --> word
  word --> app
```

### 1. Hydrographs (water levels or analyte trends)

| Step | Tool | Action |
|------|------|--------|
| 1 | Excel `WaterLevels` / `GroundwaterLab` | Source data |
| 2 | **Power BI** or Excel | Build line chart per well or parameter |
| 3 | Export | **PNG** (300 dpi for print) |
| 4 | Project SharePoint | Store `Figures/Site_GW_hydrograph_v2.1.png` |
| 5 | `ProjectData` | Set `hydrograph_image_path` to file name or full path |
| 6 | Word template | Placeholder paragraph: `Figure: {{ hydrograph_image_path }}` **or** paste image manually before final merge |

**Note:** Native `InlineImage` in docxtpl is not enabled in this repo yet. Authors typically **paste the PNG in Word** after merge, or keep the path in the report for the document team.

### 2. Site plans and plume maps

| Step | Tool | Action |
|------|------|--------|
| 1 | **QGIS** / ArcGIS | Well locations, plumes, site boundary |
| 2 | Export layout | PNG or PDF appendix |
| 3 | `ProjectData` | `site_map_image_path` |
| 4 | Deliverable zip | Optional appendix PDF via appendices A–F uploader ([02-user-guide.md](02-user-guide.md)) |

### 3. Reclamation / Phase I figures

Air photos and survey plans often stay as **appendix PDFs** (Alberta Phase I appendices A–F) rather than inline merge fields.

## Version control

- Include figure version in filename: `GW_hydrograph_MW1-2_v2.1.png`
- Match `template_version` in the app sidebar
- Archive figures next to the generation manifest JSON on SharePoint

## What not to do

- Do not embed live Power BI links in client PDF exports without IT approval
- Do not commit large PNG/PDF figures to the public GitHub repo (use SharePoint)

## Future enhancement (optional)

If the team needs automated figure embed, a small extension could read `hydrograph_image_path` from Excel and inject `docxtpl.InlineImage` in `engine.py` — only when the file exists on the server path.

## Related

- [18-groundwater-reports.md](18-groundwater-reports.md)
- [BEST_PRACTICES.md](../BEST_PRACTICES.md)
