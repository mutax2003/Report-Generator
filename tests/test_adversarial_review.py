"""Tests for ai.adversarial_review and agent_folder_report --mode review."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class AdversarialReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.samples_xlsx = ROOT / "samples" / "phase1_alberta_data.xlsx"
        cls.samples_tpl = ROOT / "samples" / "phase1_alberta_template.docx"
        if not cls.samples_xlsx.is_file() or not cls.samples_tpl.is_file():
            raise unittest.SkipTest("Run scripts/create_samples.py first")

    def _make_folder(self) -> Path:
        from project_folder import init_sample_project_folder

        tmp = Path(tempfile.mkdtemp(prefix="esa_adv_"))
        init_sample_project_folder(tmp, source_user_test=False, profile="phase1_alberta")
        return tmp

    def test_review_writes_artifacts_and_passes_clean_folder(self) -> None:
        from ai.adversarial_review import run_adversarial_review
        from project_folder import resolve_project_folder
        from scripts.agent_folder_report import run_mode

        tmp = self._make_folder()
        try:
            resolved = resolve_project_folder(tmp, create_subdirs=True)
            result = run_adversarial_review(resolved)
            self.assertTrue((tmp / "ai_drafts" / "adversarial_review.md").is_file())
            self.assertTrue((tmp / "ai_drafts" / "adversarial_review.json").is_file())
            self.assertTrue(result.can_render)
            code = run_mode(tmp, "review")
            # Warnings (e.g. no source PDFs) do not fail; only blockers.
            self.assertEqual(code, 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_red_flag_prose_is_blocker(self) -> None:
        from ai.adversarial_review import run_adversarial_review
        from project_folder import resolve_project_folder

        tmp = self._make_folder()
        try:
            drafts = tmp / "ai_drafts"
            drafts.mkdir(exist_ok=True)
            (drafts / "narratives.json").write_text(
                json.dumps(
                    {
                        "sections": [
                            {
                                "section": "executive_summary",
                                "text": "As an AI I cannot invent site history.",
                                "sources": ["source/x.pdf"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            resolved = resolve_project_folder(tmp, create_subdirs=True)
            result = run_adversarial_review(resolved)
            self.assertFalse(result.can_apply)
            self.assertTrue(any(f.code == "red_flag_prose" for f in result.blockers))
            from scripts.agent_folder_report import run_mode

            self.assertEqual(run_mode(tmp, "review"), 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_corrupt_narratives_blocker(self) -> None:
        from ai.adversarial_review import run_adversarial_review
        from project_folder import resolve_project_folder

        tmp = self._make_folder()
        try:
            drafts = tmp / "ai_drafts"
            drafts.mkdir(exist_ok=True)
            (drafts / "narratives.json").write_text("{not-json", encoding="utf-8")
            resolved = resolve_project_folder(tmp, create_subdirs=True)
            result = run_adversarial_review(resolved)
            self.assertTrue(any(f.code == "narratives_corrupt" for f in result.blockers))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_adversarial_review_prompt_in_library(self) -> None:
        from ai.prompts import agent_task_prompt, clear_prompt_library_cache, list_agent_task_ids

        clear_prompt_library_cache()
        self.assertIn("adversarial_review", list_agent_task_ids())
        text = agent_task_prompt("adversarial_review").lower()
        self.assertIn("adversarial", text)
        self.assertIn("cursor", text)


if __name__ == "__main__":
    unittest.main()
