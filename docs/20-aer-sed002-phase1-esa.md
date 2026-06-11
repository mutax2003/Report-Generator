# 20 — AER SED 002 Phase 1 ESA alignment

Ecoventure reports for **reclamation certificate** applications must satisfy **Specified Enactment Direction 002 (SED 002, July 2025)** Section 10 and the [AER reclamation certificate submissions](https://www.aer.ca/regulations-and-compliance-enforcement/site-closure-requirements/reclamation/oil-and-gas-sites/reclamation-certificate-application-submissions) workflow (Phase 1 → Phase 2 → remediation → **OneStop**).

Provincial archive copy: [open.alberta.ca SED 002 PDF](https://open.alberta.ca/dataset/ad267908-bdf4-4c97-ad9f-760a547e4245/resource/78d43883-0334-4220-a037-2746648390a1/download/6821.pdf) (same document family; use current [AER SED 002](https://www.aer.ca/regulations-and-compliance-enforcement/rules-and-regulations/specified-enactment-directions/specified-enactment-direction-002-application-submission-requirements-and-guidance-reclamation) when in doubt).

## Terminology

| Old label in app/docs | Correct regulatory framing |
|----------------------|----------------------------|
| “Schedule Two” (facility licence) | **SED 002 Section 10** — Phase 1 ESA report content |
| CSA Z768-only narrative | Must also cover **drilling waste**, records, site visit, interviews per SED |

## Machine-readable checklist

[`schemas/sed002_phase1_checklist.json`](../schemas/sed002_phase1_checklist.json) maps SED §10 items to:

- **ProjectData** columns
- **DrillingWaste** / **StorageTanks** sheets
- **Appendices** A–H
- Sidebar **meta** (`prepared_by`, `date_of_issue`)

Evaluation code: [`sed002_compliance.py`](../sed002_compliance.py). Phase 2 hints: [`phase1_decision.py`](../phase1_decision.py).

## Excel fields (ProjectData) — SED-driven

| Field | SED section |
|-------|-------------|
| `asset_activity_type` | 10.1 |
| `prior_reclamation_cert_number` | 10.1 / 10.3 |
| `records_review_summary` | 10.7 |
| `interview_operator_summary`, `interview_landowner_summary` | 10.8 |
| `site_visit_date`, `site_visit_photo_notes` | 10.6 |
| `flare_pit_used`, `no_drilling_waste_on_site` | 10.4 / 10.5 |
| `phase2_recommended`, `phase2_reasons` | 5.1 (auto from rules) |

## DrillingWaste sheet columns

| Column | SED 002 |
|--------|---------|
| `disposal_type` | On-lease sump / remote / off-lease / none |
| `gps_coordinates` | 10.4 on-lease sump |
| `sump_depth_m`, `cover_depth_m` | 10.4 |
| `remote_cert_number` | 10.4 remote sump |
| `waste_manifest_refs` | 10.4 manifests |

## Word template

Gold sample: `samples/phase1_alberta_template.docx` (headings **10.1–10.8**).  
Devon reference layout: `samples/phase1_devon_template.docx`.

Regenerate samples:

```powershell
python scripts\create_samples.py
python scripts\create_phase1_devon_pair.py
```

## Pre-flight in Streamlit

After upload, the **Report** tab shows:

- **SED 002 §10** completeness %
- Per-section counts (10.1, 10.4, …)
- **QP review checklist** download (markdown)
- Phase 2 trigger hints

## Deliverable zip / OneStop

**Download deliverable package (.zip)** includes:

- Report `.docx` + manifest JSON
- `appendices/` — auto-generated **D** and **G** as `.docx` (from DrillingWaste / ProjectData) plus uploaded A–H PDFs
- `onestop/phase1_esa_summary.json` and `.csv` — field reference for the Phase 1 ESA summary module
- `onestop/SUBMISSION_LAYOUT.txt` — suggested PDF filenames for upload

Export the Word report and generated appendix `.docx` files to PDF manually before OneStop submission.

## Related

- [11-alberta-phase1-esa.md](11-alberta-phase1-esa.md) — author workflow  
- [12-testing-with-your-documents.md](12-testing-with-your-documents.md)  
- [16-team-rollout.md](16-team-rollout.md)
