"""
Streamlit smoke test (AppTest — no browser required).

  python scripts/streamlit_smoke.py

Optional browser smoke (requires playwright):
  pip install playwright && playwright install chromium
  python scripts/playwright_smoke.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "unittest",
        "tests.test_streamlit_smoke",
        "-v",
    ]
    print("Running Streamlit AppTest smoke...")
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
