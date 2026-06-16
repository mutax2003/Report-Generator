"""Tests for source/ PDF ingest pipeline."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SourceIngestTests(unittest.TestCase):
    def test_classify_pdf_route(self) -> None:
        from ai.source_ingest import classify_pdf_route

        self.assertEqual(classify_pdf_route("lab_coa_certificate.pdf"), "lab")
        self.assertEqual(classify_pdf_route("260109R Phase 1 ESA Final.pdf"), "esa")
        self.assertEqual(classify_pdf_route("ABADATA_spill_search.pdf"), "generic")

    def test_chunk_text(self) -> None:
        from ai.source_ingest import chunk_text

        text = "word " * 2000
        chunks = chunk_text(text, chunk_size=500)
        self.assertGreater(len(chunks), 1)
        self.assertLessEqual(len(chunks[0]), 500)

    def test_ingest_offline_empty_pdf(self) -> None:
        from ai.source_ingest import ingest_source_pdfs

        tmp = Path(tempfile.mkdtemp(prefix="esa_src_"))
        pdf = tmp / "source" / "generic_doc.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.write_bytes(b"%PDF-1.4\n")
        drafts = tmp / "ai_drafts"
        written, summaries, audit = ingest_source_pdfs(
            [pdf],
            drafts,
            use_llm=False,
            write_rag_snippets=False,
        )
        self.assertTrue(any(p.name == "source_index.json" for p in written))
        self.assertTrue(any(p.name == "source_summaries.json" for p in written))
        self.assertEqual(len(summaries), 1)
        self.assertFalse(audit.used_llm)
        index = json.loads((drafts / "source_index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["pdf_count"], 1)
        self.assertEqual(index["items"][0]["route"], "generic")

    def test_source_ingest_for_folder(self) -> None:
        from project_folder import init_sample_project_folder, source_ingest_for_folder
        from project_folder import resolve_project_folder

        folder = Path(tempfile.mkdtemp(prefix="esa_src_folder_"))
        init_sample_project_folder(folder, source_user_test=False)
        esa = folder / "source" / "260109R_Phase_1_ESA.pdf"
        esa.parent.mkdir(exist_ok=True)
        esa.write_bytes(b"%PDF-1.4\n")
        resolved = resolve_project_folder(folder, create_subdirs=True)
        paths = source_ingest_for_folder(resolved, use_llm=False)
        self.assertTrue(paths)
        self.assertTrue((resolved.ai_drafts_dir / "source_index.json").is_file())

    def test_ingest_empty_returns_nothing(self) -> None:
        from ai.source_ingest import ingest_source_pdfs

        tmp = Path(tempfile.mkdtemp(prefix="esa_src_empty_"))
        written, summaries, audit = ingest_source_pdfs([], tmp / "ai_drafts", use_llm=False)
        self.assertEqual(written, [])
        self.assertEqual(summaries, [])
        self.assertFalse(audit.used_llm)

    def test_ingest_skips_invalid_pdf(self) -> None:
        from ai.source_ingest import ingest_source_pdfs

        tmp = Path(tempfile.mkdtemp(prefix="esa_src_bad_"))
        pdf = tmp / "not_a_pdf.pdf"
        pdf.write_bytes(b"NOTPDF")
        drafts = tmp / "ai_drafts"
        written, summaries, _audit = ingest_source_pdfs([pdf], drafts, use_llm=False)
        self.assertEqual(len(summaries), 0)
        index = json.loads((drafts / "source_index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["pdf_count"], 1)
        self.assertIn("Not a valid PDF", index["items"][0]["warnings"][0])

    def test_narrative_context_filters_internal_keys(self) -> None:
        from ai.narrative import _context_for_narrative_prompt

        ctx = _context_for_narrative_prompt(
            {"site_name": "Test", "_source_summaries": [], "lab_results": []}
        )
        self.assertIn("site_name", ctx)
        self.assertNotIn("_source_summaries", ctx)
        self.assertNotIn("lab_results", ctx)

    def test_load_summaries_for_narrative(self) -> None:
        from ai.source_ingest import load_summaries_for_narrative

        tmp = Path(tempfile.mkdtemp(prefix="esa_sum_"))
        drafts = tmp / "ai_drafts"
        drafts.mkdir()
        (drafts / "source_summaries.json").write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "filename": "a.pdf",
                            "route": "esa",
                            "summary": "Site UWI 01-01-001-01W5",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        loaded = load_summaries_for_narrative(drafts)
        self.assertEqual(len(loaded), 1)
        self.assertIn("UWI", loaded[0]["summary"])


if __name__ == "__main__":
    unittest.main()
