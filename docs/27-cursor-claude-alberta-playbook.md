# 27 — Cursor Pro + Claude Max: Alberta Phase I / II / GW playbook

Speed up **real client** Alberta reports using **Cursor Pro** (repo agent + folder CLI) and **Claude Max** (Cowork drafting) on the **project-folder workflow**. For Streamlit upload-only training, see [00-start-here.md](00-start-here.md).

**Data rule:** Client-confidential PDFs and Excel stay on **local desktop** or IT-hosted Docker/VM — not Streamlit Community Cloud ([14-deployment.md](14-deployment.md) hosting lock).

## What each tool does

| Tool | Use for | Does not replace |
|------|---------|------------------|
| **Cursor Pro** | Open this repo; run `agent_folder_report.py`; fill lab/well tables; apply drafts; render; fix template tags | QP sign-off, regulatory judgment |
| **Claude Max (Cowork)** | Draft narratives from `source/` PDFs into `ai_drafts/*.json`; review prose before issue | In-app AI tab (unless IT configures Anthropic API separately) |

**Hard boundary:** AI never auto-merges into `ReportEngine`. Flow: `ai_drafts/` → explicit **Apply** → review → **Generate**.

## Gold project folders (SharePoint)

Copy a starter folder from **`ProjectFolders/`** in the SharePoint pack:

| Folder | Profile | Key Excel sheets |
|--------|---------|------------------|
| `Phase1_Alberta` | `phase1_alberta` | `ProjectData` + optional `Apecs`, `DrillingWaste`, `DwdaCalculations` |
| `Phase2_ESA` | `phase2_esa` | `ProjectData` + **`LabResults`** (required) |
| `Groundwater_Monitoring` | `groundwater_monitoring` | `ProjectData` + **`MonitoringWells`**, **`WaterLevels`**, **`GroundwaterLab`** |

Regenerate locally: `python scripts\create_gold_project_folders.py`

Layout details: [22-project-folder-workflow.md](22-project-folder-workflow.md)

## Per-site workflow

### Step A — Parallel start

**Claude Cowork:** Attach `source/` + `project.json`. Write drafts to `ai_drafts/` only (see [Cowork brief templates](#cowork-brief-templates) below).

**Cursor Pro:** Open repo root → Agent chat → skill `esa-agent-folder-report`:

```powershell
cd "Report Generator"
.\.venv\Scripts\Activate.ps1
python scripts\agent_folder_report.py --folder C:\Projects\<id> --mode inventory
```

### Step B — Structured data + apply

1. Cursor fills tabular sheets from COAs (deterministic — not LLM-guessed numbers).
2. Merge Cowork JSON after review:

```powershell
python scripts\agent_folder_report.py --folder C:\Projects\<id> --mode apply-drafts
```

### Step C — Render

```powershell
python scripts\agent_folder_report.py --folder C:\Projects\<id> --mode render --package
```

Output under `delivered/`. Fix pre-flight issues in Excel/template only.

### Step D — QP review

Use [QP-REVIEW-CHECKLIST.txt](../sharepoint/QP-REVIEW-CHECKLIST.txt) before client issue.

---

## Cowork brief templates

Replace `<Folder>` and profile-specific lines. Full copy-paste file: [sharepoint/COWORK-BRIEF-TEMPLATES.txt](../sharepoint/COWORK-BRIEF-TEMPLATES.txt).

### Shared rules (all profiles)

```
Repo: ESA Report Generator (Ecoventure)
Allowed outputs: ai_drafts/*.json ONLY — do not edit project_data.xlsx directly
Field names: schemas/report_profiles.json recommended_fields for this profile
Tone: Alberta O&G QP-ready; cite source PDF filenames; mark gaps [confirm]
NEVER invent lab concentrations, exceedances, UWIs, or certificate numbers
Do not modify engine.py or skip Apply confirmation
```

### Phase I Alberta (`phase1_alberta`)

```
Profile: phase1_alberta
Folder: C:\Projects\<id>
Alberta prompt library key: phase1_alberta

Draft files:
  ai_drafts/narratives.json — sections: executive_summary, drilling_waste, site_reconnaissance, conclusions_recommendations
  ai_drafts/apecs_candidates.json — APEC rows from source PDFs (if applicable)
  ai_drafts/excel_field_suggestions.json — scalar ProjectData fields only

Agent brief (from library): AER SED 002 / DWDA tone; no invented APECs or lab data.
After drafts: user runs Cursor apply-drafts → render — QP review required.
```

### Phase II ESA (`phase2_esa`)

```
Profile: phase2_esa
Folder: C:\Projects\<id>
Alberta prompt library key: phase2_esa

Draft AFTER LabResults is populated in Excel (user or Cursor fills COA table first).

Draft files:
  ai_drafts/narratives.json — sections: executive_summary, site_description, conclusions_limitations

Agent brief: Phase II exceedances and Alberta Tier screening; no invented concentrations.
```

### Groundwater (`groundwater_monitoring`)

```
Profile: groundwater_monitoring
Folder: C:\Projects\<id>
Alberta prompt library key: groundwater_monitoring

Draft files:
  ai_drafts/narratives.json — sections: executive_summary, hydrogeologic_setting, conclusions_recommendations

Agent brief: Use MonitoringWells / WaterLevels / GroundwaterLab context; no invented trends.
Verify well_id consistency across sheets before render.
```

---

## Alberta prompt library keys (by profile)

Canonical JSON: [`schemas/alberta_prompt_library.json`](../schemas/alberta_prompt_library.json). See [26-alberta-prompt-library.md](26-alberta-prompt-library.md).

| Profile key | Narrative sections | Agent task prompts |
|-------------|-------------------|-------------------|
| `phase1_alberta` | executive_summary, drilling_waste, site_reconnaissance, conclusions_recommendations | folder_inventory, apec_extract, sed002_copilot, render_gate |
| `phase2_esa` | executive_summary, site_description, conclusions_limitations | folder_inventory, lab_coa, render_gate |
| `groundwater_monitoring` | executive_summary, hydrogeologic_setting, conclusions_recommendations | folder_inventory, render_gate |

Python access:

```python
from ai.prompts import agent_brief, system_prompt_for
print(agent_brief("phase1_alberta"))
```

---

## Cursor Pro tips

1. Open **repo root** (not only the site folder) so `.cursor/rules/` load.
2. One site per Agent task — pass absolute `--folder` path.
3. Agent mode for apply/render/fix; Ask mode for field/sheet questions.
4. Reference: [25-agent-folder-report.md](25-agent-folder-report.md), skill `.cursor/skills/esa-agent-folder-report/SKILL.md`.

---

## Anti-patterns

- Client PDFs on Community Cloud
- Cowork writing directly to `project_data.xlsx` without Apply
- LLM-extracted lab numbers without COA cross-check
- One mega-prompt for the entire report instead of inventory → drafts → apply → render

## Related

- [22-project-folder-workflow.md](22-project-folder-workflow.md) — folder layout
- [25-agent-folder-report.md](25-agent-folder-report.md) — CLI modes
- [11-alberta-phase1-esa.md](11-alberta-phase1-esa.md) · [18-groundwater-reports.md](18-groundwater-reports.md)
- [21-dwda-directive-050-compliance.md](21-dwda-directive-050-compliance.md) · [20-aer-sed002-phase1-esa.md](20-aer-sed002-phase1-esa.md)
