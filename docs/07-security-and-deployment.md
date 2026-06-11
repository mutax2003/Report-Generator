# 07 — Security and deployment

## Threat model

The application accepts **untrusted uploads** (Excel and Word) from internal users. Word templates are **trusted code** (Jinja2 can loop and branch). Attack surfaces:

- Malicious ZIP / zip bombs in `.xlsx` / `.docx`
- Oversized files (DoS)
- Path traversal inside archives
- Formula injection via cell strings re-opened in Excel
- Information disclosure via stack traces
- Unauthorized network exposure of Streamlit or HTTP render service

## Controls implemented

### File size limits

| Asset | Max size |
|-------|----------|
| Excel upload | 15 MB |
| Template upload | 30 MB |
| Rendered output | 50 MB |

### ZIP / OOXML validation

- Magic bytes `PK\x03\x04` required.
- Excel must contain spreadsheet-related parts.
- Template must contain `word/document.xml`.
- Max 5,000 ZIP members; decompressed total capped (120 MB read budget).
- Rejects `..` and absolute paths in member names.
- Rejects encrypted ZIP entries.
- Compression ratio check (ratio > 80 flagged as bomb).

### Jinja2

- **Main report:** `SandboxedEnvironment` with `StrictUndefined` during `doc.render`. Missing scalar tags warn and render empty — render does not crash.
- **Auto-generated appendices (A/D/G):** same sandbox with lenient `Undefined` so sparse Excel rows do not abort appendix render; missing keys render blank (same consultant outcome as empty main-report tags).
- Templates treated as trusted — sandbox blocks dangerous Python, not malicious template authors.

### Context limits

| Limit | Value |
|-------|-------|
| Lab rows | 10,000 (truncate + warn) |
| Project columns | 300 |
| String value length | 32,768 |
| Meta value length | 500 |
| Download filename | 200 chars, sanitized |

### Output validation

Rendered `.docx` re-validated as ZIP with `word/document.xml` before download.

### Error redaction

`user_safe_error()` shows:

- Known safe `ValueError` prefixes (missing sheet, template render message)
- `SecurityError` messages
- Generic message for other exceptions (details logged server-side)

### Formula injection

Cell strings starting with `=+-@\t\r` get leading `'` in `_cell_str`.

## Environment variables

| Variable | Effect |
|----------|--------|
| `ESA_VALIDATION_BYPASS=1` | Skip upload validation (tests only) |
| `OPENAI_API_KEY` | Enables cloud LLM in AI tab |

## Deployment guidance

### Recommended: localhost internal use

```powershell
streamlit run app.py
```

Default binds localhost. Suitable for consultant workstations.

### Not recommended without controls

- `streamlit run --server.address 0.0.0.0` on public internet
- HTTP render service exposed outside VPN

### If network access required

- VPN or private network only
- Reverse proxy with authentication (Azure AD, etc.)
- TLS termination at proxy
- Separate service account with minimal file system access

### Secrets

- Store `OPENAI_API_KEY` in `.streamlit/secrets.toml` (gitignored) or OS environment
- Never commit API keys or client `.docx` deliverables with PII to public repos

### Production template

`22xxxxR Phase 2 ESA Full_merge.docx` is gitignored — keep client templates on secure shares.

## Dependency audit

```powershell
pip install pip-audit
pip-audit -r requirements.txt
```

Security script:

```powershell
.\scripts\run_security_checks.ps1
```

## Operational checklist

- [ ] Run on patched Python 3.10+
- [ ] Limit who can edit Word templates
- [ ] Archive manifests with issued reports
- [ ] Review pre-flight warnings before client delivery
- [ ] Disable cloud LLM if data must stay offline
- [ ] Do not commit `.streamlit/secrets.toml`

## Adjusting limits

Edit constants at top of [`security.py`](../security.py). Re-run `tests/test_security.py` and `tests/test_edge_cases.py` after changes.
