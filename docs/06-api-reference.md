# 06 — API and automation reference

Programmatic interfaces for rendering reports without the Streamlit UI.

## `render_service` (recommended headless API)

**Module:** `render_service.py`

Use this for CLI, Power Automate, project folder, and Streamlit — it wraps `ReportEngine` with appendix-aware DWDA/SED context, appendix attachment, and compliance snapshot on the manifest.

### `RenderRequest`

| Field | Type | Notes |
|-------|------|-------|
| `excel_bytes` | `bytes` | Required |
| `template_bytes` | `bytes` | `.docx` or `.pdf` (PDF converted via cache) |
| `meta` | `dict[str, str]` | Sidebar / profile keys (see below) |
| `excel_filename` | `str` | Stored in manifest |
| `template_filename` | `str` | Stored in manifest |
| `project_row_index` | `int` | `ProjectData` row (0 = row 2) |
| `uploaded_appendices` | `list[AppendixFile]` | PDF uploads; labels derived from filenames/heuristics |
| `appendix_labels_present` | `set[str] \| None` | Explicit A–H labels; overrides upload inference when set |
| `include_appendices` | `bool` | Auto-render A/D/G and merge uploads (default `True`) |
| `include_coverage` | `bool` | Template coverage on manifest (default `True`) |

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `render_report(req)` | `RenderResult` | Single report + appendices + compliance snapshot |
| `render_batch_reports(req)` | `list[BatchReportResult]` | One report per non-blank `ProjectData` row |
| `render_deliverable_package(req, report_filename=...)` | `RenderResult` | Above + `package_bytes` deliverable zip |

### Example

```python
from deliverable_pack import AppendixFile
from render_service import RenderRequest, render_report

with open("data.xlsx", "rb") as f:
    excel_bytes = f.read()
with open("template.docx", "rb") as f:
    template_bytes = f.read()

result = render_report(
    RenderRequest(
        excel_bytes=excel_bytes,
        template_bytes=template_bytes,
        meta={"prepared_by": "API", "date_of_issue": "2026-05-20", "report_phase": "Phase 1", "report_type": "phase1_alberta"},
        uploaded_appendices=[
            AppendixFile(label="H", data=b"...", filename="appendix_h.pdf", format="pdf"),
        ],
    )
)
Path("out.docx").write_bytes(result.docx_bytes)
Path("out_manifest.json").write_bytes(result.record.to_json_bytes())
```

Deliverable zip includes `qp_checklists/sed002_phase1_qp_checklist.md` and `qp_checklists/dwda_directive050_qp_checklist.md` for Phase I Alberta profiles when compliance data is present.

## `ReportEngine` (low-level API)

**Module:** `engine.py`

### Constructor

```python
ReportEngine(excel_bytes: bytes, template_bytes: bytes)
```

Validates uploads unless `ESA_VALIDATION_BYPASS=1`.

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `build_context(meta)` | `dict` | Excel + sidebar merged; no render |
| `dry_run(meta, excel_filename=..., template_filename=...)` | `(context, warnings, GenerationRecord)` | Context + manifest; no Word file |
| `render(meta, ..., appendix_labels_present=..., project_row_index=...)` | `(docx_bytes, warnings, context, GenerationRecord)` | Full merge |
| `render_batch(meta, excel_filename=..., template_filename=...)` | `list[BatchReportResult]` | One `.docx` per non-blank `ProjectData` row (max 50) |
| `project_row_count(meta)` | `int` | Non-blank data rows on `ProjectData` |
| `coverage(meta)` | `TemplateCoverage` | Tag match analysis |
| `template_root_vars()` | `set[str]` | Root `{{ var }}` names from template |
| `missing_template_vars(context)` | `list[str]` | Sorted missing keys |

### Meta dict keys

| Key | Example | Notes |
|-----|---------|-------|
| `prepared_by` | `"Jane Doe"` | Sanitized, max 500 chars |
| `date_of_issue` | `"2026-05-20"` | ISO date string |
| `report_phase` | `"Phase 2"` | `"Phase 1"` skips required lab sheet |
| `report_type` | `"phase1_alberta"` | Profile ID; maps sheets to template loops |
| `template_version` | `"2.1.0"` | Stored in manifest |
| `executive_summary` | `"..."` | Sidebar override; wins over Excel / auto Phase I text |
| `template_source_format` | `"pdf"` or `"docx"` | Set by UI when template was PDF vs Word |
| `drilling_waste_intro` | `"..."` | Phrase text (UI / Excel / `PhraseCatalog`) |
| `drilling_waste_intro_option_id` | `"option_1_aer"` | Selected phrase option id |
| `site_recon_intro` / `*_option_id` | (same pattern) | From `schemas/phrase_catalog.json` |
| `phase2_recommendation` / `*_option_id` | (same pattern) | Phase II recommendation phrase |

