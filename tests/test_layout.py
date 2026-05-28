"""Layout / workflow step helpers."""

from __future__ import annotations

import unittest

from ui.layout import compute_workflow_step


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


if __name__ == "__main__":
    unittest.main()
