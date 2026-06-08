"""
Template analysis: coverage vs Excel context, tag inventory, split-run lint.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from engine import LAB_SHEET, ReportEngine
from report_profile import loops_from_block_tags, read_excel_meta, resolve_report_config
from sed002_compliance import PHASE1_SED_PROFILES
from security import SecurityError, ZipReadBudget, open_docx_zip, read_docx_xml_member


@dataclass
class TemplateCoverage:
    """Excel/sidebar keys vs template root variables."""

    template_vars: set[str] = field(default_factory=set)
    context_keys: set[str] = field(default_factory=set)
    matched: list[str] = field(default_factory=list)
    missing_in_data: list[str] = field(default_factory=list)
    unused_in_template: list[str] = field(default_factory=list)
    lab_row_count: int = 0
    drilling_waste_row_count: int = 0
    storage_tanks_row_count: int = 0
    table_row_counts: dict[str, int] = field(default_factory=dict)

    @property
    def ready(self) -> bool:
        return len(self.missing_in_data) == 0


@dataclass
class TemplateScan:
    """Single-pass template ZIP scan."""

    root_vars: set[str] = field(default_factory=set)
    mustache_exprs: set[str] = field(default_factory=set)
    block_tags: set[str] = field(default_factory=set)
    split_issues: list[str] = field(default_factory=list)


@dataclass
class PreflightResult:
    """Pre-render validation for the Streamlit UI."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    coverage: TemplateCoverage | None = None
    sheet_names: list[str] = field(default_factory=list)
    split_tag_issues: list[str] = field(default_factory=list)
    template_var_count: int = 0
    block_tag_count: int = 0
    sed002: Any = None  # Sed002ComplianceResult | None

    @property
    def can_generate(self) -> bool:
        return len(self.errors) == 0


def scan_template(template_bytes: bytes, *, max_split_issues: int = 15) -> TemplateScan:
    """One ZIP pass: root vars, expressions, blocks, split-run lint."""
    roots: set[str] = set()
    mustache: set[str] = set()
    blocks: set[str] = set()
    split_issues: list[str] = []
    run_pattern = re.compile(r"<w:t[^>]*>([^<]*)</w:t>")

    with open_docx_zip(template_bytes) as zf:
        budget = ZipReadBudget()
        for name in zf.namelist():
            if not name.startswith("word/") or not name.endswith(".xml"):
                continue
            try:
                xml = read_docx_xml_member(zf, name, budget)
            except (KeyError, OSError):
                continue
            roots |= _parse_root_vars(xml)
            for m in re.finditer(r"\{\{-?\s*([^}|]+?)\s*-?\}\}", xml):
                mustache.add(m.group(1).strip())
            for m in re.finditer(r"\{%\s*([^%]+?)\s*%\}", xml):
                blocks.add(m.group(1).strip())
            for para in re.split(r"</w:p>", xml):
                runs = run_pattern.findall(para)
                if len(runs) < 2:
                    continue
                joined = "".join(runs)
                if "{{" not in joined and "{%" not in joined:
                    continue
                if re.search(r"\{\{[^}]+\}\}", joined) or re.search(
                    r"\{%[^%]+%\}", joined
                ):
                    continue
                for i, text in enumerate(runs):
                    if text.endswith("{{") or text.endswith("{%"):
                        split_issues.append(
                            f"{name}: split opening tag near {text!r} (run {i + 1})"
                        )
                    if text.startswith("}}") or text.startswith("%}"):
                        split_issues.append(
                            f"{name}: split closing tag near {text!r} (run {i + 1})"
                        )
                if len(split_issues) >= max_split_issues:
                    break
            if len(split_issues) >= max_split_issues:
                break

    roots.discard("item")
    return TemplateScan(
        root_vars=roots,
        mustache_exprs=mustache,
        block_tags=blocks,
        split_issues=split_issues[:max_split_issues],
    )


def _parse_root_vars(xml_text: str) -> set[str]:
    needed: set[str] = set()
    for m in re.finditer(r"\{\{-?\s*([^}|]+?)\s*-?\}\}", xml_text):
        expr = m.group(1).strip()
        if not expr or expr.startswith("%"):
            continue
        if "|" in expr:
            expr = expr.split("|", 1)[0].strip()
        if "." in expr:
            continue
        if re.fullmatch(r"[A-Za-z_]\w*", expr):
            needed.add(expr)
    return needed


def analyze_template_tags(template_bytes: bytes) -> tuple[set[str], set[str]]:
    scan = scan_template(template_bytes)
    return scan.mustache_exprs, scan.block_tags


def lint_split_jinja_runs(template_bytes: bytes, *, max_issues: int = 15) -> list[str]:
    return scan_template(template_bytes, max_split_issues=max_issues).split_issues


def template_coverage(
    excel_bytes: bytes,
    template_bytes: bytes,
    meta: dict[str, str] | None,
) -> TemplateCoverage:
    engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=template_bytes)
    return engine.coverage(meta)


