"""Tests for dry-run, manifests, and field contract warnings."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from engine import ReportEngine, generate_sample_excel, generate_sample_template_docx
from field_validation import contract_warnings, load_field_contract
from provenance import build_generation_record, record_filename, sha256_hex

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


class ProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        SAMPLES.mkdir(parents=True, exist_ok=True)
        xlsx = SAMPLES / "sample_data.xlsx"
        docx = SAMPLES / "sample_template.docx"
        if not xlsx.is_file():
            generate_sample_excel(str(xlsx))
        if not docx.is_file():
            generate_sample_template_docx(str(docx))
        cls.excel = xlsx.read_bytes()
        cls.template = docx.read_bytes()

    def test_sha256_stable(self) -> None:
        h = sha256_hex(b"test")
        self.assertEqual(len(h), 64)

    def test_record_filename(self) -> None:
        self.assertTrue(record_filename("Site_Phase2.docx").endswith("_manifest.json"))

    def test_dry_run_no_docx(self) -> None:
        engine = ReportEngine(excel_bytes=self.excel, template_bytes=self.template)
        ctx, warnings, record = engine.dry_run(
            meta={"report_phase": "Phase 2", "prepared_by": "T", "date_of_issue": "2026-01-01"},
            excel_filename="sample_data.xlsx",
            template_filename="sample_template.docx",
        )
        self.assertIn("site_name", ctx)
        self.assertTrue(record.dry_run)
        self.assertIsNone(record.output_sha256)
        data = json.loads(record.to_json_bytes())
        self.assertEqual(data["app_name"], "esa-report-generator")

    def test_render_includes_manifest(self) -> None:
        engine = ReportEngine(excel_bytes=self.excel, template_bytes=self.template)
        docx, _w, _ctx, record = engine.render(
            meta={"report_phase": "Phase 2", "prepared_by": "T", "date_of_issue": "2026-01-01"}
        )
        self.assertGreater(len(docx), 1000)
        self.assertFalse(record.dry_run)
        self.assertIsNotNone(record.output_sha256)

    def test_field_contract_loads(self) -> None:
        contract = load_field_contract()
        self.assertIn("sheets", contract)
        self.assertIn("ProjectData", contract["sheets"])

    def test_contract_warnings_empty_site(self) -> None:
        warnings = contract_warnings({"client_name": "X"}, report_phase="Phase 2")
        self.assertTrue(any("site_name" in w for w in warnings))

    def test_build_generation_record(self) -> None:
        engine = ReportEngine(excel_bytes=self.excel, template_bytes=self.template)
        cov = engine.coverage({"report_phase": "Phase 2"})
        rec = build_generation_record(
            excel_bytes=self.excel,
            template_bytes=self.template,
            meta={"report_phase": "Phase 2", "template_version": "1.0.0"},
            coverage=cov,
            warnings=[],
            missing_variables=[],
            dry_run=True,
        )
        self.assertEqual(rec.template_version, "1.0.0")
        self.assertGreater(rec.template_var_count, 0)


if __name__ == "__main__":
    unittest.main()
