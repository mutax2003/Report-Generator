# Changelog

All notable changes to the ESA Report Generator. Manifest schema and profile IDs are listed when they affect audit records.

## [Unreleased]

### Added

- Report profiles with `recommended_fields` in `schemas/report_profiles.json` (canonical field lists).
- PDF template upload with cached conversion and **Download converted Word template**.
- Pre-flight: profile-aware missing-field checklist; **Download ReportConfig sheet (Excel)**.
- Sidebar: profile selectbox, phase↔profile sync, executive summary override.
- Appendices A–F PDF uploader and **Download deliverable package (.zip)**.
- Manifest fields: `report_type`, `template_source_format`, `appendix_files` (SHA-256 per appendix).
- `deliverable_pack.py`, `template_attachments.py`, `phase1_narrative.py`, `ui/appendix_panel.py`.
- Docs: [docs/00-start-here.md](docs/00-start-here.md), [docs/14-deployment.md](docs/14-deployment.md), [docs/15-power-automate-guide.md](docs/15-power-automate-guide.md).
- `Dockerfile`, `.github/dependabot.yml`, smoke integration test (75 unit tests total).

### Changed

- `field_validation.contract_warnings` reads report profiles first; `field_contract.json` is legacy reference.
- Agent rules and documentation synced to current UI and module layout.

### Not in this release

- Single merged `Final_Report.pdf` (docx + all appendices).
- Project library (remember last uploads).
- Playwright browser UI tests (headless smoke test covers engine path).

## [1.0.0] — baseline

- Streamlit UI + `ReportEngine` (docxtpl).
- Phase I Alberta samples (Ecoventure), Phase II lab tables, pre-flight, manifests.
- Optional AI tab, automate HTTP/CLI, 67+ unit tests.
