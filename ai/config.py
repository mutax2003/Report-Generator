"""
AI configuration — keys via environment or Streamlit secrets only (never commit keys).

Default preference (when AI_PROVIDER is unset): local Ollama if reachable, then free-tier
cloud keys (Gemini → Groq → Together), then paid OpenAI. LLM stays in the AI side-car
(ai/* + UI Apply) — never inside ReportEngine merge.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse

AI_PROMPT_VERSION = "1.0.0"
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_AI_INPUT_CHARS = 48_000
MAX_AI_OUTPUT_TOKENS = 4096
DEFAULT_MODEL = "gpt-4o-mini"
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
)

# AI_PROVIDER=ollama|groq|gemini|together|openai|azure|offline
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

    @property
    def available(self) -> bool:
        return bool(self.api_key) and self.provider != "offline"


def _secret(name: str) -> str:
    try:
        import streamlit as st

        if hasattr(st, "secrets") and name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:
        pass
    return os.environ.get(name, "").strip()


def _secrets_snapshot() -> dict[str, str]:
    return {key: _secret(key) for key in _SECRET_KEYS}


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


def resolve_llm_settings() -> LlmSettings:
    snap = _secrets_snapshot()
    provider = _infer_provider_from_snapshot(snap)
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
    base_url = _snap(snap, "OPENAI_BASE_URL") or _snap(snap, "AZURE_OPENAI_ENDPOINT")
    if not base_url:
        base_url = str(preset.get("base_url") or "")
    model = _snap(snap, "OPENAI_MODEL") or str(preset.get("model") or DEFAULT_MODEL)
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
    if not settings.available:
        return (
            "AI running in **offline mode** (rule-based). For a free LLM: install "
            "[Ollama](https://ollama.com) (`ollama pull qwen2.5:7b`) or set "
            "`GEMINI_API_KEY` / `GROQ_API_KEY` in `.streamlit/secrets.toml`."
        )
    cost = "free" if settings.free else "paid"
    return (
        f"LLM ready — **{settings.label}** ({cost}) · model `{settings.model}` · "
        f"host `{_host_label(settings.base_url)}`."
    )
