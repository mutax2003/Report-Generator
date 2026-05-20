# AI features (Tier 1 & 2)

Full guide: [docs/09-ai-assistant.md](docs/09-ai-assistant.md)

All AI output is **draft or advisory** — review before client delivery. The deterministic `ReportEngine` merge is unchanged.

## Setup

```powershell
pip install -r requirements.txt
```

Optional cloud LLM (improves PDF parsing, narratives, copilot prose):

1. Set `OPENAI_API_KEY` in the environment, or
2. Copy `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml` and add your key.

Without a key, **offline rule-based** fallbacks run for every feature.

## Tier 1

| Feature | Tab | What it does |
|---------|-----|----------------|
| **Template tagger** | AI → Tier 1 | Finds `[Bracket]` and known phrases; suggests `{{ jinja }}` tags from `schemas/field_contract.json`. Download `.md` guide. |
| **Lab PDF → Excel** | AI → Tier 1 | Parses COA PDFs into `LabResults` rows; download merged `.xlsx`. |
| **Narrative drafts** | AI → Tier 1 | Drafts executive summary / site / conclusions using project context + `rag_corpus/`. |

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
