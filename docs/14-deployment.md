# 14 — Deployment guide (team / production)

Run one shared instance for ~50 report authors. See [16-team-rollout.md](16-team-rollout.md) for rollout phases and [17-server-update-runbook.md](17-server-update-runbook.md) for updates.

## Local (single user / developer)

```powershell
cd "Report Generator"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501. Default config binds to localhost ([`.streamlit/config.toml`](../.streamlit/config.toml)).

## Windows deployment package (executable / portable folder)

Build a self-contained folder for Ecoventure PCs or a network share:

```powershell
cd "Report Generator"
.\scripts\build_windows_deploy.ps1 -BuildExe
```

Output: `dist\ESA-Report-Generator\`

| Artifact | Purpose |
|----------|---------|
| `ESA-Report-Generator.exe` | Double-click launcher (starts Streamlit) |
| `Start-ESA-Report-Generator.bat` | Same, opens browser first |
| `runtime\.venv\` | Portable Python dependencies (created by build) |
| `Install-Dependencies.ps1` | Re-run on target PC if venv missing (needs Python 3.11+ once) |
| `README-DEPLOY.txt` | Quick instructions |

**Target PC:** Copy the whole `ESA-Report-Generator` folder. First run: `Install-Dependencies.ps1` only if `runtime\.venv` was not included in the zip.

**Internal server:** Set environment variable `ESA_BIND_ALL=1` before launching to listen on all interfaces (use with firewall + HTTPS proxy).

```powershell
$env:ESA_BIND_ALL = "1"
.\ESA-Report-Generator.exe
```

Faster rebuild without re-installing pip packages: `.\scripts\build_windows_deploy.ps1 -BuildExe -SkipVenvInstall`

Skip sample regeneration (copy-only): `.\scripts\build_windows_deploy.ps1 -SkipSamples`

**Post-build verification:** the build script runs `runtime\.venv\Scripts\python.exe scripts\health_check.py` inside the output folder when the portable venv is created.

**Trim policy:** the build removes large/confidential samples from the deploy copy (`samples\*.pdf`, Devon pairs, large site docx, markup uploads). Consultants keep full samples in the git repo; portable builds ship Alberta demo + Ecoventure DWDA fixture only.

**Shipped assets:** `templates/ecoventure_dwda/` (QP xltm/dotm), `schemas/` (DWDA + SED checklists), `samples/appendices/` (A/D/G Word templates when `create_appendix_templates.py` ran).

**SmartScreen:** unsigned `ESA-Report-Generator.exe` may trigger Windows Defender SmartScreen — use internal code signing or AV exclusions for pilot rollout. The exe is a launcher only; the app requires the full folder + `runtime\.venv`.

**Alternative server deploy:** copy `dist\ESA-Report-Generator\` to a Windows Server share and register `esa_launcher.py` or the exe with **NSSM** as a service (see Windows Server VM section below).

## Docker (recommended for internal team host)

### Build and run

```bash
docker build -t esa-report-generator:latest .
docker run -d --name esa-reports -p 8501:8501 \
  -e OPENAI_API_KEY=optional \
  esa-report-generator:latest
```

Or use Compose (includes restart policy and config mount):

```bash
docker compose up -d --build
```

### docker-compose.yml

The repo includes [`docker-compose.yml`](../docker-compose.yml):

- Port **8501** published to the host
- Binds `0.0.0.0` inside the container — **must** sit behind firewall + HTTPS proxy with authentication
- Optional `.streamlit/secrets.toml` mount for `OPENAI_API_KEY`

## Production Streamlit settings

Copy [`.streamlit/config.production.toml.example`](../.streamlit/config.production.toml.example) to `.streamlit/config.toml` on the server (or mount in Docker):

- `headless = true`
- `enableXsrfProtection = true`
- `maxUploadSize` aligned with `security.py` (30 MB)

Do **not** set `enableCORS = false` while XSRF protection is on.

## Production hardening (internal team host)

The Docker image and compose file include baseline production controls:

| Control | Location | Notes |
|---------|----------|-------|
| Non-root container user | [`Dockerfile`](../Dockerfile) | Runs as `esa` system user |
| Resource limits | [`docker-compose.yml`](../docker-compose.yml) | 2 GiB memory cap, 2 CPU limit |
| Structured JSON logs | `ESA_JSON_LOG=1` | [`esa_logging.py`](../esa_logging.py) |
| Append-only audit trail | `ESA_AUDIT_ENABLED=1` | [`audit_trail.py`](../audit_trail.py) → `.esa_audit/` volume |
| Audit log path | `ESA_AUDIT_LOG` | Default `.esa_audit/audit.jsonl` |
| Hosted / no folder workflow | `ESA_HOSTED_MODE=1` or `ESA_DISABLE_FOLDER_WORKFLOW=1` | **Default in `docker-compose.yml`** — hides local project-folder path UI |
| Pinned dependencies | [`requirements.txt`](../requirements.txt), [`requirements.lock`](../requirements.lock) | Reproducible installs |
| CI quality gates | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | ruff, mypy, coverage, Python 3.11–3.13 matrix |
| HTTP API auth (optional) | `ESA_API_KEY` + `X-ESA-API-Key` | [`esa_auth.py`](../esa_auth.py); roles from `ESA_DEFAULT_ROLES` (client `X-ESA-Roles` ignored) |
| Pin HTTP actor | `ESA_API_SERVICE_USER` | Server-side identity for shared automation keys |
| Require key on localhost | `ESA_REQUIRE_API_KEY=1` | Forces auth even when binding `127.0.0.1` |
| Rate limiting | `ESA_RATE_LIMIT_MAX` | [`esa_rate_limit.py`](../esa_rate_limit.py) — IP + API-key digest buckets |

The Docker [`docker-entrypoint.sh`](../docker-entrypoint.sh) briefly runs as root to **chown** the audit volume (`.esa_audit`) for the non-root `esa` user, then drops privileges.

**Entra ID / VPN posture (confirmed):** Streamlit has no built-in SSO. Production deployments **must** use Application Proxy, OAuth2 reverse proxy, or VPN-only access — see options below. Do not publish port 8501 without authentication.

## HTTPS and Microsoft Entra ID (required for ~50 users)

Streamlit has no built-in Entra SSO. Use one of these patterns:

### Option A — Azure Application Proxy (common for M365 tenants)

1. Deploy the container/VM on a private network or with no public IP.
2. Register an **Enterprise application** in Entra ID for the Streamlit URL.
3. Publish `https://esa-reports.yourcompany.com` via **Application Proxy** with pre-authentication **Entra ID**.
4. Users reach the app only after sign-in; backend stays on `http://localhost:8501` on the VM.

