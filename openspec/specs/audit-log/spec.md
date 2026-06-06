# Spec: audit-log

## Purpose
Registro inmutable de todas las operaciones relevantes del sistema para trazabilidad y cumplimiento. Captura eventos de creación, modificación, eliminación y autenticación con información completa del actor y los valores afectados.

## Requirements

### Requirement: Registro obligatorio de todas las operaciones relevantes
El sistema SHALL registrar automáticamente en el log de auditoría toda operación de creación, modificación y eliminación lógica sobre las siguientes entidades: productos, categorías, atributos, usuarios, roles, configuraciones del sistema, documentos de inventario, líneas de movimiento, autorizaciones de BI/AI, sesiones de usuario y parámetros del sistema. El registro SHALL ser transparente para el usuario operativo (no requiere acción adicional).

#### Scenario: Creación de producto registrada en auditoría
- **WHEN** un Operador crea un producto nuevo
- **THEN** el sistema registra automáticamente un evento de auditoría tipo `CREATE` con la entidad `product` y todos los valores del producto creado

#### Scenario: Modificación de usuario registrada en auditoría
- **WHEN** un Administrador cambia el rol de un usuario
- **THEN** el sistema registra un evento `UPDATE` con valores anteriores y nuevos del campo `role`

#### Scenario: Aprobación de Baja de Inventario registrada
- **WHEN** un Administrador aprueba una BI con código de autorización
- **THEN** el sistema registra el evento con solicitante, autorizador, timestamp de aprobación y código de autorización hasheado

---

### Requirement: Estructura completa de cada evento de auditoría
Cada evento de auditoría SHALL contener obligatoriamente: `id`, `timestamp` (con zona horaria UTC), `usuario_id`, `usuario_nombre`, `ip_address`, `accion` (CREATE/UPDATE/DELETE/APPROVE/REJECT/LOGIN/LOGOUT), `entidad_tipo`, `entidad_id`, `valores_anteriores` (JSON, nullable para CREATE), `valores_nuevos` (JSON, nullable para DELETE) y `descripcion_legible`.

#### Scenario: Evento de auditoría con valores anteriores y nuevos
- **WHEN** se modifica el `pvp` de un producto
- **THEN** el evento de auditoría contiene `valores_anteriores: {"pvp": 10.50}` y `valores_nuevos: {"pvp": 12.00}`

#### Scenario: Evento de auditoría de creación sin valores anteriores
- **WHEN** se crea una nueva categoría
- **THEN** el evento de auditoría contiene `valores_anteriores: null` y `valores_nuevos` con todos los campos del objeto creado

#### Scenario: Evento de auditoría incluye IP del cliente
- **WHEN** cualquier operación auditable se ejecuta
- **THEN** el evento registra la dirección IP real del cliente (considerando proxies con header `X-Forwarded-For`)

---

### Requirement: Inmutabilidad del log de auditoría
Los registros del log de auditoría SHALL ser inmutables una vez escritos. El sistema MUST impedir cualquier modificación o eliminación de eventos de auditoría, incluso para el Administrador. La tabla de auditoría SHOULD tener permisos de solo INSERT a nivel de base de datos para el usuario de aplicación.

#### Scenario: Intento de modificar registro de auditoría
- **WHEN** cualquier usuario intenta modificar un registro del log de auditoría via API
- **THEN** el sistema retorna HTTP 405 (Method Not Allowed) ya que el endpoint no existe

#### Scenario: Intento de eliminar registro de auditoría
- **WHEN** cualquier usuario intenta eliminar un registro del log de auditoría via API
- **THEN** el sistema retorna HTTP 405 (Method Not Allowed)

---

### Requirement: Consulta y búsqueda del log de auditoría
El sistema SHALL permitir a Supervisores y Administradores consultar el log de auditoría con filtros por: rango de fechas (obligatorio), usuario, tipo de acción, entidad tipo y entidad id. Los resultados SHALL estar paginados, ordenados cronológicamente descendente.

#### Scenario: Consulta de auditoría por usuario en rango de fechas
- **WHEN** un Supervisor filtra la auditoría por `usuario_id` y rango de fechas
- **THEN** el sistema retorna todos los eventos del usuario en el período con paginación

#### Scenario: Consulta de historial de cambios de una entidad específica
- **WHEN** un Administrador consulta la auditoría filtrando por `entidad_tipo=product` y `entidad_id=123`
- **THEN** el sistema retorna el historial completo de cambios de ese producto en orden cronológico

#### Scenario: Consulta de auditoría sin filtro de fechas
- **WHEN** un usuario solicita el log de auditoría sin rango de fechas
- **THEN** el sistema retorna HTTP 422 indicando que el rango de fechas es obligatorio

---

### Requirement: Registro de eventos de sesión
El sistema SHALL registrar en auditoría todos los eventos de autenticación: login exitoso, login fallido, logout, expiración de sesión por inactividad y cambio de contraseña.

#### Scenario: Login exitoso registrado en auditoría
- **WHEN** un usuario se autentica exitosamente
- **THEN** el sistema registra un evento `LOGIN` con usuario, IP y timestamp

#### Scenario: Login fallido registrado en auditoría
- **WHEN** se intenta login con credenciales inválidas
- **THEN** el sistema registra un evento `LOGIN_FAILED` con el identificador de usuario intentado e IP (sin exponer si el usuario existe)

#### Scenario: Expiración de sesión por inactividad registrada
- **WHEN** una sesión expira por inactividad
- **THEN** el sistema registra un evento `SESSION_EXPIRED` con usuario y timestamp de expiración

---

### Requirement: Exportación del log de auditoría
El sistema SHALL permitir exportar el log de auditoría a Excel con los mismos filtros de consulta. La exportación SHALL incluir todos los registros del rango (sin límite de paginación) pero MUST requerir un rango de fechas máximo de 90 días por exportación para evitar exports excesivos.

#### Scenario: Exportar auditoría de 30 días
- **WHEN** un Administrador solicita exportar la auditoría de los últimos 30 días
- **THEN** el sistema genera un Excel con todos los eventos del período

#### Scenario: Intentar exportar más de 90 días de auditoría
- **WHEN** un usuario solicita exportar la auditoría con un rango mayor a 90 días
- **THEN** el sistema retorna HTTP 422 con código `DATE_RANGE_TOO_LARGE` indicando el máximo permitido
