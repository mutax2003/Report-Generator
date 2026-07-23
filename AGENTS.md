# Agent index — ESA Report Generator

Start here when working in this repo with Cursor or other coding agents.

## Rules and docs

| Resource | Purpose |
|----------|---------|
| [`.cursor/rules/esa-report-generator-architecture.mdc`](.cursor/rules/esa-report-generator-architecture.mdc) | Always-on architecture, sheets, venv, UI checklist |
| [`.cursor/rules/esa-testing-ci.mdc`](.cursor/rules/esa-testing-ci.mdc) | unittest, E2E scripts, CI parity (`tests/`, `scripts/`, workflows) |
| [`.cursor/rules/esa-streamlit-ui.mdc`](.cursor/rules/esa-streamlit-ui.mdc) | `app.py` + `ui/` — Streamlit boundaries and module roles |
| [`.cursor/rules/esa-security-uploads.mdc`](.cursor/rules/esa-security-uploads.mdc) | Upload limits, safe errors, `ESA_VALIDATION_BYPASS` |
| [`.cursor/rules/esa-schemas-and-templates.mdc`](.cursor/rules/esa-schemas-and-templates.mdc) | `schemas/*.json`, profiles, Word/Excel authoring |
| [`.cursor/rules/esa-dwda-compliance.mdc`](.cursor/rules/esa-dwda-compliance.mdc) | DWDA/Directive 050, Ecoventure calc ingest, appendices A/D/G |
| [`.cursor/rules/esa-dev-orchestration.mdc`](.cursor/rules/esa-dev-orchestration.mdc) | Cursor multi-agent playbooks, verify tiers, pre-PR |
| [`.cursor/rules/esa-agent-roles.mdc`](.cursor/rules/esa-agent-roles.mdc) | PM → Architect → Dev → QA → DevOps role pipeline |
| [`.cursor/skills/esa-dev-orchestration/SKILL.md`](.cursor/skills/esa-dev-orchestration/SKILL.md) | Condensed orchestration skill for parent agent |
| [`docs/README.md`](docs/README.md) | Full documentation map (01–24) |
| [`docs/20-aer-sed002-phase1-esa.md`](docs/20-aer-sed002-phase1-esa.md) | AER SED 002 §10 checklist, OneStop export |
| [`docs/21-dwda-directive-050-compliance.md`](docs/21-dwda-directive-050-compliance.md) | Directive 050 / ADWDA Option 1–2, DwdaChecklist, appendices D/G |
| [`docs/00-start-here.md`](docs/00-start-here.md) | Consultants — upload, profile, pre-flight, generate, deliverable zip (includes appendices) |
| [`docs/11-alberta-phase1-esa.md`](docs/11-alberta-phase1-esa.md) | Primary use case — Ecoventure Alberta Phase I |
| [`docs/12-testing-with-your-documents.md`](docs/12-testing-with-your-documents.md) | Test your Excel + Word pair |
| [`docs/13-flexible-report-profiles.md`](docs/13-flexible-report-profiles.md) | Custom report types + sheet mapping |
| [`docs/14-deployment.md`](docs/14-deployment.md) | Docker, Azure, production checklist |
| [`docs/15-power-automate-guide.md`](docs/15-power-automate-guide.md) | SharePoint → HTTP render flow |
| [`docs/16-team-rollout.md`](docs/16-team-rollout.md) | Team rollout (~50 users), SharePoint, pilot |
| [`docs/17-server-update-runbook.md`](docs/17-server-update-runbook.md) | Server deploy / update steps |
| [`sharepoint/PUBLISH_CHECKLIST.md`](sharepoint/PUBLISH_CHECKLIST.md) | SharePoint upload checklist |
| [`schemas/report_profiles.json`](schemas/report_profiles.json) | **Canonical** recommended fields per profile |
| [`schemas/sed002_phase1_checklist.json`](schemas/sed002_phase1_checklist.json) | SED 002 §10 preflight checklist |
| [`schemas/field_contract.json`](schemas/field_contract.json) | Legacy reference + AI tagger |
| [`docs/22-project-folder-workflow.md`](docs/22-project-folder-workflow.md) | Project folder — local CLI + AI enrich + render |
| [`docs/23-excel-calculation-workbook-integration.md`](docs/23-excel-calculation-workbook-integration.md) | Excel calc workbooks — hybrid ingest, cell contract, parity |

