"""Tests for compliance_helpers shared utilities."""

from __future__ import annotations

import unittest

from compliance_helpers import (
    normalize_appendix_labels,
    parse_float,
    resolved_appendix_labels,
    sorted_appendix_label_list,
    yes_value,
)


class ComplianceHelpersTests(unittest.TestCase):
    def test_normalize_appendix_labels(self) -> None:
        self.assertEqual(
            normalize_appendix_labels(["h", " D ", ""]),
            frozenset({"H", "D"}),
        )

    def test_sorted_appendix_label_list(self) -> None:
        self.assertEqual(sorted_appendix_label_list({"g", "a"}), ["A", "G"])

    def test_yes_value_extended(self) -> None:
        self.assertTrue(yes_value("required"))
        self.assertTrue(yes_value("likely"))
        self.assertFalse(yes_value("no"))

    def test_resolved_appendix_labels(self) -> None:
        ctx = {"_dwda_appendix_labels_evaluated": frozenset({"A", "D", "H"})}
        self.assertEqual(
            resolved_appendix_labels(ctx, {"B"}),
            frozenset({"A", "D", "H"}),
        )
        self.assertEqual(
            resolved_appendix_labels({}, ["h"]),
            frozenset({"H"}),
        )


if __name__ == "__main__":
    unittest.main()
