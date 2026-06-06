# Spec: inventory-movements

## Purpose
Gestión de todos los documentos de movimiento de inventario: Ingresos (IN), Egresos (EG), Bajas de Inventario (BI) y Ajustes de Inventario (AI). Controla la trazabilidad de stock con flujos de autorización para operaciones sensibles.

## Requirements

### Requirement: Numeración automática consecutiva por tipo de documento
El sistema SHALL generar automáticamente números de documento consecutivos por tipo y año con formato `{TIPO}-{AAAA}-{NNNNNN}` (ej. `IN-2025-000001`). La numeración SHALL reiniciarse en 1 cada año calendario. La numeración es gestionada con bloqueo optimista para evitar duplicados en concurrencia.

#### Scenario: Primer documento del año
- **WHEN** se crea el primer documento IN del año 2025
- **THEN** el número asignado es `IN-2025-000001`

#### Scenario: Numeración consecutiva
- **WHEN** ya existe `IN-2025-000005` y se crea un nuevo documento IN
- **THEN** el número asignado es `IN-2025-000006`

#### Scenario: Reinicio de numeración en nuevo año
- **WHEN** se crea el primer documento IN del año 2026
- **THEN** el número asignado es `IN-2026-000001`

---

### Requirement: Ingreso de Mercadería (IN)
Un documento de Ingreso SHALL incrementar el stock disponible de los productos incluidos. Cada documento SHALL contener: número automático, fecha, usuario creador, motivo/referencia opcional, y una o más líneas con: `producto_id`, `cantidad` (decimal > 0) y `costo_unitario` (decimal >= 0). El sistema MUST validar que el producto exista y esté activo antes de registrar el ingreso.

#### Scenario: Crear Ingreso con datos válidos
- **WHEN** un Operador crea un documento IN con líneas válidas
- **THEN** el sistema registra el documento, incrementa el `stock_actual` de cada producto en la cantidad indicada y retorna HTTP 201 con el número de documento generado

#### Scenario: Intentar Ingreso con producto inexistente
- **WHEN** un Operador incluye un `producto_id` que no existe en una línea del IN
- **THEN** el sistema retorna HTTP 422 con código `PRODUCT_NOT_FOUND`

#### Scenario: Intentar Ingreso con producto inactivo
- **WHEN** un Operador incluye un producto con estado inactivo en el IN
- **THEN** el sistema retorna HTTP 422 con código `PRODUCT_INACTIVE`

#### Scenario: Ingreso con costo unitario cero
- **WHEN** un Operador crea un IN con `costo_unitario = 0`
- **THEN** el sistema registra el movimiento (donaciones o transferencias sin costo son válidas)

#### Scenario: Ingreso con documento sin líneas
- **WHEN** un Operador intenta crear un IN sin líneas de detalle
- **THEN** el sistema retorna HTTP 422 con código `DOCUMENT_REQUIRES_LINES`

---

### Requirement: Egreso de Mercadería (EG)
Un documento de Egreso SHALL disminuir el stock disponible. Cada línea SHALL contener: `producto_id`, `cantidad` (decimal > 0) y `precio_unitario_venta` (decimal >= 0). El sistema MUST validar que exista stock suficiente para cada producto antes de aprobar la operación. No se permite generar stock negativo.

#### Scenario: Crear Egreso con stock suficiente
- **WHEN** un Operador crea un EG y todos los productos tienen `stock_actual >= cantidad`
- **THEN** el sistema registra el documento, reduce el `stock_actual` de cada producto y retorna HTTP 201

#### Scenario: Intentar Egreso con stock insuficiente
- **WHEN** un Operador incluye en el EG un producto con `cantidad > stock_actual`
- **THEN** el sistema retorna HTTP 422 con código `INSUFFICIENT_STOCK` indicando el producto y stock disponible

#### Scenario: Egreso que deja stock en cero
- **WHEN** un Operador egresa exactamente la cantidad disponible de un producto
- **THEN** el sistema registra el egreso y deja `stock_actual = 0` (no negativo)

---

### Requirement: Baja de Inventario (BI) con flujo de autorización
Una Baja de Inventario registra pérdidas, daños, vencimientos, robos o destrucción. El flujo SHALL ser: (1) Operador crea solicitud BI → estado `pendiente`; (2) Administrador emite código de autorización de un solo uso (válido 15 min); (3) Operador o Administrador confirma con el código → estado `aprobado` y el stock se reduce. La BI pendiente NO afecta el stock.

