# Osiris Inventario — Backend

API de gestión de inventario para PyMEs. Backend Python + FastAPI + PostgreSQL + Redis.

## Stack

| Componente       | Tecnología                           |
| ---------------- | ------------------------------------ |
| Framework        | FastAPI 0.115+                       |
| ORM              | SQLAlchemy 2.x async                 |
| Migraciones      | Alembic                              |
| Base de datos    | PostgreSQL 16                        |
| Caché / Sesiones | Redis 7                              |
| Auth             | JWT (python-jose) + bcrypt (passlib) |
| Exportaciones    | ReportLab (PDF), openpyxl (Excel)    |

## Inicio rápido

### Prerrequisitos

- Docker + Docker Compose
- Python 3.11+ (solo para desarrollo local sin Docker)

### Con Docker Compose

```bash
# 1. Copiar variables de entorno
cp .env.example .env

# 2. Levantar servicios
docker compose up -d

# 3. Ejecutar migraciones
docker compose exec api alembic upgrade head

# 4. Crear datos iniciales (usuario admin + parámetros)
docker compose exec api python -m scripts.seed

# La API está disponible en http://localhost:8000
# Documentación OpenAPI: http://localhost:8000/docs
```

### Desarrollo local (sin Docker)

```bash
# Instalar dependencias
pip install poetry
poetry install

# Variables de entorno
cp .env.example .env
# Editar .env con URLs locales de PostgreSQL y Redis

# Migraciones
alembic upgrade head

# Seed
python -m scripts.seed

# Ejecutar
uvicorn app.main:app --reload
```

## Variables de entorno

| Variable                      | Descripción                                       | Default                     |
| ----------------------------- | ------------------------------------------------- | --------------------------- |
| `DATABASE_URL`                | URL de PostgreSQL (asyncpg)                       | `postgresql+asyncpg://...`  |
| `REDIS_URL`                   | URL de Redis                                      | `redis://localhost:6379/0`  |
| `SECRET_KEY`                  | Clave secreta para JWT                            | _(cambiar en producción)_   |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Timeout de sesión en minutos                      | `30`                        |
| `REFRESH_TOKEN_EXPIRE_DAYS`   | Validez del refresh token                         | `7`                         |
| `KARDEX_METHOD`               | Método de valoración: `PEPS` o `WEIGHTED_AVERAGE` | `PEPS`                      |
| `CORS_ORIGINS`                | Orígenes CORS permitidos (JSON array)             | `["http://localhost:3000"]` |
| `MAX_EXPORT_DATE_RANGE_DAYS`  | Máximo de días para exportar auditoría            | `90`                        |
| `APP_ENV`                     | Entorno: `development`, `production`, `test`      | `development`               |

## Credenciales iniciales

Después de ejecutar `scripts.seed`:

- **Usuario**: `admin`
- **Contraseña**: `Admin@12345!`
- **Nota**: Se solicitará cambio de contraseña en el primer login.

Si el usuario `admin` ya existía y la clave por defecto no funciona, puedes resetearla:

```bash
# Compose backend
docker compose exec api python -m scripts.reset_admin_password

# Compose full stack
docker compose -f docker-compose.full.yml exec api python -m scripts.reset_admin_password
```

> Importante: tras un `git pull`, reconstruye la imagen (`up -d --build`) antes de
> ejecutar el script. La carpeta `scripts/` no se monta como volumen, por lo que un
> contenedor antiguo no verá los scripts nuevos. El script crea el admin si no existe,
> reactiva la cuenta, restablece la clave y verifica el hash (imprime `Verificacion de
contrasena: OK`).

## Comandos útiles

```bash
# Crear nueva migración
alembic revision --autogenerate -m "descripcion"

# Ejecutar migraciones
alembic upgrade head

# Revertir última migración
alembic downgrade -1

# Ejecutar tests — usan una base dedicada (osiris_inventario_test), creada
# automáticamente. NUNCA tocan la base de desarrollo.
docker compose run --rm api pytest

# Apuntar a otra base de test (opcional)
TEST_DATABASE_URL=postgresql+asyncpg://osiris:pass@localhost:5432/mi_test pytest

# Ejecutar tests con cobertura
pytest --cov=app --cov-report=html

# Mantenimiento de particiones (ejecutar mensualmente)
python -m scripts.create_partitions
```

## Ejecutar Todo Con Docker (Backend + Frontend)

Esto levanta en un solo paso: PostgreSQL, Redis, API y Frontend.

### Requisito de carpetas

El archivo `docker-compose.full.yml` asume esta estructura (carpetas hermanas):

```text
.../tu-carpeta/
  osiris-inventario-be/
  osiris-inventario-fe/
```

### macOS / Linux

```bash
cd osiris-inventario-be
chmod +x start-docker.sh stop-docker.sh
./start-docker.sh
```

Para detener:

```bash
./stop-docker.sh
```

### Windows (PowerShell)

```powershell
cd osiris-inventario-be
./start-docker.ps1
```

Para detener:

```powershell
./stop-docker.ps1
```

### Windows (CMD o doble clic)

```bat
cd osiris-inventario-be
start-docker.bat
```

Para detener:

```bat
stop-docker.bat
```

Tambien puedes ejecutar directamente con doble clic sobre:

