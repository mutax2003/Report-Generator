"""
AI configuration — keys via environment or Streamlit secrets only (never commit keys).

Default preference (when AI_PROVIDER is unset): local Ollama if reachable, then free-tier
cloud keys (Gemini → Groq → Together), then paid OpenAI. Anthropic is never auto-selected
from a bare ANTHROPIC_API_KEY (the key is often present in the environment for other
tools) — set AI_PROVIDER=anthropic to opt in. The Claude subscription provider
(AI_PROVIDER=claude_code, or the sidebar picker) is likewise opt-in only and runs the
consultant's own signed-in Claude Code CLI — see ai/claude_code.py. LLM stays in the AI side-car
(ai/* + UI Apply) — never inside ReportEngine merge.
"""

from __future__ import annotations

import ipaddress
import math
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse

from ai import claude_code

AI_PROMPT_VERSION = "1.0.0"
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_AI_INPUT_CHARS = 48_000
MAX_AI_OUTPUT_TOKENS = 4096
DEFAULT_MODEL = "gpt-4o-mini"
ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-5-5"
OLLAMA_DEFAULT_BASE = "http://localhost:11434/v1"
OLLAMA_PROBE_URL = "http://localhost:11434/api/tags"
OLLAMA_PROBE_TIMEOUT_S = 0.4

_SECRET_KEYS = (
    "AI_PROVIDER",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    "AZURE_OPENAI_ENDPOINT",
    "GEMINI_API_KEY",
    "TOGETHER_API_KEY",
    "GROQ_API_KEY",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "CLAUDE_CODE_MODEL",
    "CLAUDE_CLI_PATH",
    "ESA_CLAUDE_CONSUMER_ACK",
    "ESA_CLAUDE_CODE_TIMEOUT_SEC",
    "ESA_HOSTED_MODE",
    "ESA_DISABLE_FOLDER_WORKFLOW",
    "ESA_BIND_ALL",
)

