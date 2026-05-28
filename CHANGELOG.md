# Changelog

All notable changes to the ESA Report Generator. Manifest schema and profile IDs are listed when they affect audit records.

## [Unreleased]

### Added

- **Groundwater monitoring:** profile `groundwater_monitoring`, samples, `groundwater_narrative.py`, [docs/18-groundwater-reports.md](docs/18-groundwater-reports.md), GW phrases and RAG corpus.
- **Remediation / reclamation profiles:** `reclamation_certificate`, `phase3_remediation` (scaffold sheet mappings).
- **AI:** well log PDF extract, groundwater trend notes, Lab PDF → `GroundwaterLab`; GW consistency checks.
- [docs/19-charts-and-gis-embed.md](docs/19-charts-and-gis-embed.md) — Power BI / QGIS PNG workflow.
- Team rollout: [docs/16-team-rollout.md](docs/16-team-rollout.md), [docs/17-server-update-runbook.md](docs/17-server-update-runbook.md), [sharepoint/PUBLISH_CHECKLIST.md](sharepoint/PUBLISH_CHECKLIST.md), `scripts/package_team_sharepoint.ps1`, `docker-compose.yml`, `.streamlit/config.production.toml.example`; expanded [docs/14-deployment.md](docs/14-deployment.md) (Entra ID, Azure, Compose).

- Report profiles with `recommended_fields` in `schemas/report_profiles.json` (canonical field lists).
- PDF template upload with cached conversion and **Download converted Word template**.
- Pre-flight: profile-aware missing-field checklist; **Download ReportConfig sheet (Excel)**.
- Sidebar: profile selectbox, phase↔profile sync, executive summary override.
- Appendices A–F PDF uploader and **Download deliverable package (.zip)**.
- Manifest fields: `report_type`, `template_source_format`, `appendix_files` (SHA-256 per appendix).
- `deliverable_pack.py`, `template_attachments.py`, `phase1_narrative.py`, `ui/appendix_panel.py`.
- Docs: [docs/00-start-here.md](docs/00-start-here.md), [docs/14-deployment.md](docs/14-deployment.md), [docs/15-power-automate-guide.md](docs/15-power-automate-guide.md).
- `Dockerfile`, `.github/dependabot.yml`, smoke integration test.
- **Standard phrases:** `schemas/phrase_catalog.json`, `phrase_resolver.py`, `ui/phrase_panel.py`, optional Excel `PhraseCatalog` sheet; Approaches A–D in [docs/04-template-authoring.md](docs/04-template-authoring.md).
- **Batch reports:** `ReportEngine.render_batch()`, Streamlit **All N reports (batch)**, `render_cli.py --all-rows`; multi-row `ProjectData` (max 50 reports per run).
- Phase I tooling: `phase1_markup.py`, `phase1_pdf_text.py`, scripts `phase1_pdf_to_markup.py`, `create_phase1_site_samples.py`, `phase1_site_e2e.py`.
- Unit test suite: **93 tests** (`test_phrase_resolver`, `test_batch_render`, `test_phase1_markup`, `test_phase1_pdf_text`, and related).

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
