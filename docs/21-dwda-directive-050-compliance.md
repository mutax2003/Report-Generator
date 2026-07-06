# 21 — DWDA / AER Directive 050 compliance

How drilling waste disposal areas (DWDAs) are regulated in Alberta, **how results are calculated**, and how to **generate** preflight, narrative, appendices D/G, and OneStop fields in this tool.

## Authoritative sources (read in this order)

| Priority | Source | Role |
|----------|--------|------|
| 1 | [AER reclamation submissions](https://www.aer.ca/node/124) | Phase I must include drilling waste disposal assessment; official forms |
| 2 | [Assessing DWDA (ADWDA)](https://open.alberta.ca/publications/0778539806) | Option 1/2/3 pathways, Equivalent Salinity scope |
| 3 | [2010 Reclamation application guidelines](https://open.alberta.ca/dataset/7e64256c-42e2-4eb6-bed1-91a4e558b3e2/resource/cbbe4a4c-dc0e-4d4e-9bfb-c613618db61d/download/2011-2010-reclamation-criteria-wellsites-application-guidelines-2011-05.pdf) | LWD 50 m³ rule, partial Option 1 (§1.0–1.3), Phase II triggers |
| 4 | [AER Directive 050](https://www.aer.ca/regulations-and-compliance-enforcement/rules-and-regulations/directives/directive-050) | Operations: disposal, notifications, sampling |
| 5 | [Alberta Tier 1/2](https://open.alberta.ca/dataset/842becf6-dc0c-4cc7-8b29-e3f383133ddc) | Non-salinity COPCs + full lease outside DWDA |
| 6 | SED 002 §10.4 | Phase I report content — see [20-aer-sed002-phase1-esa.md](20-aer-sed002-phase1-esa.md) |

**Legal submission forms (not replaced by this tool):**

- AER **Drilling Waste Assessment Disposal Checklists [DOC]**
- **Drill Stem Test Return Calculations [XLS]** (Option 2 only)

Generated Appendix D is a **pre-filled companion**, not the official OneStop form.

**Critical rule:** Equivalent Salinity applies **only to salinity within the DWDA**. Hydrocarbons, metals, and other contaminants in the DWDA, and **all parameters outside the DWDA**, must meet Alberta Tier 1 or Tier 2.

---

## How to calculate DWDA results (regulatory logic)

Phase I does **not** run lab exceedance math — it documents disposal history and checklist completeness. QPs determine:

### Step 1 — Classify compliance option (`ProjectData`)

| Option | When | Tool field |
|--------|------|------------|
| Option 1 | Checklist-based (common LWD/on-lease sumps) | `aer_waste_compliance_option` → `option_1` |
| Option 2 | Calculation-based (DST returns XLS) | `option_2` |
| Option 3 | Alternative per ADWDA | `option_3` |
| Approved facility | All waste hauled off lease | `approved_facility` |
| No on-site waste | No disposal on lease | `no_on_site_waste` |

### Step 2 — Determine checklist scope (2010 guidelines)

| Scope | When |
|-------|------|
| `option_1_full` | LWD on lease and/or on-lease cuttings **>50 m³** |
| `option_1_minimal` | Off-lease disposal and **≤50 m³** on lease — ADWDA §1.0–1.3 only |
| `option_2` | Option 2 selected |
| `approved_facility` | Approved facility path |

The engine uses `cuttings_volume_on_lease_m3` from ProjectData, or **auto-sums** `DrillingWaste.volume_m3` for on-lease rows when that field is empty (`derive_cuttings_volume_on_lease_m3` in `dwda_compliance.py`).

### Step 3 — Checklist pass/fail

Each line in [`schemas/dwda_compliance_checklist.json`](../schemas/dwda_compliance_checklist.json) is evaluated by source:

| Source | Satisfied when |
|--------|----------------|
| `projectdata` | Field non-empty (e.g. `directive_050_notification_ref`) |
| `drilling_waste` | ≥1 disposal row |
| `drilling_waste_field` | GPS, depths, manifests on applicable rows |
| `appendix` | Label uploaded or auto-generated (D, G, H) |
| `dwda_checklist` | `DwdaChecklist` response Yes / N/A |

**Completeness %** = satisfied items ÷ applicable items for the current scope.

### Step 4 — Environmental limits (pathway only at Phase I)

| Zone / COPC | Guideline | Phase I field |
|-------------|-----------|---------------|
| Salinity inside DWDA | Equivalent Salinity | `dwda_salinity_pathway` = `equivalent_salinity` |
| Other COPCs inside DWDA | Tier 1/2 | Document only — no numeric engine |
| Outside DWDA | Tier 1/2 | Phase II lab-driven |

### Step 5 — Option 2 calculations

Use the official AER **DST Return Calculations [XLS]** outside this tool. The app sets scope `option_2` and renders Appendix G from `DrillingWaste` rows.

### Step 6 — Phase II trigger

Phase II when location unknown, required checklist incomplete, QP flags `dwda_phase2_required`, or SED/Phase I investigation triggers apply.

---

## Excel workbook — populate from records

### Records review → Excel

| Source document | ProjectData / sheet fields |
|-----------------|---------------------------|
| Directive 050 notification / tour report | `directive_050_notification_ref` |
| Waste manifests, haul tickets | `DrillingWaste.waste_manifest_refs`, `remote_cert_number` |
| Well file / drilling report | `DrillingWaste` rows (method, volume, location, GPS) |
| Compliance option from operator | `aer_waste_compliance_option` |
| Cuttings volume on lease | `cuttings_volume_on_lease_m3` (or leave blank to auto-sum on-lease rows) |
| QP checklist answers | `DwdaChecklist` sheet |

### ProjectData (recommended fields)

| Field | Purpose |
|-------|---------|
| `aer_waste_compliance_option` | Option 1, 2, 3, approved facility |
| `cuttings_volume_on_lease_m3` | LWD >50 m³ full Option 1 rule (auto-derived if blank) |
| `directive_050_notification_ref` | Notification / tour report reference |
| `dwda_salinity_pathway` | `equivalent_salinity`, `tier1`, `pending_phase2` |
| `dwda_phase2_required` | QP flag — syncs with `phase2_drilling_waste_required` |
| `drilling_waste_summary` | SED §10.4 narrative |

### DrillingWaste sheet

One row per disposal event: `disposal_type`, `gps_coordinates`, `sump_depth_m`, `cover_depth_m`, `remote_cert_number`, `waste_manifest_refs`. Optional: `dwda_id`, `area_m2`, `salinity_exceedance`.

### DwdaChecklist sheet

| Column | Values |
|--------|--------|
| `checklist_item_id` | e.g. `d050.notification` (see JSON schema) |
| `response` | Yes / No / N/A / Unknown |
| `notes` | QP comments |

---

## How to generate DWDA results (tool pipeline)

1. **Populate Excel** — ProjectData + DrillingWaste + optional DwdaChecklist (see above).
2. **Upload** Excel + Phase I template; profile **Alberta Phase I ESA**.
3. **Pre-flight** — open **DWDA / Directive 050** panel; note scope, completeness %, Phase II triggers.
4. **Download** **DWDA QP review checklist** (markdown) from preflight.
5. **Upload Appendix H** — site sketch with all on-lease disposal locations (GPS, sump/cover depths on sketch or in Excel).
6. **Generate Report** — main `.docx` plus auto appendices **D** (checklist companion) and **G** (calc table).
7. **Deliverable zip** — includes OneStop summary fields (`dwda_compliance_option`, `dwda_checklist_scope`, `cuttings_volume_on_lease_m3`, etc.) and **`qp_checklists/dwda_directive050_qp_checklist.md`** (same markdown as preflight download).
8. **OneStop** — complete official AER checklist DOC/XLS; export report PDF per [20-aer-sed002-phase1-esa.md](20-aer-sed002-phase1-esa.md).

### Generated context keys (Word templates)

| Key | Meaning |
|-----|---------|
| `dwda_checklist_scope` | `option_1_full`, `option_1_minimal`, etc. |
| `dwda_compliance_summary` | Scope + completeness % + guideline note |
| `dwda_checklist_results` | Rows for Appendix D table loop |
| `dwda_phase2_required` | Yes / No |
| `dwda_checklist_complete` | Yes / No |

### CLI verification

```powershell
python scripts\dwda_workflow_e2e.py
python scripts\phase1_alberta_e2e.py
```

Outputs under `out/dwda_workflow/`: QP checklist markdown, rendered report, deliverable zip, `onestop_summary.json`.

---

### Ecoventure workbook (hybrid workflow)

1. Download the Ecoventure **xltm** from preflight or `templates/ecoventure_dwda/`.
2. Complete calculation sheets in Excel; **Save As `.xlsx`**.
3. Upload via Streamlit (**Optional: Ecoventure Phase I + DWDA workbook**) or CLI:

```powershell
python scripts\ingest_ecoventure_workbook.py --workbook path\to\filled.xlsx --out merged.xlsx
```

4. Metal/salt/DST outputs merge into `DwdaCalculations` and preflight calculation metrics.

Cell contract: [`schemas/ecoventure_dwda_cell_contract.json`](../schemas/ecoventure_dwda_cell_contract.json).

---

## Calculations (metal / salt / DST)

When `DwdaCalculations` sheet or Ecoventure workbook ingest is present, [`dwda_calculations.py`](../dwda_calculations.py) evaluates:

| Calculation | Pass criterion |
|-------------|----------------|
| Metal (barite sacks/m) | ≤ 0.22 |
| Salt (NaOH-equiv sacks/m³) | ≤ 0.02 × well depth (m) |
| DST returns | Resistivity or chloride path documented |

Results appear in preflight, `dwda_calc_summary`, and Appendix G. Phase II triggers when calculations fail or Option 2 DST data is insufficient.

---

## What the tool does NOT calculate

- Live Tier 1 / Equivalent Salinity numeric exceedance from lab data
- Replacement of official AER fillable checklist DOC (`.dotm` templates ship in deliverable zip for QP completion in Word)
- Legal interpretation of Directive 050 — QP sign-off required

---

## Phase II

Phase II is required when checklist cannot be completed, disposal location is unknown, QP flags Phase II, or contamination is likely. Lab results compare to Tier 1/2 (Equivalent Salinity for salinity within DWDA only). See profile `phase2_esa` and [03-excel-data-guide.md](03-excel-data-guide.md).

---

## Related

- [11-alberta-phase1-esa.md](11-alberta-phase1-esa.md)
- [20-aer-sed002-phase1-esa.md](20-aer-sed002-phase1-esa.md)
- [00-start-here.md](00-start-here.md)
- [`schemas/dwda_compliance_checklist.json`](../schemas/dwda_compliance_checklist.json)
- [`dwda_compliance.py`](../dwda_compliance.py)
- [`dwda_calculations.py`](../dwda_calculations.py)
- [`ecoventure_workbook.py`](../ecoventure_workbook.py)
- [`templates/ecoventure_dwda/README.md`](../templates/ecoventure_dwda/README.md)
