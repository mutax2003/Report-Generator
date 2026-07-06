# 23 — Excel calculation workbook integration

Best practices for embedding legacy Excel calculation workbooks (`.xltm`, multi-sheet formulas) in a software workflow. This repo implements the **hybrid** pattern for Ecoventure DWDA; use it as a reference when adding similar integrations.

## When to use which strategy

| Strategy | When | Pros | Risks |
|----------|------|------|-------|
| **Keep Excel only** | Rare calcs, low automation | Zero parity risk | No preflight or batch |
| **Ingest outputs** | Stable layout, few output cells | Fast; QP keeps familiar tool | Layout drift breaks ingest |
| **Replicate in code** | Simple formulas, high volume | Server-native, testable | QP may distrust until proven |
| **Hybrid (recommended)** | Regulated consulting, legacy `.xltm` | QP trust + automation + audit | Contract + parity tests required |

**Hybrid** means: consultants complete the official workbook in Excel; the app ingests saved `.xlsx` values via a **cell contract**, normalizes into canonical engine Excel, and **re-evaluates** critical pass/fail logic in Python with cross-check warnings.

## Data flow (Ecoventure DWDA)

```
QP completes xltm in Excel
    → Save As .xlsx (values materialized)
    → Upload (Streamlit) or ecoventure_workbook.xlsx in project folder
    → Cell contract ingest (schemas/ecoventure_dwda_cell_contract.json)
    → merge_into_engine_excel → ProjectData / DrillingWaste / DwdaCalculations
    → ReportEngine + dwda_calculations.py (parity + cross-check)
    → Preflight, Appendix G, OneStop, deliverable zip (qp_templates/)
```

## Best practices

### 1. Excel is QP-facing, not server runtime

- Do **not** run macros or COM/Excel automation on the server.
- Require **Save As `.xlsx`** — `openpyxl` with `data_only=True` reads cached values only; it does not evaluate formulas.
- Ship original `.xltm` / `.dotm` in deliverables (`qp_templates/` in the deliverable zip).

### 2. Machine-readable cell contract

Author [`schemas/ecoventure_dwda_cell_contract.json`](../schemas/ecoventure_dwda_cell_contract.json) with:

| Element | Purpose |
|---------|---------|
| `contract_version` | Semver for ingest schema governance |
| `workbook_template_id` | Human-readable template lineage |
| `workbook_signature_sheets` | Detect correct workbook variant |
| `calculation_outputs` | Fixed sheet + cell → semantic keys |
| `phase1_data_mapping` | Header row + column labels → `ProjectData` / `DrillingWaste` |

**Checklist when authoring a new contract:**

1. List signature sheets that must exist before ingest.
2. Map only **output** cells (not every intermediate formula).
3. Use semantic snake_case keys (`metal_sacks_per_metre`), not cell addresses, in engine context.
4. Document constants (e.g. metal objective `0.22`) in the contract when they are not read from cells.
5. Bump `contract_version` when addresses or keys change; add tests.

### 3. Normalize into one internal Excel shape

[`ecoventure_workbook.merge_into_engine_excel`](../ecoventure_workbook.py) writes into standard engine sheets — never make the legacy workbook the only schema.

- Streamlit: [`ui/helpers.effective_excel_bytes`](../ui/helpers.py) with digest-based stale-session clearing.
- Project folder: optional [`ecoventure_workbook.xlsx`](../ecoventure_workbook.py) via [`maybe_merge_ecoventure_from_folder`](../ecoventure_workbook.py).
- CLI: [`scripts/ingest_ecoventure_workbook.py`](../scripts/ingest_ecoventure_workbook.py).

### 4. Replicate critical formulas with parity checks

[`dwda_calculations.py`](../dwda_calculations.py):

- Prefer **ingested workbook values** when present; compute when missing.
- Emit **cross-check warnings** when Python vs workbook differ beyond tolerance (5%).
- Document **non-goals** (no Tier 1 lab engine, no `.dotm` → docxtpl) in [21-dwda-directive-050-compliance.md](21-dwda-directive-050-compliance.md).

### 5. Version and govern

- Engine support version: `ENGINE_SUPPORTED_CONTRACT_VERSION` in `ecoventure_workbook.py`.
- Unknown contract versions **warn** at ingest; block only when required outputs are missing for the selected compliance option.
- Provenance on context: `_ecoventure_contract_version`, `_ecoventure_workbook_template_id`.

### 6. Test in layers

| Layer | Example |
|-------|---------|
| Unit (formulas) | `tests/test_dwda_calculations.py` |
| Ingest + merge | `tests/test_ecoventure_workbook.py` |
| Edge cases | `tests/test_dwda_edge_cases.py` |
| E2E | `scripts/dwda_workflow_e2e.py`, health check #16 |
| Site fixtures | `scripts/phase1_site_e2e.py` |

### 7. Operational UX

- Optional Ecoventure upload in Streamlit ([`ui/layout.py`](../ui/layout.py)).
- Preflight DWDA panel + QP checklist download ([`ui/preflight.py`](../ui/preflight.py)).
- **QP professional sign-off** remains mandatory.

## Anti-patterns

- Parsing arbitrary Excel formula strings at runtime.
- Assuming uploaded `.xlsx` contains calculated values without the QP opening/saving in Excel first.
- Full multi-sheet `.xltm` parity in Python without a phased port plan.
- Silent overwrite of consultant Excel when the base upload changes (always invalidate cached merges).

## Developer extension guide

To add a new calculation output:

1. Add key + sheet/cell to `schemas/ecoventure_dwda_cell_contract.json` (`calculation_outputs`).
2. Port pass/fail logic in `dwda_calculations.py` if needed for preflight.
3. Add fields to `schemas/report_profiles.json` `recommended_fields` for the profile.
4. Extend `DwdaCalcResult.to_context_dict()` and Appendix G if the value appears in reports.
5. Add unit test + fixture row in `samples/ecoventure_dwda/minimal_calc_workbook.xlsx`.
6. Run `python scripts/health_check.py` and `python scripts/dwda_workflow_e2e.py`.

## QP workflow (Ecoventure)

1. Download xltm from preflight or [`templates/ecoventure_dwda/`](../templates/ecoventure_dwda/).
2. Complete Phase 1 Data and calculation sheets in Excel.
3. **Save As `.xlsx`**.
4. Upload in Streamlit or place `ecoventure_workbook.xlsx` beside `project_data.xlsx` in a [project folder](22-project-folder-workflow.md).
5. Generate report; review preflight calculation metrics and cross-check warnings.

## Related

- [21-dwda-directive-050-compliance.md](21-dwda-directive-050-compliance.md) — regulatory logic and generated keys
- [22-project-folder-workflow.md](22-project-folder-workflow.md) — CLI folder layout including `ecoventure_workbook.xlsx`
- [`templates/ecoventure_dwda/README.md`](../templates/ecoventure_dwda/README.md) — QP template inventory
