"""Tests for Phase I appendix auto-generation (A/D/G)."""

from __future__ import annotations

import os
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SLOW = os.getenv("ESA_RUN_SLOW", "").strip().lower() in ("1", "true", "yes")


class AppendixGeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.xlsx = ROOT / "samples" / "phase1_devon_data.xlsx"
        cls.tpl = ROOT / "samples" / "phase1_devon_template.docx"
        cls.appendix_a = ROOT / "samples" / "appendices" / "appendix_a_qp_declaration.docx"
        cls.appendix_d = ROOT / "samples" / "appendices" / "appendix_d_drilling_waste_checklist.docx"
        cls.appendix_g = ROOT / "samples" / "appendices" / "appendix_g_waste_calc_tables.docx"
        missing = [
            p
            for p in (cls.xlsx, cls.tpl, cls.appendix_a, cls.appendix_d, cls.appendix_g)
            if not p.is_file()
        ]
        if missing:
            raise unittest.SkipTest(
                "Run scripts/create_samples.py and scripts/create_appendix_templates.py first"
            )

    def test_should_generate_a_always(self) -> None:
        from appendix_generator import should_generate_appendix

        self.assertTrue(should_generate_appendix("A", {}))

    def test_should_generate_d_and_g_with_waste_rows(self) -> None:
        from appendix_generator import should_generate_appendix

        ctx = {
            "no_drilling_waste_on_site": "No",
            "aer_waste_compliance_option": "Option 1",
            "drilling_waste": [{"mud_type": "Gel Chem", "volume_m3": "208"}],
        }
        self.assertTrue(should_generate_appendix("D", ctx))
        self.assertTrue(should_generate_appendix("G", ctx))

    def test_skip_g_when_no_waste_on_site(self) -> None:
        from appendix_generator import should_generate_appendix

        ctx = {
            "no_drilling_waste_on_site": "Yes",
            "aer_waste_compliance_option": "Option 1",
            "drilling_waste": [],
        }
        self.assertTrue(should_generate_appendix("D", ctx))
        self.assertFalse(should_generate_appendix("G", ctx))

    def test_render_a_d_g_minimal_context(self) -> None:
        from appendix_generator import render_phase1_appendices

        ctx = {
            "client_name": "Client",
            "well_name": "Well",
            "uwi": "00/01-01-001-01W1/0",
            "consultant_name": "Ecoventure Inc.",
            "company": "Ecoventure Inc.",
            "qp_names": "QP Name",
            "no_drilling_waste_on_site": "No",
            "aer_waste_compliance_option": "Option 1",
            "drilling_waste": [{"mud_type": "Gel", "volume_m3": "1"}],
        }
        meta = {
            "report_type": "phase1_alberta",
            "prepared_by": "Sidebar QP",
            "date_of_issue": "2026-06-10",
        }
        appendices, warnings = render_phase1_appendices(ctx, meta)
        self.assertFalse(warnings, warnings)
        self.assertEqual({a.label for a in appendices}, {"A", "D", "G"})

    @unittest.skipUnless(_SLOW, "Set ESA_RUN_SLOW=1 for full Devon template render")
    def test_render_phase1_appendices_from_devon_fixture(self) -> None:
        from appendix_generator import render_phase1_appendices
        from engine import ReportEngine

        meta = {
            "prepared_by": "Ecoventure QP",
            "date_of_issue": "2026-05-20",
            "report_phase": "Phase 1",
            "report_type": "phase1_devon",
        }
        engine = ReportEngine(
            excel_bytes=self.xlsx.read_bytes(),
            template_bytes=self.tpl.read_bytes(),
        )
        ctx = engine.build_context(meta)
        appendices, warnings = render_phase1_appendices(ctx, meta)
        labels = {a.label for a in appendices}
        self.assertIn("A", labels)
        self.assertIn("D", labels)
        self.assertIn("G", labels)
        for ap in appendices:
            self.assertEqual(ap.format, "docx")
            self.assertEqual(ap.source, "generated")
            self.assertGreater(len(ap.data), 5000)
            self.assertTrue(ap.filename.endswith(".docx"))

    def test_merge_upload_overrides_generated(self) -> None:
        from appendix_generator import merge_appendix_lists
        from deliverable_pack import AppendixFile

        generated = [
            AppendixFile("D", b"gen", "d.docx", format="docx", source="generated"),
        ]
        uploaded = [
            AppendixFile("D", b"up", "d.pdf", format="pdf", source="uploaded"),
        ]
        merged = merge_appendix_lists(generated, uploaded)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].data, b"up")
        self.assertEqual(merged[0].source, "uploaded")

    def test_predicted_appendix_labels(self) -> None:
        from appendix_generator import predicted_appendix_labels

        ctx = {
            "no_drilling_waste_on_site": "No",
            "drilling_waste": [{"mud_type": "Gel"}],
        }
        meta = {"report_type": "phase1_alberta", "report_phase": "Phase 1"}
        self.assertEqual(predicted_appendix_labels(ctx, meta), {"A", "D", "G"})

    def test_missing_template_warns_not_crash(self) -> None:
        from unittest.mock import patch

        from appendix_generator import render_phase1_appendices

        ctx = {
            "no_drilling_waste_on_site": "No",
            "aer_waste_compliance_option": "Option 1",
            "drilling_waste": [{"mud_type": "Gel", "volume_m3": "1"}],
            "uwi": "test",
        }
        meta = {
            "report_type": "phase1_alberta",
            "prepared_by": "QP",
            "date_of_issue": "2026-06-10",
        }
        with patch(
            "appendix_generator.resolve_appendix_template_path",
            side_effect=FileNotFoundError("missing template"),
        ):
            appendices, warnings = render_phase1_appendices(ctx, meta)
        self.assertEqual(appendices, [])
        self.assertTrue(any("Appendix D not generated" in w for w in warnings))

    def test_attach_appendices_to_record(self) -> None:
        from appendix_generator import attach_appendices_to_record
        from deliverable_pack import AppendixFile
        from provenance import build_generation_record

        ctx = {
            "no_drilling_waste_on_site": "No",
            "aer_waste_compliance_option": "Option 1",
            "drilling_waste": [{"mud_type": "Gel", "volume_m3": "1"}],
            "uwi": "00/01-01-001-01W1/0",
        }
        meta = {"report_type": "phase1_alberta"}
        record = build_generation_record(
            excel_bytes=b"x",
            template_bytes=b"t",
            meta=meta,
            coverage=None,
            warnings=[],
            missing_variables=[],
        )
        uploaded = [
            AppendixFile("B", b"pdf", "b.pdf", format="pdf", source="uploaded"),
        ]
        generated, merged, warnings = attach_appendices_to_record(
            record, ctx, meta, uploaded
        )
        self.assertEqual({a.label for a in generated}, {"A", "D", "G"})
        self.assertEqual({a.label for a in merged}, {"A", "B", "D", "G"})
        self.assertFalse(warnings)

    def test_appendix_uses_sidebar_meta(self) -> None:
        from appendix_generator import render_phase1_appendices

        ctx = {
            "no_drilling_waste_on_site": "No",
            "aer_waste_compliance_option": "Option 1",
            "drilling_waste": [{"mud_type": "Gel", "volume_m3": "1"}],
            "uwi": "test",
            "client_name": "Client",
            "well_name": "Well",
            "consultant_name": "Ecoventure Inc.",
        }
        meta = {
            "report_type": "phase1_alberta",
            "prepared_by": "Sidebar QP",
            "date_of_issue": "2026-06-10",
        }
        appendices, warnings = render_phase1_appendices(ctx, meta)
        self.assertFalse(warnings, warnings)
        self.assertEqual({a.label for a in appendices}, {"A", "D", "G"})

    @unittest.skipUnless(_SLOW, "Set ESA_RUN_SLOW=1 for full Devon template render")
    def test_package_zip_contains_docx_appendices(self) -> None:
        from appendix_generator import render_phase1_appendices
        from deliverable_pack import DeliverablePackage, build_deliverable_zip
        from engine import ReportEngine

        meta = {
            "prepared_by": "Ecoventure QP",
            "date_of_issue": "2026-05-20",
            "report_phase": "Phase 1",
            "report_type": "phase1_alberta",
        }
        engine = ReportEngine(
            excel_bytes=self.xlsx.read_bytes(),
            template_bytes=self.tpl.read_bytes(),
        )
        docx, _warnings, ctx, _record = engine.render(meta=meta)
        appendices, warnings = render_phase1_appendices(ctx, meta)
        pkg = DeliverablePackage(
            report_docx=docx,
            report_filename="report.docx",
            appendices=appendices,
            render_context=ctx,
            render_meta=meta,
        )
        zbytes = build_deliverable_zip(pkg)
        with zipfile.ZipFile(BytesIO(zbytes)) as zf:
            names = zf.namelist()
        self.assertTrue(any(n.startswith("appendices/A_") and n.endswith(".docx") for n in names))
        self.assertTrue(any(n.startswith("appendices/D_") and n.endswith(".docx") for n in names))
        self.assertTrue(any(n.startswith("appendices/G_") and n.endswith(".docx") for n in names))

    def test_batch_deliverable_packages_zip(self) -> None:
        from appendix_generator import render_phase1_appendices
        from deliverable_pack import build_batch_deliverable_packages_zip
        from engine import BatchReportResult, ReportEngine
        from provenance import build_generation_record

        meta = {
            "prepared_by": "Ecoventure QP",
            "date_of_issue": "2026-06-10",
            "report_type": "phase1_alberta",
        }
        ctx = {
            "site_name": "Test Site",
            "no_drilling_waste_on_site": "No",
            "aer_waste_compliance_option": "Option 1",
            "drilling_waste": [{"mud_type": "Gel", "volume_m3": "1"}],
            "uwi": "00/01-01-001-01W1/0",
        }
        appendices, _ = render_phase1_appendices(ctx, meta)
        record = build_generation_record(
            excel_bytes=b"x",
            template_bytes=b"t",
            meta=meta,
            coverage=None,
            warnings=[],
            missing_variables=[],
        )
        item = BatchReportResult(
            project_row_index=0,
            excel_row_number=2,
            docx_bytes=b"PK" + b"\x00" * 100,
            warnings=[],
            context=ctx,
            record=record,
            filename="test_site.docx",
            appendices=appendices,
        )
        zip_bytes = build_batch_deliverable_packages_zip([item], meta)
        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
        self.assertTrue(any(n.startswith("Test_Site/") for n in names))
        self.assertTrue(any("/appendices/A_" in n for n in names))


if __name__ == "__main__":
    unittest.main()
