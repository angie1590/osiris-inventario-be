## ADDED Requirements

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