- `start-docker.bat`
- `stop-docker.bat`

## Instalacion Windows (servidor + cliente en el mismo PC)

Para instalar todo en una sola maquina Windows en modo produccion (Nginx + API + Postgres + Redis), usa:

```bat
cd osiris-inventario-be
install-windows.bat
```

Esto ejecuta `install-windows.ps1`, que:

- instala Docker Desktop con `winget` si falta,
- instala Git con `winget` si falta,
- inicia Docker Desktop y espera el motor,
- opcionalmente actualiza backend/frontend desde Git (`fetch + checkout + pull`),
- pide en consola toda la configuracion de `.env.prod` (usuario/clave DB, `SECRET_KEY`, CORS, puerto web, etc.),
- levanta `postgres`, `redis`, `api` y `web` con `docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build`,
- valida `http://localhost:<WEB_PORT>/health`,
- abre el navegador en el frontend publicado por Nginx.

Si Docker Desktop y Git ya estan instalados, puedes omitir instalacion de dependencias:

```powershell
./install-windows.ps1 -SkipDependencyInstall
```

Si no quieres sincronizar desde Git en una ejecucion puntual:

```powershell
./install-windows.ps1 -SkipGitSync
```

### Instalador de 1 solo archivo BAT

Si quieres llevar solo un archivo a otra PC Windows, usa `bootstrap-install-windows.bat`.

Flujo:

- pide directorio de instalacion,
- pide URLs Git de backend y frontend,
- instala Git/Docker Desktop si faltan,
- clona o actualiza ambos repositorios,
- ejecuta automaticamente `install-windows.ps1` del backend.

Ejecucion:

```bat
bootstrap-install-windows.bat
```

Importante: para este modo se necesita acceso a internet y URLs Git validas de ambos repositorios.

Si Docker Desktop requiere cerrar sesion o reiniciar Windows, ejecuta nuevamente el mismo BAT. El instalador reutiliza repositorios completos y reemplaza automaticamente clones incompletos; no es necesario borrar `C:\OsirisDeploy` manualmente.

El despliegue actual conserva el codigo fuente en `C:\OsirisDeploy` porque Docker construye las imagenes localmente y el actualizador usa Git. Los contenedores no leen directamente esos archivos durante la ejecucion, pero se necesitan para reconstruir y actualizar el sistema. Para eliminar el codigo fuente del servidor haria falta publicar imagenes preconstruidas en un registro como GitHub Container Registry.

### Actualizar una instalacion existente (Windows)

Si el sistema ya esta instalado, puedes actualizarlo con los ultimos cambios del repo usando:

```bat
update-windows.bat
```

Este script:

- hace `fetch + checkout + pull` en backend y frontend,
- reaplica el despliegue con `docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build`,
- valida salud en `http://localhost:<WEB_PORT>/health`.

Al finalizar la instalacion tambien puede configurar backup diario:

- pregunta hora (`HH:mm`),
- pregunta ruta de destino (por ejemplo una memoria flash `E:\osiris-backups`),
- crea tarea programada de Windows `OsirisDailyDatabaseBackup`,
- ejecuta `backup-db.ps1` para generar `.sql` y eliminar respaldos antiguos segun retencion.

Opciones comunes:

```bat
update-windows.bat -Branch main
update-windows.bat -SkipGitPull
update-windows.bat -SkipBuild
```

Notas:

- `-SkipGitPull` redepliega con el codigo local actual.
- `-SkipBuild` evita reconstruir imagenes y solo recrea servicios si aplica.
- si la memoria flash no esta conectada al momento del backup, la tarea fallara ese dia y continuara al siguiente intento.

### URLs

- Frontend: `http://localhost` (o `http://localhost:<WEB_PORT>` si cambias puerto)
- API (proxy): `http://localhost/api/v1`
- OpenAPI: `http://localhost/docs`

## Arquitectura

```
app/
  api/v1/endpoints/   # Routers FastAPI (auth, users, categories, products,
  |                   #   inventory, kardex, reports, audit, admin)
  core/               # Config, seguridad, dependencias, excepciones, DB, Redis
  models/             # SQLAlchemy ORM models + enums
  schemas/            # Pydantic schemas (request/response)
  services/           # Lógica de negocio (auth, categories, products,
  |                   #   inventory, kardex, audit)
  repositories/       # Acceso a datos (patrón repository)
  utils/              # Utilidades (ExportService PDF/Excel)
```

## Roles y permisos

| Rol          | Descripción                                                              |
| ------------ | ------------------------------------------------------------------------ |
| `admin`      | Acceso total: usuarios, configuración, aprobaciones, reportes, auditoría |
| `operator`   | Registrar productos, crear movimientos IN/EG, solicitar BI/AI            |
| `supervisor` | Consulta y reportes (solo lectura)                                       |

## Seguridad

- Contraseñas hasheadas con bcrypt (factor de costo 12).
- JWT access token con expiración configurable por inactividad.
- Refresh token rotado en cada uso.
- Blacklist de tokens revocados en Redis.
- Trigger PostgreSQL previene modificación directa de `stock_actual`.
- Log de auditoría inmutable en todas las operaciones relevantes.
- Código OTP de un solo uso (15 min) para aprobar Bajas y Ajustes.
