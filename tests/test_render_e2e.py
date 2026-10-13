"""End-to-end render content checks."""

from __future__ import annotations

import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import ReportEngine  # noqa: E402


def _docx_plain_text(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zf:
        xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    return xml


class TestRenderE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.xlsx = ROOT / "samples" / "sample_data.xlsx"
        cls.tpl = ROOT / "samples" / "sample_template.docx"
        if not cls.xlsx.is_file() or not cls.tpl.is_file():
            raise unittest.SkipTest("Run scripts/create_samples.py first")

    def test_render_project_and_lab(self) -> None:
        engine = ReportEngine(
            excel_bytes=self.xlsx.read_bytes(),
            template_bytes=self.tpl.read_bytes(),
        )
        docx_bytes, _warnings, ctx, _rec = engine.render(
            meta={
                "prepared_by": "E2E Test",
                "date_of_issue": "2026-05-19",
                "report_phase": "Phase 2",
            }
        )
        out = ROOT / "samples" / "e2e_output.docx"
        out.write_bytes(docx_bytes)
        text = _docx_plain_text(out)

        self.assertEqual(ctx.get("site_name"), "123 Example Road")
        self.assertEqual(len(ctx.get("lab_results", [])), 3)
        for needle in ("123 Example Road", "Demo Client Ltd.", "Benzene", "TCE", "12.5", "pH"):
            self.assertIn(needle, text, msg=f"missing {needle!r}")

        # Header row should appear once; old bug repeated header per lab row
        self.assertEqual(text.count("Analyte"), 1)
        self.assertEqual(text.count("Exceedance"), 1)

    def test_formula_prefix_only_for_excel_writers(self) -> None:
        from engine import _cell_str, _excel_cell_str

        self.assertEqual(_excel_cell_str("=cmd|'/c calc'!A0"), "'=cmd|'/c calc'!A0")
        self.assertEqual(_excel_cell_str("+1+cmd|' /C calc'!A0"), "'+1+cmd|' /C calc'!A0")
        self.assertEqual(_excel_cell_str("@SUM(A1)"), "'@SUM(A1)")
        self.assertEqual(_excel_cell_str("normal"), "normal")
        # Plain numbers are never formulas — never altered.
        self.assertEqual(_excel_cell_str("-114.5"), "-114.5")
        self.assertEqual(_excel_cell_str(-0.3), "-0.3")
        # Word context never gets the apostrophe prefix.
        self.assertEqual(_cell_str("-114.5"), "-114.5")
        self.assertEqual(_cell_str(-114.5), "-114.5")
        self.assertEqual(_cell_str("=1+1"), "=1+1")


if __name__ == "__main__":
    unittest.main()
