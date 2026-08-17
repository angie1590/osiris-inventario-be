## ADDED Requirements

### Requirement: Administración de formas de pago

La configuración de empresa SHALL permitir al administrador agregar, editar, activar y desactivar formas de pago.

#### Scenario: Forma de pago por defecto

- **WHEN** se crea o no existe una configuración de formas de pago
- **THEN** el sistema dispone de `Efectivo` activo y `Transferencia` activa, con `Efectivo` como opción predeterminada

#### Scenario: Administrador modifica formas de pago

- **WHEN** un administrador agrega, edita, activa o desactiva una forma de pago
- **THEN** la configuración se guarda y las ventas solo ofrecen las formas activas

#### Scenario: Usuario no administrador modifica formas de pago

- **WHEN** un usuario sin rol administrador intenta modificar las formas de pago
- **THEN** el sistema responde 403

### Requirement: Administración de bancos

La configuración de empresa SHALL permitir al administrador agregar, editar, activar y desactivar bancos.

#### Scenario: Banco para transferencia

- **WHEN** el usuario selecciona `Transferencia` en una venta
- **THEN** el formulario muestra un combo con los bancos activos y exige seleccionar uno

#### Scenario: Banco desactivado

- **WHEN** un banco se desactiva
- **THEN** deja de ofrecerse en nuevas ventas, pero el nombre guardado en ventas anteriores permanece visible
