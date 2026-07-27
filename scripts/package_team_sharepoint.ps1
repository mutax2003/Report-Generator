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
Copy-IfExists (Join-Path $Root "docs\25-agent-folder-report.md") (Join-Path $Out "Guides\25-agent-folder-report.md")
Copy-IfExists (Join-Path $Root "docs\26-alberta-prompt-library.md") (Join-Path $Out "Guides\26-alberta-prompt-library.md")
Copy-IfExists (Join-Path $Root "docs\14-deployment.md") (Join-Path $Out "Guides\14-deployment-hosting.md")

# Pilot briefing (Cloud = sample-only)
$cloudUrl = "https://mutax2003-report-generator-app-ad7xpb.streamlit.app/"
$pilotBriefing = @"
ESA Report Generator - 3-5 person pilot briefing
================================================
(Full exit criteria: Guides/16-team-rollout-for-admins.md)

App (sample data ONLY): $cloudUrl
Settings required: Python 3.12 ; secrets ESA_HOSTED_MODE = "1"
Pushed commit should include hosted menubar hide (no Open project folder on Cloud).

Roles: Phase I author ; Phase II (optional) ; template owner ; QA

Path (<5 min):
  1. Open app -> Continue with Excel + template
  2. File -> Load Alberta Phase I sample
  3. Report tab -> pre-flight -> Generate
  4. Download deliverable package (.zip)

Rules:
  - Cloud / public URL = sample or synthetic data only - no client-confidential uploads
  - Help: in-app Help & documentation expander (F1 local help does not work on Cloud)
  - Gold Excel/Word pair: Templates/Alberta_Phase1/*_v2.1.*
  - Real client work -> Docker / Entra host (docs/14-deployment.md Hosting lock)

Exit criteria: Guides/16-team-rollout-for-admins.md -> Pilot exit criteria
"@
Set-Content -Path (Join-Path $Out "PILOT-BRIEFING.txt") -Value $pilotBriefing -Encoding utf8
Copy-Item -LiteralPath (Join-Path $Out "PILOT-BRIEFING.txt") -Destination (Join-Path $Out "Guides\PILOT-BRIEFING.txt") -Force

$teamsPost = @"
ESA Report Generator - pilot kickoff

App (sample data ONLY): $cloudUrl
SharePoint: [paste library link] -> Templates/Alberta Phase I + Guides

Path (<5 min):
1) Continue with Excel + template
2) File -> Load Alberta Phase I sample
3) Report -> pre-flight -> Generate -> Download deliverable package (.zip)

Rules:
- Upload ONLY the Alberta sample (or synthetic training data). No client-confidential files on Cloud.
- Help: in-app Help & documentation on the Report tab (F1 does not work on Cloud).
- Real client work waits for the internal Docker + Entra host.

Questions: [template owner]
"@
Set-Content -Path (Join-Path $Out "TEAMS-POST.txt") -Value $teamsPost -Encoding utf8

$opsHandoff = @"
ESA Report Generator - ops handoff
==================================
Cloud: $cloudUrl
Repo: https://github.com/mutax2003/Report-Generator

1) share.streamlit.io -> Reboot after push; Python 3.12; ESA_HOSTED_MODE=1
2) Smoke: Load Alberta sample -> Generate -> zip; File menu must NOT show Open project folder
3) Upload this folder to SharePoint (see sharepoint/PUBLISH_CHECKLIST.md)
4) Paste TEAMS-POST.txt into Teams
5) After pilot feedback: Cloud stays sample-only; client work -> Docker/Entra (docs/14)
"@
Set-Content -Path (Join-Path $Out "OPS-HANDOFF.txt") -Value $opsHandoff -Encoding utf8

$hostingLock = @"
ESA Report Generator - HOSTING LOCK (agreed)
============================================
Date: $(Get-Date -Format "yyyy-MM-dd")
Commit: see GitHub master (pilot close-out)

| Workload | Host | Data |
|----------|------|------|
| Sample / synthetic pilot, UX feedback | Streamlit Community Cloud | Sample data ONLY |
| Real client Phase I/II / confidential PDFs | Docker or Windows VM + Entra/VPN | Client project sites |

Cloud URL (sample only): $cloudUrl
Secrets: ESA_HOSTED_MODE = "1" ; Python 3.12 ; prefer no packages.txt

DO NOT expand Community Cloud into a production client pipeline.
See Guides/14-deployment-hosting.md section "Hosting lock (after pilot)".
"@
Set-Content -Path (Join-Path $Out "HOSTING-LOCK.txt") -Value $hostingLock -Encoding utf8
Copy-Item -LiteralPath (Join-Path $Out "HOSTING-LOCK.txt") -Destination (Join-Path $Out "Guides\HOSTING-LOCK.txt") -Force

$pilotExit = @"
ESA Report Generator - pilot exit checklist (3-5 people)
=======================================================
App: $cloudUrl
Full criteria: Guides/16-team-rollout-for-admins.md

Per pilot user:
[ ] Continue with Excel + template
[ ] File -> Load Alberta Phase I sample
[ ] Report -> pre-flight -> Generate
[ ] Download deliverable package (.zip); save manifest if shown
[ ] File menu has NO "Open project folder"
[ ] Help usable via in-app Help / Help menu (F1 file:// not required)
[ ] First zip under ~5 minutes unaided
[ ] At most 2 "which download?" support questions

Roll-up:
[ ] All pilots completed zip download without IT help
[ ] Template owner signed gold Phase I pair (Templates/Alberta_Phase1/*_v2.1.*)
[ ] HOSTING-LOCK.txt acknowledged (Cloud = sample-only; client work = Docker/Entra)

Agent pre-check ($(Get-Date -Format "yyyy-MM-dd")):
[x] Working tree clean of sample noise
[x] SharePoint pack regenerated (dist/team-sharepoint)
[x] Cloud hosted picker + no folder menu verified in prior smoke
[ ] Human pilots 1-5: fill rows above when complete
"@
Set-Content -Path (Join-Path $Out "PILOT-EXIT-CHECKLIST.txt") -Value $pilotExit -Encoding utf8
Copy-Item -LiteralPath (Join-Path $Out "PILOT-EXIT-CHECKLIST.txt") -Destination (Join-Path $Out "Guides\PILOT-EXIT-CHECKLIST.txt") -Force

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

- **Pilot (sample data only):** ``https://mutax2003-report-generator-app-ad7xpb.streamlit.app/`` — Alberta Phase I sample → Generate → zip. No client-confidential uploads.
- **Production:** Internal Docker/Entra host (see ``docs/14-deployment.md`` Hosting lock). Replace placeholder:
  ``https://esa-reports.YOURCOMPANY.internal``

Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm")
Repo: https://github.com/mutax2003/Report-Generator
"@
Set-Content -Path (Join-Path $Out "README.txt") -Value $readme -Encoding UTF8

Write-Host ""
Write-Host "Done. Upload dist\team-sharepoint to SharePoint or zip and share on Teams."
Write-Host "See sharepoint\PUBLISH_CHECKLIST.md for step-by-step publishing."
