"""Signum-style Phase I executive summary builder."""

from __future__ import annotations

import unittest

from phase1_narrative import build_phase1_executive_summary


class TestPhase1ExecutiveSummary(unittest.TestCase):
    def test_signum_structure_ecoventure_voice(self) -> None:
        ctx = {
            "consultant_name": "Ecoventure Inc.",
            "client_name": "Example Energy Ltd.",
            "well_name": "Example 4D Windy 4-4-49-4",
            "spud_date": "15-Mar-2004",
            "cased_date": "17-Mar-2004",
            "reentry_detail": (
                "The well was re-entered in June 2004 and drilled to a total depth of "
                "710 metres (m), and the well is currently suspended"
            ),
            "production_fluid": "gas with water",
            "aer_waste_compliance_option": "Option 1 (AER, 2014)",
            "drilling_waste_summary": (
                "110 m3 of drilling waste (surface mud and fasthole mud) was disposed of via LWD"
            ),
            "phase2_drilling_waste_required": "No",
            "air_photo_observations": (
                "The 2015 historical air photo shows the well centre"
            ),
            "site_visit_completed": "No",
            "investigations_recommended": (
                "well centre and the production areas be investigated"
            ),
            "client_phase_keyword": "Phase II",
        }
        text = build_phase1_executive_summary(ctx)
        self.assertIn("was contracted by Example Energy Ltd.", text)
        self.assertIn("Ecoventure Inc.", text)
        self.assertIn("Phase I Environmental Site Assessment", text)
        self.assertIn("associated facilities", text)
        self.assertIn("spud 15-Mar-2004", text)
        self.assertIn("cased on 17-Mar-2004", text)
        self.assertIn("re-entered in June 2004", text)
        self.assertIn("Checklist Compliance", text)
        self.assertIn("Phase II ESA is not required for the drilling waste", text)
        self.assertIn("2015 historical air photo", text)
        self.assertIn("site visit has not been completed", text)
        self.assertIn("After reviewing regulatory information", text)
        self.assertIn("informational interviews", text)
        self.assertIn("keyword is Phase II", text)

    def test_auto_fill_when_excel_executive_empty(self) -> None:
        from engine import ReportEngine
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        xlsx = root / "samples" / "phase1_alberta_data.xlsx"
        tpl = root / "samples" / "phase1_alberta_template.docx"
        if not xlsx.is_file():
            from engine import generate_phase1_alberta_excel, generate_phase1_alberta_template_docx

            generate_phase1_alberta_excel(str(xlsx))
            generate_phase1_alberta_template_docx(str(tpl))

        import pandas as pd

        book = pd.read_excel(xlsx, sheet_name=None)
        book["ProjectData"].loc[0, "executive_summary"] = ""
        out = root / "samples" / "_test_empty_exec.xlsx"
        with pd.ExcelWriter(out, engine="openpyxl") as w:
            for name, df in book.items():
                df.to_excel(w, sheet_name=name, index=False)

        engine = ReportEngine(
            excel_bytes=out.read_bytes(),
            template_bytes=tpl.read_bytes(),
        )
        ctx = engine.build_context({"report_phase": "Phase 1"})
        self.assertTrue(ctx.get("_executive_summary_auto_generated"))
        self.assertIn("was contracted by", ctx.get("executive_summary", ""))
        out.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
