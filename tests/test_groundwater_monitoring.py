"""Groundwater monitoring profile render and context."""

from __future__ import annotations

import unittest
from pathlib import Path

from engine import ReportEngine, generate_groundwater_monitoring_excel, generate_groundwater_monitoring_template_docx

ROOT = Path(__file__).resolve().parents[1]


class TestGroundwaterMonitoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        samples = ROOT / "samples"
        cls.xlsx = samples / "groundwater_monitoring_data.xlsx"
        cls.tpl = samples / "groundwater_monitoring_template.docx"
        if not cls.xlsx.is_file():
            generate_groundwater_monitoring_excel(str(cls.xlsx))
        if not cls.tpl.is_file():
            generate_groundwater_monitoring_template_docx(str(cls.tpl))

    def test_build_context_stats(self) -> None:
        engine = ReportEngine(
            excel_bytes=self.xlsx.read_bytes(),
            template_bytes=self.tpl.read_bytes(),
        )
        ctx = engine.build_context(
            {
                "report_type": "groundwater_monitoring",
                "report_phase": "Phase 1",
                "prepared_by": "QP",
                "date_of_issue": "2026-05-28",
            }
        )
        self.assertEqual(ctx.get("well_count"), "2")
        self.assertIn("exceedance_summary", ctx)
        self.assertEqual(len(ctx.get("monitoring_wells", [])), 2)
        self.assertEqual(len(ctx.get("groundwater_results", [])), 4)
        self.assertTrue(ctx.get("executive_summary"))
        self.assertTrue(ctx.get("gw_program_intro"))
        self.assertTrue(ctx.get("gw_trend_summary"))

    def test_render_sample(self) -> None:
        engine = ReportEngine(
            excel_bytes=self.xlsx.read_bytes(),
            template_bytes=self.tpl.read_bytes(),
        )
        docx, warnings, ctx, _ = engine.render(
            meta={
                "report_type": "groundwater_monitoring",
                "report_phase": "Phase 1",
                "date_of_issue": "2026-05-28",
            }
        )
        self.assertGreater(len(docx), 5000)
        self.assertEqual(ctx.get("site_name"), "Example Wellsite GW Program")
        exc = [
            r
            for r in ctx.get("groundwater_results", [])
            if r.get("exceedance_flag") == "Yes"
        ]
        self.assertGreaterEqual(len(exc), 1)


if __name__ == "__main__":
    unittest.main()
