@echo off
setlocal EnableExtensions
title Iniciar servidor OSIRIS
set "OSIRIS_STARTER=%~f0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$content = Get-Content -LiteralPath $env:OSIRIS_STARTER -Raw -Encoding ASCII; $parts = [regex]::Split($content, '(?m)^:POWERSHELL\r?$', 2); if ($parts.Count -ne 2) { throw 'Script invalido.' }; Invoke-Expression $parts[1]"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" echo No se pudo iniciar OSIRIS.
pause
exit /b %EXIT_CODE%

:POWERSHELL
$ErrorActionPreference = "Stop"

function Find-BackendDir {
  $candidates = @(
    $env:OSIRIS_BACKEND_DIR,
    (Split-Path -Parent $env:OSIRIS_STARTER),
    "C:\OsirisDeploy\osiris-inventario-be"
  )

  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path (Join-Path $candidate "docker-compose.prod.yml"))) {
      return $candidate
    }
  }
  throw "No se encontro OSIRIS. Se esperaba en C:\OsirisDeploy\osiris-inventario-be."
}

function Start-DockerDesktop {
  try {
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
      return
    }
  }
  catch {
  }

  $dockerDesktop = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
  if (-not (Test-Path $dockerDesktop)) {
    throw "Docker Desktop no esta instalado."
  }

  Write-Host "Iniciando Docker Desktop..."
  Start-Process $dockerDesktop | Out-Null
  foreach ($attempt in 1..120) {
    if ($attempt % 10 -eq 0) {
      Write-Host "Esperando Docker Desktop ($attempt/120)..."
    }
    Start-Sleep -Seconds 2
    try {
      docker info 2>$null | Out-Null
      if ($LASTEXITCODE -eq 0) {
        return
      }
    }
    catch {
    }
  }
  throw "Docker Desktop no respondio a tiempo."
}

function Get-EnvValue($Path, $Name, $Default) {
  foreach ($line in Get-Content $Path) {
    if ($line -match "^$([regex]::Escape($Name))=(.*)$") {
      return $matches[1].Trim()
    }
  }
  return $Default
}

function Wait-Osiris($Url) {
  foreach ($attempt in 1..90) {
    try {
      $response = Invoke-WebRequest -Uri "$Url/health" -UseBasicParsing -TimeoutSec 3
      if ($response.StatusCode -eq 200) {
        return $true
      }
    }
    catch {
    }
    Start-Sleep -Seconds 2
  }
  return $false
}

try {
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker no esta disponible."
  }

  $backendDir = Find-BackendDir
  $composeFile = Join-Path $backendDir "docker-compose.prod.yml"
  $envFile = Join-Path $backendDir ".env.prod"
  if (-not (Test-Path $envFile)) {
    throw "Falta $envFile. Ejecuta primero el instalador de OSIRIS."
  }

  Start-DockerDesktop
  docker compose version 2>$null | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose v2 no esta disponible."
  }

  Write-Host "Iniciando servicios OSIRIS..."
  docker compose --project-directory $backendDir --env-file $envFile -f $composeFile up -d
  if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose no pudo iniciar los servicios."
  }

  $webPort = Get-EnvValue $envFile "WEB_PORT" "80"
  $localUrl = if ($webPort -eq "80") { "http://localhost" } else { "http://localhost:$webPort" }
  Write-Host "Esperando OSIRIS..."
  if (-not (Wait-Osiris $localUrl)) {
    docker compose --project-directory $backendDir --env-file $envFile -f $composeFile ps
    docker compose --project-directory $backendDir --env-file $envFile -f $composeFile logs --no-color --tail 100 api
    throw "OSIRIS no respondio al healthcheck."
  }

  $lanIp = Get-NetIPConfiguration |
    Where-Object {
      $_.NetAdapter.Status -eq "Up" -and
      $null -ne $_.IPv4DefaultGateway -and
      $null -ne $_.IPv4Address
    } |
    ForEach-Object { $_.IPv4Address.IPAddress } |
    Select-Object -First 1
  $clientUrl = if ($lanIp) {
    if ($webPort -eq "80") { "http://$lanIp" } else { "http://${lanIp}:$webPort" }
  } else {
    $localUrl
  }

  Write-Host "OSIRIS iniciado correctamente." -ForegroundColor Green
  Write-Host "Servidor: $clientUrl" -ForegroundColor Green
  try {
    Start-Process $localUrl
  }
  catch {
    Write-Host "Abre manualmente: $localUrl" -ForegroundColor Yellow
  }
  exit 0
}
catch {
  Write-Host $_.Exception.Message -ForegroundColor Red
  exit 1
}