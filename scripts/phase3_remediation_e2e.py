"""E2E: Phase III remediation sample render."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import ReportEngine  # noqa: E402
from template_tools import run_preflight  # noqa: E402

XLSX = ROOT / "samples" / "phase3_remediation_data.xlsx"
TEMPLATE = ROOT / "samples" / "phase3_remediation_template.docx"
OUT = ROOT / "samples" / "phase3_remediation_rendered.docx"


def main() -> int:
    if not XLSX.is_file() or not TEMPLATE.is_file():
        print("Run scripts/create_samples.py first", file=sys.stderr)
        return 1

    meta = {
        "prepared_by": "Ecoventure E2E",
        "date_of_issue": "2026-06-08",
        "report_phase": "Phase 2",
        "report_type": "phase3_remediation",
    }
    excel_bytes = XLSX.read_bytes()
    template_bytes = TEMPLATE.read_bytes()
    pre = run_preflight(excel_bytes, template_bytes, meta)
    print(f"Preflight can_generate={pre.can_generate}")
    if not pre.can_generate:
        for e in pre.errors:
            print(f"  error: {e}")
        return 1

    docx_bytes, warnings, ctx, record = ReportEngine(
        excel_bytes, template_bytes
    ).render(meta=meta, excel_filename=XLSX.name, template_filename=TEMPLATE.name)
    OUT.write_bytes(docx_bytes)
    from provenance import sha256_hex

    record.output_filename = OUT.name
    record.output_sha256 = sha256_hex(docx_bytes)
    OUT.with_name(OUT.stem + "_manifest.json").write_bytes(record.to_json_bytes())
    print(f"Wrote: {OUT} ({len(docx_bytes)} bytes)")
    print(f"Confirmatory status: {ctx.get('confirmatory_status', '')}")
    if warnings:
        print("Warnings:", *warnings[:6], sep="\n  ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
