# Automation ingress (Power Automate & scripts)

Full reference: [docs/06-api-reference.md](docs/06-api-reference.md)

The Streamlit app is for interactive use. For M365 automation, call the same **`ReportEngine`** via the `automate` package.

## Python API

```python
from automate.render import render_report_from_paths

warnings, record = render_report_from_paths(
    "samples/production_data.xlsx",
    "samples/production_template.docx",
    "out/report.docx",
    meta={
        "prepared_by": "Jane Doe",
        "date_of_issue": "2026-05-20",
        "report_phase": "Phase 2",
        "template_version": "1.0.0",
    },
)
```

Or pass bytes directly: `render_report_from_bytes(excel_bytes, template_bytes, meta=...)`.

## CLI (unchanged)

```powershell
python scripts\render_cli.py --excel samples\production_data.xlsx --template samples\production_template.docx --out out.docx
```

Production smoke test:

```powershell
python scripts\production_e2e.py
```

## Local HTTP service (testing / desktop flows)

```powershell
python -m automate.http_server --port 8765
```

- `GET /health` — liveness
- `POST /render` — `multipart/form-data` fields:
  - `excel` — `.xlsx` file
  - `template` — `.docx` file
  - `meta` — optional JSON string (`prepared_by`, `date_of_issue`, `report_phase`, …)

Response body is the rendered `.docx`. Warnings may appear in header `X-ESA-Warnings`.

**Security:** bind `127.0.0.1` only unless behind VPN or authenticated reverse proxy.

## Power Automate (outline)

1. **Store** Excel and Word template (SharePoint / OneDrive).
2. **Get file content** for both.
3. **Run script** or **HTTP** action:
   - Desktop: `python -m automate.render` wrapper script with temp paths, or POST to local `http_server` on a secured machine.
   - Cloud: deploy `automate/render.py` in an Azure Function; pass base64 file bodies; return `.docx`.
4. **Save** output to SharePoint; attach manifest JSON from `GenerationRecord.to_json_bytes()` if audit is required.

Only the data ingress changes; **`engine.py`** stays the single merge implementation.

## Tagging the full merge document

When `22xxxxR Phase 2 ESA Full_merge.docx` is available at project root:

```powershell
python scripts\tag_production_template.py --source "22xxxxR Phase 2 ESA Full_merge.docx" --out samples\production_template.docx
```

Without the merge file, the script generates `samples/production_template.docx` from the field guide.
