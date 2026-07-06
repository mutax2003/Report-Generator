"""Tests for startup workflow mode helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch
from unittest.mock import MagicMock


class WorkflowModeTests(unittest.TestCase):
    def test_workflow_labels(self) -> None:
        from ui.workflow_mode import WORKFLOW_FOLDER, WORKFLOW_UPLOAD, workflow_label

        self.assertIn("folder", workflow_label(WORKFLOW_FOLDER).lower())
        self.assertIn("template", workflow_label(WORKFLOW_UPLOAD).lower())

    def test_has_generated_report_detects_docx(self) -> None:
        from ui.workflow_mode import _has_generated_report

        with patch("ui.workflow_mode.st") as mock_st:
            mock_st.session_state = {"generated_docx": b"docx"}
            self.assertTrue(_has_generated_report())

    def test_has_loaded_inputs_detects_upload(self) -> None:
        from ui.workflow_mode import _has_loaded_inputs

        with patch("ui.workflow_mode.st") as mock_st:
            mock_st.session_state = {"upload_excel": MagicMock()}
            self.assertTrue(_has_loaded_inputs())

    def test_needs_confirm_when_inputs_loaded(self) -> None:
        from ui.workflow_mode import _needs_workflow_change_confirm

        with patch("ui.workflow_mode.st") as mock_st:
            mock_st.session_state = {"project_folder_loaded": True}
            self.assertTrue(_needs_workflow_change_confirm())


if __name__ == "__main__":
    unittest.main()
