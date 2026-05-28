"""
Zip deliverable packages and optional PDF merge for appendices (Alberta Phase I).
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from typing import Any

from provenance import sha256_hex


@dataclass
class AppendixFile:
    label: str
    data: bytes
    filename: str

    @property
    def sha256(self) -> str:
        return sha256_hex(self.data)


@dataclass
class DeliverablePackage:
    """Inputs for a client deliverable zip."""

    report_docx: bytes
    report_filename: str
    manifest_bytes: bytes | None = None
    manifest_filename: str = "report_manifest.json"
    appendices: list[AppendixFile] = field(default_factory=list)
    converted_template_docx: bytes | None = None
    converted_template_name: str | None = None


def appendix_manifest_entries(appendices: list[AppendixFile]) -> list[dict[str, str]]:
    return [
        {
            "label": a.label,
            "filename": a.filename,
            "sha256": a.sha256,
            "size_bytes": str(len(a.data)),
        }
        for a in appendices
    ]


def build_batch_reports_zip(
    reports: list[tuple[str, bytes, bytes | None]],
) -> bytes:
    """Zip multiple rendered reports. Each item is (filename, docx_bytes, manifest_bytes|None)."""
    bio = io.BytesIO()
    seen: dict[str, int] = {}
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for docx_name, docx_bytes, manifest_bytes in reports:
            safe = docx_name.replace("\\", "_").replace("/", "_")
            if safe in seen:
                seen[safe] += 1
                stem, ext = (safe.rsplit(".", 1) + ["docx"])[:2]
                safe = f"{stem}_{seen[safe]}.{ext}"
            else:
                seen[safe] = 1
            zf.writestr(f"reports/{safe}", docx_bytes)
            if manifest_bytes:
                stem = safe.rsplit(".", 1)[0] if "." in safe else safe
                zf.writestr(f"manifests/{stem}_manifest.json", manifest_bytes)
    return bio.getvalue()


def build_deliverable_zip(package: DeliverablePackage) -> bytes:
    """Zip report.docx, manifest, appendices/, and optional converted template."""
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(package.report_filename, package.report_docx)
        if package.manifest_bytes:
            zf.writestr(package.manifest_filename, package.manifest_bytes)
        for ap in package.appendices:
            safe = ap.filename.replace("\\", "_").replace("/", "_")
            zf.writestr(f"appendices/{ap.label}_{safe}", ap.data)
        if package.converted_template_docx and package.converted_template_name:
            zf.writestr(
                f"templates/{package.converted_template_name}",
                package.converted_template_docx,
            )
    return bio.getvalue()


def merge_pdfs(pdf_parts: list[bytes]) -> bytes:
    """Concatenate PDF byte streams in order (report first, then appendices)."""
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for part in pdf_parts:
        if not part:
            continue
        reader = PdfReader(io.BytesIO(part))
        for page in reader.pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def enrich_manifest_dict(
    record_dict: dict[str, Any],
    *,
    template_source_format: str = "",
    appendices: list[AppendixFile] | None = None,
) -> dict[str, Any]:
    out = dict(record_dict)
    if template_source_format:
        out["template_source_format"] = template_source_format
    if appendices:
        out["appendix_files"] = appendix_manifest_entries(appendices)
    return out
