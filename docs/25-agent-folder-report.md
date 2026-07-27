# 25 — Agent folder report (Cursor / Codex / Claude Cowork)

Generate an ESA report from a **selected local project folder** of reference files using an **external agent** (Cursor, Codex CLI, or Claude Cowork). This is a **separate feature** from the Streamlit **AI tools** / Gemini side-car.

| Path | Who runs AI | Merge |
|------|-------------|--------|
| **Gemini / AI tab** | In-app LLM (advisory) | User Apply → Streamlit **Generate** |
| **Agent folder report** | Cursor / Codex / Claude Cowork | Agent prepares Excel/`ai_drafts/` → CLI **render** |

**Never** inject LLM output into `ReportEngine`. Render always uses deterministic merge (`render_service` / `project_folder.render_project_folder`).

## Folder layout

Same as [22-project-folder-workflow.md](22-project-folder-workflow.md):

```
C:\Projects\260109R\
  project_data.xlsx
  template.docx
  source\          # reference PDFs
  appendices\
  ai_drafts\
  delivered\
```

Local desktop only — not available on Streamlit Community Cloud (`ESA_HOSTED_MODE`).

## CLI (shared by all runtimes)

```powershell
cd "Report Generator"
.\.venv\Scripts\Activate.ps1

.\.venv\Scripts\python.exe scripts\agent_folder_report.py --folder C:\Projects\260109R --mode inventory
.\.venv\Scripts\python.exe scripts\agent_folder_report.py --folder C:\Projects\260109R --mode enrich --no-llm
.\.venv\Scripts\python.exe scripts\agent_folder_report.py --folder C:\Projects\260109R --mode apply-drafts
.\.venv\Scripts\python.exe scripts\agent_folder_report.py --folder C:\Projects\260109R --mode render --package
```

| Mode | Effect |
|------|--------|
| `inventory` | Preflight + inventory → `ai_drafts/` |
| `enrich` | Source ingest, narratives, appendix classify (default offline; `--llm` for Gemini/Ollama) |
| `apply-drafts` | Explicit patch of `project_data.xlsx` from `narratives.json` / `excel_field_suggestions.json` |
| `render` | Write `delivered/` (+ `--package` zip) |
| `full` | inventory → enrich → render; Excel Apply only if `--apply-drafts` |

Equivalent lower-level: `scripts/ingest_project_folder.py --ai …` / `--render --package`.

## Cursor

1. Open this repo in Cursor.
2. Ask the agent to follow skill **`esa-agent-folder-report`** (`.cursor/skills/esa-agent-folder-report/SKILL.md`) with your folder path.
3. Or paste the CLI commands above.

## Codex

From the repo root, attach this doc and run the same `agent_folder_report.py` commands. Prefer `--no-llm` when Codex itself edits Excel or `ai_drafts/`.

## Claude Cowork

Copy this task brief into Cowork (replace the folder path):

```
Repo: Report Generator (ESA)
Goal: Produce Phase I deliverable zip from local project folder.

Folder: C:\Projects\YOUR_SITE
Layout: docs/22-project-folder-workflow.md

Steps:
1) python scripts/agent_folder_report.py --folder <Folder> --mode inventory
2) Review ai_drafts/; optionally enrich with --mode enrich --no-llm
3) Only if I confirm: --mode apply-drafts
4) --mode render --package
5) Show paths under delivered/ — QP review required; do not email client without sign-off.

Do not modify engine.py to call an LLM. Do not skip Apply confirmation.
```

## Streamlit

On desktop **Project folder + AI**, you can still Load folder → Analyze → Generate. For agent-driven runs, use this CLI/skill path. See the caption on the folder step linking here.

## Related

- [22-project-folder-workflow.md](22-project-folder-workflow.md) — folder layout + ingest CLI
- [09-ai-assistant.md](09-ai-assistant.md) — in-app Gemini / AI tab
- [26-alberta-prompt-library.md](26-alberta-prompt-library.md) — standard Alberta prompts / agent briefs by profile
- [00-start-here.md](00-start-here.md) — consultant Streamlit path
- Skill: `.cursor/skills/esa-agent-folder-report/SKILL.md`
