"""
Multi-tenant data isolation helpers (filesystem paths and context scoping).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Anything outside [a-z0-9_-] (after lower-casing) is folded to "_" — including "." so
# "..", "." and dotted traversal tokens can never survive normalization.
_TENANT_UNSAFE = re.compile(r"[^a-z0-9_-]+")
# Final shape every tenant id / category segment must match before touching disk.
_TENANT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
# Windows device names: "nul", "con", ... resolve to devices, not directories, on any drive.
_WINDOWS_RESERVED_NAMES = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)


class TenantError(ValueError):
    """Invalid tenant identifier."""


def _is_reserved_name(token: str) -> bool:
    return token.lower() in _WINDOWS_RESERVED_NAMES


def normalize_tenant_id(tenant_id: str) -> str:
    token = (tenant_id or "default").strip().lower()
    if not token:
        token = "default"
    safe = _TENANT_UNSAFE.sub("_", token).strip("_-")[:64].rstrip("_-")
    if not safe or not _TENANT_ID_RE.fullmatch(safe) or _is_reserved_name(safe):
        raise TenantError("Tenant id is empty or invalid after normalization")
    return safe


def _validate_category(category: str) -> str:
    token = (category or "").strip()
    if not _TENANT_ID_RE.fullmatch(token) or _is_reserved_name(token):
        raise TenantError("Invalid tenant storage category.")
    return token


def _base_dir(base: Path | None) -> Path:
    return base or Path(os.environ.get("ESA_TENANT_DATA_ROOT", ".esa_tenants"))


def _require_within(path: Path, root: Path) -> None:
    resolved = path.resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise TenantError("Path escapes tenant root.")


def tenant_root(base: Path | None = None, tenant_id: str = "default") -> Path:
    """Return isolated storage root for a tenant (always a direct child of the base dir)."""
    root = _base_dir(base)
    path = root / normalize_tenant_id(tenant_id)
    # Defense in depth: a symlink / junction at the tenant dir must not leave the base.
    _require_within(path, root)
    if path.resolve() == root.resolve():
        raise TenantError("Path escapes tenant root.")
    return path


def tenant_subdir(
    category: str,
    *,
    tenant_id: str = "default",
    base: Path | None = None,
    create: bool = False,
) -> Path:
    """Deliverables, uploads, jobs, etc. under tenant root."""
    root = tenant_root(base, tenant_id)
    path = root / _validate_category(category)
    _require_within(path, root)
    if create:
        path.mkdir(parents=True, exist_ok=True)
        _require_within(path, root)
    return path


def assert_path_within_tenant(path: Path, tenant_id: str, *, base: Path | None = None) -> None:
    """Prevent path traversal outside tenant root."""
    _require_within(path, tenant_root(base, tenant_id))
