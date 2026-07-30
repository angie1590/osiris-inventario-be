$ErrorActionPreference = "Stop"

param(
  [string]$Branch = "main",
  [switch]$SkipGitPull,
  [switch]$SkipBuild
)

$BackendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendDir = Join-Path (Split-Path -Parent $BackendDir) "osiris-inventario-fe"
$ComposeFile = Join-Path $BackendDir "docker-compose.prod.yml"
$EnvFile = Join-Path $BackendDir ".env.prod"

function Assert-Path($Path, $Message) {
  if (-not (Test-Path $Path)) {
    throw $Message
  }
}

function Assert-Command($Name, $Message) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw $Message
  }
}

function Wait-HttpOk($Url, [int]$Attempts = 90) {
  for ($i = 0; $i -lt $Attempts; $i++) {
    Start-Sleep -Seconds 2
    try {
      $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
      if ($resp.StatusCode -eq 200) {
        return $true
      }
    }
    catch {
    }
  }
  return $false
}

Assert-Path $ComposeFile "No se encontro docker-compose.prod.yml en $BackendDir"
Assert-Path $EnvFile "No se encontro .env.prod en $BackendDir. Ejecuta install-windows.ps1 primero."
Assert-Path $FrontendDir "No se encontro carpeta frontend esperada en $FrontendDir"

Assert-Command docker "Docker no esta disponible."
Assert-Command git "Git no esta disponible."

docker info | Out-Null

docker compose version | Out-Null

if (-not $SkipGitPull) {
  if (Test-Path (Join-Path $BackendDir ".git")) {
    Write-Host "Actualizando backend ($Branch)..."
    git -C $BackendDir fetch --all --prune
    git -C $BackendDir checkout $Branch
    git -C $BackendDir pull --ff-only origin $Branch
  }

  if (Test-Path (Join-Path $FrontendDir ".git")) {
    Write-Host "Actualizando frontend ($Branch)..."
    git -C $FrontendDir fetch --all --prune
    git -C $FrontendDir checkout $Branch
    git -C $FrontendDir pull --ff-only origin $Branch
  }
}

$buildArg = "--build"
if ($SkipBuild) {
  $buildArg = ""
}

Write-Host "Aplicando despliegue..."
if ([string]::IsNullOrWhiteSpace($buildArg)) {
  docker compose --env-file $EnvFile -f $ComposeFile up -d
}
else {
  docker compose --env-file $EnvFile -f $ComposeFile up -d --build
}

$webPort = "80"
Get-Content $EnvFile | ForEach-Object {
  if ($_ -match '^WEB_PORT=(.+)$') {
    $webPort = $matches[1].Trim()
  }
}

$healthUrl = "http://localhost:$webPort/health"
Write-Host "Verificando salud en $healthUrl ..."
if (-not (Wait-HttpOk -Url $healthUrl)) {
  throw "Actualizacion aplicada pero sin respuesta de healthcheck. Revisa logs: docker compose --env-file .env.prod -f docker-compose.prod.yml logs"
}

Write-Host "Actualizacion completada."
if ($webPort -eq "80") {
  Write-Host "Frontend: http://localhost"
  Write-Host "Docs API: http://localhost/docs"
}
else {
  Write-Host "Frontend: http://localhost:$webPort"
  Write-Host "Docs API: http://localhost:$webPort/docs"
}
