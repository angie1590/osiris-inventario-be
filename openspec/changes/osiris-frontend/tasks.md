## 1. Scaffolding y configuración base

- [x] 1.1 Crear proyecto con `npm create vite@latest osiris-inventario-fe -- --template react-ts` en la carpeta hermana del backend
- [x] 1.2 Instalar dependencias: `tailwindcss`, `@tailwindcss/vite`, `shadcn/ui` (CLI), React Router v6, Axios, TanStack Query v5, React Hook Form, Zod, Recharts, `lucide-react`, `date-fns`
- [x] 1.3 Configurar Tailwind CSS (`tailwind.config.ts`, `globals.css`)
- [x] 1.4 Inicializar shadcn/ui (`npx shadcn@latest init`) y agregar componentes base: Button, Input, Label, Card, Badge, Dialog, DropdownMenu, Table, Select, Checkbox, Tabs, Toaster
- [x] 1.5 Configurar proxy Vite (`vite.config.ts`): redirigir `/api` → `http://localhost:8000`
- [x] 1.6 Crear `src/lib/api.ts`: instancia Axios con base URL `/api/v1`, interceptor de request (Bearer token) e interceptor de response (refresh en 401 con mutex para evitar race conditions)
- [x] 1.7 Crear `src/types/api.ts` con todos los tipos TypeScript de respuesta del backend: User, Category, CategoryAttribute, Product, InventoryDocument, InventoryDocumentLine, KardexEntry, AuditLog, SystemParam, y sus enums
- [x] 1.8 Configurar TanStack Query (`QueryClient` con defaults: staleTime 30s, retry 1) y envolver `App` con `QueryClientProvider`

## 2. Shell, routing y layout

- [x] 2.1 Configurar `BrowserRouter` con estructura de rutas anidadas: layout de auth (`/login`, `/change-password`) y layout de app con sidebar
- [x] 2.2 Crear `ProtectedRoute` component que verifica autenticación y redirige a `/login` si no hay token
- [x] 2.3 Crear `RoleGuard` component que verifica rol mínimo requerido y muestra página 403 si no cumple
- [x] 2.4 Crear `AppLayout` con sidebar colapsable y top bar (nombre de usuario, rol, botón logout)
- [x] 2.5 Crear `Sidebar` con ítems de navegación filtrados por rol usando `useAuth()`
- [x] 2.6 Crear página 403 "Sin acceso" y página 404 "No encontrado"
- [x] 2.7 Conectar logout button al endpoint `POST /api/v1/auth/logout` y limpiar tokens + redirigir a `/login`

## 3. Autenticación

- [x] 3.1 Crear `AuthContext` con estado: `user | null`, funciones `login()`, `logout()`, `refreshToken()`; access token en variable de módulo, refresh en localStorage
- [x] 3.2 Crear página `/login` con form (React Hook Form + Zod), llamar `POST /api/v1/auth/login`, almacenar tokens y redirigir
- [x] 3.3 Manejar errores de login: credenciales inválidas (toast), cuenta inactiva (toast), y errores de red
- [x] 3.4 Detectar `must_change_password: true` tras login y redirigir a `/change-password`
- [x] 3.5 Crear página `/change-password` con validación de contraseña actual, nueva contraseña y confirmación (Zod); llamar `POST /api/v1/auth/change-password`
- [x] 3.6 Implementar inactivity timer: contador regresivo basado en `ACCESS_TOKEN_EXPIRE_MINUTES`, modal de advertencia a los 2 minutos del vencimiento, y logout automático al expirar
- [x] 3.7 Manejar `SESSION_EXPIRED` del backend (401) con toast y redirect a login

## 4. Catálogo — Categorías

