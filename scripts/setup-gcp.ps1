# One-time GCP setup for Agentic Cinema Cloud Run deploy pipeline.
# Requires: gcloud CLI, authenticated user with Owner/Editor on the project.
#
# Usage:
#   .\scripts\setup-gcp.ps1
#   .\scripts\setup-gcp.ps1 -ProjectId script-clearance-hackathon -Region australia-southeast1

param(
    [string]$ProjectId = "script-clearance-hackathon",
    [string]$Region = "australia-southeast1",
    [string]$ArtifactRepo = "agentic-cinema"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$EnvFile = Join-Path $Root ".env"

Write-Host "==> Using project $ProjectId (region $Region)"
gcloud config set project $ProjectId | Out-Null

Write-Host "==> Enabling APIs"
$apis = @(
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "firestore.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com"
)
gcloud services enable @apis

Write-Host "==> Creating Artifact Registry repo (if missing)"
$prevErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$describeOutput = & gcloud artifacts repositories describe $ArtifactRepo --location=$Region 2>&1
$describeExit = $LASTEXITCODE
$ErrorActionPreference = $prevErrorAction

if ($describeExit -eq 0) {
    Write-Host "    Repo already exists"
} else {
    Write-Host "    Creating repo $ArtifactRepo in $Region"
    gcloud artifacts repositories create $ArtifactRepo `
        --repository-format=docker `
        --location=$Region `
        --description="Agentic Cinema container images"
}

Write-Host "==> Creating secrets from .env (if missing)"
if (-not (Test-Path $EnvFile)) {
    throw "Missing $EnvFile - needed to seed GEMINI_API_KEY, PARALLEL_API_KEY, and VITE_FIREBASE_API_KEY"
}

function Get-DotEnvValue([string]$Name) {
    $line = Get-Content $EnvFile | Where-Object { $_ -match "^\s*$Name\s*=" } | Select-Object -First 1
    if (-not $line) { return $null }
    return ($line -split "=", 2)[1].Trim().Trim('"').Trim("'")
}

function Ensure-Secret([string]$SecretName, [string]$Value) {
    if (-not $Value) {
        Write-Host "    SKIP $SecretName (no value in .env)"
        return
    }
    $prevErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & gcloud secrets describe $SecretName 2>&1 | Out-Null
    $exists = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prevErrorAction

    if (-not $exists) {
        Write-Host "    Creating secret $SecretName"
        $Value | gcloud secrets create $SecretName --data-file=-
    } else {
        Write-Host "    Adding new version for $SecretName"
        $Value | gcloud secrets versions add $SecretName --data-file=-
    }
}

$gemini = Get-DotEnvValue "GEMINI_API_KEY"
if (-not $gemini) { $gemini = Get-DotEnvValue "GOOGLE_API_KEY" }
$parallel = Get-DotEnvValue "PARALLEL_API_KEY"
$firebaseWeb = Get-DotEnvValue "VITE_FIREBASE_API_KEY"
if (-not $firebaseWeb) { $firebaseWeb = Get-DotEnvValue "FIREBASE_WEB_API_KEY" }

Ensure-Secret "GEMINI_API_KEY" $gemini
Ensure-Secret "PARALLEL_API_KEY" $parallel
# Used by Cloud Build to bake the Firebase web client key into the frontend image.
# Prefer a rotated key after any public leak; never commit this value to git.
Ensure-Secret "FIREBASE_WEB_API_KEY" $firebaseWeb

Write-Host "==> Granting Cloud Build permissions"
$projectNumber = gcloud projects describe $ProjectId --format="value(projectNumber)"
$cloudbuildSa = "$projectNumber@cloudbuild.gserviceaccount.com"
$computeSa = "$projectNumber-compute@developer.gserviceaccount.com"

$cbRoles = @(
    "roles/run.admin",
    "roles/iam.serviceAccountUser",
    "roles/artifactregistry.writer",
    "roles/secretmanager.secretAccessor",
    "roles/storage.admin"
)
foreach ($role in $cbRoles) {
    gcloud projects add-iam-policy-binding $ProjectId `
        --member="serviceAccount:$cloudbuildSa" `
        --role=$role `
        --condition=None `
        --quiet | Out-Null
}

Write-Host "==> Granting Cloud Run runtime access to secrets + data"
foreach ($role in @("roles/secretmanager.secretAccessor", "roles/datastore.user", "roles/storage.objectAdmin")) {
    gcloud projects add-iam-policy-binding $ProjectId `
        --member="serviceAccount:$computeSa" `
        --role=$role `
        --condition=None `
        --quiet | Out-Null
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "Deploy with:  .\scripts\deploy.ps1"
Write-Host ""
Write-Host "After first deploy, add the Cloud Run frontend hostname to:"
Write-Host "  Firebase Console > Authentication > Settings > Authorized domains"
