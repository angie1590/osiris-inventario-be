param(
  [string]$BackupPath = ""
)

$ErrorActionPreference = "Stop"

$BackendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ComposeFile = Join-Path $BackendDir "docker-compose.prod.yml"
$EnvFile = Join-Path $BackendDir ".env.prod"
$BackupDirectory = Join-Path $BackendDir "backups"
$Timestamp = Get-Date -Format "yyyyMMddHHmmss"
$TemporaryDb = "osiris_company_restore_$Timestamp"
$RemoteBackup = "/tmp/osiris-company-source.sql"
$RemoteCompany = "/tmp/osiris-company-config.sql"
$PostgresContainerId = ""

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

if (-not (Test-Path $ComposeFile) -or -not (Test-Path $EnvFile)) {
  throw "Faltan docker-compose.prod.yml o .env.prod en $BackendDir"
}

if ([string]::IsNullOrWhiteSpace($BackupPath)) {
  $Backup = Get-ChildItem $BackupDirectory -Filter "osiris-db-*.sql" -File |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if (-not $Backup) {
    throw "No se encontro un respaldo en $BackupDirectory"
  }
  $BackupPath = $Backup.FullName
}
elseif (-not [System.IO.Path]::IsPathRooted($BackupPath)) {
  $BackupPath = Join-Path $BackendDir $BackupPath
}

if (-not (Test-Path $BackupPath)) {
  throw "No se encontro el respaldo: $BackupPath"
}

$EnvValues = Read-EnvFile $EnvFile
$PostgresUser = $EnvValues["POSTGRES_USER"]
$PostgresDb = $EnvValues["POSTGRES_DB"]
if ([string]::IsNullOrWhiteSpace($PostgresUser)) { $PostgresUser = "osiris" }
if ([string]::IsNullOrWhiteSpace($PostgresDb)) { $PostgresDb = "osiris_inventario" }

Push-Location $BackendDir
try {
  docker compose --env-file $EnvFile -f $ComposeFile up -d postgres
  Assert-LastExitCode "No se pudo iniciar PostgreSQL."

  $PostgresContainerId = (docker compose --env-file $EnvFile -f $ComposeFile ps -q postgres).Trim()
  if ([string]::IsNullOrWhiteSpace($PostgresContainerId)) {
    throw "No se encontro el contenedor PostgreSQL."
  }

  Write-Host "Respaldo seleccionado: $BackupPath"
  docker cp $BackupPath "${PostgresContainerId}:$RemoteBackup"
  Assert-LastExitCode "No se pudo copiar el respaldo."

  docker compose --env-file $EnvFile -f $ComposeFile exec -T postgres `
    dropdb --if-exists --force -U $PostgresUser $TemporaryDb
  Assert-LastExitCode "No se pudo preparar la base temporal."
  docker compose --env-file $EnvFile -f $ComposeFile exec -T postgres `
    createdb -U $PostgresUser $TemporaryDb
  Assert-LastExitCode "No se pudo crear la base temporal."

  Write-Host "Leyendo configuracion de empresa desde el respaldo..."
  docker compose --env-file $EnvFile -f $ComposeFile exec -T postgres `
    psql -v ON_ERROR_STOP=1 -U $PostgresUser -d $TemporaryDb -f $RemoteBackup
  Assert-LastExitCode "No se pudo restaurar el respaldo en la base temporal."

  docker compose --env-file $EnvFile -f $ComposeFile exec -T postgres `
    pg_dump -U $PostgresUser -d $TemporaryDb --data-only `
    --table=public.company_config --column-inserts --no-owner --no-privileges `
    --file=$RemoteCompany
  Assert-LastExitCode "No se pudo extraer company_config."

  Write-Host "Restaurando exclusivamente la configuracion de empresa..."
  docker compose --env-file $EnvFile -f $ComposeFile exec -T postgres `
    psql -v ON_ERROR_STOP=1 --single-transaction -U $PostgresUser -d $PostgresDb `
    -c "TRUNCATE TABLE company_config RESTART IDENTITY" -f $RemoteCompany
  Assert-LastExitCode "No se pudo restaurar company_config."

  docker compose --env-file $EnvFile -f $ComposeFile exec -T postgres `
    psql -U $PostgresUser -d $PostgresDb -c `
    "SELECT id, razon_social, ruc, email FROM company_config"
  Assert-LastExitCode "No se pudo verificar company_config."
  Write-Host "Configuracion de empresa restaurada. Inventario y usuarios no fueron modificados."
}
finally {
  if (-not [string]::IsNullOrWhiteSpace($PostgresContainerId)) {
    docker compose --env-file $EnvFile -f $ComposeFile exec -T postgres `
      dropdb --if-exists --force -U $PostgresUser $TemporaryDb 2>$null | Out-Null
    docker compose --env-file $EnvFile -f $ComposeFile exec -T postgres `
      rm -f $RemoteBackup $RemoteCompany 2>$null | Out-Null
  }
  Pop-Location
}