# Alberta Phase I ESA — Field inventory (reference PDF)

**Reference (local, gitignored):** `00_04-04-049-04W4M Phase I report - Devon 2017.pdf`  
**Prepared for implementation by:** **Ecoventure Inc.** (all generated samples and templates use Ecoventure as consultant; client data may use anonymized operator names).

## Report type

Alberta O&G **AER Schedule Two** Phase 1 ESA package (reclamation certificate workflow), not a standalone CSA Z768 narrative-only report.

| Section | Automate in V1 | Notes |
|---------|-----------------|-------|
| Cover (prepared for/by, UWI, date, QP) | Yes | `ProjectData` + sidebar |
| Executive summary | Yes | `{{ executive_summary }}` |
| AER 10.2 Drilling | Yes | Scalar + `DrillingWaste` sheet |
| AER 10.3 Production / tanks | Yes | Scalar + `StorageTanks` sheet |
| AER 10.4 Site visit | Yes | Scalar checklist fields |
| AER 10.5–10.7 Imagery, interviews, conclusions | Partial | Key scalar fields |
| Appendices A–H | Streamlit upload A–H | Included in deliverable zip; SED preflight counts labels; merge to one PDF outside app |

## Ecoventure branding (implementation default)

| Field | Value in samples |
|-------|------------------|
| `consultant_name` | Ecoventure Inc. |
| `company` | Ecoventure Inc. |
| `prepared_by` | Sidebar / Excel (Ecoventure QP name) |
| Report voice | Ecoventure-authored prose in `executive_summary` |

Client in samples: **Example Energy Ltd.** (redacted; do not use Devon in committed files).

## ProjectData fields (from reference)

| Key | Example / notes |
|-----|-----------------|
| `client_name` | Example Energy Ltd. |
| `consultant_name` | Ecoventure Inc. |
| `company` | Ecoventure Inc. |
| `well_name` | Example 4D Windy 4-4-49-4 |
| `uwi` | 00/04-04-049-04W4/0 |
| `site_name` | Same as well_name or LSD line |
| `report_title` | Phase I Environmental Site Assessment |
| `report_month_year` | March 2017 |
| `qp_names` | Ecoventure QP roster (semicolon-separated) |
| `spud_date` | 15-Mar-2004 |
| `final_drill_date` | 19-Jun-2004 |
| `well_depth_m` | 710 |
| `well_status` | suspended |
| `reentry` | Yes |
| `production_fluid` | gas with water |
| `drilling_waste_summary` | Narrative (AER 2014 Option 1) |
| `aer_waste_compliance_option` | Option 1 |
| `phase2_esa_required` | Yes — keyword Phase II |
| `site_visit_completed` | No |
| `executive_summary` | Full narrative (Signum structure; auto-built from fields if empty) |
| `cased_date` | 17-Mar-2004 |
| `reentry_detail` | Re-entry / TD / status sentence |
| `phase2_drilling_waste_required` | No — Phase II for drilling waste |
| `air_photo_observations` | 2015 air photo / berm / tanks note |
| `investigations_recommended` | well centre and production areas |
| `client_phase_keyword` | Phase II (operator keyword) |
| `conclusions_recommendations` | Investigate well centre and production areas |
| `infrastructure_summary` | access road, teardrop, berm, tanks |
| `spills_releases` | No |

## DrillingWaste sheet

| Column | Example row |
|--------|-------------|
| mud_type | Gel Chem |
| volume_m3 | 208 |
| disposal_method | LWD, landspray, landspread onsite, remote site |
| location | SW1/4 04-049-04 W4M; SE-09-049-04 W4M; etc. |

Jinja: `{%tr for item in drilling_waste %}`

## StorageTanks sheet

| Column | Example row |
|--------|-------------|
| tank_type | Above ground tank |
| content | Produced water |
| location | SE of well centre |
| capacity_m3 | Unknown |

Jinja: `{%tr for item in storage_tanks %}`

## Appendices (manual)

- A: AER Phase I form and QP declaration  
- B: ABADATA, pipeline, spill search  
- C: Air photos (2001, 2004, 2015)  
- D: Drilling waste notification and checklist  
- E: Survey plan and proximity map  
- F: Land title search  

## Implementation artifacts (pending Agent mode)

- `samples/phase1_alberta_data.xlsx`  
- `samples/phase1_alberta_template.docx`  
- `schemas/report_profiles.json` — `phase1_alberta` → `recommended_fields`
- `schemas/field_contract.json` — legacy `recommended_phase_1_alberta_og`  
- `engine.py` — optional sheets + generators  
- `docs/11-alberta-phase1-esa.md`  
- Default sidebar **Phase 1**  
- `rag_corpus/phase1_alberta_aer.txt`  
