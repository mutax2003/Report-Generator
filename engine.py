"""
Document rendering for ESA reports: Excel -> Jinja2 context -> docxtpl.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Any

import pandas as pd
from docx import Document
from docxtpl import DocxTemplate, RichText
from jinja2 import StrictUndefined
from jinja2.exceptions import TemplateError
from jinja2.sandbox import SandboxedEnvironment

from phase1_narrative import build_phase1_executive_summary
from report_profile import (
    ReportRuntimeConfig,
    list_keys_from_context,
    resolve_report_config,
    table_row_counts,
)

from security import (
    MAX_BATCH_REPORTS,
    MAX_LAB_ROWS,
    MAX_PROJECT_COLUMNS,
    MAX_PROJECT_ROWS,
    SecurityError,
    ZipReadBudget,
    clamp_context,
    open_docx_zip,
    read_docx_xml_member,
    sanitize_download_filename,
    sanitize_meta,
    validate_excel_upload,
    validate_rendered_output,
    validate_template_upload,
    validation_bypass_enabled,
)


PROJECT_SHEET = "ProjectData"
LAB_SHEET = "LabResults"
DRILLING_WASTE_SHEET = "DrillingWaste"
STORAGE_TANKS_SHEET = "StorageTanks"

ECOVENTURE_CONSULTANT = "Ecoventure Inc."


def _s(value: Any) -> str:
    if value is None:
        return ""
    t = str(value).strip()
    if t.lower() in ("nan", "none"):
        return ""
    return t


def _norm_key(name: str) -> str:
    s = str(name).strip()
    s = re.sub(r"\s+", "_", s)
    return s.lower()


def _cell_str(v: Any) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    # Mitigate formula injection when values are opened in Excel from Word tables
    if s and s[0] in "=+-@\t\r":
        s = "'" + s
    if len(s) > 32_768:
        s = s[:32_768]
    return s


def _truthy_exceedance(val: Any) -> bool:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    s = str(val).strip().lower()
    return s in ("y", "yes", "true", "1", "x", "exceedance", "exc")


def _numeric_compare_exceeds(result: Any, criteria: Any) -> bool:
    try:
        r = float(result)
        c = float(criteria)
    except (TypeError, ValueError):
        return False
    return r > c


def _rich_result_plain(result: Any, exceed: bool) -> RichText | str:
    text = _cell_str(result) if result is not None else ""
    if not exceed:
        return text
    rt = RichText()
    rt.add(text, bold=True, color="FF0000")
    return rt


_TABLE_LINK_COLUMNS = (
    "project_id",
    "project_number",
    "site_name",
    "uwi",
    "well_name",
)


def _project_row_is_blank(row: pd.Series) -> bool:
    for col in row.index:
        if _cell_str(row[col]):
            return False
    return True


def _project_row_is_duplicate_header(row: pd.Series, columns: pd.Index) -> bool:
    """Skip a data row that repeats column headers (headers pasted in row 2)."""
    match_count = 0
    filled = 0
    for col in columns:
        val = _cell_str(row[col])
        if not val:
            continue
        filled += 1
        if _norm_key(val) == _norm_key(str(col)):
            match_count += 1
    return filled > 0 and match_count >= max(2, int(filled * 0.5))


def _excel_row_number(dataframe_index: int) -> int:
    """Excel row number for a ProjectData data row (row 1 = headers)."""
    return dataframe_index + 2


def _project_row_to_dict_at(df: pd.DataFrame, index: int) -> dict[str, Any]:
    if df.empty or index < 0 or index >= len(df):
        return {}
    row = df.iloc[index]
    out: dict[str, Any] = {}
    for col in df.columns:
        key = _norm_key(col)
        if not key:
            continue
        out[key] = _cell_str(row[col])
    return out


def _project_rows_from_df(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    ProjectData data rows only.

    Excel layout: row 1 = column headers (``header=0`` for pandas);
    row 2 onward = one report per non-blank row.
    """
    rows: list[dict[str, Any]] = []
    for i in range(len(df)):
        row = df.iloc[i]
        if _project_row_is_blank(row):
            continue
        if _project_row_is_duplicate_header(row, df.columns):
            continue
        rec = _project_row_to_dict_at(df, i)
        rec["_excel_row_number"] = _excel_row_number(i)
        rows.append(rec)
    return rows


def _project_row_to_dict(df: pd.DataFrame) -> dict[str, Any]:
    rows = _project_rows_from_df(df)
    return rows[0] if rows else {}


def _filter_records_for_project(
    records: list[dict[str, Any]], project: dict[str, Any]
) -> list[dict[str, Any]]:
    """When table sheets include a link column, keep rows matching this project."""
    if not records:
        return []
    for col in _TABLE_LINK_COLUMNS:
        project_val = _s(project.get(col))
        if not project_val:
            continue
        if col not in records[0]:
            continue
        matched = [r for r in records if _s(r.get(col)) == project_val]
        if matched:
            return matched
    return records


@dataclass
class BatchReportResult:
    """One rendered report from a ProjectData row."""

    project_row_index: int
    excel_row_number: int
    docx_bytes: bytes
    warnings: list[str]
    context: dict[str, Any]
    record: Any
    filename: str
    row_label: str = ""


