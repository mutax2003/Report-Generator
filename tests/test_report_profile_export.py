"""Report profile recommended fields and ReportConfig export."""

from __future__ import annotations

import unittest

from report_profile import (
    build_report_config_workbook_bytes,
    get_recommended_fields,
    profile_id_for_phase,
)


class ReportProfileExportTests(unittest.TestCase):
    def test_recommended_fields_phase1(self) -> None:
        fields = get_recommended_fields("phase1_alberta")
        self.assertIn("executive_summary", fields)
        self.assertIn("well_name", fields)

    def test_profile_for_phase(self) -> None:
        self.assertEqual(profile_id_for_phase("Phase 2"), "phase2_esa")

    def test_report_config_workbook(self) -> None:
        data = build_report_config_workbook_bytes("phase2_esa")
        self.assertGreater(len(data), 200)
        self.assertTrue(data[:2] == b"PK")


if __name__ == "__main__":
    unittest.main()
