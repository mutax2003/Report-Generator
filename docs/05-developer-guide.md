# 05 — Developer guide

Guide for maintaining and extending the ESA Report Generator codebase.

## Design principles

1. **`engine.py` is headless** — No Streamlit imports in the merge core (Power Automate / Azure ready).
2. **Warnings vs errors** — Missing scalar template vars warn and render empty; invalid files and missing required sheets error.
3. **Schema-first data** — `schemas/report_profiles.json` `recommended_fields` per profile drives pre-flight warnings; extend profiles when adding production fields. Update `field_contract.json` for AI tagger / legacy docs if needed.
4. **Defense in depth** — Validate at upload, parse, context build, and output validation.

## Module reference

### `engine.py`

| Symbol | Role |
|--------|------|
| `PROJECT_SHEET`, `LAB_SHEET` | `ProjectData`, `LabResults` |
| `DRILLING_WASTE_SHEET`, `STORAGE_TANKS_SHEET` | Optional Alberta Phase I table sheets |
| `ECOVENTURE_CONSULTANT` | Default firm string (`Ecoventure Inc.`) |
| `ReportEngine` | Main class: construct with bytes, call `build_context`, `render`, `dry_run`, `coverage` |
| `generate_phase1_alberta_excel/docx` | Committed Alberta Phase I sample fixtures |
| `collect_template_root_vars` | Parse `{{ root }}` from template ZIP XML |
| `suggested_download_name` | Safe output filename from context + meta |
| `generate_*_excel/docx` | Sample/production fixture builders |
| `PRODUCTION_BRACKET_REPLACEMENTS` | Map for `tag_production_template.py` |

**`ReportEngine` lifecycle:**

```python
engine = ReportEngine(excel_bytes=b"...", template_bytes=b"...")
context = engine.build_context(meta={"prepared_by": "..."})
docx, warnings, context, record = engine.render(meta=meta)
```

Render uses `SandboxedEnvironment` + `StrictUndefined` for Jinja inside docxtpl.

### `security.py`

Upload validators, `ZipReadBudget`, `clamp_context`, `sanitize_meta`, `user_safe_error`, `open_docx_zip`. Tunable constants at file top (`MAX_EXCEL_BYTES`, etc.).

Environment bypass for tests only: `ESA_VALIDATION_BYPASS=1`.

### `template_tools.py`

| Symbol | Role |
|--------|------|
| `TemplateCoverage` | matched / missing / unused vars |
| `PreflightResult` | errors, warnings, `can_generate` |
| `scan_template` | Vars, blocks, split-run lint |
| `run_preflight` | Full pre-render check |
| `missing_fields_checklist` | Markdown text for Excel planning |

### `report_profile.py`

`resolve_report_config`, `read_excel_meta`, `get_recommended_fields`, `build_report_config_workbook_bytes`, template loop discovery.

### `template_attachments.py`

`prepare_template_upload` — PDF → DOCX via pdf2docx; `PreparedTemplate` dataclass.

### `appendix_generator.py`

`render_phase1_appendices`, `attach_appendices_to_record`, `predicted_appendix_labels`, `merge_appendix_lists` — auto-render SED 002 appendices **D** (drilling waste checklist) and **G** (calc tables) from the same Jinja context as the main report. Templates in `samples/appendices/`; profile mapping via `appendix_templates` in `schemas/report_profiles.json`. No Streamlit imports.

### `deliverable_pack.py`

`build_deliverable_zip`, `build_deliverable_zip_bytes`, `build_onestop_export_bytes`, `AppendixFile`, `appendix_manifest_entries`, `enrich_manifest_dict`, `build_batch_reports_zip` — zip includes `appendices/` (uploaded PDFs + generated D/G `.docx`) and `onestop/` summary JSON/CSV for OneStop upload prep.

### `phase1_narrative.py`

`build_phase1_executive_summary` — Signum-style structure, Ecoventure voice.

### `phase1_decision.py`

`evaluate_phase2_triggers`, `enrich_context_phase2_decision` — Phase II ESA heuristics aligned with SED 002; adds `phase2_recommended` and `phase2_reasons` to render context.

### `sed002_compliance.py`

