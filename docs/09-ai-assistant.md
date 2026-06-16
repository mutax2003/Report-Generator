# 09 — AI assistant

The **AI assistant** tab provides optional drafting and QA tools. The deterministic merge in `ReportEngine` is unchanged — AI output is **advisory** and must be reviewed before client delivery.

## Configuration

### Offline mode (default)

No API key required. Rule-based fallbacks power all features.

### Cloud LLM mode

1. Set environment variable `OPENAI_API_KEY`, or
2. Copy `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml` and add key.

Enable **Use cloud LLM** in the sidebar (AI settings).

**Default model:** `gpt-4o-mini` (~$0.01–0.05 per site for narrative drafts).

### Free or cheap alternatives (OpenAI-compatible)

All use the same [`ai/client.py`](../ai/client.py) — set env vars or `secrets.toml`:

| Provider | Cost | Privacy | Example config |
|----------|------|---------|----------------|
| **Offline heuristics** | Free | Local | No key; uncheck “Use cloud LLM” |
| **Ollama** | Free | Local | `OPENAI_BASE_URL=http://localhost:11434/v1`, `OPENAI_MODEL=qwen2.5:7b`, `OPENAI_API_KEY=ollama` |
| **OpenAI gpt-4o-mini** | Low | Cloud | `OPENAI_API_KEY=sk-...` (default) |
| **Groq** | Free tier | Cloud | `OPENAI_BASE_URL=https://api.groq.com/openai/v1`, Groq API key |

**Ecoventure recommendation:** Ollama on desktop for confidential site folders; gpt-4o-mini when quality matters. JSON-mode features (lab PDF LLM parse) may fall back to heuristics on local models.

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
         └── ai/client.py       → OpenAI-compatible API (OpenAI, Ollama, Groq, Azure)

project_folder.py + scripts/ingest_project_folder.py — local folder ingest, AI drafts in `ai_drafts/`, render to `delivered/` ([22-project-folder-workflow.md](22-project-folder-workflow.md)).
```

`ai/config.py` — model names, limits. `ai/models.py` — `AiAudit` entries for session log.

## Tier 1 features

### Template tagger

- Input: uploaded Word template bytes
- Finds `[Bracket]` placeholders and known phrases
- Suggests `{{ jinja }}` names from `schemas/field_contract.json`
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
- On **Generate Report**, `generation_record.ai_audit` includes session AI actions in manifest JSON

## Security and privacy

| Control | Detail |
|---------|--------|
| API keys | Env / secrets only — never in source |
| PDF size | 10 MB cap |
| Prompts | Bounded length |
| Data retention | Streamlit session only; no server-side client DB |
| Offline | No external calls when LLM disabled |

For strict confidentiality, keep **Use cloud LLM** off.

## Limitations

- AI does not modify Word templates on disk automatically
- PDF parsing quality varies by lab format
- Narratives may hallucinate — verify against site files
- Not a substitute for professional sign-off

## Related

- [04-template-authoring.md](04-template-authoring.md) — Manual tagging
- [../AI_FEATURES.md](../AI_FEATURES.md) — Short summary