def _lab_frame_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    if len(df) > MAX_LAB_ROWS:
        df = df.head(MAX_LAB_ROWS)
    rows: list[dict[str, Any]] = []
    col_map = {_norm_key(c): c for c in df.columns}

    def get(row: pd.Series, *names: str) -> Any:
        for n in names:
            if n in col_map:
                return row[col_map[n]]
        return None

    for _, row in df.iterrows():
        analyte = get(row, "analyte", "parameter", "constituent")
        result = get(row, "result", "value")
        unit = get(row, "unit", "units")
        criteria = get(row, "criteria", "standard", "screening_level")
        exc_col = get(row, "exceedance", "exceeds", "flag")

        exceed = _truthy_exceedance(exc_col) or _numeric_compare_exceeds(
            result, criteria
        )
        rec: dict[str, Any] = {}
        for c in df.columns:
            k = _norm_key(c)
            if k:
                rec[k] = _cell_str(row[c])
        rec["analyte"] = _cell_str(analyte)
        rec["result"] = _cell_str(result)
        rec["unit"] = _cell_str(unit)
        rec["criteria"] = _cell_str(criteria)
        rec["exceedance_flag"] = "Yes" if exceed else "No"
        rec["result_plain"] = _cell_str(result)
        rec["result_display"] = _rich_result_plain(result, exceed)
        rows.append(rec)
    return rows