## Setup

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\create_samples.py
```

Or: `.\run.ps1 scripts\create_samples.py` (uses venv Python on Windows).

## Run

| Task | Command |
|------|---------|
| Project folder (CLI + AI) | `python scripts\ingest_project_folder.py --folder <path> --ai enrich` · [docs/22-project-folder-workflow.md](docs/22-project-folder-workflow.md) |
| Web UI | `.\run.ps1 streamlit` or `streamlit run app.py` (templates: `.docx` or `.pdf`) |
| Quick merge test | `python scripts\test_with_your_documents.py` |
| Phase 1 PDF → markup + site Excel | `python scripts\phase1_pdf_to_markup.py` · `python scripts\create_phase1_site_samples.py` |
| Phase 1 site E2E (251106R + 260109R) | `$env:ESA_ALLOW_LARGE_TEMPLATE="1"; python scripts\phase1_site_e2e.py` |
| User test folder | `python scripts\prepare_user_test_pack.py` then edit `user_test/` |
| Regression | `python scripts\health_check.py` (**18 checks**, incl. project folder, source PDF ingest, Ecoventure DWDA merge, test count parity, HTML help pack) |
| Phase I E2E + deliverable zip | `python scripts\phase1_alberta_e2e.py` |
| DWDA workflow E2E (preflight + H + D/G + OneStop) | `python scripts\dwda_workflow_e2e.py` |
| Appendix templates (A/D/G) | `python scripts\create_appendix_templates.py` |
| CLI render + package | `python scripts\render_cli.py --package` (see `--report-type phase1_alberta`) |
| SharePoint bundle | `.\scripts\package_team_sharepoint.ps1` |
| Team Docker host | `docker compose up -d --build` (see [docs/14-deployment.md](docs/14-deployment.md)) |
| Windows deploy package | `.\scripts\build_windows_deploy.ps1 -BuildExe` → `dist\ESA-Report-Generator\` |
| Unit tests | `python -m unittest discover -s tests -v` (**392 tests**, 4 may skip; see [docs/08-testing.md](docs/08-testing.md)) |
| HTML help pack | `python scripts\build_help.py` → `help/index.html` (**F1** / Help → Contents locally; on Cloud use in-app Help — [docs/14-deployment.md](docs/14-deployment.md)) |
| Streamlit Community Cloud | Python 3.12 + secrets `ESA_HOSTED_MODE=1`; sample data only; F1 `file://` broken — see [docs/14-deployment.md](docs/14-deployment.md) Hosting lock |
| Streamlit AppTest smoke | `python scripts\streamlit_smoke.py` |
| Optional browser smoke | `pip install -r requirements-dev.txt` then `python scripts\playwright_smoke.py` |
| Devon sample pair | `python scripts\create_phase1_devon_pair.py` |
| Phase II project folder | `python scripts\create_phase2_project_folder.py` |
| Slow health in smoke test | `$env:ESA_RUN_HEALTH_CHECK="1"` then run `tests.test_smoke_integration` |
| Verification tier (multi-agent) | `python scripts\verify_tier.py --tier ux` · `--tier profile --playbook b` · `--tier release` |
| Pre-commit UX gate (optional) | `pip install pre-commit` · `.\scripts\install_pre_commit.ps1` |

## Multi-agent workflow (Cursor)

