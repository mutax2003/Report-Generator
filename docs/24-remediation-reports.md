# 21 — Remediation and reclamation reports

Profiles: **`phase3_remediation`** and **`reclamation_certificate`** in [`schemas/report_profiles.json`](../schemas/report_profiles.json).

## Phase III remediation

### Sample files

```powershell
python scripts\create_samples.py
python scripts\phase3_remediation_e2e.py
```

| File | Purpose |
|------|---------|
| `samples/phase3_remediation_data.xlsx` | Objectives, treatments, confirmatory sampling |
| `samples/phase3_remediation_template.docx` | Tagged remediation template |

### Excel sheets

| Sheet | Loop variable |
|-------|----------------|
| `RemediationObjectives` | `remediation_objectives` |
| `TreatmentEvents` | `treatment_events` |
| `ConfirmatorySampling` | `confirmatory_sampling` (exceedance styling) |
| `WasteManifests` | `waste_manifests` |

Use `PhraseCatalog` / **Standard phrases** for `remediation_status`, `confirmatory_summary`, `closure_recommendation`.

## Reclamation certificate

### Sample files

```powershell
python scripts\reclamation_e2e.py
```

| File | Purpose |
|------|---------|
| `samples/reclamation_certificate_data.xlsx` | Tasks, soil placement, vegetation |
| `samples/reclamation_certificate_template.docx` | Reclamation tables |

Pre-flight runs **SED 002 §10** (Phase I fields) plus **reclamation checklist** (`schemas/reclamation_checklist.json`).

## Phase II (Alberta)

Gold pair: `samples/phase2_alberta_data.xlsx` + `samples/phase2_alberta_template.docx`

```powershell
python scripts\phase2_alberta_e2e.py
```

Auto executive summary and exceedance summary via [`phase2_narrative.py`](../phase2_narrative.py). Preflight checklist: [`schemas/phase2_esa_checklist.json`](../schemas/phase2_esa_checklist.json).
