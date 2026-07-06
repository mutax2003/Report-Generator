"""Unified Phase II trigger collection."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from phase2_triggers import collect_phase2_reasons, is_phase2_likely


class Phase2TriggersTests(unittest.TestCase):
    def test_empty_context_not_likely(self) -> None:
        likely, reasons = collect_phase2_reasons({})
        self.assertFalse(likely)
        self.assertEqual(reasons, [])

    def test_phase2_esa_required_flag(self) -> None:
        likely, reasons = collect_phase2_reasons({"phase2_esa_required": "Yes"})
        self.assertTrue(likely)
        self.assertTrue(any("Phase II ESA is required" in r for r in reasons))

    def test_spills_trigger(self) -> None:
        likely, reasons = collect_phase2_reasons({"spills_releases": "Historical diesel spill"})
        self.assertTrue(likely)
        self.assertTrue(any("Spills/releases" in r for r in reasons))

    def test_dwda_compliance_reasons_merged(self) -> None:
        dwda = SimpleNamespace(phase2_reasons=["Appendix H missing for on-lease disposal"])
        likely, reasons = collect_phase2_reasons({}, dwda_compliance=dwda)
        self.assertTrue(likely)
        self.assertIn("Appendix H missing for on-lease disposal", reasons)

    def test_deduplicates_reasons(self) -> None:
        dwda = SimpleNamespace(phase2_reasons=["Appendix H missing", "appendix h missing"])
        _, reasons = collect_phase2_reasons({"spills_releases": "none"}, dwda_compliance=dwda)
        self.assertEqual(len(reasons), 1)

    def test_is_phase2_likely_wrapper(self) -> None:
        self.assertTrue(is_phase2_likely({"phase2_recommended": "Yes"}))


if __name__ == "__main__":
    unittest.main()
