## Context

Osiris Inventario es un sistema greenfield de gestión de inventario para PyMEs. No existe base de código previa. El backend se construye con Python + FastAPI y PostgreSQL; el frontend (proyecto separado) consumirá exclusivamente la API REST. El sistema debe garantizar trazabilidad completa, impedir modificaciones directas de stock y soportar grandes volúmenes de datos con rendimiento constante.

Stakeholders: Administradores (configuración y autorización), Operadores (registro de movimientos), Supervisores/Auditores (consulta y reportes).

## Goals / Non-Goals

**Goals:**
- API REST documentada (OpenAPI) con FastAPI, lista para consumo desde frontend React.
- Autenticación segura con JWT, expiración configurable y cierre de sesión por inactividad.
- RBAC de tres roles con permisos por recurso/acción.
- Catálogo de productos con categorías jerárquicas y atributos heredados.
- Stock modificable únicamente via transacciones autorizadas (nunca edición directa).
- Cuatro tipos de movimientos con flujo de autorización formal para BI y AI.
- Kardex PEPS/FIFO y Promedio Ponderado, configurable desde parámetros del sistema.
- Reportes exportables a PDF y Excel con filtros avanzados.
- Auditoría completa e inmutable en todas las operaciones relevantes.
- Despliegue con Docker Compose, configuración por variables de entorno.
- Particionamiento de tablas de alta rotación (movimientos, auditoría, Kardex) por año/mes.

**Non-Goals:**
- Desarrollo del frontend React (proyecto separado).
- Integración con sistemas ERP externos en esta versión.
- Soporte multi-empresa/multi-tenancy.
- Gestión de proveedores o módulo de compras completo.
- Facturación electrónica o integración con SRI/SAT.
- App móvil nativa.

## Decisions

### D1: FastAPI + SQLAlchemy 2.x + Alembic

**Decisión**: FastAPI para routing/validación, SQLAlchemy 2.x (async) con patrón repository, Alembic para migraciones.

**Alternativas consideradas**: Django REST Framework (más monolítico, ORM acoplado), Flask (demasiado manual para un sistema de esta escala).

**Rationale**: FastAPI ofrece validación Pydantic integrada, generación automática de OpenAPI, alto rendimiento async y tipado estático. SQLAlchemy 2.x con async permite consultas no bloqueantes. El patrón repository desacopla la lógica de negocio del ORM.

---

### D2: JWT con refresh token y blacklist en Redis

**Decisión**: Access token (corto plazo, 30 min configurable) + refresh token (larga duración) almacenado en DB. Blacklist de tokens revocados en Redis para logout y expiración por inactividad.

**Alternativas consideradas**: Solo JWT sin blacklist (no permite invalidación en tiempo real), sesiones en DB (más latencia).

**Rationale**: La expiración por inactividad requiere poder invalidar tokens activos. Redis ofrece expiración automática (TTL), bajo latency y no contamina la DB principal. El refresh token en DB permite auditar sesiones activas.

---

### D3: Stock solo via transacciones — constraint a nivel de aplicación y DB trigger

**Decisión**: El campo `stock_actual` en la tabla `products` solo se actualiza mediante stored procedure / service layer. Un trigger PostgreSQL rechaza cualquier UPDATE directo al campo desde fuera de la función autorizada.

**Alternativas consideradas**: Solo restricción de aplicación (bypasseable vía psql directo), solo restricción de rol DB (compleja de mantener).

**Rationale**: Defensa en profundidad: la capa de servicio es la primera barrera, el trigger es la última. Esto garantiza que ni errores de código ni acceso directo a la DB puedan corromper el stock.

---

### D4: Particionamiento por rango de fechas (RANGE partitioning)

**Decisión**: Las tablas `inventory_movements`, `audit_logs` y `kardex_entries` se particionan por año-mes usando PostgreSQL declarative partitioning (RANGE on `created_at`).

**Alternativas consideradas**: Sin particionamiento (degradación de rendimiento a gran escala), particionamiento por hash (no alineado con filtros por fecha que dominan las queries).

**Rationale**: Los reportes y auditorías siempre filtran por rango de fechas. El particionamiento por fecha permite partition pruning y mantiene rendimiento constante al crecer el volumen. Las particiones antiguas pueden archivarse sin impactar el sistema.

---

### D5: Kardex calculado en tiempo real con snapshots periódicos

