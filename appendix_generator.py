"""
Auto-render Phase I appendix Word documents from merge context (SED 002 D/G).
"""

from __future__ import annotations

import io
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from docxtpl import DocxTemplate
from jinja2 import Undefined
from jinja2.exceptions import TemplateError
from jinja2.sandbox import SandboxedEnvironment

from deliverable_pack import AppendixFile, appendix_manifest_entries
from report_profile import get_profile_spec
from security import validate_rendered_output

ROOT = Path(__file__).resolve().parent
DEFAULT_APPENDIX_DIR = ROOT / "samples" / "appendices"

PHASE1_APPENDIX_PROFILES = frozenset({"phase1_alberta", "phase1_devon", "reclamation_certificate"})

DEFAULT_LABELS = ("A", "D", "G")

_JINJA_ENV = SandboxedEnvironment(undefined=Undefined, autoescape=False)


def phase1_profile_includes_appendices(report_type: str, report_phase: str = "") -> bool:
    rt = (report_type or "").strip()
    if rt in PHASE1_APPENDIX_PROFILES:
        return True
    return not rt and report_phase.strip().lower().startswith("phase 1")


def _has_value(val: Any) -> bool:
    if val is None:
        return False
    s = str(val).strip()
    return bool(s) and s.lower() not in ("nan", "none", "n/a", "")


def _no_waste_on_site(context: dict[str, Any]) -> bool:
    val = str(context.get("no_drilling_waste_on_site") or "").strip().lower()
    return val in ("y", "yes", "true", "1")


def _report_type(meta: dict[str, str] | None, report_type: str = "") -> str:
    return str((meta or {}).get("report_type") or report_type or "phase1_alberta").strip()


def get_appendix_templates(report_type: str) -> dict[str, str]:
    """Return appendix label -> template path (relative to samples/ or absolute)."""
    raw = get_profile_spec(report_type).get("appendix_templates") or {}
    return {str(k).upper(): str(v) for k, v in raw.items()}


def resolve_appendix_template_path(
    rel_path: str,
    *,
    template_dir: Path | None = None,
) -> Path:
    path = Path(rel_path)
    if path.is_file():
        return path
    base = template_dir or DEFAULT_APPENDIX_DIR
    for candidate in (base / path.name, ROOT / "samples" / path, base / path):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Appendix template not found: {rel_path}")


@lru_cache(maxsize=16)
def _cached_template_bytes(resolved_path: str, mtime_ns: int) -> bytes:
    return Path(resolved_path).read_bytes()


def _load_template_bytes(path: Path) -> bytes:
    return _cached_template_bytes(str(path), path.stat().st_mtime_ns)


def clear_appendix_template_cache() -> None:
    """Drop cached appendix template bytes (tests / template regeneration)."""
    _cached_template_bytes.cache_clear()


def should_generate_appendix(label: str, context: dict[str, Any]) -> bool:
    """Whether appendix label A, D, or G should be rendered for this context."""
    key = label.upper()
    if key == "A":
        return True
    waste_rows = context.get("drilling_waste") or []
    if key == "G":
        return bool(waste_rows) and not _no_waste_on_site(context)
    if key == "D":
        if _no_waste_on_site(context) and not waste_rows:
            return _has_value(context.get("aer_waste_compliance_option"))
        return True
    return False


def _appendix_labels_for_context(
    context: dict[str, Any],
    catalog: dict[str, str],
    labels: tuple[str, ...] | None = None,
) -> list[str]:
    keys = labels or tuple(catalog.keys())
    return [
        key.upper()
        for key in keys
        if key.upper() in catalog and should_generate_appendix(key, context)
    ]


def predicted_appendix_labels(
    context: dict[str, Any],
    meta: dict[str, str] | None = None,
    *,
    report_type: str = "",
) -> set[str]:
    """Labels that would be auto-generated (for pre-flight before render)."""
    rt = _report_type(meta, report_type)
    if rt not in PHASE1_APPENDIX_PROFILES:
        return set()
    catalog = get_appendix_templates(rt)
    return set(_appendix_labels_for_context(context, catalog))


