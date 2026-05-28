"""
Convert Phase 1 ESA PDFs to Word and apply MVP + AI Jinja markup (cover + key fields).

Trusted local files only — does not enforce MAX_TEMPLATE_BYTES on PDF input.
Large PDFs default to first 20 pages for conversion (cover + executive summary MVP).
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import zipfile
from pathlib import Path

os.environ.setdefault("ESA_ALLOW_LARGE_TEMPLATE", "1")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phase1_markup import (  # noqa: E402
    best_practices_checklist,
    enhance_phase1_markup,
    write_tagging_guide,
)
from phase1_pdf_text import (  # noqa: E402
    extract_pdf_text_local,
    parse_phase1_pdf_meta,
)
from scripts.tag_production_template import tag_docx_xml  # noqa: E402
from security import MAX_TEMPLATE_BYTES  # noqa: E402
from template_attachments import convert_pdf_to_docx  # noqa: E402
from template_size import pick_max_pages_for_upload  # noqa: E402
from scripts.safe_console import safe_print  # noqa: E402
from template_tools import scan_template  # noqa: E402

DOCUMENT_XML = "word/document.xml"
DEFAULT_MAX_PAGES = 20
LARGE_PDF_BYTES = 25 * 1024 * 1024

DEFAULT_PDFS = [
    ROOT
    / "samples"
    / "251106R - 15-20-049-10 W5M - Phase 1 ESA_Final_Secure.pdf",
    ROOT
    / "samples"
    / "260109R - 16-34-055-02W4M Phase 1 ESA_Final_Secure.pdf",
]


def tag_first_in_document_xml(docx_bytes: bytes, old: str, new: str) -> bytes:
    """Replace first occurrence in main document body only (cover-field tagging)."""
    if not old or old == new:
        return docx_bytes
    out_buf = io.BytesIO()
    replaced = False
    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as zin:
        with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                raw = zin.read(info.filename)
                if info.filename == DOCUMENT_XML and not replaced:
                    text = raw.decode("utf-8")
                    if old in text:
                        text = text.replace(old, new, 1)
                        raw = text.encode("utf-8")
                        replaced = True
                zout.writestr(info, raw)
    return out_buf.getvalue() if replaced else docx_bytes


def _body(docx_bytes: bytes) -> str:
    """Extract plain text from docx XML (trusted local files)."""
    import re

    parts: list[str] = []
    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as zf:
        for name in zf.namelist():
            if not name.startswith("word/") or not name.endswith(".xml"):
                continue
            xml = zf.read(name).decode("utf-8", errors="replace")
            for m in re.finditer(r"<w:t[^>]*>([^<]*)</w:t>", xml):
                t = m.group(1).strip()
                if t:
                    parts.append(t)
    return " ".join(parts)


def process_pdf(
    pdf_path: Path,
    *,
    skip_convert: bool = False,
    max_pages: int | None = None,
    for_streamlit: bool = False,
    use_ai: bool = True,
    apply_ai_tags: bool = True,
    no_llm: bool = False,
) -> int:
    if not pdf_path.is_file():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    stem = pdf_path.stem
    docx_path = pdf_path.with_suffix(".docx")
    if for_streamlit:
        markup_path = pdf_path.parent / f"{stem}-markup-upload.docx"
    else:
        markup_path = pdf_path.parent / f"{stem}-markup.docx"
    guide_path = pdf_path.parent / f"{stem}-tagging-guide.md"

    pdf_bytes = pdf_path.read_bytes()
    try:
        pdf_text = extract_pdf_text_local(pdf_bytes)
    except RuntimeError as e:
        print(f"ERROR: {pdf_path.name}: {e}", file=sys.stderr)
        return 1

    meta = parse_phase1_pdf_meta(pdf_path, pdf_text)
    print(f"\n=== {pdf_path.name} ===")
    print(f"  project_number: {meta.project_number}")
    print(f"  client_name:    {meta.client_name}")
    site_preview = meta.site_name if len(meta.site_name) <= 80 else meta.site_name[:77] + "..."
    print(f"  site_name:      {site_preview}")
    print(f"  uwi:            {meta.uwi}")

    page_limit = max_pages
    if for_streamlit and page_limit is None:
        page_limit = pick_max_pages_for_upload(pdf_bytes)
        print(
            f"  Streamlit upload limit ({MAX_TEMPLATE_BYTES // (1024 * 1024)} MB): "
            f"using first {page_limit} pages"
        )
    elif page_limit is None and len(pdf_bytes) > LARGE_PDF_BYTES:
        page_limit = DEFAULT_MAX_PAGES
        print(f"  Large PDF ({len(pdf_bytes) // (1024 * 1024)} MB): converting first {page_limit} pages only")

    if skip_convert and docx_path.is_file():
        docx_bytes = docx_path.read_bytes()
        print(f"  Using existing: {docx_path.name}")
    else:
        if page_limit:
            print(f"  Converting PDF to Word (first {page_limit} pages)...")
        else:
            print("  Converting PDF to Word...")
        docx_bytes = convert_pdf_to_docx(pdf_bytes, max_pages=page_limit)
        docx_path.write_bytes(docx_bytes)
        print(f"  Wrote: {docx_path} ({len(docx_bytes):,} bytes)")

    if use_ai:
        print("  Applying MVP tags + AI template tagger (phase1_alberta)...")
    else:
        print("  Applying MVP cover tags only...")

    result = enhance_phase1_markup(
        docx_bytes,
        meta,
        use_ai=use_ai,
        apply_ai_tags=apply_ai_tags,
        use_llm=use_ai and not no_llm,
    )
    tagged_bytes = result.docx_bytes

    body_after = _body(tagged_bytes)
    if "{{ uwi }}" not in body_after and meta.uwi:
        prefix = meta.uwi.split()[0]
        if prefix in body_after:
            tagged_bytes = tag_first_in_document_xml(tagged_bytes, prefix, "{{ uwi }}")

    markup_path.write_bytes(tagged_bytes)
    print(f"  Wrote: {markup_path}")
    print(f"  MVP replacements: {result.mvp_replacements}; AI applied: {result.ai_applied}")
    if result.ai_suggestions:
        print(f"  AI suggestions total: {len(result.ai_suggestions)}")
        if result.audit and result.audit.used_llm:
            print("  (used cloud LLM)")

    write_tagging_guide(
        guide_path,
        result.ai_suggestions,
        meta=meta,
        mvp_count=result.mvp_replacements,
        ai_applied=result.ai_applied,
    )
    print(f"  Wrote: {guide_path}")

    scan = scan_template(tagged_bytes)
    print(f"  Jinja root vars: {', '.join(sorted(scan.root_vars)) or '(none)'}")
    size_mb = len(tagged_bytes) / (1024 * 1024)
    print(f"  Markup file size: {size_mb:.1f} MB")
    if size_mb > MAX_TEMPLATE_BYTES / (1024 * 1024):
        print(
            f"  WARN: Still over {MAX_TEMPLATE_BYTES // (1024 * 1024)} MB — "
            "re-run with --for-streamlit or fewer --max-pages"
        )
    elif for_streamlit:
        print(f"  OK for Streamlit upload (<= {MAX_TEMPLATE_BYTES // (1024 * 1024)} MB)")
    if scan.split_issues:
        print(f"  Split-tag warnings: {len(scan.split_issues)} (fix in Word on cover pages)")
    safe_print("  Best practices:")
    for line in best_practices_checklist(markup_path):
        safe_print(f"    - {line}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert Phase 1 PDF to .docx and apply MVP + AI Jinja markup."
    )
    parser.add_argument(
        "pdfs",
        nargs="*",
        type=Path,
        help="PDF paths (default: both new samples in samples/)",
    )
    parser.add_argument(
        "--skip-convert",
        action="store_true",
        help="Reuse existing .docx next to PDF if present",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help=f"Convert only first N pages (default {DEFAULT_MAX_PAGES} for PDFs >25 MB)",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="MVP cover tags only (skip AI template tagger)",
    )
    parser.add_argument(
        "--suggest-only",
        action="store_true",
        help="Run AI tagger but do not auto-apply suggestions (guide only)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="AI tagger uses rules only (no OpenAI call)",
    )
    parser.add_argument(
        "--for-streamlit",
        action="store_true",
        help=f"Build *-markup-upload.docx under {MAX_TEMPLATE_BYTES // (1024 * 1024)} MB for app upload",
    )
    args = parser.parse_args()
    pdfs = args.pdfs or DEFAULT_PDFS

    use_ai = not args.no_ai
    apply_ai = use_ai and not args.suggest_only
    rc = 0
    for pdf in pdfs:
        if (
            process_pdf(
                pdf,
                skip_convert=args.skip_convert,
                max_pages=args.max_pages,
                for_streamlit=args.for_streamlit,
                use_ai=use_ai,
                apply_ai_tags=apply_ai,
                no_llm=args.no_llm,
            )
            != 0
        ):
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
