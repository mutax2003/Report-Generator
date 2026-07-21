"""
Multi-tenant data isolation helpers (filesystem paths and context scoping).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_TENANT_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


class TenantError(ValueError):
    """Invalid tenant identifier."""


def normalize_tenant_id(tenant_id: str) -> str:
    token = (tenant_id or "default").strip().lower()
    if not token:
        token = "default"
    safe = _TENANT_SAFE.sub("_", token).strip("_")
    if not safe:
        raise TenantError("Tenant id is empty after normalization")
    return safe[:64]


def tenant_root(base: Path | None = None, tenant_id: str = "default") -> Path:
    """Return isolated storage root for a tenant."""
    root = base or Path(os.environ.get("ESA_TENANT_DATA_ROOT", ".esa_tenants"))
    return root / normalize_tenant_id(tenant_id)


def tenant_subdir(
    category: str,
    *,
    tenant_id: str = "default",
    base: Path | None = None,
    create: bool = False,
) -> Path:
    """Deliverables, uploads, jobs, etc. under tenant root."""
    path = tenant_root(base, tenant_id) / category
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def assert_path_within_tenant(path: Path, tenant_id: str, *, base: Path | None = None) -> None:
    """Prevent path traversal outside tenant root."""
    root = tenant_root(base, tenant_id).resolve()
    resolved = path.resolve()
    if root not in resolved.parents and resolved != root:
        raise TenantError("Path escapes tenant root.")
