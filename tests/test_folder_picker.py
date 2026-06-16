"""Tests for native folder picker helper."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ui.folder_picker import (  # noqa: E402
    _resolve_initial_dir,
    folder_picker_available,
    pick_local_folder,
)


class FolderPickerTests(unittest.TestCase):
    def test_resolve_initial_dir_existing(self) -> None:
        here = str(Path(__file__).resolve().parent)
        self.assertEqual(_resolve_initial_dir(here), str(Path(here).resolve()))

    def test_resolve_initial_dir_parent(self) -> None:
        parent = str(Path(__file__).resolve().parent)
        child = str(Path(parent) / "missing_subdir_xyz")
        self.assertEqual(_resolve_initial_dir(child), str(Path(parent).resolve()))

    def test_resolve_initial_dir_empty(self) -> None:
        self.assertEqual(_resolve_initial_dir(""), "")

    @patch("ui.folder_picker.sys.platform", "win32")
    def test_available_on_windows(self) -> None:
        self.assertTrue(folder_picker_available())

    @patch("tkinter.filedialog.askdirectory", return_value="")
    @patch("tkinter.Tk")
    def test_pick_cancelled(self, _tk: MagicMock, _ask: MagicMock) -> None:
        self.assertIsNone(pick_local_folder(initial=""))

    @patch("tkinter.filedialog.askdirectory")
    @patch("tkinter.Tk")
    def test_pick_returns_resolved_path(self, _tk: MagicMock, ask: MagicMock) -> None:
        ask.return_value = str(ROOT)
        path = pick_local_folder(initial="")
        self.assertEqual(path, str(ROOT.resolve()))

    @patch("tkinter.filedialog.askdirectory")
    @patch("tkinter.Tk")
    def test_pick_handles_dialog_error(self, mock_tk: MagicMock, ask: MagicMock) -> None:
        import tkinter as tk

        ask.side_effect = tk.TclError("broken")
        self.assertIsNone(pick_local_folder(initial=""))
        mock_tk.return_value.destroy.assert_called()


class ProjectFolderUiTests(unittest.TestCase):
    def test_folder_session_keys(self) -> None:
        from ui.project_folder import FOLDER_SESSION_KEYS

        self.assertIn("project_folder_path_input", FOLDER_SESSION_KEYS)
        self.assertIn("project_folder_path_pending", FOLDER_SESSION_KEYS)
        self.assertIn("project_folder_core_sig", FOLDER_SESSION_KEYS)
        self.assertIn("folder_appendix_sig", FOLDER_SESSION_KEYS)
        self.assertIn("folder_browse_success", FOLDER_SESSION_KEYS)

    def test_coerce_folder_load_rejects_prepared_template_only(self) -> None:
        from template_attachments import PreparedTemplate
        from ui.project_folder import FolderLoadBundle, _coerce_folder_load

        self.assertIsNone(_coerce_folder_load(None))
        bundle = FolderLoadBundle("e", "t", object(), [])
        self.assertIs(bundle, _coerce_folder_load(bundle))
        self.assertIsInstance(
            _coerce_folder_load(("e", "t", object(), [])),
            FolderLoadBundle,
        )
        self.assertIsNone(
            _coerce_folder_load(
                PreparedTemplate(
                    docx_bytes=b"x",
                    source_format="docx",
                    source_filename="t.docx",
                )
            )
        )

    @patch("ui.project_folder.st")
    def test_load_folder_prepares_template(self, mock_st: MagicMock) -> None:
        from ui.project_folder import _load_folder

        samples_xlsx = ROOT / "samples" / "phase1_alberta_data.xlsx"
        samples_tpl = ROOT / "samples" / "phase1_alberta_template.docx"
        if not samples_xlsx.is_file() or not samples_tpl.is_file():
            self.skipTest("Run scripts/create_samples.py first")

        import shutil
        import tempfile
        from project_folder import init_sample_project_folder

        tmp = Path(tempfile.mkdtemp(prefix="esa_ui_load_"))
        try:
            init_sample_project_folder(tmp, source_user_test=False)
            class _SessionState(dict):
                def __getattr__(self, key: str) -> object:
                    return self[key]

                def __setattr__(self, key: str, value: object) -> None:
                    self[key] = value

            mock_st.session_state = _SessionState()
            excel, template, prepared, warnings = _load_folder(str(tmp)).as_tuple()
            self.assertIsNotNone(prepared)
            self.assertIsNotNone(prepared.docx_bytes)
            self.assertIn("project_folder_meta", mock_st.session_state)
            self.assertEqual(excel.name, "project_data.xlsx")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @patch("ui.project_folder._load_folder")
    @patch("ui.project_folder.st")
    def test_sync_folder_after_analyze_does_not_touch_widget_key(
        self, mock_st: MagicMock, mock_load: MagicMock
    ) -> None:
        from ui.project_folder import FolderLoadBundle, _sync_folder_after_analyze

        class _SessionState(dict):
            def __getattr__(self, key: str) -> object:
                return self.get(key)

            def __setattr__(self, key: str, value: object) -> None:
                self[key] = value

        state = _SessionState(
            project_folder_path="C:\\Projects\\260109R",
            project_folder_core_sig=("C:\\Projects\\260109R", 1, 2),
            project_folder_loaded=FolderLoadBundle("e", "t", object(), []),
        )
        mock_st.session_state = state
        _sync_folder_after_analyze("C:\\Projects\\260109R")
        mock_load.assert_not_called()
        self.assertNotIn("project_folder_path_input", state)

        state.pop("project_folder_loaded")
        state.pop("project_folder_core_sig")
        mock_resolved = MagicMock()
        mock_resolved.root = Path("C:/Projects/260109R")
        mock_resolved.excel_path.stat.return_value.st_mtime_ns = 1
        mock_resolved.template_path.stat.return_value.st_mtime_ns = 2
        mock_resolved.read_core_files.return_value = (b"x", b"y")
        mock_load.return_value = FolderLoadBundle("e", "t", object(), [])
        _sync_folder_after_analyze("C:\\Projects\\260109R", resolved=mock_resolved)
        mock_load.assert_called_once_with(
            "C:\\Projects\\260109R",
            resolved=mock_resolved,
            core_files=(b"x", b"y"),
        )
        self.assertEqual(state.get("project_folder_path"), "C:\\Projects\\260109R")
        self.assertNotIn("project_folder_path_input", state)


if __name__ == "__main__":
    unittest.main()
