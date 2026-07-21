#!/usr/bin/env python3
"""Pre-commit gate: UX verification tier when Streamlit/UI files are staged."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

UX_PATH_PREFIXES = (
    "app.py",
    "ui/",
    "tests/test_streamlit_smoke.py",
    "tests/test_onboarding.py",
    "tests/test_layout.py",
    "tests/test_workflow_mode.py",
)


def _staged_files() -> list[str]:
    proc = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    return [line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()]


def _needs_ux_tier(staged: list[str]) -> bool:
    for path in staged:
        norm = path.replace("\\", "/")
        for prefix in UX_PATH_PREFIXES:
            if norm == prefix or norm.startswith(prefix):
                return True
    return False


def main() -> int:
    staged = _staged_files()
    if not staged:
        return 0
    if not _needs_ux_tier(staged):
        print("pre-commit: no Streamlit/UI paths staged — skipping UX tier.")
        return 0
    print("pre-commit: Streamlit/UI changes staged — running verify_tier --tier ux")
    return subprocess.call(
        [sys.executable, str(ROOT / "scripts" / "verify_tier.py"), "--tier", "ux"],
        cwd=str(ROOT),
    )


if __name__ == "__main__":
    raise SystemExit(main())
