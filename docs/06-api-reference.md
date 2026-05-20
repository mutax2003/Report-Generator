# 06 — API and automation reference

Programmatic interfaces for rendering reports without the Streamlit UI.

## `ReportEngine` (primary API)

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
| `render(meta, excel_filename=..., template_filename=...)` | `(docx_bytes, warnings, context, GenerationRecord)` | Full merge |
| `coverage(meta)` | `TemplateCoverage` | Tag match analysis |
| `template_root_vars()` | `set[str]` | Root `{{ var }}` names from template |
| `missing_template_vars(context)` | `list[str]` | Sorted missing keys |

### Meta dict keys

| Key | Example | Notes |
|-----|---------|-------|
| `prepared_by` | `"Jane Doe"` | Sanitized, max 500 chars |
| `date_of_issue` | `"2026-05-20"` | ISO date string |
| `report_phase` | `"Phase 2"` | `"Phase 1"` skips required lab sheet |
| `template_version` | `"2.1.0"` | Stored in manifest |

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

**Module:** `automate/render.py`

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
```

Writes `out_manifest.json` beside output.

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
from provenance import build_generation_record, sha256_hex, GenerationRecord
```

## Power Automate integration pattern

1. Retrieve Excel + template binary from SharePoint.
2. Call Azure Function or on-premises Python using `render_report_from_bytes`.
3. Write output `.docx` + manifest JSON to document library.
4. Do not duplicate merge logic in Power Automate expressions — keep single `ReportEngine` path.

See [../AUTOMATE.md](../AUTOMATE.md).

## Error types

| Exception | When | UI handling |
|-----------|------|-------------|
| `SecurityError` | Invalid zip, size, bomb | `user_safe_error` → message |
| `ValueError` | Missing sheet, template error | Safe prefixes shown; others redacted |
| `TemplateError` (Jinja) | Wrapped as `ValueError` with generic message | |
