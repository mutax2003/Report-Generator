# Run a project script with the repo venv Python (Windows).
# Usage: .\run.ps1 scripts\create_samples.py
#        .\run.ps1 scripts\test_with_your_documents.py --excel user_test\my_project_data.xlsx
#        .\run.ps1 streamlit

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Script,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$Root = $PSScriptRoot
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Error "Virtual env not found. Run: python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt"
    exit 1
}

if ($Script -eq "streamlit") {
    & $VenvPython -m streamlit run (Join-Path $Root "app.py") @Args
    exit $LASTEXITCODE
}

$ScriptPath = Join-Path $Root $Script
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Script not found: $ScriptPath"
    exit 1
}

& $VenvPython $ScriptPath @Args
exit $LASTEXITCODE
