# Changelog

All notable changes to the ESA Report Generator. Manifest schema and profile IDs are listed when they affect audit records.

## [Unreleased]

### Added

- (none)

## [2.0.0] — 2026-06-16

### Added

- **Startup workflow choice** in Streamlit: **Project folder + AI** vs **Excel + Word template** — pick at launch, switch with **Change** in the banner.
- **Source PDF ingest** (`ai/source_ingest.py`): read `source/` PDFs → `ai_drafts/source_summaries.json` + optional `rag/ingested/`; wired into folder enrich and narratives.
- LLM provider docs: Ollama (free/local), Groq, gpt-4o-mini in `secrets.toml.example` and [docs/09-ai-assistant.md](docs/09-ai-assistant.md).
- **Phase I appendices A, D, and G** auto-generated as `.docx` in the deliverable zip (from `ProjectData` + `DrillingWaste`).
- **Project folder workflow:** local CLI + AI enrich (`project_folder.py`, `scripts/ingest_project_folder.py`); [docs/22-project-folder-workflow.md](docs/22-project-folder-workflow.md).
- **176 unit tests**; **15-step** health check (appendices, project folder, source PDF ingest).
- Streamlit **AppTest** smoke (`tests/test_streamlit_smoke.py`, `scripts/streamlit_smoke.py`).

### Changed

- Docs/rules sync: README, overview, team rollout; Cursor rules and testing docs aligned to **176 tests** / **15** health checks.
- Performance: template ZIP scan cache, upload bytes cache, folder mtime caches, appendix sig cache, preflight tuple cache, lazy sample generation in sidebar.
- **Browse…** native folder picker for project-folder workflow (local Windows desktop).
- CI: Phase II + groundwater E2E; project-folder CLI render smoke on GitHub Actions.
- Streamlit buttons: `use_container_width` → `width="stretch"` across `ui/`.

### Fixed

- Project folder **Load/Browse** template prep and Streamlit widget session-key conflicts (`project_folder_path_pending`).
- **Analyze folder** auto-loads folder into session for immediate generate on the Report tab.
- Folder picker handles tkinter dialog errors gracefully.

## [1.0.0] — baseline

- Streamlit UI + `ReportEngine` (docxtpl).
- Phase I Alberta samples (Ecoventure), Phase II lab tables, pre-flight, manifests.
- Optional AI tab, automate HTTP/CLI, batch reports, standard phrases, deliverable zip.
