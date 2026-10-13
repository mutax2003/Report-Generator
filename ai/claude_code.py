"""Claude subscription provider — the consultant's own signed-in Claude Code CLI.

Anthropic permits an end user's Claude Pro / Max / Team login to be used only through
Anthropic's unmodified Claude Code binary, with the user signing in themselves.
Third-party apps must not offer Claude.ai sign-in or collect, store or forward its
credentials. So this module never touches tokens: it runs ``claude -p`` on the
consultant's own PC (where they ran ``claude`` → ``/login``) and reads the text reply.

Opt-in only (``AI_PROVIDER=claude_code`` or the sidebar picker) and refused on hosted /
shared / container hosts and for remote browser sessions (see ``ai.config``), where one
login would end up serving every user.
"""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

PROVIDER_ID = "claude_code"
PROVIDER_LABEL = "Claude subscription (via Claude Code)"
DEFAULT_MODEL = "sonnet"
DEFAULT_TIMEOUT_SEC = 180
STATUS_TIMEOUT_SEC = 20
STATUS_CACHE_TTL_SEC = 60.0
STATUS_ERROR_TTL_SEC = 60.0
# After a timeout / usage-limit / sign-in error, skip calls so batch features
# (e.g. Analyze folder) fall back offline quickly instead of retrying each item.
FAILURE_COOLDOWN_SEC = 120.0

# Team / Enterprise seats fall under Anthropic's Commercial Terms. Every other plan
# (Free / Pro / Max, or an unknown value) needs the consultant's privacy acknowledgement.
COMMERCIAL_PLANS = frozenset({"team", "enterprise"})

# Child-env variables that would make Claude Code bill or authenticate with something
# other than the consultant's own claude.ai sign-in (API keys, injected OAuth tokens,
# gateways, Bedrock / Vertex / Foundry). The app never forwards credentials.
_STRIPPED_ENV = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_VERTEX",
        "CLAUDE_CODE_USE_FOUNDRY",
    }
)

PROMPT_FILE = "prompt.txt"
SYSTEM_PROMPT_FILE = "system_prompt.txt"

INSTALL_HINT = (
    "Install Claude Code (https://code.claude.com/docs/en/setup), run `claude` in a "
    "terminal and type `/login` with your Claude Max / Team account, then click "
    "**Re-check sign-in**."
)


@dataclass(frozen=True)
class ClaudeCodeStatus:
    cli_path: str = ""
    logged_in: bool = False
    auth_method: str = ""
    api_provider: str = ""
    subscription_type: str = ""
    error: str = ""

    @property
    def installed(self) -> bool:
        return bool(self.cli_path)

    @property
    def claude_account(self) -> bool:
        """Signed in with a claude.ai account against Anthropic directly (not a key / cloud)."""
        return (
            self.logged_in
            and self.auth_method == "claude.ai"
            and self.api_provider in ("", "firstParty")
        )

    @property
    def consumer_plan(self) -> bool:
        """Anything but Team / Enterprise — needs the privacy acknowledgement."""
        return self.subscription_type.lower() not in COMMERCIAL_PLANS

    @property
    def plan_label(self) -> str:
        if self.subscription_type:
            return f"Claude {self.subscription_type.title()}"
        return "Claude account"


_status_lock = threading.Lock()
_status_cache: dict[str, tuple[float, ClaudeCodeStatus]] = {}
_state_lock = threading.Lock()
_last_error = ""
_cooldown_until = 0.0


def _set_last_error(message: str, *, cooldown: bool = False) -> None:
    global _last_error, _cooldown_until
    with _state_lock:
        _last_error = message
        if cooldown:
            _cooldown_until = time.monotonic() + FAILURE_COOLDOWN_SEC
        elif not message:
            _cooldown_until = 0.0


def last_error() -> str:
    """Most recent Claude Code failure (shown in the AI options sidebar)."""
    with _state_lock:
        return _last_error


def _cooling_down() -> bool:
    with _state_lock:
        return time.monotonic() < _cooldown_until


def _forget_status() -> None:
    with _status_lock:
        _status_cache.clear()


def clear_status_cache() -> None:
    """Forget the sign-in probe, last error and cooldown (Re-check sign-in button, tests)."""
    _forget_status()
    _set_last_error("")


def find_cli(override: str = "") -> str:
    """Path to the ``claude`` executable, or '' when not installed."""
    if override:
        path = Path(override).expanduser()
        return str(path) if path.is_file() else ""
    return shutil.which("claude") or ""


def running_in_container() -> bool:
    return Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()


