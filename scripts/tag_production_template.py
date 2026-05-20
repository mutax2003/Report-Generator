"""
Tag production Word template with Jinja2 placeholders.

If the full merge document exists at project root, applies bracket replacements
from PRODUCTION_TEMPLATE_GUIDE.txt. Otherwise writes a pre-tagged template to
samples/production_template.docx (and optionally copies to the merge filename).
"""

from __future__ import annotations

import argparse
import io
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import (  # noqa: E402
    PRODUCTION_BRACKET_REPLACEMENTS,
    generate_production_template_docx,
)

DEFAULT_MERGE = ROOT / "22xxxxR Phase 2 ESA Full_merge.docx"
DEFAULT_OUT = ROOT / "samples" / "production_template.docx"


def tag_docx_xml(data: bytes, replacements: dict[str, str]) -> bytes:
    """Replace literal strings in word/*.xml parts (best-effort for bracket placeholders)."""
    out_buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data), "r") as zin:
        with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                raw = zin.read(info.filename)
                if info.filename.startswith("word/") and info.filename.endswith(".xml"):
                    text = raw.decode("utf-8")
                    for old, new in replacements.items():
                        if old in text:
                            text = text.replace(old, new)
                    raw = text.encode("utf-8")
                zout.writestr(info, raw)
    return out_buf.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description="Tag production ESA Word template.")
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_MERGE,
        help="Untagged merge .docx (optional)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Tagged output .docx",
    )
    parser.add_argument(
        "--install-root",
        action="store_true",
        help="Also write tagged copy to merge filename at project root",
    )
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)

    if args.source.is_file():
        tagged = tag_docx_xml(
            args.source.read_bytes(),
            PRODUCTION_BRACKET_REPLACEMENTS,
        )
        args.out.write_bytes(tagged)
        print(f"Tagged {args.source.name} -> {args.out}")
        if args.install_root:
            root_copy = ROOT / args.source.name
            root_copy.write_bytes(tagged)
            print(f"Installed: {root_copy}")
    else:
        generate_production_template_docx(str(args.out))
        print(f"No merge doc at {args.source}; generated tagged template: {args.out}")
        if args.install_root:
            DEFAULT_MERGE.write_bytes(args.out.read_bytes())
            print(f"Installed: {DEFAULT_MERGE}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
