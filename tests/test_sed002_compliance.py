"""SED 002 Phase 1 checklist evaluation."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestSed002Compliance(unittest.TestCase):
    def test_checklist_loads(self) -> None:
        from sed002_compliance import load_checklist

        data = load_checklist()
        self.assertIn("sections", data)
        self.assertGreater(len(data["sections"]), 5)

    def test_evaluate_phase1_context(self) -> None:
        from sed002_compliance import evaluate_sed002_compliance

        ctx = {
            "client_name": "Example Energy Ltd.",
            "uwi": "00/04-04-049-04W4/0",
            "asset_activity_type": "Oil well",
            "spud_date": "15-Mar-2004",
            "aer_waste_compliance_option": "Option 1",
            "drilling_waste_summary": "Summary",
            "infrastructure_summary": "Road, berm",
            "site_visit_completed": "No",
            "records_review_summary": "Records reviewed",
            "air_photo_observations": "2015 photo",
            "interview_operator_summary": "Operator interviewed",
            "executive_summary": "Text",
            "phase2_esa_required": "Yes",
            "qp_names": "QP",
            "drilling_waste": [{"mud_type": "Gel", "volume_m3": "1"}],
        }
        meta = {"prepared_by": "Ecoventure QP", "date_of_issue": "2026-05-20"}
        result = evaluate_sed002_compliance(
            ctx,
            meta,
            report_type="phase1_alberta",
            appendix_labels_present={"B", "D", "H"},
        )
        assert result is not None
        self.assertGreater(result.completeness_pct, 50.0)
        self.assertTrue(
            any("Phase II" in w or "Phase 2" in w for w in result.phase2_warnings)
        )

    def test_phase2_decision_enrich(self) -> None:
        from phase1_decision import enrich_context_phase2_decision

        out = enrich_context_phase2_decision(
            {
                "phase2_esa_required": "Yes",
                "site_visit_completed": "No",
                "investigations_recommended": "well centre",
            }
        )
        self.assertEqual(out["phase2_recommended"], "Yes")
        self.assertTrue(out["phase2_reasons"])


class TestOnestopExport(unittest.TestCase):
    def test_onestop_summary_in_zip(self) -> None:
        from deliverable_pack import DeliverablePackage, build_deliverable_zip

        ctx = {"client_name": "Test", "uwi": "1", "executive_summary": "x"}
        pkg = DeliverablePackage(
            report_docx=b"PK",
            report_filename="t.docx",
            render_context=ctx,
            render_meta={"prepared_by": "QP", "date_of_issue": "2026-01-01"},
        )
        z = build_deliverable_zip(pkg)
        import io
        import zipfile

        with zipfile.ZipFile(io.BytesIO(z)) as zf:
            names = zf.namelist()
        self.assertTrue(any(n.startswith("onestop/phase1_esa_summary.json") for n in names))


if __name__ == "__main__":
    unittest.main()
