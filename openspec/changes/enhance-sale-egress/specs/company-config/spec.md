## ADDED Requirements

### Requirement: Catálogos configurables de ventas

La configuración singleton de empresa SHALL incluir formas de pago y bancos administrables por nombre y estado activo.

#### Scenario: Defaults compatibles

- **WHEN** se crea o lee una configuración sin catálogos de venta definidos
- **THEN** devuelve `Efectivo` y `Transferencia` como formas activas, con `Efectivo` por defecto, y conserva una lista de bancos configurable

#### Scenario: CRUD administrativo

- **WHEN** un administrador agrega, edita, activa o desactiva una forma de pago o banco
- **THEN** el cambio queda persistido en la configuración y auditado como actualización de empresa

#### Scenario: Restricción de rol

- **WHEN** un usuario que no es administrador intenta cambiar estos catálogos
- **THEN** el sistema rechaza la operación con 403
