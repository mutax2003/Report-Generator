"""
Report type profiles: map Excel sheets and Word template markups to merge context.

Supports built-in profiles (Phase I Alberta, Phase II) and template-driven custom reports.
Optional Excel sheet ``ReportConfig`` (key/value) overrides report_type and sheet mappings.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_SHEET = "ProjectData"
LAB_SHEET = "LabResults"
DRILLING_WASTE_SHEET = "DrillingWaste"
STORAGE_TANKS_SHEET = "StorageTanks"
DWDA_CHECKLIST_SHEET = "DwdaChecklist"
DWDA_CALCULATIONS_SHEET = "DwdaCalculations"


def _norm_key(name: str) -> str:
    s = str(name).strip()
    s = re.sub(r"\s+", "_", s)
    return s.lower()

_PROFILES_PATH = Path(__file__).resolve().parent / "schemas" / "report_profiles.json"
_cached_profiles: dict[str, Any] | None = None

LOOP_FOR_ITEM_RE = re.compile(
    r"for\s+item\s+in\s+([A-Za-z_]\w*)",
    re.IGNORECASE,
)


@dataclass
class ReportRuntimeConfig:
    """Resolved rules for one generate/preflight run."""

    report_type: str
    label: str
    primary_sheet: str
    sheet_to_loop: dict[str, str]  # Excel sheet name -> context list variable
    template_loops: set[str] = field(default_factory=set)
    required_sheets: list[str] = field(default_factory=list)
    require_lab_sheet: bool = False
    lab_loop_variable: str | None = "lab_results"
    narrative_profile: str = "generic"
    config_sheet: str = "ReportConfig"
    reserved_sheets: frozenset[str] = field(
        default_factory=lambda: frozenset({PROJECT_SHEET, "ReportConfig"})
    )


def load_profiles_catalog() -> dict[str, Any]:
    global _cached_profiles
    if _cached_profiles is None:
        with _PROFILES_PATH.open(encoding="utf-8") as f:
            _cached_profiles = json.load(f)
    return _cached_profiles


def list_report_profiles() -> list[tuple[str, str]]:
    """Return (id, label) for UI selectbox."""
    catalog = load_profiles_catalog()
    profiles = catalog.get("profiles", {})
    out: list[tuple[str, str]] = []
    for pid, spec in profiles.items():
        out.append((pid, str(spec.get("label", pid))))
    return out


def get_profile_spec(profile_id: str) -> dict[str, Any]:
    catalog = load_profiles_catalog()
    return dict(catalog.get("profiles", {}).get(profile_id, {}))


def get_profile_default_phase(profile_id: str) -> str:
    return str(get_profile_spec(profile_id).get("default_phase", "Phase 1"))


def profile_id_for_phase(phase: str) -> str:
    """Default profile when user changes report phase in the UI."""
    if phase.strip() == "Phase 2":
        return "phase2_esa"
    return "phase1_alberta"


_cached_field_contract: dict[str, Any] | None = None
_field_contract_mtime: float | None = None


def _load_field_contract() -> dict[str, Any]:
    global _cached_field_contract, _field_contract_mtime
    contract_path = Path(__file__).resolve().parent / "schemas" / "field_contract.json"
    mtime = contract_path.stat().st_mtime if contract_path.is_file() else 0.0
    if _cached_field_contract is None or _field_contract_mtime != mtime:
        with contract_path.open(encoding="utf-8") as f:
            _cached_field_contract = json.load(f)
        _field_contract_mtime = mtime
    return _cached_field_contract


def get_recommended_fields(report_type: str) -> list[str]:
    """Profile-scoped recommended ProjectData / sidebar fields (single maintenance source)."""
    spec = get_profile_spec(report_type)
    fields = spec.get("recommended_fields")
    if isinstance(fields, list) and fields:
        return [str(f) for f in fields]
    contract = _load_field_contract()
    project = contract.get("sheets", {}).get("ProjectData", {})
    out = list(project.get("recommended_all_phases", []))
    if report_type == "phase1_alberta":
        out.extend(project.get("recommended_phase_1_alberta_og", []))
    elif report_type == "phase2_esa":
        out.extend(project.get("recommended_phase_2", []))
    elif report_type == "groundwater_monitoring":
        pass
    elif report_type in ("reclamation_certificate", "phase3_remediation"):
        pass
    return out


def build_report_config_workbook_bytes(
    report_type: str,
    *,
    sheet_mappings: dict[str, str] | None = None,
    extra_rows: list[tuple[str, str]] | None = None,
) -> bytes:
    """Build a minimal Excel workbook with a ReportConfig sheet for download."""
    import io

    from openpyxl import Workbook

    spec = get_profile_spec(report_type)
    mappings = dict(sheet_mappings or spec.get("sheet_mappings") or {})
    wb = Workbook()
    ws = wb.active
    ws.title = "ReportConfig"
    ws.append(["key", "value"])
    ws.append(["report_type", report_type])
    ws.append(["primary_sheet", spec.get("primary_sheet", PROJECT_SHEET)])
    for sheet, loop_var in sorted(mappings.items()):
        ws.append([f"map_{sheet}", loop_var])
    for key, val in extra_rows or []:
        ws.append([key, val])
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def loops_from_block_tags(block_tags: set[str]) -> set[str]:
    """Extract loop variable names from Jinja block tags (e.g. ``tr for item in lab_results``)."""
    loops: set[str] = set()
    for tag in block_tags:
        for m in LOOP_FOR_ITEM_RE.finditer(tag):
            loops.add(m.group(1))
    return loops


def discover_template_loops(
    template_bytes: bytes,
    *,
    block_tags: set[str] | None = None,
) -> set[str]:
    """Find ``{%tr for item in var %}`` loop variables in the Word template."""
    if block_tags is not None:
        return loops_from_block_tags(block_tags)
    from template_tools import scan_template

    return loops_from_block_tags(scan_template(template_bytes).block_tags)


def _read_report_config_sheet(df: pd.DataFrame) -> dict[str, str]:
    """Parse key/value rows from ReportConfig sheet."""
    if df.empty or len(df.columns) < 2:
        return {}
    out: dict[str, str] = {}
    for _, row in df.iterrows():
        key = _norm_key(row.iloc[0])
        if not key:
            continue
        val = row.iloc[1]
        if val is None or (isinstance(val, float) and pd.isna(val)):
            continue
        out[key] = str(val).strip()
    return out


_EXCEL_META_CACHE_MAX = 16
_excel_meta_cache: dict[str, tuple[list[str], dict[str, str]]] = {}


def clear_excel_meta_cache() -> None:
    """Drop cached workbook meta reads (tests)."""
    _excel_meta_cache.clear()


def read_excel_meta(excel_bytes: bytes) -> tuple[list[str], dict[str, str]]:
    """One openpyxl pass: sheet names and optional ReportConfig key/value rows."""
    digest = hashlib.sha256(excel_bytes).hexdigest()
    hit = _excel_meta_cache.get(digest)
    if hit is not None:
        return hit
    result = _read_excel_meta_uncached(excel_bytes)
    if len(_excel_meta_cache) >= _EXCEL_META_CACHE_MAX:
        _excel_meta_cache.pop(next(iter(_excel_meta_cache)))
    _excel_meta_cache[digest] = result
    return result


def _read_excel_meta_uncached(excel_bytes: bytes) -> tuple[list[str], dict[str, str]]:
    import io

    catalog = load_profiles_catalog()
    config_sheet = catalog.get("config_sheet", "ReportConfig")
    bio = io.BytesIO(excel_bytes)
    with pd.ExcelFile(bio, engine="openpyxl") as xl:
        names = list(xl.sheet_names)
        if config_sheet not in names:
            return names, {}
        df = xl.parse(config_sheet, header=0)
    return names, _read_report_config_sheet(df)


_read_excel_meta = read_excel_meta  # backward-compatible alias


def read_excel_report_config(excel_bytes: bytes) -> dict[str, str]:
    """Load optional ReportConfig sheet from workbook bytes."""
    return read_excel_meta(excel_bytes)[1]


def _profile_id_from_meta(meta: dict[str, str] | None) -> str:
    meta = meta or {}
    explicit = str(meta.get("report_type", "")).strip()
    if explicit:
        return explicit
    phase = str(meta.get("report_phase", "")).strip()
    if phase == "Phase 1":
        return "phase1_alberta"
    return "phase2_esa"


def _sheet_name_for_loop(
    loop_var: str,
    sheet_names: list[str],
    sheet_to_loop: dict[str, str],
    primary_sheet: str,
    config_sheet: str,
) -> str | None:
    """Resolve Excel sheet name that feeds a template loop variable."""
    for sheet, var in sheet_to_loop.items():
        if var == loop_var:
            return sheet
    norm_loop = _norm_key(loop_var)
    for name in sheet_names:
        if name in (primary_sheet, config_sheet):
            continue
        if _norm_key(name) == norm_loop:
            return name
    return None


def resolve_report_config(
    excel_bytes: bytes,
    template_bytes: bytes,
    meta: dict[str, str] | None,
    *,
    template_loops: set[str] | None = None,
    excel_meta: tuple[list[str], dict[str, str]] | None = None,
) -> ReportRuntimeConfig:
    """
    Merge profile defaults, Excel ReportConfig sheet, template loop discovery, and sidebar meta.
    """
    catalog = load_profiles_catalog()
    profiles = catalog.get("profiles", {})
    config_sheet = catalog.get("config_sheet", "ReportConfig")
    primary_default = catalog.get("primary_sheet_default", PROJECT_SHEET)

    if excel_meta is None:
        sheet_names, excel_cfg = read_excel_meta(excel_bytes)
    else:
        sheet_names, excel_cfg = excel_meta
    report_type = excel_cfg.get("report_type") or _profile_id_from_meta(meta)
    if report_type not in profiles:
        report_type = "template_driven"

    spec = dict(profiles[report_type])
    label = str(spec.get("label", report_type))
    primary_sheet = excel_cfg.get("primary_sheet") or spec.get(
        "primary_sheet", primary_default
    )

    sheet_to_loop: dict[str, str] = {}
    for sheet, var in (spec.get("sheet_mappings") or {}).items():
        sheet_to_loop[str(sheet)] = str(var)

    for key, val in excel_cfg.items():
        if not val:
            continue
        if key.startswith("map_"):
            sheet_key = key[4:]
            for actual in sheet_names:
                if actual == sheet_key or _norm_key(actual) == _norm_key(sheet_key):
                    sheet_to_loop[actual] = val
                    break
            else:
                sheet_to_loop[sheet_key] = val

    if template_loops is None:
        template_loops = discover_template_loops(template_bytes)

    for loop in template_loops:
        if loop in sheet_to_loop.values():
            continue
        matched = _sheet_name_for_loop(
            loop, sheet_names, sheet_to_loop, primary_sheet, config_sheet
        )
        if matched:
            sheet_to_loop[matched] = loop

    if spec.get("auto_map_sheets"):
        for name in sheet_names:
            if name in (primary_sheet, config_sheet):
                continue
            if name not in sheet_to_loop:
                sheet_to_loop[name] = _norm_key(name)

    lab_loop = spec.get("lab_loop_variable")
    if lab_loop == "":
        lab_loop = None
    require_lab = bool(
        spec.get("lab_loop_variable") == "lab_results"
        and LAB_SHEET in (spec.get("required_sheets") or [])
    )
    if report_type == "phase2_esa":
        require_lab = True

    required = list(spec.get("required_sheets") or [primary_sheet])
    if primary_sheet not in required:
        required.insert(0, primary_sheet)

    reserved = frozenset({primary_sheet, config_sheet, PROJECT_SHEET})

    return ReportRuntimeConfig(
        report_type=report_type,
        label=label,
        primary_sheet=primary_sheet,
        sheet_to_loop=sheet_to_loop,
        template_loops=template_loops,
        required_sheets=required,
        require_lab_sheet=require_lab,
        lab_loop_variable=lab_loop if isinstance(lab_loop, str) else None,
        narrative_profile=str(spec.get("narrative_profile", "generic")),
        config_sheet=config_sheet,
        reserved_sheets=reserved,
    )


def excel_sheet_names(excel_bytes: bytes) -> list[str]:
    """Return workbook sheet names (single openpyxl pass)."""
    return read_excel_meta(excel_bytes)[0]


def list_keys_from_context(context: dict[str, Any]) -> set[str]:
    """Scalar keys only (exclude lists and internal keys)."""
    return {
        k
        for k, v in context.items()
        if not k.startswith("_") and not isinstance(v, list)
    }


def table_row_counts(context: dict[str, Any]) -> dict[str, int]:
    return {
        k: len(v)
        for k, v in context.items()
        if isinstance(v, list) and not k.startswith("_")
    }


# Backward-compatible sheet constants for docs/tests
KNOWN_TABLE_SHEETS = {
    LAB_SHEET: "lab_results",
    DRILLING_WASTE_SHEET: "drilling_waste",
    STORAGE_TANKS_SHEET: "storage_tanks",
}
