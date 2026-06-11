"""E2E: Alberta Phase I Ecoventure sample render."""

from __future__ import annotations

import sys
import zipfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from appendix_generator import render_phase1_appendices  # noqa: E402
from deliverable_pack import build_deliverable_zip_bytes  # noqa: E402
from engine import ReportEngine  # noqa: E402
from template_tools import run_preflight  # noqa: E402

XLSX = ROOT / "samples" / "phase1_alberta_data.xlsx"
TEMPLATE = ROOT / "samples" / "phase1_alberta_template.docx"
OUT = ROOT / "samples" / "phase1_alberta_rendered.docx"
PKG = OUT.with_name(OUT.stem + "_package.zip")


def main() -> int:
    if not XLSX.is_file() or not TEMPLATE.is_file():
        print("Run scripts/create_samples.py first", file=sys.stderr)
        return 1

    meta = {
        "prepared_by": "Ecoventure E2E",
        "date_of_issue": "2026-05-20",
        "report_phase": "Phase 1",
        "report_type": "phase1_alberta",
        "template_version": "1.0.0",
    }
    excel_bytes = XLSX.read_bytes()
    template_bytes = TEMPLATE.read_bytes()
    pre = run_preflight(excel_bytes, template_bytes, meta)
    print(f"Preflight can_generate={pre.can_generate}")
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
    appendices, ap_warnings = render_phase1_appendices(ctx, meta)
    labels = {a.label for a in appendices}
    if labels != {"D", "G"}:
        print(f"Appendix labels expected D,G got {labels}", file=sys.stderr)
        return 1

    OUT.write_bytes(docx_bytes)
    manifest = OUT.with_name(OUT.stem + "_manifest.json")
    from provenance import sha256_hex

    record.output_filename = OUT.name
    record.output_sha256 = sha256_hex(docx_bytes)
    manifest_bytes = record.to_json_bytes()
    manifest.write_bytes(manifest_bytes)
    PKG.write_bytes(
        build_deliverable_zip_bytes(
            docx_bytes,
            OUT.name,
            ctx,
            meta,
            manifest_bytes,
            appendices,
        )
    )
    with zipfile.ZipFile(BytesIO(PKG.read_bytes())) as zf:
        names = zf.namelist()
    assert any(n.startswith("appendices/D_") for n in names)
    assert any(n.startswith("appendices/G_") for n in names)

    print(f"Wrote: {OUT} ({len(docx_bytes)} bytes)")
    print(f"Appendices: {sorted(labels)}")
    print(f"Package: {PKG}")
    if warnings or ap_warnings:
        print("Warnings:", *(warnings + ap_warnings)[:10], sep="\n  ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
