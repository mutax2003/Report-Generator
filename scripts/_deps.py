"""Friendly exit when project dependencies are not installed."""

from __future__ import annotations

import sys
from pathlib import Path


def require_project_deps(root: Path) -> None:
    try:
        import pandas  # noqa: F401
    except ImportError:
        venv_py = root / ".venv" / "Scripts" / "python.exe"
        print("Missing Python packages (pandas, etc.).", file=sys.stderr)
        print("From the project folder:", file=sys.stderr)
        print('  .\\.venv\\Scripts\\Activate.ps1', file=sys.stderr)
        print("  pip install -r requirements.txt", file=sys.stderr)
        if venv_py.is_file():
            print(f"Or run with venv Python:", file=sys.stderr)
            print(f'  "{venv_py}" scripts\\...', file=sys.stderr)
        raise SystemExit(1) from None
