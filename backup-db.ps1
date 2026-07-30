$ErrorActionPreference = "Stop"

param(
  [Parameter(Mandatory = $true)]
  [string]$BackupDir,
  [int]$RetentionDays = 14
)

$BackendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ComposeFile = Join-Path $BackendDir "docker-compose.prod.yml"
$EnvFile = Join-Path $BackendDir ".env.prod"

if (-not (Test-Path $ComposeFile)) {
  throw "No se encontro docker-compose.prod.yml en $BackendDir"
}

if (-not (Test-Path $EnvFile)) {
  throw "No se encontro .env.prod en $BackendDir"
}

if (-not (Test-Path $BackupDir)) {
  throw "No existe la ruta de respaldo: $BackupDir"
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker no esta disponible."
}

$envMap = @{}
Get-Content $EnvFile | ForEach-Object {
  $line = $_.Trim()
  if (-not $line -or $line.StartsWith("#")) {
    return
  }
  $parts = $line.Split("=", 2)
  if ($parts.Count -eq 2) {
    $envMap[$parts[0]] = $parts[1]
  }
}

$postgresUser = $envMap["POSTGRES_USER"]
$postgresDb = $envMap["POSTGRES_DB"]

if ([string]::IsNullOrWhiteSpace($postgresUser)) {
  $postgresUser = "osiris"
}
if ([string]::IsNullOrWhiteSpace($postgresDb)) {
  $postgresDb = "osiris_inventario"
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupFile = Join-Path $BackupDir "osiris-db-$timestamp.sql"

Push-Location $BackendDir
try {
  docker compose --env-file $EnvFile -f $ComposeFile exec -T postgres pg_dump -U $postgresUser $postgresDb | Set-Content -Path $backupFile -Encoding UTF8
  if ($LASTEXITCODE -ne 0) {
    throw "pg_dump devolvio codigo $LASTEXITCODE"
  }
}
finally {
  Pop-Location
}

if ($RetentionDays -gt 0) {
  $limitDate = (Get-Date).AddDays(-$RetentionDays)
  Get-ChildItem -Path $BackupDir -Filter "osiris-db-*.sql" -File |
    Where-Object { $_.LastWriteTime -lt $limitDate } |
    Remove-Item -Force -ErrorAction SilentlyContinue
}

Write-Host "Backup generado: $backupFile"