"""
Create a ready-to-use Alberta Phase II ESA project folder under user_test/.

  python scripts/create_phase2_project_folder.py
  python scripts/create_phase2_project_folder.py --folder C:\\Projects\\phase2_demo
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_FOLDER = ROOT / "user_test" / "phase2_alberta"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create Alberta Phase II ESA test project folder with sample Excel + template.",
    )
    parser.add_argument(
        "--folder",
        type=Path,
        default=DEFAULT_FOLDER,
        help=f"Destination folder (default: {DEFAULT_FOLDER})",
    )
    args = parser.parse_args()

    samples_script = ROOT / "scripts" / "create_samples.py"
    if samples_script.is_file():
        subprocess.run([sys.executable, str(samples_script)], check=True, cwd=str(ROOT))

    from project_folder import init_sample_project_folder, resolve_project_folder

    folder = init_sample_project_folder(
        args.folder,
        source_user_test=False,
        profile="phase2_esa",
    )
    resolved = resolve_project_folder(folder)
    print(f"Created Phase II test folder: {folder}")
    print(f"  Excel:    {resolved.excel_path.name}")
    print(f"  Template: {resolved.template_path.name}")
    print(f"  Profile:  {resolved.meta.get('report_type')}")
    print(f"  Source PDFs: {len(resolved.inventory.source_pdfs)}")
    print()
    print("Streamlit: Project folder + AI -> Browse -> select this folder")
    print(
        f"CLI render: python scripts\\ingest_project_folder.py "
        f'--folder "{folder}" --render'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
