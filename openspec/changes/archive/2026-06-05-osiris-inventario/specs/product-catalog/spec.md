## ADDED Requirements

### Requirement: Categorías jerárquicas ilimitadas
El sistema SHALL permitir organizar productos en categorías que pueden tener subcategorías anidadas sin límite de profundidad. Cada categoría SHALL tener: nombre, descripción y referencia a su categoría padre (nullable para categorías raíz).

#### Scenario: Crear categoría raíz
- **WHEN** un Administrador/Operador crea una categoría sin categoría padre
- **THEN** el sistema la registra como categoría raíz con HTTP 201

#### Scenario: Crear subcategoría
- **WHEN** un Administrador/Operador crea una categoría con una categoría padre existente
- **THEN** el sistema la registra como hija de la categoría padre especificada

#### Scenario: Eliminar categoría con subcategorías
- **WHEN** un Administrador intenta eliminar una categoría que tiene subcategorías activas
- **THEN** el sistema retorna HTTP 409 con código `CATEGORY_HAS_CHILDREN`

#### Scenario: Eliminar categoría con productos asignados
- **WHEN** un Administrador intenta eliminar una categoría que tiene productos asignados
- **THEN** el sistema retorna HTTP 409 con código `CATEGORY_HAS_PRODUCTS`

---

### Requirement: Atributos personalizados en categorías
Cada categoría SHALL poder definir atributos personalizados con nombre, tipo de dato y flag de obligatoriedad. Los tipos soportados MUST incluir: `text`, `integer`, `decimal`, `date`, `boolean`, `select` (lista de opciones). El tipo `select` MUST tener al menos una opción definida.

#### Scenario: Agregar atributo de tipo texto a una categoría
- **WHEN** un Administrador agrega un atributo tipo `text` llamado "Marca" a una categoría
- **THEN** todos los productos en esa categoría y sus subcategorías deben incluir ese atributo

#### Scenario: Agregar atributo de tipo select
- **WHEN** un Administrador agrega un atributo tipo `select` con opciones definidas
- **THEN** los productos solo pueden asignar valores que estén en la lista de opciones del atributo

#### Scenario: Intentar crear atributo select sin opciones
- **WHEN** un Administrador intenta crear un atributo tipo `select` sin opciones
- **THEN** el sistema retorna HTTP 422 con código `SELECT_REQUIRES_OPTIONS`

---

### Requirement: Herencia de atributos de categorías padre
Los atributos definidos en una categoría padre SHALL heredarse automáticamente por todas las categorías hijas y por todos los productos de la cadena de herencia. No se permitirán atributos con el mismo nombre en una cadena de herencia (ni en la misma categoría ni heredados).

#### Scenario: Producto hereda atributos de su categoría y categorías ancestras
- **WHEN** un producto es asignado a una categoría hija
- **THEN** el producto debe incluir los atributos de esa categoría más todos los atributos de sus categorías ancestras

#### Scenario: Intentar agregar atributo duplicado en cadena de herencia
- **WHEN** un Administrador intenta agregar un atributo con el mismo nombre que uno ya existente en la cadena de herencia de esa categoría
- **THEN** el sistema retorna HTTP 409 con código `DUPLICATE_ATTRIBUTE_IN_HIERARCHY`

---

### Requirement: Campos base obligatorios de productos
Cada producto SHALL tener los siguientes campos base obligatorios: `nombre`, `descripcion`, `categoria_id`, `stock_minimo` (decimal >= 0), `stock_actual` (decimal, solo lectura vía API), `estado` (activo/inactivo), `pvp` (precio de venta al público, decimal >= 0). Adicionalmente, el producto almacena los valores de los atributos heredados de su categoría.

#### Scenario: Crear producto con todos los campos base
- **WHEN** un Operador envía todos los campos base requeridos y los atributos de la categoría
- **THEN** el sistema crea el producto con `stock_actual = 0` y retorna HTTP 201

#### Scenario: Crear producto sin campo obligatorio
- **WHEN** un Operador intenta crear un producto sin alguno de los campos base obligatorios
- **THEN** el sistema retorna HTTP 422 indicando el campo faltante

#### Scenario: Crear producto con atributo obligatorio faltante de su categoría
- **WHEN** un Operador crea un producto en una categoría con atributos obligatorios pero no proporciona todos
- **THEN** el sistema retorna HTTP 422 indicando el atributo faltante

---

### Requirement: Stock actual no modificable directamente
El campo `stock_actual` de un producto SHALL ser de solo lectura a través de todos los endpoints de creación y edición de productos. El sistema MUST rechazar cualquier intento de establecer o modificar `stock_actual` directamente. El valor solo puede cambiar a través de transacciones de inventario autorizadas.

#### Scenario: Intento de modificar stock_actual al crear producto
- **WHEN** un cliente incluye el campo `stock_actual` en el payload de creación de producto
- **THEN** el sistema ignora el valor y crea el producto con `stock_actual = 0`

#### Scenario: Intento de modificar stock_actual al editar producto
- **WHEN** un cliente incluye el campo `stock_actual` en el payload de edición de producto
- **THEN** el sistema ignora el campo `stock_actual` y procesa los demás cambios normalmente

---

### Requirement: Alerta de stock mínimo
El sistema SHALL identificar productos cuyo `stock_actual` sea menor o igual a `stock_minimo` y SHALL incluir esta información en el estado del producto y en los reportes correspondientes.

#### Scenario: Producto alcanza stock mínimo
- **WHEN** una transacción reduce el stock de un producto a un valor igual o menor a su `stock_minimo`
- **THEN** el sistema marca el producto con `bajo_stock = true` en la respuesta de la API

#### Scenario: Consulta de productos bajo stock mínimo
- **WHEN** un usuario consulta el listado de productos bajo stock mínimo
- **THEN** el sistema retorna únicamente los productos activos con `stock_actual <= stock_minimo`

---

### Requirement: Búsqueda y filtrado de productos
El sistema SHALL permitir buscar productos por nombre, código, categoría y estado. Todos los listados MUST estar paginados con keyset pagination.

#### Scenario: Búsqueda por nombre parcial
- **WHEN** un usuario busca productos con el término "tornillo"
- **THEN** el sistema retorna todos los productos activos e inactivos cuyo nombre contiene "tornillo" (case-insensitive)

#### Scenario: Filtrado por categoría (incluyendo subcategorías)
- **WHEN** un usuario filtra productos por una categoría padre
- **THEN** el sistema retorna productos de esa categoría y de todas sus subcategorías descendientes

#### Scenario: Listado paginado de productos
- **WHEN** un usuario solicita el listado de productos con `limit=50`
- **THEN** el sistema retorna máximo 50 productos con cursor para la siguiente página