def _render_ctx(context: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in context.items() if not str(k).startswith("_")}


def _default_appendix_filename(label: str, context: dict[str, Any]) -> str:
    uwi = re.sub(
        r"[^\w\-]+",
        "_",
        str(context.get("uwi") or "site").replace("/", "-").replace("\\", "-"),
    )[:40]
    stem = {
        "A": "appendix_a_qp_declaration",
        "D": "appendix_d_drilling_waste_checklist",
        "G": "appendix_g_waste_calc_tables",
    }.get(label.upper(), f"appendix_{label.lower()}")
    return f"{stem}_{uwi}.docx"


def _appendix_render_context(
    context: dict[str, Any],
    meta: dict[str, str] | None,
) -> dict[str, Any]:
    """Merge context with sidebar meta keys required by appendix templates."""
    out = _render_ctx(context)
    rt = _report_type(meta)
    for key in get_profile_spec(rt).get("recommended_fields") or []:
        if not _has_value(out.get(key)):
            val = (meta or {}).get(key)
            if _has_value(val):
                out[key] = val
    for key in ("prepared_by", "date_of_issue", "template_version", "report_phase"):
        val = (meta or {}).get(key)
        if _has_value(val):
            out[key] = val
    return out


def _render_appendix_docx(
    template_bytes: bytes,
    context: dict[str, Any],
    meta: dict[str, str] | None,
) -> bytes:
    doc = DocxTemplate(io.BytesIO(template_bytes))
    try:
        doc.render(_appendix_render_context(context, meta), jinja_env=_JINJA_ENV)
    except TemplateError as e:
        raise ValueError(f"Appendix template rendering failed: {e}") from e
    out = io.BytesIO()
    doc.save(out)
    docx_bytes = out.getvalue()
    validate_rendered_output(docx_bytes)
    return docx_bytes


def render_phase1_appendices(
    context: dict[str, Any],
    meta: dict[str, str] | None = None,
    *,
    labels: tuple[str, ...] = DEFAULT_LABELS,
    template_dir: Path | None = None,
    report_type: str = "",
) -> tuple[list[AppendixFile], list[str]]:
    """Render appendix Word docs; returns (appendix files, warnings)."""
    meta = meta or {}
    rt = _report_type(meta, report_type)
    if rt not in PHASE1_APPENDIX_PROFILES:
        return [], []

    catalog = get_appendix_templates(rt)
    if not catalog:
        return [], []

    results: list[AppendixFile] = []
    warnings: list[str] = []
    for key in _appendix_labels_for_context(context, catalog, labels):
        rel = catalog[key]
        try:
            path = resolve_appendix_template_path(rel, template_dir=template_dir)
            docx_bytes = _render_appendix_docx(_load_template_bytes(path), context, meta)
        except (FileNotFoundError, ValueError, OSError) as e:
            warnings.append(f"Appendix {key} not generated: {e}")
            continue
        results.append(
            AppendixFile(
                label=key,
                data=docx_bytes,
                filename=_default_appendix_filename(key, context),
                format="docx",
                source="generated",
            )
        )
    return results, warnings


def merge_appendix_lists(
    generated: list[AppendixFile],
    uploaded: list[AppendixFile],
) -> list[AppendixFile]:
    """Merge generated and uploaded appendices; upload wins on label collision."""
    by_label = {ap.label.upper(): ap for ap in generated}
    for ap in uploaded:
        by_label[ap.label.upper()] = ap
    return [by_label[k] for k in sorted(by_label.keys())]


def attach_appendices_to_record(
    record: Any,
    context: dict[str, Any],
    meta: dict[str, str] | None,
    uploaded: list[AppendixFile],
) -> tuple[list[AppendixFile], list[AppendixFile], list[str]]:
    """Render D/G, merge with uploads, write manifest fields. Returns (generated, merged, warnings)."""
    generated, warnings = render_phase1_appendices(context, meta)
    merged = merge_appendix_lists(generated, uploaded)
    record.appendix_files = appendix_manifest_entries(merged) if merged else []
    record.generated_appendix_files = (
        appendix_manifest_entries(generated) if generated else []
    )
    return generated, merged, warnings
