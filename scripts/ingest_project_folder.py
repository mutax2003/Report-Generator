"""
Ingest a local project folder: inventory, AI enrich, render to delivered/.

  python scripts/ingest_project_folder.py --folder C:\\Projects\\260109R --ai enrich
  python scripts/ingest_project_folder.py --folder C:\\Projects\\260109R --render --package
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from project_folder import (  # noqa: E402
    SAMPLE_PROFILES,
    enrich_project_folder,
    extract_lab_pdf_to_drafts,
    init_sample_project_folder,
    render_project_folder,
    resolve_project_folder,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Project folder ingest: AI enrich and/or render ESA report.",
    )
    parser.add_argument(
        "--folder",
        type=Path,
        help="Path to project folder (see docs/22-project-folder-workflow.md)",
    )
    parser.add_argument(
        "--init-sample",
        action="store_true",
        help="Create sample folder layout (requires --folder)",
    )
    parser.add_argument(
        "--profile",
        choices=tuple(SAMPLE_PROFILES.keys()),
        default="phase1_alberta",
        help="Sample profile when using --init-sample (default: phase1_alberta)",
    )
    parser.add_argument(
        "--init-dirs",
        action="store_true",
        help="Create missing subfolders (source, ai_drafts, delivered, ...)",
    )
    parser.add_argument(
        "--ai",
        choices=(
            "inventory",
            "source-ingest",
            "narratives",
            "enrich",
            "lab-pdf",
            "appendix-classify",
            "apec-extract",
        ),
        help="Run AI advisory step(s); outputs go to ai_drafts/",
    )
    parser.add_argument(
        "--lab-pdf",
        type=Path,
        help="Lab COA PDF path (with --ai lab-pdf; relative to folder if not absolute)",
    )
    parser.add_argument(
        "--write-lab-excel",
        action="store_true",
        help="Write lab merge backup xlsx under ai_drafts/ (does not overwrite project_data.xlsx)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Use offline heuristics only for AI steps",
    )
    parser.add_argument(
        "--render",
        action="store_true",
        help="Render report to delivered/",
    )
    parser.add_argument(
        "--package",
        action="store_true",
        help="Include deliverable package zip when rendering",
    )
    args = parser.parse_args()

    if args.init_sample:
        if not args.folder:
            print("--init-sample requires --folder", file=sys.stderr)
            return 1
        path = init_sample_project_folder(args.folder, profile=args.profile)
        print(f"Created sample project folder ({args.profile}): {path}")
        if not args.ai and not args.render:
            return 0

    if not args.folder:
        parser.print_help()
        return 1

    try:
        resolved = resolve_project_folder(args.folder, create_subdirs=args.init_dirs)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.init_dirs and not args.ai and not args.render:
        from project_folder import inventory_markdown

        print(inventory_markdown(resolved))
        return 0

    use_llm = not args.no_llm

    if args.ai == "inventory":
        enrich_project_folder(resolved, use_llm=use_llm, modes=("inventory",))
        print(f"Wrote inventory + preflight to {resolved.ai_drafts_dir}")
    elif args.ai == "narratives":
        path = enrich_project_folder(resolved, use_llm=use_llm, modes=("narratives",))[0]
        print(f"Wrote narratives: {path}")
    elif args.ai == "source-ingest":
        from project_folder import source_ingest_for_folder

        paths = source_ingest_for_folder(resolved, use_llm=use_llm)
        if not paths:
            print("Note: no PDF files in source/", file=sys.stderr)
            return 0
        print(f"Source ingest wrote {len(paths)} file(s) to {resolved.ai_drafts_dir}")
        for p in paths:
            print(f"  - {p.name}")
    elif args.ai == "enrich":
        paths = enrich_project_folder(
            resolved,
            use_llm=use_llm,
            modes=("inventory", "source-ingest", "narratives", "appendix-classify"),
        )
        print(f"AI enrich wrote {len(paths)} file(s) to {resolved.ai_drafts_dir}")
        for p in paths:
            print(f"  - {p.name}")
    elif args.ai == "lab-pdf":
        if not args.lab_pdf:
            print("--ai lab-pdf requires --lab-pdf", file=sys.stderr)
            return 1
        lab = args.lab_pdf
        if not lab.is_absolute():
            lab = resolved.root / lab
        path = extract_lab_pdf_to_drafts(
            resolved,
            lab,
            use_llm=use_llm,
            write_excel=args.write_lab_excel,
        )
        print(f"Wrote lab extract: {path}")
    elif args.ai == "appendix-classify":
        from project_folder import classify_appendices_for_folder

        path = classify_appendices_for_folder(resolved, use_llm=use_llm)
        if path is None:
            print("Note: no PDF files in source/ or appendices/", file=sys.stderr)
            return 0
        print(f"Wrote appendix classifications: {path}")
    elif args.ai == "apec-extract":
        from project_folder import apec_extract_for_folder

        paths = apec_extract_for_folder(resolved, use_llm=use_llm)
        if not paths:
            print("Note: no APEC candidates from source/ PDFs", file=sys.stderr)
            return 0
        print(f"APEC extract wrote {len(paths)} file(s) to {resolved.ai_drafts_dir}")
        for p in paths:
            print(f"  - {p.name}")

    if args.render:
        outputs = render_project_folder(resolved, package=args.package)
        print(f"Rendered: {outputs['docx']}")
        print(f"Manifest: {outputs['manifest']}")
        if "package" in outputs:
            print(f"Package: {outputs['package']}")
        if "warnings" in outputs:
            print(f"Warnings: {outputs['warnings']}")

    if not args.ai and not args.render and not args.init_sample:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
