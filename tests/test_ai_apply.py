"""Unit tests for AI draft apply helpers and appendix manifest preference."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from ai.apply_drafts import (
    load_appendix_manifest_labels,
    load_field_suggestions,
    load_narratives_payload,
    narratives_from_session_drafts,
    patch_project_data_fields,
    preview_project_data_patch,
)
from ai.excel_builder import well_rows_to_xlsx_bytes
from ai.models import NarrativeDraft
from engine import MONITORING_WELLS_SHEET, PROJECT_SHEET


def _xlsx_with_project(**fields: str) -> bytes:
    df = pd.DataFrame([fields or {"site_name": "A"}])
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df.to_excel(w, sheet_name=PROJECT_SHEET, index=False)
    return out.getvalue()


class ApplyDraftsTests(unittest.TestCase):
    def test_patch_skips_filled_unless_overwrite(self) -> None:
        excel = _xlsx_with_project(site_name="Existing", executive_summary="")
        fields = {"site_name": "New", "executive_summary": "Draft summary"}
        preview_apply, preview_skip, _ = preview_project_data_patch(
            excel, fields, overwrite_filled=False
        )
        self.assertIn("executive_summary", preview_apply)
        self.assertIn("site_name", preview_skip)

        new_bytes, applied, skipped = patch_project_data_fields(
            excel, fields, overwrite_filled=False
        )
        self.assertIn("executive_summary", applied)
        self.assertIn("site_name", skipped)
        df = pd.read_excel(io.BytesIO(new_bytes), sheet_name=PROJECT_SHEET)
        self.assertEqual(str(df.iloc[0]["site_name"]), "Existing")
        self.assertEqual(str(df.iloc[0]["executive_summary"]), "Draft summary")

        new_bytes2, applied2, skipped2 = patch_project_data_fields(
            excel, fields, overwrite_filled=True
        )
        self.assertIn("site_name", applied2)
        self.assertEqual(skipped2, [])
        df2 = pd.read_excel(io.BytesIO(new_bytes2), sheet_name=PROJECT_SHEET)
        self.assertEqual(str(df2.iloc[0]["site_name"]), "New")

    def test_load_narratives_and_suggestions(self) -> None:
        payload = {
            "sections": [
                {"section": "executive_summary", "text": "Exec"},
                {"section": "conclusions_limitations", "text": "Conclude"},
            ]
        }
        fields = load_narratives_payload(payload)
        self.assertEqual(fields["executive_summary"], "Exec")
        self.assertEqual(fields["conclusions_recommendations"], "Conclude")

        sugg = load_field_suggestions({"fields": {"well_name": "12-34"}})
        self.assertEqual(sugg["well_name"], "12-34")

        from_session = narratives_from_session_drafts(
            [NarrativeDraft(section="site_description", text="Site text")]
        )
        self.assertEqual(from_session["site_description"], "Site text")

    def test_appendix_manifest_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            drafts = Path(tmp)
            (drafts / "appendix_manifest.json").write_text(
                json.dumps(
                    {
                        "items": [
                            {"filename": "sketch.pdf", "label": "H"},
                            {"filename": "bad.pdf", "label": "Z"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            labels = load_appendix_manifest_labels(drafts)
            self.assertEqual(labels["sketch.pdf"], "H")
            self.assertNotIn("bad.pdf", labels)

    def test_well_rows_merge(self) -> None:
        base = _xlsx_with_project(site_name="S")
        out = well_rows_to_xlsx_bytes(
            [{"Well ID": "MW-1", "Screen Top": "1", "Screen Bottom": "2"}],
            existing_excel=base,
        )
        xl = pd.ExcelFile(io.BytesIO(out), engine="openpyxl")
        self.assertIn(PROJECT_SHEET, xl.sheet_names)
        self.assertIn(MONITORING_WELLS_SHEET, xl.sheet_names)


class AppendixManifestLoadTests(unittest.TestCase):
    def test_load_manual_prefers_manifest(self) -> None:
        from project_folder import (
            clear_project_folder_pdf_cache,
            load_manual_appendices,
            resolve_project_folder,
        )

        root = Path(__file__).resolve().parents[1]
        samples_xlsx = root / "samples" / "phase1_alberta_data.xlsx"
        samples_docx = root / "samples" / "phase1_alberta_template.docx"
        if not samples_xlsx.is_file() or not samples_docx.is_file():
            self.skipTest("samples missing")

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "project_data.xlsx").write_bytes(samples_xlsx.read_bytes())
            (folder / "template.docx").write_bytes(samples_docx.read_bytes())
            app_dir = folder / "appendices"
            app_dir.mkdir()
            # Filename heuristic → F (land title); manifest forces H
            pdf = app_dir / "land_title_search.pdf"
            pdf.write_bytes(b"%PDF-1.4")
            drafts = folder / "ai_drafts"
            drafts.mkdir()
            (drafts / "appendix_manifest.json").write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "filename": "land_title_search.pdf",
                                "label": "H",
                                "confidence": 0.9,
                                "source": "llm",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            resolved = resolve_project_folder(folder, create_subdirs=True)
            clear_project_folder_pdf_cache()
            apps = load_manual_appendices(resolved)
            self.assertEqual(len(apps), 1)
            self.assertEqual(apps[0].label, "H")


if __name__ == "__main__":
    unittest.main()
