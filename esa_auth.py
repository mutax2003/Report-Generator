"""
Authentication and RBAC scaffolding for HTTP/API and future multi-tenant SaaS mode.

Internal deployments rely on Entra ID at the reverse proxy; this module supports
optional API-key auth and role checks for headless endpoints.

Identity headers (X-ESA-User-Id / Tenant-Id) are advisory for shared API keys.
Set ESA_API_SERVICE_USER to pin actor identity server-side. Roles always come from
ESA_DEFAULT_ROLES (client X-ESA-Roles is ignored).
"""

from __future__ import annotations

import os
import re
import secrets
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._@+=\-]{1,128}$")


class Role(str, Enum):
    VIEWER = "viewer"
    AUTHOR = "author"
    QP = "qp"
    ADMIN = "admin"


ROLE_RANK = {
    Role.VIEWER: 1,
    Role.AUTHOR: 2,
    Role.QP: 3,
    Role.ADMIN: 4,
}


class AuthError(PermissionError):
    """Authentication or authorization failure."""


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    tenant_id: str
    roles: tuple[Role, ...]

    def has_role(self, role: Role) -> bool:
        return any(ROLE_RANK.get(r, 0) >= ROLE_RANK[role] for r in self.roles)


def _parse_roles(raw: str) -> tuple[Role, ...]:
    roles: list[Role] = []
    for part in raw.split(","):
        token = part.strip().lower()
        if not token:
            continue
        try:
            roles.append(Role(token))
        except ValueError:
            continue
    return tuple(roles or (Role.VIEWER,))


def roles_from_env(default: Iterable[Role] = (Role.AUTHOR,)) -> tuple[Role, ...]:
    raw = os.environ.get("ESA_DEFAULT_ROLES", "")
    if not raw.strip():
        return tuple(default)
    return _parse_roles(raw)


def _safe_id(raw: str, fallback: str) -> str:
    token = (raw or "").strip()
    if token and _SAFE_ID_RE.fullmatch(token):
        return token
    return fallback


def _api_key_matches(provided: str, expected: str) -> bool:
    """Constant-time compare; unequal lengths are rejected without leaking timing."""
    if not provided or not expected:
        return False
    # Pad to equal length so compare_digest never raises; mismatch still fails.
    if len(provided) != len(expected):
        secrets.compare_digest(provided, provided)
        return False
    return secrets.compare_digest(provided, expected)


def api_key_required() -> bool:
    """True when ESA_API_KEY is set or ESA_REQUIRE_API_KEY forces auth."""
    if os.environ.get("ESA_API_KEY", "").strip():
        return True
    return os.environ.get("ESA_REQUIRE_API_KEY", "").strip().lower() in ("1", "true", "yes")


def auth_from_headers(headers: dict[str, str] | None = None) -> AuthContext | None:
    """
    Build AuthContext from optional API headers when ESA_API_KEY is configured.

    Headers:
      X-ESA-API-Key: must match ESA_API_KEY (timing-safe)
      X-ESA-User-Id: optional user identifier (ignored when ESA_API_SERVICE_USER is set)
      X-ESA-Tenant-Id: optional tenant identifier
      X-ESA-Roles: ignored — roles come from ESA_DEFAULT_ROLES
    """
    expected = os.environ.get("ESA_API_KEY", "").strip()
    if not expected:
        if os.environ.get("ESA_REQUIRE_API_KEY", "").strip().lower() in ("1", "true", "yes"):
            raise AuthError("Authentication required")
        return None
    hdrs = {k.lower(): v for k, v in (headers or {}).items()}
    provided = hdrs.get("x-esa-api-key", "").strip()
    if not _api_key_matches(provided, expected):
        raise AuthError("Invalid API key")

    service_user = os.environ.get("ESA_API_SERVICE_USER", "").strip()
    if service_user:
        user_id = _safe_id(service_user, "api-user")
    else:
        user_id = _safe_id(hdrs.get("x-esa-user-id", ""), "api-user")
    tenant_id = _safe_id(hdrs.get("x-esa-tenant-id", ""), "default")
    roles = roles_from_env()
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=roles)


def require_role(ctx: AuthContext | None, role: Role) -> None:
    """Raise AuthError when ctx is missing or lacks role."""
    if ctx is None:
        if api_key_required():
            raise AuthError("Authentication required")
        return
    if not ctx.has_role(role):
        raise AuthError(f"Role '{role.value}' required")
