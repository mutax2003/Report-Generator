"""DWDA metal, salt, and DST calculation engine."""

from __future__ import annotations

import unittest

from dwda_calculations import (
    calc_dst_chloride_sacks,
    calc_dst_volume_m3,
    calc_metal_sacks_per_metre,
    calc_salt_max_sacks_per_m3,
    calc_salt_naoh_equiv,
    calc_salt_sacks_per_m3,
    evaluate_dwda_calculations,
    load_salt_schema,
)


class DwdaCalculationsTests(unittest.TestCase):
    def test_metal_pass_at_objective(self) -> None:
        spm = calc_metal_sacks_per_metre(33, 500, 3)
        self.assertIsNotNone(spm)
        assert spm is not None
        self.assertAlmostEqual(spm, 0.022, places=4)
        self.assertLessEqual(spm, 0.22)

    def test_metal_fail_above_objective(self) -> None:
        spm = calc_metal_sacks_per_metre(400, 500, 3)
        assert spm is not None
        self.assertGreater(spm, 0.22)

    def test_salt_max_from_well_depth(self) -> None:
        mx = calc_salt_max_sacks_per_m3(500)
        assert mx is not None
        self.assertAlmostEqual(mx, 10.0)

    def test_salt_sacks_per_m3(self) -> None:
        spm = calc_salt_sacks_per_m3(10, 100)
        assert spm is not None
        self.assertAlmostEqual(spm, 0.1)

    def test_salt_schema_additive_factors(self) -> None:
        schema = load_salt_schema()
        additives = {a["name"]: a["naoh_factor"] for a in schema["additives"]}
        self.assertAlmostEqual(additives["Soda Ash"], 0.75)
        self.assertAlmostEqual(additives["Caustic Soda"], 1.0)
        self.assertGreater(len(additives), 10)

    def test_salt_naoh_equiv_multi_additive(self) -> None:
        total = calc_salt_naoh_equiv([(10, 1.0), (20, 0.75)])
        self.assertAlmostEqual(total, 25.0)

    def test_dst_volume_and_chloride(self) -> None:
        vol = calc_dst_volume_m3(76, 10)
        self.assertGreater(vol, 0)
        sacks = calc_dst_chloride_sacks(vol, 215000)
        self.assertGreater(sacks, 0)

    def test_evaluate_from_ingested_context(self) -> None:
        ctx = {
            "well_depth_m": 500,
            "_ecoventure_ingested": {
                "metal_barite_sacks": 40,
                "metal_well_depth_m": 500,
                "metal_mix_ratio": 3,
                "metal_sacks_per_metre": 40 / 1500,
                "salt_naoh_equiv_total": 10,
                "salt_waste_volume_m3": 100,
                "salt_sacks_per_m3": 0.1,
            },
            "aer_waste_compliance_option": "Option 1",
        }
        result = evaluate_dwda_calculations(ctx)
        self.assertTrue(result.metal_pass)
        self.assertTrue(result.salt_pass)
        self.assertIn("Metal", result.summary)

    def test_evaluate_metal_triggers_phase2(self) -> None:
        ctx = {
            "well_depth_m": 100,
            "_ecoventure_ingested": {
                "metal_sacks_per_metre": 0.5,
            },
        }
        result = evaluate_dwda_calculations(ctx)
        self.assertFalse(result.metal_pass)
        self.assertTrue(result.phase2_required)


if __name__ == "__main__":
    unittest.main()
