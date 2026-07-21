"""Ecoventure branding assets."""

from __future__ import annotations

import unittest
from pathlib import Path

from ui.branding import (
    ASSETS_DIR,
    ATTRIBUTION_LINE,
    AUTHOR_NAME,
    COLOR_MAGENTA,
    COLOR_MOSS,
    COLOR_SLATE,
    COMPANY_NAME,
    LOGO_WHITE,
    status_badge_html,
)


class TestBranding(unittest.TestCase):
    def test_colors_match_site_palette(self) -> None:
        self.assertEqual(COLOR_SLATE.lower(), "#2e3540")
        self.assertEqual(COLOR_MAGENTA.lower(), "#b24292")
        self.assertEqual(COLOR_MOSS.lower(), "#3d6b4f")

    def test_logo_asset_present(self) -> None:
        self.assertTrue(ASSETS_DIR.is_dir(), "run scripts/fetch_ecoventure_assets.py")
        self.assertTrue(LOGO_WHITE.is_file(), f"missing {LOGO_WHITE}")

    def test_company_and_attribution(self) -> None:
        self.assertIn("Ecoventure", COMPANY_NAME)
        self.assertIn(AUTHOR_NAME, ATTRIBUTION_LINE)
        self.assertIn(COMPANY_NAME, ATTRIBUTION_LINE)
        self.assertIn("Copyright 2026", ATTRIBUTION_LINE)

    def test_status_badge_html_escapes_and_kinds(self) -> None:
        html = status_badge_html("ok", 'A <b>"x"')
        self.assertIn("ev-badge-ok", html)
        self.assertIn("&lt;b&gt;", html)
        self.assertIn("&quot;x&quot;", html)
        self.assertIn("ev-badge-err", status_badge_html("err", "missing"))
        self.assertIn("ev-badge-muted", status_badge_html("unknown", "x"))


if __name__ == "__main__":
    unittest.main()