def _dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Generic sheet → list of dicts (normalized keys, string cells)."""
    if df.empty:
        return []
    if len(df) > MAX_LAB_ROWS:
        df = df.head(MAX_LAB_ROWS)
    cols = [c for c in df.columns if _norm_key(c)]
    keys = [_norm_key(c) for c in cols]
    return [
        {k: _cell_str(v) for k, v in zip(keys, row)}
        for row in df[cols].itertuples(index=False, name=None)
    ]


def _parse_simple_mustache_vars(xml_text: str) -> set[str]:
    """Top-level {{ var }} names; skips dotted paths (e.g. item.x)."""
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


def collect_template_root_vars(template_bytes: bytes) -> set[str]:
    roots: set[str] = set()
    with open_docx_zip(template_bytes) as zf:
        budget = ZipReadBudget()
        for name in zf.namelist():
            if not name.startswith("word/") or not name.endswith(".xml"):
                continue
            try:
                data = read_docx_xml_member(zf, name, budget)
            except (KeyError, OSError, SecurityError):
                continue
            roots |= _parse_simple_mustache_vars(data)
    roots.discard("item")
    return roots


def _runtime_cache_key(runtime: ReportRuntimeConfig) -> tuple[Any, ...]:
    return (
        runtime.report_type,
        runtime.primary_sheet,
        runtime.require_lab_sheet,
        runtime.lab_loop_variable,
        tuple(sorted(runtime.sheet_to_loop.items())),
        tuple(runtime.required_sheets),
        tuple(sorted(runtime.template_loops)),
    )


def _labels_from_project_rows(project_rows: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    for i, row in enumerate(project_rows):
        excel_row = int(row.get("_excel_row_number") or _excel_row_number(i))
        site = _s(row.get("site_name") or row.get("well_name"))
        client = _s(row.get("client_name"))
        proj = _s(row.get("project_number"))
        parts = [p for p in (site, client, proj) if p]
        labels.append(
            f"Excel row {excel_row}: {' — '.join(parts)}"
            if parts
            else f"Excel row {excel_row}"
        )
    return labels


class ReportEngine:
    """Load Excel + template bytes, build context, render docx."""

    def __init__(self, excel_bytes: bytes, template_bytes: bytes) -> None:
        if not validation_bypass_enabled():
            validate_excel_upload(excel_bytes)
            validate_template_upload(template_bytes)
        self.excel_bytes = excel_bytes
        self.template_bytes = template_bytes
        self._root_vars_cache: set[str] | None = None
        self._excel_cache_key: tuple[Any, ...] | None = None
        self._excel_cache: tuple[list[dict[str, Any]], dict[str, list]] | None = None

    def template_root_vars(self) -> set[str]:
        if self._root_vars_cache is None:
            self._root_vars_cache = collect_template_root_vars(self.template_bytes)
        return self._root_vars_cache

    def resolve_config(self, meta: dict[str, str] | None) -> ReportRuntimeConfig:
        return resolve_report_config(self.excel_bytes, self.template_bytes, meta)

    def coverage(self, meta: dict[str, str] | None) -> "TemplateCoverage":
        from template_tools import TemplateCoverage

        ctx = self.build_context(meta)
        needed = self.template_root_vars()
        ctx_keys = list_keys_from_context(ctx)
        counts = table_row_counts(ctx)
        return TemplateCoverage(
            template_vars=needed,
            context_keys=ctx_keys,
            matched=sorted(needed & ctx_keys),
            missing_in_data=sorted(needed - ctx_keys),
            unused_in_template=sorted(ctx_keys - needed),
            lab_row_count=counts.get("lab_results", 0),
            drilling_waste_row_count=counts.get("drilling_waste", 0),
            storage_tanks_row_count=counts.get("storage_tanks", 0),
            table_row_counts=counts,
        )

    def _get_parsed_excel(
        self, runtime: ReportRuntimeConfig
    ) -> tuple[list[dict[str, Any]], dict[str, list]]:
        key = _runtime_cache_key(runtime)
        if self._excel_cache_key == key and self._excel_cache is not None:
            return self._excel_cache
        parsed = self._read_excel(runtime)
        self._excel_cache_key = key
        self._excel_cache = parsed
        return parsed

    def _read_excel(
        self, runtime: ReportRuntimeConfig
    ) -> tuple[list[dict[str, Any]], dict[str, list]]:
        bio = io.BytesIO(self.excel_bytes)
        with pd.ExcelFile(bio, engine="openpyxl") as xl:
            names = xl.sheet_names
            for req in runtime.required_sheets:
                if req not in names:
                    raise ValueError(
                        f"Report type '{runtime.report_type}' requires sheet "
                        f"'{req}'. Found: {names}"
                    )
            if runtime.require_lab_sheet and LAB_SHEET not in names:
                raise ValueError(
                    f"Report type '{runtime.report_type}' requires sheet "
                    f"'{LAB_SHEET}'. Found: {names}"
                )
            primary = runtime.primary_sheet
            if primary not in names:
                raise ValueError(
                    f"Missing primary sheet '{primary}'. Found: {names}"
                )
            project_df = xl.parse(primary, header=0)
            if project_df.empty:
                raise ValueError(
                    f"Sheet '{primary}' has no data rows "
                    "(row 1 = headers, row 2+ = values)."
                )
            if len(project_df.columns) > MAX_PROJECT_COLUMNS:
                project_df = project_df.iloc[:, :MAX_PROJECT_COLUMNS]
            project_rows = _project_rows_from_df(project_df)
            if not project_rows:
                raise ValueError(
                    f"Sheet '{primary}' has no data rows "
                    "(row 1 = headers, row 2+ = values)."
                )
            if len(project_rows) > MAX_PROJECT_ROWS:
                project_rows = project_rows[:MAX_PROJECT_ROWS]

            lists: dict[str, list] = {}
            lab_var = runtime.lab_loop_variable or "lab_results"
            for sheet_name, loop_var in runtime.sheet_to_loop.items():
                if sheet_name == primary or sheet_name not in names:
                    continue
                df = xl.parse(sheet_name, header=0)
                if loop_var == lab_var or loop_var == "lab_results":
                    lists[loop_var] = _lab_frame_to_records(df)
                else:
                    lists[loop_var] = _dataframe_to_records(df)

            for loop_var in runtime.template_loops:
                lists.setdefault(loop_var, [])

            if runtime.require_lab_sheet and LAB_SHEET in names:
                lists.setdefault(
                    lab_var,
                    _lab_frame_to_records(xl.parse(LAB_SHEET, header=0)),
                )

        return project_rows, lists

    def project_row_count(self, meta: dict[str, str] | None = None) -> int:
        runtime = self.resolve_config(meta)
        project_rows, _ = self._get_parsed_excel(runtime)
        return len(project_rows)

    def project_row_labels(self, meta: dict[str, str] | None = None) -> list[str]:
        runtime = self.resolve_config(meta)
        project_rows, _ = self._get_parsed_excel(runtime)
        return _labels_from_project_rows(project_rows)

    def build_context(
        self,
        meta: dict[str, str] | None,
        *,
        project_row_index: int = 0,
        parsed_excel: tuple[list[dict[str, Any]], dict[str, list]] | None = None,
    ) -> dict[str, Any]:
        meta = sanitize_meta(meta)
        runtime = self.resolve_config(meta)
        if parsed_excel is not None:
            project_rows, list_data = parsed_excel
        else:
            project_rows, list_data = self._get_parsed_excel(runtime)
        if project_row_index < 0 or project_row_index >= len(project_rows):
            raise ValueError(
                f"ProjectData data row {project_row_index + 1} of {len(project_rows)} "
                f"is out of range (use Excel rows 2–{len(project_rows) + 1})."
            )
        project = dict(project_rows[project_row_index])
        excel_row = int(project.pop("_excel_row_number", _excel_row_number(project_row_index)))
        ctx: dict[str, Any] = {**project}
        ctx["_project_row_index"] = project_row_index
        ctx["_excel_row_number"] = excel_row
        ctx["_project_row_count"] = len(project_rows)
        for k, v in meta.items():
            nk = _norm_key(k)
            if nk:
                ctx[nk] = v if v is not None else ""
        from phrase_resolver import apply_phrase_resolution

        phrase_warnings = apply_phrase_resolution(
            ctx, project, self.excel_bytes, meta=meta
        )
        if phrase_warnings:
            ctx["_phrase_warnings"] = phrase_warnings
        for loop_var, rows in list_data.items():
            ctx[loop_var] = _filter_records_for_project(rows, project)
        for loop_var in runtime.template_loops:
            ctx.setdefault(loop_var, [])
        for legacy in ("lab_results", "drilling_waste", "storage_tanks"):
            ctx.setdefault(legacy, [])
        ctx["_report_type"] = runtime.report_type
        phase = str(ctx.get("report_phase", "")).strip()
        if (
            runtime.narrative_profile == "phase1_alberta"
            and phase == "Phase 1"
            and not _s(ctx.get("executive_summary"))
        ):
            ctx["executive_summary"] = build_phase1_executive_summary(ctx)
            ctx["_executive_summary_auto_generated"] = True
        return ctx

    def missing_template_vars(
        self, context: dict[str, Any]
    ) -> list[str]:
        needed = self.template_root_vars()
        missing: list[str] = []
        for name in sorted(needed):
            if name not in context:
                missing.append(name)
        return missing

    def dry_run(
        self,
        meta: dict[str, str] | None = None,
        *,
        excel_filename: str = "",
        template_filename: str = "",
        project_row_index: int = 0,
    ) -> tuple[dict[str, Any], list[str], "GenerationRecord"]:
        """
        Build context and manifest without rendering Word (preview / QA pattern).
        Does not fill missing template variables with empty strings.
        """
        from field_validation import contract_warnings
        from provenance import GenerationRecord, build_generation_record

        context = self.build_context(meta, project_row_index=project_row_index)
        auto_exec = context.pop("_executive_summary_auto_generated", False)
        phrase_warnings = context.pop("_phrase_warnings", [])
        row_count = int(context.pop("_project_row_count", 1))
        context.pop("_project_row_index", None)
        excel_row = int(context.pop("_excel_row_number", _excel_row_number(project_row_index)))
        context, clamp_warnings = clamp_context(context)
        warnings: list[str] = list(clamp_warnings) + list(phrase_warnings)
        if row_count > 1:
            warnings.append(
                f"ProjectData has {row_count} site row(s) (Excel rows 2+); "
                f"this preview uses Excel row {excel_row} only."
            )
        if auto_exec:
            warnings.append(
                "Executive summary auto-generated from ProjectData (Signum-style structure)."
            )
        missing = self.missing_template_vars(context)
        for m in missing:
            warnings.append(
                f"Template uses '{{{{ {m} }}}}' but no Excel/sidebar value yet."
            )
        warnings.extend(
            contract_warnings(
                context,
                report_phase=str((meta or {}).get("report_phase", "")),
                report_type=str(context.get("_report_type", "")),
            )
        )
        try:
            coverage = self.coverage(meta)
        except (ValueError, SecurityError) as e:
            coverage = None
            warnings.append(str(e))
        record = build_generation_record(
            excel_bytes=self.excel_bytes,
            template_bytes=self.template_bytes,
            meta=meta,
            coverage=coverage,
            warnings=warnings,
            missing_variables=missing,
            excel_filename=excel_filename,
            template_filename=template_filename,
            dry_run=True,
            template_source_format=str((meta or {}).get("template_source_format", "")),
        )
        return context, warnings, record

    def render(
        self, meta: dict[str, str] | None = None,
        *,
        excel_filename: str = "",
        template_filename: str = "",
        project_row_index: int = 0,
        parsed_excel: tuple[list[dict[str, Any]], dict[str, list]] | None = None,
        include_coverage: bool = True,
    ) -> tuple[bytes, list[str], dict[str, Any], "GenerationRecord"]:
        """
        Returns (docx_bytes, warnings, context).
        Warnings include template variables not supplied by Excel/meta
        (filled with empty string for render).
        """
        context = self.build_context(
            meta,
            project_row_index=project_row_index,
            parsed_excel=parsed_excel,
        )
        auto_exec = context.pop("_executive_summary_auto_generated", False)
        phrase_warnings = context.pop("_phrase_warnings", [])
        context.pop("_project_row_count", None)
        context.pop("_project_row_index", None)
        context.pop("_excel_row_number", None)
        context, clamp_warnings = clamp_context(context)
        warnings: list[str] = list(clamp_warnings) + list(phrase_warnings)
        if auto_exec:
            warnings.append(
                "Executive summary auto-generated from ProjectData (Signum-style structure). "
                "Review before client delivery."
            )
        for m in self.missing_template_vars(context):
            warnings.append(
                f"Template uses '{{{{ {m} }}}}' but no Excel/sidebar value; "
                "rendering with empty string."
            )
            context[m] = ""

        render_ctx = {
            k: v for k, v in context.items() if not str(k).startswith("_")
        }

        tpl_bio = io.BytesIO(self.template_bytes)
        doc = DocxTemplate(tpl_bio)
        env = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False)
        try:
            doc.render(render_ctx, jinja_env=env)
        except TemplateError as e:
            raise ValueError(
                "Template rendering failed. Check Jinja2 tags and table loops "
                "in your Word template."
            ) from e
        out = io.BytesIO()
        doc.save(out)
        docx_bytes = out.getvalue()
        validate_rendered_output(docx_bytes)
        from provenance import build_generation_record

        coverage = None
        if include_coverage:
            try:
                coverage = self.coverage(meta)
            except (ValueError, SecurityError):
                coverage = None
        record = build_generation_record(
            excel_bytes=self.excel_bytes,
            template_bytes=self.template_bytes,
            meta=meta,
            coverage=coverage,
            warnings=warnings,
            missing_variables=self.missing_template_vars(context),
            output_bytes=docx_bytes,
            excel_filename=excel_filename,
            template_filename=template_filename,
            dry_run=False,
            template_source_format=str((meta or {}).get("template_source_format", "")),
        )
        return docx_bytes, warnings, context, record

    def render_batch(
        self,
        meta: dict[str, str] | None = None,
        *,
        excel_filename: str = "",
        template_filename: str = "",
    ) -> list[BatchReportResult]:
        """Render one .docx per non-blank ProjectData row."""
        runtime = self.resolve_config(meta)
        project_rows, list_data = self._get_parsed_excel(runtime)
        n = len(project_rows)
        if n > MAX_BATCH_REPORTS:
            raise ValueError(
                f"Too many ProjectData rows ({n}). Maximum batch size is "
                f"{MAX_BATCH_REPORTS} reports per run."
            )
        labels = _labels_from_project_rows(project_rows)
        parsed = (project_rows, list_data)
        results: list[BatchReportResult] = []
        for i in range(n):
            excel_row = int(
                project_rows[i].get("_excel_row_number", _excel_row_number(i))
            )
            docx_bytes, warnings, context, record = self.render(
                meta,
                excel_filename=excel_filename,
                template_filename=template_filename,
                project_row_index=i,
                parsed_excel=parsed,
                include_coverage=(i == n - 1),
            )
            filename = suggested_download_name(
                context, meta or {}, project_row_index=i, batch_size=n
            )
            record.output_filename = filename
            results.append(
                BatchReportResult(
                    project_row_index=i,
                    excel_row_number=excel_row,
                    docx_bytes=docx_bytes,
                    warnings=list(warnings),
                    context=context,
                    record=record,
                    filename=filename,
                    row_label=labels[i] if i < len(labels) else f"Excel row {excel_row}",
                )
            )
        return results


def suggested_download_name(
    context: dict[str, Any],
    meta: dict[str, str],
    *,
    project_row_index: int | None = None,
    batch_size: int = 1,
) -> str:
    """Build a safe .docx filename from site/phase/date (unique per batch row)."""
    site = (
        str(context.get("site_name") or context.get("client_name") or "")
        .strip()
    )
    proj = str(context.get("project_number") or "").strip()
    phase = str(meta.get("report_phase") or "ESA").strip().replace(" ", "_")
    date = str(meta.get("date_of_issue") or context.get("report_month_year") or "")[:10]
    base = site or proj or "ESA"
    safe = re.sub(r"[^\w\-]+", "_", base).strip("_") or "ESA"
    parts = [safe]
    if proj and proj not in site:
        parts.append(re.sub(r"[^\w\-]+", "_", proj).strip("_"))
    parts.append(phase)
    if date:
        parts.append(re.sub(r"[^\w\-]+", "_", date).strip("_"))
    if batch_size > 1 and project_row_index is not None:
        parts.append(f"row{project_row_index + 1}")
    return sanitize_download_filename("_".join(parts) + ".docx")


def generate_sample_excel(path: str) -> None:
    """Write a minimal valid workbook (used by scripts/create_samples.py)."""
    project = pd.DataFrame(
        [
            {
                "site_name": "123 Example Road",
                "client_name": "Demo Client Ltd.",
                "project_number": "ESA-2026-001",
                "address": "Toronto, ON",
            }
        ]
    )
    lab = pd.DataFrame(
        [
            {
                "Analyte": "Benzene",
                "Result": 0.8,
                "Unit": "ug/L",
                "Criteria": 5.0,
                "Exceedance": "N",
            },
            {
                "Analyte": "TCE",
                "Result": 12.5,
                "Unit": "ug/L",
                "Criteria": 5.0,
                "Exceedance": "Y",
            },
            {
                "Analyte": "pH",
                "Result": 7.2,
                "Unit": "SU",
                "Criteria": "",
                "Exceedance": "",
            },
        ]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        project.to_excel(w, sheet_name=PROJECT_SHEET, index=False)
        lab.to_excel(w, sheet_name=LAB_SHEET, index=False)


def generate_production_excel(path: str) -> None:
    """
    Workbook aligned with typical Phase 2 ESA fields and bracket placeholders
  found in the production merge template (map to {{ jinja }} in Word).
    """
    project = pd.DataFrame(
        [
            {
                "client_name": "Client Full Name",
                "client_full_name": "Client Full Name",
                "site_name": "1XX/XX-XX-XXX-XX WXM",
                "site_address": "Site address, City, Province",
                "project_number": "22xxxxR",
                "report_title": "Phase 2 Environmental Site Assessment",
                "report_year": "2025",
                "consultant_name": "Ecoventure Inc.",
                "company": "Ecoventure Inc.",
                "company_address": "Company address line",
                "keywords": "Phase 2 ESA, environmental assessment",
                "address": "Site address, City, Province",
                "lab_name": "Laboratory Name",
            }
        ]
    )
    lab = pd.DataFrame(
        [
            {
                "Analyte": "Benzene",
                "Result": 0.8,
                "Unit": "ug/L",
                "Criteria": 5.0,
                "Exceedance": "N",
            },
            {
                "Analyte": "TCE",
                "Result": 12.5,
                "Unit": "ug/L",
                "Criteria": 5.0,
                "Exceedance": "Y",
            },
        ]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        project.to_excel(w, sheet_name=PROJECT_SHEET, index=False)
        lab.to_excel(w, sheet_name=LAB_SHEET, index=False)


def generate_sample_template_docx(path: str) -> None:
    """Minimal docxtpl template with ProjectData vars + lab_results table."""
    doc = Document()
    doc.add_heading("Phase 2 ESA — Lab Summary (Sample)", level=0)
    doc.add_paragraph("Site: {{ site_name }}")
    doc.add_paragraph("Client: {{ client_name }}")
    doc.add_paragraph("Project No.: {{ project_number }}")
    doc.add_paragraph("Address: {{ address }}")
    doc.add_paragraph("Prepared by: {{ prepared_by }}")
    doc.add_paragraph("Date of issue: {{ date_of_issue }}")

    doc.add_paragraph("")
    doc.add_paragraph("Laboratory results:")

    # docxtpl table-row loop: static header, then for / data / endfor rows
    table = doc.add_table(rows=4, cols=4)
    table.style = "Table Grid"
    hdr = ["Analyte", "Result", "Unit", "Exceedance"]
    for i, h in enumerate(hdr):
        table.rows[0].cells[i].text = h
    table.rows[1].cells[0].merge(table.rows[1].cells[3])
    table.rows[1].cells[0].text = "{%tr for item in lab_results %}"
    table.rows[2].cells[0].text = "{{ item.analyte }}"
    table.rows[2].cells[1].text = "{{ item.result_display }}"
    table.rows[2].cells[2].text = "{{ item.unit }}"
    table.rows[2].cells[3].text = "{{ item.exceedance_flag }}"
    table.rows[3].cells[0].merge(table.rows[3].cells[3])
    table.rows[3].cells[0].text = "{%tr endfor %}"

    doc.save(path)


def _add_lab_results_table(doc: Document) -> None:
    """docxtpl table-row loop: static header, for/data/endfor rows."""
    doc.add_paragraph("")
    doc.add_paragraph("Laboratory results:")
    table = doc.add_table(rows=4, cols=4)
    table.style = "Table Grid"
    for i, h in enumerate(["Analyte", "Result", "Unit", "Exceedance"]):
        table.rows[0].cells[i].text = h
    table.rows[1].cells[0].merge(table.rows[1].cells[3])
    table.rows[1].cells[0].text = "{%tr for item in lab_results %}"
    table.rows[2].cells[0].text = "{{ item.analyte }}"
    table.rows[2].cells[1].text = "{{ item.result_display }}"
    table.rows[2].cells[2].text = "{{ item.unit }}"
    table.rows[2].cells[3].text = "{{ item.exceedance_flag }}"
    table.rows[3].cells[0].merge(table.rows[3].cells[3])
    table.rows[3].cells[0].text = "{%tr endfor %}"


def generate_production_starter_template_docx(path: str) -> None:
    """
    Tagged starter for production ESA reports — key fields + lab table.
    Use while converting the full merge template to Jinja2.
    """
    doc = Document()
    doc.add_heading("Phase 2 ESA — Production Starter", level=0)
    doc.add_paragraph("Client: {{ client_name }}")
    doc.add_paragraph("Site: {{ site_name }}")
    doc.add_paragraph("Address: {{ site_address }}")
    doc.add_paragraph("Project: {{ project_number }}")
    doc.add_paragraph("Company: {{ company }}")
    doc.add_paragraph("Company address: {{ company_address }}")
    doc.add_paragraph("Keywords: {{ keywords }}")
    doc.add_paragraph("Laboratory: {{ lab_name }}")
    doc.add_paragraph("Prepared by: {{ prepared_by }}")
    doc.add_paragraph("Date of issue: {{ date_of_issue }}")
    _add_lab_results_table(doc)
    doc.save(path)


def generate_production_template_docx(path: str) -> None:
    """
    Full tagged production template aligned with PRODUCTION_TEMPLATE_GUIDE.txt
    and samples/production_data.xlsx (bracket placeholders as Jinja tags).
    """
    doc = Document()
    doc.add_heading("{{ report_title }}", level=0)
    doc.add_paragraph("Client: {{ client_full_name }}")
    doc.add_paragraph("Site / project: {{ site_name }}")
    doc.add_paragraph("Address: {{ site_address }}")
    doc.add_paragraph("Project number: {{ project_number }}")
    doc.add_paragraph("Report year: {{ report_year }}")
    doc.add_paragraph("Consultant: {{ consultant_name }}")
    doc.add_paragraph("Company: {{ company }}")
    doc.add_paragraph("Company address: {{ company_address }}")
    doc.add_paragraph("Keywords: {{ keywords }}")
    doc.add_paragraph("Laboratory: {{ lab_name }}")
    doc.add_paragraph("Prepared by: {{ prepared_by }}")
    doc.add_paragraph("Date of issue: {{ date_of_issue }}")
    _add_lab_results_table(doc)
    doc.save(path)


# Bracket placeholders in the production merge doc → Jinja (see PRODUCTION_TEMPLATE_GUIDE.txt)
PRODUCTION_BRACKET_REPLACEMENTS: dict[str, str] = {
    "[Company]": "{{ company }}",
    "[Company Address]": "{{ company_address }}",
    "[Keywords]": "{{ keywords }}",
    "[LAB]": "{{ lab_name }}",
    "Client Full Name": "{{ client_full_name }}",
}


def _add_docx_table_loop(
    doc: Document,
    title: str,
    loop_var: str,
    headers: list[str],
    item_fields: list[str],
) -> None:
    """docxtpl table-row loop with static header row."""
    doc.add_paragraph("")
    doc.add_paragraph(title)
    ncols = len(headers)
    table = doc.add_table(rows=4, cols=ncols)
    table.style = "Table Grid"
    for i, h in enumerate(headers):
        table.rows[0].cells[i].text = h
    table.rows[1].cells[0].merge(table.rows[1].cells[ncols - 1])
    table.rows[1].cells[0].text = f"{{%tr for item in {loop_var} %}}"
    for i, field in enumerate(item_fields):
        table.rows[2].cells[i].text = f"{{{{ item.{field} }}}}"
    table.rows[3].cells[0].merge(table.rows[3].cells[ncols - 1])
    table.rows[3].cells[0].text = "{%tr endfor %}"


def generate_phase1_alberta_excel(path: str) -> None:
    """Alberta O&G Phase I workbook — Ecoventure Inc. sample (Signum-style executive summary)."""
    row = {
        "client_name": "Example Energy Ltd.",
        "consultant_name": ECOVENTURE_CONSULTANT,
        "company": ECOVENTURE_CONSULTANT,
        "well_name": "Example 4D Windy 4-4-49-4",
        "site_name": "Example 4D Windy 4-4-49-4",
        "uwi": "00/04-04-049-04W4/0",
        "project_number": "ESA-P1-2017-001",
        "report_title": "Phase I Environmental Site Assessment",
        "report_month_year": "March 2017",
        "qp_names": "Ecoventure QP (P.Eng.); Ecoventure QP (R.T.Ag.)",
        "spud_date": "15-Mar-2004",
        "cased_date": "17-Mar-2004",
        "final_drill_date": "19-Jun-2004",
        "well_depth_m": "710",
        "well_status": "suspended",
        "reentry": "Yes",
        "reentry_detail": (
            "The well was re-entered in June 2004 and drilled to a total depth of 710 metres (m), "
            "and the well is currently suspended"
        ),
        "production_fluid": "gas with water",
        "aer_waste_compliance_option": "Option 1 (AER, 2014)",
        "drilling_waste_summary": (
            "110 m3 of drilling waste (surface mud and fasthole mud) was disposed of via LWD at "
            "SW1/4 04-049-04 W4M, 35 m3 of mainhole drilling mud was landsprayed at SE-09-049-04 W4M, "
            "3 m3 of shale was landspread onsite, and 60 m3 of mainhole drilling mud was hauled to "
            "the remote site at Example 10-04-048-06 W4M"
        ),
        "phase2_drilling_waste_required": "No",
        "phase2_esa_required": "Yes",
        "client_phase_keyword": "Phase II",
        "site_visit_completed": "No",
        "air_photo_observations": (
            "The 2015 historical air photo shows the well centre and a possible disturbance area "
            "southeast of well centre for the containment berm and tanks"
        ),
        "investigations_recommended": (
            "well centre and the production areas be investigated"
        ),
        "infrastructure_summary": (
            "Access road, teardrop, wellhead, containment berm for production tanks"
        ),
        "spills_releases": "No",
        "conclusions_recommendations": (
            "Investigate well centre and production areas. Phase II ESA recommended."
        ),
        "drilling_waste_intro_selected": "option_1_aer",
        "site_recon_intro_selected": "not_completed",
        "phase2_recommendation_selected": "recommended",
    }
    row["executive_summary"] = build_phase1_executive_summary(row)
    from phrase_resolver import list_phrase_definitions, resolve_phrase_text

    for phrase_key, option_id in [
        ("drilling_waste_intro", row["drilling_waste_intro_selected"]),
        ("site_recon_intro", row["site_recon_intro_selected"]),
        ("phase2_recommendation", row["phase2_recommendation_selected"]),
    ]:
        text = resolve_phrase_text(phrase_key, option_id)
        if text:
            row[phrase_key] = text
    project = pd.DataFrame([row])
    waste = pd.DataFrame(
        [
            {
                "mud_type": "Gel Chem",
                "volume_m3": "208",
                "disposal_method": "LWD, landspray, landspread onsite, remote site",
                "location": "SW1/4 04-049-04 W4M; SE-09-049-04 W4M; onsite; remote site",
            },
        ]
    )
    tanks = pd.DataFrame(
        [
            {
                "tank_type": "Above ground tank",
                "content": "Produced water",
                "location": "SE of well centre",
                "capacity_m3": "Unknown",
            },
        ]
    )
    from phrase_resolver import PHRASE_CATALOG_SHEET, list_phrase_definitions

    catalog_rows: list[dict[str, str]] = []
    for phrase_key, spec in sorted(list_phrase_definitions().items()):
        for opt in spec.get("options", []):
            catalog_rows.append(
                {
                    "phrase_key": phrase_key,
                    "option_id": str(opt.get("id", "")),
                    "text": str(opt.get("text", "")),
                }
            )
    phrase_catalog = pd.DataFrame(catalog_rows)

    with pd.ExcelWriter(path, engine="openpyxl") as w:
        project.to_excel(w, sheet_name=PROJECT_SHEET, index=False)
        waste.to_excel(w, sheet_name=DRILLING_WASTE_SHEET, index=False)
        tanks.to_excel(w, sheet_name=STORAGE_TANKS_SHEET, index=False)
        if not phrase_catalog.empty:
            phrase_catalog.to_excel(w, sheet_name=PHRASE_CATALOG_SHEET, index=False)


def generate_phase1_alberta_template_docx(path: str) -> None:
    """Alberta Phase I ESA Word template — Ecoventure Inc."""
    doc = Document()
    doc.add_heading("{{ report_title }}", level=0)
    doc.add_paragraph("PREPARED FOR: {{ client_name }}")
    doc.add_paragraph("{{ well_name }}")
    doc.add_paragraph("{{ uwi }}")
    doc.add_paragraph("")
    doc.add_paragraph("PREPARED BY:")
    doc.add_paragraph("{{ consultant_name }}")
    doc.add_paragraph("{{ qp_names }}")
    doc.add_paragraph("{{ report_month_year }}")
    doc.add_heading("Executive Summary", level=1)
    doc.add_paragraph("{{ executive_summary }}")
    doc.add_heading("AER Schedule Two — Phase I ESA (summary)", level=1)
    doc.add_paragraph("Well: {{ well_name }} | UWI: {{ uwi }}")
    doc.add_paragraph("Spud: {{ spud_date }} | Final drill: {{ final_drill_date }} | TD: {{ well_depth_m }} m")
    doc.add_paragraph("Status: {{ well_status }} | Re-entry: {{ reentry }} | Fluid: {{ production_fluid }}")
    doc.add_paragraph("Drilling waste (AER): {{ aer_waste_compliance_option }}")
    doc.add_paragraph("{{ drilling_waste_intro }}")
    doc.add_paragraph("{{ drilling_waste_summary }}")
    doc.add_paragraph("{{ site_recon_intro }}")
    doc.add_paragraph("Infrastructure: {{ infrastructure_summary }}")
    doc.add_paragraph("Spills/releases: {{ spills_releases }}")
    doc.add_paragraph("Site visit completed: {{ site_visit_completed }}")
    doc.add_paragraph("Phase II ESA required: {{ phase2_esa_required }}")
    doc.add_paragraph("{{ phase2_recommendation }}")
    doc.add_heading("Conclusions and Recommendations", level=1)
    doc.add_paragraph("{{ conclusions_recommendations }}")
    doc.add_paragraph("Prepared by: {{ prepared_by }} | Date: {{ date_of_issue }}")
    _add_docx_table_loop(
        doc,
        "Drilling waste disposal:",
        "drilling_waste",
        ["Mud type", "Volume (m3)", "Disposal method", "Location"],
        ["mud_type", "volume_m3", "disposal_method", "location"],
    )
    _add_docx_table_loop(
        doc,
        "Storage tanks:",
        "storage_tanks",
        ["Type", "Content", "Location", "Capacity (m3)"],
        ["tank_type", "content", "location", "capacity_m3"],
    )
    doc.add_paragraph("")
    doc.add_paragraph(
        "Appendices A–F (AER forms, ABADATA, air photos, drilling waste, survey, "
        "land title) are attached separately to the deliverable package."
    )
    doc.save(path)


def generate_custom_demo_excel(path: str) -> None:
    """Minimal custom report workbook (template_driven profile demo)."""
    project = pd.DataFrame(
        [
            {
                "client_name": "Custom Client Ltd.",
                "site_name": "Demo Site 100",
                "report_title": "Custom Environmental Report",
                "summary_text": "This report uses a flexible profile and custom table sheet.",
            }
        ]
    )
    observations = pd.DataFrame(
        [
            {"observation": "Stressed vegetation near access road", "severity": "Low"},
            {"observation": "Stained soil near tank berm", "severity": "Medium"},
        ]
    )
    config = pd.DataFrame(
        [
            {"key": "report_type", "value": "template_driven"},
            {"key": "map_Observations", "value": "observations"},
        ]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        project.to_excel(w, sheet_name=PROJECT_SHEET, index=False)
        observations.to_excel(w, sheet_name="Observations", index=False)
        config.to_excel(w, sheet_name="ReportConfig", index=False)


def generate_custom_demo_template_docx(path: str) -> None:
    """Word template with scalar fields + observations table loop."""
    doc = Document()
    doc.add_heading("{{ report_title }}", level=0)
    doc.add_paragraph("Client: {{ client_name }}")
    doc.add_paragraph("Site: {{ site_name }}")
    doc.add_paragraph("{{ summary_text }}")
    doc.add_paragraph("Prepared by: {{ prepared_by }} | Date: {{ date_of_issue }}")
    _add_docx_table_loop(
        doc,
        "Field observations:",
        "observations",
        ["Observation", "Severity"],
        ["observation", "severity"],
    )
    doc.save(path)
