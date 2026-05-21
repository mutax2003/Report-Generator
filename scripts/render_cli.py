"""CLI smoke test: render samples (or custom paths) to a .docx file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import ReportEngine  # noqa: E402
from template_attachments import prepare_template_upload  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Render ESA report from Excel + template.")
    parser.add_argument(
        "--excel",
        type=Path,
        default=ROOT / "samples" / "sample_data.xlsx",
        help="Path to .xlsx data file",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=ROOT / "samples" / "sample_template.docx",
        help="Path to .docx template",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "samples" / "rendered_output.docx",
        help="Output .docx path",
    )
    parser.add_argument("--prepared-by", default="CLI Test")
    parser.add_argument("--date", default="2026-05-19")
    parser.add_argument("--phase", default="Phase 2")
    parser.add_argument(
        "--report-type",
        default="",
        help="Profile id: phase1_alberta, phase2_esa, template_driven (default from --phase)",
    )
    args = parser.parse_args()

    if not args.excel.is_file():
        print(f"Excel not found: {args.excel}", file=sys.stderr)
        return 1
    if not args.template.is_file():
        print(f"Template not found: {args.template}", file=sys.stderr)
        return 1

    meta = {
        "prepared_by": args.prepared_by,
        "date_of_issue": args.date,
        "report_phase": args.phase,
    }
    if args.report_type:
        meta["report_type"] = args.report_type
    prepared = prepare_template_upload(
        args.template.read_bytes(),
        args.template.name,
    )
    if prepared.warnings:
        for w in prepared.warnings:
            print(f"Note: {w}")
    engine = ReportEngine(
        excel_bytes=args.excel.read_bytes(),
        template_bytes=prepared.docx_bytes,
    )
    docx_bytes, warnings, _context, record = engine.render(
        meta=meta,
        excel_filename=args.excel.name,
        template_filename=args.template.name,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(docx_bytes)
    manifest_path = args.out.with_name(args.out.stem + "_manifest.json")
    record.output_filename = args.out.name
    from provenance import sha256_hex

    record.output_sha256 = sha256_hex(docx_bytes)
    manifest_path.write_bytes(record.to_json_bytes())

    print(f"Wrote: {args.out} ({len(docx_bytes)} bytes)")
    print(f"Manifest: {manifest_path}")
    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"  - {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
