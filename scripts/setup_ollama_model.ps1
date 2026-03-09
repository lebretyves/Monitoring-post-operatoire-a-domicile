param(
    [string]$ModelName = "meditron-8b-local",
    [string]$GgufFilename = "",
    [string]$HostModelsDir = "",
    [switch]$StartOllama
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $ProjectRoot ".env"
$TemplatePath = Join-Path $ProjectRoot "infra\ollama\Modelfile.meditron.template"
$TargetModelfile = Join-Path $ProjectRoot "infra\ollama\Modelfile.local"

function Read-EnvValue {
    param(
        [string]$Path,
        [string]$Key
    )
    if (-not (Test-Path $Path)) {
        return $null
    }
    $line = Get-Content $Path | Where-Object { $_ -match "^\s*$Key=" } | Select-Object -First 1
    if (-not $line) {
        return $null
    }
    return ($line -split "=", 2)[1].Trim()
}

function Wait-OllamaReady {
    param([int]$TimeoutSeconds = 120)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            docker compose exec ollama ollama list | Out-Null
            return $true
        }
        catch {
            Start-Sleep -Seconds 3
        }
    }
    return $false
}

if (-not $HostModelsDir) {
    $HostModelsDir = Read-EnvValue -Path $EnvFile -Key "OLLAMA_GGUF_HOST_DIR"
}
if (-not $HostModelsDir) {
    $HostModelsDir = "C:\models"
}

if (-not (Test-Path $HostModelsDir)) {
    New-Item -ItemType Directory -Path $HostModelsDir -Force | Out-Null
}

if (-not $GgufFilename) {
    $GgufFilename = Read-EnvValue -Path $EnvFile -Key "OLLAMA_GGUF_FILENAME"
}
if (-not $GgufFilename) {
    $GgufFilename = "Meditron3-8B.Q4_0.gguf"
}

$GgufPath = Join-Path $HostModelsDir $GgufFilename
if (-not (Test-Path $GgufPath)) {
    throw "Fichier GGUF introuvable: $GgufPath"
}

$template = Get-Content -Raw $TemplatePath
$template.Replace("{{GGUF_FILENAME}}", $GgufFilename) | Set-Content -NoNewline $TargetModelfile

Write-Host "Modelfile genere: $TargetModelfile" -ForegroundColor Cyan
Write-Host "GGUF detecte: $GgufPath" -ForegroundColor Cyan

if ($StartOllama) {
    Write-Host "Demarrage du service Ollama..." -ForegroundColor Cyan
    docker compose up -d ollama
    if (-not (Wait-OllamaReady)) {
        throw "Ollama ne repond pas apres demarrage."
    }
}

Write-Host "Creation du modele local dans Ollama..." -ForegroundColor Cyan
docker compose exec ollama ollama create $ModelName -f /modelfiles/Modelfile.local

Write-Host ""
Write-Host "Modele pret: $ModelName" -ForegroundColor Green
Write-Host "Tu peux maintenant activer ENABLE_LLM=true et OLLAMA_MODEL=$ModelName dans .env" -ForegroundColor Green