- [x] 4.1 Crear hook `useCategories()` con TanStack Query para `GET /api/v1/categories` (lista paginada con cursor)
- [x] 4.2 Crear página `/categories` con árbol de categorías colapsable (componente recursivo `CategoryTreeNode`)
- [x] 4.3 Crear `CategoryFormModal` (crear y editar) con campos: nombre, descripción, categoría padre (select opcional); llamar POST/PATCH según modo
- [x] 4.4 Implementar delete de categoría con confirmación dialog; manejar error "tiene subcategorías activas"
- [x] 4.5 Crear subpágina de atributos por categoría: listar atributos propios + heredados (con badge "Heredado"), con la distinción visual de no editables para los heredados
- [x] 4.6 Crear `AttributeFormModal`: campos nombre, tipo de dato (select enum), is_required (checkbox), select_options (textarea para tipo `select`)
- [x] 4.7 Implementar delete de atributo con confirmación

## 5. Catálogo — Productos

- [x] 5.1 Crear hook `useProducts()` con filtros: nombre, category_id, status, bajo_stock
- [x] 5.2 Crear página `/products` con tabla paginada (cursor), barra de filtros (nombre, categoría, estado, bajo_stock toggle)
- [x] 5.3 Crear `ProductFormModal` para crear y editar: campos base + atributos dinámicos según categoría seleccionada (render diferente por tipo de dato: text, integer, decimal, date, boolean/checkbox, select/dropdown)
- [x] 5.4 Mostrar `stock_actual` como campo de solo lectura en el form de edición
- [x] 5.5 Implementar toggle de estado (activo/inactivo) con confirmación dialog
- [x] 5.6 Crear página `/products/:id` con detalle completo: stock, badge bajo stock, atributos, link al Kardex del producto

## 6. Movimientos de inventario — Ingresos y Egresos

- [x] 6.1 Crear componente `DocumentLinesEditor`: tabla editable con filas dinámicas (add/remove), columnas: producto (combobox con búsqueda), cantidad, costo unitario (opcional según tipo de documento)
- [x] 6.2 Crear página `/inventory/ingresos/new` con `DocumentLinesEditor` y campos de cabecera: referencia, notas; llamar `POST /api/v1/inventory/ingresos`
- [x] 6.3 Crear página `/inventory/egresos/new` igual a ingresos pero sin campo unit_cost
- [x] 6.4 Crear página `/inventory/ingresos` con tabla paginada, filtros (fecha desde/hasta, producto) y links a detalle
- [x] 6.5 Crear página `/inventory/egresos` con tabla paginada idéntica en estructura
- [x] 6.6 Crear página de detalle `/inventory/ingresos/:id` y `/inventory/egresos/:id` mostrando cabecera + tabla de líneas
- [x] 6.7 Manejar errores: `INSUFFICIENT_STOCK` (toast en la línea afectada), `PRODUCT_NOT_FOUND` (toast), errores genéricos

## 7. Movimientos de inventario — Bajas y Ajustes

- [x] 7.1 Crear página `/inventory/bajas/new` con `DocumentLinesEditor` (sin costo), campo notas, y ajuste de tipo; llamar `POST /api/v1/inventory/bajas`
- [x] 7.2 Crear página `/inventory/ajustes/new` con campo adicional `adjust_type` (increment/decrement toggle)
- [x] 7.3 Crear páginas de lista `/inventory/bajas` y `/inventory/ajustes` con filtro de estado (pending/approved/cancelled)
- [x] 7.4 Crear página de detalle `/inventory/bajas/:id` y `/inventory/ajustes/:id` con acciones contextuales según estado y rol
- [x] 7.5 Implementar botón "Generar código OTP" (solo Admin, solo en estado pending): llamar `POST authorization-code`, mostrar modal con el código en texto grande para copiar
- [x] 7.6 Implementar formulario de aprobación: campo OTP + botón "Aprobar"; llamar `POST approve`; manejar `AUTHORIZATION_CODE_INVALID` con mensaje claro
- [x] 7.7 Implementar botón "Cancelar" (solo en estado pending) con dialog de confirmación

## 8. Kardex

