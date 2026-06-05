## Why

El sistema carece de identidad corporativa: los documentos y reportes generados no incluyen datos de la empresa propietaria del inventario, lo que los hace inválidos para uso formal o auditoría externa. Además, los parámetros generales del sistema están parcialmente configurables pero carecen de un modelo de empresa que los ancle.

## What Changes

- Se agrega el modelo `CompanyConfig` con todos los datos de la empresa (razón social, nombre comercial, RUC, dirección, teléfono, email, logo en base64/URL).
- Se expone un conjunto de endpoints REST para crear, leer y actualizar la configuración de empresa (solo admins).
- El sistema bloquea la generación de documentos (IN, EG, BI, AI) y reportes si la configuración obligatoria de empresa no está completa.
- Los reportes PDF y Excel incorporan automáticamente el encabezado corporativo (logo, razón social, nombre comercial, RUC, fecha/hora, nombre del reporte).
- Los formatos de impresión/exportación de documentos transaccionales incluyen la información de empresa.
- Cada creación o modificación de `CompanyConfig` queda registrada en auditoría.
- Los parámetros del sistema (`SystemParam`) se extienden con las nuevas claves de configuración: prefijo/formato documental, opciones de reportes.

## Capabilities

### New Capabilities
- `company-config`: Gestión CRUD de la configuración corporativa de la empresa, validación de completitud, y exposición de datos para uso en documentos y reportes.

### Modified Capabilities
- `reports`: Los reportes ahora requieren que la empresa esté configurada y deben incluir el encabezado corporativo en PDF/Excel.
- `inventory-documents`: Los documentos transaccionales (IN, EG, BI, AI) verifican que la empresa esté configurada antes de generarse y la incluyen en sus exports.
- `system-params`: Se amplían las claves permitidas con prefijo documental y opciones de generación de reportes.

## Impact

- **Backend**: Nuevo modelo `CompanyConfig` y migración Alembic; nuevos endpoints en `/api/v1/company`; guards en los routers de inventario y reportes; extensión del servicio de exportación PDF/Excel para incluir encabezado.
- **Base de datos**: Nueva tabla `company_config` (singleton — máximo 1 registro); columna `logo` como texto (URL o base64).
- **Auditoría**: Nuevas entradas de auditoría con `entity_type = "company_config"`.
- **Reportes**: Todas las funciones de generación de PDF/Excel reciben el objeto empresa como parámetro.
- **Frontend**: Nuevas pantallas de configuración de empresa en el panel admin (fuera del scope de este cambio — se puede proponer como cambio separado `company-config-ui`).
