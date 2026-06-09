$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ComposeFile = Join-Path $RootDir "docker-compose.full.yml"

if (-not (Test-Path $ComposeFile)) {
  Write-Error "No se encontro docker-compose.full.yml en $RootDir"
}

try {
  docker compose version | Out-Null
}
catch {
  Write-Error "Docker Compose no esta instalado."
}

Write-Host "Deteniendo OSIRIS..."
docker compose -f $ComposeFile down
Write-Host "Listo."
