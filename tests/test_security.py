"""Security and validation unit tests."""

from __future__ import annotations

import io
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from security import (  # noqa: E402
    SecurityError,
    ZipReadBudget,
    inspect_zip_archive,
    read_zip_member,
    sanitize_download_filename,
    user_safe_error,
    validate_excel_upload,
    validate_rendered_output,
    validate_template_upload,
)
from engine import ReportEngine  # noqa: E402


def _minimal_docx_zip(extra_members: dict[str, bytes] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", "<w:document/>")
        if extra_members:
            for name, data in extra_members.items():
                zf.writestr(name, data)
    return buf.getvalue()


def _minimal_xlsx_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            "</Types>",
        )
        zf.writestr("xl/workbook.xml", "<workbook/>")
    return buf.getvalue()


class TestSecurity(unittest.TestCase):
    def test_reject_empty_excel(self) -> None:
        with self.assertRaises(SecurityError):
            validate_excel_upload(b"")

    def test_reject_non_zip(self) -> None:
        with self.assertRaises(SecurityError):
            validate_excel_upload(b"not a zip file" * 100)

    def test_sanitize_download_filename(self) -> None:
        self.assertEqual(
            sanitize_download_filename("../../etc/passwd.docx"),
            "etc_passwd.docx",
        )
        self.assertTrue(
            sanitize_download_filename("site/name.docx").endswith(".docx")
        )

    def test_sample_render(self) -> None:
        xlsx = ROOT / "samples" / "sample_data.xlsx"
        docx = ROOT / "samples" / "sample_template.docx"
        if not xlsx.is_file() or not docx.is_file():
            self.skipTest("samples not generated")
        engine = ReportEngine(
            excel_bytes=xlsx.read_bytes(),
            template_bytes=docx.read_bytes(),
        )
        out, warnings, ctx, _rec = engine.render(
            meta={
                "prepared_by": "Test",
                "date_of_issue": "2026-05-19",
                "report_phase": "Phase 2",
            }
        )
        self.assertGreater(len(out), 1000)
        self.assertIn("lab_results", ctx)
        validate_rendered_output(out)

    def test_user_safe_error_redacts_internal_value_error(self) -> None:
        msg = user_safe_error(ValueError("openpyxl.internal.parser failed at offset 99"))
        self.assertNotIn("openpyxl", msg)
        self.assertIn("failed", msg.lower())

    def test_user_safe_error_allows_missing_sheet(self) -> None:
        msg = user_safe_error(ValueError("Missing sheet 'ProjectData'. Found: ['Sheet1']"))
        self.assertIn("Missing sheet", msg)


class TestZipBomb(unittest.TestCase):
    def test_rejects_path_traversal_member(self) -> None:
        with self.assertRaises(SecurityError):
            inspect_zip_archive(
                _minimal_docx_zip({"../evil.xml": b"x"}),
                purpose="docx",
            )

    def test_rejects_encrypted_member(self) -> None:
        from security import _check_zip_member_metadata

        info = zipfile.ZipInfo("word/document.xml")
        info.file_size = 12
        info.compress_size = 12
        info.flag_bits = 0x1
        with self.assertRaises(SecurityError) as ctx:
            _check_zip_member_metadata(info)
        self.assertIn("Encrypted", str(ctx.exception))

    def test_read_budget_enforced(self) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
            zf.writestr("word/document.xml", b"x" * 50_000)
            zf.writestr("word/comments.xml", b"y" * 200_000)
        data = buf.getvalue()
        validate_template_upload(data)
        zf = zipfile.ZipFile(io.BytesIO(data), "r")
        budget = ZipReadBudget(limit=100_000)
        with zf:
            read_zip_member(zf, "word/document.xml", budget)
            with self.assertRaises(SecurityError):
                read_zip_member(zf, "word/comments.xml", budget)
        zf.close()

    def test_valid_minimal_xlsx(self) -> None:
        validate_excel_upload(_minimal_xlsx_zip())


if __name__ == "__main__":
    unittest.main()
