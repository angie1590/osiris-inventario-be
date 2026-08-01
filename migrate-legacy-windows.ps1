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

function Read-EnvFile($Path) {
  $Values = @{}
  Get-Content $Path | ForEach-Object {
    $Line = $_.Trim()
    if (-not $Line -or $Line.StartsWith("#")) {
      return
    }
    $Parts = $Line.Split("=", 2)
    if ($Parts.Count -eq 2) {
      $Values[$Parts[0]] = $Parts[1]
    }
  }
  return $Values
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

if ($Actor -ne "admin") {
  throw "Al recrear la base solo existe el usuario inicial 'admin'. No uses -Actor con otro valor."
}

$EnvValues = Read-EnvFile $EnvFile
$PostgresUser = $EnvValues["POSTGRES_USER"]
$PostgresDb = $EnvValues["POSTGRES_DB"]

if ([string]::IsNullOrWhiteSpace($PostgresUser)) {
  $PostgresUser = "osiris"
}
if ([string]::IsNullOrWhiteSpace($PostgresDb)) {
  $PostgresDb = "osiris_inventario"
}

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
    Write-Host "La base PostgreSQL '$PostgresDb' sera eliminada y creada nuevamente."
    Write-Host "Se perderan todos sus datos actuales. Se generara un respaldo antes de borrarla."
    $Confirmation = Read-Host "Escribe MIGRAR para respaldar, recrear la base y cargar el dump"
    if ($Confirmation -ne "MIGRAR") {
      Write-Host "Operacion cancelada."
      exit 0
    }
  }

  Write-Host "Generando respaldo previo..."
  & $BackupScript -BackupDir $BackupDirectory

  Write-Host ""
  Write-Host "Deteniendo API..."
  docker compose --env-file $EnvFile -f $ComposeFile stop api
  Assert-LastExitCode "No se pudo detener la API."

  Write-Host "Eliminando base PostgreSQL '$PostgresDb'..."
  docker compose --env-file $EnvFile -f $ComposeFile exec -T postgres `
    dropdb --if-exists --force -U $PostgresUser $PostgresDb
  Assert-LastExitCode "No se pudo eliminar la base PostgreSQL."

  Write-Host "Creando base PostgreSQL '$PostgresDb'..."
  docker compose --env-file $EnvFile -f $ComposeFile exec -T postgres `
    createdb -U $PostgresUser $PostgresDb
  Assert-LastExitCode "No se pudo crear la base PostgreSQL."

  Write-Host "Recreando esquema y datos iniciales..."
  docker compose --env-file $EnvFile -f $ComposeFile up -d --wait --wait-timeout 120 api
  Assert-LastExitCode "No se pudo recrear el esquema de la base."

  $ContainerId = (docker compose --env-file $EnvFile -f $ComposeFile ps -q api).Trim()
  Assert-LastExitCode "No se pudo consultar el nuevo contenedor API."

  Write-Host "Copiando nuevamente el dump al contenedor recreado..."
  docker cp $DumpFile "${ContainerId}:$RemoteDump"
  Assert-LastExitCode "No se pudo copiar el dump al contenedor recreado."

  Write-Host "Aplicando migracion completa con ZAPATO aplanada..."
  docker compose --env-file $EnvFile -f $ComposeFile exec -T api `
    python -m scripts.migrate_legacy_dump $RemoteDump `
    --actor $Actor --report $RemoteReport --apply
  Assert-LastExitCode "La migracion fallo. La base recreada quedo sin los datos del dump; usa el respaldo para restaurar si es necesario."

  Write-Host "Restableciendo y verificando acceso del usuario admin..."
  docker compose --env-file $EnvFile -f $ComposeFile exec -T api `
    python -m scripts.reset_admin_password --password "Admin@12345!"
  Assert-LastExitCode "La migracion termino, pero no se pudo restablecer la clave del usuario admin."

  docker cp "${ContainerId}:$RemoteReport" $FinalReport
  Assert-LastExitCode "La migracion termino, pero no se pudo copiar el reporte final."

  Write-Host ""
  Write-Host "Migracion completada."
  Write-Host "Usuario temporal: admin"
  Write-Host "Clave temporal: Admin@12345!"
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