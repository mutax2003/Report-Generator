"""
Records retention policy helpers for generated deliverables and audit logs.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

_FALLBACK_POLICY = "schemas/records_retention_policy.json"


def resolve_policy_path(path: Path | None = None) -> Path:
    """Resolve retention policy path; reads ESA_RETENTION_POLICY at call time."""
    if path is not None:
        return path
    return Path(os.environ.get("ESA_RETENTION_POLICY", _FALLBACK_POLICY))


# Back-compat alias — prefer resolve_policy_path() for late env changes.
DEFAULT_POLICY_PATH = Path(_FALLBACK_POLICY)


@dataclass(frozen=True)
class RetentionPolicy:
    deliverable_days: int = 2555  # ~7 years
    audit_log_days: int = 2555
    temp_upload_days: int = 30

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> RetentionPolicy:
        def _days(key: str, default: int) -> int:
            raw = data.get(key, default)
            return int(raw) if isinstance(raw, (int, float, str)) else default

        return cls(
            deliverable_days=_days("deliverable_days", 2555),
            audit_log_days=_days("audit_log_days", 2555),
            temp_upload_days=_days("temp_upload_days", 30),
        )


def load_retention_policy(path: Path | None = None) -> RetentionPolicy:
    policy_path = resolve_policy_path(path)
    if not policy_path.is_file():
        return RetentionPolicy()
    data = json.loads(policy_path.read_text(encoding="utf-8"))
    return RetentionPolicy.from_dict(data)


def file_age_days(path: Path, *, now: datetime | None = None) -> float:
    ref = now or datetime.now(UTC)
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return (ref - mtime).total_seconds() / 86400.0


def files_exceeding_retention(
    root: Path,
    *,
    max_age_days: int,
    patterns: Iterable[str] = ("*.docx", "*.zip", "*.json", "*.jsonl"),
    now: datetime | None = None,
) -> list[Path]:
    """Return files under root older than max_age_days matching patterns."""
    if not root.is_dir():
        return []
    cutoff = (now or datetime.now(UTC)) - timedelta(days=max_age_days)
    stale: list[Path] = []
    for pattern in patterns:
        for path in root.rglob(pattern):
            if not path.is_file():
                continue
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            if mtime < cutoff:
                stale.append(path)
    return sorted(stale)


def purge_stale_files(
    root: Path,
    *,
    max_age_days: int,
    dry_run: bool = True,
    patterns: Iterable[str] = ("*.docx", "*.zip", "*.json", "*.jsonl"),
) -> list[Path]:
    """Delete or list files exceeding retention. Returns affected paths."""
    targets = files_exceeding_retention(root, max_age_days=max_age_days, patterns=patterns)
    if not dry_run:
        for path in targets:
            path.unlink(missing_ok=True)
    return targets
