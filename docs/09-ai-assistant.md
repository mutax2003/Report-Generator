# 09 — AI assistant

The **AI assistant** tab provides optional drafting and QA tools. The deterministic merge in `ReportEngine` is unchanged — AI output is **advisory** and must be reviewed before client delivery.

## Configuration

### Offline mode (default)

No API key required. Rule-based fallbacks power all features.

### Cloud LLM mode

1. Set environment variable `OPENAI_API_KEY`, or
2. Copy `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml` and add key.

Enable **Use cloud LLM** in the sidebar (AI settings).

Dependencies: `openai`, `pypdf` in `requirements.txt`.

## Architecture

```
ui/ai_panel.py
    ├── ai/template_tagger.py   → bracket → Jinja suggestions
    ├── ai/lab_extract.py       → PDF COA → LabResults rows
    ├── ai/narrative.py         → section drafts + RAG
    ├── ai/copilot.py           → pre-flight explanations
    ├── ai/consistency.py       → data QA rules
    └── ai/exceedance_notes.py  → plain-language lab notes
         └── ai/client.py       → OpenAI or offline stub
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
- Output: Excel with `LabResults` rows (merged with existing upload if present)
- Heuristic parsing offline; LLM improves extraction when enabled

**Use when:** Rapidly building lab sheet from lab PDF.

### Narrative drafts

- Input: Excel context + optional `rag_corpus/*.txt` snippets
- Output: Draft paragraphs (executive summary, site description, conclusions)
- Citations reference corpus filenames only (not full text dump)

**Use when:** First draft of narrative sections — always edit in Word after merge.

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
