# 17 — Server update runbook

Use this after each merge to `master` on GitHub when maintaining the **single internal** ESA Report Generator host (~50 users).

**Typical time:** 10–20 minutes including smoke test.

## Prerequisites

- SSH or RDP access to the host (VM) or Azure Container Apps revision deploy rights
- App installed from Git clone or Docker image (see [14-deployment.md](14-deployment.md))
- Maintenance window announced if restart interrupts active users

## Git-based VM deployment

```powershell
cd C:\Apps\Report-Generator   # your install path
git fetch origin
git checkout master
git pull origin master

.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python scripts\create_samples.py
python scripts\health_check.py
python -m unittest discover -s tests -q
```

Restart Streamlit (adjust for your service manager):

```powershell
# If running as a scheduled task or manual console — stop the old process, then:
streamlit run app.py --server.port=8501
```

**Docker deployment:**

```bash
cd /path/to/Report-Generator
git pull origin master
docker build -t esa-report-generator:latest .
docker compose up -d --force-recreate
```

## Post-deploy verification

| Check | Command / action |
|-------|------------------|
| Health script | `python scripts\health_check.py` → **18/18 passed** |
| Unit tests | `python -m unittest discover -s tests -q` → **392 tests OK** (4 may skip) |
| UI smoke | Open app URL → upload `samples/sample_data.xlsx` + `samples/sample_template.docx` → pre-flight → generate → download |
| Version visible | Note git commit in Teams post: `git log -1 --oneline` |

## Rollback

```powershell
git log -5 --oneline
git checkout <previous-commit-sha>
pip install -r requirements.txt
python scripts\health_check.py
# restart Streamlit / recreate container
```

Keep the previous container image tag if using Docker (`esa-report-generator:previous`).

## Teams announcement template

Copy and fill in after a successful deploy:

```
ESA Report Generator — update deployed

• App: https://esa-reports.YOURCOMPANY.internal
• Version: <git short sha, e.g. adcdfeb>
• Changes: <1–3 bullets from CHANGELOG.md Unreleased / latest release>
• Action for authors: refresh browser (Ctrl+F5); use Templates library v2.1 if templates changed
• Issues: contact <support name>; IT for login/URL problems

Smoke test passed on server <date>.
```

## When to skip or delay deploy

- CI failing on `master` (fix before deploy)
- `health_check.py` not 18/18 on the server
- Friday afternoon before a long weekend (unless urgent fix)

## Environment reminders

| Variable | Production |
|----------|------------|
| `ESA_VALIDATION_BYPASS` | **Unset** |
| `ESA_SKIP_VALIDATION` | **Unset** |
| `OPENAI_API_KEY` | Host secret only, if AI tab enabled |

## Related

- [16-team-rollout.md](16-team-rollout.md) — pilot and SharePoint phases
- [08-testing.md](08-testing.md) — full E2E script list
- [CHANGELOG.md](../CHANGELOG.md) — release notes for Teams message
