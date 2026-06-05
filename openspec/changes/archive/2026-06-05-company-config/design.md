## Context

El backend ya cuenta con `SystemParam` para parámetros clave/valor genéricos y un servicio de exportación PDF/Excel (reportpy/openpyxl). Lo que falta es un modelo estructurado para los datos corporativos, ya que usar `SystemParam` para campos como el logo (potencialmente binario/base64 grande) o RUC no sería apropiado. Los reportes actuales no tienen encabezado corporativo.

## Goals / Non-Goals

**Goals:**
- Modelo `CompanyConfig` singleton con validación de completitud.
- CRUD REST bajo `/api/v1/company` restringido a admins.
- Guard reutilizable que bloquea documentos y reportes si la empresa no está configurada.
- Inyección automática del encabezado corporativo en todos los exports PDF/Excel existentes.
- Registro de auditoría en cada CREATE/UPDATE de la configuración.

**Non-Goals:**
- Pantalla frontend (proponer como `company-config-ui` por separado).
- Soporte para múltiples empresas / multi-tenant.
- Almacenamiento del logo en S3 u objeto externo (se guarda como URL o base64 en columna Text).

## Decisions

**D1 — Tabla dedicada vs SystemParam**
`CompanyConfig` usa tabla propia (`company_config`) con columnas tipadas, no clave/valor en `SystemParam`. Motivo: el logo puede ser base64 grande, se necesita validación de completitud campo por campo, y los reportes necesitan acceder a los datos en forma estructurada sin parsear JSON/texto.

**D2 — Singleton controlado por aplicación**
La tabla puede tener a lo sumo un registro. Se garantiza con un check en el service: si ya existe, `POST /company` devuelve 409; usar `PATCH /company` para actualizar. No se usa un único ID fijo en la PK para evitar acoplamiento implícito; en cambio, el servicio hace `SELECT ... LIMIT 1`.

**D3 — Logo como Text (URL o base64)**
El logo se almacena como string en una columna `Text`. El cliente envía una URL pública o un data-URI base64. El backend no valida el contenido binario, solo que el campo no supere 2 MB en longitud de string. Esto evita dependencias de almacenamiento externo en la fase inicial.

**D4 — Guard como dependencia FastAPI**
Se crea `require_company_configured()` como dependencia inyectable (`Depends`). Se agrega como dependencia en los routers de inventario (POST ingresos/egresos/bajas/ajustes) y en los endpoints de exportación de reportes. Los endpoints de listado y detalle no requieren el guard.

**D5 — Auditoría via AuditService existente**
Se reutiliza `AuditService.log()` con `entity_type="company_config"`, `entity_id=1` (singleton), y acciones `CREATE`/`UPDATE`. No se requieren cambios en el modelo de auditoría.

**D6 — Encabezado de reportes como función utilitaria**
Se crea `app/utils/report_header.py` con `build_header(company: CompanyConfig) -> dict` que devuelve los campos de encabezado normalizados. Cada función de exportación (PDF/Excel) llama a esta utilidad para ensamblar el encabezado antes de escribir el contenido.

## Risks / Trade-offs

- **Logo grande en DB** → El logo base64 puede ser varios MB. Mitigation: validar longitud máxima en el schema Pydantic (≤ 2 MB = ~2_097_152 chars). Si en el futuro se migra a S3, solo cambia el campo `logo_url`.
- **Guard agresivo en producción** → Si la empresa no está configurada, operaciones transaccionales fallan con 422. Mitigation: el seed inicial puede dejar un registro de empresa incompleto con un flag `is_complete=False`, y documentar el flujo de onboarding.
- **Migración en sistemas live** → La nueva tabla y columnas se agregan sin modificar tablas existentes. Rollback seguro: `alembic downgrade -1` elimina la tabla `company_config`.

## Migration Plan

1. Agregar migración Alembic: crea tabla `company_config`.
2. El seed existente no se modifica; la configuración de empresa es opcional al arrancar.
3. En producción: ejecutar `alembic upgrade head` antes de desplegar el nuevo código.
4. Rollback: `alembic downgrade -1` elimina la tabla sin afectar el resto del sistema.
