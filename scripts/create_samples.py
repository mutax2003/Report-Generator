from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import (  # noqa: E402
    generate_phase1_alberta_excel,
    generate_phase1_alberta_template_docx,
    generate_production_excel,
    generate_production_starter_template_docx,
    generate_production_template_docx,
    generate_sample_excel,
    generate_sample_template_docx,
)


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

    generate_sample_excel(str(xlsx))
    generate_production_excel(str(prod_xlsx))
    generate_sample_template_docx(str(docx_tpl))
    generate_production_starter_template_docx(str(prod_starter))
    generate_production_template_docx(str(prod_tpl))
    generate_phase1_alberta_excel(str(p1_xlsx))
    generate_phase1_alberta_template_docx(str(p1_tpl))

    print(f"Wrote: {xlsx}")
    print(f"Wrote: {prod_xlsx}")
    print(f"Wrote: {docx_tpl}")
    print(f"Wrote: {prod_starter}")
    print(f"Wrote: {prod_tpl}")
    print(f"Wrote: {p1_xlsx}")
    print(f"Wrote: {p1_tpl}")


if __name__ == "__main__":
    main()

