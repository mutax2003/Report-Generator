"""
Build phase1_devon_data.xlsx + phase1_devon_template.docx from the Devon 2017 reference.

Source (local): samples/00_04-04-049-04W4M Phase I report - Devon 2017.docx
Committed outputs use Ecoventure Inc. and anonymized client (Example Energy Ltd.).
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import ECOVENTURE_CONSULTANT, generate_phase1_alberta_excel  # noqa: E402
from phase1_narrative import build_phase1_executive_summary  # noqa: E402
from scripts.phase1_pdf_to_markup import tag_first_in_document_xml  # noqa: E402
from scripts.tag_production_template import tag_docx_xml  # noqa: E402
from template_tools import scan_template  # noqa: E402

SOURCE_DOCX = ROOT / "samples" / "00_04-04-049-04W4M Phase I report - Devon 2017.docx"
OUT_XLSX = ROOT / "samples" / "phase1_devon_data.xlsx"
OUT_TEMPLATE = ROOT / "samples" / "phase1_devon_template.docx"
OUT_GUIDE = ROOT / "samples" / "phase1_devon_tagging-guide.md"

DOCUMENT_XML = "word/document.xml"

EXEC_SUMMARY_START = (
    "Signum Consulting Ltd. (Signum) was contracted by Devon Canada Corporation"
)
EXEC_SUMMARY_END = "The Devon keyword is Phase II"

# Strings verified contiguous in document.xml (Word run boundaries).
SCALAR_TAG_REPLACEMENTS: dict[str, str] = {
    "DEVON CANADA CORPORATION": "{{ client_name }}",
    "Devon Canada Corporation": "{{ client_name }}",
    "00/04-04-049-04W4/0": "{{ uwi }}",
    "Signum Consulting Ltd.": "{{ consultant_name }}",
    "March 2017": "{{ report_month_year }}",
    "March 15, 2004": "{{ spud_date }}",
    "March 17, 2004": "{{ cased_date }}",
    "June 2004": "{{ final_drill_date }}",
    "710 metres (m)": "{{ well_depth_m }} metres (m)",
    "710 m": "{{ well_depth_m }} m",
    "currently suspended": "currently {{ well_status }}",
    "gas with water": "{{ production_fluid }}",
    "Checklist Compliance Option 1 (AER, 2014 )": "{{ aer_waste_compliance_option }}",
    "Checklist Compliance Option 1 (AER, 2014)": "{{ aer_waste_compliance_option }}",
    "A site visit has not been completed at this time.": "{{ site_visit_completed }} — site visit note.",
    "well centre and the production areas be investigated": "{{ investigations_recommended }}",
    "The Devon keyword is Phase II": "Client phase keyword: {{ client_phase_keyword }}",
    "4-4-49-4": "{{ well_name }}",
    "Ron Lutz P. Eng.": "{{ qp_names }}",
}


def _replace_executive_summary_block(docx_bytes: bytes) -> bytes:
    """Replace the full executive summary narrative with a single Jinja tag."""
    out_buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as zin:
        with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                raw = zin.read(info.filename)
                if info.filename == DOCUMENT_XML:
                    text = raw.decode("utf-8")
                    start = text.find(EXEC_SUMMARY_START)
                    end = text.find(EXEC_SUMMARY_END)
                    if start >= 0 and end > start:
                        end += len(EXEC_SUMMARY_END)
                        text = text[:start] + "{{ executive_summary }}" + text[end:]
                    raw = text.encode("utf-8")
                zout.writestr(info, raw)
    return out_buf.getvalue()


def tag_devon_template(docx_bytes: bytes) -> bytes:
    tagged = _replace_executive_summary_block(docx_bytes)
    ordered = dict(sorted(SCALAR_TAG_REPLACEMENTS.items(), key=lambda x: -len(x[0])))
    tagged = tag_docx_xml(tagged, ordered)
    tagged = tag_first_in_document_xml(tagged, "Signum", "{{ consultant_name }}")
    return tagged


def _patch_devon_excel(path: Path) -> None:
    import pandas as pd

    from engine import DRILLING_WASTE_SHEET, PROJECT_SHEET, STORAGE_TANKS_SHEET

    row = {
        "client_name": "Example Energy Ltd.",
        "client_short": "Example Energy",
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
        "asset_activity_type": "Oil well site — Devon 2017 reference",
        "records_review_summary": (
            "Company well file, AER spills search, ABADATA, and historical air photos reviewed."
        ),
        "interview_operator_summary": (
            "Informational interview with former operator regarding waste disposal and infrastructure."
        ),
        "interview_landowner_summary": "",
        "flare_pit_used": "No",
        "no_drilling_waste_on_site": "No",
        "site_visit_date": "",
        "site_visit_photo_notes": "",
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

    xl = pd.ExcelFile(path)
    sheets = {name: pd.read_excel(xl, sheet_name=name) for name in xl.sheet_names}
    project = sheets[PROJECT_SHEET]
    base = {str(c): "" for c in project.columns}
    if not project.empty:
        base = {str(c): project.at[0, c] for c in project.columns}
    for key, val in row.items():
        base[str(key)] = "" if val is None else str(val)
    sheets[PROJECT_SHEET] = pd.DataFrame([base])

    with pd.ExcelWriter(path, engine="openpyxl") as w:
        for name, df in sheets.items():
            df.to_excel(w, sheet_name=name, index=False)


def write_tagging_guide(scan_roots: set[str]) -> None:
    lines = [
        "# Devon 2017 Phase I — template pairing guide",
        "",
        "| File | Role |",
        "|------|------|",
        f"| `{OUT_XLSX.name}` | Excel data (ProjectData, DrillingWaste, StorageTanks) |",
        f"| `{OUT_TEMPLATE.name}` | Word template tagged from Devon 2017 reference |",
        "",
        "**Sidebar profile:** Alberta Phase I ESA (Ecoventure) (`phase1_alberta`)",
        "",
        "## Jinja tags applied automatically",
        "",
    ]
    for var in sorted(scan_roots):
        lines.append(f"- `{{{{ {var} }}}}`")
    lines.extend(
        [
            "",
            "## Manual follow-up in Word",
            "",
            "- Verify cover `{{ well_name }}` (replaces `4-4-49-4` token only).",
            "- Add `{%tr for item in drilling_waste %}` table rows if you extend AER tables.",
            "- Run pre-flight in the app before client delivery.",
            "",
            "## Source",
            "",
            f"Local reference: `{SOURCE_DOCX.name}` (not committed if gitignored).",
        ]
    )
    OUT_GUIDE.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    if not SOURCE_DOCX.is_file():
        print(f"ERROR: Source not found: {SOURCE_DOCX}", file=sys.stderr)
        print("Place the Devon 2017 .docx in samples/ and re-run.", file=sys.stderr)
        return 1

    generate_phase1_alberta_excel(str(OUT_XLSX))
    _patch_devon_excel(OUT_XLSX)
    print(f"Wrote: {OUT_XLSX}")

    tagged = tag_devon_template(SOURCE_DOCX.read_bytes())
    OUT_TEMPLATE.write_bytes(tagged)
    print(f"Wrote: {OUT_TEMPLATE} ({len(tagged):,} bytes)")

    scan = scan_template(tagged)
    write_tagging_guide(scan.root_vars)
    print(f"Wrote: {OUT_GUIDE}")
    print(f"Jinja root vars ({len(scan.root_vars)}): {', '.join(sorted(scan.root_vars))}")
    if scan.split_issues:
        print(f"WARN: {len(scan.split_issues)} split-tag issues — review cover in Word")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
