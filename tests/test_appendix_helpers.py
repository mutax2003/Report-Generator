"""Tests for appendix panel helpers."""

from __future__ import annotations

import unittest

from ui.appendix_panel import first_missing_onestop_label


class TestAppendixHelpers(unittest.TestCase):
    def test_first_missing_onestop_label(self) -> None:
        self.assertEqual(
            first_missing_onestop_label(set(), set()),
            "B",
        )
        self.assertIsNone(
            first_missing_onestop_label({"B", "C", "E", "F", "H"}, set()),
        )
        self.assertEqual(
            first_missing_onestop_label(set(), {"D", "G", "A"}),
            "B",
        )
        self.assertEqual(
            first_missing_onestop_label({"B", "C"}, {"A", "D", "G"}),
            "E",
        )


if __name__ == "__main__":
    unittest.main()