### Option B — Reverse proxy (nginx / IIS / Azure Front Door)

1. Terminate TLS at the proxy (`https://` → `http://127.0.0.1:8501`).
2. Enable **OAuth2/OIDC** at the proxy (e.g. `oauth2-proxy` with Entra, or IIS with Windows/Entra auth).
3. Restrict source IPs to corporate VPN if possible.

### Option C — VPN only (minimum)

- Host listens on internal IP only; users connect via corporate VPN.
- Weaker than per-user auth; acceptable only on a trusted flat network.

**Never** expose `docker run -p 8501:8501` directly to the internet without a proxy and authentication ([07-security-and-deployment.md](07-security-and-deployment.md)).

## Azure Container Apps (outline)

1. Build image → push to **Azure Container Registry**.
2. Create Container App:
   - Ingress: external or internal, target port **8501**
   - Min replicas: **1** (cold start avoids user timeouts)
   - CPU/memory: start with 1 vCPU / 2 GiB; scale if PDF conversion is heavy
3. Place **Front Door** or **Application Gateway** in front with Entra authentication, or use internal ingress + VPN.
4. Secrets: `OPENAI_API_KEY` in Container App secrets or Key Vault reference.
5. Deploy updates: new revision from image tag; run smoke test from [17-server-update-runbook.md](17-server-update-runbook.md).

## Windows Server VM (outline)

1. Install Git, Python 3.11+, or Docker Desktop.
2. Clone `https://github.com/mutax2003/Report-Generator.git` to `C:\Apps\Report-Generator`.
3. Follow [17-server-update-runbook.md](17-server-update-runbook.md) for venv + `streamlit run`.
4. Run Streamlit as a **Windows Service** (NSSM) or scheduled task at logon.
5. IIS or Application Proxy in front for HTTPS + Entra.

## Streamlit Community Cloud (tester share URL)

Use this for a **public or invite-only** browser URL for pilot testers. Prefer Docker/Windows internal host for production ([above](#docker-recommended-for-internal-team-host)).

1. Push this repo to GitHub (`mutax2003/Report-Generator`).
2. Open [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Repository: `mutax2003/Report-Generator` · Branch: `master` · Main file: `app.py`.
4. **Advanced settings:**
   - Python **3.12** (required — 3.13 can fail wheels for some deps)
   - Secrets (paste):

```toml
ESA_HOSTED_MODE = "1"
```

   Optional AI (tester cloud drafts):

```toml
ESA_HOSTED_MODE = "1"
AI_PROVIDER = "gemini"
GEMINI_API_KEY = "..."
```

5. Deploy. Share the `*.streamlit.app` URL with testers.
6. Tester path: **Excel + Word template** workflow → Load Alberta Phase I sample → Generate → download zip.

**Notes:** Project-folder workflow is hidden when `ESA_HOSTED_MODE=1`. Do not commit real API keys. Community Cloud is fine for pilots; do not put client confidential site data on a public app without IT approval. `packages.txt` must list **apt package names only** (no `#` comments — Cloud passes every token to `apt-get`).

## HTTP render API (optional, same host)

For future Power Automate ([15-power-automate-guide.md](15-power-automate-guide.md)):

```powershell
python -m automate.http_server --host 127.0.0.1 --port 8765
```

Bind to **127.0.0.1** only; do not expose port 8765 without the same auth layer as Streamlit.

## Production checklist

- [ ] Streamlit not reachable on the public internet without Entra/VPN/proxy auth
- [ ] `ESA_VALIDATION_BYPASS` and `ESA_SKIP_VALIDATION` **unset**
- [ ] `ESA_DISABLE_RATE_LIMIT` **unset** in production
- [ ] `ESA_API_KEY` set for any non-localhost HTTP bind; rotate periodically
- [ ] `ESA_QP_SIGNING_SECRET` set when QP sealing is enabled; store in secrets manager
- [ ] `ESA_RETENTION_POLICY` points at approved policy (or default schema)
- [ ] Templates versioned in filenames (`phase1_ecoventure_v2.1.docx`)
- [ ] SharePoint library published per [sharepoint/PUBLISH_CHECKLIST.md](../sharepoint/PUBLISH_CHECKLIST.md)
- [ ] Generation manifests saved next to issued reports on SharePoint
- [ ] `python scripts\build_help.py` and `help/` present in deploy package (F1 help)
- [ ] `python scripts\health_check.py` after each deploy (**18 checks**)
- [ ] Update process documented and tested ([17-server-update-runbook.md](17-server-update-runbook.md))

## Related

- [07-security-and-deployment.md](07-security-and-deployment.md)
- [16-team-rollout.md](16-team-rollout.md)
- [15-power-automate-guide.md](15-power-automate-guide.md)
- [AUTOMATE.md](../AUTOMATE.md)
