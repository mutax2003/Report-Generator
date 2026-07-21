"""Layout / workflow step helpers."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ui.layout import compute_workflow_step, generate_blockers, render_workflow_stepper


class TestLayout(unittest.TestCase):
    def test_workflow_steps(self) -> None:
        self.assertEqual(
            compute_workflow_step(
                has_excel=False, has_template=False, preflight_ok=None, has_output=False
            ),
            1,
        )
        self.assertEqual(
            compute_workflow_step(
                has_excel=True, has_template=True, preflight_ok=None, has_output=False
            ),
            2,
        )
        self.assertEqual(
            compute_workflow_step(
                has_excel=True, has_template=True, preflight_ok=True, has_output=False
            ),
            3,
        )
        self.assertEqual(
            compute_workflow_step(
                has_excel=True, has_template=True, preflight_ok=True, has_output=True
            ),
            4,
        )

    @patch("ui.layout.st")
    def test_workflow_stepper_renders_four_steps(self, mock_st: MagicMock) -> None:
        render_workflow_stepper(2)
        mock_st.markdown.assert_called()
        html = str(mock_st.markdown.call_args[0][0])
        self.assertIn("ev-stepper", html)
        self.assertIn("Pre-flight", html)
        self.assertIn("ev-step-current", html)
        self.assertIn("ev-step-done", html)
        self.assertIn("1. Inputs", html)

    @patch("ui.layout.st")
    def test_workflow_context_strip_renders(self, mock_st: MagicMock) -> None:
        from ui.layout import render_workflow_context_strip

        render_workflow_context_strip(
            mode_label="Excel + Word template",
            profile_label="phase1 alberta",
            excel_name="data.xlsx",
            template_name="tpl.docx",
            site_label="Wellsite A",
        )
        html = str(mock_st.markdown.call_args[0][0])
        self.assertIn("ev-context", html)
        self.assertIn("Excel + Word template", html)
        self.assertIn("data.xlsx", html)
        self.assertIn("Wellsite A", html)

    def test_generate_blockers_lists_missing_inputs(self) -> None:
        blockers = generate_blockers(
            rendering=False,
            has_excel=False,
            has_template=True,
            can_generate=False,
        )
        self.assertEqual(blockers, ["Excel not loaded (step 1)"])

    def test_generate_blockers_empty_while_rendering(self) -> None:
        self.assertEqual(
            generate_blockers(
                rendering=True,
                has_excel=False,
                has_template=False,
                can_generate=False,
            ),
            [],
        )


class TestPreflightHelpers(unittest.TestCase):
    def test_preflight_allows_generate_when_no_errors(self) -> None:
        from template_tools import PreflightResult
        from ui.preflight import preflight_allows_generate

        ok = PreflightResult(errors=[], warnings=[], sheet_names=["ProjectData"])
        self.assertTrue(preflight_allows_generate(ok))

    def test_preflight_allows_generate_false_on_errors(self) -> None:
        from template_tools import PreflightResult
        from ui.preflight import preflight_allows_generate

        bad = PreflightResult(errors=["missing sheet"], warnings=[], sheet_names=[])
        self.assertFalse(preflight_allows_generate(bad))
        self.assertFalse(preflight_allows_generate(None))


if __name__ == "__main__":
    unittest.main()
