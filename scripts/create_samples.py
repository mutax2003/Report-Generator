from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import (  # noqa: E402
    generate_custom_demo_excel,
    generate_custom_demo_template_docx,
    generate_groundwater_monitoring_excel,
    generate_groundwater_monitoring_template_docx,
    generate_phase1_alberta_excel,
    generate_phase1_alberta_template_docx,
    generate_phase2_alberta_excel,
    generate_phase2_alberta_template_docx,
    generate_phase3_remediation_excel,
    generate_phase3_remediation_template_docx,
    generate_production_excel,
    generate_production_starter_template_docx,
    generate_production_template_docx,
    generate_reclamation_certificate_excel,
    generate_reclamation_certificate_template_docx,
    generate_sample_excel,
    generate_sample_template_docx,
)

try:
    from scripts.create_appendix_templates import main as create_appendix_templates  # noqa: E402
except ImportError:
    create_appendix_templates = None

try:
    from scripts.create_phase1_devon_pair import main as create_phase1_devon_pair  # noqa: E402
except ImportError:
    create_phase1_devon_pair = None

try:
    from scripts.create_phase1_site_samples import main as create_phase1_site_samples  # noqa: E402
except ImportError:
    create_phase1_site_samples = None


def main() -> None:
    samples = ROOT / "samples"
    samples.mkdir(parents=True, exist_ok=True)

    xlsx = samples / "sample_data.xlsx"
    docx_tpl = samples / "sample_template.docx"

    prod_xlsx = samples / "production_data.xlsx"
    prod_starter = samples / "production_starter_template.docx"
    prod_tpl = samples / "production_template.docx"
    p1_xlsx = samples / "phase1_alberta_data.xlsx"
    p1_tpl = samples / "phase1_alberta_template.docx"
    custom_xlsx = samples / "custom_demo_data.xlsx"
    custom_tpl = samples / "custom_demo_template.docx"
    gw_xlsx = samples / "groundwater_monitoring_data.xlsx"
    gw_tpl = samples / "groundwater_monitoring_template.docx"
    p2_xlsx = samples / "phase2_alberta_data.xlsx"
    p2_tpl = samples / "phase2_alberta_template.docx"
    p3_xlsx = samples / "phase3_remediation_data.xlsx"
    p3_tpl = samples / "phase3_remediation_template.docx"
    rc_xlsx = samples / "reclamation_certificate_data.xlsx"
    rc_tpl = samples / "reclamation_certificate_template.docx"

    generate_sample_excel(str(xlsx))
    generate_production_excel(str(prod_xlsx))
    generate_sample_template_docx(str(docx_tpl))
    generate_production_starter_template_docx(str(prod_starter))
    generate_production_template_docx(str(prod_tpl))
    generate_phase1_alberta_excel(str(p1_xlsx))
    generate_phase1_alberta_template_docx(str(p1_tpl))
    generate_custom_demo_excel(str(custom_xlsx))
    generate_custom_demo_template_docx(str(custom_tpl))
    generate_groundwater_monitoring_excel(str(gw_xlsx))
    generate_groundwater_monitoring_template_docx(str(gw_tpl))
    generate_phase2_alberta_excel(str(p2_xlsx))
    generate_phase2_alberta_template_docx(str(p2_tpl))
    generate_phase3_remediation_excel(str(p3_xlsx))
    generate_phase3_remediation_template_docx(str(p3_tpl))
    generate_reclamation_certificate_excel(str(rc_xlsx))
    generate_reclamation_certificate_template_docx(str(rc_tpl))

    print(f"Wrote: {xlsx}")
    print(f"Wrote: {prod_xlsx}")
    print(f"Wrote: {docx_tpl}")
    print(f"Wrote: {prod_starter}")
    print(f"Wrote: {prod_tpl}")
    print(f"Wrote: {p1_xlsx}")
    print(f"Wrote: {p1_tpl}")
    print(f"Wrote: {custom_xlsx}")
    print(f"Wrote: {custom_tpl}")
    print(f"Wrote: {gw_xlsx}")
    print(f"Wrote: {gw_tpl}")
    print(f"Wrote: {p2_xlsx}")
    print(f"Wrote: {p2_tpl}")
    print(f"Wrote: {p3_xlsx}")
    print(f"Wrote: {p3_tpl}")
    print(f"Wrote: {rc_xlsx}")
    print(f"Wrote: {rc_tpl}")

    if create_phase1_devon_pair is not None:
        create_phase1_devon_pair()
    if create_appendix_templates is not None:
        create_appendix_templates()
    if create_phase1_site_samples is not None:
        create_phase1_site_samples()


if __name__ == "__main__":
    main()

