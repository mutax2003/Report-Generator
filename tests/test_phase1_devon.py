"""Devon 2017 reference Phase I pair (04-04-049-04W4M) render and preflight."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestPhase1Devon(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.xlsx = ROOT / "samples" / "phase1_devon_data.xlsx"
        cls.tpl = ROOT / "samples" / "phase1_devon_template.docx"
        if not cls.xlsx.is_file() or not cls.tpl.is_file():
            raise unittest.SkipTest(
                "Run scripts/create_phase1_devon_pair.py (or create_samples.py) first"
            )

    def test_preflight_and_render(self) -> None:
        from engine import ECOVENTURE_CONSULTANT, ReportEngine
        from template_tools import run_preflight

        excel_bytes = self.xlsx.read_bytes()
        template_bytes = self.tpl.read_bytes()
        meta = {
            "prepared_by": "Ecoventure QP",
            "date_of_issue": "2026-05-20",
            "report_phase": "Phase 1",
        }
        pre = run_preflight(excel_bytes, template_bytes, meta)
        self.assertTrue(pre.can_generate, pre.errors)
        engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=template_bytes)
        docx, warnings, ctx, _record = engine.render(meta=meta)
        self.assertGreater(len(docx), 500_000)
        self.assertEqual(ctx.get("company"), ECOVENTURE_CONSULTANT)
        self.assertEqual(ctx.get("client_name"), "Example Energy Ltd.")
        self.assertIn("00/04-04-049-04W4/0", ctx.get("uwi", ""))

        from security import open_docx_zip, read_docx_xml_member, ZipReadBudget

        with open_docx_zip(docx) as zf:
            xml = read_docx_xml_member(zf, "word/document.xml", ZipReadBudget())
        self.assertIn("Example Energy", xml)
        self.assertIn("Ecoventure", xml)
        self.assertNotIn("DEVON CANADA CORPORATION", xml)


if __name__ == "__main__":
    unittest.main()
