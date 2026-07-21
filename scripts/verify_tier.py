"""
Run verification tiers for Cursor multi-agent workflow (see AGENTS.md).

  python scripts/verify_tier.py --tier unit
  python scripts/verify_tier.py --tier ux
  python scripts/verify_tier.py --tier profile --playbook b
  python scripts/verify_tier.py --tier release
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PLAYBOOK_E2E: dict[str, list[str]] = {
    "a": [],
    "b": ["scripts/phase1_alberta_e2e.py"],
    "c": ["scripts/dwda_workflow_e2e.py"],
    "d": ["scripts/tag_production_template.py"],
    "e": [],
}

RELEASE_STEPS: list[str | list[str]] = [
    ["scripts/count_tests.py"],
    ["scripts/build_help.py"],
    [
        "-m",
        "ruff",
        "check",
        "esa_*.py",
        "audit_trail.py",
        "qp_signature.py",
        "records_retention.py",
        "job_queue.py",
        "automate/multipart.py",
        "automate/http_server.py",
        "render_service.py",
        "ui/helpers.py",
    ],
    [
        "-m",
        "ruff",
        "format",
        "--check",
        "esa_*.py",
        "audit_trail.py",
        "qp_signature.py",
        "records_retention.py",
        "job_queue.py",
        "automate/multipart.py",
        "automate/http_server.py",
        "render_service.py",
        "ui/helpers.py",
    ],
    [
        "-m",
        "mypy",
        "--follow-imports=skip",
        "esa_logging.py",
        "esa_auth.py",
        "esa_tenant.py",
        "esa_rate_limit.py",
        "esa_observability.py",
        "audit_trail.py",
        "qp_signature.py",
        "records_retention.py",
        "job_queue.py",
        "automate/multipart.py",
    ],
    ["scripts/validation_evidence.py"],
    ["scripts/create_samples.py"],
    ["scripts/create_appendix_templates.py"],
    ["scripts/tag_production_template.py"],
    ["-m", "unittest", "discover", "-s", "tests", "-v"],
    ["scripts/streamlit_smoke.py"],
    ["scripts/render_cli.py"],
    ["scripts/phase1_package_smoke.py"],
    ["scripts/production_e2e.py"],
    ["scripts/phase1_alberta_e2e.py"],
    ["scripts/phase2_alberta_e2e.py"],
    ["scripts/groundwater_e2e.py"],
    ["scripts/create_phase2_project_folder.py"],
    [
        "scripts/ingest_project_folder.py",
        "--folder",
        "user_test/phase2_alberta",
        "--render",
        "--no-llm",
    ],
    ["scripts/test_with_your_documents.py"],
    ["scripts/create_ecoventure_dwda_fixture.py"],
    ["scripts/dwda_workflow_e2e.py"],
    ["scripts/phase3_remediation_e2e.py"],
    ["scripts/reclamation_e2e.py"],
    ["scripts/health_check.py"],
]


def _run_step(label: str, args: list[str]) -> int:
    cmd = [sys.executable, *[str(a) for a in args]]
    rel = " ".join(str(a) for a in args)
    print(f"\n--- {label}: python {rel} ---")
    rc = subprocess.call(cmd, cwd=str(ROOT))
    if rc != 0:
        print(f"FAIL ({rc}): {label}")
    else:
        print(f"PASS: {label}")
    return rc


def _run_script(path: str, *, label: str | None = None) -> int:
    return _run_step(label or path, [path])


def _tier_unit() -> int:
    if _run_script("scripts/count_tests.py") != 0:
        return 1
    return _run_step("unittest discover", ["-m", "unittest", "discover", "-s", "tests", "-v"])


def _tier_ux() -> int:
    if _run_script("scripts/build_help.py") != 0:
        return 1
    rc = _tier_unit()
    if rc != 0:
        return rc
    return _run_script("scripts/streamlit_smoke.py")


def _tier_profile(playbook: str | None) -> int:
    rc = _tier_ux()
    if rc != 0:
        return rc
    key = (playbook or "b").lower()
    if key not in PLAYBOOK_E2E:
        print(f"Unknown playbook {playbook!r}; use a–e")
        return 2
    for script in PLAYBOOK_E2E[key]:
        if _run_script(script) != 0:
            return 1
    if key in ("b", "c", "d"):
        return _run_script("scripts/health_check.py")
    return 0


def _tier_release() -> int:
    for step in RELEASE_STEPS:
        args = step if isinstance(step, list) else [step]
        label = args[0] if args else "step"
        if _run_step(label, args) != 0:
            return 1
    return 0


def run_tier(tier: str, playbook: str | None = None) -> int:
    """Dispatch verification tier (testable entry point)."""
    if tier == "quick":
        print("Quick tier: docs-only — no commands run.")
        return 0
    if tier == "unit":
        return _tier_unit()
    if tier == "ux":
        return _tier_ux()
    if tier == "profile":
        return _tier_profile(playbook)
    return _tier_release()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ESA verification tier (multi-agent workflow).")
    parser.add_argument(
        "--tier",
        choices=("quick", "unit", "ux", "profile", "release"),
        required=True,
        help="Verification tier (AGENTS.md)",
    )
    parser.add_argument(
        "--playbook",
        choices=tuple(PLAYBOOK_E2E),
        help="Playbook a–e (profile tier: extra E2E scripts)",
    )
    args = parser.parse_args()
    return run_tier(args.tier, args.playbook)


if __name__ == "__main__":
    raise SystemExit(main())
