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

`resolve_report_config`, `get_recommended_fields`, `build_report_config_workbook_bytes`, template loop discovery.

### `template_attachments.py`

`prepare_template_upload` — PDF → DOCX via pdf2docx; `PreparedTemplate` dataclass.

### `deliverable_pack.py`

`build_deliverable_zip`, `AppendixFile`, `appendix_manifest_entries`, `enrich_manifest_dict`.

### `phase1_narrative.py`

`build_phase1_executive_summary` — Signum-style structure, Ecoventure voice.

### `provenance.py`

`GenerationRecord` dataclass (`report_type`, `template_source_format`, `appendix_files`), `build_generation_record`, `sha256_hex`.

### `field_validation.py`

`contract_warnings` — reads `report_profiles.json` first; falls back to `field_contract.json`.

### `app.py`

Streamlit orchestration only: session state, uploaders, calls `ui/*`, instantiates `ReportEngine` on generate.

### `ui/` package

| Module | Role |
|--------|------|
| `sidebar.py` | Profile, phase sync, meta, executive summary override, sample downloads |
| `helpers.py` | Template cache, PDF conversion download, `_ensure_samples`, template analysis |
| `preflight.py` | Cached preflight, profile checklist, ReportConfig export |
| `preview.py` | Dry-run panel |
| `results.py` | Download buttons, context preview, manifest |
| `appendix_panel.py` | Appendix A–F uploads, deliverable zip download |
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
