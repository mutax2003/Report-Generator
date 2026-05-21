"""Inventory Alberta Phase I reference PDF — sections and merge field hints."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.lab_extract import extract_pdf_text  # noqa: E402

DEFAULT_PDF = ROOT / "samples" / "00_04-04-049-04W4M Phase I report - Devon 2017.pdf"
OUT_MD = ROOT / "samples" / "phase1_alberta_inventory.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory Phase I Alberta ESA PDF.")
    parser.add_argument("pdf", nargs="?", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--out", type=Path, default=OUT_MD)
    args = parser.parse_args()

    if not args.pdf.is_file():
        print(f"PDF not found: {args.pdf}", file=sys.stderr)
        print("See samples/phase1_alberta_inventory.md for committed inventory.", file=sys.stderr)
        return 1

    text = extract_pdf_text(args.pdf.read_bytes())
    sections = sorted(
        set(re.findall(r"10\.\d+(?:\.\d+)?[^\n]{0,60}", text)),
        key=str.lower,
    )
    appendices = sorted(set(re.findall(r"APPENDIX [A-F][^\n]{0,50}", text, re.I)))

    lines = [
        "# PDF inventory (auto-generated)",
        "",
        f"**Source:** `{args.pdf.name}`",
        f"**Characters extracted:** {len(text)}",
        "",
        "## AER Schedule Two sections",
        "",
    ]
    for s in sections[:40]:
        lines.append(f"- {s.strip()}")
    lines.extend(["", "## Appendices", ""])
    for a in appendices:
        lines.append(f"- {a.strip()}")
    lines.extend(
        [
            "",
            "## Implementation note",
            "",
            "Generated reports use **Ecoventure Inc.** as consultant. "
            "See `phase1_alberta_data.xlsx` and `phase1_alberta_template.docx`.",
            "",
        ]
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
