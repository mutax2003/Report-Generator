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
        upload.getvalue = MagicMock(return_value=payload)

        first = cached_upload_bytes(upload, slot="template")
        second = cached_upload_bytes(upload, slot="template")
        self.assertEqual(first, payload)
        self.assertIs(second, first)
        self.assertEqual(upload.getvalue.call_count, 1)

    def test_format_folder_error_excel_hint(self) -> None:
        from ui.project_folder import _format_folder_error

        msg = _format_folder_error(
            FileNotFoundError("No Excel file in C:\\demo. Expected one of: project_data.xlsx")
        )
        self.assertIn("project_data.xlsx", msg)


if __name__ == "__main__":
    unittest.main()
