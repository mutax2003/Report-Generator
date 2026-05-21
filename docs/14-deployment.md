# Deployment guide

Run the ESA Report Generator on a workstation, VM, or container for your team.

## Local (recommended for consultants)

```powershell
cd "Report Generator"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501. Bind to localhost only unless you add authentication (see [07-security-and-deployment.md](07-security-and-deployment.md)).

## Docker

```bash
docker build -t esa-report-generator .
docker run -p 8501:8501 esa-report-generator
```

Set environment variables for AI features (`OPENAI_API_KEY`) if using the AI tab.

## Azure Container Apps / VM (outline)

1. Build and push the image to Azure Container Registry.
2. Deploy a Container App with port **8501**, min replicas 0–1.
3. Place the app behind **HTTPS** with Microsoft Entra ID or an authenticated reverse proxy.
4. Store secrets (API keys) in Key Vault / Container App secrets — not in the image.
5. Mount or sync SharePoint/OneDrive paths only if using file-based automation; prefer the HTTP API in [15-power-automate-guide.md](15-power-automate-guide.md).

## Production checklist

- [ ] Streamlit not exposed on `0.0.0.0` without auth
- [ ] `ESA_SKIP_VALIDATION` unset in production
- [ ] Templates versioned in filenames (`phase1_ecoventure_v2.1.docx`)
- [ ] Generation manifests saved next to issued reports on SharePoint
- [ ] Run `python scripts/health_check.py` after template or dependency changes

## Related

- [07-security-and-deployment.md](07-security-and-deployment.md)
- [15-power-automate-guide.md](15-power-automate-guide.md)
- [AUTOMATE.md](../AUTOMATE.md)
