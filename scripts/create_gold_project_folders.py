"""
Build gold SharePoint project-folder templates for Alberta Phase I, Phase II, and GW.

  python scripts/create_gold_project_folders.py
  python scripts/create_gold_project_folders.py --dest dist/team-sharepoint/ProjectFolders

Copies profile-specific Excel + Word samples, project.json, and subdirs (source/,
appendices/, ai_drafts/, delivered/). Consultants copy a folder to C:\\Projects\\<id>
and replace demo row 2 data with site-specific values.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GOLD_PROFILES: dict[str, str] = {
    "phase1_alberta": "Phase1_Alberta",
    "phase2_esa": "Phase2_ESA",
    "groundwater_monitoring": "Groundwater_Monitoring",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create gold project-folder templates for SharePoint packaging.",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=ROOT / "dist" / "team-sharepoint" / "ProjectFolders",
        help="Output root (default: dist/team-sharepoint/ProjectFolders)",
    )
    parser.add_argument(
        "--profile",
        choices=[*GOLD_PROFILES.keys(), "all"],
        default="all",
        help="Profile to build (default: all)",
    )
    args = parser.parse_args()

    samples_script = ROOT / "scripts" / "create_samples.py"
    if samples_script.is_file():
        subprocess.run([sys.executable, str(samples_script)], check=True, cwd=str(ROOT))

    from project_folder import init_sample_project_folder, resolve_project_folder

    dest_root = args.dest.expanduser().resolve()
    dest_root.mkdir(parents=True, exist_ok=True)

    profiles = GOLD_PROFILES if args.profile == "all" else {args.profile: GOLD_PROFILES[args.profile]}
    created: list[Path] = []

    for profile_id, folder_name in profiles.items():
        folder = dest_root / folder_name
        if folder.exists():
            import shutil

            shutil.rmtree(folder)
        init_sample_project_folder(folder, source_user_test=False, profile=profile_id)
        resolved = resolve_project_folder(folder)
        howto = folder / "HOWTO-COPY-THIS-FOLDER.txt"
        howto.write_text(
            f"Gold project folder — {folder_name}\n"
            f"{'=' * (24 + len(folder_name))}\n\n"
            "1. Copy this entire folder to C:\\Projects\\<your_project_number>\n"
            f"2. Edit project.json — set project_number, prepared_by, date_of_issue\n"
            f"3. Replace demo data in project_data.xlsx (row 2+) with your site\n"
            "4. Drop reference PDFs in source\\; maps in figures\\\n"
            "5. Desktop: Cursor Pro + Claude Cowork — see Guides/27-cursor-claude-alberta-playbook.md\n\n"
            f"Report profile: {resolved.meta.get('report_type')}\n"
            f"Excel: {resolved.excel_path.name}\n"
            f"Template: {resolved.template_path.name}\n",
            encoding="utf-8",
        )
        created.append(folder)
        print(f"  {folder}")

    print(f"\nCreated {len(created)} gold project folder(s) under {dest_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
