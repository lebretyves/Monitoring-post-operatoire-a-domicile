param(
    [string]$RepoId = "QuantFactory/Meditron3-8B-GGUF",
    [string]$Filename = "Meditron3-8B.Q4_0.gguf",
    [string]$LocalDir = "C:\models"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Get-Command huggingface-cli -ErrorAction SilentlyContinue)) {
    throw "huggingface-cli introuvable. Installe-le avec: py -m pip install -U huggingface_hub"
}

if (-not (Test-Path $LocalDir)) {
    New-Item -ItemType Directory -Path $LocalDir -Force | Out-Null
}

Write-Host "Telechargement de $Filename depuis $RepoId vers $LocalDir" -ForegroundColor Cyan
huggingface-cli download $RepoId $Filename --local-dir $LocalDir --local-dir-use-symlinks False

Write-Host ""
Write-Host "GGUF telecharge: $(Join-Path $LocalDir $Filename)" -ForegroundColor Green
