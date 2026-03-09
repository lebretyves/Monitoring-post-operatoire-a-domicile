param(
    [string]$ModelName = "qwen2.5:7b-instruct",
    [switch]$StartOllama
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $ProjectRoot ".env"

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

if ($StartOllama) {
    Write-Host "Demarrage du service Ollama..." -ForegroundColor Cyan
    docker compose up -d ollama
    if (-not (Wait-OllamaReady)) {
        throw "Ollama ne repond pas apres demarrage."
    }
}

Write-Host "Telechargement du modele Ollama..." -ForegroundColor Cyan
docker compose exec ollama ollama pull $ModelName

Write-Host ""
Write-Host "Modele pret: $ModelName" -ForegroundColor Green
Write-Host "Tu peux maintenant activer ENABLE_LLM=true et OLLAMA_MODEL=$ModelName dans .env" -ForegroundColor Green