`evaluate_sed002_compliance`, `build_qp_review_checklist_markdown` — SED 002 §10 checklist driven by [`schemas/sed002_phase1_checklist.json`](../schemas/sed002_phase1_checklist.json); used in preflight and QP review export.

### `provenance.py`

`GenerationRecord` dataclass (`report_type`, `template_source_format`, `appendix_files`, `generated_appendix_files`), `build_generation_record`, `sha256_hex`.

### `field_validation.py`

`contract_warnings` — reads `report_profiles.json` first; falls back to `field_contract.json`.

### `app.py`

Streamlit orchestration only: session state, uploaders, calls `ui/*`, instantiates `ReportEngine` on generate.

### `ui/` package

| Module | Role |
|--------|------|
| `sidebar.py` | Profile, phase sync, meta, executive summary override, sample downloads |
| `helpers.py` | Template cache, PDF conversion download, `_ensure_samples`, template analysis |
| `preflight.py` | Cached preflight, SED 002 §10 metrics, appendix-aware checklist, ReportConfig export |
| `preview.py` | Dry-run panel |
| `appendix_panel.py` | Appendix A–H PDF uploads, generated D/G downloads, deliverable zip + OneStop export |
| `results.py` | Download buttons, context preview, manifest; batch zip includes per-site `appendices/` |
| `workflow.py` | Step indicator UI |
| `ai_panel.py` | AI tab (Tier 1 & 2) |

### `ai/` package

Optional LLM features; each module has offline fallback. Does not modify `ReportEngine.render` logic.

### `automate/` package

`render.py` — path/bytes wrappers; `http_server.py` — localhost POST `/render`.

## Session state keys (`app.py`)

| Key | Type | Purpose |
|-----|------|---------|
| `generated_docx` | `bytes \| None` | Last render output |
| `generated_filename` | `str \| None` | Download name |
| `warnings` | `list[str]` | Last render warnings |
| `last_context` | `dict \| None` | Preview dict |
| `generation_record` | `GenerationRecord \| None` | Manifest source |
| `rendering` | `bool` | Concurrency guard |
| `ai_audit_log` | `list` | Copied into manifest on generate |

## Extending the engine

### Add a new ProjectData field

1. Add column to Excel / `production_data.xlsx`.
2. Add to `schemas/report_profiles.json` `recommended_fields` for the relevant profile (and `field_contract.json` if AI tagger needs it).
3. Add `{{ field }}` to Word template.
4. No code change required if header normalizes to existing Jinja name.

### Add computed fields

Extend `build_context` in `ReportEngine` after `project` dict is built:

```python
ctx["report_year_short"] = ctx.get("report_year", "")[:4]
```

### Add lab row computed fields

Extend `_lab_frame_to_records` in `engine.py`.

### Batch reports

- Multiple non-blank `ProjectData` rows (row 1 = headers).
- `ReportEngine.render_batch()` / Streamlit **All N reports (batch)** / `render_cli.py --all-rows`.
- Table sheets can link per site via `site_name`, `project_number`, `uwi`, `well_name`, or `project_id`.
- Limits: `MAX_PROJECT_ROWS` (100), `MAX_BATCH_REPORTS` (50).

## Coding conventions

- Python 3.10+ type hints (`from __future__ import annotations`).
- User-facing errors: `SecurityError` or `ValueError` with safe messages; `user_safe_error()` in UI.
- Logging: `logger.exception` on render failure in `app.py`.
- Tests: `unittest` in `tests/`; samples required for E2E (committed in repo).

## Dependencies

See `requirements.txt`. Core: `streamlit`, `docxtpl`, `pandas`, `openpyxl`, `python-docx`, `Jinja2`, `pdf2docx`, `pypdf`. Optional AI: `openai`.

## Local development loop

```powershell
pip install -r requirements.txt
python scripts\create_samples.py
python -m unittest discover -s tests -v
streamlit run app.py
```

## CI

GitHub Actions: `.github/workflows/ci.yml` — install, samples, tag, unittest, CLI, production E2E.

## Related

- [06-api-reference.md](06-api-reference.md) — Public functions and scripts
- [08-testing.md](08-testing.md) — Test matrix
