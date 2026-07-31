param(
  [switch]$SkipDependencyInstall,
  [switch]$SkipGitSync
)

$ErrorActionPreference = "Stop"

$BackendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ComposeFile = Join-Path $BackendDir "docker-compose.prod.yml"
$EnvFile = Join-Path $BackendDir ".env.prod"
$BackupScript = Join-Path $BackendDir "backup-db.ps1"
$FrontendDir = Join-Path (Split-Path -Parent $BackendDir) "osiris-inventario-fe"

function Prompt-Value($Prompt, $Default = "") {
  if ([string]::IsNullOrWhiteSpace($Default)) {
    return (Read-Host $Prompt).Trim()
  }
  $value = (Read-Host "$Prompt [$Default]").Trim()
  if ([string]::IsNullOrWhiteSpace($value)) {
    return $Default
  }
  return $value
}

function Prompt-Required($Prompt) {
  while ($true) {
    $value = (Read-Host $Prompt).Trim()
    if (-not [string]::IsNullOrWhiteSpace($value)) {
      return $value
    }
    Write-Host "Este valor es obligatorio."
  }
}

function Prompt-Time($Prompt, $Default = "02:00") {
  while ($true) {
    $raw = Prompt-Value $Prompt $Default
    try {
      return [DateTime]::ParseExact($raw, "HH:mm", $null)
    }
    catch {
      Write-Host "Formato invalido. Usa HH:mm (24 horas)."
    }
  }
}

function New-RandomSecret([int]$Length = 48) {
  $chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
  $bytes = New-Object byte[] $Length
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  $out = New-Object System.Text.StringBuilder
  foreach ($b in $bytes) {
    [void]$out.Append($chars[$b % $chars.Length])
  }
  return $out.ToString()
}

function Assert-Command($Name, $InstallHint) {
  if (Get-Command $Name -ErrorAction SilentlyContinue) {
    return
  }
  throw "$Name no esta disponible. $InstallHint"
}

function Install-DockerDesktop-WithWinget {
  if (Get-Command docker -ErrorAction SilentlyContinue) {
    return
  }
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "No se encontro winget. Instala App Installer desde Microsoft Store o instala Docker Desktop manualmente."
  }

  Write-Host "Instalando Docker Desktop con winget..."
  winget install --id Docker.DockerDesktop -e --accept-package-agreements --accept-source-agreements
}

function Install-Git-WithWinget {
  if (Get-Command git -ErrorAction SilentlyContinue) {
    return
  }
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "No se encontro winget para instalar Git automaticamente."
  }
  Write-Host "Instalando Git con winget..."
  winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements
}

function Start-DockerDesktop {
  try {
    docker info | Out-Null
    return
  }
  catch {
  }

  $dockerDesktopExe = Join-Path $Env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
  if (Test-Path $dockerDesktopExe) {
    Write-Host "Iniciando Docker Desktop..."
    Start-Process -FilePath $dockerDesktopExe | Out-Null
  }

  Write-Host "Esperando motor Docker..."
  $maxAttempts = 120
  for ($i = 0; $i -lt $maxAttempts; $i++) {
    Start-Sleep -Seconds 2
    try {
      docker info | Out-Null
      return
    }
    catch {
    }
  }

  throw "Docker no respondio a tiempo. Verifica Docker Desktop y WSL2."
}

function Register-DailyBackupTask {
  param(
    [Parameter(Mandatory = $true)]
    [string]$TaskName,
    [Parameter(Mandatory = $true)]
    [string]$BackupDir,
    [Parameter(Mandatory = $true)]
    [DateTime]$RunAt,
    [int]$RetentionDays = 14
  )

  if (-not (Test-Path $BackupScript)) {
    throw "No se encontro script de backup en $BackupScript"
  }

  if (-not (Test-Path $BackupDir)) {
    throw "No existe la ruta de backup: $BackupDir"
  }

  $actionArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$BackupScript`" -BackupDir `"$BackupDir`" -RetentionDays $RetentionDays"
  $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $actionArgs
  $trigger = New-ScheduledTaskTrigger -Daily -At $RunAt
  $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null
}

if (-not (Test-Path $ComposeFile)) {
  throw "No se encontro docker-compose.prod.yml en $BackendDir"
}

if (-not (Test-Path $BackupScript)) {
  throw "No se encontro backup-db.ps1 en $BackendDir"
}

if (-not (Test-Path $FrontendDir)) {
  throw "No se encontro carpeta frontend esperada en $FrontendDir"
}

if (-not $SkipDependencyInstall) {
  Install-DockerDesktop-WithWinget
  Install-Git-WithWinget
}

Assert-Command docker "Instala Docker Desktop e intenta de nuevo."
Start-DockerDesktop

try {
  docker compose version | Out-Null
}
catch {
  throw "Docker Compose no esta disponible."
}

