---
name: esa-agent-folder-report
description: >-
  Generate an ESA report from a selected local project folder using Cursor,
  Codex, or Claude Cowork. Inventory/enrich drafts, optional explicit Apply,
  then render via existing ingest/render_cli — never inject LLM into ReportEngine.
---

# ESA Agent folder report

Use when the user wants a report from **reference files in a selected folder** via
**Cursor**, **Codex**, or **Claude Cowork** (not the Streamlit Gemini AI tab).

**Contrast:** Gemini / **AI tools** tab = in-app advisory. This skill = external agent
+ folder + CLI render. Docs: [docs/25-agent-folder-report.md](../../../docs/25-agent-folder-report.md).

## Hard boundaries

- Do **not** put LLM calls inside `engine.py` / `render_service.py`
- Drafts go to `ai_drafts/`; Excel updates only with **explicit Apply** (`--apply-drafts`)
- Render only through `scripts/agent_folder_report.py` or `ingest_project_folder.py --render`
- **Local desktop only** — refuse when `folder_workflow_disabled()` (`ESA_HOSTED_MODE` / `ESA_DISABLE_FOLDER_WORKFLOW`)
- Use venv Python: `.\.venv\Scripts\python.exe` on Windows

## Folder layout

See [docs/22-project-folder-workflow.md](../../../docs/22-project-folder-workflow.md):

```
project_data.xlsx   # required
template.docx       # required (or template.pdf)
source/             # reference PDFs
appendices/         # optional B/C/E/F/H PDFs
ai_drafts/          # agent / enrich outputs
delivered/          # render output
```

## Steps

1. Confirm the user gave a real folder path with Excel + template.
2. Inventory:

```powershell
.\.venv\Scripts\python.exe scripts\agent_folder_report.py --folder <path> --mode inventory
```

3. Optional enrich (heuristics by default; `--llm` only if Gemini/Ollama configured and user wants it):

```powershell
.\.venv\Scripts\python.exe scripts\agent_folder_report.py --folder <path> --mode enrich --no-llm
```

4. Review `ai_drafts/`. If applying narratives / field suggestions into Excel (user confirmed):

```powershell
.\.venv\Scripts\python.exe scripts\agent_folder_report.py --folder <path> --mode apply-drafts
```

5. Render package:

```powershell
.\.venv\Scripts\python.exe scripts\agent_folder_report.py --folder <path> --mode render --package
```

Or one shot after review: `--mode full --package` (still requires `--apply-drafts` to patch Excel).

6. Deliverable checklist: `delivered/*.docx`, manifest, optional zip — **QP review required** before client delivery.

## Agent writing drafts

You may write/edit files under `ai_drafts/` (e.g. `narratives.json`, `excel_field_suggestions.json`) yourself, then `--mode apply-drafts` + `--mode render`. Prefer updating `project_data.xlsx` carefully with Apply rather than inventing a second merge path.

## Alberta prompt library

Load profile briefs and task prompts from `schemas/alberta_prompt_library.json` via `ai.prompts`:

```python
from ai.prompts import agent_brief, agent_task_prompt
agent_brief("phase1_alberta")
agent_task_prompt("folder_inventory")
```

See [docs/26-alberta-prompt-library.md](../../../docs/26-alberta-prompt-library.md).
