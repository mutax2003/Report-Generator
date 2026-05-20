"""Optional OpenAI chat client (JSON + text)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from ai.config import AI_PROMPT_VERSION, MAX_AI_OUTPUT_TOKENS, openai_api_key, openai_base_url, openai_model

logger = logging.getLogger(__name__)


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


def chat_completion(
    *,
    system: str,
    user: str,
    json_mode: bool = False,
) -> str | None:
    key = openai_api_key()
    if not key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed")
        return None

    kwargs: dict[str, Any] = {
        "model": openai_model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user[:120_000]},
        ],
        "max_tokens": MAX_AI_OUTPUT_TOKENS,
        "temperature": 0.2,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    client_kwargs: dict[str, Any] = {"api_key": key}
    base = openai_base_url()
    if base:
        client_kwargs["base_url"] = base.rstrip("/") + (
            "" if "/openai" in base else "/openai/v1"
        )

    try:
        client = OpenAI(**client_kwargs)
        resp = client.chat.completions.create(**kwargs)
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        logger.exception("OpenAI API call failed")
        return None


def complete_json(system: str, user: str) -> dict[str, Any] | None:
    raw = chat_completion(system=system, user=user, json_mode=True)
    if not raw:
        return None
    return _extract_json_object(raw)


def complete_text(system: str, user: str) -> str | None:
    return chat_completion(system=system, user=user, json_mode=False)


def prompt_version() -> str:
    return AI_PROMPT_VERSION
