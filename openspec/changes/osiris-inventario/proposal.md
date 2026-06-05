## Why

Las pequeñas y medianas empresas carecen de un sistema de inventario que garantice trazabilidad completa, impida modificaciones no controladas del stock y proporcione información confiable para operaciones, administración y contabilidad. Osiris Inventario resuelve esto con un sistema web robusto que centraliza la gestión de inventario bajo reglas estrictas de negocio y auditoría.

## What Changes

Este es el sistema inicial (greenfield). Se construyen las siguientes capacidades desde cero:

- Sistema de autenticación con usuario/contraseña, sesión con expiración configurable (default 30 min) y cierre automático por inactividad.
- Control de acceso basado en roles: Administrador, Operador y Supervisor/Auditor.
- Catálogo de productos con categorías jerárquicas ilimitadas, atributos personalizados con herencia y tipos de datos variados.
- Gestión de productos con campos base obligatorios; el stock actual solo puede modificarse mediante transacciones autorizadas.
- Cuatro tipos de movimientos de inventario: Ingreso (IN), Egreso (EG), Baja (BI) y Ajuste (AI), con flujo de autorización formal para BI y AI.
- Numeración automática consecutiva por tipo de documento (ej. IN-2025-000001).
- Kardex configurable con métodos PEPS/FIFO y Promedio Ponderado, conforme a NIIF.
- Reportes operativos y administrativos con filtros avanzados, exportables a PDF y Excel.
- Auditoría completa e inmutable de todas las operaciones relevantes del sistema.
- API REST documentada con OpenAPI (FastAPI), lista para despliegue con Docker.

## Capabilities

### New Capabilities

- `user-auth`: Autenticación con usuario/contraseña, hashing seguro, sesión JWT con expiración configurable y cierre automático por inactividad.
- `rbac`: Control de acceso basado en roles (Administrador, Operador, Supervisor/Auditor) con permisos granulares por recurso y acción.
- `product-catalog`: Gestión de productos con categorías jerárquicas ilimitadas, atributos personalizados con herencia, tipos de datos variados y campos base obligatorios.
- `inventory-movements`: Cuatro tipos de movimientos (IN, EG, BI, AI) con numeración automática, validaciones de stock, flujo de autorización para BI/AI y registro de costos y precios.
- `kardex`: Kardex por producto con métodos PEPS/FIFO y Promedio Ponderado, registro de entradas/salidas/saldos/valorizaciones, configurable desde parámetros del sistema.
- `reports`: Reportes operativos y administrativos por rango de fechas con filtros múltiples, exportables a PDF y Excel; incluye stock mínimo, inventario valorizado, Kardex y consolidado general.
- `audit-log`: Registro inmutable de todas las operaciones del sistema con fecha, hora, usuario, IP, acción, entidad, valores anteriores y nuevos.

### Modified Capabilities

## Impact

- **Backend**: Python + FastAPI, nueva base de código completa con estructura de capas (routers, services, repositories, models).
- **Base de datos**: PostgreSQL con índices optimizados, particionamiento por fecha en tablas de movimientos, auditoría y Kardex; vistas materializadas para reportes complejos.
- **Frontend**: React (proyecto separado), consume exclusivamente la API REST documentada.
- **Infraestructura**: Docker Compose para desarrollo y despliegue; configuración de variables de entorno para parámetros del sistema.
- **Dependencias clave**: FastAPI, SQLAlchemy, Alembic, Pydantic, python-jose (JWT), passlib/bcrypt, ReportLab/openpyxl para exportaciones.
