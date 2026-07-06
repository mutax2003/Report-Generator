"""Smoke tests for automate.render deliverable package path."""

from __future__ import annotations

import json
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AutomateRenderPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.xlsx = ROOT / "samples" / "phase1_alberta_data.xlsx"
        cls.tpl = ROOT / "samples" / "phase1_alberta_template.docx"
        if not cls.xlsx.is_file() or not cls.tpl.is_file():
            raise unittest.SkipTest("Run scripts/create_samples.py first")

    def test_render_deliverable_zip_from_bytes(self) -> None:
        from automate.render import render_deliverable_zip_from_bytes

        meta = {
            "report_phase": "Phase 1",
            "report_type": "phase1_alberta",
            "prepared_by": "Ecoventure QP",
            "date_of_issue": "2026-06-10",
        }
        zip_bytes, warnings, record = render_deliverable_zip_from_bytes(
            self.xlsx.read_bytes(),
            self.tpl.read_bytes(),
            meta=meta,
            report_filename="report.docx",
        )
        self.assertGreater(len(zip_bytes), 10_000)
        self.assertFalse(warnings, warnings)
        self.assertTrue(record.appendix_files)
        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            self.assertTrue(any(n.startswith("appendices/D_") for n in names))
            self.assertTrue(any(n.startswith("appendices/A_") for n in names))
            self.assertTrue(any(n.startswith("onestop/") for n in names))
            self.assertTrue(
                any(n.startswith("qp_checklists/dwda_") for n in names),
                f"expected DWDA QP checklist in zip: {names}",
            )
            self.assertTrue(
                any(n.startswith("qp_checklists/sed002_") for n in names),
                f"expected SED QP checklist in zip: {names}",
            )
            manifest_name = next(n for n in names if n.endswith("_manifest.json"))
            manifest = json.loads(zf.read(manifest_name).decode("utf-8"))
        self.assertTrue(manifest.get("appendix_labels_evaluated"))
        self.assertIsNotNone(manifest.get("sed002_completeness_pct"))


if __name__ == "__main__":
    unittest.main()
