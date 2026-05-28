"""E2E render for both new Phase 1 site PDF markup templates."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["ESA_ALLOW_LARGE_TEMPLATE"] = "1"

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import ReportEngine  # noqa: E402
from template_tools import run_preflight  # noqa: E402

PAIRS = [
    (
        ROOT / "samples" / "phase1_251106R_data.xlsx",
        ROOT
        / "samples"
        / "251106R - 15-20-049-10 W5M - Phase 1 ESA_Final_Secure-markup.docx",
        ROOT / "out" / "phase1_251106R_rendered.docx",
    ),
    (
        ROOT / "samples" / "phase1_260109R_data.xlsx",
        ROOT
        / "samples"
        / "260109R - 16-34-055-02W4M Phase 1 ESA_Final_Secure-markup.docx",
        ROOT / "out" / "phase1_260109R_rendered.docx",
    ),
]

META = {
    "prepared_by": "Ecoventure E2E",
    "date_of_issue": "2026-05-27",
    "report_phase": "Phase 1",
    "template_version": "1.0.0",
}


def render_one(xlsx: Path, template: Path, out: Path) -> int:
    if not xlsx.is_file():
        print(f"Missing Excel: {xlsx}", file=sys.stderr)
        return 1
    if not template.is_file():
        print(f"Missing template: {template}", file=sys.stderr)
        print("Run: python scripts\\phase1_pdf_to_markup.py", file=sys.stderr)
        return 1

    excel_bytes = xlsx.read_bytes()
    template_bytes = template.read_bytes()
    pre = run_preflight(excel_bytes, template_bytes, META)
    print(f"{template.name}: preflight can_generate={pre.can_generate}")
    if not pre.can_generate:
        for e in pre.errors:
            print(f"  error: {e}")
        return 1

    engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=template_bytes)
    docx_bytes, warnings, _ctx, record = engine.render(
        meta=META,
        excel_filename=xlsx.name,
        template_filename=template.name,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(docx_bytes)
    manifest = out.with_name(out.stem + "_manifest.json")
    from provenance import sha256_hex

    record.output_filename = out.name
    record.output_sha256 = sha256_hex(docx_bytes)
    manifest.write_bytes(record.to_json_bytes())
    print(f"  Wrote: {out} ({len(docx_bytes):,} bytes)")
    if warnings:
        print(f"  Warnings: {len(warnings)}")
    return 0


def main() -> int:
    rc = 0
    for xlsx, tpl, out in PAIRS:
        print(f"\n--- {xlsx.name} + {tpl.name} ---")
        if render_one(xlsx, tpl, out) != 0:
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
