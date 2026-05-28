"""E2E smoke test for groundwater_monitoring profile."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import ReportEngine, generate_groundwater_monitoring_excel, generate_groundwater_monitoring_template_docx
from template_tools import run_preflight


def main() -> int:
    xlsx = ROOT / "samples" / "groundwater_monitoring_data.xlsx"
    tpl = ROOT / "samples" / "groundwater_monitoring_template.docx"
    out = ROOT / "samples" / "groundwater_monitoring_rendered.docx"

    if not xlsx.is_file() or not tpl.is_file():
        generate_groundwater_monitoring_excel(str(xlsx))
        generate_groundwater_monitoring_template_docx(str(tpl))

    meta = {
        "report_type": "groundwater_monitoring",
        "report_phase": "Phase 1",
        "prepared_by": "Ecoventure QP",
        "date_of_issue": "2026-05-28",
    }
    xb, tb = xlsx.read_bytes(), tpl.read_bytes()
    pre = run_preflight(xb, tb, meta)
    print(f"Preflight can_generate={pre.can_generate} errors={len(pre.errors)}")
    if not pre.can_generate:
        for e in pre.errors:
            print(f"  ERROR: {e}")
        return 1

    engine = ReportEngine(xb, tb)
    docx, warnings, ctx, record = engine.render(meta=meta)
    out.write_bytes(docx)
    manifest = out.with_suffix("").name + "_manifest.json"
    (ROOT / "samples" / f"{manifest}").write_bytes(record.to_json_bytes())
    print(f"Wrote: {out} ({len(docx)} bytes)")
    print(f"well_count={ctx.get('well_count')} exceedances in summary")
    if warnings:
        print(f"Warnings ({len(warnings)}):")
        for w in warnings[:5]:
            print(f"  - {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
