"""Tests for Phase 1 PDF metadata parsing."""

from __future__ import annotations

import unittest
from pathlib import Path

from phase1_pdf_text import parse_phase1_pdf_meta

ROOT = Path(__file__).resolve().parents[1]
PDF_260109 = (
    ROOT / "samples" / "260109R - 16-34-055-02W4M Phase 1 ESA_Final_Secure.pdf"
)


class TestPhase1PdfText(unittest.TestCase):
    @unittest.skipUnless(PDF_260109.is_file(), "sample PDF not present")
    def test_parse_260109_meta(self) -> None:
        meta = parse_phase1_pdf_meta(PDF_260109)
        self.assertEqual(meta.project_number, "260109R")
        self.assertIn("Caltex", meta.client_name)
        self.assertTrue(meta.uwi)


if __name__ == "__main__":
    unittest.main()
