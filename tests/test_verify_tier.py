"""Unit tests for scripts/verify_tier.py and pre-commit UX gate."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_script_module(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


verify_tier = _load_script_module("verify_tier")
pre_commit_check = _load_script_module("pre_commit_check")


class VerifyTierTests(unittest.TestCase):
    def test_quick_tier_returns_zero(self) -> None:
        self.assertEqual(verify_tier.run_tier("quick"), 0)

    def test_playbook_e2e_keys(self) -> None:
        self.assertEqual(set(verify_tier.PLAYBOOK_E2E), {"a", "b", "c", "d", "e"})

    def test_release_steps_non_empty(self) -> None:
        self.assertGreater(len(verify_tier.RELEASE_STEPS), 10)

    @mock.patch.object(verify_tier, "_run_script", return_value=0)
    @mock.patch.object(verify_tier, "_run_step", return_value=0)
    def test_tier_unit_calls_count_and_unittest(
        self, mock_step: mock.Mock, mock_script: mock.Mock
    ) -> None:
        self.assertEqual(verify_tier.run_tier("unit"), 0)
        mock_script.assert_called_once_with("scripts/count_tests.py")
        mock_step.assert_called_once()

    @mock.patch.object(verify_tier, "_run_script", return_value=1)
    def test_tier_unit_stops_on_count_tests_failure(self, mock_script: mock.Mock) -> None:
        self.assertEqual(verify_tier.run_tier("unit"), 1)
        mock_script.assert_called_once_with("scripts/count_tests.py")

    @mock.patch.object(verify_tier, "_run_script")
    @mock.patch.object(verify_tier, "_run_step", return_value=0)
    def test_tier_ux_runs_streamlit_smoke(
        self, _mock_step: mock.Mock, mock_script: mock.Mock
    ) -> None:
        mock_script.return_value = 0
        self.assertEqual(verify_tier.run_tier("ux"), 0)
        mock_script.assert_any_call("scripts/streamlit_smoke.py")

    @mock.patch.object(verify_tier, "_tier_ux", return_value=0)
    @mock.patch.object(verify_tier, "_run_script", return_value=0)
    def test_tier_profile_playbook_b(
        self, mock_script: mock.Mock, _mock_ux: mock.Mock
    ) -> None:
        self.assertEqual(verify_tier.run_tier("profile", "b"), 0)
        mock_script.assert_any_call("scripts/phase1_alberta_e2e.py")
        mock_script.assert_any_call("scripts/health_check.py")

    @mock.patch.object(verify_tier, "_tier_ux", return_value=0)
    @mock.patch.object(verify_tier, "_run_script", return_value=0)
    def test_tier_profile_playbook_a_skips_e2e(
        self, mock_script: mock.Mock, _mock_ux: mock.Mock
    ) -> None:
        self.assertEqual(verify_tier.run_tier("profile", "a"), 0)
        for call in mock_script.call_args_list:
            self.assertNotIn("e2e", str(call))


class PreCommitCheckTests(unittest.TestCase):
    def test_needs_ux_tier_for_ui_path(self) -> None:
        self.assertTrue(pre_commit_check._needs_ux_tier(["ui/onboarding.py"]))

    def test_needs_ux_tier_for_app_py(self) -> None:
        self.assertTrue(pre_commit_check._needs_ux_tier(["app.py"]))

    def test_skips_docs_only(self) -> None:
        self.assertFalse(pre_commit_check._needs_ux_tier(["docs/02-user-guide.md"]))

    @mock.patch.object(pre_commit_check, "subprocess")
    def test_main_skips_when_no_ui_staged(self, mock_subprocess: mock.Mock) -> None:
        mock_subprocess.run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="docs/foo.md\n", stderr=""
        )
        self.assertEqual(pre_commit_check.main(), 0)
        mock_subprocess.call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
