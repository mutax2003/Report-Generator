"""
Zip deliverable packages and optional PDF merge for appendices (Alberta Phase I).
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from provenance import sha256_hex


@dataclass
class AppendixFile:
    label: str
    data: bytes
    filename: str
    format: str = "pdf"
    source: str = "uploaded"

    @cached_property
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
    render_context: dict[str, Any] | None = None
    render_meta: dict[str, str] | None = None
    include_onestop_export: bool = True


def appendix_manifest_entries(appendices: list[AppendixFile]) -> list[dict[str, str]]:
    return [
        {
            "label": a.label,
            "filename": a.filename,
            "sha256": a.sha256,
            "size_bytes": str(len(a.data)),
            "format": a.format,
            "source": a.source,
        }
        for a in appendices
    ]


def build_batch_reports_zip(
    reports: list[tuple[str, bytes, bytes | None, list[AppendixFile] | None]],
) -> bytes:
    """Zip reports; optional fourth element is merged appendices per report."""
    bio = io.BytesIO()
    seen: dict[str, int] = {}
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for entry in reports:
            docx_name = entry[0]
            docx_bytes = entry[1]
            manifest_bytes = entry[2] if len(entry) > 2 else None
            appendices = entry[3] if len(entry) > 3 else None
            safe = docx_name.replace("\\", "_").replace("/", "_")
            if safe in seen:
                seen[safe] += 1
                stem, ext = (safe.rsplit(".", 1) + ["docx"])[:2]
                safe = f"{stem}_{seen[safe]}.{ext}"
            else:
                seen[safe] = 1
            stem = safe.rsplit(".", 1)[0] if "." in safe else safe
            zf.writestr(f"reports/{safe}", docx_bytes)
            if manifest_bytes:
                zf.writestr(f"manifests/{stem}_manifest.json", manifest_bytes)
            for ap in appendices or []:
                ap_safe = ap.filename.replace("\\", "_").replace("/", "_")
                zf.writestr(f"appendices/{stem}/{ap.label}_{ap_safe}", ap.data)
    return bio.getvalue()


def _phase2_likely(context: dict[str, Any], meta: dict[str, str]) -> bool:
    for key in ("phase2_recommended", "phase2_esa_required"):
        for src in (context, meta):
            val = str(src.get(key) or "").strip().lower()
            if val.startswith("y") or val in ("required", "likely", "true", "1"):
                return True
    return False


def build_onestop_phase1_summary(
    context: dict[str, Any],
    meta: dict[str, str] | None = None,
) -> dict[str, str]:
    """Map render context to OneStop Phase 1 ESA summary module-style fields."""
    meta = meta or {}
    phase2 = str(
        context.get("phase2_recommended")
        or context.get("phase2_esa_required")
        or meta.get("phase2_esa_required")
        or ""
    ).strip()
    likely = _phase2_likely(context, meta)
    return {
        "client_name": str(context.get("client_name", "")),
        "operator_name": str(context.get("client_name", "")),
        "well_name": str(context.get("well_name", "")),
        "uwi": str(context.get("uwi", "")),
        "consultant_name": str(context.get("consultant_name", "")),
        "qp_names": str(context.get("qp_names", "")),
        "prepared_by": str(meta.get("prepared_by", context.get("prepared_by", ""))),
        "report_date": str(
            meta.get("date_of_issue", context.get("date_of_issue", ""))
        ),
        "phase1_esa_date": str(context.get("report_month_year", "")),
        "site_visit_completed": str(context.get("site_visit_completed", "")),
        "site_visit_date": str(context.get("site_visit_date", "")),
        "aer_waste_compliance_option": str(
            context.get("aer_waste_compliance_option", "")
        ),
        "phase2_esa_required": str(context.get("phase2_esa_required", "")),
        "phase2_recommended": phase2,
        "contamination_likelihood": "likely" if likely else "unlikely",
        "executive_summary_excerpt": str(context.get("executive_summary", ""))[
            :2000
        ],
        "project_number": str(context.get("project_number", "")),
    }


def build_onestop_export_bytes(
    context: dict[str, Any],
    meta: dict[str, str] | None = None,
) -> tuple[bytes, bytes, bytes]:
    """Return (summary.json, summary.csv, readme.txt) for OneStop upload prep."""
    summary = build_onestop_phase1_summary(context, meta)
    json_bytes = json.dumps(summary, indent=2, sort_keys=True).encode("utf-8")
    csv_buf = io.StringIO()
    writer = csv.writer(csv_buf)
    writer.writerow(["field", "value"])
    for k, v in sorted(summary.items()):
        writer.writerow([k, v])
    csv_bytes = csv_buf.getvalue().encode("utf-8")
    readme = """OneStop submission folder (manual upload)
============================================

1. Export the Word report to PDF: 01_Phase1_ESA_Report.pdf
2. Upload appendices from appendices/ per AER reclamation certificate guidance
3. Use onestop/phase1_esa_summary.json when completing the Phase 1 ESA summary module
4. Verify professional declaration (R&R/12-05) before submitting

