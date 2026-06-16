"""Automated health checks (run after changes: python scripts/health_check.py)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ok(n: int, name: str) -> tuple[bool, str]:
    total = len(CHECKS)
    try:
        return CHECKS[n - 1](), f"Check {n}/{total}: {name}"
    except Exception as e:
        return False, f"Check {n}/{total}: {name} — {e}"


def check_imports() -> bool:
    import app  # noqa: F401
    from engine import ECOVENTURE_CONSULTANT, ReportEngine  # noqa: F401
    from ui.folder_picker import folder_picker_available, pick_local_folder  # noqa: F401

    assert ECOVENTURE_CONSULTANT == "Ecoventure Inc."
    assert callable(pick_local_folder)
    assert isinstance(folder_picker_available(), bool)
    return True


def check_phase1_context() -> bool:
    from engine import ReportEngine

    xlsx = ROOT / "samples" / "phase1_alberta_data.xlsx"
    tpl = ROOT / "samples" / "phase1_alberta_template.docx"
    if not xlsx.is_file() or not tpl.is_file():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "create_samples.py")], check=True)
    engine = ReportEngine(xlsx.read_bytes(), tpl.read_bytes())
    ctx = engine.build_context({"report_phase": "Phase 1"})
    assert ctx["consultant_name"] == "Ecoventure Inc."
    assert len(ctx["drilling_waste"]) >= 1
    assert ctx["lab_results"] == []
    return True


def check_phase1_render() -> bool:
    from security import open_docx_zip, read_docx_xml_member, ZipReadBudget
    from engine import ReportEngine

    xlsx = ROOT / "samples" / "phase1_alberta_data.xlsx"
    tpl = ROOT / "samples" / "phase1_alberta_template.docx"
    docx, _, _, _ = ReportEngine(xlsx.read_bytes(), tpl.read_bytes()).render(
        meta={"report_phase": "Phase 1", "prepared_by": "Ecoventure"},
    )
    with open_docx_zip(docx) as zf:
        xml = read_docx_xml_member(zf, "word/document.xml", ZipReadBudget())
    assert "Ecoventure" in xml
    return True


def check_phase2_requires_lab() -> bool:
    from engine import ReportEngine

    p1 = ROOT / "samples" / "phase1_alberta_data.xlsx"
    tpl = ROOT / "samples" / "sample_template.docx"
    engine = ReportEngine(p1.read_bytes(), tpl.read_bytes())
    try:
        engine.build_context({"report_phase": "Phase 2"})
        return False
    except ValueError as e:
        return "LabResults" in str(e)


def check_preflight_phase1() -> bool:
    from template_tools import run_preflight

    xlsx = ROOT / "samples" / "phase1_alberta_data.xlsx"
    tpl = ROOT / "samples" / "phase1_alberta_template.docx"
    pre = run_preflight(xlsx.read_bytes(), tpl.read_bytes(), {"report_phase": "Phase 1"})
    assert pre.can_generate, pre.errors
    assert pre.coverage and pre.coverage.drilling_waste_row_count >= 1
    return True


def check_narrative_phase1() -> bool:
    from ai.narrative import draft_narratives, sections_for_phase

    assert "drilling_waste" in sections_for_phase("Phase 1")
    drafts, _ = draft_narratives(
        {
            "report_phase": "Phase 1",
            "client_name": "Test",
            "consultant_name": "Ecoventure Inc.",
            "executive_summary": "Ecoventure prepared this Phase I ESA.",
        },
        use_llm=False,
    )
    assert any(d.section == "executive_summary" for d in drafts)
    return True


def check_demo_render() -> bool:
    from engine import ReportEngine

    xlsx = ROOT / "samples" / "sample_data.xlsx"
    tpl = ROOT / "samples" / "sample_template.docx"
    docx, _, _, _ = ReportEngine(xlsx.read_bytes(), tpl.read_bytes()).render(
        meta={"report_phase": "Phase 2"},
    )
    return len(docx) > 1000


def check_missing_vars_filled() -> bool:
    from engine import ReportEngine

    tpl = ROOT / "samples" / "sample_template.docx"
    xlsx = ROOT / "samples" / "sample_data.xlsx"
    engine = ReportEngine(xlsx.read_bytes(), tpl.read_bytes())
    ctx = engine.build_context({"report_phase": "Phase 2"})
    missing = engine.missing_template_vars(ctx)
    docx, warnings, _, _ = engine.render(meta={"report_phase": "Phase 2"})
    if missing:
        assert any("empty string" in w for w in warnings)
    return len(docx) > 1000


def check_security_reject_swap() -> bool:
    from engine import ReportEngine

    xlsx = ROOT / "samples" / "sample_data.xlsx"
    tpl = ROOT / "samples" / "sample_template.docx"
    try:
        ReportEngine(tpl.read_bytes(), xlsx.read_bytes())
        return False
    except Exception:
        return True


def check_batch_render() -> bool:
    """Smoke test multi-row ProjectData without re-running the full unittest suite."""
    import io

    import pandas as pd

    from deliverable_pack import build_batch_reports_zip
    from engine import PROJECT_SHEET, ReportEngine

    bio = io.BytesIO()
    from engine import LAB_SHEET

    project = pd.DataFrame(
        [
            {"site_name": "Batch A", "client_name": "C1", "project_number": "BA-1"},
            {"site_name": "Batch B", "client_name": "C2", "project_number": "BB-1"},
        ]
    )
    lab = pd.DataFrame(
        [
            {
                "site_name": "Batch A",
                "analyte": "Benzene",
                "result": "0.01",
                "unit": "mg/L",
                "criteria": "0.005",
            },
        ]
    )
    with pd.ExcelWriter(bio, engine="openpyxl") as w:
        project.to_excel(w, sheet_name=PROJECT_SHEET, index=False)
        lab.to_excel(w, sheet_name=LAB_SHEET, index=False)
    tpl = ROOT / "samples" / "sample_template.docx"
    if not tpl.is_file():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "create_samples.py")], check=True)
    engine = ReportEngine(bio.getvalue(), tpl.read_bytes())
    batch = engine.render_batch(meta={"report_phase": "Phase 2"})
    assert len(batch) == 2
    assert batch[0].filename != batch[1].filename
    zip_bytes = build_batch_reports_zip(
        [(b.filename, b.docx_bytes, None) for b in batch]
    )
    assert len(zip_bytes) > 500
    return True


def check_groundwater_monitoring() -> bool:
    from engine import ReportEngine, generate_groundwater_monitoring_excel, generate_groundwater_monitoring_template_docx

    xlsx = ROOT / "samples" / "groundwater_monitoring_data.xlsx"
    tpl = ROOT / "samples" / "groundwater_monitoring_template.docx"
    if not xlsx.is_file() or not tpl.is_file():
        generate_groundwater_monitoring_excel(str(xlsx))
        generate_groundwater_monitoring_template_docx(str(tpl))
    engine = ReportEngine(xlsx.read_bytes(), tpl.read_bytes())
    ctx = engine.build_context(
        {"report_type": "groundwater_monitoring", "report_phase": "Phase 1"}
    )
    assert int(ctx.get("well_count", 0)) >= 1
    assert ctx.get("groundwater_results")
    docx, _, _, _ = engine.render(
        meta={"report_type": "groundwater_monitoring", "date_of_issue": "2026-05-28"},
    )
    return len(docx) > 5000


def check_phrase_catalog_gw() -> bool:
    from phrase_resolver import list_phrase_definitions

    phrases = list_phrase_definitions()
    for key in ("gw_program_intro", "gw_recommendations", "remediation_status"):
        assert key in phrases, f"missing phrase {key}"
    return True


def check_phase1_appendices() -> bool:
    from appendix_generator import render_phase1_appendices
    from engine import ReportEngine

    xlsx = ROOT / "samples" / "phase1_alberta_data.xlsx"
    tpl = ROOT / "samples" / "phase1_alberta_template.docx"
    meta = {"report_phase": "Phase 1", "report_type": "phase1_alberta", "prepared_by": "Ecoventure", "date_of_issue": "2026-06-10"}
    engine = ReportEngine(xlsx.read_bytes(), tpl.read_bytes())
    ctx = engine.build_context(meta)
    appendices, warnings = render_phase1_appendices(ctx, meta)
    labels = {a.label for a in appendices}
    assert labels == {"A", "D", "G"}, labels
    assert not warnings, warnings
    return True


def check_project_folder() -> bool:
    import tempfile

    from project_folder import enrich_project_folder, init_sample_project_folder, resolve_project_folder

    with tempfile.TemporaryDirectory(prefix="esa_health_") as tmp:
        folder = init_sample_project_folder(Path(tmp), source_user_test=False)
        resolved = resolve_project_folder(folder)
        assert resolved.excel_path.is_file()
        core1 = resolved.read_core_files()
        core2 = resolved.read_core_files()
        assert core1 is core2
        paths = enrich_project_folder(resolved, use_llm=False, modes=("inventory",))
        assert any(p.name == "preflight_report.md" for p in paths)
    return True


def check_source_ingest() -> bool:
    import tempfile

    from project_folder import (
        init_sample_project_folder,
        resolve_project_folder,
        source_ingest_for_folder,
    )

    with tempfile.TemporaryDirectory(prefix="esa_health_src_") as tmp:
        folder = init_sample_project_folder(Path(tmp), source_user_test=False)
        src = Path(tmp) / "source"
        src.mkdir(exist_ok=True)
        (src / "phase1_esa_report.pdf").write_bytes(b"%PDF-1.4\n")
        resolved = resolve_project_folder(folder)
        paths = source_ingest_for_folder(resolved, use_llm=False)
        assert any(p.name == "source_index.json" for p in paths)
        assert (resolved.ai_drafts_dir / "source_summaries.json").is_file()
    return True


CHECKS = [
    check_imports,
    check_phase1_context,
    check_phase1_render,
    check_phase1_appendices,
    check_phase2_requires_lab,
    check_preflight_phase1,
    check_narrative_phase1,
    check_demo_render,
    check_missing_vars_filled,
    check_security_reject_swap,
    check_batch_render,
    check_groundwater_monitoring,
    check_phrase_catalog_gw,
    check_project_folder,
    check_source_ingest,
]

CHECK_NAMES = [
    "imports",
    "phase1 context",
    "phase1 render",
    "phase1 appendices A/D/G",
    "phase2 lab guard",
    "preflight phase1",
    "narrative phase1",
    "demo render",
    "missing var warnings",
    "security swap reject",
    "batch render (2 rows)",
    "groundwater monitoring render",
    "phrase catalog GW keys",
    "project folder ingest",
    "source PDF ingest",
]


def main() -> int:
    failed = 0
    total = len(CHECKS)
    for i, name in enumerate(CHECK_NAMES, start=1):
        ok, msg = _ok(i, name)
        print(f"{'PASS' if ok else 'FAIL'} — {msg}")
        if not ok:
            failed += 1
    print(f"\n{total - failed}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
