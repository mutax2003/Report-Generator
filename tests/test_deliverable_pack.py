"""Tests for deliverable zip and manifest appendix entries."""

from __future__ import annotations

import json
import unittest
import zipfile
from io import BytesIO

from deliverable_pack import (
    AppendixFile,
    DeliverablePackage,
    appendix_manifest_entries,
    build_deliverable_zip,
    enrich_manifest_dict,
)
from provenance import build_generation_record, sha256_hex


class DeliverablePackTests(unittest.TestCase):
    def test_appendix_manifest_entries(self) -> None:
        ap = AppendixFile(label="A", data=b"%PDF-1.4", filename="a.pdf")
        entries = appendix_manifest_entries([ap])
        self.assertEqual(entries[0]["label"], "A")
        self.assertEqual(entries[0]["sha256"], sha256_hex(b"%PDF-1.4"))

    def test_build_zip_contains_report_and_appendix(self) -> None:
        ap = AppendixFile(label="B", data=b"pdf2", filename="b.pdf")
        pkg = DeliverablePackage(
            report_docx=b"docx",
            report_filename="report.docx",
            manifest_bytes=b'{"ok": true}',
            manifest_filename="report_manifest.json",
            appendices=[ap],
        )
        zbytes = build_deliverable_zip(pkg)
        self.assertGreater(len(zbytes), 10)
        with zipfile.ZipFile(BytesIO(zbytes)) as zf:
            names = zf.namelist()
        self.assertIn("report.docx", names)
        self.assertIn("report_manifest.json", names)
        self.assertTrue(any(n.startswith("appendices/") for n in names))

    def test_enrich_manifest_dict(self) -> None:
        rec = build_generation_record(
            excel_bytes=b"x",
            template_bytes=b"t",
            meta={"report_type": "phase1_alberta"},
            coverage=None,
            warnings=[],
            missing_variables=[],
            template_source_format="pdf",
        )
        d = enrich_manifest_dict(
            rec.to_dict(),
            template_source_format="pdf",
            appendices=[AppendixFile("A", b"p", "a.pdf")],
        )
        self.assertEqual(d["template_source_format"], "pdf")
        self.assertEqual(len(d["appendix_files"]), 1)
        json.dumps(d)


if __name__ == "__main__":
    unittest.main()
