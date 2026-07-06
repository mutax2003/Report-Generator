"""
Local project folder layout: discover Excel + template, AI enrich, render to delivered/.

See docs/22-project-folder-workflow.md and schemas/project_folder.json.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from report_profile import profile_id_for_phase

from ecoventure_workbook import maybe_merge_ecoventure_from_folder

ROOT = Path(__file__).resolve().parent

EXCEL_CANDIDATES = ("project_data.xlsx", "my_project_data.xlsx")
TEMPLATE_CANDIDATES = ("template.docx", "my_template.docx", "template.pdf")
SUBDIRS = ("source", "figures", "appendices", "ai_drafts", "delivered", "rag")
PROJECT_JSON = "project.json"
META_KEYS = (
    "report_type",
    "report_phase",
    "prepared_by",
    "date_of_issue",
    "template_version",
    "project_number",
    "site_name",
    "uwi",
)

SAMPLE_PROFILES: dict[str, dict[str, str]] = {
    "phase1_alberta": {
        "excel": "phase1_alberta_data.xlsx",
        "template": "phase1_alberta_template.docx",
        "report_type": "phase1_alberta",
        "report_phase": "Phase 1",
        "template_version": "2.1",
    },
    "phase2_esa": {
        "excel": "phase2_alberta_data.xlsx",
        "template": "phase2_alberta_template.docx",
        "report_type": "phase2_esa",
        "report_phase": "Phase 2",
        "template_version": "1.0.0",
    },
}


@dataclass
class ProjectFolderInventory:
    """Scan results for a resolved project folder."""

    excel_path: Path
    template_path: Path
    meta: dict[str, str]
    source_pdfs: list[Path] = field(default_factory=list)
    appendix_pdfs: list[Path] = field(default_factory=list)
    figure_files: list[Path] = field(default_factory=list)
    rag_files: list[Path] = field(default_factory=list)
    missing_subdirs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    project_json: dict[str, str] = field(default_factory=dict)
    pdf_sizes_kb: dict[str, int] = field(default_factory=dict)


@dataclass
class ResolvedProjectFolder:
    root: Path
    inventory: ProjectFolderInventory
    _core_bytes: tuple[bytes, bytes] | None = field(default=None, repr=False)
    _core_sig: tuple[int, int] | None = field(default=None, repr=False)

    def read_core_files(self) -> tuple[bytes, bytes]:
        """Read Excel + template once per instance; share bytes across folders via mtime cache."""
        ep, tp = self.excel_path, self.template_path
        sig = (ep.stat().st_mtime_ns, tp.stat().st_mtime_ns)
        if self._core_bytes is not None and self._core_sig == sig:
            return self._core_bytes
        self._core_bytes = (
            _cached_file_bytes(str(ep.resolve()), sig[0]),
            _cached_file_bytes(str(tp.resolve()), sig[1]),
        )
        self._core_sig = sig
        return self._core_bytes

    def invalidate_core_files(self) -> None:
        """Drop cached bytes after on-disk Excel/template changes."""
        self._core_bytes = None
        self._core_sig = None

    @property
    def excel_path(self) -> Path:
        return self.inventory.excel_path

    @property
    def template_path(self) -> Path:
        return self.inventory.template_path

    @property
    def meta(self) -> dict[str, str]:
        return self.inventory.meta

    @property
    def ai_drafts_dir(self) -> Path:
        return self.root / "ai_drafts"

    @property
    def delivered_dir(self) -> Path:
        return self.root / "delivered"

    @property
    def source_dir(self) -> Path:
        return self.root / "source"

    @property
    def appendices_dir(self) -> Path:
        return self.root / "appendices"

    @property
    def rag_dir(self) -> Path:
        return self.root / "rag"


def _read_project_json(folder: Path) -> dict[str, str]:
    path = folder / PROJECT_JSON
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"Invalid {PROJECT_JSON}: {e}") from e
    if not isinstance(raw, dict):
        raise ValueError(f"{PROJECT_JSON} must be a JSON object")
    return {str(k): str(v) for k, v in raw.items() if v is not None and str(v).strip()}


def _find_file(folder: Path, names: tuple[str, ...], override: str = "") -> Path | None:
    if override:
        p = folder / override
        if p.is_file():
            return p
        raise FileNotFoundError(f"Configured file not found: {p}")
    for name in names:
        p = folder / name
        if p.is_file():
            return p
    return None


def _list_pdfs(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")


def _list_figures(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    exts = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    return sorted(p for p in directory.iterdir() if p.suffix.lower() in exts)


def _list_rag(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.glob("*.txt") if p.is_file())


def build_meta(project_json: dict[str, str]) -> dict[str, str]:
    phase = project_json.get("report_phase", "Phase 1").strip() or "Phase 1"
    meta: dict[str, str] = {
        "report_phase": phase,
        "prepared_by": project_json.get("prepared_by", "").strip() or "Ecoventure QP",
        "date_of_issue": project_json.get("date_of_issue", "").strip() or "2026-06-10",
    }
    rt = project_json.get("report_type", "").strip()
    meta["report_type"] = rt or profile_id_for_phase(phase)
    if tv := project_json.get("template_version", "").strip():
        meta["template_version"] = tv
    return meta


def _pdf_size_map(paths: list[Path]) -> dict[str, int]:
    return {p.name: p.stat().st_size // 1024 for p in paths}


@lru_cache(maxsize=64)
def _cached_pdf_bytes(path_str: str, mtime_ns: int) -> bytes:
    return Path(path_str).read_bytes()


@lru_cache(maxsize=64)
def _cached_file_bytes(path_str: str, mtime_ns: int) -> bytes:
    return Path(path_str).read_bytes()


def _read_pdf_bytes(path: Path) -> bytes:
    return _cached_pdf_bytes(str(path.resolve()), path.stat().st_mtime_ns)


def clear_project_folder_pdf_cache() -> None:
    """Drop cached appendix/source PDF bytes (tests)."""
    _cached_pdf_bytes.cache_clear()


def clear_project_folder_file_cache() -> None:
    """Drop cached Excel/template bytes (tests)."""
    _cached_file_bytes.cache_clear()
    clear_project_folder_pdf_cache()


def resolve_project_folder(folder: Path, *, create_subdirs: bool = False) -> ResolvedProjectFolder:
    """Validate folder layout and resolve Excel + template paths."""
    root = folder.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Project folder not found: {root}")

    project_json = _read_project_json(root)
    excel = _find_file(
        root,
        EXCEL_CANDIDATES,
        project_json.get("excel_filename", "").strip(),
    )
    if excel is None:
        raise FileNotFoundError(
            f"No Excel file in {root}. Expected one of: {', '.join(EXCEL_CANDIDATES)}"
        )
    template = _find_file(
        root,
        TEMPLATE_CANDIDATES,
        project_json.get("template_filename", "").strip(),
    )
    if template is None:
        raise FileNotFoundError(
            f"No template in {root}. Expected one of: {', '.join(TEMPLATE_CANDIDATES)}"
        )

    missing_subdirs: list[str] = []
    for name in SUBDIRS:
        sub = root / name
        if not sub.is_dir():
            missing_subdirs.append(name)
            if create_subdirs:
                sub.mkdir(parents=True, exist_ok=True)

    meta = build_meta(project_json)
    warnings: list[str] = []
    if missing_subdirs and not create_subdirs:
        warnings.append(
            "Optional subfolders missing: "
            + ", ".join(missing_subdirs)
            + " (run with --init-dirs to create)"
        )

    source_pdfs = _list_pdfs(root / "source")
    appendix_pdfs = _list_pdfs(root / "appendices")
    inventory = ProjectFolderInventory(
        excel_path=excel,
        template_path=template,
        meta=meta,
        source_pdfs=source_pdfs,
        appendix_pdfs=appendix_pdfs,
        figure_files=_list_figures(root / "figures"),
        rag_files=_list_rag(root / "rag"),
        missing_subdirs=missing_subdirs,
        warnings=warnings,
        project_json=project_json,
        pdf_sizes_kb=_pdf_size_map(source_pdfs + appendix_pdfs),
    )
    return ResolvedProjectFolder(root=root, inventory=inventory)


def inventory_markdown(resolved: ResolvedProjectFolder) -> str:
    inv = resolved.inventory
    lines = [
        f"# Project folder inventory: {resolved.root.name}",
        "",
        f"- **Excel:** `{inv.excel_path.name}`",
        f"- **Template:** `{inv.template_path.name}`",
        f"- **Profile:** `{inv.meta.get('report_type')}` ({inv.meta.get('report_phase')})",
    ]
    pj = inv.project_json
    if pj:
        for key in ("project_number", "uwi", "site_name"):
            if pj.get(key):
                lines.append(f"- **{key}:** `{pj[key]}`")
    lines.extend(["", "## Source PDFs (run `--ai source-ingest` to extract)"])
    if inv.source_pdfs:
        for p in inv.source_pdfs:
            kb = inv.pdf_sizes_kb.get(p.name, p.stat().st_size // 1024)
            lines.append(f"- `{p.name}` ({kb} KB)")
    else:
        lines.append("- _(none in source/)_")
    lines.extend(["", "## Appendix PDFs (manual upload folder)"])
    if inv.appendix_pdfs:
        for p in inv.appendix_pdfs:
            kb = inv.pdf_sizes_kb.get(p.name, p.stat().st_size // 1024)
            lines.append(f"- `{p.name}` ({kb} KB)")
    else:
        lines.append("- _(none in appendices/)_")
    lines.extend(["", "## Figures"])
    if inv.figure_files:
        for p in inv.figure_files:
            lines.append(f"- `{p.name}`")
    else:
        lines.append("- _(none in figures/)_")
    if inv.rag_files:
        lines.extend(["", "## Project RAG snippets"])
        for p in inv.rag_files:
            lines.append(f"- `{p.name}`")
    if inv.warnings:
        lines.extend(["", "## Warnings"])
        for w in inv.warnings:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def effective_excel_bytes_for_folder(
    resolved: ResolvedProjectFolder,
    excel_bytes: bytes | None = None,
) -> tuple[bytes, list[str]]:
    """Apply optional ecoventure_workbook.xlsx merge from project folder root."""
    raw = excel_bytes if excel_bytes is not None else resolved.read_core_files()[0]
    return maybe_merge_ecoventure_from_folder(raw, resolved.root)


def run_preflight_for_folder(
    resolved: ResolvedProjectFolder,
    *,
    core_files: tuple[bytes, bytes] | None = None,
) -> Any:
    from template_tools import run_preflight

    excel_bytes, template_bytes = core_files or resolved.read_core_files()
    excel_bytes, _ = effective_excel_bytes_for_folder(resolved, excel_bytes)
    return run_preflight(excel_bytes, template_bytes, resolved.meta)


def write_preflight_artifacts(
    resolved: ResolvedProjectFolder,
    preflight: Any,
    *,
    use_llm: bool = False,
) -> list[Path]:
    from template_tools import missing_fields_checklist

    resolved.ai_drafts_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    inv_path = resolved.ai_drafts_dir / "inventory.md"
    inv_path.write_text(inventory_markdown(resolved), encoding="utf-8")
    written.append(inv_path)

    pre_path = resolved.ai_drafts_dir / "preflight_report.md"
    lines = [
        "# Pre-flight report",
        "",
        f"can_generate: **{preflight.can_generate}**",
        "",
    ]
    if preflight.errors:
        lines.append("## Errors")
        for e in preflight.errors:
            lines.append(f"- {e}")
    if preflight.warnings:
        lines.append("## Warnings")
        for w in preflight.warnings[:40]:
            lines.append(f"- {w}")
    if getattr(preflight, "predicted_appendix_labels", None):
        labels = sorted(preflight.predicted_appendix_labels)
        lines.append(f"\nPredicted auto-appendices: **{', '.join(labels)}**")
    src_count = len(resolved.inventory.source_pdfs)
    if src_count:
        lines.append(
            f"\nSource PDFs in folder: **{src_count}** — run source-ingest or "
            "`--ai enrich` to populate `source_summaries.json`."
        )
    pre_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    written.append(pre_path)

    if preflight.coverage and preflight.coverage.missing_in_data:
        miss_path = resolved.ai_drafts_dir / "missing_excel_columns.txt"
        miss_path.write_text(
            missing_fields_checklist(
                preflight.coverage,
                report_type=resolved.meta.get("report_type", "phase1_alberta"),
            ),
            encoding="utf-8",
        )
        written.append(miss_path)

    from ai.copilot import explain_preflight

    advice, _audit = explain_preflight(
        preflight,
        resolved.meta,
        use_llm=use_llm,
    )
    copilot_path = resolved.ai_drafts_dir / "copilot_advice.md"
    copilot_lines = [f"# {advice.summary}", ""]
    if advice.steps:
        copilot_lines.append("## Steps")
        for i, step in enumerate(advice.steps, 1):
            copilot_lines.append(f"{i}. {step}")
    if advice.excel_columns_to_add:
        copilot_lines.append("\n## Excel columns to add")
        for col in advice.excel_columns_to_add:
            copilot_lines.append(f"- `{col}`")
    copilot_path.write_text("\n".join(copilot_lines) + "\n", encoding="utf-8")
    written.append(copilot_path)

    return written


def source_ingest_for_folder(
    resolved: ResolvedProjectFolder,
    *,
    use_llm: bool = True,
) -> list[Path]:
    from ai.source_ingest import ingest_source_pdfs

    pdfs = list(resolved.inventory.source_pdfs)
    if not pdfs:
        return []
    rag_dir = resolved.root / "rag"
    rag_dir.mkdir(parents=True, exist_ok=True)
    written, _summaries, _audit = ingest_source_pdfs(
        pdfs,
        resolved.ai_drafts_dir,
        use_llm=use_llm,
        write_rag_snippets=True,
        rag_dir=rag_dir,
    )
    return written


def draft_narratives_for_folder(
    resolved: ResolvedProjectFolder,
    *,
    use_llm: bool = True,
    core_files: tuple[bytes, bytes] | None = None,
) -> Path:
    from ai.narrative import draft_narratives, sections_for_phase
    from engine import ReportEngine
    from template_attachments import prepare_template_upload_cached

    excel_bytes, template_bytes = core_files or resolved.read_core_files()
    excel_bytes, _ = effective_excel_bytes_for_folder(resolved, excel_bytes)
    prepared = prepare_template_upload_cached(template_bytes, resolved.template_path.name)
    engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=prepared.docx_bytes)
    ctx = engine.build_context(resolved.meta)
    ctx["_report_type"] = resolved.meta.get("report_type", "")
    sections = sections_for_phase(
        resolved.meta.get("report_phase", "Phase 1"),
        resolved.meta.get("report_type", ""),
    )
    if resolved.rag_dir.is_dir():
        ctx["_project_rag_dir"] = str(resolved.rag_dir)

    from ai.source_ingest import (
        format_summaries_for_prompt,
        load_summaries_for_narrative,
    )

    summaries = load_summaries_for_narrative(resolved.ai_drafts_dir)
    if summaries:
        ctx["_source_summaries"] = summaries
        ctx["_source_summaries_text"] = format_summaries_for_prompt(summaries)

    drafts, audit = draft_narratives(ctx, sections=sections, use_llm=use_llm)
    resolved.ai_drafts_dir.mkdir(parents=True, exist_ok=True)
    out_path = resolved.ai_drafts_dir / "narratives.json"
    payload = {
        "disclaimer": "AI draft — review before copying into Excel or Word.",
        "sections": [
            {
                "section": d.section,
                "text": d.text,
                "sources": d.sources,
                "disclaimer": d.disclaimer,
            }
            for d in drafts
        ],
        "audit": {
            "features": audit.features,
            "used_llm": audit.used_llm,
            "model": audit.model,
        },
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


def extract_lab_pdf_to_drafts(
    resolved: ResolvedProjectFolder,
    lab_pdf: Path,
    *,
    use_llm: bool = True,
    write_excel: bool = False,
) -> Path:
    from ai.excel_builder import lab_rows_to_xlsx_bytes
    from ai.lab_extract import extract_lab_from_pdf

    if not lab_pdf.is_file():
        raise FileNotFoundError(lab_pdf)
    result = extract_lab_from_pdf(_read_pdf_bytes(lab_pdf), use_llm=use_llm)
    resolved.ai_drafts_dir.mkdir(parents=True, exist_ok=True)
    draft_path = resolved.ai_drafts_dir / f"lab_extract_{lab_pdf.stem}.json"
    draft_path.write_text(
        json.dumps(
            {
                "source_pdf": lab_pdf.name,
                "row_count": len(result.rows),
                "source": result.source,
                "warnings": result.warnings,
                "rows": [r.to_excel_dict() for r in result.rows],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    if write_excel and result.rows:
        excel_bytes, _ = effective_excel_bytes_for_folder(resolved)
        xlsx_bytes = lab_rows_to_xlsx_bytes(
            result.rows,
            existing_excel=excel_bytes,
        )
        backup = resolved.ai_drafts_dir / f"project_data_with_lab_{lab_pdf.stem}.xlsx"
        backup.write_bytes(xlsx_bytes)
    return draft_path


def classify_appendices_for_folder(
    resolved: ResolvedProjectFolder,
    *,
    use_llm: bool = True,
) -> Path | None:
    from ai.appendix_classifier import classify_appendix_pdfs

    inv = resolved.inventory
    seen: set[Path] = set()
    pdfs: list[Path] = []
    for p in inv.appendix_pdfs + inv.source_pdfs:
        key = p.resolve()
        if key not in seen:
            seen.add(key)
            pdfs.append(p)
    if not pdfs:
        return None
    results = classify_appendix_pdfs(pdfs, use_llm=use_llm)
    resolved.ai_drafts_dir.mkdir(parents=True, exist_ok=True)
    out_path = resolved.ai_drafts_dir / "appendix_manifest.json"
    out_path.write_text(
        json.dumps(
            {
                "disclaimer": "Suggested labels — confirm before copying PDFs to appendices/.",
                "items": [r.to_dict() for r in results],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return out_path


def enrich_project_folder(
    resolved: ResolvedProjectFolder,
    *,
    use_llm: bool = True,
    modes: tuple[str, ...] = (
        "inventory",
        "source-ingest",
        "narratives",
        "appendix-classify",
    ),
) -> list[Path]:
    """Run AI advisory steps; outputs land in ai_drafts/."""
    written: list[Path] = []
    core: tuple[bytes, bytes] | None = None
    if any(m in modes for m in ("inventory", "narratives")):
        core = resolved.read_core_files()
    if "inventory" in modes:
        pre = run_preflight_for_folder(resolved, core_files=core)
        written.extend(write_preflight_artifacts(resolved, pre, use_llm=use_llm))
    if "source-ingest" in modes:
        written.extend(source_ingest_for_folder(resolved, use_llm=use_llm))
    elif "narratives" in modes:
        inv = resolved.inventory
        summaries_path = resolved.ai_drafts_dir / "source_summaries.json"
        if inv.source_pdfs and not summaries_path.is_file():
            written.extend(source_ingest_for_folder(resolved, use_llm=use_llm))
    if "narratives" in modes:
        written.append(
            draft_narratives_for_folder(resolved, use_llm=use_llm, core_files=core)
        )
    if "appendix-classify" in modes:
        path = classify_appendices_for_folder(resolved, use_llm=use_llm)
        if path is not None:
            written.append(path)
    return written


def load_manual_appendices(resolved: ResolvedProjectFolder) -> list[Any]:
    """Load PDFs from appendices/ as AppendixFile list (upload wins at render)."""
    from ai.appendix_classifier import heuristic_appendix_label
    from deliverable_pack import AppendixFile

    pdfs = resolved.inventory.appendix_pdfs
    if not pdfs:
        return []
    out: list[AppendixFile] = []
    for pdf in pdfs:
        out.append(
            AppendixFile(
                label=heuristic_appendix_label(pdf),
                data=_read_pdf_bytes(pdf),
                filename=pdf.name,
                format="pdf",
                source="uploaded",
            )
        )
    return out


def render_project_folder(
    resolved: ResolvedProjectFolder,
    *,
    package: bool = True,
    include_appendices: bool = True,
) -> dict[str, Path]:
    """Render report (+ optional package) into delivered/."""
    from appendix_generator import phase1_profile_includes_appendices
    from deliverable_pack import build_deliverable_zip_bytes
    from engine import suggested_download_name
    from provenance import sha256_hex
    from render_service import RenderRequest, render_report

    resolved.delivered_dir.mkdir(parents=True, exist_ok=True)
    excel_bytes, template_bytes = resolved.read_core_files()
    excel_bytes, eco_warnings = effective_excel_bytes_for_folder(resolved, excel_bytes)
    meta = dict(resolved.meta)

    uploaded = load_manual_appendices(resolved) if include_appendices else []
    inc_ap = include_appendices and phase1_profile_includes_appendices(
        meta.get("report_type", ""), meta.get("report_phase", "")
    )

    result = render_report(
        RenderRequest(
            excel_bytes=excel_bytes,
            template_bytes=template_bytes,
            meta=meta,
            excel_filename=resolved.excel_path.name,
            template_filename=resolved.template_path.name,
            include_appendices=inc_ap,
            uploaded_appendices=uploaded,
        )
    )
    docx_bytes = result.docx_bytes
    warnings = list(eco_warnings) + result.warnings
    context = result.context
    record = result.record
    appendices = result.appendices

    out_name = suggested_download_name(context, meta)
    record.output_filename = out_name
    record.output_sha256 = sha256_hex(docx_bytes)
    record.project_folder = str(resolved.root)
    manifest_bytes = record.to_json_bytes()

    docx_path = resolved.delivered_dir / out_name
    docx_path.write_bytes(docx_bytes)
    manifest_path = resolved.delivered_dir / (docx_path.stem + "_manifest.json")
    manifest_path.write_bytes(manifest_bytes)

    outputs: dict[str, Path] = {"docx": docx_path, "manifest": manifest_path}

    if package:
        zip_path = resolved.delivered_dir / (docx_path.stem + "_package.zip")
        zip_path.write_bytes(
            build_deliverable_zip_bytes(
                docx_bytes,
                out_name,
                context,
                meta,
                manifest_bytes,
                appendices,
            )
        )
        outputs["package"] = zip_path

    warn_path = resolved.delivered_dir / "render_warnings.txt"
    all_warnings = list(warnings) + list(eco_warnings)
    if all_warnings:
        warn_path.write_text("\n".join(all_warnings) + "\n", encoding="utf-8")
        outputs["warnings"] = warn_path

    return outputs


def init_sample_project_folder(
    dest: Path,
    *,
    source_user_test: bool = True,
    profile: str = "phase1_alberta",
) -> Path:
    """Create a sample project folder from user_test or Alberta samples."""
    dest = dest.expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)

    spec = SAMPLE_PROFILES.get(profile) or SAMPLE_PROFILES["phase1_alberta"]
    samples = ROOT / "samples"
    user_test = ROOT / "user_test"
    if (
        profile == "phase1_alberta"
        and source_user_test
        and (user_test / "my_project_data.xlsx").is_file()
    ):
        shutil.copy2(user_test / "my_project_data.xlsx", dest / "project_data.xlsx")
        if (user_test / "my_template.docx").is_file():
            shutil.copy2(user_test / "my_template.docx", dest / "template.docx")
    else:
        excel_src = samples / spec["excel"]
        tpl_src = samples / spec["template"]
        if not excel_src.is_file() or not tpl_src.is_file():
            raise FileNotFoundError(
                f"Missing samples for profile '{profile}'. Run: python scripts/create_samples.py"
            )
        shutil.copy2(excel_src, dest / "project_data.xlsx")
        shutil.copy2(tpl_src, dest / "template.docx")

    for name in SUBDIRS:
        (dest / name).mkdir(exist_ok=True)

    _seed_sample_folder_extras(dest, profile=profile)

    if not (dest / PROJECT_JSON).is_file():
        (dest / PROJECT_JSON).write_text(
            json.dumps(
                {
                    "project_number": dest.name,
                    "report_type": spec["report_type"],
                    "report_phase": spec["report_phase"],
                    "prepared_by": "Ecoventure QP",
                    "date_of_issue": "2026-06-10",
                    "template_version": spec["template_version"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return dest


def _seed_sample_folder_extras(dest: Path, *, profile: str) -> None:
    """Optional README stubs, RAG snippet, and placeholder PDFs for demo folders."""
    readme = dest / "README.txt"
    if not readme.is_file():
        if profile == "phase2_esa":
            readme.write_text(
                "Alberta Phase II ESA — test project folder\n"
                "==========================================\n\n"
                "  project_data.xlsx  — ProjectData + LabResults + SampleLocations\n"
                "  template.docx      — Phase II Jinja template\n"
                "  source/            — Lab COA / prior reports (PDF)\n"
                "  appendices/        — Manual appendix PDFs\n\n"
                "Streamlit: Project folder + AI → Browse to this folder\n"
                "CLI: python scripts\\ingest_project_folder.py --folder "
                f"{dest} --render\n",
                encoding="utf-8",
            )
        else:
            readme.write_text(
                "Alberta Phase I ESA — test project folder\n"
                "See docs/22-project-folder-workflow.md\n",
                encoding="utf-8",
            )

    rag_src = ROOT / "rag_corpus" / (
        "phase2_intro.txt" if profile == "phase2_esa" else "phase1_alberta_aer.txt"
    )
    rag_dest = dest / "rag" / rag_src.name
    if rag_src.is_file() and not rag_dest.is_file():
        shutil.copy2(rag_src, rag_dest)

    if profile == "phase2_esa":
        lab_stub = dest / "source" / "lab_coa_example.pdf"
        if not lab_stub.is_file():
            lab_stub.write_bytes(
                b"%PDF-1.4\n% Phase II lab COA placeholder - replace with real COA PDF\n"
            )
        src_readme = dest / "source" / "README.txt"
        if not src_readme.is_file():
            src_readme.write_text(
                "Add lab certificate-of-analysis PDFs here for source-ingest / AI.\n"
                "Filename hints: lab_coa, certificate, analytical\n",
                encoding="utf-8",
            )
