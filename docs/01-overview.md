# 01 — System overview

## Purpose

The **ESA Report Generator** is an internal tool for producing **Phase 1** and **Phase 2 Environmental Site Assessment (ESA)** reports. Non-technical users upload:

1. An **Excel workbook** (`.xlsx`) with project fields and optional lab results.
2. A **Word template** (`.docx`) containing Jinja2 placeholders.

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
2. **Read Excel** — Sheet `ProjectData` → flat dict (first data row only). Sheet `LabResults` → list of row dicts (Phase 2).
3. **Merge metadata** — Sidebar fields (`prepared_by`, `date_of_issue`, `report_phase`, `template_version`) normalized and merged; sidebar overrides Excel on key collision.
4. **Build Jinja context** — Keys are lowercased headers with spaces → underscores (`Site Name` → `site_name`).
5. **Pre-flight / coverage** — Compare template `{{ root_vars }}` to context keys; lint split Word runs.
6. **Render** — Missing scalar tags filled with `""` (warning, not crash). Lab exceedances → `result_display` as bold red RichText.
7. **Output** — Validated `.docx` + optional `GenerationRecord` JSON manifest.

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
| `security.py` | Upload validation, zip-bomb guards, context clamps |
| `template_tools.py` | Template scan, pre-flight, coverage |
| `provenance.py` | `GenerationRecord` manifest |
| `field_validation.py` | Warnings vs `schemas/field_contract.json` |
| `ui/` | Streamlit UI components |
| `ai/` | Optional LLM helpers (does not replace merge engine) |
| `automate/` | Headless render API for scripts / HTTP / Power Automate |
| `scripts/` | CLI utilities (samples, tag, E2E, inventory) |
| `schemas/field_contract.json` | Recommended fields and template rules |
| `samples/` | Committed demo and production-aligned fixtures |
| `tests/` | Unit and integration tests |
| `docs/` | This documentation set |

## What the system does not do

- **Batch reports** — Only the first `ProjectData` data row is used (single report per run).
- **PDF output** — Output is `.docx`; convert to PDF in Word if required.
- **Untrusted template sandbox for logic** — Jinja in templates is trusted author code (sandbox blocks unsafe Python, not malicious template design).
- **Automatic tagging of full 100+ page reports** — Production merge documents require manual or semi-automated Jinja insertion (see [04-template-authoring.md](04-template-authoring.md)).

## Related reading

- [02-user-guide.md](02-user-guide.md) — Day-to-day Streamlit workflow
- [05-developer-guide.md](05-developer-guide.md) — Code structure and extension
- [06-api-reference.md](06-api-reference.md) — Programmatic access
