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

### URLs

- Frontend: http://localhost:5173
- API: http://localhost:8000
- OpenAPI: http://localhost:8000/docs

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
