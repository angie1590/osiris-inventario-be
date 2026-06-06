## ADDED Requirements

### Requirement: Página de administración de empresa
El sistema SHALL proveer una página `/admin/company` accesible solo a usuarios con rol `admin` que permita crear o editar la configuración de empresa.

#### Scenario: Acceso a la página sin configuración previa
- **WHEN** un admin navega a `/admin/company` y no existe configuración de empresa
- **THEN** la página muestra un formulario vacío con todos los campos y un botón "Guardar"

#### Scenario: Acceso a la página con configuración existente
- **WHEN** un admin navega a `/admin/company` y ya existe configuración de empresa
- **THEN** la página muestra los valores actuales precargados en el formulario y el botón muestra "Actualizar"

#### Scenario: Acceso denegado a no-admins
- **WHEN** un usuario sin rol `admin` intenta navegar a `/admin/company`
- **THEN** es redirigido a `/403`

---

### Requirement: Formulario con campos de empresa
El formulario SHALL incluir los siguientes campos: razón social (obligatorio), RUC (obligatorio), email (obligatorio), nombre comercial (opcional), dirección (opcional), teléfono (opcional), logo (opcional).

#### Scenario: Validación de campos obligatorios
- **WHEN** el usuario intenta guardar sin completar razón social, RUC o email
- **THEN** el formulario muestra mensajes de error inline y no envía la solicitud al API

#### Scenario: Guardado exitoso — creación
- **WHEN** no existe configuración y el admin completa los campos requeridos y presiona "Guardar"
- **THEN** se envía `POST /api/v1/company`, se muestra toast "Configuración guardada" y el formulario pasa a modo edición

#### Scenario: Guardado exitoso — actualización
- **WHEN** ya existe configuración y el admin modifica campos y presiona "Actualizar"
- **THEN** se envía `PATCH /api/v1/company` con solo los campos modificados, se muestra toast "Configuración actualizada"

---

### Requirement: Subida de logo
El formulario SHALL permitir cargar el logo de la empresa como archivo local (base64) o como URL directa, a elección del usuario.

#### Scenario: Subida de archivo local válido
- **WHEN** el usuario selecciona un archivo de imagen ≤ 2 MB en el tab "Subir archivo"
- **THEN** el archivo se lee como base64 y se almacena en el campo logo; se muestra una vista previa del logo

#### Scenario: Archivo demasiado grande
- **WHEN** el usuario selecciona un archivo de imagen > 2 MB
- **THEN** se muestra un mensaje de error "El logo no puede superar 2 MB" y no se actualiza el campo

#### Scenario: URL directa
- **WHEN** el usuario ingresa una URL en el tab "URL directa" y guarda
- **THEN** el valor de la URL se envía como campo logo

#### Scenario: Logo existente
- **WHEN** existe una configuración con logo y el admin abre la página
- **THEN** se muestra una vista previa del logo actual junto al campo de carga

---

### Requirement: Ítem de navegación "Empresa" en el sidebar
El sidebar SHALL mostrar el ítem "Empresa" apuntando a `/admin/company` solo para usuarios con rol `admin`.

#### Scenario: Visibilidad del ítem
- **WHEN** el usuario autenticado tiene rol `admin`
- **THEN** el ítem "Empresa" aparece en el sidebar entre "Parámetros" y el final de la lista

#### Scenario: Ocultamiento para otros roles
- **WHEN** el usuario tiene rol `operator` o `supervisor`
- **THEN** el ítem "Empresa" no aparece en el sidebar
