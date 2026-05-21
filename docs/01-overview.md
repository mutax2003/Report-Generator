# 01 — System overview

## Purpose

The **ESA Report Generator** is an internal tool for producing **Phase 1** and **Phase 2 Environmental Site Assessment (ESA)** reports. Non-technical users upload:

1. An **Excel workbook** (`.xlsx`) with project fields and optional lab results.
2. A **Word or PDF template** (`.docx` preferred; `.pdf` converted to Word for merge) containing Jinja2 placeholders.

The application merges data into the template and returns a finished Word document for review and client delivery.

Design goals:

- **Separation of concerns** — Word design vs Excel data vs Python merge logic (same pattern as mail merge / HotDocs / docxtpl production systems).
- **Pre-flight QA** — Validate sheets, tags, and split-run issues before rendering.
- **Audit trail** — SHA-256 manifests record inputs, outputs, and warnings.
- **Portability** — Core logic in `engine.py` can run in Streamlit, CLI, HTTP, or future Power Automate flows without rewrite.

## Technology stack

| Layer | Technology | Role |
|-------|------------|------|
| UI | [Streamlit](https://streamlit.io/) | Upload, sidebar, pre-flight, generate, download |
| Templating | [docxtpl](https://docxtpl.readthedocs.io/) + Jinja2 | Word merge, table row loops, RichText |
| Data | pandas + openpyxl | Read `ProjectData` / `LabResults` sheets |
| Security | Custom `security.py` | Zip validation, size limits, sandboxed Jinja |
| Optional AI | OpenAI API (optional) | PDF import, narratives, copilot — offline fallbacks available |

**Python:** 3.10+ recommended.

## High-level architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Streamlit (app.py)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │ sidebar  │ │preflight │ │ preview  │ │ results  │ │ ai_panel│ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬────┘ │
└───────┼────────────┼────────────┼────────────┼────────────┼───────┘
        │            │            │            │            │
        └────────────┴────────────┴─────┬──────┴────────────┘
                                        ▼
                              ┌─────────────────┐
                              │  ReportEngine   │
                              │   (engine.py)   │
                              └────────┬────────┘
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
            template_tools.py    field_validation.py   provenance.py
            security.py
                    ▼
            Excel context dict + lab_results list
                    ▼
              docxtpl → .docx bytes
```

## Core data flow

1. **Validate uploads** — File type, ZIP structure, size (see [07-security-and-deployment.md](07-security-and-deployment.md)).
2. **Prepare template** — `.docx` as-is; `.pdf` → DOCX via `template_attachments.py` (cached in UI).
3. **Read Excel** — Sheet `ProjectData` → flat dict (first data row only). Optional `ReportConfig`, `LabResults`, table sheets per [report profile](13-flexible-report-profiles.md).
4. **Merge metadata** — Sidebar (`report_type`, `report_phase`, `prepared_by`, `date_of_issue`, `template_version`, `executive_summary`) normalized and merged; sidebar overrides Excel on key collision.
5. **Build Jinja context** — Keys are lowercased headers with spaces → underscores (`Site Name` → `site_name`).
6. **Pre-flight / coverage** — Profile-aware checklist; compare template `{{ root_vars }}` to context keys; lint split Word runs.
7. **Render** — Missing scalar tags filled with `""` (warning, not crash). Lab exceedances → `result_display` as bold red RichText.
8. **Output** — Validated `.docx` + `GenerationRecord` JSON manifest + optional deliverable **zip** (appendices A–F).

## Report phases

| Phase | `LabResults` | `DrillingWaste` / `StorageTanks` | Behavior |
|-------|--------------|----------------------------------|----------|
| **Phase 1** | Optional | Optional (Alberta O&G) | Empty `lab_results` if sheet missing; optional `drilling_waste` / `storage_tanks` table loops |
| **Phase 2** | **Required** | Optional | Lab table loops populate from `LabResults` rows |

Primary Alberta Phase I workflow: [11-alberta-phase1-esa.md](11-alberta-phase1-esa.md). Set phase in the sidebar **Report phase** dropdown (default **Phase 1**).

## Repository layout

| Path | Responsibility |
|------|----------------|
| `app.py` | Streamlit entry, session state, generate button |
| `engine.py` | `ReportEngine`, Excel parsing, docxtpl render, sample generators |
| `report_profile.py` | Profile resolution, `ReportConfig`, recommended fields |
| `template_attachments.py` | PDF → DOCX template preparation |
| `deliverable_pack.py` | Zip package, appendix manifest entries |
| `phase1_narrative.py` | Auto executive summary (Alberta Phase I) |
| `security.py` | Upload validation, zip-bomb guards, context clamps |
| `template_tools.py` | Template scan, pre-flight, coverage |
| `provenance.py` | `GenerationRecord` manifest |
| `field_validation.py` | Warnings vs `schemas/report_profiles.json` (profiles first) |
| `ui/` | Streamlit UI (`sidebar`, `preflight`, `appendix_panel`, …) |
| `ai/` | Optional LLM helpers (does not replace merge engine) |
| `automate/` | Headless render API for scripts / HTTP / Power Automate |
| `scripts/` | CLI utilities (samples, tag, E2E, inventory) |
| `schemas/report_profiles.json` | **Canonical** recommended fields per profile |
| `schemas/field_contract.json` | Legacy reference and AI tagger |
| `samples/` | Committed demo and production-aligned fixtures |
| `tests/` | Unit and integration tests (75) |
| `Dockerfile` | Container image for Streamlit |
| `docs/` | This documentation set |

## What the system does not do

- **Batch reports** — Only the first `ProjectData` data row is used (single report per run).
- **PDF output** — Output is `.docx`; convert to PDF in Word if required. Appendix PDFs are zipped, not merged into one PDF in-app.
- **Untrusted template sandbox for logic** — Jinja in templates is trusted author code (sandbox blocks unsafe Python, not malicious template design).
- **Automatic tagging of full 100+ page reports** — Production merge documents require manual or semi-automated Jinja insertion (see [04-template-authoring.md](04-template-authoring.md)).

## Related reading

- [02-user-guide.md](02-user-guide.md) — Day-to-day Streamlit workflow
- [05-developer-guide.md](05-developer-guide.md) — Code structure and extension
- [06-api-reference.md](06-api-reference.md) — Programmatic access