#### Scenario: Crear solicitud de Baja de Inventario
- **WHEN** un Operador crea una solicitud BI con motivo y líneas de productos
- **THEN** el sistema registra la solicitud con estado `pendiente` y NO modifica el stock

#### Scenario: Administrador genera código de autorización
- **WHEN** un Administrador solicita un código de autorización para una BI pendiente
- **THEN** el sistema genera un código OTP alfanumérico de 8 caracteres, válido por 15 minutos, y lo retorna al Administrador

#### Scenario: Confirmar BI con código válido
- **WHEN** se confirma una BI con el código de autorización correcto y dentro del tiempo de validez
- **THEN** el sistema cambia el estado a `aprobado`, reduce el stock de los productos y registra: solicitante, autorizador, timestamp y motivo

#### Scenario: Intentar confirmar BI con código expirado
- **WHEN** se intenta confirmar una BI con un código que ya expiró o fue usado
- **THEN** el sistema retorna HTTP 422 con código `AUTHORIZATION_CODE_INVALID`

#### Scenario: BI aprobada que generaría stock negativo
- **WHEN** al momento de aprobar una BI el stock actual es menor que la cantidad solicitada
- **THEN** el sistema retorna HTTP 422 con código `INSUFFICIENT_STOCK` y la BI permanece pendiente

---

### Requirement: Ajuste de Inventario (AI) con flujo de autorización
Un Ajuste de Inventario corrige diferencias detectadas en conteos físicos. El ajuste puede ser positivo (incrementa stock) o negativo (reduce stock). El flujo de autorización SHALL ser idéntico al de la Baja de Inventario. Cada línea SHALL indicar el `tipo_ajuste` (`incremento` o `decremento`), `producto_id`, `cantidad` y `motivo`.

#### Scenario: Crear solicitud de Ajuste de Inventario
- **WHEN** un Operador crea una solicitud AI
- **THEN** el sistema la registra con estado `pendiente` y NO modifica el stock

#### Scenario: Aprobar Ajuste positivo
- **WHEN** se aprueba un AI de tipo `incremento` con código de autorización válido
- **THEN** el sistema incrementa el `stock_actual` del producto en la cantidad indicada

#### Scenario: Aprobar Ajuste negativo
- **WHEN** se aprueba un AI de tipo `decremento` con código de autorización válido y stock suficiente
- **THEN** el sistema reduce el `stock_actual` del producto en la cantidad indicada

#### Scenario: Ajuste negativo que generaría stock negativo
- **WHEN** al aprobar un AI de decremento el stock actual es insuficiente
- **THEN** el sistema retorna HTTP 422 con código `INSUFFICIENT_STOCK`

---

### Requirement: Inmutabilidad de documentos aprobados
Los documentos de inventario en estado `aprobado` SHALL ser inmutables. No se podrán editar ni eliminar. Solo se permiten consultas. Cualquier corrección MUST realizarse mediante un nuevo documento compensatorio.

#### Scenario: Intento de editar documento aprobado
- **WHEN** cualquier usuario intenta modificar un documento con estado `aprobado`
- **THEN** el sistema retorna HTTP 409 con código `DOCUMENT_IS_IMMUTABLE`

#### Scenario: Cancelar documento pendiente
- **WHEN** un Administrador u Operador (quien lo creó) cancela una solicitud BI/AI en estado `pendiente`
- **THEN** el sistema cambia el estado a `cancelado` sin afectar el stock

---

### Requirement: Consulta de movimientos con filtros
El sistema SHALL permitir consultar el historial de documentos de inventario con filtros por: tipo de documento, rango de fechas, producto, usuario creador y estado. Todos los listados MUST estar paginados.

#### Scenario: Filtrar movimientos por tipo y rango de fechas
- **WHEN** un usuario filtra movimientos IN entre dos fechas
- **THEN** el sistema retorna los documentos IN dentro del rango con paginación

#### Scenario: Consultar detalle de un documento
- **WHEN** un usuario solicita el detalle de un documento por su número
- **THEN** el sistema retorna el documento completo con todas sus líneas, estado, historial de autorización y metadatos de auditoría
