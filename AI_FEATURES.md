# AI features (Tier 1 & 2)

Full guide: [docs/09-ai-assistant.md](docs/09-ai-assistant.md)

All AI output is **draft or advisory** — review before client delivery. The deterministic `ReportEngine` merge is unchanged. Use **Apply** / **Merge** buttons to write into session Excel after confirmation.

## Setup

```powershell
pip install -r requirements.txt
```

Optional free/local LLM (improves PDF parsing, narratives, APEC extract, copilot prose):

1. **Ollama** (recommended): install from https://ollama.com, run `ollama pull qwen2.5:7b` — auto-detected when running, or
2. Set `GEMINI_API_KEY` / `GROQ_API_KEY` in `.streamlit/secrets.toml` (see `.streamlit/secrets.toml.example`), or
3. Paid: `OPENAI_API_KEY` with `AI_PROVIDER=openai`.

Without a key or Ollama, **offline rule-based** fallbacks run for every feature. LLM output is advisory until you **Apply** / **Merge**.

## Tier 1

| Feature | Tab / CLI | What it does |
|---------|-----------|----------------|
| **Template tagger** | AI → Data & templates | Finds `[Bracket]` and known phrases; suggests `{{ jinja }}` from profile `recommended_fields` in `schemas/report_profiles.json`. Download `.md` guide. |
| **Lab PDF → Excel** | AI → Data & templates | Parses COA PDFs into `LabResults` / `GroundwaterLab`; download or **Merge into current workbook**. |
| **Well log PDF** | AI → Data & templates | Borehole PDF → `MonitoringWells`; download or merge into session Excel. |
| **Historical docs → APECs** | AI → Data & templates / `--ai apec-extract` | PDF/DOCX → `Apecs` sheet candidates; Apply/Merge (QP review). Scanned/JPG = Phase 2. |
| **Source PDF ingest** | Project folder / `--ai source-ingest` | Reads `source/*.pdf` → `ai_drafts/` (+ optional field suggestions + APEC drafts). |
| **Narrative drafts** | AI → QA & narratives | Drafts executive summary / site / conclusions; **Apply to Excel** or sidebar override. |
| **GW trend notes** | AI → QA & narratives | Rule (+ optional LLM) trend / well-ID QA. |

## Tier 2

| Feature | Tab | What it does |
|---------|-----|----------------|
| **Pre-flight copilot** | Report + AI | Explains errors/warnings; Report tab expander **Explain these gaps**. |
| **Consistency checker** | Report + AI | Site/address, duplicate analytes, flag vs numeric exceedance. |
| **Exceedance notes** | Report + AI | One-line plain-language note per lab row. |
| **Appendix classify** | Folder Analyze | Writes `appendix_manifest.json`; labels preferred when loading `appendices/`. |

## RAG corpus

Add approved `.txt` snippets under `rag_corpus/` (separate sections with `---`). Narrative drafts cite filenames only.

## Audit

Session **AI audit log** appears in the AI tab (includes folder Analyze). After **Generate Report**, manifest JSON includes `ai_audit` entries from the session.

## Security

- API keys are read from env/secrets only (never hard-coded).
- PDF size capped at 10 MB.
- LLM prompts are bounded; no client data is stored by this app beyond Streamlit session state.
