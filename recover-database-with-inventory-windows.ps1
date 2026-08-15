param(
  [Parameter(Mandatory = $true)]
  [string]$BackupPath,
  [string]$DumpPath = "Dump20260815.sql",
  [string]$Actor = "admin",
  [switch]$SkipBuild,
  [switch]$Yes
)

$ErrorActionPreference = "Stop"

$BackendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ComposeFile = Join-Path $BackendDir "docker-compose.prod.yml"
$EnvFile = Join-Path $BackendDir ".env.prod"
$BackupScript = Join-Path $BackendDir "backup-db.ps1"
$BackupDirectory = Join-Path $BackendDir "backups"
$ReportDirectory = Join-Path $BackendDir "migration-reports"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$RemoteBackup = "/tmp/osiris-pre-migration.sql"
$RemoteDump = "/tmp/osiris-legacy-dump.sql"
$RemoteReport = "/tmp/osiris-recovery-report.json"
$FinalReport = Join-Path $ReportDirectory "recovery-with-inventory-$Timestamp.json"
$ApiContainerId = ""
$PostgresContainerId = ""

function Resolve-LocalPath($Path, $BaseDir) {
  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $BaseDir $Path))
}

function Assert-LastExitCode($Message) {
  if ($LASTEXITCODE -ne 0) {
    throw "$Message Codigo: $LASTEXITCODE"
  }
}

function Read-EnvFile($Path) {
  $Values = @{}
  Get-Content $Path | ForEach-Object {
    $Line = $_.Trim()
    if (-not $Line -or $Line.StartsWith("#")) { return }
    $Parts = $Line.Split("=", 2)
    if ($Parts.Count -eq 2) { $Values[$Parts[0]] = $Parts[1] }
  }
  return $Values
}

$BackupFile = Resolve-LocalPath $BackupPath $BackendDir
$DumpFile = Resolve-LocalPath $DumpPath $BackendDir
foreach ($Path in @($ComposeFile, $EnvFile, $BackupScript, $BackupFile, $DumpFile)) {
  if (-not (Test-Path $Path)) { throw "No se encontro: $Path" }
}

$EnvValues = Read-EnvFile $EnvFile
$PostgresUser = $EnvValues["POSTGRES_USER"]
$PostgresDb = $EnvValues["POSTGRES_DB"]
if ([string]::IsNullOrWhiteSpace($PostgresUser)) { $PostgresUser = "osiris" }
if ([string]::IsNullOrWhiteSpace($PostgresDb)) { $PostgresDb = "osiris_inventario" }

New-Item -ItemType Directory -Path $BackupDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $ReportDirectory -Force | Out-Null

Push-Location $BackendDir
try {
  if ($SkipBuild) {
    docker compose --env-file $EnvFile -f $ComposeFile up -d --wait --wait-timeout 120 api
  }
  else {
    docker compose --env-file $EnvFile -f $ComposeFile up -d --build --wait --wait-timeout 120 api
  }
  Assert-LastExitCode "No se pudo iniciar la API."

  $ApiContainerId = (docker compose --env-file $EnvFile -f $ComposeFile ps -q api).Trim()
  $PostgresContainerId = (docker compose --env-file $EnvFile -f $ComposeFile ps -q postgres).Trim()
  if ([string]::IsNullOrWhiteSpace($ApiContainerId) -or [string]::IsNullOrWhiteSpace($PostgresContainerId)) {
    throw "No se encontraron los contenedores API/PostgreSQL."
  }

  Write-Host "Validando dump sin modificar datos..."
  docker cp $DumpFile "${ApiContainerId}:$RemoteDump"
  Assert-LastExitCode "No se pudo copiar el dump."
  docker compose --env-file $EnvFile -f $ComposeFile exec -T api `
    python -m scripts.migrate_legacy_dump $RemoteDump --actor $Actor --report $RemoteReport
  Assert-LastExitCode "El dump no paso la validacion. No se modifico la base."

  if (-not $Yes) {
    Write-Host ""
    Write-Host "Se restaurara completamente: $BackupFile"
    Write-Host "Luego se reemplazara solo catalogo e inventario usando: $DumpFile"
    $Confirmation = Read-Host "Escribe RECUPERAR para continuar"
    if ($Confirmation -ne "RECUPERAR") {
      Write-Host "Operacion cancelada."
      exit 0
    }
  }

  Write-Host "Generando respaldo de seguridad del estado actual..."
  & $BackupScript -BackupDir $BackupDirectory

  Write-Host "Deteniendo API..."
  docker compose --env-file $EnvFile -f $ComposeFile stop api
  Assert-LastExitCode "No se pudo detener la API."

  docker cp $BackupFile "${PostgresContainerId}:$RemoteBackup"
  Assert-LastExitCode "No se pudo copiar el respaldo pre-migracion."

  Write-Host "Restaurando la base completa anterior..."
  docker compose --env-file $EnvFile -f $ComposeFile exec -T postgres `
    dropdb --if-exists --force -U $PostgresUser $PostgresDb
  Assert-LastExitCode "No se pudo eliminar la base actual."
  docker compose --env-file $EnvFile -f $ComposeFile exec -T postgres `
    createdb -U $PostgresUser $PostgresDb
  Assert-LastExitCode "No se pudo recrear la base."
  docker compose --env-file $EnvFile -f $ComposeFile exec -T postgres `
    psql -v ON_ERROR_STOP=1 -U $PostgresUser -d $PostgresDb -f $RemoteBackup
  Assert-LastExitCode "No se pudo restaurar el respaldo pre-migracion."

  Write-Host "Actualizando esquema y levantando API..."
  docker compose --env-file $EnvFile -f $ComposeFile up -d --wait --wait-timeout 120 api
  Assert-LastExitCode "La base fue restaurada, pero la API no inicio."
  $ApiContainerId = (docker compose --env-file $EnvFile -f $ComposeFile ps -q api).Trim()

  Write-Host "Agregando el inventario del dump sobre la base restaurada..."
  docker cp $DumpFile "${ApiContainerId}:$RemoteDump"
  Assert-LastExitCode "No se pudo copiar el dump al contenedor reiniciado."
  docker compose --env-file $EnvFile -f $ComposeFile exec -T api `
    python -m scripts.migrate_legacy_dump $RemoteDump --actor $Actor `
    --report $RemoteReport --apply
  Assert-LastExitCode "La base anterior fue restaurada, pero no se pudo agregar el inventario."

  docker cp "${ApiContainerId}:$RemoteReport" $FinalReport
  Assert-LastExitCode "La recuperacion termino, pero no se pudo copiar el reporte."
  Write-Host "Recuperacion completada."
  Write-Host "Base anterior restaurada; catalogo e inventario cargados desde el dump."
  Write-Host "Reporte: $FinalReport"
}
finally {
  if (-not [string]::IsNullOrWhiteSpace($ApiContainerId)) {
    docker compose --env-file $EnvFile -f $ComposeFile exec -T api `
      rm -f $RemoteDump $RemoteReport 2>$null | Out-Null
  }
  if (-not [string]::IsNullOrWhiteSpace($PostgresContainerId)) {
    docker compose --env-file $EnvFile -f $ComposeFile exec -T postgres `
      rm -f $RemoteBackup 2>$null | Out-Null
  }
  Pop-Location
}