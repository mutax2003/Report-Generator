"""Claude subscription provider (local Claude Code CLI) — opt-in, hosted-blocked, no tokens."""

from __future__ import annotations

import json
import os
import subprocess
import unittest
from unittest.mock import patch

from ai import claude_code
from ai.claude_code import ClaudeCodeStatus
from ai.config import ai_status_message, resolve_llm_settings

CLI = "/opt/claude/bin/claude"


def _status(**kw) -> ClaudeCodeStatus:
    base = dict(cli_path=CLI, logged_in=True, auth_method="claude.ai", subscription_type="team")
    base.update(kw)
    return ClaudeCodeStatus(**base)


def _completed(stdout: str, *, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([CLI], returncode, stdout, stderr)


class ClaudeCodeSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        patches = [
            patch.dict(os.environ, {}, clear=True),
            patch("ai.config._secret", side_effect=lambda name: os.environ.get(name, "").strip()),
            patch("ai.config.ollama_reachable", return_value=False),
            patch("ai.claude_code.running_in_container", return_value=False),
            patch("ai.claude_code.find_cli", return_value=CLI),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.auth = patch("ai.claude_code.auth_status", return_value=_status())
        self.auth_mock = self.auth.start()
        self.addCleanup(self.auth.stop)
        claude_code.clear_status_cache()

    def test_never_auto_selected(self) -> None:
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-x"
        settings = resolve_llm_settings()
        self.assertNotEqual(settings.provider, claude_code.PROVIDER_ID)
        self.auth_mock.assert_not_called()

    def test_team_seat_ready_without_ack(self) -> None:
        os.environ["AI_PROVIDER"] = "claude_code"
        settings = resolve_llm_settings()
        self.assertTrue(settings.available)
        self.assertEqual(settings.provider, "claude_code")
        self.assertEqual(settings.cli_path, CLI)
        self.assertEqual(settings.api_key, "")
        self.assertEqual(settings.account, "Claude Team")
        self.assertFalse(settings.consumer_plan)
        self.assertEqual(settings.model, claude_code.DEFAULT_MODEL)
        self.assertIn("LLM ready", ai_status_message(settings))

    def test_max_plan_requires_privacy_ack(self) -> None:
        os.environ["AI_PROVIDER"] = "claude_code"
        self.auth_mock.return_value = _status(subscription_type="max")
        settings = resolve_llm_settings()
        self.assertFalse(settings.available)
        self.assertTrue(settings.consumer_plan)
        self.assertIn("consumer plan", settings.unavailable_reason)
        os.environ["ESA_CLAUDE_CONSUMER_ACK"] = "1"
        settings = resolve_llm_settings()
        self.assertTrue(settings.available)
        self.assertTrue(settings.consumer_plan)
        self.assertEqual(settings.account, "Claude Max")

    def test_hosted_mode_blocks_without_running_cli(self) -> None:
        os.environ["AI_PROVIDER"] = "claude_code"
        os.environ["ESA_HOSTED_MODE"] = "1"
        settings = resolve_llm_settings()
        self.assertFalse(settings.available)
        self.assertIn("own PC", settings.unavailable_reason)
        self.auth_mock.assert_not_called()

    def test_container_blocks(self) -> None:
        os.environ["AI_PROVIDER"] = "claude_code"
        with patch("ai.claude_code.running_in_container", return_value=True):
            settings = resolve_llm_settings()
        self.assertFalse(settings.available)
        self.auth_mock.assert_not_called()

    def test_not_installed(self) -> None:
        os.environ["AI_PROVIDER"] = "claude_code"
        with patch("ai.claude_code.find_cli", return_value=""):
            settings = resolve_llm_settings()
        self.assertFalse(settings.available)
        self.assertIn("not installed", settings.unavailable_reason)
        self.assertIn("not ready", ai_status_message(settings))

    def test_not_signed_in(self) -> None:
        os.environ["AI_PROVIDER"] = "claude_code"
        self.auth_mock.return_value = _status(logged_in=False, subscription_type="")
        settings = resolve_llm_settings()
        self.assertFalse(settings.available)
        self.assertIn("/login", settings.unavailable_reason)

    def test_sidebar_choice_and_ack_from_session_state(self) -> None:
        self.auth_mock.return_value = _status(subscription_type="max")
        state = {"ai_provider_choice": "claude_code", "claude_code_consumer_ack": True}
        with patch("ai.config._session_state", return_value=state):
            self.assertTrue(resolve_llm_settings().available)
        with patch("ai.config._session_state", return_value={"ai_provider_choice": "auto"}):
            self.assertEqual(resolve_llm_settings().provider, "offline")

    def test_model_and_timeout_overrides(self) -> None:
        os.environ.update(
            AI_PROVIDER="claude_code", CLAUDE_CODE_MODEL="opus", ESA_CLAUDE_CODE_TIMEOUT_SEC="5000"
        )
        settings = resolve_llm_settings()
        self.assertEqual(settings.model, "opus")
        self.assertEqual(settings.timeout_sec, 900.0)


class ClaudeCodeStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        claude_code.clear_status_cache()
        self.addCleanup(claude_code.clear_status_cache)

    def test_parse_status_keeps_only_plan_fields(self) -> None:
        out = json.dumps(
            {
                "loggedIn": True,
                "authMethod": "claude.ai",
                "subscriptionType": "max",
                "email": "someone@example.com",
                "orgId": "abc",
            }
        )
        with patch("ai.claude_code._run", return_value=_completed(out)) as run:
            status = claude_code.auth_status(CLI)
            claude_code.auth_status(CLI)  # cached
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0], [CLI, "auth", "status"])
        self.assertTrue(status.logged_in)
        self.assertTrue(status.consumer_plan)
        self.assertNotIn("someone@example.com", repr(status))

    def test_api_key_auth_is_not_consumer(self) -> None:
        status = ClaudeCodeStatus(cli_path=CLI, logged_in=True, auth_method="api_key")
        self.assertFalse(status.consumer_plan)
        self.assertEqual(status.plan_label, "Claude Code (api_key)")

    def test_status_timeout_reports_error(self) -> None:
        with patch("ai.claude_code._run", side_effect=subprocess.TimeoutExpired(CLI, 1)):
            status = claude_code.auth_status(CLI)
        self.assertFalse(status.logged_in)
        self.assertIn("timed out", status.error)


