#!/usr/bin/env python3
"""
Windows deployment launcher for ESA Report Generator (Streamlit).

Looks for runtime\\.venv next to this script or ESA-Report-Generator.exe,
then starts: streamlit run app.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def deploy_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_python(root: Path) -> Path | None:
    for rel in (
        "runtime/.venv/Scripts/python.exe",
        ".venv/Scripts/python.exe",
    ):
        candidate = root / rel.replace("/", os.sep)
        if candidate.is_file():
            return candidate
    return None


def streamlit_command(py: Path, root: Path) -> list[str]:
    streamlit_exe = py.parent / "streamlit.exe"
    if streamlit_exe.is_file():
        base = [str(streamlit_exe)]
    else:
        base = [str(py), "-m", "streamlit"]
    cmd = base + [
        "run",
        str(root / "app.py"),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    port = os.environ.get("ESA_PORT", "").strip()
    if port.isdigit():
        cmd.extend(["--server.port", port])
    if os.environ.get("ESA_BIND_ALL", "").strip().lower() in ("1", "true", "yes"):
        cmd.extend(["--server.address", "0.0.0.0"])
    return cmd


def main() -> int:
    root = deploy_root()
    os.chdir(root)

    if not (root / "app.py").is_file():
        print(f"ERROR: app.py not found in {root}")
        return 1

    py = find_python(root)
    if py is None:
        print(
            "ERROR: Python runtime not found.\n"
            f"  Expected: {root / 'runtime' / '.venv' / 'Scripts' / 'python.exe'}\n"
            "  Run Install-Dependencies.ps1 once in this folder."
        )
        return 1

    print("ESA Report Generator — starting Streamlit…")
    print(f"  Root: {root}")
    print("  Open http://localhost:8501 in your browser.")
    print("  Press Ctrl+C to stop.\n")
    return subprocess.call(streamlit_command(py, root), cwd=str(root))


if __name__ == "__main__":
    raise SystemExit(main())
