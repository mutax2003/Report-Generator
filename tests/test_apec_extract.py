"""Tests for APEC extract heuristics and Excel merge."""

from __future__ import annotations

import io
import unittest

import pandas as pd

from ai.apec_extract import (
    extract_apecs_from_text,
    extract_text_from_upload,
    merge_apec_results,
)
from ai.excel_builder import apec_rows_to_xlsx_bytes
from ai.models import ApecExtractResult, ApecExtractRow
from engine import APECS_SHEET, PROJECT_SHEET
from security import SecurityError


SAMPLE_TEXT = """
Historical Phase I ESA review.
A former flare pit was located at the SW corner of the lease.
ABADATA spill search identified a minor release near the well centre.
Produced water storage tank berm SE of well centre.
Phase II ESA is recommended to further evaluate identified areas of potential environmental concern.
"""


class ApecExtractTests(unittest.TestCase):
    def test_heuristic_finds_concerns(self) -> None:
        result, audit = extract_apecs_from_text(
            SAMPLE_TEXT, source_document="hist.pdf", use_llm=False
        )
        self.assertFalse(audit.used_llm)
        self.assertGreaterEqual(len(result.rows), 2)
        types = {r.concern_type for r in result.rows}
        self.assertTrue({"flare_pit", "spill", "storage_tank"} & types)
        self.assertTrue(any(r.phase2_recommended == "Y" for r in result.rows))
        self.assertTrue(all(r.source_document == "hist.pdf" for r in result.rows))

    def test_merge_renumbers(self) -> None:
        a = ApecExtractResult(
            rows=[
                ApecExtractRow(
                    apec_id="APEC-9",
                    apec_name="A",
                    concern_type="spill",
                    evidence_summary="spill near road",
                )
            ]
        )
        b = ApecExtractResult(
            rows=[
                ApecExtractRow(
                    apec_id="APEC-1",
                    apec_name="B",
                    concern_type="flare_pit",
                    evidence_summary="flare pit SW",
                )
            ]
        )
        merged = merge_apec_results([a, b])
        self.assertEqual(len(merged.rows), 2)
        self.assertEqual(merged.rows[0].apec_id, "APEC-1")
        self.assertEqual(merged.rows[1].apec_id, "APEC-2")

    def test_rejects_images(self) -> None:
        with self.assertRaises(SecurityError):
            extract_text_from_upload(b"\xff\xd8\xff", "scan.jpg")

    def test_apec_sheet_merge_append(self) -> None:
        base = apec_rows_to_xlsx_bytes(
            [
                {
                    "apec_id": "APEC-1",
                    "apec_name": "Old",
                    "location_description": "",
                    "concern_type": "other",
                    "source_of_concern": "records",
                    "evidence_summary": "x",
                    "source_document": "a.pdf",
                    "phase2_recommended": "N",
                    "notes": "",
                }
            ]
        )
        out = apec_rows_to_xlsx_bytes(
            [
                {
                    "apec_id": "APEC-1",
                    "apec_name": "New",
                    "location_description": "",
                    "concern_type": "spill",
                    "source_of_concern": "records",
                    "evidence_summary": "y",
                    "source_document": "b.pdf",
                    "phase2_recommended": "Y",
                    "notes": "",
                }
            ],
            existing_excel=base,
            mode="append",
        )
        df = pd.read_excel(io.BytesIO(out), sheet_name=APECS_SHEET)
        self.assertEqual(len(df), 2)
        self.assertEqual(list(df["apec_id"]), ["APEC-1", "APEC-2"])
        xl = pd.ExcelFile(io.BytesIO(out), engine="openpyxl")
        self.assertIn(PROJECT_SHEET, xl.sheet_names)


class ApecProfileMappingTests(unittest.TestCase):
    def test_phase1_maps_apecs(self) -> None:
        from report_profile import get_profile_spec

        spec = get_profile_spec("phase1_alberta")
        self.assertEqual(spec["sheet_mappings"].get("Apecs"), "apecs")


if __name__ == "__main__":
    unittest.main()