Phrase keys mirror catalog entries in [`schemas/phrase_catalog.json`](../schemas/phrase_catalog.json). Excel may use `PhraseCatalog` sheet or `{phrase_key}_selected` columns on `ProjectData`; resolution is in `phrase_resolver.apply_phrase_resolution`.

### Example

```python
from engine import ReportEngine

with open("data.xlsx", "rb") as f:
    excel_bytes = f.read()
with open("template.docx", "rb") as f:
    template_bytes = f.read()

engine = ReportEngine(excel_bytes, template_bytes)
docx_bytes, warnings, context, record = engine.render(
    meta={"prepared_by": "API", "date_of_issue": "2026-05-20", "report_phase": "Phase 2"},
    excel_filename="data.xlsx",
    template_filename="template.docx",
)
Path("out.docx").write_bytes(docx_bytes)
Path("out_manifest.json").write_bytes(record.to_json_bytes())
```

## `automate` package

**Module:** `automate/render.py` — delegates to **`render_service`** (`render_report_from_bytes`, `render_batch_from_bytes`, `render_deliverable_zip_from_bytes`, `render_report_from_paths`).

```python
from automate.render import render_report_from_paths, render_report_from_bytes

warnings, record = render_report_from_paths(
    "samples/production_data.xlsx",
    "samples/production_template.docx",
    "out/report.docx",
    meta={"prepared_by": "Automate", "date_of_issue": "2026-05-20", "report_phase": "Phase 2"},
    write_manifest=True,
)
```

## HTTP render service

**Module:** `automate/http_server.py`

```powershell
python -m automate.http_server --host 127.0.0.1 --port 8765
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | `{"status":"ok"}` |
| `/render` | POST | Multipart: `excel`, `template`, optional `meta` (JSON string) |

**Response:** Raw `.docx` bytes. Header `X-ESA-Warnings` may contain JSON array of warnings (truncated).

**Example (curl):**

```bash
curl -X POST http://127.0.0.1:8765/render \
  -F "excel=@samples/sample_data.xlsx" \
  -F "template=@samples/sample_template.docx" \
  -F 'meta={"prepared_by":"curl","date_of_issue":"2026-05-20","report_phase":"Phase 2"}' \
  -o out.docx
```

## CLI scripts

### `scripts/render_cli.py`

```powershell
python scripts\render_cli.py
python scripts\render_cli.py --excel path.xlsx --template path.docx --out out.docx `
  --prepared-by "Name" --date 2026-05-20 --phase "Phase 2"
python scripts\render_cli.py --all-rows --excel path.xlsx --template path.docx --out batch.zip
```

`--all-rows` uses `render_service.render_batch_reports` (same path as Streamlit batch generate). Writes a `.zip` of reports + manifests (+ appendices when Phase I flags apply).

Writes `out_manifest.json` beside single-report output.

### `scripts/create_samples.py`

Regenerates all files under `samples/`.

### `scripts/tag_production_template.py`

```powershell
python scripts\tag_production_template.py
python scripts\tag_production_template.py --source "merge.docx" --out samples\production_template.docx --install-root
```

### `scripts/production_e2e.py`

Production preflight + render to `samples/production_rendered.docx` (gitignored).

### `scripts/inventory_template.py`

```powershell
python scripts\inventory_template.py samples\sample_template.docx
```

### `scripts/scan_placeholder_text.py`

Finds bracket placeholders and `{{ jinja }}` in body text (debugging untagged merge docs).

### `scripts/extract_merge_fields.py`

Lists Word `MERGEFIELD` names (legacy mail-merge fields).

## `template_tools` API

```python
from template_tools import run_preflight, scan_template, missing_fields_checklist

pre = run_preflight(excel_bytes, template_bytes, meta)
assert pre.can_generate

scan = scan_template(template_bytes)
# scan.root_vars, scan.block_tags, scan.split_issues
```

## `provenance` API

```python
from provenance import build_generation_record, sha256_hex, GenerationRecord, apply_compliance_snapshot
```

Manifest compliance fields (set by `apply_compliance_snapshot` after render): `sed002_completeness_pct`, `dwda_checklist_scope`, `appendix_labels_evaluated`, `phase2_reasons`, `dwda_calc_source`.

## Power Automate integration pattern

1. Retrieve Excel + template binary from SharePoint.
2. Call Azure Function or on-premises Python using **`render_service.render_report`** or `automate.render.render_report_from_bytes`.
3. Write output `.docx` + manifest JSON to document library.
4. Do not duplicate merge logic in Power Automate expressions — keep single render path through `render_service`.

See [../AUTOMATE.md](../AUTOMATE.md).

## Error types

| Exception | When | UI handling |
|-----------|------|-------------|
| `SecurityError` | Invalid zip, size, bomb | `user_safe_error` → message |
| `ValueError` | Missing sheet, template error | Safe prefixes shown; others redacted |
| `TemplateError` (Jinja) | Wrapped as `ValueError` with generic message | |
