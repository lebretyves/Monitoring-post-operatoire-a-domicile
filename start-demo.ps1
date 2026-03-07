param(
    [switch]$NoBrowser,
    [switch]$OpenDocs,
    [int]$DockerTimeoutSeconds = 180,
    [int]$ServiceTimeoutSeconds = 180
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendUrl = "http://localhost:5173"
$BackendUrl = "http://localhost:8000/health"
$BackendDocsUrl = "http://localhost:8000/docs"
$EnvFile = Join-Path $ProjectRoot ".env"
$EnvExampleFile = Join-Path $ProjectRoot ".env.example"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-Command {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-DockerDaemon {
    try {
        docker info | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Find-DockerDesktopPath {
    $candidates = @(
        (Join-Path $Env:ProgramFiles "Docker\Docker\Docker Desktop.exe"),
        (Join-Path $Env:LocalAppData "Programs\Docker\Docker\Docker Desktop.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    return $null
}

function Start-DockerDesktopIfNeeded {
    if (Test-DockerDaemon) {
        Write-Step "Docker daemon deja disponible"
        return
    }

    $dockerDesktopPath = Find-DockerDesktopPath
    if (-not $dockerDesktopPath) {
        throw "Docker Desktop introuvable. Installe Docker Desktop puis relance start-demo.ps1."
    }

    Write-Step "Demarrage de Docker Desktop"
    Start-Process -FilePath $dockerDesktopPath | Out-Null

    $deadline = (Get-Date).AddSeconds($DockerTimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 4
        if (Test-DockerDaemon) {
            Write-Step "Docker daemon pret"
            return
        }
    }

    throw "Docker Desktop a ete lance mais le daemon n'est pas pret apres $DockerTimeoutSeconds secondes."
}

function Ensure-EnvFile {
    if (Test-Path $EnvFile) {
        Write-Step ".env deja present"
        return
    }
    if (-not (Test-Path $EnvExampleFile)) {
        throw ".env.example introuvable dans le projet."
    }
    Copy-Item $EnvExampleFile $EnvFile
    Write-Step ".env cree depuis .env.example"
}

function Wait-HttpReady {
    param(
        [string]$Url,
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        }
        catch {
        }
        Start-Sleep -Seconds 3
    }

    return $false
}

function Show-FailureContext {
    Write-Host ""
    Write-Host "Etat courant Docker Compose:" -ForegroundColor Yellow
    docker compose ps
    Write-Host ""
    Write-Host "Derniers logs utiles:" -ForegroundColor Yellow
    docker compose logs --tail=80 backend frontend simulator
}

try {
    Set-Location $ProjectRoot

    if (-not (Test-Command "docker")) {
        throw "La commande 'docker' est introuvable. Installe Docker Desktop ou ajoute docker au PATH."
    }

    Write-Step "Preparation du projet"
    Ensure-EnvFile
    Start-DockerDesktopIfNeeded

    Write-Step "Validation Docker Compose"
    docker compose config | Out-Null

    Write-Step "Construction et demarrage de la stack"
    docker compose up --build -d

    Write-Step "Attente du backend"
    if (-not (Wait-HttpReady -Url $BackendUrl -TimeoutSeconds $ServiceTimeoutSeconds)) {
        Show-FailureContext
        throw "Le backend ne repond pas sur $BackendUrl"
    }

    Write-Step "Attente du frontend"
    if (-not (Wait-HttpReady -Url $FrontendUrl -TimeoutSeconds $ServiceTimeoutSeconds)) {
        Show-FailureContext
        throw "Le frontend ne repond pas sur $FrontendUrl"
    }

    Write-Host ""
    Write-Host "Stack prete" -ForegroundColor Green
    Write-Host "- Frontend : $FrontendUrl"
    Write-Host "- Backend  : http://localhost:8000"
    Write-Host "- Docs API : $BackendDocsUrl"
    Write-Host ""
    Write-Host "Pour suivre les logs : docker compose logs -f --tail=200" -ForegroundColor DarkGray
    Write-Host "Pour arreter : docker compose down -v" -ForegroundColor DarkGray

    if (-not $NoBrowser) {
        Write-Step "Ouverture du dashboard"
        Start-Process $FrontendUrl | Out-Null
        if ($OpenDocs) {
            Start-Process $BackendDocsUrl | Out-Null
        }
    }
}
catch {
    Write-Host ""
    Write-Host "Echec du lancement" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
