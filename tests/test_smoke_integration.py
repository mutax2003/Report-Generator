"""
Smoke integration: headless pre-flight + render (no browser).
Mirrors Streamlit upload → pre-flight → generate without Playwright.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from engine import ReportEngine, generate_sample_excel, generate_sample_template_docx
from template_tools import run_preflight

ROOT = Path(__file__).resolve().parents[1]


class SmokeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        samples = ROOT / "samples"
        samples.mkdir(parents=True, exist_ok=True)
        xlsx = samples / "sample_data.xlsx"
        docx = samples / "sample_template.docx"
        if not xlsx.is_file():
            generate_sample_excel(str(xlsx))
        if not docx.is_file():
            generate_sample_template_docx(str(docx))
        cls.excel = xlsx.read_bytes()
        cls.template = docx.read_bytes()
        cls.meta = {
            "prepared_by": "Smoke Test",
            "date_of_issue": "2026-05-20",
            "report_phase": "Phase 2",
            "report_type": "phase2_esa",
        }

    def test_health_check_script(self) -> None:
        if os.environ.get("ESA_RUN_HEALTH_CHECK", "").strip().lower() not in (
            "1",
            "true",
            "yes",
        ):
            self.skipTest("Set ESA_RUN_HEALTH_CHECK=1 to run health_check in unittest")
        script = ROOT / "scripts" / "health_check.py"
        if not script.is_file():
            self.skipTest("health_check.py missing")
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

    def test_preflight_then_render(self) -> None:
        pf = run_preflight(self.excel, self.template, self.meta)
        self.assertTrue(pf.can_generate)
        self.assertEqual(len(pf.errors), 0)
        engine = ReportEngine(excel_bytes=self.excel, template_bytes=self.template)
        docx, warnings, _ctx, record = engine.render(meta=self.meta)
        self.assertGreater(len(docx), 1000)
        self.assertIsNotNone(record.output_sha256)
        self.assertEqual(record.report_type, "phase2_esa")


if __name__ == "__main__":
    unittest.main()
