# SharePoint publishing checklist (Phase 1 — standards)

Use this when rolling out the ESA Report Generator to ~50 report authors. IT or a template owner completes these steps once; authors only use the published library.

## Before you start

- [ ] Decide library name (e.g. **ESA Report Generator — Templates & Guides**)
- [ ] Restrict **Edit** to 1–2 template owners; **Read** for all report authors
- [ ] Run `python scripts\create_samples.py` then `.\scripts\package_team_sharepoint.ps1` to build `dist\team-sharepoint\`

## Upload from `dist\team-sharepoint`

| Upload | SharePoint path | Notes |
|--------|-----------------|-------|
| `Guides/00-start-here.md` | Guides/ | Pin or link from Teams channel |
| `PILOT-BRIEFING.txt` | Guides/ (and library root) | Cloud sample-only pilot kickoff |
| `Guides/EXCEL_LAYOUT.txt` | Guides/ | Column reference |
| `Guides/JINJA2_CHEATSHEET.txt` | Guides/ | Word tag reference |
| `Guides/02-user-guide-streamlit.md` | Guides/ | Full UI workflow |
| `Guides/10-glossary-faq.md` | Guides/ | Batch, phrases, PDF templates |
| `Guides/11-alberta-phase1-esa.md` | Guides/ | Ecoventure Phase I fields |
| `Guides/04-template-authoring.md` | Guides/ | Template authors only |
| `Guides/BEST_PRACTICES.md` | Guides/ | Manifests, versioning |
| `Templates/Alberta_Phase1/*` | Templates/Alberta Phase I/ | Bump `v2.1` in names when updated |
| `Templates/Production/*` | Templates/Phase II/ | Production samples |
| `Templates/Demo/*` | Templates/Demo/ | Training only |

## Gold Phase I pair (versioned)

After packaging, confirm these files exist under `dist\team-sharepoint\Templates\Alberta_Phase1\`:

- [ ] `phase1_alberta_data_v2.1.xlsx`
- [ ] `phase1_alberta_template_v2.1.docx`

Upload with those names (or bump `v2.1` → `v2.2` when you change content). Template owners sign off this pair before the pilot exit criteria in [docs/16-team-rollout.md](../docs/16-team-rollout.md).

## Teams channel post (copy/paste)

```
ESA Report Generator — templates and guides are on SharePoint:
[link to library]

• New authors: open Guides → 00-start-here.md
• Alberta Phase I gold pair: Templates/Alberta Phase I → phase1_alberta_data_v2.1.xlsx + phase1_alberta_template_v2.1.docx
• Pilot app (sample data ONLY): [*.streamlit.app URL] — Load Alberta sample → Generate → deliverable zip
• Production / client work: wait for internal Docker + Entra host (not Cloud)
• Help on Cloud: in-app Help & documentation expander (F1 does not open local help)
• Questions: [template owner contact]
```

## Governance

- [ ] Master Word templates edited only by designated owners; authors use **published** copies
- [ ] Client deliverables and confidential PDFs stay on **project** sites — not this library
- [ ] Record `template_version` in the app sidebar (e.g. `2.1`) to match filename
- [ ] Save **generation manifest JSON** next to issued reports ([BEST_PRACTICES.md](../BEST_PRACTICES.md))

## Related

- [docs/16-team-rollout.md](../docs/16-team-rollout.md) — full team rollout (hosting + pilot)
- [docs/17-server-update-runbook.md](../docs/17-server-update-runbook.md) — app updates after deploy
