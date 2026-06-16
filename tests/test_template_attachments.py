"""Word and PDF template attachment handling."""

from __future__ import annotations

import io
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestTemplateAttachments(unittest.TestCase):
    def test_docx_passthrough(self) -> None:
        from template_attachments import prepare_template_upload

        tpl = ROOT / "samples" / "sample_template.docx"
        if not tpl.is_file():
            raise unittest.SkipTest("run create_samples.py")
        raw = tpl.read_bytes()
        prepared = prepare_template_upload(raw, "sample_template.docx")
        self.assertEqual(prepared.source_format, "docx")
        self.assertEqual(prepared.docx_bytes, raw)

    def test_prepare_template_upload_cached(self) -> None:
        from template_attachments import (
            clear_prepared_template_cache,
            prepare_template_upload_cached,
        )

        tpl = ROOT / "samples" / "sample_template.docx"
        if not tpl.is_file():
            self.skipTest("run create_samples.py")
        clear_prepared_template_cache()
        raw = tpl.read_bytes()
        first = prepare_template_upload_cached(raw, "sample_template.docx")
        second = prepare_template_upload_cached(raw, "sample_template.docx")
        self.assertIs(first, second)

    def test_pdf_convert_to_docx(self) -> None:
        from pypdf import PdfWriter
        from template_attachments import prepare_template_upload
        from security import validate_template_upload

        buf = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.add_blank_page(width=200, height=200)
        writer.write(buf)
        pdf_bytes = buf.getvalue()

        prepared = prepare_template_upload(pdf_bytes, "blank_template.pdf")
        self.assertEqual(prepared.source_format, "pdf")
        self.assertGreater(len(prepared.docx_bytes), 1000)
        self.assertTrue(any("converted" in w.lower() for w in prepared.warnings))
        validate_template_upload(prepared.docx_bytes)

    def test_invalid_extension(self) -> None:
        from security import SecurityError
        from template_attachments import prepare_template_upload

        with self.assertRaises(SecurityError):
            prepare_template_upload(b"not a zip", "file.txt")


if __name__ == "__main__":
    unittest.main()
