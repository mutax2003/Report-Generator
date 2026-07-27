"""
Agent-driven project folder report orchestrator (Cursor / Codex / Claude Cowork).

Wraps project_folder inventory/enrich/render. Does not call LLMs inside ReportEngine.
Apply drafts into Excel only with explicit --mode apply-drafts (or --apply-drafts with full).

  .\\.venv\\Scripts\\python.exe scripts\\agent_folder_report.py --folder <path> --mode inventory
  .\\.venv\\Scripts\\python.exe scripts\\agent_folder_report.py --folder <path> --mode enrich --no-llm
  .\\.venv\\Scripts\\python.exe scripts\\agent_folder_report.py --folder <path> --mode apply-drafts
  .\\.venv\\Scripts\\python.exe scripts\\agent_folder_report.py --folder <path> --mode render --package
  .\\.venv\\Scripts\\python.exe scripts\\agent_folder_report.py --folder <path> --mode full --package
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from project_folder import (  # noqa: E402
    enrich_project_folder,
    render_project_folder,
    resolve_project_folder,
)

MODES = ("inventory", "enrich", "apply-drafts", "render", "full")
MAX_FOLDER_PATH_LEN = 480
EXCEL_SUFFIXES = {".xlsx"}
TEMPLATE_SUFFIXES = {".docx", ".pdf"}


def _print_next(msg: str) -> None:
    print(f"NEXT: {msg}")


def _err(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


def _hosted_mode_blocked() -> bool:
    from security import folder_workflow_disabled

    return folder_workflow_disabled()


def _normalize_folder(folder: Path) -> Path:
    try:
        path = folder.expanduser().resolve(strict=False)
    except (OSError, RuntimeError) as e:
        raise ValueError(f"Cannot resolve folder path: {e}") from e
    text = str(path)
    if len(text) > MAX_FOLDER_PATH_LEN:
        raise ValueError(f"Folder path too long (max {MAX_FOLDER_PATH_LEN} characters).")
    if not path.exists():
        raise FileNotFoundError(f"Project folder not found: {path}")
    if not path.is_dir():
        raise ValueError(f"Not a directory: {path}")
    return path


def _validate_core_files(resolved: object) -> None:
    excel = resolved.excel_path  # type: ignore[attr-defined]
    template = resolved.template_path  # type: ignore[attr-defined]
    if not excel.is_file():
        raise FileNotFoundError(f"Missing Excel at {excel}")
    if excel.suffix.lower() not in EXCEL_SUFFIXES:
        raise ValueError(f"Excel must be .xlsx (got {excel.suffix!r})")
    if not template.is_file():
        raise FileNotFoundError(f"Missing template at {template}")
    if template.suffix.lower() not in TEMPLATE_SUFFIXES:
        raise ValueError(f"Template must be .docx or .pdf (got {template.suffix!r})")
    from security import MAX_EXCEL_BYTES, MAX_TEMPLATE_BYTES, SecurityError, validate_excel_upload

    try:
        excel_bytes = excel.read_bytes()
        validate_excel_upload(excel_bytes, filename=excel.name)
    except SecurityError as e:
        raise ValueError(f"Excel failed security checks: {e}") from e
    except OSError as e:
        raise ValueError(f"Cannot read Excel: {e}") from e
    try:
        tsize = template.stat().st_size
    except OSError as e:
        raise ValueError(f"Cannot stat template: {e}") from e
    if tsize <= 0:
        raise ValueError("Template file is empty.")
    if tsize > MAX_TEMPLATE_BYTES:
        raise ValueError(
            f"Template too large ({tsize} bytes; max {MAX_TEMPLATE_BYTES})."
        )
    # Silence unused import warning if MAX_EXCEL_BYTES only used via validate
    _ = MAX_EXCEL_BYTES


def _load_draft_fields(drafts: Path) -> dict[str, str]:
    from ai.apply_drafts import load_field_suggestions, load_narratives_payload

    fields: dict[str, str] = {}
    narr_path = drafts / "narratives.json"
    if narr_path.is_file():
        try:
            fields.update(load_narratives_payload(narr_path))
        except (OSError, UnicodeError, ValueError, TypeError) as e:
            raise ValueError(f"Invalid narratives.json: {e}") from e
    sug_path = drafts / "excel_field_suggestions.json"
    if sug_path.is_file():
        try:
            fields.update(load_field_suggestions(sug_path))
        except (OSError, UnicodeError, ValueError, TypeError) as e:
            raise ValueError(f"Invalid excel_field_suggestions.json: {e}") from e
    return fields


def _atomic_write_bytes(
    path: Path,
    data: bytes,
    *,
    max_bytes: int | None = None,
    root: Path | None = None,
) -> None:
    from project_folder import ensure_under_project_root
    from security import MAX_EXCEL_BYTES

    cap = max_bytes if max_bytes is not None else MAX_EXCEL_BYTES
    if len(data) > cap:
        raise ValueError(f"Write rejected: payload too large ({len(data)} > {cap} bytes)")
    if root is not None:
        path = ensure_under_project_root(root, path, allow_missing=True)
        ensure_under_project_root(root, path.parent, allow_missing=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.stem}_",
        suffix=path.suffix + ".tmp",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def apply_drafts_to_excel(
    resolved: object,
    *,
    overwrite_filled: bool = False,
    backup: bool = True,
) -> tuple[list[str], list[str]]:
    """Patch project_data.xlsx from ai_drafts narratives + field suggestions."""
    if _hosted_mode_blocked():
        raise PermissionError(
            "Apply-drafts is disabled when ESA_HOSTED_MODE / "
            "ESA_DISABLE_FOLDER_WORKFLOW is set."
        )
    from ai.apply_drafts import patch_project_data_fields
    from project_folder import ensure_under_project_root
    from security import SecurityError, validate_excel_upload

    excel_path = Path(resolved.excel_path)  # type: ignore[attr-defined]
    drafts = Path(resolved.ai_drafts_dir)  # type: ignore[attr-defined]
    try:
        root = Path(os.fspath(resolved.root))  # type: ignore[attr-defined]
    except (TypeError, AttributeError, ValueError):
        root = excel_path.resolve().parent
    drafts = ensure_under_project_root(root, drafts)
    excel_path = ensure_under_project_root(root, excel_path)
    if not drafts.is_dir():
        print("No ai_drafts/ directory; nothing to apply.")
        return [], []
    fields = _load_draft_fields(drafts)
    if not fields:
        print("No narratives.json or excel_field_suggestions.json fields to apply.")
        return [], []
    try:
        excel_bytes = None
        read_core = getattr(resolved, "read_core_files", None)
        if callable(read_core):
            try:
                core = read_core()
                if (
                    isinstance(core, (tuple, list))
                    and len(core) >= 1
                    and isinstance(core[0], (bytes, bytearray))
                ):
                    excel_bytes = bytes(core[0])
            except (TypeError, OSError, AttributeError, ValueError):
                excel_bytes = None
        if excel_bytes is None:
            excel_bytes = excel_path.read_bytes()
        validate_excel_upload(excel_bytes, filename=excel_path.name)
    except SecurityError as e:
        raise ValueError(f"Excel failed security checks before apply: {e}") from e
    except OSError as e:
        raise ValueError(f"Cannot read Excel for apply: {e}") from e
    new_bytes, applied, skipped = patch_project_data_fields(
        excel_bytes,
        fields,
        overwrite_filled=overwrite_filled,
    )
    if not applied:
        print("No fields applied (all skipped or empty).")
        if skipped:
            print(f"Skipped filled field(s): {', '.join(skipped)}")
        return applied, skipped
    try:
        validate_excel_upload(new_bytes, filename=excel_path.name)
    except SecurityError as e:
        raise ValueError(f"Patched Excel failed security checks: {e}") from e
    if backup:
        bak = drafts / f"{excel_path.stem}_pre_apply_backup.xlsx"
        try:
            _atomic_write_bytes(bak, excel_bytes, root=root)
            print(f"Backup written: {bak}")
        except OSError as e:
            raise ValueError(f"Could not write Excel backup before apply: {e}") from e
    try:
        _atomic_write_bytes(excel_path, new_bytes, root=root)
        invalidate = getattr(resolved, "invalidate_core_files", None)
        if callable(invalidate):
            try:
                invalidate()
            except (TypeError, AttributeError, OSError):
                pass
    except OSError as e:
        raise ValueError(f"Could not write patched Excel: {e}") from e
    print(f"Applied {len(applied)} field(s) to {excel_path.name}: {', '.join(applied)}")
    if skipped:
        print(f"Skipped filled field(s): {', '.join(skipped)}")
    return applied, skipped


def run_mode(
    folder: Path,
    mode: str,
    *,
    use_llm: bool = False,
    package: bool = False,
    apply_drafts: bool = False,
    overwrite_filled: bool = False,
    init_dirs: bool = False,
) -> int:
    """Run one orchestrator mode. Returns process exit code."""
    if _hosted_mode_blocked():
        _err(
            "Project folder agent path is disabled when ESA_HOSTED_MODE / "
            "ESA_DISABLE_FOLDER_WORKFLOW is set (use Excel + template upload on Cloud)."
        )
        return 2

    if mode not in MODES:
        _err(f"Unknown mode {mode!r}. Choose from: {', '.join(MODES)}")
        return 1

    try:
        folder = _normalize_folder(folder)
        resolved = resolve_project_folder(folder, create_subdirs=init_dirs)
        _validate_core_files(resolved)
    except (FileNotFoundError, ValueError, OSError) as e:
        _err(str(e))
        return 1

    try:
        if mode == "inventory":
            enrich_project_folder(resolved, use_llm=use_llm, modes=("inventory",))
            print(f"Wrote inventory + preflight to {resolved.ai_drafts_dir}")
            _print_next(
                "Review ai_drafts/, then --mode enrich and/or --mode render --package"
            )
            return 0

        if mode == "enrich":
            paths = enrich_project_folder(
                resolved,
                use_llm=use_llm,
                modes=("inventory", "source-ingest", "narratives", "appendix-classify"),
            )
            print(f"Enrich wrote {len(paths)} file(s) to {resolved.ai_drafts_dir}")
            for p in paths:
                print(f"  - {p.name}")
            _print_next(
                "Review drafts. To patch Excel: --mode apply-drafts. "
                "Then --mode render --package"
            )
            return 0

        if mode == "apply-drafts":
            apply_drafts_to_excel(resolved, overwrite_filled=overwrite_filled)
            _print_next("Run --mode render --package after confirming Excel")
            return 0

        if mode == "render":
            outputs = render_project_folder(resolved, package=package)
            print(f"Rendered: {outputs['docx']}")
            print(f"Manifest: {outputs['manifest']}")
            if "package" in outputs:
                print(f"Package: {outputs['package']}")
            if outputs.get("warnings"):
                print(f"Warnings: {outputs['warnings']}")
            _print_next("QP review required before client delivery")
            return 0

        if mode == "full":
            enrich_project_folder(resolved, use_llm=use_llm, modes=("inventory",))
            print(f"Inventory done → {resolved.ai_drafts_dir}")
            paths = enrich_project_folder(
                resolved,
                use_llm=use_llm,
                modes=("source-ingest", "narratives", "appendix-classify"),
            )
            print(f"Enrich wrote {len(paths)} file(s)")
            if apply_drafts:
                apply_drafts_to_excel(resolved, overwrite_filled=overwrite_filled)
            else:
                print(
                    "Skipping Excel Apply (pass --apply-drafts to patch from ai_drafts/). "
                    "Render uses current project_data.xlsx."
                )
            outputs = render_project_folder(resolved, package=package)
            print(f"Rendered: {outputs['docx']}")
            print(f"Manifest: {outputs['manifest']}")
            if "package" in outputs:
                print(f"Package: {outputs['package']}")
            _print_next("QP review required before client delivery")
            return 0
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as e:
        _err(f"{mode} failed: {e}")
        return 1
    except Exception as e:  # noqa: BLE001 — last-resort CLI boundary
        _err(f"{mode} failed unexpectedly: {type(e).__name__}: {e}")
        return 1

    _err(f"Unknown mode {mode!r}")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Agent folder report: inventory / enrich / apply-drafts / render "
            "for Cursor, Codex, or Claude Cowork (see docs/25-agent-folder-report.md)."
        ),
    )
    parser.add_argument(
        "--folder",
        type=Path,
        required=True,
        help="Path to project folder (docs/22-project-folder-workflow.md)",
    )
    parser.add_argument(
        "--mode",
        choices=MODES,
        required=True,
        help="Orchestrator step (full = inventory → enrich → optional apply → render)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Offline heuristics only for enrich (default behavior; kept for CLI symmetry)",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Allow Gemini/Ollama during enrich (default is offline heuristics)",
    )
    parser.add_argument(
        "--package",
        action="store_true",
        help="Include deliverable package zip when rendering",
    )
    parser.add_argument(
        "--apply-drafts",
        action="store_true",
        help="With --mode full: patch Excel from ai_drafts before render",
    )
    parser.add_argument(
        "--overwrite-filled",
        action="store_true",
        help="When applying drafts, overwrite non-empty ProjectData cells",
    )
    parser.add_argument(
        "--init-dirs",
        action="store_true",
        help="Create missing subfolders (source, ai_drafts, delivered, ...)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        code = e.code
        return int(code) if isinstance(code, int) else 1
    use_llm = bool(args.llm) and not bool(args.no_llm)
    return run_mode(
        args.folder,
        args.mode,
        use_llm=use_llm,
        package=args.package,
        apply_drafts=args.apply_drafts,
        overwrite_filled=args.overwrite_filled,
        init_dirs=args.init_dirs,
    )


if __name__ == "__main__":
    raise SystemExit(main())
