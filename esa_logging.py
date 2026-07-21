"""
Centralized structured logging for ESA Report Generator.

Emits JSON lines when ESA_JSON_LOG=1 (default in Docker/production).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for key in ("tenant_id", "user_id", "request_id", "event"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)


def json_logging_enabled() -> bool:
    return os.environ.get("ESA_JSON_LOG", "").strip().lower() in ("1", "true", "yes")


def configure_logging(*, level: int | None = None) -> None:
    """Configure root logger once (idempotent)."""
    root = logging.getLogger()
    if getattr(root, "_esa_configured", False):
        return
    log_level = (
        level
        if level is not None
        else getattr(logging, os.environ.get("ESA_LOG_LEVEL", "INFO").upper(), logging.INFO)
    )
    root.setLevel(log_level)
    handler = logging.StreamHandler(sys.stderr)
    if json_logging_enabled():
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)
    root._esa_configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Structured info log with an event name and extra fields."""
    extra = {k: v for k, v in fields.items() if v is not None}
    extra["event"] = event
    logger.info(event, extra=extra)
