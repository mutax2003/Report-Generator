"""Groundwater narrative enrichment."""

from __future__ import annotations

import unittest

from groundwater_narrative import build_groundwater_executive_summary, enrich_groundwater_context


class TestGroundwaterNarrative(unittest.TestCase):
    def test_enrich_and_summary(self) -> None:
        ctx = {
            "client_name": "Test Client",
            "site_name": "Test Site",
            "monitoring_program": "annual monitoring",
            "monitoring_wells": [{"well_id": "MW-1"}],
            "water_levels": [{"well_id": "MW-1"}],
            "groundwater_results": [
                {"analyte": "Chloride", "exceedance_flag": "Yes"},
            ],
        }
        enrich_groundwater_context(ctx)
        self.assertEqual(ctx["well_count"], "1")
        summary = build_groundwater_executive_summary(ctx)
        self.assertIn("Ecoventure", summary)
        self.assertIn("exceed", summary.lower())


if __name__ == "__main__":
    unittest.main()
