"""Tests for local project folder ingest and AI enrich."""

from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProjectFolderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.samples_xlsx = ROOT / "samples" / "phase1_alberta_data.xlsx"
        cls.samples_tpl = ROOT / "samples" / "phase1_alberta_template.docx"
        if not cls.samples_xlsx.is_file() or not cls.samples_tpl.is_file():
            raise unittest.SkipTest("Run scripts/create_samples.py first")

    def _make_folder(self) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="esa_project_"))
        from project_folder import init_sample_project_folder

        init_sample_project_folder(tmp, source_user_test=False)
        return tmp

    def test_resolve_project_folder(self) -> None:
        from project_folder import resolve_project_folder

        folder = self._make_folder()
        resolved = resolve_project_folder(folder)
        self.assertTrue(resolved.excel_path.is_file())
        self.assertTrue(resolved.template_path.is_file())
        self.assertEqual(resolved.meta.get("report_type"), "phase1_alberta")

    def test_init_phase2_sample_folder(self) -> None:
        import shutil
        import tempfile

        from project_folder import init_sample_project_folder, resolve_project_folder

        tmp = Path(tempfile.mkdtemp(prefix="esa_p2_"))
        try:
            init_sample_project_folder(tmp, source_user_test=False, profile="phase2_esa")
            resolved = resolve_project_folder(tmp)
            self.assertEqual(resolved.meta.get("report_type"), "phase2_esa")
            self.assertEqual(resolved.meta.get("report_phase"), "Phase 2")
            self.assertTrue((tmp / "project_data.xlsx").is_file())
            self.assertTrue((tmp / "template.docx").is_file())
            self.assertTrue((tmp / "source" / "lab_coa_example.pdf").is_file())
            self.assertTrue((tmp / "rag" / "phase2_intro.txt").is_file())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_inventory_and_preflight(self) -> None:
        from project_folder import enrich_project_folder, resolve_project_folder

        folder = self._make_folder()
        resolved = resolve_project_folder(folder, create_subdirs=True)
        paths = enrich_project_folder(resolved, use_llm=False, modes=("inventory",))
        self.assertTrue(any(p.name == "preflight_report.md" for p in paths))
        self.assertTrue((resolved.ai_drafts_dir / "inventory.md").is_file())

    def test_narratives_offline(self) -> None:
        from project_folder import draft_narratives_for_folder, resolve_project_folder

        folder = self._make_folder()
        resolved = resolve_project_folder(folder, create_subdirs=True)
        out = draft_narratives_for_folder(resolved, use_llm=False)
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertIn("sections", data)
        self.assertTrue(data["sections"])

    def test_render_to_delivered(self) -> None:
        from project_folder import render_project_folder, resolve_project_folder

        folder = self._make_folder()
        resolved = resolve_project_folder(folder, create_subdirs=True)
        outputs = render_project_folder(resolved, package=True)
        self.assertTrue(outputs["docx"].is_file())
        self.assertTrue(outputs["manifest"].is_file())
        self.assertIn("package", outputs)
        with zipfile.ZipFile(BytesIO(outputs["package"].read_bytes())) as zf:
            names = zf.namelist()
        self.assertTrue(any(n.startswith("appendices/A_") for n in names))
        self.assertTrue(any(n.startswith("appendices/D_") for n in names))
        self.assertTrue(any(n.startswith("appendices/G_") for n in names))

    def test_read_core_files_cached(self) -> None:
        from project_folder import (
            clear_project_folder_file_cache,
            resolve_project_folder,
        )

        clear_project_folder_file_cache()
        folder = self._make_folder()
        resolved = resolve_project_folder(folder)
        first = resolved.read_core_files()
        second = resolved.read_core_files()
        self.assertIs(first, second)
        resolved.invalidate_core_files()
        third = resolved.read_core_files()
        self.assertIsNot(third, first)
        self.assertEqual(third[0], first[0])
        resolved2 = resolve_project_folder(folder)
        fourth = resolved2.read_core_files()
        self.assertIs(fourth[0], first[0])
        clear_project_folder_file_cache()

    def test_heuristic_appendix_label(self) -> None:
        from ai.appendix_classifier import heuristic_appendix_label

        folder = self._make_folder()
        self.assertEqual(
            heuristic_appendix_label(folder / "appendices" / "Appendix_F_land_title.pdf"),
            "F",
        )
        self.assertEqual(
            heuristic_appendix_label(folder / "appendices" / "B.pdf"),
            "B",
        )

    def test_load_manual_appendices(self) -> None:
        from project_folder import (
            clear_project_folder_pdf_cache,
            load_manual_appendices,
            resolve_project_folder,
        )

        folder = self._make_folder()
        app_dir = folder / "appendices"
        app_dir.mkdir(exist_ok=True)
        (app_dir / "land_title_search.pdf").write_bytes(b"%PDF-1.4")
        resolved = resolve_project_folder(folder)
        clear_project_folder_pdf_cache()
        apps = load_manual_appendices(resolved)
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0].label, "F")
        self.assertEqual(apps[0].source, "uploaded")
        # Cached read returns same bytes object path
        apps2 = load_manual_appendices(resolved)
        self.assertEqual(apps[0].data, apps2[0].data)

    def test_classify_skips_when_no_pdfs(self) -> None:
        from project_folder import classify_appendices_for_folder, resolve_project_folder

        folder = self._make_folder()
        resolved = resolve_project_folder(folder, create_subdirs=True)
        self.assertIsNone(classify_appendices_for_folder(resolved, use_llm=False))

    def test_narratives_only_auto_source_ingest(self) -> None:
        from project_folder import enrich_project_folder, resolve_project_folder

        folder = self._make_folder()
        (folder / "source").mkdir(exist_ok=True)
        (folder / "source" / "phase1_esa.pdf").write_bytes(b"%PDF-1.4\n")
        resolved = resolve_project_folder(folder, create_subdirs=True)
        paths = enrich_project_folder(resolved, use_llm=False, modes=("narratives",))
        self.assertTrue(any(p.name == "source_summaries.json" for p in paths))
        self.assertTrue(any(p.name == "narratives.json" for p in paths))

    def test_enrich_includes_source_ingest(self) -> None:
        from project_folder import enrich_project_folder, resolve_project_folder

        folder = self._make_folder()
        (folder / "source").mkdir(exist_ok=True)
        (folder / "source" / "legacy_phase1_esa.pdf").write_bytes(b"%PDF-1.4")
        resolved = resolve_project_folder(folder, create_subdirs=True)
        paths = enrich_project_folder(
            resolved,
            use_llm=False,
            modes=("source-ingest",),
        )
        self.assertTrue(any(p.name == "source_index.json" for p in paths))

    def test_appendix_classifier_heuristic(self) -> None:
        from ai.appendix_classifier import classify_appendix_pdfs

        folder = self._make_folder()
        abadata = folder / "source" / "ABADATA_spill_search.pdf"
        abadata.parent.mkdir(exist_ok=True)
        abadata.write_bytes(b"%PDF-1.4 minimal")
        results = classify_appendix_pdfs([abadata], use_llm=False)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].label, "B")
        self.assertTrue(results[0].to_dict()["auto_generated_at_render"] is False)

    def test_drilling_waste_classified_as_auto_generated_note(self) -> None:
        from ai.appendix_classifier import classify_appendix_pdfs

        folder = self._make_folder()
        waste = folder / "source" / "drilling_waste_checklist.pdf"
        waste.parent.mkdir(exist_ok=True)
        waste.write_bytes(b"%PDF-1.4")
        results = classify_appendix_pdfs([waste], use_llm=False)
        self.assertEqual(results[0].label, "D")
        self.assertTrue(results[0].to_dict()["auto_generated_at_render"])

    def test_classify_appendices_for_folder(self) -> None:
        from project_folder import classify_appendices_for_folder, resolve_project_folder

        folder = self._make_folder()
        (folder / "source").mkdir(exist_ok=True)
        (folder / "source" / "land_title_search.pdf").write_bytes(b"%PDF-1.4")
        resolved = resolve_project_folder(folder, create_subdirs=True)
        out = classify_appendices_for_folder(resolved, use_llm=False)
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(payload["items"])
        self.assertEqual(payload["items"][0]["label"], "F")


if __name__ == "__main__":
    unittest.main()
