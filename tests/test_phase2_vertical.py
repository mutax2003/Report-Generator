"""Phase II narrative and compliance tests."""

from __future__ import annotations

import unittest


class TestPhase2Vertical(unittest.TestCase):
    def test_enrich_and_summary(self) -> None:
        from phase2_narrative import build_phase2_executive_summary, enrich_phase2_context

        ctx = {
            "client_name": "Test Client",
            "consultant_name": "Ecoventure Inc.",
            "site_name": "Test Site",
            "lab_results": [
                {
                    "analyte": "Benzene",
                    "exceedance_flag": "Yes",
                    "matrix": "Soil",
                    "location": "BH-01",
                },
            ],
        }
        enrich_phase2_context(ctx)
        self.assertEqual(ctx["exceedance_count"], "1")
        summary = build_phase2_executive_summary(ctx)
        self.assertIn("Phase II", summary)
        self.assertIn("Benzene", ctx["exceedance_summary"])

    def test_phase2_compliance(self) -> None:
        from phase2_compliance import evaluate_phase2_compliance

        ctx = {
            "site_name": "S",
            "lab_name": "Lab",
            "lab_results": [{"analyte": "A"}],
            "conclusions_recommendations": "Done",
        }
        result = evaluate_phase2_compliance(
            ctx,
            {"prepared_by": "QP"},
            report_type="phase2_esa",
            sheet_row_counts={"lab_results": 1},
        )
        assert result is not None
        self.assertGreater(result.completeness_pct, 50.0)

    def test_remediation_summary(self) -> None:
        from remediation_narrative import build_remediation_executive_summary

        ctx = {
            "client_name": "C",
            "site_name": "S",
            "remediation_objectives": [{"media": "GW"}],
            "confirmatory_sampling": [
                {"exceedance_flag": "Yes", "analyte": "Benzene"},
            ],
        }
        text = build_remediation_executive_summary(ctx)
        self.assertIn("remediation", text.lower())
        self.assertIn("confirmatory", text.lower())

    def test_groundwater_compliance(self) -> None:
        from groundwater_compliance import evaluate_groundwater_compliance

        ctx = {
            "site_name": "S",
            "monitoring_program": "Annual",
            "gw_program_intro": "Intro text",
            "gw_sampling_methods": "Methods",
            "gw_recommendations": "Rec",
        }
        result = evaluate_groundwater_compliance(
            ctx,
            {},
            sheet_row_counts={
                "monitoring_wells": 2,
                "water_levels": 2,
                "groundwater_results": 3,
            },
        )
        assert result is not None
        self.assertGreaterEqual(result.completeness_pct, 80.0)


if __name__ == "__main__":
    unittest.main()
