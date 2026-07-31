@echo off
setlocal EnableExtensions

echo ==============================================
echo   OSIRIS Bootstrap Installer (1 archivo BAT)
echo ==============================================
echo.

set "DEFAULT_WORKDIR=C:\OsirisDeploy"
set /p "WORKDIR=Directorio de trabajo [%DEFAULT_WORKDIR%]: "
if "%WORKDIR%"=="" set "WORKDIR=%DEFAULT_WORKDIR%"

set "DEFAULT_BACKEND_REPO=https://github.com/angie1590/osiris-inventario-be.git"

set /p "BACKEND_REPO=URL repo backend [%DEFAULT_BACKEND_REPO%]: "
if "%BACKEND_REPO%"=="" set "BACKEND_REPO=%DEFAULT_BACKEND_REPO%"

set "DEFAULT_FRONTEND_REPO=%BACKEND_REPO:osiris-inventario-be=osiris-inventario-fe%"

set /p "FRONTEND_REPO=URL repo frontend [%DEFAULT_FRONTEND_REPO%]: "
if "%FRONTEND_REPO%"=="" set "FRONTEND_REPO=%DEFAULT_FRONTEND_REPO%"

set "DEFAULT_BRANCH=main"
set /p "BRANCH=Branch a desplegar [%DEFAULT_BRANCH%]: "
if "%BRANCH%"=="" set "BRANCH=%DEFAULT_BRANCH%"

echo.
echo [1/6] Verificando carpetas...
if not exist "%WORKDIR%" mkdir "%WORKDIR%"
if errorlevel 1 (
  echo No se pudo crear el directorio: %WORKDIR%
  exit /b 1
)

echo.
echo [2/6] Verificando Git...
where git >nul 2>&1
if errorlevel 1 (
  where winget >nul 2>&1
  if errorlevel 1 (
    echo Git no esta instalado y winget no esta disponible.
    echo Instala Git manualmente y vuelve a ejecutar.
    exit /b 1
  )
  echo Instalando Git con winget...
  winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo No se pudo instalar Git.
    exit /b 1
  )
  set "PATH=%PATH%;%ProgramFiles%\Git\cmd"
  where git >nul 2>&1
  if errorlevel 1 (
    echo Git fue instalado, pero Windows aun no actualizo el PATH.
    echo Cierra esta ventana y ejecuta nuevamente este mismo BAT.
    pause
    exit /b 2
  )
)

echo.
echo [3/6] Verificando Docker...
where docker >nul 2>&1
if errorlevel 1 (
  where winget >nul 2>&1
  if errorlevel 1 (
    echo Docker no esta instalado y winget no esta disponible.
    echo Instala Docker Desktop manualmente y vuelve a ejecutar.
    exit /b 1
  )
  echo Instalando Docker Desktop con winget...
  winget install --id Docker.DockerDesktop -e --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo No se pudo instalar Docker Desktop.
    exit /b 1
  )
  set "PATH=%PATH%;%ProgramFiles%\Docker\Docker\resources\bin"
  where docker >nul 2>&1
  if errorlevel 1 (
    echo Docker Desktop fue instalado, pero Windows requiere reiniciar sesion o el PC.
    echo Luego ejecuta nuevamente este mismo BAT; continuara sin borrar carpetas.
    pause
    exit /b 2
  )
)

echo.
echo [4/6] Clonando/actualizando repositorios...
set "BACKEND_DIR=%WORKDIR%\osiris-inventario-be"
set "FRONTEND_DIR=%WORKDIR%\osiris-inventario-fe"

if exist "%BACKEND_DIR%\.git" (
  echo Actualizando backend...
  git -C "%BACKEND_DIR%" fetch --all --prune
  if errorlevel 1 exit /b 1
  git -C "%BACKEND_DIR%" checkout "%BRANCH%"
  if errorlevel 1 exit /b 1
  git -C "%BACKEND_DIR%" pull --ff-only origin "%BRANCH%"
  if errorlevel 1 exit /b 1
) else (
  if exist "%BACKEND_DIR%" (
    echo Eliminando clon incompleto de backend...
    rmdir /s /q "%BACKEND_DIR%"
    if errorlevel 1 exit /b 1
  )
  echo Clonando backend...
  git clone "%BACKEND_REPO%" "%BACKEND_DIR%"
  if errorlevel 1 exit /b 1
  git -C "%BACKEND_DIR%" checkout "%BRANCH%"
  if errorlevel 1 exit /b 1
)

if exist "%FRONTEND_DIR%\.git" (
  echo Actualizando frontend...
  git -C "%FRONTEND_DIR%" fetch --all --prune
  if errorlevel 1 exit /b 1
  git -C "%FRONTEND_DIR%" checkout "%BRANCH%"
  if errorlevel 1 exit /b 1
  git -C "%FRONTEND_DIR%" pull --ff-only origin "%BRANCH%"
  if errorlevel 1 exit /b 1
) else (
  if exist "%FRONTEND_DIR%" (
    echo Eliminando clon incompleto de frontend...
    rmdir /s /q "%FRONTEND_DIR%"
    if errorlevel 1 exit /b 1
  )
  echo Clonando frontend...
  git clone "%FRONTEND_REPO%" "%FRONTEND_DIR%"
  if errorlevel 1 exit /b 1
  git -C "%FRONTEND_DIR%" checkout "%BRANCH%"
  if errorlevel 1 exit /b 1
)

echo.
echo [5/6] Verificando instalador principal...
set "INSTALL_PS1=%BACKEND_DIR%\install-windows.ps1"
if not exist "%INSTALL_PS1%" (
  echo No se encontro: %INSTALL_PS1%
  exit /b 1
)

echo.
echo [6/6] Ejecutando instalador productivo...
powershell -NoProfile -ExecutionPolicy Bypass -File "%INSTALL_PS1%" -SkipDependencyInstall -SkipGitSync
if errorlevel 1 (
  echo Instalacion finalizo con error.
  pause
  exit /b 1
)

echo.
echo Instalacion completada.
echo Si es la primera vez con Docker Desktop, puede requerir reinicio de sesion/PC.
pause
exit /b 0