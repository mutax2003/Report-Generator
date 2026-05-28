"""
Test Excel + Word template pair: preflight, dry-run summary, render (no Streamlit).

Defaults to Alberta Phase I Ecoventure samples. Use --excel and --template for your files.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Large Phase 1 templates converted from PDF may exceed default upload cap.
os.environ.setdefault("ESA_ALLOW_LARGE_TEMPLATE", "1")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._deps import require_project_deps  # noqa: E402

require_project_deps(ROOT)

from engine import ReportEngine  # noqa: E402
from template_tools import missing_fields_checklist, run_preflight  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Excel + Word template merge.")
    parser.add_argument(
        "--excel",
        type=Path,
        default=ROOT / "samples" / "phase1_alberta_data.xlsx",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=ROOT / "samples" / "phase1_alberta_template.docx",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "out" / "test_output.docx",
    )
    parser.add_argument("--phase", default="Phase 1")
    parser.add_argument("--prepared-by", default="Ecoventure Test")
    parser.add_argument("--date", default="2026-05-20")
    parser.add_argument("--template-version", default="1.0.0")
    parser.add_argument("--dry-run-only", action="store_true")
    args = parser.parse_args()

    if not args.excel.is_file():
        print(f"Excel not found: {args.excel}", file=sys.stderr)
        print("Run: python scripts\\prepare_user_test_pack.py", file=sys.stderr)
        return 1
    if not args.template.is_file():
        print(f"Template not found: {args.template}", file=sys.stderr)
        return 1

    meta = {
        "prepared_by": args.prepared_by,
        "date_of_issue": args.date,
        "report_phase": args.phase,
        "template_version": args.template_version,
    }
    excel_bytes = args.excel.read_bytes()
    template_bytes = args.template.read_bytes()

    print(f"Excel:     {args.excel}")
    print(f"Template:  {args.template}")
    print(f"Phase:     {args.phase}")
    print()

    pre = run_preflight(excel_bytes, template_bytes, meta)
    print("--- Pre-flight ---")
    if pre.sheet_names:
        print(f"Sheets: {', '.join(pre.sheet_names)}")
    for err in pre.errors:
        print(f"ERROR: {err}")
    for warn in pre.warnings:
        print(f"WARN:  {warn}")
    cov = pre.coverage
    if cov:
        print(f"Tags: {pre.template_var_count} | Matched: {len(cov.matched)} | Missing: {len(cov.missing_in_data)}")
        if args.phase.strip() == "Phase 1":
            print(
                f"Rows: drilling_waste={cov.drilling_waste_row_count} "
                f"storage_tanks={cov.storage_tanks_row_count}"
            )
        else:
            print(f"Rows: lab_results={cov.lab_row_count}")
        if cov.missing_in_data:
            print("Missing tags:", ", ".join(cov.missing_in_data))
            checklist = ROOT / "out" / "missing_fields_checklist.txt"
            checklist.parent.mkdir(parents=True, exist_ok=True)
            checklist.write_text(missing_fields_checklist(cov), encoding="utf-8")
            print(f"Wrote checklist: {checklist}")

    if not pre.can_generate:
        print("\nCannot render until pre-flight errors are fixed.")
        return 1

    engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=template_bytes)
    context, dry_warnings, dry_record = engine.dry_run(
        meta=meta,
        excel_filename=args.excel.name,
        template_filename=args.template.name,
    )
    print("\n--- Dry run (no Word file) ---")
    scalar_keys = [
        k
        for k in sorted(context)
        if k not in ("lab_results", "drilling_waste", "storage_tanks")
    ]
    for k in scalar_keys[:12]:
        v = str(context[k])[:80]
        print(f"  {k}: {v}")
    if len(scalar_keys) > 12:
        print(f"  ... +{len(scalar_keys) - 12} more keys")
    for list_key in ("lab_results", "drilling_waste", "storage_tanks"):
        rows = context.get(list_key)
        if isinstance(rows, list):
            print(f"  {list_key}: {len(rows)} row(s)")
    for w in dry_warnings[:8]:
        print(f"  WARN: {w}")

    if args.dry_run_only:
        manifest = args.out.with_name(args.out.stem + "_dryrun_manifest.json")
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_bytes(dry_record.to_json_bytes())
        print(f"\nDry-run manifest: {manifest}")
        return 0

    print("\n--- Render ---")
    docx_bytes, warnings, _ctx, record = engine.render(
        meta=meta,
        excel_filename=args.excel.name,
        template_filename=args.template.name,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(docx_bytes)
    record.output_filename = args.out.name
    from provenance import sha256_hex

    record.output_sha256 = sha256_hex(docx_bytes)
    manifest_path = args.out.with_name(args.out.stem + "_manifest.json")
    manifest_path.write_bytes(record.to_json_bytes())

    print(f"Wrote: {args.out} ({len(docx_bytes)} bytes)")
    print(f"Manifest: {manifest_path}")
    if warnings:
        print(f"Warnings ({len(warnings)}):")
        for w in warnings[:10]:
            print(f"  - {w}")
    print("\nOpen the .docx in Word to verify fields and tables.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
