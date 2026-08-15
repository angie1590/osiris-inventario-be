@echo off
setlocal EnableExtensions
title Encontrar servidor OSIRIS
set "OSIRIS_FINDER=%~f0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$content = Get-Content -LiteralPath $env:OSIRIS_FINDER -Raw -Encoding ASCII; $parts = [regex]::Split($content, '(?m)^:POWERSHELL\r?$', 2); if ($parts.Count -ne 2) { throw 'Script invalido.' }; Invoke-Expression $parts[1]"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" echo No se encontro OSIRIS. Verifica que cliente y servidor esten en la misma red.
pause
exit /b %EXIT_CODE%

:POWERSHELL
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http

function Test-OsirisIdentity($BaseUrl, $Client) {
  $response = $null
  try {
    $response = $Client.GetAsync("$BaseUrl/openapi.json").GetAwaiter().GetResult()
    if (-not $response.IsSuccessStatusCode) {
      return $false
    }
    $openApi = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult() | ConvertFrom-Json
    return $openApi.info.title -eq "Osiris Inventario API"
  }
  catch {
    return $false
  }
  finally {
    if ($null -ne $response) {
      $response.Dispose()
    }
  }
}

function Test-Osiris($BaseUrl, $Client) {
  $response = $null
  try {
    $baseUrl = $BaseUrl.TrimEnd("/")
    $response = $Client.GetAsync("$baseUrl/health").GetAwaiter().GetResult()
    if (-not $response.IsSuccessStatusCode) {
      return $false
    }
    $health = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult() | ConvertFrom-Json
    return $health.status -eq "ok" -and (Test-OsirisIdentity $baseUrl $Client)
  }
  catch {
    return $false
  }
  finally {
    if ($null -ne $response) {
      $response.Dispose()
    }
  }
}

function Find-Osiris($Prefix, $Client) {
  Write-Host "Buscando OSIRIS en $Prefix.0/24..."
  $requests = foreach ($hostNumber in 1..254) {
    $baseUrl = "http://$Prefix.$hostNumber"
    [pscustomobject]@{
      BaseUrl = $baseUrl
      Task = $Client.GetAsync("$baseUrl/health")
      Checked = $false
    }
  }

  $deadline = (Get-Date).AddSeconds(6)
  while ((Get-Date) -lt $deadline) {
    $pending = $false
    foreach ($request in $requests) {
      if ($request.Checked) {
        continue
      }
      if (-not $request.Task.IsCompleted) {
        $pending = $true
        continue
      }

      $request.Checked = $true
      if ($request.Task.Status -ne [System.Threading.Tasks.TaskStatus]::RanToCompletion) {
        continue
      }

      $response = $request.Task.Result
      try {
        if (-not $response.IsSuccessStatusCode) {
          continue
        }
        $health = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult() | ConvertFrom-Json
        if ($health.status -eq "ok" -and (Test-OsirisIdentity $request.BaseUrl $Client)) {
          return $request.BaseUrl
        }
      }
      catch {
      }
      finally {
        $response.Dispose()
      }
    }

    if (-not $pending) {
      break
    }
    Start-Sleep -Milliseconds 100
  }
  return $null
}

$handler = New-Object System.Net.Http.HttpClientHandler
$handler.UseProxy = $false
$client = New-Object System.Net.Http.HttpClient($handler)
$client.Timeout = [TimeSpan]::FromSeconds(5)
$cacheDir = Join-Path $env:LOCALAPPDATA "Osiris"
$cacheFile = Join-Path $cacheDir "server-url.txt"

try {
  $candidates = @()
  if (Test-Path $cacheFile) {
    $cachedUrl = (Get-Content $cacheFile -Raw).Trim()
    if ($cachedUrl) {
      $candidates = @($cachedUrl)
    }
  }

  $serverUrl = $null
  foreach ($candidate in ($candidates | Select-Object -Unique)) {
    Write-Host "Probando $candidate..."
    if (Test-Osiris $candidate $client) {
      $serverUrl = $candidate.TrimEnd("/")
      break
    }
  }

  if (-not $serverUrl) {
    $prefixes = Get-NetIPConfiguration |
      Where-Object { $null -ne $_.IPv4DefaultGateway -and $null -ne $_.IPv4Address } |
      ForEach-Object { ($_.IPv4Address.IPAddress.Split(".")[0..2] -join ".") } |
      Sort-Object -Unique

    foreach ($prefix in $prefixes) {
      $serverUrl = Find-Osiris $prefix $client
      if ($serverUrl) {
        break
      }
    }
  }

  if (-not $serverUrl) {
    exit 1
  }

  New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null
  Set-Content -Path $cacheFile -Value $serverUrl -Encoding ASCII
  Write-Host "OSIRIS encontrado: $serverUrl" -ForegroundColor Green
  Start-Process $serverUrl
  exit 0
}
finally {
  $client.Dispose()
  $handler.Dispose()
}