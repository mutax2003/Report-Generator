"""Cross-check merge context for internal consistency."""

from __future__ import annotations

import re
from typing import Any

from ai.client import complete_json, prompt_version
from ai.config import openai_model
from ai.docx_extract import extract_docx_full_text
from ai.models import AiAudit, ConsistencyFinding


def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def check_consistency(
    context: dict[str, Any],
    *,
    template_bytes: bytes | None = None,
    use_llm: bool = False,
) -> tuple[list[ConsistencyFinding], AiAudit]:
    findings: list[ConsistencyFinding] = []
    audit = AiAudit(features=["consistency_checker"], prompt_version=prompt_version())

    site = _norm(context.get("site_name"))
    addr = _norm(context.get("site_address") or context.get("address"))
    client = _norm(context.get("client_name") or context.get("client_full_name"))

    if site and addr and site not in addr and addr not in site:
        if not any(tok in addr for tok in site.split() if len(tok) > 3):
            findings.append(
                ConsistencyFinding(
                    severity="warning",
                    code="site_address_mismatch",
                    message="Site name and address may refer to different locations.",
                    suggestion="Align site_name and site_address in ProjectData.",
                )
            )

    lab = context.get("lab_results")
    if isinstance(lab, list):
        seen: set[str] = set()
        for i, row in enumerate(lab):
            if not isinstance(row, dict):
                continue
            analyte = _norm(row.get("analyte"))
            if analyte in seen:
                findings.append(
                    ConsistencyFinding(
                        severity="warning",
                        code="duplicate_analyte",
                        message=f"Duplicate analyte at lab row {i + 1}: {row.get('analyte')}.",
                        suggestion="Remove or merge duplicate rows in LabResults.",
                    )
                )
            seen.add(analyte)

            flag = str(row.get("exceedance_flag", "")).upper()
            result = row.get("result")
            criteria = row.get("criteria")
            try:
                r, c = float(result), float(criteria)
                numeric_exc = r > c
            except (TypeError, ValueError):
                numeric_exc = False
            if flag in ("Y", "YES") and not numeric_exc and criteria:
                findings.append(
                    ConsistencyFinding(
                        severity="info",
                        code="flag_vs_value",
                        message=(
                            f"Exceedance flag Yes for {row.get('analyte')} but "
                            "result ≤ criteria by numeric compare."
                        ),
                        suggestion="Verify Exceedance column and criteria units.",
                    )
                )

    def _well_ids(rows: list) -> set[str]:
        from ai.well_log_extract import normalize_well_id

        out: set[str] = set()
        for row in rows:
            if isinstance(row, dict):
                raw = str(row.get("well_id") or row.get("well") or "").strip()
                if raw:
                    out.add(normalize_well_id(raw))
        return out

    mw = context.get("monitoring_wells")
    wl = context.get("water_levels")
    gw = context.get("groundwater_results")
    if isinstance(mw, list) and isinstance(wl, list):
        ids_mw = _well_ids(mw)
        ids_wl = _well_ids(wl)
        if ids_mw and ids_wl and ids_wl - ids_mw:
            findings.append(
                ConsistencyFinding(
                    severity="warning",
                    code="water_level_unknown_well",
                    message=(
                        "WaterLevels contains well IDs not on MonitoringWells: "
                        + ", ".join(sorted(ids_wl - ids_mw)[:5])
                    ),
                    suggestion="Align well_id values across sheets.",
                )
            )
    if isinstance(mw, list) and isinstance(gw, list):
        ids_mw = _well_ids(mw)
        ids_gw = _well_ids(gw)
        if ids_mw and ids_gw and ids_gw - ids_mw:
            findings.append(
                ConsistencyFinding(
                    severity="warning",
                    code="gw_lab_unknown_well",
                    message=(
                        "GroundwaterLab results include well IDs not on MonitoringWells: "
                        + ", ".join(sorted(ids_gw - ids_mw)[:5])
                    ),
                    suggestion="Add missing wells or correct well_id spelling.",
                )
            )

    field_events = context.get("field_events")
    if isinstance(field_events, list):
        for i, row in enumerate(field_events):
            if not isinstance(row, dict):
                continue
            purge = str(row.get("purge_volume_l") or row.get("purge_volume") or "").strip()
            if not purge:
                findings.append(
                    ConsistencyFinding(
                        severity="info",
                        code="missing_purge_volume",
                        message=f"FieldNotes row {i + 1} has no purge volume recorded.",
                        suggestion="Add purge_volume_l for QA traceability.",
                    )
                )

    if template_bytes:
        doc_text = extract_docx_full_text(template_bytes).lower()
        if site and site not in doc_text and "{{ site_name }}" not in doc_text:
            findings.append(
                ConsistencyFinding(
                    severity="info",
                    code="site_not_in_template",
                    message="Site name value does not appear in template text (may use tags only).",
                )
            )

    if use_llm and context:
        data = complete_json(
            system=(
                'Return JSON: {"findings": [{"severity":"error|warning|info","code":"",'
                '"message":"","suggestion":""}]}. Max 8 findings. Facts from context only.'
            ),
            user=str(
                {
                    k: v
                    for k, v in context.items()
                    if k != "lab_results"
                }
            )[:12_000],
        )
        if data:
            audit.used_llm = True
            audit.model = openai_model()
            for item in data.get("findings", [])[:8]:
                if isinstance(item, dict):
                    findings.append(
                        ConsistencyFinding(
                            severity=item.get("severity", "info"),
                            code=str(item.get("code", "llm"))[:32],
                            message=str(item.get("message", ""))[:500],
                            suggestion=str(item.get("suggestion", ""))[:500],
                        )
                    )

    return findings, audit
