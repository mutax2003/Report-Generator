# Security regression checks (run from project root with venv active)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "=== unittest (security) ===" -ForegroundColor Cyan
.\.venv\Scripts\python.exe -m unittest tests.test_security -v

Write-Host "`n=== CLI smoke render ===" -ForegroundColor Cyan
.\.venv\Scripts\python.exe scripts\render_cli.py

Write-Host "`n=== pip-audit (install if missing) ===" -ForegroundColor Cyan
.\.venv\Scripts\pip.exe install pip-audit -q 2>$null
.\.venv\Scripts\pip-audit.exe -r requirements.txt

Write-Host "`nAll security checks finished." -ForegroundColor Green
