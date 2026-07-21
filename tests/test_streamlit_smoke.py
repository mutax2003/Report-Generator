"""Streamlit AppTest smoke — workflow picker, UX onboarding, folder load without a browser."""

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

        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "create_samples.py")],
            check=True,
            cwd=str(ROOT),
        )
        if not (PHASE2_FOLDER / "project_data.xlsx").is_file():
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "create_phase2_project_folder.py")],
                check=True,
                cwd=str(ROOT),
            )

    @staticmethod
    def _session_get(at: object, key: str, default=None):
        ss = at.session_state  # type: ignore[attr-defined]
        return ss[key] if key in ss else default

    @staticmethod
    def _markdown_text(at: object) -> str:
        return " ".join(m.value or "" for m in at.markdown)  # type: ignore[attr-defined]

    def _assert_no_exceptions(self, at: object) -> None:
        self.assertEqual(len(at.exception), 0, msg=str(at.exception))  # type: ignore[attr-defined]

    def _upload_workflow_app(self, *, timeout: int = 60):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=timeout)
        at.run()
        at.button(key="pick_workflow_upload").click().run()
        self._assert_no_exceptions(at)
        return at

    def _click_load_alberta_sample(self, at: object) -> object:
        at.button(key="load_phase1_alberta_sample").click().run()  # type: ignore[attr-defined]
        self._assert_no_exceptions(at)
        return at

    def test_app_starts_with_workflow_picker(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=45)
        at.run()
        self._assert_no_exceptions(at)
        headlines = [m.value or "" for m in at.markdown] + [s.value or "" for s in at.subheader]
        self.assertTrue(
            any("How do you want to generate" in h for h in headlines),
            "Expected workflow picker headline",
        )

    def test_upload_workflow_selects(self) -> None:
        at = self._upload_workflow_app(timeout=45)
        self.assertEqual(at.session_state["workflow_mode"], "upload")
        stepper_md = self._markdown_text(at)
        self.assertIn("Pre-flight", stepper_md)
        self.assertIn("ev-stepper", stepper_md)
        self.assertIn("ev-step-current", stepper_md)
        self.assertIn("1. Inputs", stepper_md)

    def test_welcome_dismiss(self) -> None:
        at = self._upload_workflow_app(timeout=60)
        at.button(key="ux_welcome_dismiss").click().run()
        self._assert_no_exceptions(at)
        self.assertTrue(self._session_get(at, "ux_welcome_dismissed"))

    def test_load_alberta_sample(self) -> None:
        at = self._click_load_alberta_sample(self._upload_workflow_app(timeout=90))
        self.assertTrue(self._session_get(at, "session_excel_bytes"))
        self.assertTrue(self._session_get(at, "session_template_bytes"))
        stepper_md = self._markdown_text(at)
        self.assertIn("loaded", stepper_md.lower())
        self.assertIn("ev-stepper", stepper_md)
        self.assertIn("3. Generate", stepper_md)
        self.assertIn("ev-step-current", stepper_md)

    def test_report_tab_next_steps(self) -> None:
        at = self._click_load_alberta_sample(self._upload_workflow_app(timeout=90))
        self.assertIn("Your next steps", self._markdown_text(at))

    def test_golden_path_generate_deliverable_zip(self) -> None:
        at = self._click_load_alberta_sample(self._upload_workflow_app(timeout=120))
        at.button(key="ux_welcome_dismiss").click().run()  # type: ignore[attr-defined]
        self._assert_no_exceptions(at)
        at.button(key="generate_report_btn").click().run()  # type: ignore[attr-defined]
        self._assert_no_exceptions(at)
        docx = self._session_get(at, "generated_docx")
        self.assertTrue(docx, "Expected generated_docx in session after Generate")
        zip_bytes = self._session_get(at, "deliverable_zip_bytes")
        self.assertTrue(zip_bytes, "Expected deliverable_zip_bytes in session")
        self.assertTrue(zip_bytes.startswith(b"PK"), "Deliverable zip should be a valid archive")
        self.assertIn("Your report is ready", self._markdown_text(at))
        self.assertTrue(self._session_get(at, "generation_record"), "Expected generation_record")

    def test_folder_workflow_loads_test_folder(self) -> None:
        from streamlit.testing.v1 import AppTest

        folder = str(PHASE2_FOLDER.resolve())
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
        at.run()
        at.button(key="pick_workflow_folder").click().run()
        self._assert_no_exceptions(at)
        at.text_input(key="project_folder_path_input").set_value(folder).run()
        at.button(key="load_project_folder").click().run()
        self._assert_no_exceptions(at)
        self.assertEqual(at.session_state["project_folder_path"], folder)
        self.assertIsNotNone(at.session_state["project_folder_loaded"])


if __name__ == "__main__":
    unittest.main()
