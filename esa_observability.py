"""
Lightweight observability hooks: counters, timers, optional Sentry forwarding.
"""

from __future__ import annotations

import os
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from typing import Any

_lock = Lock()
_counters: Counter[str] = Counter()


@dataclass
class _TimerStat:
    """Running aggregate — O(1) memory per metric, no unbounded sample list."""

    count: int = 0
    total_sec: float = 0.0

    def add(self, elapsed: float) -> None:
        self.count += 1
        self.total_sec += elapsed


_timers: dict[str, _TimerStat] = {}


def increment(metric: str, value: int = 1) -> None:
    with _lock:
        _counters[metric] += value


def snapshot_metrics() -> dict[str, Any]:
    with _lock:
        timers = {
            name: {
                "count": stat.count,
                "total_sec": round(stat.total_sec, 4),
                "avg_sec": round(stat.total_sec / stat.count, 4) if stat.count else 0.0,
            }
            for name, stat in _timers.items()
        }
        return {"counters": dict(_counters), "timers": timers}


def reset_metrics() -> None:
    with _lock:
        _counters.clear()
        _timers.clear()


@contextmanager
def observe_duration(metric: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        with _lock:
            _timers.setdefault(metric, _TimerStat()).add(elapsed)
        increment(f"{metric}.count")


_sentry_ready = False


def _ensure_sentry() -> Any | None:
    """Initialize the Sentry SDK once; return the module or None when unavailable."""
    global _sentry_ready
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return None
    try:
        import sentry_sdk
    except ImportError:
        return None
    if not _sentry_ready:
        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0")),
        )
        _sentry_ready = True
    return sentry_sdk


def capture_exception(exc: BaseException, *, context: dict[str, Any] | None = None) -> None:
    """Forward to Sentry when SENTRY_DSN is set; always increment error counter."""
    increment("errors.total")
    sentry_sdk = _ensure_sentry()
    if sentry_sdk is None:
        return
    try:
        with sentry_sdk.push_scope() as scope:
            for key, value in (context or {}).items():
                scope.set_extra(key, value)
            sentry_sdk.capture_exception(exc)
    except Exception:
        increment("errors.sentry_forward_failed")
