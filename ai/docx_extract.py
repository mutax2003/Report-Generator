"""Extract plain text from .docx for AI analysis."""

from __future__ import annotations

import re

from security import ZipReadBudget, open_docx_zip, read_docx_xml_member

_RUN_TEXT = re.compile(r"<w:t[^>]*>([^<]*)</w:t>")


def extract_docx_paragraphs(template_bytes: bytes, *, max_paragraphs: int = 500) -> list[str]:
    paragraphs: list[str] = []
    with open_docx_zip(template_bytes) as zf:
        budget = ZipReadBudget()
        for name in zf.namelist():
            if not name.startswith("word/") or not name.endswith(".xml"):
                continue
            try:
                xml = read_docx_xml_member(zf, name, budget)
            except Exception:
                continue
            for block in re.split(r"</w:p>", xml):
                runs = _RUN_TEXT.findall(block)
                if not runs:
                    continue
                text = "".join(runs).strip()
                if text and len(text) > 1:
                    paragraphs.append(text)
                if len(paragraphs) >= max_paragraphs:
                    return paragraphs
    return paragraphs


def extract_docx_full_text(template_bytes: bytes, *, max_chars: int = 80_000) -> str:
    parts = extract_docx_paragraphs(template_bytes)
    joined = "\n".join(parts)
    return joined[:max_chars]
