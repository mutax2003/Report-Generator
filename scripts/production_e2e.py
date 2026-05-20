"""End-to-end production render: production_data.xlsx + production_template.docx."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import ReportEngine  # noqa: E402
from template_tools import run_preflight  # noqa: E402

SAMPLES = ROOT / "samples"
XLSX = SAMPLES / "production_data.xlsx"
TEMPLATE = SAMPLES / "production_template.docx"
MERGE_TEMPLATE = ROOT / "22xxxxR Phase 2 ESA Full_merge.docx"
OUT = SAMPLES / "production_rendered.docx"


def main() -> int:
    if not XLSX.is_file():
        print(f"Missing {XLSX}; run scripts/create_samples.py", file=sys.stderr)
        return 1

    tpl = MERGE_TEMPLATE if MERGE_TEMPLATE.is_file() else TEMPLATE
    if not tpl.is_file():
        print("No production template; run scripts/tag_production_template.py", file=sys.stderr)
        return 1

    excel_bytes = XLSX.read_bytes()
    template_bytes = tpl.read_bytes()
    meta = {
        "prepared_by": "Production E2E",
        "date_of_issue": "2026-05-20",
        "report_phase": "Phase 2",
        "template_version": "1.0.0",
    }

    pre = run_preflight(excel_bytes, template_bytes, meta)
    cov = pre.coverage
    missing = cov.missing_in_data if cov else []
    matched = len(cov.matched) if cov else 0
    print(
        f"Preflight: can_generate={pre.can_generate} matched={matched} "
        f"missing={len(missing)} errors={len(pre.errors)}"
    )
    for err in pre.errors:
        print(f"  error: {err}")
    if missing:
        for v in missing[:20]:
            print(f"  missing: {v}")
        if len(missing) > 20:
            print(f"  ... +{len(missing) - 20} more")

    engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=template_bytes)
    docx_bytes, warnings, _ctx, record = engine.render(
        meta=meta,
        excel_filename=XLSX.name,
        template_filename=tpl.name,
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(docx_bytes)
    manifest = OUT.with_name(OUT.stem + "_manifest.json")
    record.output_filename = OUT.name
    from provenance import sha256_hex

    record.output_sha256 = sha256_hex(docx_bytes)
    manifest.write_bytes(record.to_json_bytes())

    print(f"Wrote: {OUT} ({len(docx_bytes)} bytes)")
    print(f"Manifest: {manifest}")
    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"  - {w}")
    return 0 if pre.can_generate else 1


if __name__ == "__main__":
    raise SystemExit(main())
