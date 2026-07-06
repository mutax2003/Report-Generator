"""Parity between report_profiles.json, field_contract.json, and Ecoventure cell contract."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILES_PATH = ROOT / "schemas" / "report_profiles.json"
CONTRACT_PATH = ROOT / "schemas" / "field_contract.json"
CELL_CONTRACT_PATH = ROOT / "schemas" / "ecoventure_dwda_cell_contract.json"

# Profile-only computed fields not stored in Excel ProjectData
PROFILE_ONLY_FIELDS = frozenset(
    {
        "dwda_calc_summary",
        "dwda_metal_sacks_per_metre",
        "dwda_salt_sacks_per_m3",
        "dwda_phase2_required",
        "phase2_recommended",
        "phase2_drilling_waste_required",
        "dwda_metal_pass",
        "dwda_salt_pass",
        "dwda_dst_pass",
        "dwda_calc_phase2_required",
    }
)

# Cell contract keys map to context via dwda_calculations / ecoventure ingest
CELL_OUTPUT_CONTEXT_KEYS = frozenset(
    {
        "dwda_metal_sacks_per_metre",
        "dwda_salt_sacks_per_m3",
        "dwda_metal_pass",
        "dwda_salt_pass",
        "dwda_dst_pass",
        "dwda_calc_summary",
        "dwda_calc_phase2_required",
    }
)


class SchemaParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profiles = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))["profiles"]
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        cls.cell = json.loads(CELL_CONTRACT_PATH.read_text(encoding="utf-8"))

    def _contract_project_fields(self) -> set[str]:
        pd = self.contract.get("sheets", {}).get("ProjectData", {})
        keys: set[str] = set()
        for key in (
            "recommended_all_phases",
            "recommended_phase_1_alberta_og",
            "recommended_phase_2",
            "recommended_dwda",
        ):
            keys.update(pd.get(key, []))
        return keys

    def test_phase1_alberta_fields_in_contract(self) -> None:
        recommended = set(self.profiles["phase1_alberta"]["recommended_fields"])
        contract_fields = self._contract_project_fields()
        missing = sorted(
            f for f in recommended if f not in contract_fields and f not in PROFILE_ONLY_FIELDS
        )
        self.assertFalse(missing, f"field_contract missing phase1_alberta fields: {missing}")

    def test_cell_contract_outputs_covered_by_profiles(self) -> None:
        phase1_fields = set(self.profiles["phase1_alberta"]["recommended_fields"])
        phase1_fields |= PROFILE_ONLY_FIELDS
        uncovered = sorted(CELL_OUTPUT_CONTEXT_KEYS - phase1_fields)
        self.assertFalse(uncovered, f"cell contract outputs not in phase1_alberta profile: {uncovered}")

    def test_drilling_waste_row_fields_match_excel_layout(self) -> None:
        dw = self.contract.get("sheets", {}).get("DrillingWaste", {})
        row_fields = set(dw.get("row_fields", []))
        expected = {
            "disposal_type",
            "gps_coordinates",
            "sump_depth_m",
            "cover_depth_m",
            "disposal_method",
            "volume_m3",
            "location",
            "waste_manifest_refs",
        }
        self.assertTrue(expected.issubset(row_fields), row_fields)


if __name__ == "__main__":
    unittest.main()
