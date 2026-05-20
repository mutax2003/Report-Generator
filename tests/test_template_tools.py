"""Tests for template_tools pre-flight and coverage."""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import LAB_SHEET, PROJECT_SHEET  # noqa: E402
from template_tools import (  # noqa: E402
    run_preflight,
    template_coverage,
)


def _workbook(project: pd.DataFrame, lab: pd.DataFrame) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as w:
        project.to_excel(w, sheet_name=PROJECT_SHEET, index=False)
        lab.to_excel(w, sheet_name=LAB_SHEET, index=False)
    return bio.getvalue()


class TestTemplateTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tpl = ROOT / "samples" / "sample_template.docx"
        if not cls.tpl.is_file():
            raise unittest.SkipTest("samples missing")
        cls.template_bytes = cls.tpl.read_bytes()

    def test_preflight_ok_for_samples(self) -> None:
        xlsx = ROOT / "samples" / "sample_data.xlsx"
        if not xlsx.is_file():
            self.skipTest("sample xlsx missing")
        pf = run_preflight(
            xlsx.read_bytes(),
            self.template_bytes,
            {"report_phase": "Phase 2", "prepared_by": "T", "date_of_issue": "2026-01-01"},
        )
        self.assertTrue(pf.can_generate)
        self.assertIsNotNone(pf.coverage)
        assert pf.coverage is not None
        self.assertIn("site_name", pf.coverage.matched)

    def test_preflight_missing_sheet(self) -> None:
        xlsx = _workbook(
            pd.DataFrame({"site_name": ["S"]}),
            pd.DataFrame(),
        )
        bio = io.BytesIO()
        with pd.ExcelWriter(bio, engine="openpyxl") as w:
            pd.DataFrame({"site_name": ["S"]}).to_excel(w, sheet_name="Wrong", index=False)
        pf = run_preflight(
            bio.getvalue(),
            self.template_bytes,
            {"report_phase": "Phase 2"},
        )
        self.assertFalse(pf.can_generate)

    def test_coverage_missing_var(self) -> None:
        from docx import Document

        doc = Document()
        doc.add_paragraph("{{ site_name }} {{ only_in_template }}")
        buf = io.BytesIO()
        doc.save(buf)
        xlsx = _workbook(
            pd.DataFrame({"site_name": ["S"], "client_name": ["C"]}),
            pd.DataFrame(
                [{"Analyte": "A", "Result": 1, "Unit": "u", "Exceedance": "N"}]
            ),
        )
        cov = template_coverage(
            xlsx,
            buf.getvalue(),
            {"report_phase": "Phase 2", "prepared_by": "x", "date_of_issue": "2026-01-01"},
        )
        self.assertIn("only_in_template", cov.missing_in_data)
        self.assertIn("site_name", cov.matched)


if __name__ == "__main__":
    unittest.main()
