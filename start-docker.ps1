$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ComposeFile = Join-Path $RootDir "docker-compose.full.yml"

if (-not (Test-Path $ComposeFile)) {
  Write-Error "No se encontro docker-compose.full.yml en $RootDir"
}

try {
  docker compose version | Out-Null
  $ComposeArgs = @("compose", "-f", $ComposeFile, "up", "-d", "--build")
}
catch {
  Write-Error "Docker Compose no esta instalado."
}

Write-Host "Levantando OSIRIS (api + web + postgres + redis)..."
docker @ComposeArgs

Write-Host ""
Write-Host "Listo."
Write-Host "Frontend: http://localhost:5173"
Write-Host "API:      http://localhost:8000"
Write-Host "Docs API: http://localhost:8000/docs"
