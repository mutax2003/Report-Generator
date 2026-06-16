"""
Optional Playwright browser smoke for Streamlit (local desktop).

Requires:
  pip install playwright
  playwright install chromium

CI uses tests/test_streamlit_smoke.py (AppTest) instead — no browser download.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "http://localhost:8501"


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "playwright not installed — run: pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        return 1

    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true"],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(8)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(URL, wait_until="networkidle", timeout=60_000)
            page.get_by_text("How do you want to generate your report?").wait_for(timeout=30_000)
            page.get_by_role("button", name="Use Excel + template workflow").click()
            page.get_by_text("Excel + Word template").wait_for(timeout=30_000)
            page.get_by_role("button", name="Change").click()
            page.get_by_text("How do you want to generate your report?").wait_for(timeout=30_000)
            page.get_by_role("button", name="Use project folder workflow").click()
            folder = str((ROOT / "user_test" / "phase2_alberta").resolve())
            page.get_by_label("Project folder path").fill(folder)
            page.get_by_role("button", name="Load folder").click()
            page.get_by_text("Loaded files").wait_for(timeout=30_000)
            browser.close()
        print("Playwright smoke OK")
        return 0
    except Exception as exc:
        print(f"Playwright smoke failed: {exc}", file=sys.stderr)
        return 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
