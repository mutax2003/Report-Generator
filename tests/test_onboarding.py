"""Tests for consultant UX onboarding helpers (no Streamlit runtime)."""

from __future__ import annotations

import unittest

from template_tools import PreflightResult, TemplateCoverage
from ui.onboarding import GLOSSARY, NextAction, compute_next_actions


class TestOnboardingGlossary(unittest.TestCase):
    def test_glossary_has_core_terms(self) -> None:
        for term in ("OneStop", "SED 002", "DWDA", "Deliverable package"):
            self.assertIn(term, GLOSSARY)
            self.assertTrue(len(GLOSSARY[term]) > 20)


class TestComputeNextActions(unittest.TestCase):
    def test_missing_files_errors_first(self) -> None:
        actions = compute_next_actions(
            None,
            has_excel=False,
            has_template=False,
            has_output=False,
        )
        self.assertGreaterEqual(len(actions), 2)
        self.assertEqual(actions[0].priority, "error")
        self.assertEqual(actions[1].priority, "error")

    def test_preflight_errors_before_warnings(self) -> None:
        preflight = PreflightResult(
            errors=["Missing LabResults sheet"],
            coverage=TemplateCoverage(missing_in_data=["site_name"]),
        )
        actions = compute_next_actions(
            preflight,
            has_excel=True,
            has_template=True,
            has_output=False,
            prepared_by="Author",
        )
        priorities = [a.priority for a in actions]
        self.assertIn("error", priorities)
        err_idx = priorities.index("error")
        if "warning" in priorities:
            warn_idx = priorities.index("warning")
            self.assertLess(err_idx, warn_idx)

    def test_ready_when_clean_preflight(self) -> None:
        preflight = PreflightResult(
            coverage=TemplateCoverage(matched=["site_name"], template_vars={"site_name"}),
        )
        actions = compute_next_actions(
            preflight,
            has_excel=True,
            has_template=True,
            has_output=False,
            report_phase="Phase 2",
            report_type="phase2_esa",
            prepared_by="Test Author",
        )
        self.assertTrue(any(a.priority == "ready" for a in actions))

    def test_prepared_by_warning_when_blank(self) -> None:
        preflight = PreflightResult(
            coverage=TemplateCoverage(matched=["site_name"], template_vars={"site_name"}),
        )
        actions = compute_next_actions(
            preflight,
            has_excel=True,
            has_template=True,
            has_output=False,
            report_phase="Phase 2",
            report_type="phase2_esa",
            prepared_by="",
        )
        self.assertTrue(any(a.title == "Set Prepared by" for a in actions))

    def test_max_five_actions(self) -> None:
        preflight = PreflightResult(
            errors=[f"err{i}" for i in range(10)],
        )
        actions = compute_next_actions(
            preflight,
            has_excel=True,
            has_template=True,
            has_output=False,
            prepared_by="Author",
        )
        self.assertLessEqual(len(actions), 5)

    def test_next_action_dataclass(self) -> None:
        act = NextAction("warning", "Title", "Detail", "Hint")
        self.assertEqual(act.title, "Title")
        self.assertEqual(act.action_hint, "Hint")


if __name__ == "__main__":
    unittest.main()
