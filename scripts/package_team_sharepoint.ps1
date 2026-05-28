# Package consultant-facing files for upload to SharePoint / Teams.
# Usage: .\scripts\package_team_sharepoint.ps1
# Output: dist\team-sharepoint\ (zip-friendly folder tree)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Out = Join-Path $Root "dist\team-sharepoint"

if (Test-Path $Out) {
    Remove-Item -Recurse -Force $Out
}
New-Item -ItemType Directory -Path $Out -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Out "Guides") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Out "Templates") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Out "Templates\Alberta_Phase1") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Out "Templates\Production") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Out "Templates\Demo") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Out "Templates\Groundwater") -Force | Out-Null

function Copy-IfExists($src, $dest) {
    if (Test-Path $src) {
        Copy-Item -LiteralPath $src -Destination $dest -Force
        Write-Host "  $dest"
    } else {
        Write-Warning "Missing: $src (run: python scripts\create_samples.py)"
    }
}

Write-Host "Packaging team SharePoint bundle to $Out"

# Guides (from repo docs and quick refs)
Copy-IfExists (Join-Path $Root "docs\00-start-here.md") (Join-Path $Out "Guides\00-start-here.md")
Copy-IfExists (Join-Path $Root "docs\02-user-guide.md") (Join-Path $Out "Guides\02-user-guide-streamlit.md")
Copy-IfExists (Join-Path $Root "docs\03-excel-data-guide.md") (Join-Path $Out "Guides\03-excel-data-guide.md")
Copy-IfExists (Join-Path $Root "docs\04-template-authoring.md") (Join-Path $Out "Guides\04-template-authoring.md")
Copy-IfExists (Join-Path $Root "docs\10-glossary-faq.md") (Join-Path $Out "Guides\10-glossary-faq.md")
Copy-IfExists (Join-Path $Root "docs\11-alberta-phase1-esa.md") (Join-Path $Out "Guides\11-alberta-phase1-esa.md")
Copy-IfExists (Join-Path $Root "EXCEL_LAYOUT.txt") (Join-Path $Out "Guides\EXCEL_LAYOUT.txt")
Copy-IfExists (Join-Path $Root "JINJA2_CHEATSHEET.txt") (Join-Path $Out "Guides\JINJA2_CHEATSHEET.txt")
Copy-IfExists (Join-Path $Root "BEST_PRACTICES.md") (Join-Path $Out "Guides\BEST_PRACTICES.md")
Copy-IfExists (Join-Path $Root "docs\16-team-rollout.md") (Join-Path $Out "Guides\16-team-rollout-for-admins.md")
Copy-IfExists (Join-Path $Root "docs\18-groundwater-reports.md") (Join-Path $Out "Guides\18-groundwater-reports.md")
Copy-IfExists (Join-Path $Root "docs\19-charts-and-gis-embed.md") (Join-Path $Out "Guides\19-charts-and-gis-embed.md")

# Versioned template samples (rename with your org version when publishing)
Copy-IfExists (Join-Path $Root "samples\phase1_alberta_data.xlsx") (Join-Path $Out "Templates\Alberta_Phase1\phase1_alberta_data_v2.1.xlsx")
Copy-IfExists (Join-Path $Root "samples\phase1_alberta_template.docx") (Join-Path $Out "Templates\Alberta_Phase1\phase1_alberta_template_v2.1.docx")
Copy-IfExists (Join-Path $Root "samples\production_data.xlsx") (Join-Path $Out "Templates\Production\production_data_v2.1.xlsx")
Copy-IfExists (Join-Path $Root "samples\production_template.docx") (Join-Path $Out "Templates\Production\production_template_v2.1.docx")
Copy-IfExists (Join-Path $Root "samples\production_starter_template.docx") (Join-Path $Out "Templates\Production\production_starter_template_v2.1.docx")
Copy-IfExists (Join-Path $Root "samples\sample_data.xlsx") (Join-Path $Out "Templates\Demo\sample_data.xlsx")
Copy-IfExists (Join-Path $Root "samples\sample_template.docx") (Join-Path $Out "Templates\Demo\sample_template.docx")
Copy-IfExists (Join-Path $Root "samples\groundwater_monitoring_data.xlsx") (Join-Path $Out "Templates\Groundwater\groundwater_monitoring_data_v2.1.xlsx")
Copy-IfExists (Join-Path $Root "samples\groundwater_monitoring_template.docx") (Join-Path $Out "Templates\Groundwater\groundwater_monitoring_template_v2.1.docx")

$readme = @"
# ESA Report Generator — SharePoint bundle

Upload this folder to your Microsoft 365 **Templates** or **ESA Reports** library.

## Folders

- **Guides/** — consultant and template-author documentation (start with ``00-start-here.md``)
- **Templates/** — gold-copy Excel + Word samples; bump ``v2.1`` in filenames when you publish updates

## Do not upload here

- Client-specific final reports or confidential PDFs (keep on project SharePoint sites only)
- Files listed in repo ``.gitignore`` under ``samples/*Devon*``, ``samples/*R*.docx``, etc.

## App URL

After IT deploys the internal app, add the team link to this library description:
``https://esa-reports.YOURCOMPANY.internal`` (replace with your hostname).

Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm")
Repo: https://github.com/mutax2003/Report-Generator
"@
Set-Content -Path (Join-Path $Out "README.txt") -Value $readme -Encoding UTF8

Write-Host ""
Write-Host "Done. Upload dist\team-sharepoint to SharePoint or zip and share on Teams."
Write-Host "See sharepoint\PUBLISH_CHECKLIST.md for step-by-step publishing."
