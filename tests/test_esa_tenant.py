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


if __name__ == "__main__":
    unittest.main()
