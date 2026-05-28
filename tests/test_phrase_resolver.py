"""Tests for multiple-choice phrase resolution."""

from __future__ import annotations

import io
import unittest
from pathlib import Path

import pandas as pd

from engine import ReportEngine, generate_phase1_alberta_excel, generate_phase1_alberta_template_docx
from phrase_resolver import (
    PHRASE_CATALOG_SHEET,
    apply_phrase_resolution,
    extract_selection_ids_from_project,
    list_phrase_definitions,
    read_phrase_catalog_sheet,
    resolve_phrase_text,
)

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


class PhraseResolverTests(unittest.TestCase):
    def test_list_phrase_definitions(self) -> None:
        defs = list_phrase_definitions()
        self.assertIn("drilling_waste_intro", defs)
        self.assertGreaterEqual(len(defs["drilling_waste_intro"]["options"]), 2)

    def test_resolve_from_json_catalog(self) -> None:
        text = resolve_phrase_text("drilling_waste_intro", "option_1_aer")
        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("AER", text)

    def test_extract_selection_columns(self) -> None:
        project = {"drilling_waste_intro_selected": "option_2", "site_name": "X"}
        sel = extract_selection_ids_from_project(project)
        self.assertEqual(sel["drilling_waste_intro"], "option_2")

    def test_phrase_catalog_sheet_roundtrip(self) -> None:
        bio = io.BytesIO()
        pd.DataFrame(
            [
                {"phrase_key": "drilling_waste_intro", "option_id": "a", "text": "Text A"},
                {"phrase_key": "drilling_waste_intro", "option_id": "b", "text": "Text B"},
            ]
        ).to_excel(bio, sheet_name=PHRASE_CATALOG_SHEET, index=False)
        lookup = read_phrase_catalog_sheet(bio.getvalue())
        self.assertEqual(lookup[("drilling_waste_intro", "b")], "Text B")

    def test_apply_phrase_resolution_excel_and_meta(self) -> None:
        ctx: dict = {"site_name": "Test"}
        project = {"drilling_waste_intro_selected": "option_1_aer"}
        warnings = apply_phrase_resolution(ctx, project, b"", meta=None)
        self.assertEqual(len(warnings), 0)
        self.assertIn("drilling_waste_intro", ctx)

        meta = {"drilling_waste_intro": "Override from UI", "drilling_waste_intro_option_id": "x"}
        apply_phrase_resolution(ctx, project, b"", meta=meta)
        self.assertEqual(ctx["drilling_waste_intro"], "Override from UI")

    def test_phase1_sample_includes_phrase_fields(self) -> None:
        xlsx = SAMPLES / "phase1_alberta_data.xlsx"
        docx = SAMPLES / "phase1_alberta_template.docx"
        generate_phase1_alberta_excel(str(xlsx))
        if not docx.is_file():
            generate_phase1_alberta_template_docx(str(docx))
        engine = ReportEngine(xlsx.read_bytes(), docx.read_bytes())
        ctx, warnings, _ = engine.dry_run(
            meta={"report_phase": "Phase 1", "report_type": "phase1_alberta"}
        )
        self.assertIn("drilling_waste_intro", ctx)
        self.assertTrue(str(ctx["drilling_waste_intro"]).strip())


if __name__ == "__main__":
    unittest.main()