Use **one parent agent** (main chat) as orchestrator. Delegate discovery to subagents; parent synthesizes and applies a **focused diff**. Full playbooks: [docs/05-developer-guide.md](docs/05-developer-guide.md#cursor-multi-agent-orchestration) · project skill: [`.cursor/skills/esa-dev-orchestration/SKILL.md`](.cursor/skills/esa-dev-orchestration/SKILL.md).

### Parent responsibilities

1. **Classify** the task (playbook A–E below) before editing.
2. **Load** this file + the relevant [`.cursor/rules/`](.cursor/rules/) glob rule.
3. **Delegate** to `explore` when touching 3+ modules; use `Read`/`Grep` for 1–2 known files.
4. **Verify** at the tier matching blast radius (see table).
5. **Sync** `scripts/count_tests.py` and docs when tests or CI change.

**Hard boundaries:** renders through `render_service.RenderRequest` · UI in `app.py`/`ui/*` only · no `streamlit` in `engine.py` · **no LLM/AI inside `ReportEngine`** (drafts via `ai/*` + UI apply only) · fields in `schemas/report_profiles.json` · venv Python for scripts/tests.

### Subagent routing

| Subagent | Use for |
|----------|---------|
| `explore` (readonly) | Map call paths, usages, schema touch points |
| `shell` | Git, venv, E2E scripts, `count_tests.py` |
| `generalPurpose` | Multi-module refactors (engine + tests + samples) |
| `bugbot` (readonly) | Pre-PR scan — `Diff: branch changes` |
| `security-review` (readonly) | Changes to `security.py`, upload helpers, auth/tenant/rate-limit/audit/QP/retention/job queue/observability/logging/multipart, deploy |
| `ci-investigator` | Single failing GitHub check |

Launch **in parallel** when independent (e.g. explore UI + explore tests). **Sequential** when output feeds the next step (explore → implement → verify).

### Task playbooks

| ID | Change type | Rule | Verify |
|----|-------------|------|--------|
| **A** | Streamlit / UX (`app.py`, `ui/*`) | [esa-streamlit-ui.mdc](.cursor/rules/esa-streamlit-ui.mdc) | `verify_tier.py --tier ux` (build_help → unittest → streamlit_smoke); Report tab = next steps → preflight → **Generate** → appendices → zip |
| **B** | Engine / templates / profiles | architecture + [schemas rule](.cursor/rules/esa-schemas-and-templates.mdc) | profile `*_e2e.py` + `health_check.py` |
| **C** | DWDA / SED / compliance | [esa-dwda-compliance.mdc](.cursor/rules/esa-dwda-compliance.mdc) | `dwda_workflow_e2e.py` + SED unit tests |
| **D** | Schemas / phrases / Word tags | [esa-schemas-and-templates.mdc](.cursor/rules/esa-schemas-and-templates.mdc) | schema parity + `tag_production_template.py` if tags change |
| **E** | CI / tests only | [esa-testing-ci.mdc](.cursor/rules/esa-testing-ci.mdc) | `count_tests.py`; keep CI aligned with [08-testing.md](docs/08-testing.md) |

### Verification tiers

| Tier | When | Commands |
|------|------|----------|
| Quick | Docs-only | — |
| Unit | Logic / unit tests | `count_tests.py` + `unittest discover` |
| UX | Streamlit / menubar / help | `build_help.py` → unit → `streamlit_smoke.py` |
| Profile | Engine / template / profile | UX + playbook `*_e2e.py` (+ `health_check` for b/c/d) |
| Release | Pre-merge / pre-deploy | `python scripts\verify_tier.py --tier release` (canonical; see [esa-testing-ci.mdc](.cursor/rules/esa-testing-ci.mdc)) |

Run `python scripts\count_tests.py` when adding or removing tests. Or run the tier runner:

```powershell
python scripts\verify_tier.py --tier unit
python scripts\verify_tier.py --tier ux
python scripts\verify_tier.py --tier profile --playbook b
python scripts\verify_tier.py --tier release
```

### Pre-PR review

After implementation + verification tier:

1. Launch **bugbot** on `branch changes`.
2. If upload/auth/tenant/rate-limit/audit/QP/retention/job queue/observability/logging/multipart/deploy touched, launch **security-review**.
3. Use PR checklist in [docs/05-developer-guide.md](docs/05-developer-guide.md#cursor-multi-agent-orchestration).

### Anti-patterns

- `explore` for a single known file (use `Read`)
- Render logic outside `engine.py` / `render_service.py`
- New Streamlit widget keys without AppTest coverage
- Skipping `DOCUMENTED_TEST_COUNT` sync in `count_tests.py`
- `phase1_site_e2e.py` on every change (large templates; local + `ESA_ALLOW_LARGE_TEMPLATE=1` only)

## Key modules

`app.py` · `render_service.py` · `engine.py` (`ReportEngine`, `render_batch`) · `project_folder.py` · `appendix_generator.py` (A/D/G for `phase1_alberta`, `phase1_devon`, `reclamation_certificate`) · `compliance_helpers.py` · `phase2_triggers.py` · `phrase_resolver.py` · `groundwater_narrative.py` · `phase1_narrative.py` · `phase1_decision.py` · `sed002_compliance.py` · `dwda_compliance.py` · `dwda_calculations.py` · `ecoventure_workbook.py` · `report_profile.py` (`read_excel_meta`) · `template_attachments.py` · `template_size.py` · `deliverable_pack.py` (OneStop export, deliverable zip, `qp_templates/`) · `phase1_markup.py` · `phase1_pdf_text.py` · `template_tools.py` · `security.py` · `provenance.py` · `esa_launcher.py` · `esa_auth.py` · `esa_logging.py` · `esa_observability.py` · `esa_rate_limit.py` · `esa_tenant.py` · `audit_trail.py` · `job_queue.py` · `qp_signature.py` · `records_retention.py` · `ui/` (`workflow_mode`, `onboarding`, `menubar`, `project_folder`, `layout`, `sidebar`, `phrase_panel`, `preflight`, `appendix_panel`, `results`, `helpers`, `branding`, `preview`, `ai_panel`, `alberta_imagery`, `folder_picker`) · `help/` (`index.html` from `scripts/build_help.py`; **F1**) · `ai/appendix_classifier.py` · `schemas/phrase_catalog.json` · `schemas/sed002_phase1_checklist.json` · `schemas/ecoventure_dwda_cell_contract.json` · `scripts/` (`ingest_project_folder.py`, `ingest_ecoventure_workbook.py`, `create_appendix_templates.py`, `build_help.py`, `build_windows_deploy.ps1`) · `automate/` (incl. `multipart.py`)

Do not put Streamlit imports in `engine.py`. Extend **`schemas/report_profiles.json`** `recommended_fields` when adding production fields; update `field_contract.json` if the AI tagger or legacy docs need the same names. For phrase fields, update **`schemas/phrase_catalog.json`** and [docs/04-template-authoring.md](docs/04-template-authoring.md). For multi-site Excel, use **`ProjectData` rows 3+** and batch mode or `render_cli.py --all-rows`.
