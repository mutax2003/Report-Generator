# 11 — Alberta oil & gas Phase I ESA (Ecoventure)

Primary use case for this tool: **Alberta upstream oil and gas Phase I Environmental Site Assessments**, prepared by **Ecoventure Inc.**, aligned with **AER SED 002 Section 10** and reclamation certificate Phase 1 ESA workflows. See [20-aer-sed002-phase1-esa.md](20-aer-sed002-phase1-esa.md).

## Reference structure

See [samples/phase1_alberta_inventory.md](../samples/phase1_alberta_inventory.md) (derived from a Devon 2017 Signum-style report; **committed samples use Ecoventure branding** and anonymized client names).

## Consultant of record

| Item | Standard value |
|------|----------------|
| Preparing firm | **Ecoventure Inc.** |
| `consultant_name` / `company` in Excel | Ecoventure Inc. |
| Sidebar **Prepared by** | Ecoventure qualified person |

Client name, UWI, and well identifiers come from project Excel data per engagement.

## Excel workbook (Phase 1)

### Required

- **`ProjectData`** — row 1 headers, row 2 values (see inventory for Alberta O&G fields).

### Optional (no lab sheet for Phase 1)

- **`DrillingWaste`** — mud type, volume (m³), disposal method, location, disposal type, GPS, sump dimensions, manifests → `drilling_waste` loop in Word.
- **`StorageTanks`** — tank type, content, location, capacity → `storage_tanks` loop.
- **`ReportConfig`** — key/value rows to override profile or sheet mappings (see [13-flexible-report-profiles.md](13-flexible-report-profiles.md)).

Do **not** require **`LabResults`** when sidebar **Report phase** is **Phase 1**. Sidebar **Profile** should be **Alberta Phase I ESA (Ecoventure)** (`phase1_alberta`).

## Word template

`phase1_alberta_template.docx` (generated sample) includes:

1. Cover — prepared for / **prepared by Ecoventure Inc.** / UWI / QP names / date  
2. **Executive summary** — `{{ executive_summary }}` (Signum Consulting–style multi-paragraph structure; Ecoventure voice). If blank in Excel, the engine auto-generates from ProjectData fields. Override in sidebar **Override executive summary** before generate.  
3. **SED 002 §10** sections (10.1–10.8) — asset, drilling, waste, production, site visit, records, interviews  
4. Table loops for drilling waste and storage tanks  
5. Appendices **A–H** — **D** and **G** auto-generated as `.docx` from DrillingWaste data; other appendices uploaded as PDFs in the app; **onestop/** summary JSON in deliverable zip  

## Workflow

1. Sidebar: **Phase 1**, profile **Alberta Phase I ESA**, **Prepared by**, date, template version.  
2. Upload `phase1_alberta_data.xlsx` + `phase1_alberta_template.docx` (or `.pdf` layout reference—convert and tag in Word if needed).  
3. Pre-flight → optional dry run → **Generate Report**.  
4. Review auto-generated appendices **D** (checklist) and **G** (calc tables) in step 4 downloads; upload other appendix PDFs **A–C, E–F, H** (ABADATA, air photos, land title, site sketch, etc.) under **Optional tools**.  
5. Review **SED 002 §10** completeness in pre-flight; download QP checklist if needed.  
6. Download **Report (.docx)**, **manifest JSON**, and **deliverable package (.zip)** (includes generated appendices and `onestop/` summary for OneStop).

Export generated appendix `.docx` files to PDF in Word before OneStop submission. Combined **Final_Report.pdf** (Word + appendices in one file) is not merged in-app.

## Commands

```powershell
python scripts\create_samples.py
python scripts\render_cli.py --excel samples\phase1_alberta_data.xlsx --template samples\phase1_alberta_template.docx --phase "Phase 1" --out samples\phase1_alberta_rendered.docx
```

## Related

- [00-start-here.md](00-start-here.md) — consultant quick path  
- [03-excel-data-guide.md](03-excel-data-guide.md)  
- [04-template-authoring.md](04-template-authoring.md)  
- [09-ai-assistant.md](09-ai-assistant.md) — Phase 1 narrative drafts (Alberta/AER tone when RAG loaded)  
- [13-flexible-report-profiles.md](13-flexible-report-profiles.md)  
- [20-aer-sed002-phase1-esa.md](20-aer-sed002-phase1-esa.md) — SED 002 checklist and OneStop export  
