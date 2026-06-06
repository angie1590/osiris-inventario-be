# Spec: user-auth

## Purpose
Autenticación de usuarios mediante identificador y contraseña con emisión de tokens JWT. Gestiona el ciclo de vida de sesiones, renovación de tokens, cierre de sesión explícito, almacenamiento seguro de contraseñas y cambio obligatorio de contraseña en el primer login.

## Requirements

### Requirement: Login con usuario y contraseña
El sistema SHALL autenticar usuarios mediante un identificador de usuario (no email) y contraseña. Las contraseñas MUST almacenarse usando bcrypt. El identificador de usuario es asignado por el Administrador y es único en el sistema. Tras autenticación exitosa, el sistema SHALL emitir un access token JWT y un refresh token.

#### Scenario: Login exitoso
- **WHEN** un usuario envía credenciales válidas (usuario + contraseña correcta)
- **THEN** el sistema retorna un access token JWT y un refresh token con HTTP 200

#### Scenario: Login con contraseña incorrecta
- **WHEN** un usuario envía un usuario existente con contraseña incorrecta
- **THEN** el sistema retorna HTTP 401 con mensaje genérico sin revelar si el usuario existe

#### Scenario: Login con usuario inexistente
- **WHEN** un usuario envía un identificador que no existe en el sistema
- **THEN** el sistema retorna HTTP 401 con el mismo mensaje genérico que contraseña incorrecta

#### Scenario: Login con usuario inactivo
- **WHEN** un usuario con estado inactivo intenta autenticarse
- **THEN** el sistema retorna HTTP 401 y deniega el acceso

---

### Requirement: Expiración de sesión configurable por inactividad
El access token SHALL tener un tiempo de expiración configurable por el Administrador (default 30 minutos). Cada request autenticado exitoso DEBE renovar el contador de inactividad. Cuando el tiempo de inactividad se agota, el token SHALL invalidarse y el usuario MUST re-autenticarse.

#### Scenario: Sesión activa dentro del tiempo configurado
- **WHEN** un usuario hace un request antes de que expire el tiempo de inactividad
- **THEN** el sistema procesa el request normalmente y renueva el contador de inactividad

#### Scenario: Sesión expirada por inactividad
- **WHEN** un usuario hace un request después de que expire el tiempo de inactividad configurado
- **THEN** el sistema retorna HTTP 401 con código `SESSION_EXPIRED`

#### Scenario: Cambio del tiempo de inactividad por Administrador
- **WHEN** un Administrador modifica el parámetro `session_timeout_minutes`
- **THEN** el nuevo valor aplica a todas las sesiones nuevas y activas a partir de ese momento

---

### Requirement: Renovación de token con refresh token
El sistema SHALL permitir renovar el access token usando el refresh token sin necesidad de ingresar credenciales nuevamente, siempre que el refresh token sea válido y no haya expirado.

#### Scenario: Renovación exitosa
- **WHEN** el cliente envía un refresh token válido y no expirado
- **THEN** el sistema emite un nuevo access token y opcionalmente un nuevo refresh token con HTTP 200

#### Scenario: Renovación con refresh token inválido
- **WHEN** el cliente envía un refresh token inválido, expirado o ya utilizado
- **THEN** el sistema retorna HTTP 401 y el usuario debe re-autenticarse completamente

---

### Requirement: Cierre de sesión explícito
El sistema SHALL permitir al usuario cerrar su sesión activa. Al cerrar sesión, el access token y refresh token actuales MUST invalidarse inmediatamente y no podrán reutilizarse.

#### Scenario: Logout exitoso
- **WHEN** un usuario autenticado solicita cerrar sesión
- **THEN** el sistema invalida los tokens activos, registra el evento en auditoría y retorna HTTP 200

#### Scenario: Uso de token revocado después de logout
- **WHEN** un cliente intenta usar un access token después de que el usuario cerró sesión
- **THEN** el sistema retorna HTTP 401 con código `TOKEN_REVOKED`

---

### Requirement: Almacenamiento seguro de contraseñas
El sistema SHALL almacenar únicamente el hash de las contraseñas usando bcrypt con factor de costo mínimo de 12. Nunca se almacenará la contraseña en texto plano, logs ni respuestas de API.

#### Scenario: Registro de nuevo usuario con contraseña
- **WHEN** un Administrador crea un usuario con contraseña temporal
- **THEN** el sistema almacena únicamente el hash bcrypt, nunca la contraseña en texto plano

#### Scenario: Cambio de contraseña
- **WHEN** un usuario cambia su contraseña
- **THEN** el sistema genera un nuevo hash bcrypt y descarta el hash anterior; los tokens anteriores son invalidados

---

### Requirement: Cambio de contraseña obligatorio en primer login
El sistema SHALL marcar cuentas nuevas con flag `must_change_password`. En el primer login, el sistema MUST forzar al usuario a cambiar su contraseña temporal antes de acceder a cualquier otra función.

#### Scenario: Primer login con contraseña temporal
- **WHEN** un usuario con `must_change_password = true` se autentica
- **THEN** el sistema retorna HTTP 200 con campo `require_password_change: true` y el access token solo permite acceder al endpoint de cambio de contraseña

#### Scenario: Cambio de contraseña inicial exitoso
- **WHEN** el usuario envía una nueva contraseña válida al endpoint de cambio inicial
- **THEN** el sistema actualiza el hash, desactiva el flag `must_change_password` y emite tokens de acceso completo
