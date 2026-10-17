"""Tests for tenant isolation helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from esa_tenant import TenantError, assert_path_within_tenant, normalize_tenant_id, tenant_subdir


class EsaTenantTests(unittest.TestCase):
    def test_normalize_tenant_id(self) -> None:
        self.assertEqual(normalize_tenant_id(" Ecoventure/West "), "ecoventure_west")

    def test_tenant_subdir_create(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = tenant_subdir("deliverables", tenant_id="team-a", base=Path(tmp), create=True)
            self.assertTrue(path.is_dir())

    def test_path_traversal_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            outside = base / "outside.txt"
            outside.write_text("x", encoding="utf-8")
            with self.assertRaises(TenantError) as ctx:
                assert_path_within_tenant(outside, "team-a", base=base / "tenants")
            self.assertEqual(str(ctx.exception), "Path escapes tenant root.")
            self.assertNotIn(str(outside), str(ctx.exception))

    def test_traversal_tenant_ids_rejected(self) -> None:
        for tid in ("..", ".", "....", "../..", "..\\..", "_", "-", "/", ". ."):
            with self.subTest(tenant_id=tid):
                with self.assertRaises(TenantError):
                    normalize_tenant_id(tid)

    def test_path_ish_tenant_ids_stay_under_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "tenants"
            for tid in ("../../etc", "a/../..", "x/..", "acme.com", "..a", "a" * 200):
                with self.subTest(tenant_id=tid):
                    path = tenant_subdir("jobs", tenant_id=tid, base=base)
                    resolved = path.resolve()
                    self.assertTrue(resolved.is_relative_to(base.resolve()))
                    self.assertNotEqual(resolved.parent, base.resolve())
                    self.assertRegex(path.parent.name, r"^[a-z0-9][a-z0-9_-]{0,63}$")

    def test_traversal_category_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for category in ("..", "../x", "", "a/b"):
                with self.subTest(category=category):
                    with self.assertRaises(TenantError):
                        tenant_subdir(category, tenant_id="team-a", base=Path(tmp))

    def test_windows_reserved_device_names_rejected(self) -> None:
        reserved = ("nul", "NUL", "con", "prn", "aux", "com1", "Com9", "lpt1", "LPT9", " nul ")
        with tempfile.TemporaryDirectory() as tmp:
            for name in reserved:
                with self.subTest(tenant_id=name):
                    with self.assertRaises(TenantError):
                        normalize_tenant_id(name)
                    with self.assertRaises(TenantError):
                        tenant_subdir("jobs", tenant_id=name, base=Path(tmp), create=True)
                with self.subTest(category=name):
                    with self.assertRaises(TenantError):
                        tenant_subdir(name, tenant_id="team-a", base=Path(tmp), create=True)
            # Lookalikes that are not device names stay valid.
            for ok in ("nul_x", "console", "com10", "lpt0", "auxiliary"):
                with self.subTest(ok=ok):
                    self.assertEqual(normalize_tenant_id(ok), ok)
                    tenant_subdir(ok, tenant_id="team-a", base=Path(tmp), create=True)


if __name__ == "__main__":
    unittest.main()
