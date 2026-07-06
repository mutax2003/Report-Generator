# Ecoventure DWDA templates

QP-facing assets for Alberta Phase I ESA drilling waste disposal assessment (Directive 050 / ADWDA).

## Files

| File | Purpose |
|------|---------|
| `2025 Phase 1 ESA - Excel Sheets_TEMPLATE (1).xltm` | Master Phase I + DWDA calculation workbook (14 sheets) |
| `25XXXX_DWDA Compliance Option Form (1).dotm` | Official-style compliance option checklist (Word MERGEFIELD) |
| `25XXXXR Phase 1 ESA Letter_Template (1).dotm` | Client cover letter template |

## QP workflow

1. Open the **xltm** in Excel and complete `Phase 1 Data`, mud tallies, and calculation sheets.
2. **Save As `.xlsx`** before uploading to the ESA Report Generator (macros are not required for ingest).
3. Upload the saved workbook via Streamlit (**Ecoventure Phase I workbook**) or place `ecoventure_workbook.xlsx` in a project folder.
4. Generate the report; metal/salt/DST outputs merge into `DwdaCalculations` and preflight.

## Calculation sheets

| Sheet | Regulatory use |
|-------|----------------|
| `Metal Calcs (Options 1 &2)` | Barite sacks per metre (objective 0.22) |
| `Salt Calculations (Option 2)` | NaOH-equivalent sacks per m³ |
| `Drill Stem Test Returns` | Option 2 DST return equivalents |

Ingest cell addresses are defined in [`schemas/ecoventure_dwda_cell_contract.json`](../../schemas/ecoventure_dwda_cell_contract.json).

## Word templates

The `.dotm` files use Word MERGEFIELD mail merge — **not** docxtpl/Jinja. They are included in the deliverable zip under `qp_templates/` for QP completion in Word. Generated Appendix D remains the docxtpl companion for the report package.
