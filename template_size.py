"""Helpers to keep Word templates within Streamlit upload limits."""

from __future__ import annotations

from security import MAX_TEMPLATE_BYTES


def pick_max_pages_for_upload(
    pdf_bytes: bytes,
    *,
    target_bytes: int = MAX_TEMPLATE_BYTES,
    markup_headroom: float = 0.85,
) -> int:
    """
    Find the largest page count whose pdf2docx output stays under target_bytes
    (with headroom for Jinja markup inflation).
    """
    from template_attachments import convert_pdf_to_docx

    budget = int(target_bytes * markup_headroom)
    # Fast path: 12 pages is enough for most Phase I cover + summary sections
    docx = convert_pdf_to_docx(pdf_bytes, max_pages=12)
    if len(docx) <= budget:
        return 12
    for pages in (8, 6):
        docx = convert_pdf_to_docx(pdf_bytes, max_pages=pages)
        if len(docx) <= budget:
            return pages
    return 6