def missing_fields_checklist(
    coverage: TemplateCoverage,
    *,
    report_type: str = "",
) -> str:
    """Text block for Excel ProjectData column planning (profile-aware)."""
    from report_profile import get_recommended_fields

    lines = [
        "# Add these columns to sheet 'ProjectData' (row 1 = headers, row 2+ = one site per row)",
        "",
    ]
    if coverage.missing_in_data:
        lines.append("Missing for template:")
        for name in coverage.missing_in_data:
            lines.append(f"  {name}")
    else:
        lines.append("All template root variables are covered.")
    rt = (report_type or "").strip()
    if rt:
        rec = get_recommended_fields(rt)
        missing_rec = [
            f
            for f in rec
            if f not in coverage.matched and f not in coverage.missing_in_data
        ]
        if missing_rec:
            lines.extend(["", f"Recommended for profile '{rt}' (not in template scan):"])
            for name in missing_rec:
                lines.append(f"  {name}")
    if coverage.unused_in_template:
        lines.extend(["", "Excel columns not used in template:"])
        for name in coverage.unused_in_template:
            lines.append(f"  {name}")
    if coverage.table_row_counts:
        lines.extend(["", "Table row counts:"])
        for k, n in sorted(coverage.table_row_counts.items()):
            lines.append(f"  {k}: {n}")
    else:
        lines.extend(["", f"Lab rows loaded: {coverage.lab_row_count}"])
    return "\n".join(lines)


def run_preflight(
    excel_bytes: bytes,
    template_bytes: bytes,
    meta: dict[str, str] | None,
    *,
    appendix_labels_present: set[str] | None = None,
) -> PreflightResult:
    """Dry-run checks without rendering the document."""
    result = PreflightResult()
    meta = meta or {}

    scan: TemplateScan | None = None
    try:
        scan = scan_template(template_bytes)
        result.template_var_count = len(scan.root_vars)
        result.block_tag_count = len(scan.block_tags)
        result.split_tag_issues = scan.split_issues
        if not scan.root_vars and not scan.block_tags:
            result.warnings.append(
                "No Jinja2 tags found — output may match the uploaded template unchanged."
            )
        for issue in scan.split_issues:
            result.warnings.append(f"Possible broken tag: {issue}")
    except Exception as e:
        result.errors.append(f"Could not read template: {e}")

    excel_meta: tuple[list[str], dict[str, str]] | None = None
    try:
        excel_meta = read_excel_meta(excel_bytes)
        result.sheet_names = excel_meta[0]
    except Exception as e:
        result.errors.append(f"Could not read Excel: {e}")

    template_loops = loops_from_block_tags(scan.block_tags) if scan else None
    try:
        runtime = resolve_report_config(
            excel_bytes,
            template_bytes,
            meta,
            template_loops=template_loops,
            excel_meta=excel_meta,
        )
    except Exception as e:
        result.errors.append(f"Could not resolve report profile: {e}")
        return result

    result.warnings.append(f"Report type: {runtime.label} (`{runtime.report_type}`)")

    if excel_meta:
        for req in runtime.required_sheets:
            if req not in result.sheet_names:
                result.errors.append(
                    f"Report type requires sheet '{req}'. "
                    f"Found: {result.sheet_names}"
                )
        if runtime.primary_sheet not in result.sheet_names:
            result.errors.append(
                f"Missing primary sheet '{runtime.primary_sheet}'. "
                f"Found: {result.sheet_names}"
            )

    try:
        engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=template_bytes)
        if scan:
            engine._root_vars_cache = scan.root_vars
            engine._template_loops_cache = template_loops or set()
    except SecurityError as e:
        result.errors.append(str(e))
        return result
    except ValueError as e:
        result.errors.append(str(e))
        return result

    if scan and runtime.template_loops:
        for loop_var in sorted(runtime.template_loops):
            has_sheet = loop_var in runtime.sheet_to_loop.values()
            if not has_sheet:
                result.warnings.append(
                    f"Template loops '{{{{ item in {loop_var} }}}}' but no Excel sheet "
                    f"is mapped — table will be empty."
                )

    if not result.errors:
        try:
            ctx = engine.build_context(meta)
            result.coverage = engine.coverage(meta, context=ctx)
            cov = result.coverage
            if runtime.require_lab_sheet and cov and cov.lab_row_count == 0:
                result.warnings.append(
                    f"Sheet '{LAB_SHEET}' (lab_results) has no data rows."
                )
            if cov and cov.table_row_counts:
                for loop_var, count in sorted(cov.table_row_counts.items()):
                    if count == 0 and scan and any(
                        loop_var in b for b in scan.block_tags
                    ):
                        result.warnings.append(
                            f"Table loop '{loop_var}' has 0 rows in Excel."
                        )
            if runtime.report_type in PHASE1_SED_PROFILES or runtime.narrative_profile == "phase1_alberta":
                from sed002_compliance import evaluate_sed002_compliance

                sheet_counts = (
                    dict(cov.table_row_counts)
                    if cov and cov.table_row_counts
                    else {}
                )
                sed = evaluate_sed002_compliance(
                    ctx,
                    meta,
                    report_type=runtime.report_type,
                    sheet_row_counts=sheet_counts,
                    appendix_labels_present=appendix_labels_present,
                )
                result.sed002 = sed
                if sed:
                    result.warnings.append(
                        f"SED 002 §10 completeness: {sed.completeness_pct}% "
                        f"({sed.satisfied_count}/{sed.total_items})"
                    )
                    for ir in sed.required_missing[:8]:
                        result.warnings.append(
                            f"SED 002 required: {ir.section_id} — {ir.label}"
                        )
                    if len(sed.required_missing) > 8:
                        result.warnings.append(
                            f"... and {len(sed.required_missing) - 8} more SED 002 required items"
                        )
                    for pw in sed.phase2_warnings[:5]:
                        result.warnings.append(f"Phase 2 hint: {pw}")
        except ValueError as e:
            result.errors.append(str(e))
        except Exception as e:
            result.errors.append(f"Could not build data context: {e}")

    return result
