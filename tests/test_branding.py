"""Ecoventure branding assets."""

from __future__ import annotations

import unittest
from pathlib import Path

from ui.branding import (
    ASSETS_DIR,
    ATTRIBUTION_LINE,
    AUTHOR_NAME,
    COLOR_MAGENTA,
    COLOR_SLATE,
    COMPANY_NAME,
    LOGO_WHITE,
)


class TestBranding(unittest.TestCase):
    def test_colors_match_site_palette(self) -> None:
        self.assertEqual(COLOR_SLATE.lower(), "#2e3540")
        self.assertEqual(COLOR_MAGENTA.lower(), "#b24292")

    def test_logo_asset_present(self) -> None:
        self.assertTrue(ASSETS_DIR.is_dir(), "run scripts/fetch_ecoventure_assets.py")
        self.assertTrue(LOGO_WHITE.is_file(), f"missing {LOGO_WHITE}")

    def test_company_and_attribution(self) -> None:
        self.assertIn("Ecoventure", COMPANY_NAME)
        self.assertIn(AUTHOR_NAME, ATTRIBUTION_LINE)
        self.assertIn(COMPANY_NAME, ATTRIBUTION_LINE)
        self.assertIn("Copyright 2026", ATTRIBUTION_LINE)


if __name__ == "__main__":
    unittest.main()
