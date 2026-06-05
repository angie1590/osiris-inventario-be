## ADDED Requirements

### Requirement: Tres roles de sistema predefinidos
El sistema SHALL implementar tres roles: `Administrador`, `Operador` y `Supervisor`. Cada rol define un conjunto fijo de permisos sobre recursos del sistema. Los roles no son modificables por usuarios finales.

#### Scenario: Asignación de rol a usuario
- **WHEN** un Administrador asigna un rol a un usuario
- **THEN** el usuario adquiere todos los permisos asociados a ese rol inmediatamente

#### Scenario: Cambio de rol de un usuario
- **WHEN** un Administrador cambia el rol de un usuario activo
- **THEN** los permisos del usuario se actualizan en la siguiente request autenticada; las sesiones activas deben reflejar el nuevo rol en máximo 1 minuto

---

### Requirement: Permisos del Administrador
El Administrador SHALL tener acceso total al sistema, incluyendo: gestión de usuarios, gestión de roles, configuración de parámetros del sistema, aprobación de Bajas e Ajustes de Inventario, acceso a todos los reportes y consulta de auditoría completa.

#### Scenario: Administrador accede a gestión de usuarios
- **WHEN** un Administrador accede al módulo de usuarios
- **THEN** puede crear, editar, activar, desactivar y asignar roles a usuarios

#### Scenario: Administrador aprueba Baja de Inventario
- **WHEN** un Administrador emite un código de autorización para una BI/AI pendiente
- **THEN** el movimiento se aprueba y afecta el inventario

#### Scenario: Rol no-Administrador intenta configurar parámetros del sistema
- **WHEN** un Operador o Supervisor intenta modificar parámetros del sistema
- **THEN** el sistema retorna HTTP 403

---

### Requirement: Permisos del Operador
El Operador SHALL poder: registrar productos, crear movimientos de inventario tipo IN y EG, solicitar Bajas (BI) y Ajustes (AI) que quedan pendientes de aprobación. El Operador NO podrá aprobar operaciones, modificar configuraciones ni acceder a reportes administrativos.

#### Scenario: Operador registra un Ingreso de Mercadería
- **WHEN** un Operador crea un documento IN con datos válidos
- **THEN** el sistema registra el documento y actualiza el stock del producto

#### Scenario: Operador intenta aprobar una Baja de Inventario
- **WHEN** un Operador intenta aprobar una solicitud BI pendiente
- **THEN** el sistema retorna HTTP 403

#### Scenario: Operador intenta ver reportes administrativos
- **WHEN** un Operador accede a un endpoint de reporte restringido a Supervisor/Administrador
- **THEN** el sistema retorna HTTP 403

---

### Requirement: Permisos del Supervisor/Auditor
El Supervisor SHALL poder: consultar productos e inventario, generar y exportar todos los reportes, revisar el log de auditoría completo. El Supervisor NO podrá crear ni modificar productos, registrar movimientos ni cambiar configuraciones.

#### Scenario: Supervisor consulta el Kardex de un producto
- **WHEN** un Supervisor solicita el Kardex de un producto específico
- **THEN** el sistema retorna el Kardex completo con HTTP 200

#### Scenario: Supervisor intenta registrar un movimiento de inventario
- **WHEN** un Supervisor intenta crear un documento EG
- **THEN** el sistema retorna HTTP 403

#### Scenario: Supervisor exporta un reporte a Excel
- **WHEN** un Supervisor solicita la exportación de un reporte
- **THEN** el sistema genera y retorna el archivo Excel con HTTP 200

---

### Requirement: Verificación de permisos en cada request
El sistema SHALL verificar permisos en cada request autenticado. La verificación MUST ocurrir después de la validación del token y DEBE considerar el rol actual del usuario, no el rol al momento de emitir el token.

#### Scenario: Request a endpoint protegido con token válido y permiso correcto
- **WHEN** un usuario con rol y permiso válido accede a un endpoint protegido
- **THEN** el sistema procesa el request normalmente

#### Scenario: Request a endpoint protegido con token válido pero sin permiso
- **WHEN** un usuario con token válido pero rol insuficiente accede a un endpoint restringido
- **THEN** el sistema retorna HTTP 403 con código `INSUFFICIENT_PERMISSIONS`

#### Scenario: Request sin token de autenticación
- **WHEN** un cliente accede a cualquier endpoint protegido sin token
- **THEN** el sistema retorna HTTP 401 con código `AUTHENTICATION_REQUIRED`
