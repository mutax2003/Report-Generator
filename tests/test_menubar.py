"""Unit tests for Windows-style menubar helpers and HTML help pack."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class HelpBuildTests(unittest.TestCase):
    def test_build_help_writes_index(self) -> None:
        from scripts.build_help import HELP_PAGES, build_help

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            docs = tmp_path / "docs"
            docs.mkdir()
            (docs / "00-start-here.md").write_text("# Start\n\nHello help.\n", encoding="utf-8")
            for name in (
                "02-user-guide.md",
                "03-excel-data-guide.md",
                "04-template-authoring.md",
                "11-alberta-phase1-esa.md",
                "22-project-folder-workflow.md",
                "09-ai-assistant.md",
            ):
                (docs / name).write_text(f"# {name}\n\nContent.\n", encoding="utf-8")

            index = build_help(tmp_path)
            self.assertTrue(index.is_file())
            html = index.read_text(encoding="utf-8")
            self.assertIn("ESA Report Generator Help", html)
            self.assertIn("Keyboard shortcuts", html)
            self.assertIn("F1", html)
            self.assertIn('id="start"', html)

            for _anchor, _title, rel in HELP_PAGES:
                if not rel:
                    continue
                self.assertTrue((ROOT / rel).is_file(), f"Missing help source {rel}")

    def test_repo_help_sources_exist(self) -> None:
        from scripts.build_help import HELP_PAGES

        for _anchor, _title, rel in HELP_PAGES:
            if not rel:
                continue
            self.assertTrue((ROOT / rel).is_file(), f"Missing help source {rel}")
        # Prefer committed/built pack; build into temp only if missing
        index = ROOT / "help" / "index.html"
        if not index.is_file():
            from scripts.build_help import build_help

            build_help(ROOT)
        self.assertTrue(index.is_file())
        self.assertGreater(index.stat().st_size, 500)


class MenubarHelperTests(unittest.TestCase):
    def test_smoke_labels(self) -> None:
        from ui.menubar import menubar_smoke_labels

        labels = menubar_smoke_labels()
        self.assertEqual(labels, ["File", "Edit", "View", "Tools", "Help"])

    def test_shortcuts_dict_has_f1(self) -> None:
        from ui.menubar import SHORTCUTS

        self.assertEqual(SHORTCUTS["help_contents"], "F1")
        self.assertEqual(SHORTCUTS["file_open_folder"], "")

    def test_open_help_contents_missing(self) -> None:
        from ui import menubar as mb

        with mock.patch.object(mb, "HELP_INDEX", ROOT / "help" / "__missing_help__.html"):
            self.assertFalse(mb.open_help_contents())


class StreamlitMenubarSmoke(unittest.TestCase):
    @staticmethod
    def _session_get(at: object, key: str, default=None):
        ss = at.session_state  # type: ignore[attr-defined]
        return ss[key] if key in ss else default

    def test_picker_shows_menubar_popovers(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=45)
        at.run()
        self.assertEqual(len(at.exception), 0, msg=str(at.exception))
        labels = []
        for attr in ("button", "popover"):
            widgets = getattr(at, attr, None)
            if widgets is None:
                continue
            try:
                for w in widgets:
                    labels.append(getattr(w, "label", None) or getattr(w, "value", None) or "")
            except TypeError:
                pass
        joined = " ".join(str(x) for x in labels)
        markdown = " ".join(m.value or "" for m in at.markdown)
        self.assertIn(
            "ev-menubar",
            markdown,
            "Expected menubar chrome CSS / wrapper in page markdown",
        )
        # AppTest often surfaces popover *items*, not the File/Edit parent labels.
        for item in (
            "Load Alberta Phase I sample",
            "Toggle Simple mode",
            "Glossary",
            "Contents",
        ):
            self.assertTrue(
                item in joined or any(item in str(x) for x in labels),
                f"Expected menubar item {item!r} (got {labels!r})",
            )

    def test_menu_load_sample_and_clear(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
        at.run()
        at.button(key="pick_workflow_upload").click().run()
        self.assertEqual(len(at.exception), 0, msg=str(at.exception))
        at.button(key="menu_file_sample").click().run()
        self.assertEqual(len(at.exception), 0, msg=str(at.exception))
        self.assertTrue(self._session_get(at, "session_excel_bytes"))
        self.assertTrue(self._session_get(at, "session_template_bytes"))

        at.session_state["generated_docx"] = b"PK\x03\x04fake"
        at.session_state["ux_deliverable_download_clicked"] = True
        at.button(key="menu_file_clear").click().run()
        self.assertEqual(len(at.exception), 0, msg=str(at.exception))
        self.assertIsNone(self._session_get(at, "generated_docx"))
        self.assertIsNone(self._session_get(at, "ux_deliverable_download_clicked"))

    def test_menu_toggle_simple_mode(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
        at.run()
        at.button(key="pick_workflow_upload").click().run()
        before = bool(self._session_get(at, "ux_simple_mode", True))
        at.button(key="menu_edit_simple").click().run()
        self.assertEqual(len(at.exception), 0, msg=str(at.exception))
        after = bool(self._session_get(at, "ux_simple_mode"))
        self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()
