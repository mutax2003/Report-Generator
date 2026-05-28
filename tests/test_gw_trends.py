"""Groundwater trend analysis."""

from __future__ import annotations

import unittest

from ai.gw_trends import analyze_groundwater_trends


class TestGwTrends(unittest.TestCase):
    def test_detects_percent_change(self) -> None:
        ctx = {
            "monitoring_wells": [{"well_id": "MW-1"}, {"well_id": "MW-2"}],
            "groundwater_results": [
                {"well_id": "MW-1", "analyte": "Chloride", "result": "100", "sample_date": "2025-06-01"},
                {"well_id": "MW-1", "analyte": "Chloride", "result": "150", "sample_date": "2025-12-01"},
            ],
        }
        notes, audit = analyze_groundwater_trends(ctx, use_llm=False)
        self.assertTrue(any("increased" in n.message for n in notes))
        self.assertIn("gw_trends", audit.features)

    def test_single_value_no_trend_note(self) -> None:
        ctx = {
            "monitoring_wells": [{"well_id": "MW-1"}],
            "groundwater_results": [
                {"well_id": "MW-1", "analyte": "Chloride", "result": "100", "sample_date": "2026-01-01"},
            ],
        }
        notes, _ = analyze_groundwater_trends(ctx, use_llm=False)
        self.assertFalse(any("increased" in n.message or "decreased" in n.message for n in notes))

    def test_unknown_well_warning(self) -> None:
        ctx = {
            "monitoring_wells": [{"well_id": "MW-1"}],
            "groundwater_results": [{"well_id": "MW-99", "analyte": "Benzene", "result": "0.01"}],
        }
        notes, _ = analyze_groundwater_trends(ctx, use_llm=False)
        self.assertTrue(any("not listed" in n.message for n in notes))


if __name__ == "__main__":
    unittest.main()
