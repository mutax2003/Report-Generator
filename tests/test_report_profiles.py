"""Flexible report profiles and template-driven sheet mapping."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestReportProfiles(unittest.TestCase):
    def test_resolve_phase1_profile(self) -> None:
        from report_profile import resolve_report_config

        xlsx = ROOT / "samples" / "phase1_alberta_data.xlsx"
        tpl = ROOT / "samples" / "phase1_alberta_template.docx"
        if not xlsx.is_file():
            raise unittest.SkipTest("run create_samples.py")
        runtime = resolve_report_config(
            xlsx.read_bytes(),
            tpl.read_bytes(),
            {"report_type": "phase1_alberta", "report_phase": "Phase 1"},
        )
        self.assertEqual(runtime.report_type, "phase1_alberta")
        self.assertIn("DrillingWaste", runtime.sheet_to_loop)

    def test_custom_demo_render(self) -> None:
        from engine import ReportEngine, generate_custom_demo_excel, generate_custom_demo_template_docx
        from report_profile import discover_template_loops

        xlsx = ROOT / "samples" / "custom_demo_data.xlsx"
        tpl = ROOT / "samples" / "custom_demo_template.docx"
        if not xlsx.is_file():
            generate_custom_demo_excel(str(xlsx))
            generate_custom_demo_template_docx(str(tpl))

        loops = discover_template_loops(tpl.read_bytes())
        self.assertIn("observations", loops)

        engine = ReportEngine(xlsx.read_bytes(), tpl.read_bytes())
        docx, warnings, ctx, _ = engine.render(
            meta={
                "report_type": "template_driven",
                "report_phase": "Phase 1",
                "prepared_by": "Test",
                "date_of_issue": "2026-05-21",
            }
        )
        self.assertGreater(len(docx), 2000)
        self.assertEqual(len(ctx.get("observations", [])), 2)
        self.assertIn("Custom Client", str(ctx.get("client_name", "")))


if __name__ == "__main__":
    unittest.main()
