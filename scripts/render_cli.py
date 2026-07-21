"""CLI smoke test: render samples (or custom paths) to a .docx file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from appendix_generator import phase1_profile_includes_appendices  # noqa: E402
from automate.render import render_report_from_bytes  # noqa: E402
from deliverable_pack import build_deliverable_zip_bytes  # noqa: E402
from provenance import sha256_hex  # noqa: E402


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
    parser.add_argument(
        "--all-rows",
        action="store_true",
        help="Render one .docx per ProjectData row; writes --out as a .zip",
    )
    parser.add_argument(
        "--appendices",
        action="store_true",
        help="Generate Phase I appendices D/G and include in deliverable zip when --package is set",
    )
    parser.add_argument(
        "--no-appendices",
        action="store_true",
        help="Skip auto-generated appendices even for Phase I profiles",
    )
    parser.add_argument(
        "--package",
        action="store_true",
        help="Also write deliverable package .zip (report + manifest + appendices + onestop/)",
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
    include_appendices = phase1_profile_includes_appendices(
        meta.get("report_type", ""), meta.get("report_phase", "")
    )
    if args.appendices:
        include_appendices = True
    if args.no_appendices:
        include_appendices = False

    excel_bytes = args.excel.read_bytes()
    template_bytes = args.template.read_bytes()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    if args.all_rows:
        from deliverable_pack import build_batch_reports_zip
        from render_service import RenderRequest, render_batch_reports

        batch = render_batch_reports(
            RenderRequest(
                excel_bytes=excel_bytes,
                template_bytes=template_bytes,
                meta=meta,
                excel_filename=args.excel.name,
                template_filename=args.template.name,
                include_appendices=include_appendices,
            )
        )
        zip_path = args.out if args.out.suffix.lower() == ".zip" else args.out.with_suffix(".zip")
        zip_path.write_bytes(
            build_batch_reports_zip(
                [
                    (
                        item.filename,
                        item.docx_bytes,
                        item.record.to_json_bytes(),
                        item.appendices,
                    )
                    for item in batch
                ]
            )
        )
        print(f"Wrote batch zip ({len(batch)} reports): {zip_path}")
        for item in batch:
            for w in item.warnings[:3]:
                print(f"  WARN [{item.filename}]: {w}")
        return 0

    docx_bytes, warnings, context, record, appendices = render_report_from_bytes(
        excel_bytes,
        template_bytes,
        meta=meta,
        excel_filename=args.excel.name,
        template_filename=args.template.name,
        include_appendices=include_appendices,
    )
    record.output_filename = args.out.name
    record.output_sha256 = sha256_hex(docx_bytes)
    manifest_bytes = record.to_json_bytes()

    args.out.write_bytes(docx_bytes)
    manifest_path = args.out.with_name(args.out.stem + "_manifest.json")
    manifest_path.write_bytes(manifest_bytes)

    print(f"Wrote: {args.out} ({len(docx_bytes)} bytes)")
    print(f"Manifest: {manifest_path}")
    if record.generated_appendix_files:
        print(
            "Generated appendices: "
            f"{[a['label'] for a in record.generated_appendix_files]}"
        )

    if args.package:
        zip_path = args.out.with_name(args.out.stem + "_package.zip")
        zip_path.write_bytes(
            build_deliverable_zip_bytes(
                docx_bytes,
                args.out.name,
                context,
                meta,
                manifest_bytes,
                appendices,
            )
        )
        print(f"Package: {zip_path}")

    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"  - {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
