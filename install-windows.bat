@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%install-windows.ps1"

if not exist "%PS_SCRIPT%" (
  echo No se encontro install-windows.ps1 en %SCRIPT_DIR%
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo Instalacion finalizo con error (%EXIT_CODE%).
  exit /b %EXIT_CODE%
)

echo Instalacion completada.
exit /b 0
