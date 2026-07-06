"""Reclamation certificate compliance checklist."""

from __future__ import annotations

import unittest

from reclamation_compliance import evaluate_reclamation_compliance


class ReclamationComplianceTests(unittest.TestCase):
    def test_non_reclamation_profile_returns_none(self) -> None:
        result = evaluate_reclamation_compliance(
            {"uwi": "100/01-01-001-00W4"},
            {},
            report_type="phase1_alberta",
        )
        self.assertIsNone(result)

    def test_required_fields_missing(self) -> None:
        result = evaluate_reclamation_compliance(
            {},
            {},
            report_type="reclamation_certificate",
        )
        assert result is not None
        self.assertFalse(result.ready_for_qp_review)
        self.assertGreater(len(result.required_missing), 0)

    def test_satisfied_required_fields(self) -> None:
        result = evaluate_reclamation_compliance(
            {
                "uwi": "100/01-01-001-00W4",
                "conclusions_recommendations": "Site meets reclamation criteria.",
            },
            {},
            report_type="reclamation_certificate",
            sheet_row_counts={"reclamation_tasks": 2},
        )
        assert result is not None
        self.assertTrue(result.ready_for_qp_review)
        self.assertGreater(result.completeness_pct, 0)


if __name__ == "__main__":
    unittest.main()
