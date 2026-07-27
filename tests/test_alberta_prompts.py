"""Tests for Alberta prompt library loader."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class AlbertaPromptLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        from ai.prompts import clear_prompt_library_cache

        clear_prompt_library_cache()

    def test_library_file_exists_and_loads(self) -> None:
        from ai.prompts import LIBRARY_PATH, load_prompt_library

        self.assertTrue(LIBRARY_PATH.is_file())
        lib = load_prompt_library()
        self.assertEqual(lib.get("jurisdiction"), "Alberta")
        self.assertIn("profiles", lib)
        self.assertIn("agent_tasks", lib)

    def test_all_expected_profiles(self) -> None:
        from ai.prompts import list_profile_keys

        keys = set(list_profile_keys())
        for expected in (
            "phase1_alberta",
            "phase2_esa",
            "groundwater_monitoring",
            "reclamation_certificate",
            "phase3_remediation",
            "template_driven",
        ):
            self.assertIn(expected, keys)

    def test_devon_maps_to_phase1(self) -> None:
        from ai.prompts import profile_key_for_report_type, system_prompt_for

        self.assertEqual(profile_key_for_report_type("phase1_devon"), "phase1_alberta")
        text = system_prompt_for("phase1_devon")
        self.assertIn("Ecoventure", text)
        self.assertIn("Phase I", text)

    def test_section_instruction_phase2(self) -> None:
        from ai.prompts import section_instruction, sections_for_report_type

        sections = sections_for_report_type("phase2_esa")
        self.assertIn("executive_summary", sections)
        inst = section_instruction("phase2_esa", "executive_summary")
        self.assertIn("exceedance", inst.lower())

    def test_agent_brief_and_tasks(self) -> None:
        from ai.prompts import agent_brief, agent_task_prompt, list_agent_task_ids

        brief = agent_brief("groundwater_monitoring")
        self.assertTrue(brief)
        self.assertIn("Groundwater", brief)
        tasks = list_agent_task_ids()
        self.assertIn("folder_inventory", tasks)
        self.assertIn("render_gate", tasks)
        self.assertIn("project folder", agent_task_prompt("folder_inventory").lower())

    def test_narrative_sections_use_library(self) -> None:
        from ai.narrative import sections_for_phase

        gw = sections_for_phase("Groundwater", "groundwater_monitoring")
        self.assertEqual(gw[0], "executive_summary")
        self.assertIn("hydrogeologic_setting", gw)
        p3 = sections_for_phase("Phase 3", "phase3_remediation")
        self.assertIn("conclusions_limitations", p3)

    def test_strict_load_ok(self) -> None:
        from ai.prompts import load_prompt_library

        lib = load_prompt_library(strict=True)
        self.assertIn("phase1_alberta", lib["profiles"])

    def test_validate_rejects_bad_payload(self) -> None:
        from ai.prompts import PromptLibraryError, validate_library_payload

        with self.assertRaises(PromptLibraryError):
            validate_library_payload({"version": "1"})
        with self.assertRaises(PromptLibraryError):
            validate_library_payload(
                {
                    "version": "1",
                    "profiles": {
                        "bad profile!": {
                            "label": "x",
                            "report_types": [],
                            "sections": [],
                            "system_addon": "",
                        }
                    },
                }
            )

    def test_invalid_task_id_returns_empty(self) -> None:
        from ai.prompts import agent_task_prompt

        self.assertEqual(agent_task_prompt("../etc/passwd"), "")
        self.assertEqual(agent_task_prompt(""), "")

    def test_corrupt_library_soft_fallback(self) -> None:
        from ai import prompts as prompts_mod

        prompts_mod.clear_prompt_library_cache()
        real = prompts_mod.LIBRARY_PATH
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not-json", encoding="utf-8")
            prompts_mod.LIBRARY_PATH = bad
            try:
                prompts_mod.clear_prompt_library_cache()
                self.assertEqual(prompts_mod.load_prompt_library(), {})
                with self.assertRaises(prompts_mod.PromptLibraryError):
                    prompts_mod.load_prompt_library(strict=True)
            finally:
                prompts_mod.LIBRARY_PATH = real
                prompts_mod.clear_prompt_library_cache()


if __name__ == "__main__":
    unittest.main()
