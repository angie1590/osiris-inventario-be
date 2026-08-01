param(
  [string]$DumpPath = "Dump20260730.sql",
  [string]$Actor = "admin",
  [string]$ReportDir = "migration-reports",
  [switch]$DryRunOnly,
  [switch]$SkipBuild,
  [switch]$Yes
)

$ErrorActionPreference = "Stop"

$BackendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ComposeFile = Join-Path $BackendDir "docker-compose.prod.yml"
$EnvFile = Join-Path $BackendDir ".env.prod"
$MigrationScript = Join-Path $BackendDir "scripts\migrate_legacy_dump.py"
$BackupScript = Join-Path $BackendDir "backup-db.ps1"

function Resolve-LocalPath($Path, $BaseDir) {
  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $BaseDir $Path))
}

function Assert-Path($Path, $Message) {
  if (-not (Test-Path $Path)) {
    throw $Message
  }
}

function Assert-LastExitCode($Message) {
  if ($LASTEXITCODE -ne 0) {
    throw "$Message Codigo: $LASTEXITCODE"
  }
}

$DumpFile = Resolve-LocalPath $DumpPath $BackendDir
$ReportDirectory = Resolve-LocalPath $ReportDir $BackendDir
$BackupDirectory = Join-Path $BackendDir "backups"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$DryRunReport = Join-Path $ReportDirectory "migration-dry-run-$Timestamp.json"
$FinalReport = Join-Path $ReportDirectory "migration-applied-$Timestamp.json"
$RemoteDump = "/tmp/osiris-legacy-dump.sql"
$RemoteReport = "/tmp/osiris-migration-report.json"
$ContainerId = ""

Assert-Path $ComposeFile "No se encontro docker-compose.prod.yml en $BackendDir"
Assert-Path $EnvFile "No se encontro .env.prod. Ejecuta install-windows.ps1 primero."
Assert-Path $MigrationScript "No se encontro scripts\migrate_legacy_dump.py. Actualiza el backend."
Assert-Path $BackupScript "No se encontro backup-db.ps1."
Assert-Path $DumpFile "No se encontro el dump: $DumpFile"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker no esta disponible."
}

docker info | Out-Null
Assert-LastExitCode "Docker Desktop no esta iniciado."
docker compose version | Out-Null
Assert-LastExitCode "Docker Compose no esta disponible."

New-Item -ItemType Directory -Path $ReportDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $BackupDirectory -Force | Out-Null

Push-Location $BackendDir
try {
  if ($SkipBuild) {
    Write-Host "Iniciando API de produccion..."
    docker compose --env-file $EnvFile -f $ComposeFile up -d api
  }
  else {
    Write-Host "Reconstruyendo e iniciando API de produccion..."
    docker compose --env-file $EnvFile -f $ComposeFile up -d --build api
  }
  Assert-LastExitCode "No se pudo iniciar la API."

  $ContainerId = (docker compose --env-file $EnvFile -f $ComposeFile ps -q api).Trim()
  Assert-LastExitCode "No se pudo consultar el contenedor API."
  if ([string]::IsNullOrWhiteSpace($ContainerId)) {
    throw "No se encontro el contenedor API en ejecucion."
  }

  Write-Host "Copiando dump al contenedor..."
  docker cp $DumpFile "${ContainerId}:$RemoteDump"
  Assert-LastExitCode "No se pudo copiar el dump al contenedor."

  Write-Host ""
  Write-Host "Ejecutando validacion sin modificar la base..."
  docker compose --env-file $EnvFile -f $ComposeFile exec -T api `
    python -m scripts.migrate_legacy_dump $RemoteDump `
    --actor $Actor --report $RemoteReport
  Assert-LastExitCode "El dry-run de migracion fallo."

  docker cp "${ContainerId}:$RemoteReport" $DryRunReport
  Assert-LastExitCode "No se pudo copiar el reporte del dry-run."
  Write-Host "Reporte dry-run: $DryRunReport"

  if ($DryRunOnly) {
    Write-Host "Dry-run completado. No se modifico la base de datos."
    exit 0
  }

  if (-not $Yes) {
    Write-Host ""
    Write-Host "La migracion exige una base sin categorias, productos, proveedores ni documentos de inventario."
    $Confirmation = Read-Host "Escribe MIGRAR para generar respaldo y aplicar la migracion"
    if ($Confirmation -ne "MIGRAR") {
      Write-Host "Operacion cancelada."
      exit 0
    }
  }

  Write-Host "Generando respaldo previo..."
  & $BackupScript -BackupDir $BackupDirectory

  Write-Host ""
  Write-Host "Aplicando migracion..."
  docker compose --env-file $EnvFile -f $ComposeFile exec -T api `
    python -m scripts.migrate_legacy_dump $RemoteDump `
    --actor $Actor --report $RemoteReport --apply
  Assert-LastExitCode "La migracion fallo. La transaccion fue revertida."

  docker cp "${ContainerId}:$RemoteReport" $FinalReport
  Assert-LastExitCode "La migracion termino, pero no se pudo copiar el reporte final."

  Write-Host ""
  Write-Host "Migracion completada."
  Write-Host "Reporte: $FinalReport"
  Write-Host "Respaldos: $BackupDirectory"
}
finally {
  if (-not [string]::IsNullOrWhiteSpace($ContainerId)) {
    docker compose --env-file $EnvFile -f $ComposeFile exec -T api `
      rm -f $RemoteDump $RemoteReport 2>$null | Out-Null
  }
  Pop-Location
}