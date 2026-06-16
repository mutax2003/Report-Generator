# AI features (Tier 1 & 2)

Full guide: [docs/09-ai-assistant.md](docs/09-ai-assistant.md)

All AI output is **draft or advisory** — review before client delivery. The deterministic `ReportEngine` merge is unchanged.

## Setup

```powershell
pip install -r requirements.txt
```

Optional cloud LLM (improves PDF parsing, narratives, copilot prose):

1. Set `OPENAI_API_KEY` in the environment, or
2. Copy `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml` (supports **OpenAI**, **Ollama** local, **Groq**).

Without a key, **offline rule-based** fallbacks run for every feature.

## Tier 1

| Feature | Tab / CLI | What it does |
|---------|-----------|----------------|
| **Template tagger** | AI → Tier 1 | Finds `[Bracket]` and known phrases; suggests `{{ jinja }}` tags from `schemas/field_contract.json` (see also `report_profiles.json` for profile fields). Download `.md` guide. **Alberta Phase I:** pass `report_type=phase1_alberta` (CLI: `scripts/phase1_pdf_to_markup.py`). |
| **Lab PDF → Excel** | AI → Tier 1 | Parses COA PDFs into `LabResults` rows; download merged `.xlsx`. |
| **Source PDF ingest** | Project folder / `--ai source-ingest` | Reads `source/*.pdf` → `ai_drafts/source_summaries.json` + optional `rag/ingested/` (see [docs/22-project-folder-workflow.md](docs/22-project-folder-workflow.md)). |
| **Narrative drafts** | AI → Tier 1 | Drafts executive summary / site / conclusions using Excel context + `rag_corpus/` + ingested source summaries. |

## Tier 2

| Feature | Tab | What it does |
|---------|-----|----------------|
| **Pre-flight copilot** | AI → Tier 2 | Explains errors/warnings and lists Excel columns to add. |
| **Consistency checker** | AI → Tier 2 | Flags site/address mismatch, duplicate analytes, flag vs numeric exceedance. |
| **Exceedance notes** | AI → Tier 2 | One-line plain-language note per lab row. |

## RAG corpus

Add approved `.txt` snippets under `rag_corpus/` (separate sections with `---`). Narrative drafts cite filenames only.

## Audit

Session **AI audit log** appears in the AI tab. After **Generate Report**, manifest JSON includes `ai_audit` entries from the session.

## Security

- API keys are read from env/secrets only (never hard-coded).
- PDF size capped at 10 MB.
- LLM prompts are bounded; no client data is stored by this app beyond Streamlit session state.
