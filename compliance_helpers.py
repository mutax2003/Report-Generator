"""Shared field helpers for compliance checklist modules."""

from __future__ import annotations

import re
from typing import Any, Iterable


def norm_key(name: str) -> str:
    s = str(name).strip()
    s = re.sub(r"\s+", "_", s)
    return s.lower()


def has_value(val: Any) -> bool:
    if val is None:
        return False
    s = str(val).strip()
    return bool(s) and s.lower() not in ("nan", "none", "n/a", "")


def yes_value(val: Any) -> bool:
    return str(val or "").strip().lower() in (
        "yes",
        "y",
        "true",
        "1",
        "required",
        "likely",
    )


def meta_value(meta: dict[str, str], field_name: str) -> Any:
    target = norm_key(field_name)
    for key, val in meta.items():
        if norm_key(key) == target and has_value(val):
            return val
    return None


def context_value(
    context: dict[str, Any],
    meta: dict[str, str],
    field_name: str,
) -> Any:
    meta_val = meta_value(meta, field_name)
    if meta_val is not None:
        return meta_val
    target = norm_key(field_name)
    for key, val in context.items():
        if norm_key(key) == target:
            return val
    return None


_EXCEL_BAD_FLOAT = frozenset({"nan", "none", "#div/0!", "#value!"})


def parse_float(val: Any) -> float | None:
    """Parse numeric Excel/context values; returns None for blanks and formula errors."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in _EXCEL_BAD_FLOAT:
        return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def normalize_appendix_labels(
    labels: Iterable[Any] | None,
) -> frozenset[str]:
    """Uppercase A–H labels from any iterable (uploads, context, preflight)."""
    return frozenset(
        str(x).strip().upper() for x in (labels or ()) if str(x).strip()
    )


def sorted_appendix_label_list(
    labels: Iterable[Any] | None,
) -> list[str]:
    return sorted(normalize_appendix_labels(labels))


def resolved_appendix_labels(
    context: dict[str, Any],
    fallback: Iterable[Any] | None = None,
) -> frozenset[str]:
    """Prefer engine-evaluated labels (incl. predicted A/D/G), else upload/fallback."""
    evaluated = context.get("_dwda_appendix_labels_evaluated")
    if evaluated is not None:
        return normalize_appendix_labels(evaluated)
    return normalize_appendix_labels(fallback)