- [x] 8.1 Crear hook `useKardex(productId, dateFrom?, dateTo?)` con TanStack Query para `GET /api/v1/kardex/:id`
- [x] 8.2 Crear página `/kardex/:productId` con selector de producto en el header, rango de fechas opcional
- [x] 8.3 Renderizar tabla de entradas Kardex con fila de "Saldo inicial" cuando `opening_balance_quantity > 0`
- [x] 8.4 Crear tarjeta de resumen al pie de la tabla: saldo final cantidad, saldo final valor, costo promedio ponderado
- [x] 8.5 Conectar link "Ver Kardex" desde la página de detalle del producto

## 9. Reportes

- [x] 9.1 Crear `ReportLayout` con sub-navegación tipo tabs para los 9 tipos de reporte
- [x] 9.2 Crear componente `DateRangeFilter` reutilizable con validación (rango obligatorio, fecha inicial < final); integrar con React Hook Form + Zod
- [x] 9.3 Implementar reporte Ingresos `/reports/ingresos`: filtros fecha, producto, usuario; tabla de resultados; botones export PDF/Excel
- [x] 9.4 Implementar reporte Egresos `/reports/egresos` (misma estructura)
- [x] 9.5 Implementar reporte Bajas `/reports/bajas`
- [x] 9.6 Implementar reporte Ajustes `/reports/ajustes`
- [x] 9.7 Implementar reporte Stock `/reports/stock`: filtros categoría, bajo_stock; sin rango de fechas obligatorio
- [x] 9.8 Implementar reporte Stock Valorizado `/reports/stock-valorizado`
- [x] 9.9 Implementar reporte Movimientos por Usuario `/reports/movimientos-por-usuario` con selector de usuario obligatorio
- [x] 9.10 Implementar reporte Kardex exportable `/reports/kardex` con selector de producto
- [x] 9.11 Implementar reporte Consolidado `/reports/consolidado`: 4 metric cards (IN/EG/BI/AI totales, productos activos, bajo stock) + gráfico de barras con Recharts
- [x] 9.12 Crear helper `downloadBlob(response, filename)` para manejar descargas de PDF y Excel desde Axios

## 10. Auditoría

- [x] 10.1 Crear página `/audit` con filtros: rango de fechas obligatorio, usuario (dropdown), acción (enum select), tipo entidad, ID entidad
- [x] 10.2 Renderizar tabla de auditoría paginada con columnas: timestamp, usuario, acción (badge coloreado), entidad, ID entidad, IP, descripción
- [x] 10.3 Implementar botón "Exportar Excel" con validación frontend de rango ≤ 90 días antes de llamar al API
- [x] 10.4 Proteger la ruta `/audit` para Admin y Supervisor únicamente

## 11. Administración

- [x] 11.1 Crear página `/admin/users` con tabla de usuarios, búsqueda por username y filtro por rol
- [x] 11.2 Crear `UserFormModal` para crear usuario: username, full_name, rol (select), password, is_active
- [x] 11.3 Crear `UserEditModal` para editar: full_name, rol, is_active, must_change_password
- [x] 11.4 Implementar eliminación/desactivación de usuario con dialog de confirmación; manejar error de usuario activo con sesión
- [x] 11.5 Crear página `/admin/params` con tabla de parámetros editable inline (campo de texto por valor)
- [x] 11.6 Implementar guardado de parámetro con PATCH y toast de confirmación; manejar error de método Kardex bloqueado

## 12. Pulido y detalles finales

- [x] 12.1 Agregar loading states globales (skeleton loaders en tablas, spinner en botones de submit) usando estados de TanStack Query
- [x] 12.2 Agregar empty states en todas las tablas/listas cuando no hay resultados
- [x] 12.3 Implementar manejo global de errores de red (toast genérico cuando el backend no responde)
- [x] 12.4 Agregar página Dashboard `/` con resumen: stock bajo mínimo count, últimos movimientos recientes, link rápido a consolidado
- [x] 12.5 Configurar `README.md` del proyecto frontend con instrucciones de setup y comandos de desarrollo
- [x] 12.6 Verificar que `npm run build` compila sin errores TypeScript
