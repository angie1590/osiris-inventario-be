@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%restore-company-config-windows.ps1"

if not exist "%PS_SCRIPT%" (
  echo No se encontro restore-company-config-windows.ps1 en %SCRIPT_DIR%
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %*
exit /b %ERRORLEVEL%