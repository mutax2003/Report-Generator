"""
E2E: DWDA calculation and generation workflow (Excel → preflight → appendices → package).

Validates the consultant path in docs/21-dwda-directive-050-compliance.md:
  populate Excel → preflight + QP checklist → appendix H → render D/G + OneStop.
"""

from __future__ import annotations

import json
import sys
import zipfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from appendix_generator import attach_appendices_to_record  # noqa: E402
from deliverable_pack import (  # noqa: E402
    AppendixFile,
    build_deliverable_zip_bytes,
    build_onestop_phase1_summary,
)
from dwda_compliance import build_dwda_qp_checklist_markdown  # noqa: E402
from engine import ReportEngine  # noqa: E402
from provenance import sha256_hex  # noqa: E402
from template_tools import run_preflight  # noqa: E402

from ecoventure_workbook import merge_into_engine_excel  # noqa: E402

XLSX = ROOT / "samples" / "phase1_alberta_data.xlsx"
ECO_FIXTURE = ROOT / "samples" / "ecoventure_dwda" / "minimal_calc_workbook.xlsx"
TEMPLATE = ROOT / "samples" / "phase1_alberta_template.docx"
OUT_DIR = ROOT / "out" / "dwda_workflow"


def main() -> int:
    if not XLSX.is_file() or not TEMPLATE.is_file():
        print("Run scripts/create_samples.py first", file=sys.stderr)
        return 1

    meta = {
        "prepared_by": "Ecoventure DWDA E2E",
        "date_of_issue": "2026-06-10",
        "report_phase": "Phase 1",
        "report_type": "phase1_alberta",
    }
    excel_bytes = XLSX.read_bytes()
    if ECO_FIXTURE.is_file():
        excel_bytes = merge_into_engine_excel(excel_bytes, ECO_FIXTURE.read_bytes())
        print("Merged Ecoventure fixture workbook into Excel")
    template_bytes = TEMPLATE.read_bytes()

    # Step 1: preflight (appendix H uploaded — satisfies site sketch requirement)
    appendix_h = AppendixFile(
        label="H",
        data=b"%PDF-1.4 minimal site sketch placeholder",
        filename="appendix_h_site_sketch.pdf",
        format="pdf",
        source="uploaded",
    )
    pre = run_preflight(
        excel_bytes,
        template_bytes,
        meta,
        appendix_labels_present={"H"},
    )
    print("--- Pre-flight (with Appendix H) ---")
    print(f"can_generate={pre.can_generate}")
    if not pre.dwda:
        print("ERROR: DWDA preflight block missing", file=sys.stderr)
        return 1
    print(
        f"scope={pre.dwda.checklist_scope} "
        f"complete={pre.dwda.completeness_pct}% "
        f"({pre.dwda.satisfied_count}/{pre.dwda.total_items})"
    )
    if pre.dwda.phase2_reasons:
        print("Phase II hints:", *pre.dwda.phase2_reasons[:3], sep="\n  ")
    if not pre.can_generate:
        for e in pre.errors:
            print(f"  error: {e}")
        return 1

    # Step 2: QP checklist markdown export
    qp_md = build_dwda_qp_checklist_markdown(pre.dwda)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    qp_path = OUT_DIR / "dwda_qp_checklist.md"
    qp_path.write_text(qp_md, encoding="utf-8")
    print(f"Wrote QP checklist: {qp_path}")

    # Step 3: render report + appendices D/G with uploaded H
    engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=template_bytes)
    docx_bytes, warnings, ctx, record = engine.render(
        meta=meta,
        excel_filename=XLSX.name,
        template_filename=TEMPLATE.name,
        appendix_labels_present={"H"},
    )
    required_keys = (
        "dwda_compliance_summary",
        "dwda_checklist_scope",
        "dwda_checklist_results",
        "dwda_guideline_summary",
        "dwda_calc_summary",
    )
    for key in required_keys:
        if key not in ctx:
            print(f"ERROR: missing context key {key}", file=sys.stderr)
            return 1

    generated, merged, ap_warnings = attach_appendices_to_record(
        record, ctx, meta, [appendix_h]
    )
    labels = {a.label for a in merged}
    if not {"A", "D", "G", "H"}.issubset(labels):
        print(f"ERROR: expected appendices A,D,G,H got {sorted(labels)}", file=sys.stderr)
        return 1

    # Step 4: deliverable package + OneStop summary
    onestop = build_onestop_phase1_summary(ctx, meta)
    for field in (
        "dwda_compliance_option",
        "dwda_checklist_scope",
        "dwda_checklist_complete",
        "cuttings_volume_on_lease_m3",
        "dwda_calc_summary",
    ):
        if not str(onestop.get(field, "")).strip():
            print(f"WARN: OneStop field empty: {field}")

    out_docx = OUT_DIR / "phase1_dwda_rendered.docx"
    out_docx.write_bytes(docx_bytes)
    record.output_filename = out_docx.name
    record.output_sha256 = sha256_hex(docx_bytes)
    manifest_bytes = record.to_json_bytes()
    pkg_bytes = build_deliverable_zip_bytes(
        docx_bytes,
        out_docx.name,
        ctx,
        meta,
        manifest_bytes,
        merged,
    )
    pkg_path = OUT_DIR / "phase1_dwda_package.zip"
    pkg_path.write_bytes(pkg_bytes)
    onestop_path = OUT_DIR / "onestop_summary.json"
    onestop_path.write_text(json.dumps(onestop, indent=2), encoding="utf-8")

    with zipfile.ZipFile(BytesIO(pkg_bytes)) as zf:
        names = zf.namelist()
    assert any(n.startswith("appendices/D_") for n in names), names
    assert any(n.startswith("appendices/G_") for n in names), names
    assert any(n.startswith("appendices/H_") for n in names), names
    assert any(n.startswith("qp_templates/") for n in names), names

    print(f"Wrote report: {out_docx} ({len(docx_bytes)} bytes)")
    print(f"Appendices: {sorted(labels)}")
    print(f"Package: {pkg_path}")
    print(f"OneStop summary: {onestop_path}")
    if warnings or ap_warnings:
        print(f"Warnings: {len(warnings) + len(ap_warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
