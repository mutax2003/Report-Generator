# 09 — AI assistant

The **AI assistant** tab provides optional drafting and QA tools. The deterministic merge in `ReportEngine` is unchanged — AI output is **advisory** and must be reviewed before client delivery.

## Configuration

### Offline mode (default)

No API key required. Rule-based fallbacks power all features.

### Cloud / free LLM mode

1. Copy [`.streamlit/secrets.toml.example`](../.streamlit/secrets.toml.example) → `.streamlit/secrets.toml`, or set environment variables.
2. **Free default:** if [Ollama](https://ollama.com) is running locally (`ollama pull qwen2.5:7b`), the app auto-selects it. Otherwise set `GEMINI_API_KEY` or `GROQ_API_KEY`, or set `AI_PROVIDER` explicitly.
3. Enable **Use LLM when available** in the sidebar (**AI options** expander).

Provider resolution is in [`ai/config.py`](../ai/config.py) (`resolve_llm_settings()`). Preference when `AI_PROVIDER` is unset: **Ollama (reachable) → Gemini → Groq → Together → OpenAI**. Anthropic is **opt-in only** (`AI_PROVIDER=anthropic`); a bare `ANTHROPIC_API_KEY` is ignored because Claude Code / Claude Desktop often export one. The **Claude subscription** provider (`claude_code`) is also opt-in only — picked in sidebar **AI options** or with `AI_PROVIDER=claude_code` — and is never auto-selected. Explicit `OPENAI_BASE_URL` / `OPENAI_MODEL` override preset defaults. LLM output is advisory until you **Apply** / **Merge** — it is never injected into `ReportEngine` merge automatically.

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
| **Anthropic Claude** | Paid (API) | Cloud | `anthropic` | `ANTHROPIC_API_KEY` | `claude-sonnet-5-5` (override with `ANTHROPIC_MODEL`) |
| **Claude subscription** (Max / Team via Claude Code) | Plan limits | Local PC → Anthropic | `claude_code` | none — `claude` → `/login` | `sonnet` (override with `CLAUDE_CODE_MODEL`) |
| **OpenAI** | Low | Cloud | `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` |

**Ecoventure recommendation:** **Ollama** on desktop for confidential site folders (auto-detected when running); **Gemini** or **Groq** for free cloud trials; **Claude subscription** (your own Max / Team seat via Claude Code) or the **Anthropic Claude API** for Cowork-quality narratives inside Streamlit; **gpt-4o-mini** when paid OpenAI quality matters most.

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

### Setup: Anthropic Claude (Streamlit in-app — API key)

Use this when you want **Claude inside the AI tab** (narratives, lab extract, copilot) without pasting into Cowork.

This needs an [Anthropic Console](https://console.anthropic.com/settings/keys) **API key** (usage-based billing). It is the only Claude option on hosted / Docker / shared servers. On your own PC you can use your Claude Max / Team plan instead — see the next section.

1. Create an API key at [Anthropic Console](https://console.anthropic.com/settings/keys).
2. Add to `.streamlit/secrets.toml`:

```toml
AI_PROVIDER = "anthropic"
ANTHROPIC_API_KEY = "sk-ant-..."
# ANTHROPIC_MODEL = "claude-sonnet-5-5"
```

3. Restart Streamlit; sidebar **AI options** should show **Anthropic Claude (API)**.
4. Enable **Use LLM when available**; draft narratives on the **AI drafts & tools** tab, then **Apply** → **Generate** on the Report tab.

Same hard boundary: LLM output stays advisory until Apply; `ReportEngine` merge is unchanged. For folder workflow, you can still use Cowork brief + adversarial review — or use in-app **Draft narratives** with Claude API.

### Setup: Claude subscription (Max / Team) via Claude Code — local PC only

Use your **own** Claude Max, Team Standard or Team Premium seat for AI drafting, with no API key.

Anthropic's terms let a subscription be used by third-party tools **only through Anthropic's unmodified Claude Code**, with each person signing in themselves. Apps may not offer "Sign in with Claude" or handle Claude.ai tokens. So the app never shows a Claude login and never sees a password or token. It runs the `claude` command already signed in on your PC and reads back the text.

1. Install [Claude Code](https://code.claude.com/docs/en/setup). A Team seat must include Claude Code access; your Team admin controls this.
2. Sign in once, in a terminal:

   ```powershell
   claude
   ```

   Type `/login`, choose **Claude account**, finish Anthropic's sign-in page, then `/exit`. Check it with `claude auth status`: you should see `"loggedIn": true` and your plan.
3. In the app, open sidebar **AI options** → **AI provider** → **My Claude account (via Claude Code)**. The caption shows your plan (e.g. *Claude Team*) and `LLM ready`.
4. **Anything but Team / Enterprise** (Pro, Max, or a plan Claude Code doesn't report). These are consumer plans. Before using client data, turn off **Help improve Claude** at claude.ai → Settings → Privacy, then tick **I've checked my Claude Max privacy settings**. Team / Enterprise seats are under commercial terms and skip this step. The provider only runs when Claude Code is signed in with a **Claude account** directly with Anthropic. An API-key, Bedrock or Vertex sign-in is refused; use `AI_PROVIDER=anthropic` for API billing.
5. Keep **Use LLM when available** on and use the AI tab as usual. Each LLM call runs one Claude Code turn and counts toward your plan's usage limits. Batch features such as **Analyze folder** make several calls. If a call fails (limit reached, signed out, timeout), the app falls back to offline heuristics, skips further Claude calls for 2 minutes, and shows **Last Claude Code error** in AI options. Use **Re-check sign-in** after `/login` to retry straight away.

How it runs: `claude -p --output-format json --no-session-persistence --safe-mode --tools ""` with a system-prompt file, the prompt on stdin, and an empty temp folder as the working directory.
- No tools, MCP servers, plugins, hooks or skills.
- Your personal `CLAUDE.md` and memory are not loaded.
- No session is saved.
- The child environment drops every `ANTHROPIC_*`, `AWS_*` and `CLAUDE*` variable (except `CLAUDE_CONFIG_DIR` and `CLAUDE_CODE_GIT_BASH_PATH`), and anything ending in `_KEY`, `_TOKEN`, `_SECRET` or `_PASSWORD` (e.g. `OPENAI_API_KEY`, `ESA_API_KEY`). The call therefore uses your own `/login`, never a key, token or gateway the app could pass along, and doesn't inherit the session of a Claude Code window you launched the app from.
- `CLAUDE_CODE_MODEL` must be a plain alias or model id (`sonnet`, `opus`, `claude-sonnet-4-5`); anything with spaces or shell characters is refused.

| Setting (env or secrets) | Default | Purpose |
|--------------------------|---------|---------|
| `AI_PROVIDER = "claude_code"` | — | Choose it without the sidebar (CLI scripts such as `ingest_project_folder.py --ai enrich`) |
| `CLAUDE_CODE_MODEL` | `sonnet` | Claude Code model alias or full name (`opus` uses limits faster) |
| `CLAUDE_CLI_PATH` | `claude` on `PATH` | Full path to the executable if it is not on `PATH` |
| `ESA_CLAUDE_CONSUMER_ACK = "1"` | off | Scripts: confirms the Pro / Max privacy step above |
| `ESA_CLAUDE_CODE_TIMEOUT_SEC` | `180` | Per-call limit (10–900 s); the whole process tree is killed on timeout |

**Blocked on shared hosts.** The picker is hidden and `claude_code` refuses to run when any of these hold:
- `ESA_HOSTED_MODE`, `ESA_DISABLE_FOLDER_WORKFLOW` or `ESA_BIND_ALL` is set to anything but `0` / `false` / `no` / `off` (in the environment **or** secrets);
- `ESA_API_KEY` is present in the environment, even empty (the HTTP render server);
- the app runs in a container;
- the browser is not on the same PC, e.g. a colleague opens `http://<your-pc>:8501` over the LAN.
- the page is reached through a tunnel or proxy (ngrok, cloudflared, VS Code port forwarding): any `X-Forwarded-*` / `Forwarded` header, or a host name other than `localhost` / `127.0.0.1`, counts as remote.

One person's sign-in must never serve other users. Use `AI_PROVIDER=anthropic` with an API key there. A reverse proxy on the same machine looks local, so always set `ESA_HOSTED_MODE=1` on any shared server.

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
         └── ai/client.py       → OpenAI-compatible API (OpenAI, Ollama, Groq, Gemini, Together, Anthropic, Azure)
                                  or ai/claude_code.py → local signed-in `claude -p` (Claude subscription)
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
| Claude subscription | App never handles Claude.ai credentials; local `claude` CLI only; refused in hosted mode / containers |
| PDF size | 10 MB cap |
| Prompts | Bounded length |
| Data retention | Streamlit session only; no server-side client DB |
| Offline | No external calls when LLM disabled |

For strict confidentiality, use **Ollama** (local) or keep **Use LLM when available** off (offline heuristics only).

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
- [25-agent-folder-report.md](25-agent-folder-report.md) — **Agent folder report** (Cursor / Codex / Claude Cowork) — separate from this in-app Gemini path
- [26-alberta-prompt-library.md](26-alberta-prompt-library.md) — Standard Alberta LLM/agent prompts by profile
- [../AI_FEATURES.md](../AI_FEATURES.md) — Short summary
