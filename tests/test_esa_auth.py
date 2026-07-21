"""Tests for auth/RBAC scaffolding."""

from __future__ import annotations

import os
import unittest

from esa_auth import AuthContext, AuthError, Role, auth_from_headers, require_role


class EsaAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self._prev = {
            key: os.environ.get(key)
            for key in (
                "ESA_API_KEY",
                "ESA_DEFAULT_ROLES",
                "ESA_API_SERVICE_USER",
                "ESA_REQUIRE_API_KEY",
            )
        }
        os.environ["ESA_API_KEY"] = "secret-key"
        os.environ.pop("ESA_DEFAULT_ROLES", None)
        os.environ.pop("ESA_API_SERVICE_USER", None)
        os.environ.pop("ESA_REQUIRE_API_KEY", None)

    def tearDown(self) -> None:
        for key, prev in self._prev.items():
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev

    def test_valid_api_key_defaults_to_author(self) -> None:
        ctx = auth_from_headers({"X-ESA-API-Key": "secret-key", "X-ESA-Roles": "qp,admin"})
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertTrue(ctx.has_role(Role.AUTHOR))
        # Client-supplied elevated roles must be ignored.
        self.assertFalse(ctx.has_role(Role.QP))
        self.assertFalse(ctx.has_role(Role.ADMIN))

    def test_roles_from_env_not_client_header(self) -> None:
        os.environ["ESA_DEFAULT_ROLES"] = "qp"
        ctx = auth_from_headers({"X-ESA-API-Key": "secret-key", "X-ESA-Roles": "admin"})
        assert ctx is not None
        self.assertTrue(ctx.has_role(Role.QP))
        self.assertFalse(ctx.has_role(Role.ADMIN))

    def test_service_user_overrides_client_user_id(self) -> None:
        os.environ["ESA_API_SERVICE_USER"] = "automation-bot"
        ctx = auth_from_headers(
            {
                "X-ESA-API-Key": "secret-key",
                "X-ESA-User-Id": "spoofed-user",
            }
        )
        assert ctx is not None
        self.assertEqual(ctx.user_id, "automation-bot")

    def test_invalid_api_key(self) -> None:
        with self.assertRaises(AuthError):
            auth_from_headers({"X-ESA-API-Key": "wrong"})

    def test_require_role_without_ctx_when_api_key_set(self) -> None:
        with self.assertRaises(AuthError):
            require_role(None, Role.AUTHOR)

    def test_require_api_key_env_without_key_configured(self) -> None:
        os.environ.pop("ESA_API_KEY", None)
        os.environ["ESA_REQUIRE_API_KEY"] = "1"
        with self.assertRaises(AuthError):
            auth_from_headers({})


if __name__ == "__main__":
    unittest.main()
