"""DWDA / Directive 050 compliance evaluation."""

from __future__ import annotations

import unittest

from dwda_compliance import (
    determine_checklist_scope,
    evaluate_dwda_compliance,
    enrich_dwda_context,
    normalize_compliance_option,
)


class DwdaComplianceTests(unittest.TestCase):
    def test_normalize_option_1(self) -> None:
        self.assertEqual(normalize_compliance_option("Option 1 (AER, 2014)"), "option_1")

    def test_scope_full_when_cuttings_over_50(self) -> None:
        ctx = {
            "aer_waste_compliance_option": "Option 1 (AER, 2014)",
            "cuttings_volume_on_lease_m3": "55",
            "drilling_waste": [
                {
                    "disposal_method": "LWD",
                    "disposal_type": "on-lease",
                    "location": "well centre",
                    "gps_coordinates": "51.0,-114.0",
                }
            ],
        }
        option, scope, cuttings = determine_checklist_scope(ctx)
        self.assertEqual(option, "option_1")
        self.assertEqual(scope, "option_1_full")
        self.assertEqual(cuttings, 55.0)

    def test_scope_minimal_off_lease_low_cuttings(self) -> None:
        ctx = {
            "aer_waste_compliance_option": "Option 1",
            "cuttings_volume_on_lease_m3": "10",
            "drilling_waste": [
                {
                    "disposal_method": "remote haul",
                    "disposal_type": "off-lease",
                    "location": "remote site",
                }
            ],
        }
        _, scope, _ = determine_checklist_scope(ctx)
        self.assertEqual(scope, "option_1_minimal")

    def test_evaluate_flags_missing_notification(self) -> None:
        ctx = {
            "aer_waste_compliance_option": "Option 1 (AER, 2014)",
            "drilling_waste_summary": "Summary text",
            "cuttings_volume_on_lease_m3": "60",
            "drilling_waste": [{"disposal_method": "LWD", "location": "on lease"}],
        }
        result = evaluate_dwda_compliance(ctx, {}, report_type="phase1_alberta")
        assert result is not None
        missing_ids = {ir.item_id for ir in result.required_missing}
        self.assertIn("d050.notification", missing_ids)

    def test_evaluate_with_dwda_checklist_responses(self) -> None:
        ctx = {
            "aer_waste_compliance_option": "Option 1 (AER, 2014)",
            "drilling_waste_summary": "Summary",
            "directive_050_notification_ref": "NOT-123",
            "cuttings_volume_on_lease_m3": "60",
            "dwda_salinity_pathway": "equivalent_salinity",
            "drilling_waste": [
                {
                    "disposal_method": "LWD",
                    "disposal_type": "on-lease",
                    "location": "SW1/4",
                    "gps_coordinates": "51,-114",
                    "sump_depth_m": "2",
                    "cover_depth_m": "1",
                }
            ],
            "dwda_checklist": [
                {"checklist_item_id": "d050.notification", "response": "Yes"},
            ],
        }
        result = evaluate_dwda_compliance(
            ctx,
            {},
            report_type="phase1_alberta",
            appendix_labels_present={"D", "G"},
        )
        assert result is not None
        self.assertGreater(result.satisfied_count, 0)
        self.assertTrue(any(r["item_id"] == "d050.notification" for r in result.checklist_results))

    def test_unknown_location_triggers_phase2_reason(self) -> None:
        ctx = {
            "aer_waste_compliance_option": "Option 1",
            "drilling_waste_summary": "Summary",
            "directive_050_notification_ref": "NOT-1",
            "drilling_waste": [
                {"disposal_type": "unknown", "location": "", "disposal_method": "LWD"}
            ],
        }
        result = evaluate_dwda_compliance(ctx, {}, report_type="phase1_alberta")
        assert result is not None
        self.assertTrue(
            any("unknown" in r.lower() or "location" in r.lower() for r in result.phase2_reasons)
        )

    def test_enrich_dwda_context_adds_summary(self) -> None:
        ctx = {
            "_report_type": "phase1_alberta",
            "aer_waste_compliance_option": "Option 1",
            "drilling_waste_summary": "Summary",
            "directive_050_notification_ref": "NOT-1",
            "drilling_waste": [{"disposal_method": "LWD", "location": "on lease", "gps_coordinates": "x"}],
        }
        out = enrich_dwda_context(ctx, {})
        self.assertIn("dwda_compliance_summary", out)
        self.assertIn("dwda_checklist_results", out)

    def test_enrich_dwda_adds_calc_fields(self) -> None:
        ctx = {
            "_report_type": "phase1_alberta",
            "well_depth_m": 500,
            "aer_waste_compliance_option": "Option 1",
            "drilling_waste_summary": "Summary",
            "directive_050_notification_ref": "NOT-1",
            "drilling_waste": [{"disposal_method": "LWD", "location": "on lease", "gps_coordinates": "x"}],
            "_ecoventure_ingested": {
                "metal_sacks_per_metre": 0.02,
                "salt_sacks_per_m3": 0.05,
                "salt_naoh_equiv_total": 5,
                "salt_waste_volume_m3": 100,
            },
        }
        out = enrich_dwda_context(ctx, {})
        self.assertIn("dwda_calc_summary", out)
        self.assertEqual(out.get("dwda_metal_pass"), "Yes")
        self.assertEqual(out.get("dwda_salt_pass"), "Yes")

    def test_enrich_dwda_skips_recompute_when_labels_unchanged(self) -> None:
        ctx = {
            "_report_type": "phase1_alberta",
            "aer_waste_compliance_option": "Option 1",
            "drilling_waste_summary": "Summary",
            "directive_050_notification_ref": "NOT-1",
            "drilling_waste": [{"disposal_method": "LWD", "location": "on lease", "gps_coordinates": "x"}],
        }
        first = enrich_dwda_context(ctx, {}, appendix_labels_present={"D", "G"})
        cached = first["_dwda_compliance"]
        second = enrich_dwda_context(first, {}, appendix_labels_present={"G", "D"})
        self.assertIs(second["_dwda_compliance"], cached)

    def test_derive_cuttings_from_on_lease_rows(self) -> None:
        from dwda_compliance import derive_cuttings_volume_on_lease_m3

        rows = [
            {
                "volume_m3": "110",
                "disposal_method": "LWD",
                "disposal_type": "on-lease",
                "location": "well centre",
            },
            {"volume_m3": "60", "disposal_type": "off-lease", "location": "remote"},
        ]
        self.assertEqual(derive_cuttings_volume_on_lease_m3(rows), 110.0)

    def test_scope_uses_derived_cuttings_when_projectdata_empty(self) -> None:
        ctx = {
            "aer_waste_compliance_option": "Option 1",
            "drilling_waste": [
                {
                    "volume_m3": "55",
                    "disposal_method": "LWD",
                    "disposal_type": "on-lease",
                    "location": "on lease",
                }
            ],
        }
        _, scope, cuttings = determine_checklist_scope(ctx)
        self.assertEqual(scope, "option_1_full")
        self.assertEqual(cuttings, 55.0)


    def test_qp_markdown_includes_calc_section(self) -> None:
        from dwda_compliance import build_dwda_qp_checklist_markdown

        ctx = {
            "_report_type": "phase1_alberta",
            "well_depth_m": 100,
            "aer_waste_compliance_option": "Option 1",
            "drilling_waste_summary": "S",
            "directive_050_notification_ref": "N-1",
            "drilling_waste": [{"disposal_method": "LWD", "location": "on lease", "gps_coordinates": "x"}],
            "_ecoventure_ingested": {"metal_sacks_per_metre": 0.5},
        }
        out = enrich_dwda_context(ctx, {})
        md = build_dwda_qp_checklist_markdown(
            out["_dwda_compliance"],
            calc_result=out.get("_dwda_calc_result"),
        )
        self.assertIn("## Calculations", md)
        self.assertIn("Metal", md)


if __name__ == "__main__":
    unittest.main()
