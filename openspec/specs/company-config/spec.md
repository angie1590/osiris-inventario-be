# Spec: company-config

## Purpose
Gestión de la configuración corporativa singleton de la empresa propietaria del inventario. Incluye CRUD restringido por rol, indicador de completitud y registro de auditoría.

## Requirements

### Requirement: Modelo de configuración de empresa
El sistema debe mantener una configuración corporativa singleton con los datos de la empresa propietaria del inventario.

#### Scenario: Campos obligatorios
- **WHEN** se crea o actualiza la configuración de empresa
- **THEN** los campos `razon_social`, `ruc` y `email` son obligatorios; el resto son opcionales

#### Scenario: Singleton
- **WHEN** ya existe una configuración de empresa en el sistema
- **THEN** `POST /api/v1/company` responde 409 CONFLICT con código `COMPANY_ALREADY_EXISTS`

---

### Requirement: CRUD restringido a administradores
Solo usuarios con rol `admin` pueden crear o modificar la configuración de empresa.

#### Scenario: Acceso de lectura libre
- **WHEN** cualquier usuario autenticado llama `GET /api/v1/company`
- **THEN** recibe la configuración actual (o 404 si no existe)

#### Scenario: Acceso de escritura restringido
- **WHEN** un usuario sin rol `admin` intenta `POST` o `PATCH /api/v1/company`
- **THEN** el sistema responde 403 FORBIDDEN

---

### Requirement: Indicador de completitud
El sistema expone un campo `is_complete` calculado que indica si todos los campos obligatorios están presentes y no vacíos.

#### Scenario: Configuración completa
- **WHEN** `razon_social`, `ruc` y `email` tienen valor
- **THEN** `is_complete = true`

#### Scenario: Configuración incompleta
- **WHEN** alguno de los campos obligatorios está ausente o vacío
- **THEN** `is_complete = false`

---

### Requirement: Registro en auditoría
Cada creación o modificación de la configuración de empresa queda registrada en el log de auditoría.

#### Scenario: Creación
- **WHEN** se llama `POST /api/v1/company` exitosamente
- **THEN** se genera una entrada de auditoría con `action=CREATE`, `entity_type="company_config"`, `entity_id=1`

#### Scenario: Actualización
- **WHEN** se llama `PATCH /api/v1/company` exitosamente
- **THEN** se genera una entrada de auditoría con `action=UPDATE`, `entity_type="company_config"`, `entity_id=1`

---

### Requirement: Banner de advertencia cuando la empresa no está configurada
El sistema SHALL mostrar un banner de advertencia persistente en el layout principal cuando la configuración de empresa está incompleta (`is_complete = false` o no existe), visible para todos los usuarios autenticados.

#### Scenario: Banner para administradores
- **WHEN** el admin accede a cualquier página del panel y `is_complete = false` o la empresa no existe
- **THEN** se muestra un banner amarillo en la zona superior del contenido principal con el texto "Configuración de empresa incompleta" y un enlace "Configurar ahora" que navega a `/admin/company`

#### Scenario: Banner para otros roles
- **WHEN** un operador o supervisor accede al panel y `is_complete = false` o la empresa no existe
- **THEN** se muestra un banner amarillo informativo con el texto "El administrador debe completar la configuración de empresa antes de operar" sin link de acción

#### Scenario: Banner oculto cuando empresa está configurada
- **WHEN** `is_complete = true`
- **THEN** el banner no se muestra y el layout funciona normalmente
