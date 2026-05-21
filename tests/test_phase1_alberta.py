"""Alberta Phase I ESA (Ecoventure) render and preflight."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestPhase1Alberta(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.xlsx = ROOT / "samples" / "phase1_alberta_data.xlsx"
        cls.tpl = ROOT / "samples" / "phase1_alberta_template.docx"
        if not cls.xlsx.is_file() or not cls.tpl.is_file():
            raise unittest.SkipTest("Run scripts/create_samples.py first")

    def test_build_context_phase1_lists(self) -> None:
        from engine import ReportEngine

        engine = ReportEngine(
            excel_bytes=self.xlsx.read_bytes(),
            template_bytes=self.tpl.read_bytes(),
        )
        ctx = engine.build_context(
            {"report_phase": "Phase 1", "prepared_by": "Ecoventure QP"}
        )
        self.assertEqual(ctx.get("consultant_name"), "Ecoventure Inc.")
        self.assertIsInstance(ctx.get("drilling_waste"), list)
        self.assertGreater(len(ctx["drilling_waste"]), 0)
        self.assertIsInstance(ctx.get("storage_tanks"), list)
        self.assertEqual(ctx.get("lab_results"), [])

    def test_preflight_and_render(self) -> None:
        from engine import ECOVENTURE_CONSULTANT, ReportEngine
        from template_tools import run_preflight

        excel_bytes = self.xlsx.read_bytes()
        template_bytes = self.tpl.read_bytes()
        meta = {
            "prepared_by": "Ecoventure Test",
            "date_of_issue": "2026-05-20",
            "report_phase": "Phase 1",
        }
        pre = run_preflight(excel_bytes, template_bytes, meta)
        self.assertTrue(pre.can_generate, pre.errors)
        engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=template_bytes)
        docx, warnings, ctx, record = engine.render(meta=meta)
        self.assertGreater(len(docx), 2000)
        self.assertEqual(ctx.get("company"), ECOVENTURE_CONSULTANT)
        self.assertEqual(ctx.get("consultant_name"), ECOVENTURE_CONSULTANT)
        self.assertFalse(any("Missing sheet 'LabResults'" in w for w in warnings))
        from security import open_docx_zip, read_docx_xml_member, ZipReadBudget

        with open_docx_zip(docx) as zf:
            xml = read_docx_xml_member(zf, "word/document.xml", ZipReadBudget())
        self.assertIn("Ecoventure", xml)
        self.assertIn("Example Energy", xml)
        self.assertIn("was contracted by", xml)
        self.assertIn("Checklist Compliance", xml)
        self.assertIn("After reviewing regulatory information", xml)


if __name__ == "__main__":
    unittest.main()
