"""
DWDA metal, salt, and DST calculation engine (Ecoventure xltm formula parity).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from compliance_helpers import has_value as _has_value
from compliance_helpers import parse_float as _parse_float

_SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "dwda_salt_additives.json"
_CALC_TOLERANCE = 0.05

_INGEST_KEYS = (
    "metal_barite_sacks",
    "metal_well_depth_m",
    "metal_mix_ratio",
    "metal_sacks_per_metre",
    "salt_naoh_equiv_total",
    "salt_waste_volume_m3",
    "salt_sacks_per_m3",
    "dst_resistivity_sacks_total",
    "dst_chloride_sacks_total",
)


@dataclass
class DwdaCalcRow:
    calc_type: str
    result_value: float | None
    objective: float | None
    passed: bool | None
    notes: str = ""
    input_json: str = ""


@dataclass
class DwdaCalcResult:
    metal_sacks_per_metre: float | None = None
    metal_pass: bool | None = None
    salt_naoh_equiv_total: float | None = None
    salt_waste_volume_m3: float | None = None
    salt_sacks_per_m3: float | None = None
    salt_max_sacks_per_m3: float | None = None
    salt_pass: bool | None = None
    dst_resistivity_sacks_total: float | None = None
    dst_chloride_sacks_total: float | None = None
    dst_pass: bool | None = None
    phase2_required: bool = False
    phase2_reasons: list[str] = field(default_factory=list)
    cross_check_warnings: list[str] = field(default_factory=list)
    summary: str = ""
    rows: list[DwdaCalcRow] = field(default_factory=list)

    def to_context_dict(self) -> dict[str, Any]:
        return {
            "dwda_metal_sacks_per_metre": self._fmt(self.metal_sacks_per_metre),
            "dwda_metal_pass": self._yn(self.metal_pass),
            "dwda_salt_naoh_equiv_total": self._fmt(self.salt_naoh_equiv_total),
            "dwda_salt_waste_volume_m3": self._fmt(self.salt_waste_volume_m3),
            "dwda_salt_sacks_per_m3": self._fmt(self.salt_sacks_per_m3),
            "dwda_salt_max_sacks_per_m3": self._fmt(self.salt_max_sacks_per_m3),
            "dwda_salt_pass": self._yn(self.salt_pass),
            "dwda_dst_resistivity_sacks_total": self._fmt(self.dst_resistivity_sacks_total),
            "dwda_dst_chloride_sacks_total": self._fmt(self.dst_chloride_sacks_total),
            "dwda_dst_pass": self._yn(self.dst_pass),
            "dwda_calc_phase2_required": "Yes" if self.phase2_required else "No",
            "dwda_calc_summary": self.summary,
            "dwda_calculations": [
                {
                    "calc_type": r.calc_type,
                    "result_value": self._fmt(r.result_value),
                    "objective": self._fmt(r.objective),
                    "pass": self._yn(r.passed),
                    "notes": r.notes,
                }
                for r in self.rows
            ],
        }

    @staticmethod
    def _fmt(val: float | None) -> str:
        if val is None:
            return ""
        if abs(val - round(val)) < 1e-9:
            return str(int(round(val)))
        return f"{val:.4f}".rstrip("0").rstrip(".")

    @staticmethod
    def _yn(val: bool | None) -> str:
        if val is None:
            return ""
        return "Yes" if val else "No"


@lru_cache(maxsize=1)
def load_salt_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _salt_constants() -> tuple[float, float, float, float]:
    schema = load_salt_schema()
    return (
        float(schema.get("metal_objective_sacks_per_m", 0.22)),
        float(schema.get("salt_max_sacks_per_m3_factor", 0.02)),
        float(schema.get("dst_chloride_divisor", 7600)),
        float(schema.get("dst_resistivity_default", 0.28)),
    )


def calc_metal_sacks_per_metre(
    barite_sacks: float,
    well_depth_m: float,
    mix_ratio: float,
) -> float | None:
    if well_depth_m <= 0 or mix_ratio <= 0:
        return None
    return barite_sacks / (well_depth_m * mix_ratio)


def calc_salt_naoh_equiv(additive_sacks: list[tuple[float, float]]) -> float:
    return sum(sacks * factor for sacks, factor in additive_sacks if sacks > 0)


def calc_salt_sacks_per_m3(naoh_equiv: float, waste_volume_m3: float) -> float | None:
    if waste_volume_m3 <= 0:
        return None
    return naoh_equiv / waste_volume_m3


def calc_salt_max_sacks_per_m3(well_depth_m: float) -> float | None:
    factor = _salt_constants()[1]
    if well_depth_m <= 0:
        return None
    return factor * well_depth_m


def calc_dst_volume_m3(pipe_id_mm: float, return_length_m: float) -> float:
    return (pipe_id_mm / 2000.0) ** 2 * math.pi * return_length_m


def calc_dst_resistivity_sacks(
    volume_m3: float,
    resistivity_factor: float,
    resistivity_ohms: float,
) -> float | None:
    if resistivity_ohms <= 0:
        return None
    return volume_m3 * resistivity_factor / resistivity_ohms


def calc_dst_chloride_sacks(volume_m3: float, chloride_mg_l: float) -> float:
    return volume_m3 * chloride_mg_l / _salt_constants()[2]


def _is_option_2(option: str) -> bool:
    opt = option.lower()
    return "option 2" in opt or "option_2" in opt


def _resolve_metric(
    ingested: float | None,
    computed: float | None,
    label: str,
    warnings: list[str],
) -> float | None:
    _cross_check(computed, ingested, label, warnings)
    return ingested if ingested is not None else computed


def _ingested_calc_values(context: dict[str, Any]) -> dict[str, float | None]:
    out = {k: _parse_float(context.get(k)) for k in _INGEST_KEYS}
    ingested = context.get("_ecoventure_ingested")
    if isinstance(ingested, dict):
        for k in _INGEST_KEYS:
            if out[k] is None:
                out[k] = _parse_float(ingested.get(k))
    for row in context.get("dwda_calculations") or ():
        if not isinstance(row, dict):
            continue
        ct = str(row.get("calc_type", "")).lower()
        rv = _parse_float(row.get("result_value"))
        if rv is None:
            continue
        if "metal" in ct and out["metal_sacks_per_metre"] is None:
            out["metal_sacks_per_metre"] = rv
        elif "salt" in ct and "m3" in ct and out["salt_sacks_per_m3"] is None:
            out["salt_sacks_per_m3"] = rv
        if out["metal_sacks_per_metre"] is not None and out["salt_sacks_per_m3"] is not None:
            break
    return out


def _cross_check(
    computed: float | None,
    ingested: float | None,
    label: str,
    warnings: list[str],
) -> None:
    if computed is None or ingested is None:
        return
    if ingested == 0 and computed == 0:
        return
    denom = max(abs(ingested), abs(computed), 1e-9)
    if abs(computed - ingested) / denom > _CALC_TOLERANCE:
        warnings.append(
            f"{label}: Python ({computed:.4f}) vs workbook ({ingested:.4f}) differ"
        )


def _evaluate_dst_rows(
    dst_rows: list[Any],
    dst_res: float | None,
    dst_cl: float | None,
    resistivity_default: float,
    chloride_divisor: float,
    warnings: list[str],
) -> tuple[float | None, float | None]:
    res_total = 0.0
    cl_total = 0.0
    for row in dst_rows:
        if not isinstance(row, dict):
            continue
        pid = _parse_float(row.get("pipe_id_mm"))
        length = _parse_float(row.get("return_length_m"))
        if pid is None or length is None:
            continue
        vol = calc_dst_volume_m3(pid, length)
        res_ohms = _parse_float(row.get("resistivity_ohms"))
        res_factor = _parse_float(row.get("resistivity_factor")) or resistivity_default
        if res_ohms:
            s = calc_dst_resistivity_sacks(vol, res_factor, res_ohms)
            if s and s > 0:
                res_total += s
        chloride = _parse_float(row.get("chloride_mg_l"))
        if chloride:
            s = vol * chloride / chloride_divisor
            if s > 0:
                cl_total += s
    out_res = dst_res
    out_cl = dst_cl
    if res_total > 0:
        _cross_check(res_total, dst_res, "DST resistivity sacks", warnings)
        if out_res is None:
            out_res = res_total
    if cl_total > 0:
        _cross_check(cl_total, dst_cl, "DST chloride sacks", warnings)
        if out_cl is None:
            out_cl = cl_total
    return out_res, out_cl


def _build_summary(result: DwdaCalcResult) -> str:
    parts: list[str] = []
    if result.metal_pass is not None:
        status = "pass" if result.metal_pass else "FAIL"
        parts.append(
            f"Metal: {status} ({result.metal_sacks_per_metre:.4f} sacks/m)"
        )
    if result.salt_pass is not None:
        status = "pass" if result.salt_pass else "FAIL"
        parts.append(f"Salt: {status} ({result.salt_sacks_per_m3:.4f} sacks/m³)")
    if result.dst_resistivity_sacks_total is not None:
        parts.append(f"DST resistivity: {result.dst_resistivity_sacks_total:.2f} sacks")
    if result.dst_chloride_sacks_total is not None:
        parts.append(f"DST chloride: {result.dst_chloride_sacks_total:.2f} sacks")
    return "; ".join(parts) if parts else "No DWDA calculation inputs present."


def evaluate_dwda_calculations(
    context: dict[str, Any],
    *,
    compliance_option: str = "",
) -> DwdaCalcResult:
    """Evaluate metal/salt/DST calculations from context or ingested workbook values."""
    metal_obj, salt_factor, chloride_div, resistivity_default = _salt_constants()
    ingested = _ingested_calc_values(context)
    option = (
        compliance_option or str(context.get("aer_waste_compliance_option", ""))
    ).lower()
    dst_rows = context.get("dst_returns") or []
    has_dst_rows = isinstance(dst_rows, list) and bool(dst_rows)
    if (
        not any(v is not None for v in ingested.values())
        and not has_dst_rows
        and not _is_option_2(option)
    ):
        return DwdaCalcResult(summary="No DWDA calculation inputs present.")

    result = DwdaCalcResult()
    warnings: list[str] = []
    reasons: list[str] = []

    well_depth = _parse_float(context.get("well_depth_m")) or ingested.get(
        "metal_well_depth_m"
    )

    barite = ingested.get("metal_barite_sacks")
    mix_ratio = ingested.get("metal_mix_ratio")
    metal_spm_ingested = ingested.get("metal_sacks_per_metre")
    metal_spm = metal_spm_ingested
    if barite is not None and well_depth is not None and mix_ratio is not None:
        metal_spm = _resolve_metric(
            metal_spm_ingested,
            calc_metal_sacks_per_metre(barite, well_depth, mix_ratio),
            "Metal sacks/m",
            warnings,
        )
    if metal_spm is not None:
        result.metal_sacks_per_metre = metal_spm
        result.metal_pass = metal_spm <= metal_obj
        result.rows.append(
            DwdaCalcRow(
                calc_type="metal_sacks_per_metre",
                result_value=metal_spm,
                objective=metal_obj,
                passed=result.metal_pass,
                notes="Barite sacks per metre (objective 0.22)",
            )
        )
        if not result.metal_pass:
            reasons.append(
                f"Metal calculation exceeds objective ({metal_spm:.4f} > {metal_obj} sacks/m)"
            )

    salt_naoh = ingested.get("salt_naoh_equiv_total")
    salt_vol = ingested.get("salt_waste_volume_m3")
    salt_spm_ingested = ingested.get("salt_sacks_per_m3")
    salt_spm = salt_spm_ingested
    if salt_naoh is not None and salt_vol is not None:
        salt_spm = _resolve_metric(
            salt_spm_ingested,
            calc_salt_sacks_per_m3(salt_naoh, salt_vol),
            "Salt sacks/m³",
            warnings,
        )
    if salt_naoh is not None:
        result.salt_naoh_equiv_total = salt_naoh
    if salt_vol is not None:
        result.salt_waste_volume_m3 = salt_vol
    if well_depth is not None:
        result.salt_max_sacks_per_m3 = salt_factor * well_depth
    if salt_spm is not None and result.salt_max_sacks_per_m3 is not None:
        result.salt_sacks_per_m3 = salt_spm
        result.salt_pass = salt_spm <= result.salt_max_sacks_per_m3
        result.rows.append(
            DwdaCalcRow(
                calc_type="salt_sacks_per_m3",
                result_value=salt_spm,
                objective=result.salt_max_sacks_per_m3,
                passed=result.salt_pass,
                notes="NaOH-equivalent sacks per m³ (max 0.02 × well depth)",
            )
        )
        if not result.salt_pass:
            reasons.append(
                f"Salt calculation exceeds objective ({salt_spm:.4f} > "
                f"{result.salt_max_sacks_per_m3:.4f} sacks/m³)"
            )

    dst_res = ingested.get("dst_resistivity_sacks_total")
    dst_cl = ingested.get("dst_chloride_sacks_total")
    if has_dst_rows:
        dst_res, dst_cl = _evaluate_dst_rows(
            dst_rows, dst_res, dst_cl, resistivity_default, chloride_div, warnings
        )
    if dst_res is not None:
        result.dst_resistivity_sacks_total = dst_res
    if dst_cl is not None:
        result.dst_chloride_sacks_total = dst_cl

    dst_total = result.dst_resistivity_sacks_total or result.dst_chloride_sacks_total
    if dst_total is not None:
        result.dst_pass = True
        result.rows.append(
            DwdaCalcRow(
                calc_type="dst_returns",
                result_value=dst_total,
                objective=None,
                passed=True,
                notes="DST return equivalent sacks (resistivity or chloride path)",
            )
        )
    elif _is_option_2(option):
        if not _has_value(dst_res) and not _has_value(dst_cl):
            reasons.append("Option 2: DST return calculation data insufficient")

    result.cross_check_warnings = warnings
    result.phase2_reasons = list(dict.fromkeys(reasons))
    result.phase2_required = bool(reasons)
    result.summary = _build_summary(result)
    return result


def apply_dwda_calc_to_context(
    context: dict[str, Any],
    *,
    compliance_option: str = "",
) -> dict[str, Any]:
    """Merge calculation results into render context."""
    calc = evaluate_dwda_calculations(context, compliance_option=compliance_option)
    out = {**context, **calc.to_context_dict(), "_dwda_calc_result": calc}
    if context.get("_ecoventure_workbook_template_id"):
        out["dwda_calc_source"] = "workbook"
    elif context.get("_ecoventure_ingested"):
        out["dwda_calc_source"] = "sheet"
    else:
        out["dwda_calc_source"] = "engine"
    if calc.cross_check_warnings:
        out["_dwda_calc_warnings"] = calc.cross_check_warnings
    return out
