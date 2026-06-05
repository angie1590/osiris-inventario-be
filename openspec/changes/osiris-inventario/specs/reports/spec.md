## ADDED Requirements

### Requirement: Reportes operativos de movimientos
El sistema SHALL generar reportes de: ingresos de mercadería, egresos de mercadería, bajas de inventario y ajustes de inventario. Cada reporte SHALL incluir filtros por: rango de fechas (obligatorio), categoría, producto, usuario creador y estado del documento. Los resultados SHALL estar paginados y ordenados cronológicamente.

#### Scenario: Reporte de ingresos en rango de fechas
- **WHEN** un Supervisor/Administrador solicita el reporte de IN entre dos fechas
- **THEN** el sistema retorna todos los documentos IN del período con número, fecha, usuario, total de líneas y valor total

#### Scenario: Reporte filtrado por producto y rango de fechas
- **WHEN** un usuario filtra el reporte de EG por un producto específico y rango de fechas
- **THEN** el sistema retorna únicamente los egresos que incluyen ese producto en el período

#### Scenario: Reporte con filtros que no tienen resultados
- **WHEN** los filtros aplicados no corresponden a ningún documento
- **THEN** el sistema retorna lista vacía con HTTP 200

---

### Requirement: Reporte de stock actual
El sistema SHALL generar un reporte de stock actual que muestre todos los productos activos con su `stock_actual`, `stock_minimo`, estado de stock (bajo/normal) y `pvp`. Deberá permitir filtrar por categoría, rango de stock y estado de stock.

#### Scenario: Reporte de stock actual de todos los productos
- **WHEN** un usuario solicita el reporte de stock sin filtros
- **THEN** el sistema retorna todos los productos activos con sus valores de stock actuales

#### Scenario: Filtrar reporte por productos bajo stock mínimo
- **WHEN** un usuario filtra por estado `bajo_stock`
- **THEN** el sistema retorna únicamente los productos con `stock_actual <= stock_minimo`

---

### Requirement: Reporte de inventario valorizado
El sistema SHALL generar un reporte de inventario valorizado que muestre por producto: `stock_actual`, costo promedio o costo PEPS según método activo, valor total en inventario (stock × costo). El reporte SHALL incluir totales por categoría y total general.

#### Scenario: Inventario valorizado completo
- **WHEN** un Supervisor/Administrador solicita el reporte de inventario valorizado
- **THEN** el sistema retorna todos los productos activos con stock y su valorización, subtotales por categoría y total general

#### Scenario: Inventario valorizado a una fecha específica
- **WHEN** un usuario solicita el inventario valorizado con fecha de corte
- **THEN** el sistema calcula la valorización considerando el estado del inventario en esa fecha

---

### Requirement: Reporte de movimientos por usuario
El sistema SHALL generar un reporte que consolide todos los movimientos registrados por un usuario específico en un rango de fechas, agrupados por tipo de documento.

#### Scenario: Movimientos de un operador en el mes
- **WHEN** un Administrador solicita los movimientos del operador "usuario01" en el mes actual
- **THEN** el sistema retorna todos los IN, EG, BI y AI registrados por ese usuario en el período

---

### Requirement: Reporte de Kardex por producto
El sistema SHALL exponer el Kardex de un producto como reporte, con las mismas capacidades de filtrado por fecha y exportación que los demás reportes.

#### Scenario: Exportar Kardex de un producto a Excel
- **WHEN** un Supervisor solicita la exportación del Kardex de un producto a Excel
- **THEN** el sistema genera un archivo .xlsx con todas las entradas del Kardex en el período solicitado

---

### Requirement: Reporte consolidado general de inventario
El sistema SHALL generar un reporte consolidado que muestre un resumen ejecutivo del estado del inventario: total de productos, total valorizado, productos bajo mínimo, movimientos del período, entradas vs salidas en unidades y valor.

#### Scenario: Consolidado del período actual
- **WHEN** un Supervisor/Administrador solicita el consolidado del mes actual
- **THEN** el sistema retorna métricas resumidas del inventario para el período

---

### Requirement: Exportación de reportes a PDF y Excel
Todos los reportes SHALL poder exportarse a formato PDF y Excel (.xlsx). El PDF SHALL incluir encabezado con nombre del reporte, rango de fechas, fecha de generación y usuario que lo generó. El Excel SHALL incluir los datos en formato tabular listo para análisis.

#### Scenario: Exportar reporte de ingresos a PDF
- **WHEN** un usuario solicita la exportación del reporte de IN a PDF
- **THEN** el sistema genera un archivo PDF con encabezado y datos tabulares y retorna el archivo para descarga

#### Scenario: Exportar reporte de stock a Excel
- **WHEN** un usuario solicita la exportación del reporte de stock a Excel
- **THEN** el sistema genera un archivo .xlsx con los datos del reporte en la hoja activa y retorna el archivo para descarga

#### Scenario: Exportación de reporte grande
- **WHEN** se solicita la exportación de un reporte con más de 10.000 registros
- **THEN** el sistema genera el archivo completo (sin límite de paginación en la exportación) con todos los registros

---

### Requirement: Filtros comunes en todos los reportes
Todos los reportes SHALL soportar como mínimo los siguientes filtros: `fecha_inicio` y `fecha_fin` (obligatorios), `categoria_id` (opcional), `producto_id` (opcional), `usuario_id` (opcional). Los filtros de fecha SHALL ser inclusivos en ambos extremos.

#### Scenario: Reporte con fecha_inicio mayor a fecha_fin
- **WHEN** un usuario envía `fecha_inicio > fecha_fin`
- **THEN** el sistema retorna HTTP 422 con código `INVALID_DATE_RANGE`

#### Scenario: Reporte sin fechas obligatorias
- **WHEN** un usuario solicita un reporte sin incluir el rango de fechas
- **THEN** el sistema retorna HTTP 422 indicando que `fecha_inicio` y `fecha_fin` son obligatorios
