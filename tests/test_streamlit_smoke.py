"""Streamlit AppTest smoke — workflow picker and folder load without a browser."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PHASE2_FOLDER = ROOT / "user_test" / "phase2_alberta"


class StreamlitSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import subprocess

        if not (PHASE2_FOLDER / "project_data.xlsx").is_file():
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "create_phase2_project_folder.py")],
                check=True,
                cwd=str(ROOT),
            )

    def test_app_starts_with_workflow_picker(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=45)
        at.run()
        self.assertEqual(len(at.exception), 0, msg=str(at.exception))
        headlines = [m.value or "" for m in at.markdown] + [s.value or "" for s in at.subheader]
        self.assertTrue(
            any("How do you want to generate" in h for h in headlines),
            "Expected workflow picker headline",
        )

    def test_upload_workflow_selects(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=45)
        at.run()
        at.button(key="pick_workflow_upload").click().run()
        self.assertEqual(len(at.exception), 0, msg=str(at.exception))
        self.assertEqual(at.session_state["workflow_mode"], "upload")

    def test_folder_workflow_loads_test_folder(self) -> None:
        from streamlit.testing.v1 import AppTest

        folder = str(PHASE2_FOLDER.resolve())
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
        at.run()
        at.button(key="pick_workflow_folder").click().run()
        self.assertEqual(len(at.exception), 0, msg=str(at.exception))
        at.text_input(key="project_folder_path_input").set_value(folder).run()
        at.button(key="load_project_folder").click().run()
        self.assertEqual(len(at.exception), 0, msg=str(at.exception))
        self.assertEqual(at.session_state["project_folder_path"], folder)
        self.assertIsNotNone(at.session_state["project_folder_loaded"])


if __name__ == "__main__":
    unittest.main()
