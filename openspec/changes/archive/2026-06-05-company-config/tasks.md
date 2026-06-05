## 1. Modelo y migración

- [x] 1.1 Crear modelo SQLAlchemy `CompanyConfig` en `app/models/company_config.py` con campos: `id`, `razon_social`, `nombre_comercial`, `ruc`, `direccion`, `telefono`, `email`, `logo` (Text nullable), `created_at`, `updated_at`, `updated_by` (FK a users)
- [x] 1.2 Generar migración Alembic `0006_company_config.py` que crea la tabla `company_config`
- [x] 1.3 Exportar el nuevo modelo desde `app/models/__init__.py` para que Alembic lo detecte

## 2. Schemas Pydantic

- [x] 2.1 Crear `app/schemas/company.py` con: `CompanyConfigCreate` (razon_social, ruc, email obligatorios; resto opcionales), `CompanyConfigUpdate` (todos opcionales), `CompanyConfigResponse` (todos los campos + `is_complete: bool`)
- [x] 2.2 Agregar validación en `CompanyConfigCreate`: `logo` no puede superar 2 097 152 caracteres (2 MB en base64)

## 3. Repositorio y servicio

- [x] 3.1 Crear `app/repositories/company_repository.py` con métodos: `get()` (retorna el único registro o None), `create(data)`, `update(data)`
- [x] 3.2 Crear `app/services/company_service.py` con: `get_or_none()`, `create(payload, user, request)` (lanza `COMPANY_ALREADY_EXISTS` si ya existe), `update(payload, user, request)`; registrar auditoría en create y update con `entity_type="company_config"`

## 4. Guard de empresa configurada

- [x] 4.1 Crear dependencia FastAPI `require_company_configured` en `app/core/deps.py`: consulta `CompanyRepository.get()`, verifica `is_complete`, lanza `ValidationAppError("COMPANY_NOT_CONFIGURED", ...)` si no
- [x] 4.2 Agregar `Depends(require_company_configured)` a los endpoints `POST` de ingresos, egresos, bajas y ajustes en `app/api/v1/endpoints/inventory.py`
- [x] 4.3 Agregar `Depends(require_company_configured)` a los endpoints de exportación PDF y Excel en `app/api/v1/endpoints/reports.py`

## 5. Endpoints REST

- [x] 5.1 Crear `app/api/v1/endpoints/company.py` con: `GET /company` (cualquier usuario autenticado), `POST /company` (solo admin), `PATCH /company` (solo admin)
- [x] 5.2 Registrar el router en `app/api/v1/router.py` con prefix `/company` y tag `company`

## 6. Utilidad de encabezado para reportes

- [x] 6.1 Crear `app/utils/report_header.py` con función `build_header(company: CompanyConfig) -> dict` que retorna: `razon_social`, `nombre_comercial`, `ruc`, `logo`, `generated_at` (ISO string), y `report_name` (parámetro)
- [x] 6.2 Modificar el servicio de exportación PDF (`app/services/report_service.py` o equivalente) para incluir el encabezado corporativo al inicio de cada PDF exportado: logo (si existe), razón social, nombre comercial, RUC, fecha/hora, nombre del reporte
- [x] 6.3 Modificar el servicio de exportación Excel para agregar las primeras filas con: razón social, nombre comercial, RUC, fecha de generación y nombre del reporte

## 7. Seed — nuevos SystemParams

- [x] 7.1 Agregar al seed (`scripts/seed.py`) las claves: `doc_number_prefix` (default `"OSR"`), `doc_number_padding` (default `"6"`), `report_include_logo` (default `"true"`), con idempotencia (crear solo si no existen)

## 8. Tests

- [x] 8.1 Crear `tests/test_company_config.py` con tests: GET sin configuración retorna 404; POST crea correctamente; GET retorna el registro; PATCH actualiza; segundo POST retorna 409; acceso sin admin retorna 403
- [x] 8.2 Test: `POST /inventory/ingresos` sin empresa configurada retorna 422 con código `COMPANY_NOT_CONFIGURED`
- [x] 8.3 Test: endpoint de exportación de reporte sin empresa configurada retorna 422 con código `COMPANY_NOT_CONFIGURED`
- [x] 8.4 Test: auditoría registra CREATE y UPDATE de company_config correctamente
