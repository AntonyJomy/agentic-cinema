# Deploy frontend + backend to Cloud Run via Cloud Build.
#
# Prerequisites (once): .\scripts\setup-gcp.ps1
# Usage:                 .\scripts\deploy.ps1
#                        .\scripts\deploy.ps1 -Region us-central1
#
# Reads project + Firebase web config from local .env (not committed).

param(
    [string]$ProjectId = "",
    [string]$Region = "australia-southeast1"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$EnvFile = Join-Path $Root ".env"
if (-not (Test-Path $EnvFile)) {
    throw "Missing $EnvFile - copy from .env.example and fill project/Firebase values."
}

function Get-DotEnvValue([string]$Name) {
    $line = Get-Content $EnvFile | Where-Object { $_ -match "^\s*$Name\s*=" } | Select-Object -First 1
    if (-not $line) { return $null }
    return ($line -split "=", 2)[1].Trim().Trim('"').Trim("'")
}

if (-not $ProjectId) {
    $ProjectId = Get-DotEnvValue "FIREBASE_PROJECT_ID"
    if (-not $ProjectId) { $ProjectId = Get-DotEnvValue "FIRESTORE_PROJECT" }
}
if (-not $ProjectId) {
    throw "Set FIREBASE_PROJECT_ID (or FIRESTORE_PROJECT) in .env, or pass -ProjectId."
}

$gcsBucket = Get-DotEnvValue "GCS_BUCKET_NAME"
$firestoreProject = Get-DotEnvValue "FIRESTORE_PROJECT"
$firestoreDatabase = Get-DotEnvValue "FIRESTORE_DATABASE"
$firebaseProjectId = Get-DotEnvValue "FIREBASE_PROJECT_ID"
if (-not $firebaseProjectId) { $firebaseProjectId = $firestoreProject }

$viteAuthDomain = Get-DotEnvValue "VITE_FIREBASE_AUTH_DOMAIN"
$viteProjectId = Get-DotEnvValue "VITE_FIREBASE_PROJECT_ID"
$viteAppId = Get-DotEnvValue "VITE_FIREBASE_APP_ID"
$viteStorageBucket = Get-DotEnvValue "VITE_FIREBASE_STORAGE_BUCKET"
$viteMessagingSenderId = Get-DotEnvValue "VITE_FIREBASE_MESSAGING_SENDER_ID"

$required = @{
    GCS_BUCKET_NAME = $gcsBucket
    FIRESTORE_PROJECT = $firestoreProject
    FIRESTORE_DATABASE = $firestoreDatabase
    FIREBASE_PROJECT_ID = $firebaseProjectId
    VITE_FIREBASE_AUTH_DOMAIN = $viteAuthDomain
    VITE_FIREBASE_PROJECT_ID = $viteProjectId
    VITE_FIREBASE_APP_ID = $viteAppId
    VITE_FIREBASE_STORAGE_BUCKET = $viteStorageBucket
    VITE_FIREBASE_MESSAGING_SENDER_ID = $viteMessagingSenderId
}
foreach ($name in $required.Keys) {
    if (-not $required[$name]) {
        throw "Missing $name in .env"
    }
}

# Cloud Build substitutions use comma separators; values must not contain commas.
$subs = @(
    "_REGION=$Region",
    "_GCS_BUCKET=$gcsBucket",
    "_FIRESTORE_PROJECT=$firestoreProject",
    "_FIRESTORE_DATABASE=$firestoreDatabase",
    "_FIREBASE_PROJECT_ID=$firebaseProjectId",
    "_VITE_FIREBASE_AUTH_DOMAIN=$viteAuthDomain",
    "_VITE_FIREBASE_PROJECT_ID=$viteProjectId",
    "_VITE_FIREBASE_APP_ID=$viteAppId",
    "_VITE_FIREBASE_STORAGE_BUCKET=$viteStorageBucket",
    "_VITE_FIREBASE_MESSAGING_SENDER_ID=$viteMessagingSenderId"
) -join ","

Write-Host "==> Submitting Cloud Build (project=$ProjectId region=$Region)"
Write-Host "    Config from .env; Firebase API key from Secret Manager."

gcloud builds submit `
    --project $ProjectId `
    --config cloudbuild.yaml `
    --substitutions=$subs

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
