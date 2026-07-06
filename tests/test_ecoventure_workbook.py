"""Ecoventure Phase I + DWDA workbook ingest."""

from __future__ import annotations

import unittest
from pathlib import Path

from ecoventure_workbook import (
    ECOVENTURE_FOLDER_FILENAME,
    ENGINE_SUPPORTED_CONTRACT_VERSION,
    cell_contract_provenance,
    contract_ingest_warnings,
    extract_ecoventure_workbook,
    get_cell_contract_version,
    get_workbook_template_id,
    is_ecoventure_workbook,
    maybe_merge_ecoventure_from_folder,
    merge_into_engine_excel,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "samples" / "ecoventure_dwda" / "minimal_calc_workbook.xlsx"
BASE = ROOT / "samples" / "phase1_alberta_data.xlsx"


class EcoventureWorkbookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not FIXTURE.is_file():
            import subprocess
            import sys

            subprocess.check_call(
                [sys.executable, str(ROOT / "scripts" / "create_ecoventure_dwda_fixture.py")]
            )

    def test_detect_fixture(self) -> None:
        self.assertTrue(is_ecoventure_workbook(FIXTURE))

    def test_extract_phase1_and_calcs(self) -> None:
        data = extract_ecoventure_workbook(FIXTURE.read_bytes())
        pd = data["project_data"]
        self.assertIn("client_name", pd)
        self.assertEqual(pd.get("well_depth_m"), "500")
        calcs = data["calc_outputs"]
        self.assertIn("metal_sacks_per_metre", calcs)
        self.assertIn("salt_sacks_per_m3", calcs)

    def test_contract_metadata(self) -> None:
        self.assertEqual(get_cell_contract_version(), ENGINE_SUPPORTED_CONTRACT_VERSION)
        self.assertEqual(get_workbook_template_id(), "ecoventure_phase1_2025")
        self.assertFalse(contract_ingest_warnings())

    def test_extract_includes_provenance(self) -> None:
        data = extract_ecoventure_workbook(FIXTURE.read_bytes())
        prov = data.get("contract_provenance") or {}
        self.assertEqual(prov.get("contract_version"), ENGINE_SUPPORTED_CONTRACT_VERSION)
        self.assertIn("workbook_template_id", prov)

    def test_contract_version_mismatch_warns(self) -> None:
        from unittest.mock import patch

        with patch(
            "ecoventure_workbook.get_cell_contract_version",
            return_value="9.9.9",
        ):
            warnings = contract_ingest_warnings()
        self.assertTrue(warnings)
        self.assertIn("9.9.9", warnings[0])

    def test_maybe_merge_from_folder(self) -> None:
        if not BASE.is_file():
            self.skipTest("phase1_alberta_data.xlsx missing")
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            shutil.copy(FIXTURE, folder / ECOVENTURE_FOLDER_FILENAME)
            merged, warnings = maybe_merge_ecoventure_from_folder(
                BASE.read_bytes(), folder
            )
            self.assertFalse(warnings)
            self.assertGreater(len(merged), len(BASE.read_bytes()))

    def test_merge_into_engine_excel(self) -> None:
        if not BASE.is_file():
            self.skipTest("phase1_alberta_data.xlsx missing")
        merged = merge_into_engine_excel(BASE.read_bytes(), FIXTURE.read_bytes())
        self.assertGreater(len(merged), 1000)
        import pandas as pd
        from io import BytesIO

        sheets = pd.read_excel(BytesIO(merged), sheet_name=None)
        self.assertIn("DwdaCalculations", sheets)
        self.assertIn("DrillingWaste", sheets)


if __name__ == "__main__":
    unittest.main()
