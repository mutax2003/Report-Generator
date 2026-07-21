"""Render-path parity: Streamlit/engine vs automate vs project folder."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RenderPathParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.xlsx = ROOT / "samples" / "phase1_alberta_data.xlsx"
        cls.tpl = ROOT / "samples" / "phase1_alberta_template.docx"
        if not cls.xlsx.is_file() or not cls.tpl.is_file():
            raise unittest.SkipTest("Run scripts/create_samples.py first")

    def _meta(self) -> dict[str, str]:
        return {
            "report_phase": "Phase 1",
            "report_type": "phase1_alberta",
            "prepared_by": "Parity Test",
            "date_of_issue": "2026-06-10",
        }

    def _appendix_h(self):
        from deliverable_pack import AppendixFile

        return AppendixFile(
            label="H",
            data=b"%PDF-1.4 site sketch placeholder",
            filename="appendix_h.pdf",
            format="pdf",
            source="uploaded",
        )

    def _dwda_snapshot(self, context: dict) -> dict:
        dwda = context.get("_dwda_compliance")
        return {
            "complete": context.get("dwda_checklist_complete"),
            "scope": context.get("dwda_checklist_scope"),
            "satisfied": getattr(dwda, "satisfied_count", None) if dwda else None,
            "appendix_h": any(
                r.get("item_id") == "d050.appendix_h" and r.get("satisfied")
                for r in (context.get("dwda_checklist_results") or [])
                if isinstance(r, dict)
            ),
        }

    def test_engine_and_automate_match_with_appendix_h(self) -> None:
        from automate.render import render_report_from_bytes
        from engine import ReportEngine
        from template_attachments import prepare_template_upload_cached

        meta = self._meta()
        excel_bytes = self.xlsx.read_bytes()
        template_bytes = self.tpl.read_bytes()
        appendix_h = self._appendix_h()
        labels = {"H"}

        prepared = prepare_template_upload_cached(template_bytes, self.tpl.name)
        engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=prepared.docx_bytes)
        _, _, engine_ctx, _ = engine.render(
            meta=meta,
            excel_filename=self.xlsx.name,
            template_filename=self.tpl.name,
            appendix_labels_present=labels,
        )

        _, _, auto_ctx, _, _ = render_report_from_bytes(
            excel_bytes,
            template_bytes,
            meta=meta,
            excel_filename=self.xlsx.name,
            template_filename=self.tpl.name,
            uploaded_appendices=[appendix_h],
        )

        self.assertEqual(
            self._dwda_snapshot(engine_ctx),
            self._dwda_snapshot(auto_ctx),
        )

    def test_render_request_matches_engine_streamlit_path(self) -> None:
        """Same RenderRequest shape as app.py single-report generate."""
        from render_service import RenderRequest, render_report
        from template_attachments import prepare_template_upload_cached

        meta = self._meta()
        excel_bytes = self.xlsx.read_bytes()
        template_bytes = self.tpl.read_bytes()
        appendix_h = self._appendix_h()
        labels = {"H"}

        prepared = prepare_template_upload_cached(template_bytes, self.tpl.name)
        from engine import ReportEngine

        engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=prepared.docx_bytes)
        _, _, engine_ctx, _ = engine.render(
            meta=meta,
            excel_filename=self.xlsx.name,
            template_filename=self.tpl.name,
            appendix_labels_present=labels,
        )

        result = render_report(
            RenderRequest(
                excel_bytes=excel_bytes,
                template_bytes=template_bytes,
                meta=meta,
                excel_filename=self.xlsx.name,
                template_filename=self.tpl.name,
                uploaded_appendices=[appendix_h],
                appendix_labels_present=labels,
            )
        )
        self.assertEqual(
            self._dwda_snapshot(engine_ctx),
            self._dwda_snapshot(result.context),
        )
        self.assertIn("H", result.record.appendix_labels_evaluated or [])

    def test_render_batch_service_matches_engine(self) -> None:
        """render_batch_reports (CLI --all-rows path) matches engine.render_batch with labels."""
        from engine import ReportEngine
        from render_service import RenderRequest, render_batch_reports
        from template_attachments import prepare_template_upload_cached

        meta = self._meta()
        excel_bytes = self.xlsx.read_bytes()
        template_bytes = self.tpl.read_bytes()
        labels = {"H"}
        appendix_h = self._appendix_h()

        prepared = prepare_template_upload_cached(template_bytes, self.tpl.name)
        engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=prepared.docx_bytes)
        engine_batch = engine.render_batch(
            meta=meta,
            excel_filename=self.xlsx.name,
            template_filename=self.tpl.name,
            appendix_labels_present=labels,
        )

        service_batch = render_batch_reports(
            RenderRequest(
                excel_bytes=excel_bytes,
                template_bytes=template_bytes,
                meta=meta,
                excel_filename=self.xlsx.name,
                template_filename=self.tpl.name,
                uploaded_appendices=[appendix_h],
                appendix_labels_present=labels,
            )
        )

        self.assertEqual(len(engine_batch), len(service_batch))
        self.assertGreater(len(service_batch), 0)
        self.assertEqual(
            self._dwda_snapshot(engine_batch[0].context),
            self._dwda_snapshot(service_batch[0].context),
        )

    def test_project_folder_matches_engine_with_appendix_h(self) -> None:
        from engine import ReportEngine
        from project_folder import init_sample_project_folder, render_project_folder, resolve_project_folder
        from template_attachments import prepare_template_upload_cached

        meta = self._meta()
        appendix_h = self._appendix_h()
        tmp = Path(tempfile.mkdtemp(prefix="esa_parity_"))
        try:
            init_sample_project_folder(tmp, source_user_test=False)
            appendices_dir = tmp / "appendices"
            appendices_dir.mkdir(exist_ok=True)
            (appendices_dir / "appendix_h_site_sketch.pdf").write_bytes(appendix_h.data)

            resolved = resolve_project_folder(tmp)
            outputs = render_project_folder(resolved, package=False)
            self.assertTrue(outputs["docx"].is_file())

            excel_bytes = resolved.excel_path.read_bytes()
            template_bytes = resolved.template_path.read_bytes()
            prepared = prepare_template_upload_cached(template_bytes, resolved.template_path.name)
            engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=prepared.docx_bytes)
            _, _, engine_ctx, folder_record = engine.render(
                meta=meta,
                excel_filename=resolved.excel_path.name,
                template_filename=resolved.template_path.name,
                appendix_labels_present={"H"},
            )

            import json

            manifest = json.loads(outputs["manifest"].read_text(encoding="utf-8"))
            self.assertIn("H", manifest.get("appendix_labels_evaluated", []))

            from render_service import RenderRequest, render_report

            result = render_report(
                RenderRequest(
                    excel_bytes=excel_bytes,
                    template_bytes=template_bytes,
                    meta=dict(resolved.meta),
                    excel_filename=resolved.excel_path.name,
                    template_filename=resolved.template_path.name,
                    uploaded_appendices=[appendix_h],
                )
            )
            self.assertEqual(
                self._dwda_snapshot(engine_ctx),
                self._dwda_snapshot(result.context),
            )
            _ = folder_record
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
