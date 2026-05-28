"""Merge Word runs so Jinja tags sit in a single w:t (docxtpl requirement)."""

from __future__ import annotations

import argparse
import io
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from template_tools import scan_template  # noqa: E402

RUN_TEXT = re.compile(r"<w:t[^>]*>([^<]*)</w:t>")
PARA = re.compile(r"(<w:p\b[^>]*>)(.*?)(</w:p>)", re.DOTALL)
RPR = re.compile(r"(<w:rPr>.*?</w:rPr>)", re.DOTALL)

# Normalize common split spell-check fragments before merging runs.
_FRAGMENT_FIXES = (
    (re.compile(r"\{\{\s*client_\s*name\s*\}\}"), "{{ client_name }}"),
    (re.compile(r"\{\{\s*client_\s*short\s*\}\}"), "{{ client_short }}"),
    (re.compile(r"\{\{\s*site_\s*name\s*\}\}"), "{{ site_name }}"),
    (re.compile(r"\{\{\s*executive\s*_\s*summary\s*\}\}"), "{{ executive_summary }}"),
    (re.compile(r"\{\{\s*client_name\s*\}\}"), "{{ client_name }}"),
    (re.compile(r"\{\{\s*site_name\s*\}\}"), "{{ site_name }}"),
    (re.compile(r"\{\{\s*uwi\s*\}\}"), "{{ uwi }}"),
    (re.compile(r"\{\{\s*company\s*\}\}"), "{{ company }}"),
)


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _merge_paragraph(para_inner: str) -> str:
    texts = RUN_TEXT.findall(para_inner)
    if not texts:
        return para_inner
    joined = "".join(texts)
    if "{{" not in joined and "{%" not in joined:
        return para_inner
    for pattern, repl in _FRAGMENT_FIXES:
        joined = pattern.sub(repl, joined)
    rpr_match = RPR.search(para_inner)
    rpr = rpr_match.group(1) if rpr_match else ""
    t_attr = ' xml:space="preserve"' if joined.startswith(" ") or joined.endswith(" ") else ""
    run = f"<w:r>{rpr}<w:t{t_attr}>{_escape_xml(joined)}</w:t></w:r>"
    ppr_match = re.search(r"<w:pPr>.*?</w:pPr>", para_inner, re.DOTALL)
    ppr = ppr_match.group(0) if ppr_match else ""
    return ppr + run


def fix_docx_xml(xml: str) -> str:
    def repl(m: re.Match[str]) -> str:
        open_tag, inner, close_tag = m.group(1), m.group(2), m.group(3)
        return open_tag + _merge_paragraph(inner) + close_tag

    return PARA.sub(repl, xml)


def fix_docx_bytes(data: bytes) -> bytes:
    out_buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data), "r") as zin:
        with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                raw = zin.read(info.filename)
                if info.filename.startswith("word/") and info.filename.endswith(".xml"):
                    text = raw.decode("utf-8")
                    text = fix_docx_xml(text)
                    raw = text.encode("utf-8")
                zout.writestr(info, raw)
    return out_buf.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description="Fix split Jinja runs in a .docx template.")
    parser.add_argument("docx", type=Path, help="Template path")
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the input file (default: write *-fixed.docx sibling)",
    )
    args = parser.parse_args()
    src = args.docx.resolve()
    if not src.is_file():
        print(f"Not found: {src}", file=sys.stderr)
        return 1
    before = scan_template(src.read_bytes())
    fixed = fix_docx_bytes(src.read_bytes())
    after = scan_template(fixed)
    out = src if args.in_place else src.with_name(src.stem + "-fixed.docx")
    out.write_bytes(fixed)
    print(f"Wrote: {out}")
    print(f"Split issues before: {len(before.split_issues)}")
    print(f"Split issues after:  {len(after.split_issues)}")
    print(f"Root vars: {', '.join(sorted(after.root_vars)) or '(none)'}")
    return 0 if not after.split_issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