**Decisión**: El Kardex se calcula en tiempo real al registrar cada movimiento (se actualiza la tabla `kardex_entries`). Para reportes históricos complejos se usan vistas materializadas que se refrescan periódicamente.

**Alternativas consideradas**: Calcular el Kardex solo al consultar (costoso para historiales largos), recalcular completo en cada movimiento (prohibitivo en volumen).

**Rationale**: Actualización incremental al registrar cada transacción mantiene el Kardex siempre consistente. Las vistas materializadas aceleran reportes sin recálculos completos.

---

### D6: Flujo de autorización BI/AI con código de autorización

**Decisión**: Bajas e Ajustes de Inventario requieren: (1) registro de solicitud por Operador → estado `pendiente`; (2) aprobación por Administrador mediante código de autorización generado por el sistema (OTP de un solo uso, válido 15 min). El movimiento solo afecta stock al aprobarse.

**Alternativas consideradas**: Solo aprobación por clic (menos seguro, sin registro de intención), firma digital (complejidad excesiva para PyMEs).

**Rationale**: El código de autorización vincula la identidad del administrador a la operación y proporciona evidencia auditable. Es suficientemente seguro para PyMEs sin requerir infraestructura PKI.

---

### D7: Estructura de capas del backend

```
app/
  api/          # Routers FastAPI (endpoints REST)
  core/         # Config, seguridad, dependencias
  models/       # SQLAlchemy models (ORM)
  schemas/      # Pydantic schemas (request/response)
  services/     # Lógica de negocio
  repositories/ # Acceso a datos (patrón repository)
  utils/        # Helpers (exportación PDF/Excel, etc.)
```

**Rationale**: Separación clara de responsabilidades facilita testing por capas y escalabilidad futura.

---

### D8: Paginación obligatoria en todos los listados

**Decisión**: Todos los endpoints de listado implementan cursor-based pagination (keyset pagination) con límite máximo configurable (default 100 registros). Reportes complejos tienen endpoints dedicados con paginación propia.

**Alternativas consideradas**: Offset pagination (degradación de rendimiento en páginas tardías), sin paginación (inaceptable en producción).

**Rationale**: Keyset pagination mantiene rendimiento constante independientemente del volumen total de datos.

## Risks / Trade-offs

- **Complejidad del trigger de stock** → Puede dificultar debugging en migraciones. Mitigación: documentar exhaustivamente en código y mantener tests de integración que validen el comportamiento del trigger.
- **Particionamiento requiere gestión de particiones** → PostgreSQL no crea particiones futuras automáticamente. Mitigación: job de mantenimiento que crea particiones del mes siguiente con anticipación.
- **Vistas materializadas desactualizadas** → Los reportes pueden mostrar datos con segundos/minutos de retraso. Mitigación: configurar refresh automático frecuente y documentar el comportamiento al usuario.
- **Redis como dependencia adicional** → Aumenta complejidad de infraestructura. Mitigación: Redis configurado en Docker Compose; si no está disponible, el sistema puede operar con degradación (logout no invalida token inmediatamente, sesión expira al vencer el JWT).
- **Kardex PEPS requiere FIFO estricto de lotes** → Cambiar el método activo retroactivamente invalida el Kardex histórico. Mitigación: el método solo puede cambiarse en un nuevo ejercicio contable; el historial previo queda bloqueado.

## Migration Plan

Sistema greenfield — no hay migración de datos existentes.

1. Inicializar DB con Alembic `initial_migration`.
2. Crear particiones iniciales para año actual + siguiente.
3. Crear usuario Administrador inicial vía script de seed.
4. Configurar parámetros del sistema (método Kardex, timeout de sesión).
5. Desplegar con `docker compose up -d`.
6. Ejecutar test suite de integración contra la instancia desplegada.

Rollback: dado que es greenfield, el rollback es simplemente no desplegar o destruir el contenedor.

## Open Questions

- ¿El frontend necesita WebSockets para notificaciones en tiempo real (ej. cuando se aprueba una BI/AI)? Si sí, considerar Server-Sent Events como alternativa más simple.
- ¿Se requiere soporte multilenguaje (i18n) en los mensajes de la API desde el inicio?
- ¿Los reportes PDF deben incluir logo y membrete personalizables por la empresa?
- ¿La exportación Excel debe generar tablas con formato o solo datos planos (CSV equivalente)?
