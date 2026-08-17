## ADDED Requirements

### Requirement: Cobro de venta

Una venta SHALL permitir seleccionar forma de pago y, cuando corresponda, banco, valor recibido y cambio.

#### Scenario: Efectivo sin valor recibido

- **WHEN** la forma de pago es `Efectivo` y el valor recibido está vacío
- **THEN** el valor recibido se interpreta como el total de la factura y el cambio es cero

#### Scenario: Recibido mayor al total

- **WHEN** el valor recibido es mayor o igual al total de la factura
- **THEN** el sistema calcula y muestra el cambio como recibido menos total

#### Scenario: Recibido menor al total

- **WHEN** el valor recibido es menor al total de la factura
- **THEN** no permite guardar, muestra una advertencia de validación y comunica el valor faltante

#### Scenario: Transferencia

- **WHEN** la forma de pago es `Transferencia`
- **THEN** el banco es obligatorio y los campos de efectivo se completan sin exigir un valor recibido manual

### Requirement: Resumen de venta

El resumen SHALL mostrar por separado cantidad de líneas, suma de cantidades, total monetario, valor recibido y cambio.

#### Scenario: Líneas con cantidades diferentes

- **WHEN** existen dos líneas con cantidades 1 y 3
- **THEN** total de ítems es 2 y total de productos es 4

### Requirement: Carga rápida de productos

El editor SHALL enfocar el buscador de cada nueva línea y agregar automáticamente una coincidencia exacta leída por código.

#### Scenario: Lector encuentra código exacto

- **WHEN** el lector escribe un código de barras o interno exacto y envía Enter
- **THEN** se agrega el producto con cantidad 1, se incrementa si ya existe, y el foco queda en el buscador de la siguiente línea

#### Scenario: Búsqueda no exacta

- **WHEN** el texto coincide solo por nombre o con más de un resultado
- **THEN** el usuario debe seleccionar un resultado de la lista

### Requirement: Presentación de línea y stock

La tabla SHALL mostrar una columna de código y el stock con el formato configurado.

#### Scenario: Código habilitado

- **WHEN** el parámetro habilita código de barras o código interno
- **THEN** la columna única muestra el código correspondiente de cada producto

#### Scenario: Stock decimal

- **WHEN** el modo de stock es decimal
- **THEN** stock y cantidades aceptan y muestran decimales; en modo entero no se muestran fracciones

### Requirement: Vendedor en venta

La ventana de productos de una venta SHALL mostrar el vendedor seleccionado en lugar del usuario.

#### Scenario: Venta con vendedor

- **WHEN** se abre la ventana de productos desde una venta
- **THEN** se muestra el vendedor de la venta
