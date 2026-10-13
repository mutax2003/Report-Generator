"""Claude subscription provider (local Claude Code CLI) — opt-in, hosted-blocked, no tokens."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from ai import claude_code
from ai.claude_code import ClaudeCodeStatus
from ai.config import ai_status_message, resolve_llm_settings

CLI = "/opt/claude/bin/claude"


def _status(**kw) -> ClaudeCodeStatus:
    base = dict(
        cli_path=CLI,
        logged_in=True,
        auth_method="claude.ai",
        api_provider="firstParty",
        subscription_type="team",
    )
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
            patch("ai.config._session_state", return_value=None),
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
        self.assertIn("privacy note", settings.unavailable_reason)
        os.environ["ESA_CLAUDE_CONSUMER_ACK"] = "1"
        settings = resolve_llm_settings()
        self.assertTrue(settings.available)
        self.assertTrue(settings.consumer_plan)
        self.assertEqual(settings.account, "Claude Max")

    def test_unknown_plan_requires_ack(self) -> None:
        os.environ["AI_PROVIDER"] = "claude_code"
        self.auth_mock.return_value = _status(subscription_type="")
        settings = resolve_llm_settings()
        self.assertFalse(settings.available)
        self.assertTrue(settings.consumer_plan)

    def test_api_key_or_cloud_sign_in_refused(self) -> None:
        os.environ["AI_PROVIDER"] = "claude_code"
        for status in (
            _status(auth_method="api_key", subscription_type=""),
            _status(api_provider="bedrock"),
        ):
            self.auth_mock.return_value = status
            settings = resolve_llm_settings()
            self.assertFalse(settings.available)
            self.assertIn("not a Claude account", settings.unavailable_reason)

    def test_shared_host_flags_block_without_running_cli(self) -> None:
        for env in (
            {"ESA_HOSTED_MODE": "1"},
            {"ESA_DISABLE_FOLDER_WORKFLOW": "true"},
            {"ESA_BIND_ALL": "1"},
            {"ESA_API_KEY": "server-key"},
        ):
            with self.subTest(env=env), patch.dict(os.environ, {"AI_PROVIDER": "claude_code", **env}):
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

    def test_remote_browser_session_blocks(self) -> None:
        state = {"ai_provider_selected": "claude_code", "claude_code_ack_selected": True}
        with patch("ai.config._session_state", return_value=state), patch(
            "ai.config.remote_browser_session", return_value=True
        ):
            settings = resolve_llm_settings()
        self.assertEqual(settings.provider, "claude_code")
        self.assertFalse(settings.available)
        self.auth_mock.assert_not_called()

    def test_remote_browser_session_detection(self) -> None:
        from types import SimpleNamespace

        import streamlit as st

        from ai.config import remote_browser_session

        cases = {
            None: False,
            "127.0.0.1": False,
            "::1": False,
            "::ffff:127.0.0.1": False,
            "192.168.1.20": True,
            "fe80::1%eth0": True,
            "not-an-ip": True,
        }
        with patch("ai.config._session_state", return_value={}):
            for ip, remote in cases.items():
                with self.subTest(ip=ip), patch.object(st, "context", SimpleNamespace(ip_address=ip)):
                    self.assertEqual(remote_browser_session(), remote)
        # Outside a Streamlit run (CLI scripts) there is no browser viewer.
        self.assertFalse(remote_browser_session())

    def test_hosted_session_choice_still_blocked(self) -> None:
        os.environ["ESA_HOSTED_MODE"] = "1"
        with patch("ai.config._session_state", return_value={"ai_provider_selected": "claude_code"}):
            self.assertFalse(resolve_llm_settings().available)
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
        state = {"ai_provider_selected": "claude_code", "claude_code_ack_selected": True}
        with patch("ai.config._session_state", return_value=state):
            self.assertTrue(resolve_llm_settings().available)
        with patch("ai.config._session_state", return_value={"ai_provider_selected": "auto"}):
            self.assertEqual(resolve_llm_settings().provider, "offline")

    def test_model_and_timeout_overrides(self) -> None:
        os.environ.update(
            AI_PROVIDER="claude_code", CLAUDE_CODE_MODEL="opus", ESA_CLAUDE_CODE_TIMEOUT_SEC="5000"
        )
        settings = resolve_llm_settings()
        self.assertEqual(settings.model, "opus")
        self.assertEqual(settings.timeout_sec, 900.0)
        for bad in ("nan", "inf", "soon"):
            os.environ["ESA_CLAUDE_CODE_TIMEOUT_SEC"] = bad
            self.assertEqual(resolve_llm_settings().timeout_sec, claude_code.DEFAULT_TIMEOUT_SEC)


class ClaudeCodeStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        claude_code.clear_status_cache()
        self.addCleanup(claude_code.clear_status_cache)

    def test_parse_status_keeps_only_plan_fields(self) -> None:
        out = json.dumps(
            {
                "loggedIn": True,
                "authMethod": "claude.ai",
                "apiProvider": "firstParty",
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
        self.assertTrue(status.claude_account)
        self.assertTrue(status.consumer_plan)
        self.assertNotIn("someone@example.com", repr(status))

    def test_commercial_plans(self) -> None:
        for plan, consumer in (("team", False), ("Enterprise", False), ("pro", True), ("", True)):
            self.assertEqual(_status(subscription_type=plan).consumer_plan, consumer, plan)

    def test_status_timeout_reports_error(self) -> None:
        with patch("ai.claude_code._run", side_effect=subprocess.TimeoutExpired(CLI, 1)):
            status = claude_code.auth_status(CLI)
        self.assertFalse(status.logged_in)
        self.assertIn("timed out", status.error)

    def test_find_cli_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "claude.exe"
            exe.write_bytes(b"")
            self.assertEqual(claude_code.find_cli(str(exe)), str(exe))
            # A bad override never falls back to PATH.
            self.assertEqual(claude_code.find_cli(str(Path(tmp) / "missing.exe")), "")


class ClaudeCodeRunTests(unittest.TestCase):
    def setUp(self) -> None:
        claude_code.clear_status_cache()
        self.addCleanup(claude_code.clear_status_cache)

    def test_command_is_tool_free_and_sessionless(self) -> None:
        cmd = claude_code._command(CLI, "sonnet")
        self.assertEqual(cmd[:2], [CLI, "-p"])
        for flag in ("--safe-mode", "--no-session-persistence"):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")
        # Relative path only — no profile directory in argv.
        self.assertEqual(cmd[cmd.index("--system-prompt-file") + 1], "system_prompt.txt")
        self.assertEqual(cmd[cmd.index("--model") + 1], "sonnet")
        self.assertNotIn("--bare", cmd)

    def test_child_env_drops_credentials_and_personal_memory(self) -> None:
        injected = {
            "ANTHROPIC_API_KEY": "sk",
            "ANTHROPIC_AUTH_TOKEN": "t",
            "ANTHROPIC_BASE_URL": "https://proxy",
            "CLAUDE_CODE_OAUTH_TOKEN": "oat",
            "CLAUDE_CODE_USE_BEDROCK": "1",
            # Host Claude Code session (app started from inside Claude Code)
            "CLAUDECODE": "1",
            "CLAUDE_CODE_SESSION_ID": "sess",
            "CLAUDE_CODE_MESSAGING_TOKEN": "msg",
            "CLAUDE_CODE_SDK_HAS_HOST_AUTH_REFRESH": "1",
            "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "0",
            "PATH": "x",
            "CLAUDE_CODE_GIT_BASH_PATH": "C:/Git/bin/bash.exe",
        }
        kept = {"PATH", "CLAUDE_CODE_GIT_BASH_PATH", "CLAUDE_CODE_DISABLE_CLAUDE_MDS"}
        with patch.dict(os.environ, injected):
            env = claude_code._child_env()
        for key in injected:
            if key not in kept:
                self.assertNotIn(key, env)
        self.assertEqual(env["PATH"], "x")
        self.assertEqual(env["CLAUDE_CODE_GIT_BASH_PATH"], "C:/Git/bin/bash.exe")
        self.assertEqual(env["CLAUDE_CODE_DISABLE_CLAUDE_MDS"], "1")
        self.assertEqual(env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"], "1")

    def test_success_returns_result_text_and_prompt_goes_via_file(self) -> None:
        out = json.dumps({"type": "result", "is_error": False, "result": '  {"a": 1}\n'})
        seen: dict[str, str] = {}

        def fake_run(cmd, *, stdin_path, timeout, cwd):
            seen["stdin"] = Path(stdin_path).read_text(encoding="utf-8")
            seen["system"] = (Path(cwd) / "system_prompt.txt").read_text(encoding="utf-8")
            return _completed(out)

        with patch("ai.claude_code._run", side_effect=fake_run):
            text = claude_code.run_prompt(cli=CLI, system="SYS", user="USER")
        self.assertEqual(text, '{"a": 1}')
        self.assertEqual(seen, {"stdin": "USER", "system": "SYS"})
        self.assertEqual(claude_code.last_error(), "")

    def test_error_result_returns_none_and_cools_down(self) -> None:
        out = json.dumps({"is_error": True, "result": "Usage limit reached"})
        with patch("ai.claude_code._run", return_value=_completed(out)) as run:
            self.assertIsNone(claude_code.run_prompt(cli=CLI, system="s", user="u"))
            self.assertIsNone(claude_code.run_prompt(cli=CLI, system="s", user="u"))
        self.assertEqual(run.call_count, 1, "second call should be skipped during cooldown")
        self.assertIn("Usage limit", claude_code.last_error())
        claude_code.clear_status_cache()  # Re-check sign-in ends the cooldown
        with patch("ai.claude_code._run", return_value=_completed(json.dumps({"result": "ok"}))):
            self.assertEqual(claude_code.run_prompt(cli=CLI, system="s", user="u"), "ok")

    def test_old_cli_gets_update_hint(self) -> None:
        proc = _completed("", returncode=1, stderr="error: unknown option '--safe-mode'")
        with patch("ai.claude_code._run", return_value=proc) as run:
            self.assertIsNone(claude_code.run_prompt(cli=CLI, system="s", user="u"))
            self.assertIsNone(claude_code.run_prompt(cli=CLI, system="s", user="u"))
        self.assertEqual(run.call_count, 1, "a broken CLI should not be respawned during cooldown")
        self.assertIn("claude update", claude_code.last_error())

    def test_timeout_returns_none(self) -> None:
        with patch("ai.claude_code._run", side_effect=subprocess.TimeoutExpired(CLI, 3)):
            self.assertIsNone(claude_code.run_prompt(cli=CLI, system="s", user="u", timeout=3))
        self.assertIn("within 3 s", claude_code.last_error())

    def test_unexpected_exception_falls_back(self) -> None:
        with patch("ai.claude_code._run", side_effect=ValueError("bad")) as run:
            self.assertIsNone(claude_code.run_prompt(cli=CLI, system="s", user="u"))
            self.assertIsNone(claude_code.run_prompt(cli=CLI, system="s", user="u"))
        self.assertEqual(run.call_count, 1)
        self.assertIn("bad", claude_code.last_error())

    def test_missing_cli_returns_none(self) -> None:
        self.assertIsNone(claude_code.run_prompt(cli="", system="s", user="u"))

    def test_run_hard_timeout_kills_real_process(self) -> None:
        """Real subprocess: a hung child is killed close to the deadline, large stdin included."""
        with tempfile.TemporaryDirectory() as tmp:
            stdin_path = Path(tmp) / "prompt.txt"
            stdin_path.write_text("x" * 500_000, encoding="utf-8")
            start = time.monotonic()
            with self.assertRaises(subprocess.TimeoutExpired):
                claude_code._run(
                    [sys.executable, "-c", "import time; time.sleep(60)"],
                    stdin_path=stdin_path,
                    timeout=1,
                    cwd=tmp,
                )
            self.assertLess(time.monotonic() - start, 20)

    def test_run_reads_stdin_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stdin_path = Path(tmp) / "prompt.txt"
            stdin_path.write_text("héllo", encoding="utf-8")
            proc = claude_code._run(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())",
                ],
                stdin_path=stdin_path,
                timeout=30,
                cwd=tmp,
            )
        self.assertEqual(proc.stdout, "héllo")

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