# Sidebar picker values; "auto" = secrets/env. The UI mirrors its widgets into these
# non-widget keys so the choice survives runs where the sidebar is not rendered.
PROVIDER_CHOICE_AUTO = "auto"
SESSION_PROVIDER_KEY = "ai_provider_selected"
SESSION_CONSUMER_ACK_KEY = "claude_code_ack_selected"
_TRUTHY = ("1", "true", "yes")
# Shared-host flags fail safe: anything but an explicit "off" value blocks claude_code.
_FALSY = ("", "0", "false", "no", "off")
_SHARED_HOST_FLAGS = ("ESA_HOSTED_MODE", "ESA_DISABLE_FOLDER_WORKFLOW", "ESA_BIND_ALL")
_LOCAL_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1"})
_PROXY_HEADERS = ("x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "forwarded", "x-real-ip")

# AI_PROVIDER=ollama|groq|gemini|together|anthropic|claude_code|openai|azure|offline
PROVIDER_PRESETS: dict[str, dict[str, str | bool]] = {
    "ollama": {
        "label": "Ollama (local, free)",
        "base_url": OLLAMA_DEFAULT_BASE,
        "model": "qwen2.5:7b",
        "placeholder_key": "ollama",
        "supports_json_mode": False,
        "free": True,
    },
    "groq": {
        "label": "Groq (free tier)",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.1-8b-instant",
        "supports_json_mode": True,
        "free": True,
    },
    "gemini": {
        "label": "Google Gemini (free tier)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.0-flash",
        "supports_json_mode": False,
        "free": True,
    },
    "together": {
        "label": "Together AI (free credits)",
        "base_url": "https://api.together.xyz/v1",
        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "supports_json_mode": False,
        "free": True,
    },
    "anthropic": {
        "label": "Anthropic Claude (API)",
        "base_url": "https://api.anthropic.com/v1",
        "model": ANTHROPIC_DEFAULT_MODEL,
        # Anthropic's OpenAI-compatible endpoint ignores response_format.
        "supports_json_mode": False,
        "free": False,
    },
    claude_code.PROVIDER_ID: {
        "label": claude_code.PROVIDER_LABEL,
        "base_url": "",
        "model": claude_code.DEFAULT_MODEL,
        "supports_json_mode": False,
        "free": False,
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "",
        "model": DEFAULT_MODEL,
        "supports_json_mode": True,
        "free": False,
    },
    "azure": {
        "label": "Azure OpenAI",
        "base_url": "",
        "model": DEFAULT_MODEL,
        "supports_json_mode": True,
        "free": False,
    },
}

PROVIDER_KEY_ENV: dict[str, str] = {
    "gemini": "GEMINI_API_KEY",
    "together": "TOGETHER_API_KEY",
    "groq": "GROQ_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

# Prefer free providers when AI_PROVIDER is unset (after Ollama auto-detect).
_FREE_CLOUD_INFER_ORDER = ("gemini", "groq", "together")


@dataclass(frozen=True)
class LlmSettings:
    provider: str
    label: str
    api_key: str
    base_url: str
    model: str
    supports_json_mode: bool
    free: bool = False
    # Why an explicitly chosen provider cannot run (shown in the sidebar instead of a key hint).
    unavailable_reason: str = ""
    # Plan shown for the Claude subscription provider, e.g. "Claude Max".
    account: str = ""
    # Claude Free / Pro / Max (Consumer Terms) — sidebar shows the privacy acknowledgement.
    consumer_plan: bool = False
    cli_path: str = ""
    timeout_sec: float = 0.0

    @property
    def available(self) -> bool:
        if self.provider == "offline" or self.unavailable_reason:
            return False
        if self.provider == claude_code.PROVIDER_ID:
            return bool(self.cli_path)
        return bool(self.api_key)


def _secret(name: str) -> str:
    try:
        import streamlit as st

        if hasattr(st, "secrets") and name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:
        pass
    return os.environ.get(name, "").strip()


def _session_state():
    """Streamlit session_state during a script run, else None (CLI, tests, threads)."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        if get_script_run_ctx(suppress_warning=True) is None:
            return None
        import streamlit as st

        return st.session_state
    except Exception:
        return None


def _secrets_snapshot() -> dict[str, str]:
    snap = {key: _secret(key) for key in _SECRET_KEYS}
    state = _session_state()
    if state is not None:
        choice = str(state.get(SESSION_PROVIDER_KEY) or "").strip().lower()
        if choice and choice != PROVIDER_CHOICE_AUTO:
            snap["AI_PROVIDER"] = choice
        if state.get(SESSION_CONSUMER_ACK_KEY):
            snap["ESA_CLAUDE_CONSUMER_ACK"] = "1"
    return snap


def remote_browser_session() -> bool:
    """True when the current Streamlit viewer is not on this machine (LAN / proxy / cloud).

    ``st.context.ip_address`` is None for localhost connections; anything else means
    someone else's browser would be driving this PC's Claude sign-in.
    """
    if _session_state() is None:
        return False
    try:
        import streamlit as st

        ip = st.context.ip_address
    except Exception:
        return False
    if isinstance(ip, str) and ip:
        try:
            addr = ipaddress.ip_address(ip.split("%")[0])
        except ValueError:
            return True
        mapped = getattr(addr, "ipv4_mapped", None)
        if not (mapped or addr).is_loopback:
            return True
    # A tunnel or reverse proxy on this PC (ngrok, cloudflared, VS Code port forwarding)
    # connects from 127.0.0.1, so the socket address looks local. The headers don't.
    return _proxied_or_foreign_host()


def _proxied_or_foreign_host() -> bool:
    try:
        import streamlit as st

        headers = st.context.headers
    except Exception:
        return False
    if not hasattr(headers, "get"):
        return False
    for name in _PROXY_HEADERS:
        value = headers.get(name)
        if isinstance(value, str) and value.strip():
            return True
    host = headers.get("host")
    if not isinstance(host, str) or not host.strip():
        return False
    host = host.strip().lower()
    if host.startswith("["):
        hostname = host[1:].split("]", 1)[0]
    else:
        hostname = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    return hostname not in _LOCAL_HOSTNAMES


def _snap(snap: dict[str, str], name: str) -> str:
    return snap.get(name, "")


@lru_cache(maxsize=1)
def ollama_reachable() -> bool:
    """True when a local Ollama daemon answers on localhost:11434."""
    try:
        with urllib.request.urlopen(OLLAMA_PROBE_URL, timeout=OLLAMA_PROBE_TIMEOUT_S) as resp:
            return 200 <= getattr(resp, "status", 200) < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def clear_ollama_probe_cache() -> None:
    """Test helper — reset Ollama reachability cache."""
    ollama_reachable.cache_clear()


def _infer_provider_from_snapshot(snap: dict[str, str]) -> str:
    explicit = _snap(snap, "AI_PROVIDER").lower()
    if explicit:
        return explicit
    if _snap(snap, "AZURE_OPENAI_ENDPOINT"):
        return "azure"
    base = _snap(snap, "OPENAI_BASE_URL").lower()
    if "11434" in base or "ollama" in base:
        return "ollama"
    if "groq.com" in base:
        return "groq"
    if "generativelanguage.googleapis.com" in base:
        return "gemini"
    if "together.xyz" in base:
        return "together"
    if "anthropic.com" in base:
        return "anthropic"
    # Free-first auto-select when no explicit provider
    if ollama_reachable():
        return "ollama"
    for free_cloud in _FREE_CLOUD_INFER_ORDER:
        env_name = PROVIDER_KEY_ENV[free_cloud]
        if _snap(snap, env_name):
            return free_cloud
    if _snap(snap, "OPENAI_API_KEY"):
        # Placeholder "ollama" without base URL still means local Ollama intent
        if _snap(snap, "OPENAI_API_KEY").lower() == "ollama":
            return "ollama"
        return "openai"
    return "offline"


def _resolve_api_key(provider: str, preset: dict[str, str | bool], snap: dict[str, str]) -> str:
    """Resolve API key for the selected provider only (no cross-vendor key reuse)."""
    env_name = PROVIDER_KEY_ENV.get(provider)
    if env_name:
        key = _snap(snap, env_name)
        if key:
            return key
    # OpenAI-compatible stacks may share OPENAI_API_KEY (never Gemini).
    if provider in ("openai", "azure", "ollama", "groq", "together"):
        key = _snap(snap, "OPENAI_API_KEY")
        if key:
            return key
        placeholder = preset.get("placeholder_key")
        if placeholder and provider == "ollama":
            return str(placeholder)
    return ""


def _shared_host_snapshot(snap: dict[str, str]) -> bool:
    """Hosted mode, LAN binding, HTTP API key or a container: a shared server."""
    from security import folder_workflow_disabled

    if folder_workflow_disabled() or "ESA_API_KEY" in os.environ:
        return True
    if claude_code.running_in_container():
        return True
    # Either source turning a flag on wins: secrets can't switch off an env flag.
    return any(
        value.strip().lower() not in _FALSY
        for key in _SHARED_HOST_FLAGS
        for value in (_snap(snap, key), os.environ.get(key, ""))
    )


def claude_code_blocked() -> bool:
    """Personal Claude sign-in must never serve a shared host or a remote browser."""
    return _shared_host_snapshot(_secrets_snapshot()) or remote_browser_session()


def _timeout_from_snapshot(snap: dict[str, str]) -> float:
    try:
        value = float(_snap(snap, "ESA_CLAUDE_CODE_TIMEOUT_SEC") or claude_code.DEFAULT_TIMEOUT_SEC)
    except ValueError:
        value = claude_code.DEFAULT_TIMEOUT_SEC
    if not math.isfinite(value):
        value = claude_code.DEFAULT_TIMEOUT_SEC
    return min(max(value, 10.0), 900.0)


def _claude_code_settings(snap: dict[str, str]) -> LlmSettings:
    """Claude subscription via the local, user-signed-in Claude Code CLI (no keys, no tokens)."""
    base = dict(
        provider=claude_code.PROVIDER_ID,
        label=claude_code.PROVIDER_LABEL,
        api_key="",
        base_url="",
        model=_snap(snap, "CLAUDE_CODE_MODEL") or claude_code.DEFAULT_MODEL,
        supports_json_mode=False,
        free=False,
        timeout_sec=_timeout_from_snapshot(snap),
    )
    if _shared_host_snapshot(snap) or remote_browser_session():
        return LlmSettings(
            **base,
            unavailable_reason=(
                "Claude subscription works only on a consultant's own PC, opened from that "
                "PC's browser — it is disabled on hosted / shared servers, containers and "
                "for remote viewers, where one sign-in would serve everyone. Use "
                "`AI_PROVIDER=anthropic` with an Anthropic API key there."
            ),
        )
    if not claude_code.valid_model(base["model"]):
        return LlmSettings(
            **base,
            unavailable_reason=(
                "CLAUDE_CODE_MODEL must be a model alias or id such as `sonnet`, `opus` or "
                "`claude-sonnet-4-5` (letters, digits, `.`, `-`, `_`, `:` only)."
            ),
        )
    cli = claude_code.find_cli(_snap(snap, "CLAUDE_CLI_PATH"))
    if not cli:
        return LlmSettings(
            **base, unavailable_reason=f"Claude Code is not installed. {claude_code.INSTALL_HINT}"
        )
    status = claude_code.auth_status(cli)
    if status.error or not status.logged_in:
        detail = f" ({status.error})" if status.error else ""
        return LlmSettings(
            **base,
            cli_path=cli,
            unavailable_reason=f"Claude Code is not signed in{detail}. {claude_code.INSTALL_HINT}",
        )
    if not status.claude_account:
        return LlmSettings(
            **base,
            cli_path=cli,
            unavailable_reason=(
                "Claude Code is signed in with an API key or cloud provider, not a Claude "
                f"account. Run `claude` → `/login` and choose **Claude account**. "
                "For API-key billing use `AI_PROVIDER=anthropic` instead."
            ),
        )
    if status.consumer_plan and _snap(snap, "ESA_CLAUDE_CONSUMER_ACK").lower() not in _TRUTHY:
        return LlmSettings(
            **base,
            cli_path=cli,
            account=status.plan_label,
            consumer_plan=True,
            unavailable_reason=(
                f"{status.plan_label} is not a Team / Enterprise seat. Confirm the privacy note in "
                "**AI options** (or set `ESA_CLAUDE_CONSUMER_ACK=1` for scripts) before "
                "sending project data."
            ),
        )
    return LlmSettings(
        **base, cli_path=cli, account=status.plan_label, consumer_plan=status.consumer_plan
    )


def resolve_llm_settings() -> LlmSettings:
    snap = _secrets_snapshot()
    provider = _infer_provider_from_snapshot(snap)
    if provider == claude_code.PROVIDER_ID:
        return _claude_code_settings(snap)
    if provider == "offline":
        return LlmSettings(
            provider="offline",
            label="Offline",
            api_key="",
            base_url="",
            model=DEFAULT_MODEL,
            supports_json_mode=False,
            free=True,
        )

    preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["openai"])
    label = str(preset.get("label", provider.title()))
    api_key = _resolve_api_key(provider, preset, snap)
    if provider == "anthropic":
        # OPENAI_* overrides usually belong to another provider; never send an
        # Anthropic key to a non-Anthropic host or a non-Claude model name.
        override = _snap(snap, "OPENAI_BASE_URL")
        base_url = override if "anthropic.com" in override.lower() else ""
        openai_model = _snap(snap, "OPENAI_MODEL")
        model = _snap(snap, "ANTHROPIC_MODEL") or (
            openai_model if openai_model.lower().startswith("claude") else ""
        )
    else:
        base_url = _snap(snap, "OPENAI_BASE_URL") or _snap(snap, "AZURE_OPENAI_ENDPOINT")
        model = _snap(snap, "OPENAI_MODEL")
    if not base_url:
        base_url = str(preset.get("base_url") or "")
    model = model or str(preset.get("model") or DEFAULT_MODEL)
    supports_json_mode = bool(preset.get("supports_json_mode", True))
    free = bool(preset.get("free", False))

    return LlmSettings(
        provider=provider,
        label=label,
        api_key=api_key,
        base_url=base_url,
        model=model,
        supports_json_mode=supports_json_mode,
        free=free,
    )


def openai_api_key() -> str:
    return resolve_llm_settings().api_key


def openai_base_url() -> str:
    return resolve_llm_settings().base_url


def openai_model() -> str:
    return resolve_llm_settings().model


def ai_available() -> bool:
    return resolve_llm_settings().available


def _host_label(base_url: str) -> str:
    if not base_url:
        return "default"
    try:
        return urlparse(base_url).netloc or base_url
    except Exception:
        return base_url


def ai_status_message(settings: LlmSettings | None = None) -> str:
    settings = settings or resolve_llm_settings()
    if settings.provider == claude_code.PROVIDER_ID:
        if not settings.available:
            return f"**{settings.label}** not ready — {settings.unavailable_reason}"
        return (
            f"LLM ready — **{settings.label}** · {settings.account} · model "
            f"`{settings.model}` · runs on this PC through your own Claude Code sign-in "
            "(usage counts toward your plan limits)."
        )
    if not settings.available:
        return (
            "AI running in **offline mode** (rule-based). For a free LLM: install "
            "[Ollama](https://ollama.com) (`ollama pull qwen2.5:7b`) or set "
            "`GEMINI_API_KEY` / `GROQ_API_KEY` in `.streamlit/secrets.toml`. "
            "For **Claude in Streamlit**, set `AI_PROVIDER=anthropic` and "
            "`ANTHROPIC_API_KEY` (Anthropic Console API key). To use your own "
            "**Claude Max / Team** plan on this PC, pick **My Claude account** in "
            "AI options (requires Claude Code signed in with `/login`)."
        )
    cost = "free" if settings.free else "paid"
    return (
        f"LLM ready — **{settings.label}** ({cost}) · model `{settings.model}` · "
        f"host `{_host_label(settings.base_url)}`."
    )
