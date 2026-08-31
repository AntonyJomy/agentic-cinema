# Deploy frontend + backend to Cloud Run via Cloud Build.
#
# Prerequisites (once): .\scripts\setup-gcp.ps1
# Usage:                 .\scripts\deploy.ps1
#                        .\scripts\deploy.ps1 -Region us-central1

param(
    [string]$ProjectId = "script-clearance-hackathon",
    [string]$Region = "australia-southeast1"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "==> Submitting Cloud Build (project=$ProjectId region=$Region)"
Write-Host "    This builds and deploys api + web to Cloud Run."

gcloud builds submit `
    --project $ProjectId `
    --config cloudbuild.yaml `
    --substitutions="_REGION=$Region"

Write-Host ""
Write-Host "==> Fetching service URLs"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Cloud Build failed. Check the build log URL above."
    exit $LASTEXITCODE
}

$backend = gcloud run services describe agentic-cinema-api --project $ProjectId --region $Region --format="value(status.url)"
$frontend = gcloud run services describe agentic-cinema-web --project $ProjectId --region $Region --format="value(status.url)"
$frontendHost = ([uri]$frontend).Host

Write-Host ""
Write-Host "Frontend: $frontend"
Write-Host "Backend:  $backend"
Write-Host ""
Write-Host "Remember: add '$frontendHost' to Firebase Auth authorized domains."
