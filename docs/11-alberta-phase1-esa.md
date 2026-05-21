# 11 — Alberta oil & gas Phase I ESA (Ecoventure)

Primary use case for this tool: **Alberta upstream oil and gas Phase I Environmental Site Assessments**, prepared by **Ecoventure Inc.**, aligned with AER **Schedule Two** / reclamation certificate Phase 1 ESA workflows.

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

- **`DrillingWaste`** — mud type, volume (m³), disposal method, location → `drilling_waste` loop in Word.
- **`StorageTanks`** — tank type, content, location, capacity → `storage_tanks` loop.

Do **not** require **`LabResults`** when sidebar **Report phase** is **Phase 1**.

## Word template

`phase1_alberta_template.docx` (generated sample) includes:

1. Cover — prepared for / **prepared by Ecoventure Inc.** / UWI / QP names / date  
2. **Executive summary** — `{{ executive_summary }}` (Signum Consulting–style multi-paragraph structure; Ecoventure voice). If blank in Excel, the engine auto-generates from ProjectData fields (`spud_date`, `drilling_waste_summary`, `air_photo_observations`, etc.).  
3. AER Schedule Two highlights — drilling, production, site visit, conclusions (scalar tags)  
4. Table loops for drilling waste and storage tanks  
5. Static appendix list (A–F) — attach PDFs separately in deliverable package  

## Workflow

1. Sidebar: **Phase 1**, **Prepared by**, date, template version.  
2. Upload `phase1_alberta_data.xlsx` + `phase1_alberta_template.docx` (or your Ecoventure `.docx`).  
3. Pre-flight → dry run → **Generate Report**.  
4. Append client-specific appendix PDFs (air photos, ABADATA, land title) outside the merge engine.

## Commands

```powershell
python scripts\create_samples.py
python scripts\render_cli.py --excel samples\phase1_alberta_data.xlsx --template samples\phase1_alberta_template.docx --phase "Phase 1" --out samples\phase1_alberta_rendered.docx
```

## Related

- [03-excel-data-guide.md](03-excel-data-guide.md)  
- [04-template-authoring.md](04-template-authoring.md)  
- [09-ai-assistant.md](09-ai-assistant.md) — Phase 1 narrative drafts (Alberta/AER tone when RAG loaded)  
