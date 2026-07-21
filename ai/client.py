"""Optional OpenAI chat client (JSON + text)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from ai.config import AI_PROMPT_VERSION, MAX_AI_OUTPUT_TOKENS, LlmSettings, resolve_llm_settings

logger = logging.getLogger(__name__)

_JSON_ONLY_SUFFIX = "\n\nRespond with a single valid JSON object only."


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def normalize_base_url(base: str) -> str:
    """OpenAI SDK base_url — preserve /v1 and Gemini /openai/ paths."""
    base = base.rstrip("/")
    if not base:
        return base
    if "/openai" in base or base.endswith("/v1"):
        return base
    return f"{base}/openai/v1"


def _create_client(settings: LlmSettings):
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed")
        return None

    client_kwargs: dict[str, Any] = {"api_key": settings.api_key}
    if settings.base_url:
        client_kwargs["base_url"] = normalize_base_url(settings.base_url)
    return OpenAI(**client_kwargs)


def _chat_completion_with_settings(
    settings: LlmSettings,
    *,
    system: str,
    user: str,
    json_mode: bool,
) -> str | None:
    client = _create_client(settings)
    if client is None:
        return None

    kwargs: dict[str, Any] = {
        "model": settings.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user[:120_000]},
        ],
        "max_tokens": MAX_AI_OUTPUT_TOKENS,
        "temperature": 0.2,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        resp = client.chat.completions.create(**kwargs)
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        logger.exception("LLM API call failed (json_mode=%s)", json_mode)
        return None


def chat_completion(
    *,
    system: str,
    user: str,
    json_mode: bool = False,
) -> str | None:
    settings = resolve_llm_settings()
    if not settings.available:
        return None

    if json_mode and settings.supports_json_mode:
        result = _chat_completion_with_settings(
            settings, system=system, user=user, json_mode=True
        )
        if result is not None:
            return result
        return _chat_completion_with_settings(
            settings, system=system + _JSON_ONLY_SUFFIX, user=user, json_mode=False
        )

    if json_mode:
        return _chat_completion_with_settings(
            settings, system=system + _JSON_ONLY_SUFFIX, user=user, json_mode=False
        )

    return _chat_completion_with_settings(
        settings, system=system, user=user, json_mode=False
    )


def complete_json(system: str, user: str) -> dict[str, Any] | None:
    raw = chat_completion(system=system, user=user, json_mode=True)
    if not raw:
        return None
    return _extract_json_object(raw)


def complete_text(system: str, user: str) -> str | None:
    return chat_completion(system=system, user=user, json_mode=False)


def prompt_version() -> str:
    return AI_PROMPT_VERSION
