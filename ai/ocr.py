"""OCR / vision helpers for scanned PDFs and images (Phase 2 — not wired in V1).

V1 APEC extract accepts text PDF and DOCX only. When implementing Phase 2:
- Add optional deps (e.g. pytesseract + pdf2image) or vision LLM when ai_use_llm
- Call from ai/apec_extract.extract_text_from_upload for image/* and empty PDFs
- Cap pages/size per security.MAX_* limits; always flag OCR text for QP review
"""

from __future__ import annotations

OCR_SUPPORTED = False


def ocr_available() -> bool:
    """True when Phase 2 OCR backends are installed and configured."""
    return False


def extract_text_via_ocr(_data: bytes, *, _filename: str = "") -> str:
    """Placeholder — raises until Phase 2 OCR is implemented."""
    raise NotImplementedError(
        "OCR for scanned PDFs and JPG is not implemented yet (APEC extract Phase 2). "
        "Use a text-extractable PDF or Word (.docx)."
    )
