"""
CI smoke: render_cli --package and assert deliverable zip contains appendix D.

Run: python scripts/phase1_package_smoke.py
"""

from __future__ import annotations

import sys
import zipfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deliverable_pack import build_deliverable_zip_bytes  # noqa: E402
from engine import ReportEngine  # noqa: E402
from appendix_generator import attach_appendices_to_record  # noqa: E402


def main() -> int:
    xlsx = ROOT / "samples" / "phase1_alberta_data.xlsx"
    tpl = ROOT / "samples" / "phase1_alberta_template.docx"
    if not xlsx.is_file() or not tpl.is_file():
        print("FAIL: run scripts/create_samples.py first")
        return 1

    meta = {
        "report_phase": "Phase 1",
        "report_type": "phase1_alberta",
        "prepared_by": "Ecoventure",
        "date_of_issue": "2026-06-10",
    }
    engine = ReportEngine(xlsx.read_bytes(), tpl.read_bytes())
    docx, warnings, ctx, record = engine.render(meta=meta)
    _generated, merged, ap_warnings = attach_appendices_to_record(
        record, ctx, meta, []
    )
    if ap_warnings:
        print("FAIL: appendix warnings:", ap_warnings)
        return 1

    zip_bytes = build_deliverable_zip_bytes(
        docx,
        "phase1_alberta_report.docx",
        ctx,
        meta,
        record.to_json_bytes(),
        merged,
    )
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
    if not any(n.startswith("appendices/D_") for n in names):
        print("FAIL: zip missing appendices/D_* — got:", names[:20])
        return 1
    if not any(n.startswith("onestop/") for n in names):
        print("FAIL: zip missing onestop/")
        return 1

    print("OK: deliverable package zip contains appendix D and onestop export")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
