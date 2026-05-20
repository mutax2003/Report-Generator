"""
AI configuration — keys via environment or Streamlit secrets only (never commit keys).
"""

from __future__ import annotations

import os

AI_PROMPT_VERSION = "1.0.0"
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_AI_INPUT_CHARS = 48_000
MAX_AI_OUTPUT_TOKENS = 4096
DEFAULT_MODEL = "gpt-4o-mini"


def _secret(name: str) -> str:
    try:
        import streamlit as st

        if hasattr(st, "secrets") and name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:
        pass
    return os.environ.get(name, "").strip()


def openai_api_key() -> str:
    return _secret("OPENAI_API_KEY")


def openai_base_url() -> str:
    return _secret("OPENAI_BASE_URL") or _secret("AZURE_OPENAI_ENDPOINT")


def openai_model() -> str:
    return _secret("OPENAI_MODEL") or DEFAULT_MODEL


def ai_available() -> bool:
    return bool(openai_api_key())


def ai_status_message() -> str:
    if ai_available():
        return f"AI enabled ({openai_model()}). Heuristics still used where noted."
    return (
        "AI running in **offline mode** (rule-based). Set `OPENAI_API_KEY` in "
        "environment or `.streamlit/secrets.toml` for enhanced extraction and narratives."
    )
