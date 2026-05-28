"""Batch report generation from multiple ProjectData rows."""

from __future__ import annotations

import io
import unittest
import zipfile
from pathlib import Path

import pandas as pd

from deliverable_pack import build_batch_reports_zip
from engine import (
    PROJECT_SHEET,
    ReportEngine,
    _project_rows_from_df,
    generate_sample_template_docx,
)

ROOT = Path(__file__).resolve().parents[1]


class TestBatchRender(unittest.TestCase):
    def _multi_row_excel(self) -> bytes:
        bio = io.BytesIO()
        project = pd.DataFrame(
            [
                {
                    "site_name": "Site Alpha",
                    "client_name": "Client A",
                    "project_number": "P-001",
                },
                {
                    "site_name": "Site Beta",
                    "client_name": "Client B",
                    "project_number": "P-002",
                },
            ]
        )
        lab = pd.DataFrame(
            [
                {
                    "site_name": "Site Alpha",
                    "analyte": "Benzene",
                    "result": "0.01",
                    "unit": "mg/L",
                    "criteria": "0.005",
                },
                {
                    "site_name": "Site Beta",
                    "analyte": "Toluene",
                    "result": "0.02",
                    "unit": "mg/L",
                    "criteria": "0.01",
                },
            ]
        )
        with pd.ExcelWriter(bio, engine="openpyxl") as w:
            project.to_excel(w, sheet_name=PROJECT_SHEET, index=False)
            lab.to_excel(w, sheet_name="LabResults", index=False)
        return bio.getvalue()

    def test_project_row_count(self) -> None:
        xlsx = self._multi_row_excel()
        tpl = (ROOT / "samples" / "sample_template.docx").read_bytes()
        engine = ReportEngine(excel_bytes=xlsx, template_bytes=tpl)
        self.assertEqual(engine.project_row_count({"report_phase": "Phase 2"}), 2)

    def test_render_batch_produces_two_reports(self) -> None:
        xlsx = self._multi_row_excel()
        tpl = (ROOT / "samples" / "sample_template.docx").read_bytes()
        engine = ReportEngine(excel_bytes=xlsx, template_bytes=tpl)
        meta = {"report_phase": "Phase 2", "date_of_issue": "2026-05-27"}
        batch = engine.render_batch(
            meta=meta,
            excel_filename="batch.xlsx",
            template_filename="sample_template.docx",
        )
        self.assertEqual(len(batch), 2)
        self.assertIn("Site_Alpha", batch[0].filename)
        self.assertIn("Site_Beta", batch[1].filename)
        self.assertNotEqual(batch[0].filename, batch[1].filename)
        self.assertEqual(batch[0].context.get("site_name"), "Site Alpha")
        self.assertEqual(len(batch[0].context.get("lab_results", [])), 1)
        self.assertEqual(
            batch[0].context["lab_results"][0].get("analyte"),
            "Benzene",
        )

    def test_batch_zip(self) -> None:
        xlsx = self._multi_row_excel()
        tpl = (ROOT / "samples" / "sample_template.docx").read_bytes()
        engine = ReportEngine(excel_bytes=xlsx, template_bytes=tpl)
        batch = engine.render_batch(meta={"report_phase": "Phase 2"})
        zip_bytes = build_batch_reports_zip(
            [(b.filename, b.docx_bytes, b.record.to_json_bytes()) for b in batch]
        )
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
        self.assertEqual(len([n for n in names if n.startswith("reports/")]), 2)

    def test_excel_row_numbers_start_at_row_2(self) -> None:
        project = pd.DataFrame(
            [
                {"site_name": "Site A", "client_name": "C1"},
                {"site_name": "Site B", "client_name": "C2"},
            ]
        )
        rows = _project_rows_from_df(project)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["_excel_row_number"], 2)
        self.assertEqual(rows[1]["_excel_row_number"], 3)

    def test_duplicate_header_row_skipped(self) -> None:
        project = pd.DataFrame(
            [
                {"site_name": "site_name", "client_name": "client_name"},
                {"site_name": "Real Site", "client_name": "Real Client"},
            ]
        )
        rows = _project_rows_from_df(project)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["site_name"], "Real Site")
        self.assertEqual(rows[0]["_excel_row_number"], 3)

    def test_batch_result_excel_row_numbers(self) -> None:
        xlsx = self._multi_row_excel()
        tpl = (ROOT / "samples" / "sample_template.docx").read_bytes()
        batch = ReportEngine(xlsx, tpl).render_batch(meta={"report_phase": "Phase 2"})
        self.assertEqual(batch[0].excel_row_number, 2)
        self.assertEqual(batch[1].excel_row_number, 3)

    def test_blank_rows_skipped(self) -> None:
        bio = io.BytesIO()
        project = pd.DataFrame(
            [
                {"site_name": "Only Site", "client_name": "C"},
                {"site_name": "", "client_name": ""},
            ]
        )
        with pd.ExcelWriter(bio, engine="openpyxl") as w:
            project.to_excel(w, sheet_name=PROJECT_SHEET, index=False)
        tpl_path = ROOT / "samples" / "sample_template.docx"
        if not tpl_path.is_file():
            generate_sample_template_docx(str(tpl_path))
        engine = ReportEngine(
            excel_bytes=bio.getvalue(),
            template_bytes=tpl_path.read_bytes(),
        )
        self.assertEqual(
            engine.project_row_count({"report_phase": "Phase 1"}), 1
        )


if __name__ == "__main__":
    unittest.main()
