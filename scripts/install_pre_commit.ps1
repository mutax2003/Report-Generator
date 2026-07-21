#Requires -Version 5.1
<#
  Install pre-commit hooks for ESA Report Generator (optional).

  pip install pre-commit
  .\scripts\install_pre_commit.ps1
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

Push-Location $Root
try {
    & .\.venv\Scripts\python.exe -m pip install pre-commit -q
    & .\.venv\Scripts\pre-commit.exe install
    Write-Host "Installed pre-commit hook: UX tier runs when app.py or ui/ is staged."
    Write-Host "Skip once: git commit --no-verify"
} finally {
    Pop-Location
}
