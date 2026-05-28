"""Well log PDF extraction heuristics."""

from __future__ import annotations

import unittest

from ai.well_log_extract import _heuristic_wells


class TestWellLogExtract(unittest.TestCase):
    def test_heuristic_finds_mw_ids(self) -> None:
        from ai.well_log_extract import normalize_well_id

        text = """
        Monitoring Well MW-1 installed with screen 12.0 to 18.0 m.
        MW 2 completed at north berm.
        """
        rows = _heuristic_wells(text)
        ids = {r.well_id for r in rows}
        self.assertIn("MW-1", ids)
        self.assertIn("MW-2", ids)
        self.assertEqual(normalize_well_id("mw 2"), "MW-2")
        mw1 = next(r for r in rows if r.well_id == "MW-1")
        self.assertEqual(mw1.screen_top_m, "12.0")
        self.assertEqual(mw1.screen_bottom_m, "18.0")


if __name__ == "__main__":
    unittest.main()
