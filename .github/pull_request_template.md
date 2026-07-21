## Summary

<!-- What changed and why (1–3 sentences) -->

## Playbook

<!-- A UX · B engine · C compliance · D schemas · E CI — see AGENTS.md -->

- [ ] Playbook identified and relevant `.cursor/rules/` rule read

## Test plan

- [ ] Verification tier run (`python scripts\verify_tier.py --tier …` — see [AGENTS.md](../AGENTS.md#verification-tiers))
- [ ] `python scripts\count_tests.py` PASS _(if tests added or removed)_
- [ ] Commands run: <!-- e.g. streamlit_smoke, phase1_alberta_e2e, health_check -->

## Review

- [ ] bugbot on branch changes _(or note why skipped)_
- [ ] security-review if upload/auth/tenant/rate-limit/audit/QP/retention/job queue/observability/logging/multipart/deploy touched

## Hard boundaries

- [ ] Renders through `render_service` only
- [ ] No Streamlit imports in `engine.py`
- [ ] No LLM/AI auto-inject into `ReportEngine`
- [ ] New production fields in `schemas/report_profiles.json`
