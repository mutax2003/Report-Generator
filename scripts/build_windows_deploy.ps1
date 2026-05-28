# Build Windows deployment folder + optional ESA-Report-Generator.exe launcher.
# Usage:
#   .\scripts\build_windows_deploy.ps1
#   .\scripts\build_windows_deploy.ps1 -BuildExe
#   .\scripts\build_windows_deploy.ps1 -SkipVenvInstall   # copy only; install on target PC

param(
    [switch]$BuildExe,
    [switch]$SkipVenvInstall,
    [switch]$SkipSamples
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Out = Join-Path $Root "dist\ESA-Report-Generator"
$RuntimeVenv = Join-Path $Out "runtime\.venv"
$DevVenvPython = Join-Path $Root ".venv\Scripts\python.exe"

function Write-Step($msg) {
    Write-Host "`n=== $msg ===" -ForegroundColor Cyan
}

if (-not (Test-Path $DevVenvPython)) {
    Write-Error "Dev venv missing. Run: python -m venv .venv; pip install -r requirements.txt"
}

if (Test-Path $Out) {
    Remove-Item -Recurse -Force $Out
}
New-Item -ItemType Directory -Path $Out -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Out "runtime") -Force | Out-Null

Write-Step "Generate samples"
if (-not $SkipSamples) {
    & $DevVenvPython (Join-Path $Root "scripts\create_samples.py")
    & $DevVenvPython (Join-Path $Root "scripts\tag_production_template.py")
}

Write-Step "Copy application files"
$excludeDirs = @(
    ".git", ".venv", "dist", "out", "user_test", "__pycache__", ".pytest_cache",
    ".cursor", "terminals", "node_modules"
)
$excludeFiles = @("*.pyc", "*.pyo")

Get-ChildItem -Path $Root -Force | ForEach-Object {
    $name = $_.Name
    if ($excludeDirs -contains $name) { return }
    if ($name -match '^\.' -and $name -notin @(".streamlit")) { return }
    $dest = Join-Path $Out $name
    if ($_.PSIsContainer) {
        Copy-Item -LiteralPath $_.FullName -Destination $dest -Recurse -Force
    } else {
        Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
    }
}

# Trim heavy / confidential patterns from deploy copy
$trimPatterns = @(
    "samples\*.pdf",
    "samples\*Devon*",
    "samples\00_*.docx",
    "samples\25*R*.docx",
    "samples\26*R*.docx",
    "samples\*markup*",
    "samples\*Secure*"
)
foreach ($pat in $trimPatterns) {
    Get-ChildItem -Path (Join-Path $Out $pat) -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse
}

Write-Step "Fetch brand assets"
& $DevVenvPython (Join-Path $Root "scripts\fetch_ecoventure_assets.py") 2>$null

if (-not $SkipVenvInstall) {
    Write-Step "Create portable runtime venv (may take several minutes)"
    $sysPy = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $sysPy) { $sysPy = "python" }
    & $sysPy -m venv $RuntimeVenv
    $pip = Join-Path $RuntimeVenv "Scripts\pip.exe"
    & $pip install --upgrade pip
    & $pip install -r (Join-Path $Out "requirements.txt")
}

Write-Step "Launcher scripts"
@'
@echo off
cd /d "%~dp0"
if not exist "runtime\.venv\Scripts\python.exe" (
  echo Run Install-Dependencies.ps1 first.
  pause
  exit /b 1
)
start "" "http://localhost:8501"
if exist "ESA-Report-Generator.exe" (
  "ESA-Report-Generator.exe"
) else (
  runtime\.venv\Scripts\python.exe esa_launcher.py
)
pause
'@ | Set-Content -Path (Join-Path $Out "Start-ESA-Report-Generator.bat") -Encoding ASCII

@'
# One-time setup on target PC (requires Python 3.11+ on PATH)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
python -m venv "$Root\runtime\.venv"
& "$Root\runtime\.venv\Scripts\pip.exe" install --upgrade pip
& "$Root\runtime\.venv\Scripts\pip.exe" install -r "$Root\requirements.txt"
Write-Host "Done. Double-click Start-ESA-Report-Generator.bat or ESA-Report-Generator.exe"
'@ | Set-Content -Path (Join-Path $Out "Install-Dependencies.ps1") -Encoding UTF8

if ($BuildExe) {
    Write-Step "Build ESA-Report-Generator.exe (PyInstaller)"
    $pip = Join-Path $Root ".venv\Scripts\pip.exe"
    & $pip install pyinstaller --quiet
    $launcher = Join-Path $Out "esa_launcher.py"
    Copy-Item (Join-Path $Root "esa_launcher.py") $launcher -Force
    Push-Location $Out
    try {
        & (Join-Path $Root ".venv\Scripts\pyinstaller.exe") `
            --onefile `
            --name "ESA-Report-Generator" `
            --console `
            --clean `
            esa_launcher.py
        Move-Item -Force (Join-Path $Out "dist\ESA-Report-Generator.exe") (Join-Path $Out "ESA-Report-Generator.exe")
        Remove-Item -Recurse -Force (Join-Path $Out "build"), (Join-Path $Out "dist\ESA-Report-Generator") -ErrorAction SilentlyContinue
        Remove-Item (Join-Path $Out "ESA-Report-Generator.spec") -ErrorAction SilentlyContinue
    } finally {
        Pop-Location
    }
}

$readme = @"
# ESA Report Generator — Windows deployment

## Quick start (this PC)

1. If ``runtime\.venv`` is missing, run **Install-Dependencies.ps1** (requires Python 3.11+ installed once).
2. Double-click **ESA-Report-Generator.exe** or **Start-ESA-Report-Generator.bat**.
3. Browser opens http://localhost:8501

## Team rollout

- Copy the entire ``ESA-Report-Generator`` folder to a network share or each PC.
- Do not split the folder — keep ``runtime\.venv``, ``samples``, ``assets``, and ``schemas`` together.

## Optional environment

- ``ESA_PORT=8502`` — alternate port
- ``ESA_BIND_ALL=1`` — listen on all interfaces (internal server only; use firewall + HTTPS)

## Docker / server

See docs\14-deployment.md in the source repo for Docker and Azure hosting.

Created by Andrew Liu, Ecoventure Inc., Copyright 2026

Built: $(Get-Date -Format 'yyyy-MM-dd HH:mm')
"@
Set-Content -Path (Join-Path $Out "README-DEPLOY.txt") -Value $readme -Encoding UTF8

Write-Step "Done"
Write-Host "Deployment package: $Out" -ForegroundColor Green
if (Test-Path (Join-Path $Out "ESA-Report-Generator.exe")) {
    Write-Host "Executable: $(Join-Path $Out 'ESA-Report-Generator.exe')" -ForegroundColor Green
}
