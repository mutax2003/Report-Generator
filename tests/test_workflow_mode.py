"""Tests for startup workflow mode helpers."""

from __future__ import annotations

import unittest


class WorkflowModeTests(unittest.TestCase):
    def test_workflow_labels(self) -> None:
        from ui.workflow_mode import WORKFLOW_FOLDER, WORKFLOW_UPLOAD, workflow_label

        self.assertIn("folder", workflow_label(WORKFLOW_FOLDER).lower())
        self.assertIn("template", workflow_label(WORKFLOW_UPLOAD).lower())


if __name__ == "__main__":
    unittest.main()
