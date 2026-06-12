@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "COMPOSE_FILE=%ROOT_DIR%docker-compose.full.yml"

if not exist "%COMPOSE_FILE%" (
  echo No se encontro docker-compose.full.yml en %ROOT_DIR%
  exit /b 1
)

docker --version >nul 2>&1
if errorlevel 1 (
  echo Docker no esta instalado o no esta en el PATH.
  exit /b 1
)

docker compose version >nul 2>&1
if errorlevel 1 (
  echo Docker Compose no esta disponible.
  exit /b 1
)

echo Reinicio limpio de OSIRIS: eliminando contenedores y volumenes del proyecto...
docker compose -f "%COMPOSE_FILE%" down --remove-orphans --volumes
if errorlevel 1 exit /b 1

echo Levantando OSIRIS (api + web + postgres + redis)...
docker compose -f "%COMPOSE_FILE%" up -d --build
if errorlevel 1 exit /b 1

echo.
echo Esperando a que la API este lista...
set /a ATTEMPTS=0
:WAIT_API
set /a ATTEMPTS+=1
docker compose -f "%COMPOSE_FILE%" exec -T api python -c "import sys; sys.exit(0)" >nul 2>&1
if not errorlevel 1 goto API_READY
if %ATTEMPTS% geq 30 (
  echo La API no respondio a tiempo. Revisa: docker compose -f "%COMPOSE_FILE%" logs api
  exit /b 1
)
timeout /t 2 /nobreak >nul
goto WAIT_API

:API_READY
echo.
echo Ejecutando migraciones...
docker compose -f "%COMPOSE_FILE%" exec -T api alembic upgrade head
if errorlevel 1 exit /b 1

echo.
echo Creando datos iniciales (admin + parametros)...
docker compose -f "%COMPOSE_FILE%" exec -T api python -m scripts.seed
if errorlevel 1 exit /b 1

echo.
echo Asegurando credenciales del admin (reset + verificacion)...
docker compose -f "%COMPOSE_FILE%" exec -T api python -m scripts.reset_admin_password
if errorlevel 1 (
  echo Fallo el reset/verificacion de la contrasena del admin.
  exit /b 1
)

echo.
echo Listo.
echo Frontend: http://localhost:5173
echo API:      http://localhost:8000
echo Docs API: http://localhost:8000/docs
echo Usuario admin: admin
echo Clave inicial: Admin@12345!

exit /b 0
