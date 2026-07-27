"""Unit tests for scripts/agent_folder_report.py orchestrator."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PHASE2_FOLDER = ROOT / "user_test" / "phase2_alberta"


class AgentFolderReportCliTests(unittest.TestCase):
    def test_build_parser_requires_folder_and_mode(self) -> None:
        from scripts.agent_folder_report import build_parser

        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args([])

    def test_missing_folder_returns_one(self) -> None:
        from scripts import agent_folder_report as afr

        code = afr.main(
            ["--folder", str(ROOT / "__no_such_folder__"), "--mode", "inventory"]
        )
        self.assertEqual(code, 1)

    def test_unknown_mode_via_run_mode(self) -> None:
        from scripts.agent_folder_report import run_mode

        with tempfile.TemporaryDirectory() as tmp:
            # resolve will fail before mode check if folder invalid
            code = run_mode(Path(tmp), "inventory")
            self.assertEqual(code, 1)

    def test_inventory_on_phase2_sample_folder(self) -> None:
        from scripts.agent_folder_report import run_mode

        if not (PHASE2_FOLDER / "project_data.xlsx").is_file():
            self.skipTest("user_test/phase2_alberta not prepared")
        code = run_mode(PHASE2_FOLDER, "inventory", use_llm=False)
        self.assertEqual(code, 0)
        self.assertTrue((PHASE2_FOLDER / "ai_drafts").is_dir())

    def test_llm_flag_parsing(self) -> None:
        from scripts.agent_folder_report import build_parser

        parser = build_parser()
        args = parser.parse_args(
            ["--folder", "C:\\x", "--mode", "enrich", "--llm"]
        )
        self.assertTrue(args.llm)
        args2 = parser.parse_args(
            ["--folder", "C:\\x", "--mode", "enrich", "--llm", "--no-llm"]
        )
        self.assertTrue(args2.no_llm)

    def test_apply_drafts_noop_without_files(self) -> None:
        from scripts.agent_folder_report import apply_drafts_to_excel

        fake = mock.Mock()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            excel = root / "project_data.xlsx"
            # minimal xlsx via pandas
            import pandas as pd

            pd.DataFrame([{"site_name": "A"}]).to_excel(
                excel, sheet_name="ProjectData", index=False
            )
            drafts = root / "ai_drafts"
            drafts.mkdir()
            fake.excel_path = excel
            fake.ai_drafts_dir = drafts
            applied, skipped = apply_drafts_to_excel(fake)
            self.assertEqual(applied, [])
            self.assertEqual(skipped, [])

    def test_hosted_mode_blocks(self) -> None:
        import os

        from scripts.agent_folder_report import run_mode

        os.environ["ESA_HOSTED_MODE"] = "1"
        try:
            code = run_mode(PHASE2_FOLDER, "inventory")
            self.assertEqual(code, 2)
        finally:
            os.environ.pop("ESA_HOSTED_MODE", None)

    def test_apply_rejects_corrupt_narratives(self) -> None:
        from scripts.agent_folder_report import apply_drafts_to_excel

        fake = mock.Mock()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            excel = root / "project_data.xlsx"
            import pandas as pd

            pd.DataFrame([{"site_name": "A"}]).to_excel(
                excel, sheet_name="ProjectData", index=False
            )
            drafts = root / "ai_drafts"
            drafts.mkdir()
            (drafts / "narratives.json").write_text("{bad", encoding="utf-8")
            fake.excel_path = excel
            fake.ai_drafts_dir = drafts
            with self.assertRaises(ValueError):
                apply_drafts_to_excel(fake)

    def test_normalize_folder_rejects_file(self) -> None:
        from scripts.agent_folder_report import _normalize_folder

        with tempfile.NamedTemporaryFile(delete=False) as fh:
            path = Path(fh.name)
        try:
            with self.assertRaises(ValueError):
                _normalize_folder(path)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
