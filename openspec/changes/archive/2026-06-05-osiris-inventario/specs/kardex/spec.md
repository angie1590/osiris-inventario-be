## ADDED Requirements

### Requirement: Método de valoración configurable
El sistema SHALL soportar dos métodos de valoración de inventario: `PEPS` (Primero en Entrar, Primero en Salir / FIFO) y `Promedio Ponderado`. El método activo SHALL configurarse como parámetro del sistema desde la interfaz de Administrador. Solo un método puede estar activo a la vez. El método SHALL aplicarse a todos los productos del sistema sin excepción.

#### Scenario: Configurar método Promedio Ponderado
- **WHEN** un Administrador cambia el parámetro `kardex_method` a `weighted_average`
- **THEN** todos los movimientos nuevos se valorizan usando Promedio Ponderado

#### Scenario: Intento de cambio de método con movimientos en el ejercicio actual
- **WHEN** un Administrador intenta cambiar el método con documentos registrados en el ejercicio contable actual
- **THEN** el sistema retorna HTTP 409 con código `KARDEX_METHOD_LOCKED` y descripción de que el cambio solo aplica a inicio de ejercicio

---

### Requirement: Registro de Kardex por producto
El sistema SHALL mantener un registro Kardex por producto con una entrada por cada movimiento que afecte el stock. Cada entrada SHALL contener: `fecha`, `numero_documento`, `tipo_movimiento`, `cantidad_entrada`, `costo_unitario_entrada`, `cantidad_salida`, `costo_unitario_salida`, `saldo_cantidad`, `saldo_valor_total`, `costo_promedio_actual` (para Promedio Ponderado) y `lote_id` (para PEPS).

#### Scenario: Registro de entrada en Kardex
- **WHEN** se aprueba un documento IN para un producto
- **THEN** el sistema crea una entrada de Kardex con `cantidad_entrada`, `costo_unitario_entrada`, actualiza `saldo_cantidad` y `saldo_valor_total`

#### Scenario: Registro de salida en Kardex
- **WHEN** se aprueba un documento EG para un producto
- **THEN** el sistema crea una entrada de Kardex con `cantidad_salida`, `costo_unitario_salida` (calculado según método activo), actualiza `saldo_cantidad` y `saldo_valor_total`

---

### Requirement: Cálculo PEPS/FIFO
Con método PEPS, las salidas de inventario SHALL valorarse al costo del lote más antiguo disponible. Si una salida consume múltiples lotes, el sistema MUST desglosar el costo proporcionalmente entre los lotes consumidos. Los lotes se crean con cada documento IN y se identifican por fecha y número de documento.

#### Scenario: Salida consume un solo lote PEPS
- **WHEN** existe un solo lote con stock suficiente y se registra un EG
- **THEN** el costo de salida es el costo unitario del lote más antiguo

#### Scenario: Salida consume múltiples lotes PEPS
- **WHEN** la cantidad del EG supera el stock del lote más antiguo y hay lotes más nuevos disponibles
- **THEN** el sistema consume primero el lote más antiguo completo y luego continúa con el siguiente, generando múltiples entradas de Kardex si es necesario

#### Scenario: Consulta de lotes disponibles PEPS
- **WHEN** se consulta el Kardex de un producto con método PEPS
- **THEN** el sistema muestra los lotes disponibles ordenados de más antiguo a más reciente con cantidad y costo por lote

---

### Requirement: Cálculo Promedio Ponderado
Con método Promedio Ponderado, cada entrada (IN) SHALL recalcular el costo promedio ponderado acumulado. El nuevo costo promedio = (saldo_valor_anterior + valor_entrada) / (saldo_cantidad_anterior + cantidad_entrada). Las salidas (EG, BI, AI negativo) se valorizan al costo promedio vigente al momento de la operación.

#### Scenario: Cálculo de nuevo promedio ponderado tras Ingreso
- **WHEN** se registra un IN con costo unitario diferente al costo promedio actual
- **THEN** el sistema recalcula el costo promedio ponderado con la fórmula correcta y lo registra en el Kardex

#### Scenario: Salida valorizada al promedio actual
- **WHEN** se registra un EG con método Promedio Ponderado
- **THEN** el costo de salida unitario es el costo promedio ponderado vigente en ese momento

#### Scenario: Costo promedio con saldo cero
- **WHEN** el saldo de un producto llega a cero y se registra un nuevo Ingreso
- **THEN** el costo promedio ponderado se reinicia al costo unitario del nuevo Ingreso

---

### Requirement: Consulta de Kardex por producto
El sistema SHALL permitir consultar el Kardex completo de un producto con filtros por rango de fechas. La consulta SHALL retornar todas las entradas del Kardex en orden cronológico con saldos acumulados, el método de valoración aplicado y el resumen de valorización total.

#### Scenario: Consulta de Kardex en rango de fechas
- **WHEN** un usuario consulta el Kardex de un producto entre dos fechas
- **THEN** el sistema retorna todas las entradas del período con saldos iniciales del período y saldos finales

#### Scenario: Kardex vacío para producto sin movimientos
- **WHEN** un usuario consulta el Kardex de un producto que no tiene movimientos
- **THEN** el sistema retorna lista vacía con saldo inicial y final en cero

---

### Requirement: Reproducibilidad y auditabilidad del Kardex
Todos los cálculos del Kardex SHALL ser reproducibles: dado el mismo conjunto de movimientos en el mismo orden, el Kardex siempre producirá los mismos valores. El sistema SHALL almacenar el costo calculado en el momento de cada transacción para garantizar que el historial no cambie retroactivamente.

#### Scenario: Recálculo de Kardex produce mismo resultado
- **WHEN** el sistema recalcula el Kardex de un producto desde el inicio
- **THEN** el resultado es idéntico al Kardex almacenado

#### Scenario: Kardex histórico no cambia al cambiar parámetros
- **WHEN** se cambia el método de Kardex al inicio de un nuevo ejercicio
- **THEN** las entradas del Kardex del ejercicio anterior no se modifican