def _child_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.upper() not in _STRIPPED_ENV}
    # The consultant's personal CLAUDE.md / memory must not steer report drafting.
    env["CLAUDE_CODE_DISABLE_CLAUDE_MDS"] = "1"
    env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    return env


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill Claude Code and any helpers it spawned (they would hold our pipes open)."""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def _run(cmd: list[str], *, stdin_path: Path | None, timeout: float, cwd: str) -> subprocess.CompletedProcess:
    """Run with a hard deadline: on timeout the whole process tree is killed.

    stdin comes from a file, never a pipe write: on Windows / Python < 3.13 a large
    ``communicate(input=...)`` blocks in the caller before the timeout starts.
    """
    if not math.isfinite(timeout) or timeout <= 0:
        timeout = DEFAULT_TIMEOUT_SEC
    kwargs: dict[str, object] = {}
    if sys.platform == "win32":
        # No console window flashing up behind Streamlit on Windows.
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kwargs["start_new_session"] = True
    with open(stdin_path or os.devnull, "rb") as stdin:
        proc = subprocess.Popen(
            cmd,
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=_child_env(),
            **kwargs,
        )
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            try:
                proc.communicate(timeout=5)
            except (subprocess.TimeoutExpired, OSError, ValueError):
                pass
            raise
    return subprocess.CompletedProcess(
        cmd,
        proc.returncode,
        out.decode("utf-8", errors="replace"),
        err.decode("utf-8", errors="replace"),
    )


def _parse_status(cli: str, stdout: str) -> ClaudeCodeStatus:
    try:
        data = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return ClaudeCodeStatus(cli_path=cli, error="Could not read `claude auth status` output.")
    if not isinstance(data, dict):
        return ClaudeCodeStatus(cli_path=cli, error="Unexpected `claude auth status` output.")
    # Only plan fields are kept — never email / org identifiers.
    return ClaudeCodeStatus(
        cli_path=cli,
        logged_in=bool(data.get("loggedIn")),
        auth_method=str(data.get("authMethod") or ""),
        api_provider=str(data.get("apiProvider") or ""),
        subscription_type=str(data.get("subscriptionType") or ""),
    )


def auth_status(cli: str) -> ClaudeCodeStatus:
    """``claude auth status`` (cached briefly). Reads only the JSON summary — no tokens."""
    if not cli:
        return ClaudeCodeStatus(error="Claude Code CLI not found.")
    now = time.monotonic()
    with _status_lock:
        cached = _status_cache.get(cli)
        if cached:
            ttl = STATUS_CACHE_TTL_SEC if not cached[1].error else STATUS_ERROR_TTL_SEC
            if now - cached[0] < ttl:
                return cached[1]
    try:
        with tempfile.TemporaryDirectory(prefix="esa-claude-", ignore_cleanup_errors=True) as tmp:
            proc = _run([cli, "auth", "status"], stdin_path=None, timeout=STATUS_TIMEOUT_SEC, cwd=tmp)
        status = _parse_status(cli, proc.stdout)
    except subprocess.TimeoutExpired:
        status = ClaudeCodeStatus(cli_path=cli, error="`claude auth status` timed out.")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        status = ClaudeCodeStatus(cli_path=cli, error=f"Could not start Claude Code: {exc}")
    with _status_lock:
        _status_cache[cli] = (now, status)
    return status


def _command(cli: str, model: str) -> list[str]:
    cmd = [
        cli,
        "-p",
        "--output-format",
        "json",
        "--no-session-persistence",
        # Plain text completion: --safe-mode skips CLAUDE.md, skills, plugins, hooks and
        # MCP servers while keeping the user's own sign-in; --tools "" removes every tool.
        "--safe-mode",
        "--tools",
        "",
        # Relative to the temp cwd, so no user-profile path reaches a .cmd shim's cmd.exe.
        "--system-prompt-file",
        SYSTEM_PROMPT_FILE,
    ]
    if model:
        cmd += ["--model", model]
    return cmd


def run_prompt(
    *,
    cli: str,
    system: str,
    user: str,
    model: str = DEFAULT_MODEL,
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> str | None:
    """One headless Claude Code turn; returns the reply text or None (offline fallback)."""
    if not cli:
        _set_last_error("Claude Code CLI not found.")
        return None
    if _cooling_down():
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="esa-claude-", ignore_cleanup_errors=True) as tmp:
            (Path(tmp) / SYSTEM_PROMPT_FILE).write_text(system, encoding="utf-8")
            prompt_path = Path(tmp) / PROMPT_FILE
            prompt_path.write_text(user, encoding="utf-8")
            proc = _run(_command(cli, model), stdin_path=prompt_path, timeout=timeout, cwd=tmp)
    except subprocess.TimeoutExpired:
        _set_last_error(f"Claude Code did not answer within {int(timeout)} s.", cooldown=True)
        logger.warning("Claude Code call timed out after %ss", timeout)
        return None
    except Exception as exc:  # never let a CLI problem break the UI — fall back offline
        _set_last_error(f"Could not run Claude Code: {exc}")
        logger.warning("Claude Code could not run: %s", exc)
        return None

    try:
        data = json.loads(proc.stdout or "")
    except json.JSONDecodeError:
        detail = ((proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or [""])[0][:300]
        if "unknown option" in detail:
            detail += " — update Claude Code (`claude update`)"
        _set_last_error(f"Claude Code exited with code {proc.returncode}: {detail}")
        logger.warning("Claude Code returned non-JSON output (exit %s)", proc.returncode)
        return None

    result = data.get("result") if isinstance(data, dict) else None
    if not isinstance(data, dict) or data.get("is_error") or not isinstance(result, str):
        message = str(result or (data.get("subtype") if isinstance(data, dict) else "") or "error")
        _set_last_error(f"Claude Code: {message[:300]}", cooldown=True)
        logger.warning("Claude Code reported an error: %s", message[:300])
        if "login" in message.lower() or "oauth" in message.lower():
            _forget_status()
        return None
    _set_last_error("")
    return result.strip()
