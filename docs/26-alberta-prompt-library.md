# 26 — Alberta prompt library

Canonical LLM / agent prompts for Ecoventure Alberta environmental reports.

| Asset | Role |
|-------|------|
| [`schemas/alberta_prompt_library.json`](../schemas/alberta_prompt_library.json) | System + section instructions by profile; agent briefs; task prompts |
| [`ai/prompts.py`](../ai/prompts.py) | Loader (`system_prompt_for`, `section_instruction`, `agent_brief`, …) |
| [`ai/narrative.py`](../ai/narrative.py) | Uses library system + section instructions when drafting with LLM |

**Hard boundary:** prompts are advisory. Apply drafts via UI / `--apply-drafts`. Never auto-inject into `ReportEngine`.

## Hardening

- Library load validates JSON shape, profile keys, and size (`MAX_LIBRARY_BYTES`); corrupt/missing file soft-falls back to empty + built-in system text (strict mode raises `PromptLibraryError`).
- Report type / section / task ids are sanitized (safe identifier pattern).
- Agent folder CLI: rejects hosted mode, validates path/dir/Excel/template, security-checks Excel, atomic Excel write with backup on apply, traps enrich/render failures with non-zero exit.

## Profiles covered

| Profile key | Report types |
|-------------|--------------|
| `phase1_alberta` | `phase1_alberta`, `phase1_devon` |
| `phase2_esa` | `phase2_esa` |
| `groundwater_monitoring` | `groundwater_monitoring` |
| `reclamation_certificate` | `reclamation_certificate` |
| `phase3_remediation` | `phase3_remediation` |
| `template_driven` | `template_driven` |

Each profile has: `system_addon`, `sections`, `section_instructions`, `agent_brief`.

## Agent tasks (folder workflow)

Under `agent_tasks` in the JSON: `folder_inventory`, `apec_extract`, `lab_coa`, `sed002_copilot`, `render_gate`.

```python
from ai.prompts import agent_brief, agent_task_prompt, system_prompt_for

print(agent_brief("phase1_alberta"))
print(agent_task_prompt("folder_inventory"))
print(system_prompt_for("groundwater_monitoring"))
```

## Cursor / Codex / Claude Cowork

1. Set report type / profile from `project.json` or Excel `ReportConfig`.
2. Paste `agent_brief(<report_type>)` into the agent task.
3. For folder runs, follow [25-agent-folder-report.md](25-agent-folder-report.md) and skill `esa-agent-folder-report`.
4. Use `agent_task_prompt(...)` for inventory / APEC / lab / SED / render-gate steps.

## Contrast with phrase catalog

| Resource | Purpose |
|----------|---------|
| [`schemas/phrase_catalog.json`](../schemas/phrase_catalog.json) | **Fixed** multi-choice paragraphs for Word tags |
| **Prompt library** | **LLM/agent** instructions to draft variable prose |

## Related

- [09-ai-assistant.md](09-ai-assistant.md) — in-app AI tab
- [25-agent-folder-report.md](25-agent-folder-report.md) — external agent folder path
- [13-flexible-report-profiles.md](13-flexible-report-profiles.md) — report profiles
- [04-template-authoring.md](04-template-authoring.md) — phrases / Word tags
