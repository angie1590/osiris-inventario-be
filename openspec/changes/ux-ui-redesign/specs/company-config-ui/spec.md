## MODIFIED Requirements

### Requirement: Formulario con campos de empresa
El formulario SHALL incluir los siguientes campos: razón social (obligatorio), RUC (obligatorio), email (obligatorio), nombre comercial (opcional), dirección (opcional), teléfono (opcional), logo (opcional). Todos los campos obligatorios deben mostrar el indicador `*` junto a su etiqueta, y el formulario debe incluir la nota "Los campos marcados con * son obligatorios". Los errores de validación deben mostrarse inline debajo de cada campo afectado, siguiendo el spec `ux-validation`. El error genérico "Error al guardar la configuración" queda prohibido.

#### Scenario: Validación de campos obligatorios
- **WHEN** el usuario intenta guardar sin completar razón social, RUC o email
- **THEN** el formulario muestra mensajes de error inline específicos debajo de cada campo vacío (e.g., "La razón social es obligatoria") y no envía la solicitud al API

#### Scenario: Error de backend mapeado a campo
- **WHEN** el backend responde con `errors: { "ruc": "El RUC debe tener 13 dígitos." }`
- **THEN** el campo RUC muestra borde rojo y el mensaje específico debajo del campo; además se muestra un banner de error general al tope del formulario

#### Scenario: Sin toasts duplicados
- **WHEN** el usuario hace clic en Guardar múltiples veces antes de que responda la API
- **THEN** solo un toast aparece para ese intento; no se acumulan toasts idénticos

#### Scenario: Guardado exitoso — creación
- **WHEN** no existe configuración y el admin completa los campos requeridos y presiona "Guardar"
- **THEN** se envía `POST /api/v1/company`, se muestra toast "Configuración guardada" y el formulario pasa a modo edición

#### Scenario: Guardado exitoso — actualización
- **WHEN** ya existe configuración y el admin modifica campos y presiona "Actualizar"
- **THEN** se envía `PATCH /api/v1/company` con solo los campos modificados, se muestra toast "Configuración actualizada"