if (-not $SkipGitSync) {
  Assert-Command git "Instala Git e intenta de nuevo."

  $syncAnswer = Prompt-Value "Actualizar codigo desde git antes de instalar? (S/n)" "S"
  if ($syncAnswer -notmatch "^[nN]") {
    $branch = Prompt-Value "Branch a desplegar" "main"

    if (Test-Path (Join-Path $BackendDir ".git")) {
      Write-Host "Actualizando backend..."
      git -C $BackendDir fetch --all --prune
      git -C $BackendDir checkout $branch
      git -C $BackendDir pull --ff-only origin $branch
    }

    if (Test-Path (Join-Path $FrontendDir ".git")) {
      Write-Host "Actualizando frontend..."
      git -C $FrontendDir fetch --all --prune
      git -C $FrontendDir checkout $branch
      git -C $FrontendDir pull --ff-only origin $branch
    }
  }
}

$serverHost = Prompt-Value "Nombre del servidor para clientes LAN (ej. osiris.local)" "osiris.local"
$webPort = Prompt-Value "Puerto HTTP para frontend" "80"
$postgresUser = Prompt-Value "POSTGRES_USER" "osiris"
$postgresPassword = Prompt-Required "POSTGRES_PASSWORD"
$postgresDb = Prompt-Value "POSTGRES_DB" "osiris_inventario"
$secretDefault = New-RandomSecret
$secretKey = Prompt-Value "SECRET_KEY" $secretDefault
$accessMinutes = Prompt-Value "ACCESS_TOKEN_EXPIRE_MINUTES" "30"
$refreshDays = Prompt-Value "REFRESH_TOKEN_EXPIRE_DAYS" "7"
$kardexMethod = Prompt-Value "KARDEX_METHOD (PEPS o WEIGHTED_AVERAGE)" "PEPS"
$maxRangeDays = Prompt-Value "MAX_EXPORT_DATE_RANGE_DAYS" "90"
$timeZone = Prompt-Value "APP_TIMEZONE" "America/Guayaquil"
$corsOrigins = Prompt-Value "CORS_ORIGINS (JSON array)" "[\"http://$serverHost\",\"http://localhost\"]"

$envContent = @"
POSTGRES_USER=$postgresUser
POSTGRES_PASSWORD=$postgresPassword
POSTGRES_DB=$postgresDb
SECRET_KEY=$secretKey
ACCESS_TOKEN_EXPIRE_MINUTES=$accessMinutes
REFRESH_TOKEN_EXPIRE_DAYS=$refreshDays
KARDEX_METHOD=$kardexMethod
MAX_EXPORT_DATE_RANGE_DAYS=$maxRangeDays
APP_TIMEZONE=$timeZone
CORS_ORIGINS=$corsOrigins
WEB_PORT=$webPort
"@

[System.IO.File]::WriteAllText($EnvFile, $envContent, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "Se genero $EnvFile"

Write-Host "Levantando OSIRIS produccion (postgres + redis + api + web/nginx)..."
docker compose --env-file $EnvFile -f $ComposeFile up -d --build

Write-Host "Esperando servicio web en http://localhost:$webPort/health ..."
$ready = $false
for ($i = 0; $i -lt 90; $i++) {
  Start-Sleep -Seconds 2
  try {
    $resp = Invoke-WebRequest -Uri "http://localhost:$webPort/health" -UseBasicParsing -TimeoutSec 2
    if ($resp.StatusCode -eq 200) {
      $ready = $true
      break
    }
  }
  catch {
  }
}

if (-not $ready) {
  Write-Host "El servicio no quedo listo a tiempo. Revisa logs con:"
  Write-Host "docker compose --env-file .env.prod -f docker-compose.prod.yml logs"
  exit 1
}

Write-Host "Instalacion lista."
if ($webPort -eq "80") {
  Write-Host "Frontend: http://localhost"
  Write-Host "Docs API: http://localhost/docs"
  Start-Process "http://localhost"
}
else {
  Write-Host "Frontend: http://localhost:$webPort"
  Write-Host "Docs API: http://localhost:$webPort/docs"
  Start-Process "http://localhost:$webPort"
}

$enableBackup = Prompt-Value "Configurar respaldo diario automatico? (S/n)" "S"
if ($enableBackup -notmatch "^[nN]") {
  $backupDir = Prompt-Required "Ruta de respaldo (memoria flash), ej. E:\\osiris-backups"
  if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
  }

  $backupTime = Prompt-Time "Hora diaria del respaldo (HH:mm)" "02:00"
  $retentionRaw = Prompt-Value "Dias de retencion de backups" "14"
  $retentionDays = 14
  if ([int]::TryParse($retentionRaw, [ref]$retentionDays) -eq $false) {
    $retentionDays = 14
  }

  $taskName = "OsirisDailyDatabaseBackup"
  Register-DailyBackupTask -TaskName $taskName -BackupDir $backupDir -RunAt $backupTime -RetentionDays $retentionDays

  Write-Host "Tarea programada creada: $taskName"
  Write-Host "Respaldo diario: $($backupTime.ToString('HH:mm'))"
  Write-Host "Destino: $backupDir"
}
