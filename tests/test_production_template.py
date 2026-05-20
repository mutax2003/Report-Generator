"""Production template render and preflight."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestProductionTemplate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.xlsx = ROOT / "samples" / "production_data.xlsx"
        cls.tpl = ROOT / "samples" / "production_template.docx"
        if not cls.xlsx.is_file() or not cls.tpl.is_file():
            raise unittest.SkipTest("Run scripts/create_samples.py and tag_production_template.py")

    def test_preflight_and_render(self) -> None:
        from engine import ReportEngine
        from template_tools import run_preflight

        excel_bytes = self.xlsx.read_bytes()
        template_bytes = self.tpl.read_bytes()
        meta = {
            "prepared_by": "Test",
            "date_of_issue": "2026-05-20",
            "report_phase": "Phase 2",
        }
        pre = run_preflight(excel_bytes, template_bytes, meta)
        self.assertTrue(pre.can_generate, pre.errors)
        engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=template_bytes)
        docx, warnings, _ctx, record = engine.render(meta=meta)
        self.assertGreater(len(docx), 1000)
        self.assertIsNotNone(record.output_sha256 or record.excel_sha256)


if __name__ == "__main__":
    unittest.main()
