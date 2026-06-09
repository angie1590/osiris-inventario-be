@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "COMPOSE_FILE=%ROOT_DIR%docker-compose.full.yml"

if not exist "%COMPOSE_FILE%" (
  echo No se encontro docker-compose.full.yml en %ROOT_DIR%
  exit /b 1
)

echo Deteniendo OSIRIS...
docker compose -f "%COMPOSE_FILE%" down
if errorlevel 1 exit /b 1

echo Listo.
exit /b 0
