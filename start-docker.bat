@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "COMPOSE_FILE=%ROOT_DIR%docker-compose.full.yml"

if not exist "%COMPOSE_FILE%" (
  echo No se encontro docker-compose.full.yml en %ROOT_DIR%
  exit /b 1
)

echo Levantando OSIRIS (api + web + postgres + redis)...
docker compose -f "%COMPOSE_FILE%" up -d --build
if errorlevel 1 exit /b 1

echo.
echo Listo.
echo Frontend: http://localhost:5173
echo API:      http://localhost:8000
echo Docs API: http://localhost:8000/docs

exit /b 0
