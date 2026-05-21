"""
Template analysis: coverage vs Excel context, tag inventory, split-run lint.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import pandas as pd

from engine import DRILLING_WASTE_SHEET, LAB_SHEET, PROJECT_SHEET, ReportEngine
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


def missing_fields_checklist(coverage: TemplateCoverage) -> str:
    """Text block for Excel ProjectData column planning."""
    lines = [
        "# Add these columns to sheet 'ProjectData' (row 1 headers, row 2 values)",
        "",
    ]
    if coverage.missing_in_data:
        lines.append("Missing for template:")
        for name in coverage.missing_in_data:
            lines.append(f"  {name}")
    else:
        lines.append("All template root variables are covered.")
    if coverage.unused_in_template:
        lines.extend(["", "Excel columns not used in template:"])
        for name in coverage.unused_in_template:
            lines.append(f"  {name}")
    lines.extend(["", f"Lab rows loaded: {coverage.lab_row_count}"])
    return "\n".join(lines)


def run_preflight(
    excel_bytes: bytes,
    template_bytes: bytes,
    meta: dict[str, str] | None,
) -> PreflightResult:
    """Dry-run checks without rendering the document."""
    result = PreflightResult()
    phase = str((meta or {}).get("report_phase", "Phase 2")).strip()
    require_lab = phase != "Phase 1"

    try:
        engine = ReportEngine(excel_bytes=excel_bytes, template_bytes=template_bytes)
    except SecurityError as e:
        result.errors.append(str(e))
        return result
    except ValueError as e:
        result.errors.append(str(e))
        return result

    try:
        bio = io.BytesIO(excel_bytes)
        with pd.ExcelFile(bio, engine="openpyxl") as xl:
            result.sheet_names = list(xl.sheet_names)
            if PROJECT_SHEET not in result.sheet_names:
                result.errors.append(
                    f"Missing sheet '{PROJECT_SHEET}'. Found: {result.sheet_names}"
                )
            elif require_lab and LAB_SHEET not in result.sheet_names:
                result.errors.append(
                    f"Phase 2 requires sheet '{LAB_SHEET}'. Found: {result.sheet_names}"
                )
    except Exception as e:
        result.errors.append(f"Could not read Excel: {e}")

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

    if not result.errors:
        try:
            result.coverage = engine.coverage(meta)
            if require_lab and result.coverage.lab_row_count == 0:
                result.warnings.append("LabResults has no data rows.")
            if not require_lab:
                if DRILLING_WASTE_SHEET not in result.sheet_names:
                    result.warnings.append(
                        f"Phase 1: optional sheet '{DRILLING_WASTE_SHEET}' not found."
                    )
                if (
                    scan
                    and result.coverage
                    and result.coverage.drilling_waste_row_count == 0
                    and any("drilling_waste" in b for b in scan.block_tags)
                ):
                    result.warnings.append(
                        "Template loops drilling_waste but sheet has no rows."
                    )
        except ValueError as e:
            result.errors.append(str(e))
        except Exception as e:
            result.errors.append(f"Could not build data context: {e}")

    return result
