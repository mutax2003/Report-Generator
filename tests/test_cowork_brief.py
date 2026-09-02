"""Tests for Claude Max / Cowork brief builder."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class CoworkBriefTests(unittest.TestCase):
    def test_build_site_cowork_brief_phase1(self) -> None:
        from ai.cowork_brief import build_site_cowork_brief

        with tempfile.TemporaryDirectory() as tmp:
            text = build_site_cowork_brief(tmp, report_type="phase1_alberta")
        self.assertIn("phase1_alberta", text)
        self.assertIn("ai_drafts", text)
        self.assertIn("adversarial", text.lower())
        self.assertIn("Claude Max", text)
        self.assertIn(str(Path(tmp).resolve()), text)

    def test_groundwater_brief_mentions_well_ids(self) -> None:
        from ai.cowork_brief import build_site_cowork_brief

        text = build_site_cowork_brief("C:\\Projects\\demo", report_type="groundwater_monitoring")
        self.assertIn("well", text.lower())
        self.assertIn("groundwater_monitoring", text)


if __name__ == "__main__":
    unittest.main()