class ClaudeCodeRunTests(unittest.TestCase):
    def setUp(self) -> None:
        claude_code.clear_status_cache()
        self.addCleanup(claude_code.clear_status_cache)

    def test_command_is_tool_free_and_sessionless(self) -> None:
        cmd = claude_code._command(CLI, "sys.txt", "sonnet")
        self.assertEqual(cmd[:2], [CLI, "-p"])
        for flag in ("--safe-mode", "--no-session-persistence", "--system-prompt-file"):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")
        self.assertEqual(cmd[cmd.index("--model") + 1], "sonnet")
        self.assertNotIn("--bare", cmd)

    def test_child_env_drops_api_keys_and_personal_memory(self) -> None:
        with patch.dict(
            os.environ, {"ANTHROPIC_API_KEY": "sk", "ANTHROPIC_AUTH_TOKEN": "t", "PATH": "x"}
        ):
            env = claude_code._child_env()
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", env)
        self.assertEqual(env["PATH"], "x")
        self.assertEqual(env["CLAUDE_CODE_DISABLE_CLAUDE_MDS"], "1")

    def test_success_returns_result_text(self) -> None:
        out = json.dumps({"type": "result", "is_error": False, "result": '  {"a": 1}\n'})
        with patch("ai.claude_code._run", return_value=_completed(out)) as run:
            text = claude_code.run_prompt(cli=CLI, system="SYS", user="USER")
        self.assertEqual(text, '{"a": 1}')
        self.assertEqual(run.call_args.kwargs["input_text"], "USER")
        self.assertEqual(claude_code.last_error(), "")

    def test_error_result_returns_none(self) -> None:
        out = json.dumps({"is_error": True, "result": "Usage limit reached"})
        with patch("ai.claude_code._run", return_value=_completed(out)):
            self.assertIsNone(claude_code.run_prompt(cli=CLI, system="s", user="u"))
        self.assertIn("Usage limit", claude_code.last_error())

    def test_old_cli_gets_update_hint(self) -> None:
        proc = _completed("", returncode=1, stderr="error: unknown option '--safe-mode'")
        with patch("ai.claude_code._run", return_value=proc):
            self.assertIsNone(claude_code.run_prompt(cli=CLI, system="s", user="u"))
        self.assertIn("claude update", claude_code.last_error())

    def test_timeout_returns_none(self) -> None:
        with patch("ai.claude_code._run", side_effect=subprocess.TimeoutExpired(CLI, 3)):
            self.assertIsNone(claude_code.run_prompt(cli=CLI, system="s", user="u", timeout=3))
        self.assertIn("within 3 s", claude_code.last_error())

    def test_missing_cli_returns_none(self) -> None:
        self.assertIsNone(claude_code.run_prompt(cli="", system="s", user="u"))

    def test_chat_completion_routes_through_cli_with_json_suffix(self) -> None:
        from ai.client import complete_json
        from ai.config import LlmSettings

        settings = LlmSettings(
            provider="claude_code",
            label=claude_code.PROVIDER_LABEL,
            api_key="",
            base_url="",
            model="sonnet",
            supports_json_mode=False,
            cli_path=CLI,
            timeout_sec=42.0,
        )
        with patch("ai.client.resolve_llm_settings", return_value=settings), patch(
            "ai.claude_code.run_prompt", return_value='{"site_name": "X"}'
        ) as run, patch("ai.client._create_client") as openai_client:
            self.assertEqual(complete_json("SYS", "USER"), {"site_name": "X"})
        openai_client.assert_not_called()
        kwargs = run.call_args.kwargs
        self.assertTrue(kwargs["system"].startswith("SYS"))
        self.assertIn("JSON", kwargs["system"])
        self.assertEqual((kwargs["cli"], kwargs["model"], kwargs["timeout"]), (CLI, "sonnet", 42.0))


if __name__ == "__main__":
    unittest.main()
