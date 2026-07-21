---
name: esa-dev-orchestration
description: >-
  Cursor multi-agent orchestration for the ESA Report Generator repo. Use when
  the user asks to orchestrate agents, pick a subagent, run pre-PR review,
  classify a dev task, verify tier, or follow verification tiers for Streamlit,
  engine, DWDA, schemas, or CI changes in this project.
---
# ESA Report Generator — dev orchestration

Parent agent orchestrates; subagents discover or verify. **Do not** delegate the full feature to a subagent and stop — parent applies the diff.

**Roles:** [esa-agent-roles.mdc](../../rules/esa-agent-roles.mdc) — PM → Architect → Dev → QA → DevOps for non-trivial work.

Start: [AGENTS.md](../../../AGENTS.md) · rules: [`.cursor/rules/`](../../rules/) · verify: `python scripts/verify_tier.py`

## Classify first

| Playbook | Paths | Glob rule |
|----------|-------|-----------|
| **A** UX | `app.py`, `ui/*` | `esa-streamlit-ui.mdc` |
| **B** Engine | `engine.py`, `render_service.py`, `template_tools.py`, profiles | `esa-report-generator-architecture.mdc` |
| **C** Compliance | `dwda_*`, `sed002_*`, `appendix_generator.py` | `esa-dwda-compliance.mdc` |
| **D** Schemas | `schemas/*`, phrases, Word tags | `esa-schemas-and-templates.mdc` |
| **E** CI/tests | `tests/`, `scripts/`, `.github/workflows/` | `esa-testing-ci.mdc` |

## Subagents

| Type | When |
|------|------|
| `explore` | 3+ modules or unknown call path (readonly) |
| `shell` | Run `verify_tier.py`, E2E, git, `count_tests.py` |
| `generalPurpose` | End-to-end field/profile across engine + samples + tests |
| `bugbot` | Pre-PR, `Diff: branch changes` (readonly) |
| `security-review` | `security.py`, upload helpers, auth/tenant/rate-limit/audit/QP/retention/job queue/observability/logging/multipart, deploy (readonly) |
| `ci-investigator` | One failing CI check |

**Parallel:** independent explores (UI + tests). **Sequential:** explore → implement → shell verify.

## Verification tiers

Run via `scripts/verify_tier.py` (preferred for shell subagent):

```powershell
python scripts\verify_tier.py --tier unit
python scripts\verify_tier.py --tier ux
python scripts\verify_tier.py --tier profile --playbook b
python scripts\verify_tier.py --tier release
```

| Tier | `--tier` | Extra |
|------|----------|-------|
| Quick | `quick` | docs only |
| Unit | `unit` | count_tests + unittest |
| UX | `ux` | **build_help** → unit → streamlit_smoke |
| Profile | `profile --playbook X` | + playbook E2E + health_check (b/c/d) |
| Release | `release` | full RELEASE_STEPS (canonical pre-merge) |

Playbook E2E mapping: **b** → `phase1_alberta_e2e` · **c** → `dwda_workflow_e2e` · **d** → `tag_production_template` · **a/e** → tier UX/unit only.

Use `.\.venv\Scripts\python.exe` on Windows.

## Hard boundaries

- All renders → `render_service.RenderRequest`
- No `import streamlit` in `engine.py`
- **No LLM/AI inside `ReportEngine`** — drafts via `ai/*` + UI apply only
- New fields → `schemas/report_profiles.json` `recommended_fields`
- Extend existing modules; no second render path

## Playbook checklists

**A UX:** Report tab order (next steps → preflight → **Generate** → appendices → zip); menubar/F1 help rebuild via `build_help`; new widget keys → `test_streamlit_smoke.py` / `test_menubar.py`; `--tier ux`

**B Engine:** CLI/automation unchanged; update samples; `--tier profile --playbook b`

**C Compliance:** SED/DWDA appendices; `--tier profile --playbook c`

**D Schemas:** `report_profiles.json` + phrase catalog; `--tier profile --playbook d` if tags change

**E CI:** align `ci.yml` with `docs/08-testing.md`; `--tier unit` or `--tier release`

## Pre-PR

1. `verify_tier.py` for playbook tier.
2. Optional: `pip install pre-commit` + `scripts/install_pre_commit.ps1` (UX tier on staged `ui/`).
3. **bugbot** on branch changes.
4. **security-review** if upload/auth/tenant/rate-limit/audit/QP/retention/job queue/observability/logging/multipart/deploy touched.

## Example orchestration prompts

**Parent → parallel explore:**
> Classify A. Launch explore on `ui/onboarding.py` call graph and explore on `tests/test_streamlit_smoke.py`. Synthesize. Implement. Run `verify_tier.py --tier ux`.

**Parent → shell subagent:**
> Run `python scripts/verify_tier.py --tier profile --playbook b` and report failures only.

**Pre-PR:**
> Run `verify_tier.py --tier release`. Then bugbot on branch changes. Security-review if security / auth / tenant / rate-limit / audit / QP / retention / job queue / observability / multipart / deploy in diff.
