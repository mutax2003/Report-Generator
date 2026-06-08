"""E2E: Alberta Phase II Ecoventure sample render."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import ReportEngine  # noqa: E402
from template_tools import run_preflight  # noqa: E402

XLSX = ROOT / "samples" / "phase2_alberta_data.xlsx"
TEMPLATE = ROOT / "samples" / "phase2_alberta_template.docx"
OUT = ROOT / "samples" / "phase2_alberta_rendered.docx"


def main() -> int:
    if not XLSX.is_file() or not TEMPLATE.is_file():
        print("Run scripts/create_samples.py first", file=sys.stderr)
        return 1

    meta = {
        "prepared_by": "Ecoventure E2E",
        "date_of_issue": "2026-06-08",
        "report_phase": "Phase 2",
        "report_type": "phase2_esa",
        "template_version": "1.0.0",
    }
    excel_bytes = XLSX.read_bytes()
    template_bytes = TEMPLATE.read_bytes()
    pre = run_preflight(excel_bytes, template_bytes, meta)
    print(f"Preflight can_generate={pre.can_generate}")
    if pre.phase2:
        print(f"Phase II checklist: {pre.phase2.completeness_pct}%")
    if not pre.can_generate:
        for e in pre.errors:
            print(f"  error: {e}")
        return 1

    engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=template_bytes)
    docx_bytes, warnings, ctx, record = engine.render(
        meta=meta,
        excel_filename=XLSX.name,
        template_filename=TEMPLATE.name,
    )
    OUT.write_bytes(docx_bytes)
    from provenance import sha256_hex

    record.output_filename = OUT.name
    record.output_sha256 = sha256_hex(docx_bytes)
    OUT.with_name(OUT.stem + "_manifest.json").write_bytes(record.to_json_bytes())
    print(f"Wrote: {OUT} ({len(docx_bytes)} bytes)")
    if ctx.get("exceedance_summary"):
        print(f"Exceedances: {ctx.get('exceedance_summary')}")
    if warnings:
        print("Warnings:", *warnings[:8], sep="\n  ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