References:
- https://www.aer.ca/regulations-and-compliance-enforcement/site-closure-requirements/reclamation/oil-and-gas-sites/reclamation-certificate-application-submissions
- SED 002 (July 2025)
"""
    return json_bytes, csv_bytes, readme.encode("utf-8")


def build_submission_folder_readme(appendix_labels: list[str]) -> bytes:
    lines = [
        "Suggested OneStop / reclamation package layout",
        "=============================================",
        "",
        "01_Phase1_ESA_Report.pdf          — export from Word report in this zip",
        "02_DrillingWaste_Checklist.pdf    — appendix D (export .docx to PDF if generated)",
        "03_DrillingWaste_CalcTables.pdf   — appendix G (export .docx to PDF if generated)",
        "04_ABADATA_SpillSearch.pdf        — appendix B",
        "05_AirPhotos_Sketch.pdf           — appendix C / H",
        "06_Survey_Plan.pdf                — appendix E",
        "07_LandTitle.pdf                  — appendix F",
        "",
        "Appendices uploaded in this package:",
    ]
    for label in sorted(appendix_labels):
        lines.append(f"  - Appendix {label}")
    lines.append("")
    lines.append("onestop/phase1_esa_summary.json — summary module field reference")
    return "\n".join(lines).encode("utf-8")


def build_deliverable_zip_bytes(
    docx_bytes: bytes,
    report_filename: str,
    context: dict[str, Any],
    meta: dict[str, str] | None,
    manifest_bytes: bytes,
    appendices: list[AppendixFile],
) -> bytes:
    """Build deliverable zip from an already-rendered report and manifest."""
    manifest_name = report_filename.rsplit(".", 1)[0] + "_manifest.json"
    return build_deliverable_zip(
        DeliverablePackage(
            report_docx=docx_bytes,
            report_filename=report_filename,
            manifest_bytes=manifest_bytes,
            manifest_filename=manifest_name,
            appendices=appendices,
            render_context=context,
            render_meta=meta,
            include_onestop_export=True,
        )
    )


def _zip_path(prefix: str, name: str) -> str:
    prefix = prefix.strip("/")
    return f"{prefix}/{name}" if prefix else name


def write_deliverable_to_zip(
    zf: zipfile.ZipFile,
    package: DeliverablePackage,
    *,
    path_prefix: str = "",
) -> None:
    """Write one deliverable package into an open ZipFile (optional folder prefix)."""
    zf.writestr(_zip_path(path_prefix, package.report_filename), package.report_docx)
    if package.manifest_bytes:
        zf.writestr(
            _zip_path(path_prefix, package.manifest_filename),
            package.manifest_bytes,
        )
    for ap in package.appendices:
        safe = ap.filename.replace("\\", "_").replace("/", "_")
        zf.writestr(
            _zip_path(path_prefix, f"appendices/{ap.label}_{safe}"),
            ap.data,
        )
    if package.converted_template_docx and package.converted_template_name:
        zf.writestr(
            _zip_path(path_prefix, f"templates/{package.converted_template_name}"),
            package.converted_template_docx,
        )
    if package.include_onestop_export and package.render_context is not None:
        jbytes, cbytes, rbytes = build_onestop_export_bytes(
            package.render_context, package.render_meta
        )
        zf.writestr(_zip_path(path_prefix, "onestop/phase1_esa_summary.json"), jbytes)
        zf.writestr(_zip_path(path_prefix, "onestop/phase1_esa_summary.csv"), cbytes)
        zf.writestr(_zip_path(path_prefix, "onestop/README.txt"), rbytes)
        labels = [a.label for a in package.appendices]
        zf.writestr(
            _zip_path(path_prefix, "onestop/SUBMISSION_LAYOUT.txt"),
            build_submission_folder_readme(labels),
        )


def build_deliverable_zip(package: DeliverablePackage) -> bytes:
    """Zip report.docx, manifest, appendices/, onestop/, and optional converted template."""
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        write_deliverable_to_zip(zf, package)
    return bio.getvalue()


def _batch_site_folder_name(item: Any) -> str:
    """Safe folder name for one batch deliverable package."""
    ctx = getattr(item, "context", None) or {}
    for key in ("site_name", "well_name", "uwi", "project_number"):
        val = str(ctx.get(key) or "").strip()
        if val:
            safe = re.sub(r"[^\w\-]+", "_", val.replace("/", "-").replace("\\", "-"))[:48]
            if safe:
                return safe
    stem = str(getattr(item, "filename", "site") or "site")
    return stem.rsplit(".", 1)[0][:48] or "site"


def build_batch_deliverable_packages_zip(
    batch: list[Any],
    meta: dict[str, str] | None,
) -> bytes:
    """One deliverable folder per site: report + manifest + appendices + onestop."""
    bio = io.BytesIO()
    seen: dict[str, int] = {}
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in batch:
            folder = _batch_site_folder_name(item)
            if folder in seen:
                seen[folder] += 1
                folder = f"{folder}_{seen[folder]}"
            else:
                seen[folder] = 1
            manifest_bytes = item.record.to_json_bytes()
            manifest_name = item.filename.rsplit(".", 1)[0] + "_manifest.json"
            write_deliverable_to_zip(
                zf,
                DeliverablePackage(
                    report_docx=item.docx_bytes,
                    report_filename=item.filename,
                    manifest_bytes=manifest_bytes,
                    manifest_filename=manifest_name,
                    appendices=list(item.appendices or []),
                    render_context=item.context,
                    render_meta=meta,
                    include_onestop_export=True,
                ),
                path_prefix=folder,
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
