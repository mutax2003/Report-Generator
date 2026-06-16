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

DEFAULT_LABELS: tuple[str, ...] | None = None

_JINJA_ENV = SandboxedEnvironment(undefined=Undefined, autoescape=False)

_META_SIDEBAR_KEYS = ("prepared_by", "date_of_issue", "template_version", "report_phase")


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
    return _appendix_templates_for_profile(report_type)


@lru_cache(maxsize=8)
def _appendix_templates_for_profile(report_type: str) -> dict[str, str]:
    raw = get_profile_spec(report_type).get("appendix_templates") or {}
    return {str(k).upper(): str(v) for k, v in raw.items()}


@lru_cache(maxsize=32)
def _resolved_appendix_path(rel_path: str, template_dir_str: str) -> str:
    template_dir = Path(template_dir_str) if template_dir_str else DEFAULT_APPENDIX_DIR
    path = resolve_appendix_template_path(rel_path, template_dir=template_dir)
    return str(path)


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
    _appendix_templates_for_profile.cache_clear()
    _resolved_appendix_path.cache_clear()
    _recommended_fields.cache_clear()


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


@lru_cache(maxsize=8)
def _recommended_fields(report_type: str) -> tuple[str, ...]:
    return tuple(get_profile_spec(report_type).get("recommended_fields") or [])


def _appendix_render_context(
    context: dict[str, Any],
    meta: dict[str, str] | None,
    *,
    report_type: str = "",
) -> dict[str, Any]:
    """Merge context with sidebar meta keys required by appendix templates."""
    out = _render_ctx(context)
    rt = _report_type(meta, report_type)
    for key in _recommended_fields(rt):
        if not _has_value(out.get(key)):
            val = (meta or {}).get(key)
            if _has_value(val):
                out[key] = val
    for key in _META_SIDEBAR_KEYS:
        val = (meta or {}).get(key)
        if _has_value(val):
            out[key] = val
    return out


def _render_appendix_docx(
    template_bytes: bytes,
    render_context: dict[str, Any],
) -> bytes:
    doc = DocxTemplate(io.BytesIO(template_bytes))
    try:
        doc.render(render_context, jinja_env=_JINJA_ENV)
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
    labels: tuple[str, ...] | None = DEFAULT_LABELS,
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

    label_keys = _appendix_labels_for_context(context, catalog, labels)
    if not label_keys:
        return [], []

    render_context = _appendix_render_context(context, meta, report_type=rt)
    template_dir_str = str(template_dir or DEFAULT_APPENDIX_DIR)
    results: list[AppendixFile] = []
    warnings: list[str] = []
    for key in label_keys:
        rel = catalog[key]
        try:
            path = Path(_resolved_appendix_path(rel, template_dir_str))
            docx_bytes = _render_appendix_docx(
                _load_template_bytes(path),
                render_context,
            )
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
    """Render A/D/G, merge with uploads, write manifest fields. Returns (generated, merged, warnings)."""
    generated, warnings = render_phase1_appendices(context, meta)
    merged = merge_appendix_lists(generated, uploaded)
    if merged:
        record.appendix_files = appendix_manifest_entries(merged)
    else:
        record.appendix_files = []
    if generated:
        record.generated_appendix_files = appendix_manifest_entries(generated)
    else:
        record.generated_appendix_files = []
    return generated, merged, warnings
