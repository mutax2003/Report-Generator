"""Production starter template + production_data.xlsx integration."""

from __future__ import annotations

import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import ReportEngine  # noqa: E402
from template_tools import run_preflight  # noqa: E402


class TestProductionStarter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.xlsx = ROOT / "samples" / "production_data.xlsx"
        cls.docx = ROOT / "samples" / "production_starter_template.docx"
        if not cls.xlsx.is_file() or not cls.docx.is_file():
            raise unittest.SkipTest("Run scripts/create_samples.py")

    def test_preflight_and_render(self) -> None:
        xb = self.xlsx.read_bytes()
        tb = self.docx.read_bytes()
        meta = {
            "prepared_by": "Test",
            "date_of_issue": "2026-05-19",
            "report_phase": "Phase 2",
        }
        pf = run_preflight(xb, tb, meta)
        self.assertTrue(pf.can_generate)
        self.assertGreater(len(pf.coverage.matched) if pf.coverage else 0, 5)

        engine = ReportEngine(xb, tb)
        docx_bytes, warnings, ctx, _record = engine.render(meta=meta)
        self.assertGreater(len(docx_bytes), 2000)
        text = zipfile.ZipFile(__import__("io").BytesIO(docx_bytes)).read(
            "word/document.xml"
        ).decode("utf-8", errors="ignore")
        self.assertIn("Client Full Name", text)
        self.assertIn("Benzene", text)


if __name__ == "__main__":
    unittest.main()
