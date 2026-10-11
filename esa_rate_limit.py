"""
Simple in-process rate limiting for HTTP render service and future API endpoints.
"""

from __future__ import annotations

import os
import time
from collections import OrderedDict, defaultdict, deque
from threading import Lock

_DEFAULT_WINDOW_SEC = 60
_DEFAULT_MAX_REQUESTS = 30


class RateLimitExceeded(Exception):
    """Too many requests from a client in the sliding window."""


_lock = Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)


def _window_sec() -> int:
    raw = os.environ.get("ESA_RATE_LIMIT_WINDOW_SEC", str(_DEFAULT_WINDOW_SEC))
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_WINDOW_SEC


def _max_requests() -> int:
    raw = os.environ.get("ESA_RATE_LIMIT_MAX", str(_DEFAULT_MAX_REQUESTS))
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_MAX_REQUESTS


def _rate_limit_disabled() -> bool:
    return os.environ.get("ESA_DISABLE_RATE_LIMIT", "").strip().lower() in ("1", "true", "yes")


def check_rate_limit(client_key: str) -> None:
    """Raise RateLimitExceeded when client_key exceeds the sliding window cap."""
    if _rate_limit_disabled():
        return
    now = time.monotonic()
    window = _window_sec()
    cap = _max_requests()
    with _lock:
        bucket = _hits[client_key]
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= cap:
            raise RateLimitExceeded("Rate limit exceeded; retry later.")
        bucket.append(now)
        # Full-map eviction only when the map grows — avoid O(n) on every hit.
        if len(_hits) > 256:
            stale = [k for k, q in _hits.items() if not q or now - q[-1] > window]
            for k in stale:
                if k != client_key:
                    del _hits[k]
            if len(_hits) > 4096:
                overflow = sorted(
                    ((k, q[-1] if q else 0.0) for k, q in _hits.items() if k != client_key),
                    key=lambda item: item[1],
                )
                for k, _ in overflow[: max(0, len(_hits) - 4096)]:
                    _hits.pop(k, None)


# --- Failed-authentication throttle (separate from authenticated render quota) ---

_DEFAULT_AUTH_FAIL_WINDOW_SEC = 60
_DEFAULT_AUTH_FAIL_MAX = 10
# Hard cap on tracked client keys; the least recently failing key is evicted first.
_AUTH_FAIL_MAX_TRACKED = 4096

# Own lock so failed-auth floods never contend with authenticated quota checks.
_auth_lock = Lock()
# Ordered by most recent failure (move_to_end on every hit), so expired keys and
# eviction candidates are always at the front: pruning is O(1) amortized.
_auth_failures: OrderedDict[str, deque[float]] = OrderedDict()


def _auth_fail_window_sec() -> int:
    raw = os.environ.get("ESA_AUTH_FAIL_WINDOW_SEC", str(_DEFAULT_AUTH_FAIL_WINDOW_SEC))
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_AUTH_FAIL_WINDOW_SEC


def _auth_fail_max() -> int:
    raw = os.environ.get("ESA_AUTH_FAIL_MAX", str(_DEFAULT_AUTH_FAIL_MAX))
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_AUTH_FAIL_MAX


def record_failed_auth(client_key: str) -> None:
    """Record one failed authentication for client_key (usually ``ip:<peer>``).

    Raises RateLimitExceeded when client_key has exceeded ``ESA_AUTH_FAIL_MAX`` failures
    within ``ESA_AUTH_FAIL_WINDOW_SEC``. Only failures are counted, so unauthenticated
    traffic never consumes the authenticated render quota of other clients behind the
    same IP / NAT. At most ``_AUTH_FAIL_MAX_TRACKED`` keys are kept (oldest evicted).
    """
    if _rate_limit_disabled():
        return
    now = time.monotonic()
    window = _auth_fail_window_sec()
    cap = _auth_fail_max()
    with _auth_lock:
        bucket = _auth_failures.get(client_key)
        if bucket is None:
            bucket = deque()
            _auth_failures[client_key] = bucket
        else:
            _auth_failures.move_to_end(client_key)
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        bucket.append(now)
        exceeded = len(bucket) > cap
        # Front entries have the oldest last-failure: drop expired ones, then enforce cap.
        while _auth_failures:
            oldest_key, oldest = next(iter(_auth_failures.items()))
            if oldest_key == client_key:
                break
            if (oldest and now - oldest[-1] <= window) and len(
                _auth_failures
            ) <= _AUTH_FAIL_MAX_TRACKED:
                break
            _auth_failures.popitem(last=False)
    if exceeded:
        raise RateLimitExceeded("Too many failed authentication attempts; retry later.")


def reset_rate_limits() -> None:
    """Clear counters (tests only)."""
    with _lock:
        _hits.clear()
    with _auth_lock:
        _auth_failures.clear()
