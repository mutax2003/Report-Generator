"""
Alberta Phase I executive summary prose — Signum Consulting report structure, Ecoventure voice.

Reference: Devon 2017 Signum-style Phase I ESA (AER Schedule Two). Committed outputs use Ecoventure Inc.
"""

from __future__ import annotations

from typing import Any

ECOVENTURE_CONSULTANT = "Ecoventure Inc."


def _s(value: Any) -> str:
    if value is None:
        return ""
    t = str(value).strip()
    if t.lower() in ("nan", "none"):
        return ""
    return t


def _yes(value: Any) -> bool:
    return _s(value).upper() in ("Y", "YES", "TRUE", "1", "X")


def build_phase1_executive_summary(context: dict[str, Any]) -> str:
    """
    Build multi-paragraph executive summary matching Signum Consulting Ltd. sample structure:
    engagement opening, well history, drilling waste (AER Option 1), imagery/site visit,
    regulatory review and Phase II recommendation.
    """
    consultant = _s(context.get("consultant_name")) or ECOVENTURE_CONSULTANT
    client = _s(context.get("client_name")) or "the client"
    well = _s(context.get("well_name")) or _s(context.get("site_name")) or "the subject wellsite"
    spud = _s(context.get("spud_date"))
    cased = _s(context.get("cased_date"))
    final_drill = _s(context.get("final_drill_date"))
    depth = _s(context.get("well_depth_m"))
    status = _s(context.get("well_status")) or "suspended"
    fluid = _s(context.get("production_fluid"))
    reentry = _s(context.get("reentry"))
    reentry_detail = _s(context.get("reentry_detail"))
    option = _s(context.get("aer_waste_compliance_option")) or "Option 1 (AER, 2014)"
    waste_summary = _s(context.get("drilling_waste_summary"))
    phase2_waste = _s(context.get("phase2_drilling_waste_required")) or _s(
        context.get("dwda_phase2_required")
    ) or "No"
    dwda_summary = _s(context.get("dwda_compliance_summary"))
    salinity_note = _s(context.get("dwda_salinity_pathway"))
    air_photo = _s(context.get("air_photo_observations"))
    site_visit = _s(context.get("site_visit_completed")) or "No"
    investigate = _s(context.get("investigations_recommended")) or (
        "well centre and the production areas be investigated"
    )
    client_keyword = _s(context.get("client_phase_keyword"))
    if not client_keyword:
        phase2 = _s(context.get("phase2_esa_required"))
        client_keyword = "Phase II" if _yes(phase2) or phase2.upper().startswith("Y") else "Phase II"

    paragraphs: list[str] = []

    # Paragraph 1 — engagement and well history (Signum opening)
    p1 = (
        f"{consultant} was contracted by {client} to conduct a Phase I Environmental "
        f"Site Assessment on the wellsite and associated facilities known as {well}."
    )
    well_bits: list[str] = []
    if spud:
        if cased:
            well_bits.append(f"The well was spud {spud} and cased on {cased}.")
        else:
            well_bits.append(f"The well was spud {spud}.")
    if reentry_detail:
        well_bits.append(reentry_detail.rstrip(".") + ".")
    elif _yes(reentry) or reentry.lower() == "yes":
        if final_drill and depth:
            well_bits.append(
                f"The well was re-entered and drilled to a final drill date of {final_drill} "
                f"to a total depth of {depth} metres (m), and the well is currently {status}."
            )
        elif depth:
            well_bits.append(
                f"The well was re-entered and drilled to a total depth of {depth} metres (m), "
                f"and the well is currently {status}."
            )
        else:
            well_bits.append(f"The well was re-entered and is currently {status}.")
    elif depth:
        well_bits.append(
            f"The well was drilled to a total depth of {depth} metres (m), "
            f"and the well is currently {status}."
        )
    elif status:
        well_bits.append(f"The well is currently {status}.")
    if fluid:
        well_bits.append(f"The well produced {fluid}.")
    paragraphs.append(p1 + "  " + "  ".join(well_bits))

    # Paragraph 2 — drilling waste (Signum Option 1 block)
    if waste_summary:
        waste_body = (
            f"The drilling waste was assessed using Checklist Compliance {option}; "
            f"{waste_summary.rstrip('.')}."
        )
    else:
        waste_body = (
            f"The drilling waste was assessed using Checklist Compliance {option}. "
            "[Add drilling_waste_summary in ProjectData.]"
        )
    paragraphs.append(waste_body)

    if salinity_note or dwda_summary:
        salinity_bits: list[str] = []
        if salinity_note == "equivalent_salinity":
            salinity_bits.append(
                "Salinity within disposal areas may be assessed using Equivalent "
                "Salinity Guidelines; other parameters must meet Alberta Tier 1/2."
            )
        elif salinity_note == "pending_phase2":
            salinity_bits.append(
                "Phase II sampling is required to assess salinity and other "
                "contaminants against applicable guidelines."
            )
        if dwda_summary:
            salinity_bits.append(dwda_summary.rstrip(".") + ".")
        if salinity_bits:
            paragraphs.append("  ".join(salinity_bits))

    # Paragraph 3 — Phase II for drilling waste + air photo + site visit (Signum)
    p3_parts: list[str] = []
    if phase2_waste.lower().startswith("n"):
        p3_parts.append("A Phase II ESA is not required for the drilling waste.")
    elif phase2_waste.lower().startswith("y"):
        p3_parts.append("A Phase II ESA is required for the drilling waste.")
    if air_photo:
        p3_parts.append(air_photo.rstrip(".") + ".")
    if site_visit.lower().startswith("n"):
        p3_parts.append("A site visit has not been completed at this time.")
    elif site_visit.lower().startswith("y"):
        p3_parts.append("A site visit has been completed.")
    if p3_parts:
        paragraphs.append("  ".join(p3_parts))

    # Paragraph 4 — regulatory review and recommendation (Signum closing)
    paragraphs.append(
        "After reviewing regulatory information and records, and conducting informational "
        f"interviews; it is recommended that {investigate.rstrip('.')}. "
        f"The {client} keyword is {client_keyword.rstrip('.')}."
    )

    return "\n\n".join(paragraphs)
