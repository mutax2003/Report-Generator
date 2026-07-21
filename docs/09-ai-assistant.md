# 09 — AI assistant

The **AI assistant** tab provides optional drafting and QA tools. The deterministic merge in `ReportEngine` is unchanged — AI output is **advisory** and must be reviewed before client delivery.

## Configuration

### Offline mode (default)

No API key required. Rule-based fallbacks power all features.

### Cloud / free LLM mode

1. Copy [`.streamlit/secrets.toml.example`](../.streamlit/secrets.toml.example) → `.streamlit/secrets.toml`, or set environment variables.
2. **Free default:** if [Ollama](https://ollama.com) is running locally (`ollama pull qwen2.5:7b`), the app auto-selects it. Otherwise set `GEMINI_API_KEY` or `GROQ_API_KEY`, or set `AI_PROVIDER` explicitly.
3. Enable **Use free/local LLM when available** in the sidebar (**AI options** expander).

Provider resolution is in [`ai/config.py`](../ai/config.py) (`resolve_llm_settings()`). Preference when `AI_PROVIDER` is unset: **Ollama (reachable) → Gemini → Groq → Together → OpenAI**. Explicit `OPENAI_BASE_URL` / `OPENAI_MODEL` override preset defaults. LLM output is advisory until you **Apply** / **Merge** — it is never injected into `ReportEngine` merge automatically.

**Default paid model:** `gpt-4o-mini` when `AI_PROVIDER=openai` (~$0.01–0.05 per site for narrative drafts).

### Free or cheap alternatives (OpenAI-compatible)

All use the same [`ai/client.py`](../ai/client.py) via the OpenAI Python SDK:

| Provider | Cost | Privacy | `AI_PROVIDER` | Key env var | Default model |
|----------|------|---------|---------------|-------------|---------------|
| **Offline heuristics** | Free | Local | `offline` or no key | — | — |
| **Ollama** | Free | Local | `ollama` | `OPENAI_API_KEY=ollama` | `qwen2.5:7b` |
| **Groq** | Free tier | Cloud | `groq` | `GROQ_API_KEY` | `llama-3.1-8b-instant` |
| **Google Gemini** | Free tier | Cloud | `gemini` | `GEMINI_API_KEY` | `gemini-2.0-flash` |
| **Together AI** | Free credits | Cloud | `together` | `TOGETHER_API_KEY` | `meta-llama/Llama-3.3-70B-Instruct-Turbo` |
| **OpenAI** | Low | Cloud | `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` |

**Ecoventure recommendation:** **Ollama** on desktop for confidential site folders (auto-detected when running); **Gemini** or **Groq** for free cloud trials; **gpt-4o-mini** when paid quality matters most.

**JSON-mode note:** Lab PDF and template tagger use structured JSON when supported. Gemini, Together, and Ollama may fall back to text + heuristic JSON parse — quality varies; offline heuristics still run when LLM output is unusable.

### Setup: Google Gemini (free tier)

1. Create an API key at [Google AI Studio](https://aistudio.google.com/apikey).
2. Add to `.streamlit/secrets.toml`:

```toml
AI_PROVIDER = "gemini"
GEMINI_API_KEY = "your-key"
```

3. Restart Streamlit; sidebar should show **Google Gemini — gemini-2.0-flash**.
4. Respect [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) on the free tier.

### Setup: Together AI

1. Sign up at [Together AI](https://www.together.ai/) and create an API key.
2. Add to secrets:

```toml
AI_PROVIDER = "together"
TOGETHER_API_KEY = "your-key"
```

3. Optional: override model with `OPENAI_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo"`.

### CLI without LLM

For headless folder ingest with no external calls:

```powershell
python scripts\ingest_project_folder.py --folder C:\Projects\260109R --ai source-ingest --no-llm
```

Dependencies: `openai`, `pypdf` in `requirements.txt`.

## Architecture

```
ui/ai_panel.py
    ├── ai/template_tagger.py   → bracket → Jinja suggestions
    ├── ai/lab_extract.py       → PDF COA → LabResults / GroundwaterLab rows
    ├── ai/well_log_extract.py  → PDF → MonitoringWells rows
    ├── ai/gw_trends.py         → trend notes from GW context
    ├── ai/narrative.py         → section drafts + RAG
    ├── ai/copilot.py           → pre-flight explanations
    ├── ai/consistency.py       → data QA rules
    ├── ai/exceedance_notes.py  → plain-language lab notes
    └── ai/appendix_classifier.py → PDF → appendix label A–H (project folder)
    └── ai/source_ingest.py     → source/ PDF text + summaries → ai_drafts/
         └── ai/client.py       → OpenAI-compatible API (OpenAI, Ollama, Groq, Gemini, Together, Azure)
```

`ai/config.py` — `AI_PROVIDER` presets, `resolve_llm_settings()`. `ai/models.py` — `AiAudit` entries for session log.

Project folder: [`project_folder.py`](../project_folder.py) + [`scripts/ingest_project_folder.py`](../scripts/ingest_project_folder.py) — AI drafts in `ai_drafts/`, render to `delivered/` ([22-project-folder-workflow.md](22-project-folder-workflow.md)).

## Tier 1 features

### Template tagger

- Input: uploaded Word template bytes
- Finds `[Bracket]` placeholders and known phrases
- Suggests `{{ jinja }}` names from the selected profile’s `recommended_fields` in `schemas/report_profiles.json`
- Download markdown tagging guide

**Use when:** Converting an untagged merge document to Jinja2.

### Lab PDF → Excel

- Input: Certificate of Analysis PDF (max 10 MB)
- Output: Excel with `LabResults` or **`GroundwaterLab`** rows (select target sheet in UI)
- Heuristic parsing offline; LLM improves extraction when enabled

**Use when:** Rapidly building lab sheet from lab PDF.

### Well log PDF → MonitoringWells

- Input: Borehole / well construction PDF
- Output: Excel with `MonitoringWells` rows (well ID, optional screen interval heuristics)

**Use when:** Bootstrapping the well network table from contractor logs.

### Historical docs → APECs

- Input: text-extractable **PDF** or **Word (.docx)** (historical ESA, ABADATA/spill search, air-photo notes)
- Output: candidate rows for the **`Apecs`** sheet (`apec_id`, concern type, evidence, source document, Phase II Y/N)
- Offline heuristics + optional LLM; **Apply / Merge** into session Excel (append or replace)
- Folder Analyze / `--ai apec-extract` / source-ingest writes `ai_drafts/apec_extract_*.json` and `apecs_candidates.json`
- **Not in V1:** scanned image PDFs and JPG (see Phase 2 OCR in `ai/ocr.py`)

**Use when:** Building the Phase I APEC inventory table from historical records — always QP-review before delivery.

### Groundwater trend notes

- Input: merge context with `monitoring_wells`, `groundwater_results`, `water_levels`
- Output: rule-based trend messages and well ID cross-checks

**Use when:** QA before issuing a groundwater monitoring report.

### Narrative drafts

- Input: Excel context + optional `rag_corpus/*.txt` + **project folder** `source/` PDF summaries (when ingested)
- Output: Draft paragraphs (executive summary, site description, conclusions)
- Citations reference corpus filenames and source PDF names (not full text dump)

**Use when:** First draft of narrative sections — always edit in Word after merge.

### Source PDF ingest (project folder)

- Input: PDFs in project folder `source/`
- Output: `ai_drafts/source_index.json`, `source_extracts/*.txt`, `source_summaries.json`, optional `excel_field_suggestions.json`, optional `rag/ingested/*.txt`
- Lab COA filenames routed to `lab_extract_*.json`; Phase I ESA PDFs parsed for cover metadata

**Use when:** Bootstrapping narratives from legacy reports and site PDFs — review before copying into Excel.

### RAG corpus

Add approved text files under [`rag_corpus/`](../rag_corpus/). Separate sections with `---` on its own line. Example files: `phase2_intro.txt`, `exceedance_language.txt`.

## Tier 2 features

### Pre-flight copilot

- Input: current `PreflightResult`, sidebar meta
- Explains errors/warnings in plain language
- Suggests Excel columns to add

### Consistency checker

Rule-based checks including:

- Site name vs address mismatch hints
- Duplicate analyte rows
- Exceedance flag inconsistent with numeric result vs criteria

### Exceedance notes

One-line plain-language note per lab row for report narrative cross-reference.

## Audit trail

- **AI audit log** visible in AI tab during session
- On **Generate report**, `generation_record.ai_audit` includes session AI actions in manifest JSON

## Security and privacy

| Control | Detail |
|---------|--------|
| API keys | Env / secrets only — never in source |
| PDF size | 10 MB cap |
| Prompts | Bounded length |
| Data retention | Streamlit session only; no server-side client DB |
| Offline | No external calls when LLM disabled |

For strict confidentiality, use **Ollama** (local) or keep **Use free/local LLM** off (offline heuristics only).

## Limitations

- AI does not modify Word templates on disk automatically (tagger is suggest-only)
- PDF parsing quality varies by lab format; **scanned/image PDFs and JPG need Phase 2 OCR** (`ai/ocr.py` stub)
- Narratives and APEC rows may hallucinate — verify against site files
- Not a substitute for professional sign-off
- **Apply** buttons write into session Excel / sidebar only after explicit confirmation; empty cells are filled by default, filled cells require **Overwrite filled**

## Apply into the report workflow

| Action | Where |
|--------|--------|
| Apply narratives / field suggestions to ProjectData | **AI drafts & tools** (folder) or **AI tools** (upload) → Folder drafts or Narrative drafts |
| Apply executive summary as sidebar override | Same Apply row (turn off Simple mode to edit) |
| Merge lab / well / APEC extract into loaded Excel | **AI tools** / **AI drafts & tools** → Lab / Well / Historical docs → APECs → **Merge** |
| Apply APEC candidates from folder Analyze | **AI drafts & tools** → Folder drafts → **Apply APECs to Excel** |
| Explain pre-flight gaps | **Report** tab → **Explain these gaps (AI copilot)** |

Tab names: folder workflow = **AI drafts & tools**; Excel + template upload = **AI tools**.
| Consistency / exceedance cues | **Report** tab → **Data QA cues (AI)** |
| Appendix labels from Analyze | `ai_drafts/appendix_manifest.json` preferred over filename heuristics when loading `appendices/` |

## Related

- [04-template-authoring.md](04-template-authoring.md) — Manual tagging
- [22-project-folder-workflow.md](22-project-folder-workflow.md) — Folder enrich + Apply
- [../AI_FEATURES.md](../AI_FEATURES.md) — Short summary
