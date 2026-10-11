"""Tests for upload digest and session byte cache helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class _SessionState(dict):
    def __getattr__(self, key: str) -> object:
        return self[key]

    def __setattr__(self, key: str, value: object) -> None:
        self[key] = value

    def setdefault(self, key: str, default: object) -> object:
        if key not in self:
            self[key] = default
        return self[key]


class UploadHelpersTests(unittest.TestCase):
    def test_content_fingerprint_differs_on_tail_change(self) -> None:
        from ui.helpers import _upload_content_fingerprint

        base = b"A" * 100
        swapped = b"A" * 92 + b"XXXXXXXX"
        self.assertNotEqual(
            _upload_content_fingerprint(base),
            _upload_content_fingerprint(swapped),
        )

    @patch("ui.helpers.st")
    def test_stable_upload_digest_same_bytes_cached(self, mock_st: MagicMock) -> None:
        from ui.helpers import stable_upload_digest

        mock_st.session_state = _SessionState()
        data = b"excel-bytes"
        d1 = stable_upload_digest("excel", "data.xlsx", data)
        d2 = stable_upload_digest("excel", "data.xlsx", data)
        self.assertEqual(d1, d2)

    @patch("ui.helpers.st")
    def test_cached_upload_bytes_skips_getvalue_on_rerun(self, mock_st: MagicMock) -> None:
        from ui.helpers import cached_upload_bytes

        mock_st.session_state = _SessionState()
        payload = b"template-bytes"
        upload = MagicMock()
        upload.name = "template.docx"
        upload.size = len(payload)
        upload.file_id = "file-abc123"
        upload.getvalue = MagicMock(return_value=payload)

        first = cached_upload_bytes(upload, slot="template")
        second = cached_upload_bytes(upload, slot="template")
        self.assertEqual(first, payload)
        self.assertIs(second, first)
        self.assertEqual(upload.getvalue.call_count, 1)

    @patch("ui.helpers.st")
    def test_cached_upload_bytes_same_name_size_different_content(self, mock_st: MagicMock) -> None:
        from ui.helpers import cached_upload_bytes

        mock_st.session_state = _SessionState()
        size = 100
        first_payload = b"A" * size
        second_payload = b"B" * size

        upload1 = MagicMock()
        upload1.name = "data.xlsx"
        upload1.size = size
        upload1.file_id = "file-first"
        upload1.getvalue = MagicMock(return_value=first_payload)

        upload2 = MagicMock()
        upload2.name = "data.xlsx"
        upload2.size = size
        upload2.file_id = "file-second"
        upload2.getvalue = MagicMock(return_value=second_payload)

        cached_upload_bytes(upload1, slot="excel")
        result = cached_upload_bytes(upload2, slot="excel")
        self.assertEqual(result, second_payload)
        self.assertNotEqual(result, first_payload)

    def test_content_fingerprint_differs_on_middle_change(self) -> None:
        """Same size, same head/tail, different middle byte must not collide."""
        from ui.helpers import _upload_content_fingerprint

        base = b"H" * 8 + b"A" * 84 + b"T" * 8
        edited = b"H" * 8 + b"A" * 40 + b"B" + b"A" * 43 + b"T" * 8
        self.assertEqual(len(base), len(edited))
        self.assertNotEqual(
            _upload_content_fingerprint(base),
            _upload_content_fingerprint(edited),
        )

    @patch("ui.helpers.st")
    def test_same_size_edit_without_file_id_returns_new_bytes(self, mock_st: MagicMock) -> None:
        """Session/sample uploads have no file_id — an in-place edit must not reuse stale bytes."""
        from ui.helpers import BytesUpload, cached_upload_bytes, stable_upload_digest

        mock_st.session_state = _SessionState()
        original = b"PK" + b"x" * 200 + b"END"
        edited = b"PK" + b"x" * 100 + b"y" + b"x" * 99 + b"END"
        self.assertEqual(len(original), len(edited))

        first = cached_upload_bytes(BytesUpload("data.xlsx", original), slot="excel")
        second = cached_upload_bytes(BytesUpload("data.xlsx", edited), slot="excel")
        self.assertEqual(first, original)
        self.assertEqual(second, edited)

        d1 = stable_upload_digest("excel", "data.xlsx", original)
        d2 = stable_upload_digest("excel", "data.xlsx", edited)
        self.assertNotEqual(d1, d2)
        # Equal content in a different bytes object still hashes to the same digest.
        self.assertEqual(stable_upload_digest("excel", "data.xlsx", bytes(edited)), d2)

    @patch("ui.helpers.st")
    def test_cached_engine_validates_uploads_and_never_serves_stale_engine(
        self, mock_st: MagicMock
    ) -> None:
        import io
        import zipfile

        from security import SecurityError
        from ui.helpers import get_cached_report_engine

        xlsx = ROOT / "samples" / "sample_data.xlsx"
        tpl = ROOT / "samples" / "sample_template.docx"
        if not xlsx.is_file() or not tpl.is_file():
            self.skipTest("Run scripts/create_samples.py first")
        good_xlsx, good_tpl = xlsx.read_bytes(), tpl.read_bytes()

        buf = io.BytesIO()
        with zipfile.ZipFile(xlsx) as src, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
            for info in src.infolist():
                data = src.read(info.filename)
                if info.filename == "xl/worksheets/sheet1.xml":
                    data += b" " * (4 * 1024 * 1024)
                out.writestr(info.filename, data)
        bomb = buf.getvalue()

        mock_st.session_state = _SessionState()
        engine = get_cached_report_engine(good_xlsx, good_tpl)
        self.assertIsNotNone(engine)
        for _ in range(2):  # second call must not return the previously cached engine
            with self.assertRaises(SecurityError):
                get_cached_report_engine(bomb, good_tpl)

    @patch("ui.helpers.st")
    def test_validated_excel_upload_bytes_rejects_bad_excel(self, mock_st: MagicMock) -> None:
        from ui.helpers import validated_excel_upload_bytes

        mock_st.session_state = _SessionState()
        self.assertIsNone(validated_excel_upload_bytes(b"not a zip" * 10, "x.xlsx"))
        mock_st.error.assert_called_once()
        xlsx = ROOT / "samples" / "sample_data.xlsx"
        if xlsx.is_file():
            data = xlsx.read_bytes()
            self.assertIs(validated_excel_upload_bytes(data, "sample_data.xlsx"), data)

    def test_format_folder_error_excel_hint(self) -> None:
        from ui.project_folder import _format_folder_error

        msg = _format_folder_error(
            FileNotFoundError("No Excel file in C:\\demo. Expected one of: project_data.xlsx")
        )
        self.assertIn("project_data.xlsx", msg)


if __name__ == "__main__":
    unittest.main()
