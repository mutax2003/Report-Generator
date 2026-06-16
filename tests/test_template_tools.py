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

    def test_scan_template_cache(self) -> None:
        from template_tools import clear_template_scan_cache, scan_template

        clear_template_scan_cache()
        first = scan_template(self.template_bytes)
        second = scan_template(self.template_bytes)
        self.assertIs(first, second)

    def test_read_excel_meta_cache(self) -> None:
        from report_profile import clear_excel_meta_cache, read_excel_meta

        xlsx = ROOT / "samples" / "sample_data.xlsx"
        if not xlsx.is_file():
            self.skipTest("sample xlsx missing")
        clear_excel_meta_cache()
        data = xlsx.read_bytes()
        first = read_excel_meta(data)
        second = read_excel_meta(data)
        self.assertIs(first, second)

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

    def test_preflight_appendix_labels_improve_sed002(self) -> None:
        xlsx = ROOT / "samples" / "phase1_alberta_data.xlsx"
        if not xlsx.is_file():
            self.skipTest("phase1 alberta sample missing")
        without = run_preflight(
            xlsx.read_bytes(),
            self.template_bytes,
            {"report_phase": "Phase 1"},
            appendix_labels_present=set(),
        )
        with_apps = run_preflight(
            xlsx.read_bytes(),
            self.template_bytes,
            {"report_phase": "Phase 1"},
            appendix_labels_present={"B", "D", "H"},
        )
        assert without.sed002 is not None and with_apps.sed002 is not None
        self.assertGreater(
            with_apps.sed002.satisfied_count,
            without.sed002.satisfied_count,
        )


if __name__ == "__main__":
    unittest.main()
