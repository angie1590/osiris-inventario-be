## 1. Infraestructura y proyecto base

- [x] 1.1 Inicializar proyecto FastAPI con estructura de directorios: `app/api`, `app/core`, `app/models`, `app/schemas`, `app/services`, `app/repositories`, `app/utils`
- [x] 1.2 Configurar `pyproject.toml` con dependencias: FastAPI, SQLAlchemy 2.x async, Alembic, Pydantic v2, asyncpg, python-jose, passlib[bcrypt], redis, reportlab, openpyxl
- [x] 1.3 Crear `docker-compose.yml` con servicios: postgres, redis, api (con hot-reload para desarrollo)
- [x] 1.4 Configurar variables de entorno con Pydantic Settings: DATABASE_URL, REDIS_URL, SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES (default 30), KARDEX_METHOD, APP_ENV
- [x] 1.5 Configurar conexión async a PostgreSQL con SQLAlchemy 2.x y pool de conexiones
- [x] 1.6 Configurar conexión a Redis para blacklist de tokens
- [x] 1.7 Inicializar Alembic con `alembic init` y configurar `env.py` para async SQLAlchemy
- [x] 1.8 Configurar middleware de CORS, logging estructurado y manejo global de excepciones
- [x] 1.9 Crear `app/core/security.py` con funciones: hash_password, verify_password, create_access_token, create_refresh_token, decode_token

## 2. Modelos de base de datos y migraciones

- [x] 2.1 Crear modelo `users`: id, username, hashed_password, full_name, role, is_active, must_change_password, created_at, updated_at
- [x] 2.2 Crear modelo `refresh_tokens`: id, user_id, token_hash, expires_at, revoked_at, ip_address, created_at
- [x] 2.3 Crear modelo `categories`: id, name, description, parent_id (self-referential FK), is_active, created_at, updated_at
- [x] 2.4 Crear modelo `category_attributes`: id, category_id, name, data_type (enum: text/integer/decimal/date/boolean/select), is_required, select_options (JSON), created_at
- [x] 2.5 Crear modelo `products`: id, name, description, category_id, stock_minimo, stock_actual, pvp, status, custom_attributes (JSONB), created_at, updated_at
- [x] 2.6 Crear modelo `system_params`: id, key, value, description, updated_by, updated_at
- [x] 2.7 Crear modelo `document_sequences`: id, doc_type, year, last_number (con índice único en doc_type+year)
- [x] 2.8 Crear modelo `inventory_documents`: id, number, doc_type (IN/EG/BI/AI), status (pending/approved/cancelled), reference, notes, created_by, authorized_by, authorization_code_hash, requested_at, authorized_at, created_at
- [x] 2.9 Crear modelo `inventory_document_lines`: id, document_id, product_id, quantity, unit_cost, unit_price, lot_id (FK nullable), created_at
- [x] 2.10 Crear modelo `authorization_codes`: id, document_id, code_hash, expires_at, used_at, created_by, created_at
- [x] 2.11 Crear modelo `kardex_entries`: id, product_id, document_id, document_line_id, entry_type (IN/OUT/ADJUST), quantity_in, cost_in, quantity_out, cost_out, balance_quantity, balance_value, weighted_avg_cost, lot_id, created_at — con particionamiento por rango en `created_at`
- [x] 2.12 Crear modelo `inventory_lots` (para PEPS): id, product_id, document_id, quantity_initial, quantity_available, unit_cost, lot_date, created_at
- [x] 2.13 Crear modelo `audit_logs`: id, timestamp, user_id, username, ip_address, action, entity_type, entity_id, previous_values (JSONB), new_values (JSONB), description — con particionamiento por rango en `timestamp`
- [x] 2.14 Crear migración inicial de Alembic con todos los modelos, índices y constraints
- [x] 2.15 Crear índices: FK de todas las tablas, (doc_type, year) en sequences, (product_id, created_at) en kardex_entries y audit_logs, (entity_type, entity_id) en audit_logs, (username) en users
- [x] 2.16 Crear trigger PostgreSQL que impide UPDATE directo al campo `stock_actual` de `products` (solo permite actualización via función `update_product_stock()`)
- [x] 2.17 Crear función PostgreSQL `update_product_stock(product_id, delta)` que actualiza stock_actual y valida no negatividad
- [x] 2.18 Crear particiones iniciales para `kardex_entries` y `audit_logs` (año actual + siguiente)
- [x] 2.19 Crear script de seed para usuario Administrador inicial y parámetros del sistema por defecto

## 3. Autenticación y sesiones

- [x] 3.1 Implementar `POST /auth/login`: validar credenciales, verificar usuario activo, emitir access token + refresh token, registrar en auditoría
- [x] 3.2 Implementar `POST /auth/refresh`: validar refresh token en DB, emitir nuevo access token, rotar refresh token
- [x] 3.3 Implementar `POST /auth/logout`: revocar access token en Redis blacklist, revocar refresh token en DB, registrar en auditoría
- [x] 3.4 Implementar `POST /auth/change-password`: validar contraseña actual, hashear nueva contraseña, invalidar tokens activos del usuario, desactivar flag `must_change_password`
- [x] 3.5 Crear dependencia FastAPI `get_current_user` que valida JWT, verifica blacklist Redis y refresca contador de inactividad
- [x] 3.6 Implementar lógica de inactividad: en cada request autenticado exitoso, actualizar TTL de la clave de sesión en Redis; si expiró, retornar 401 SESSION_EXPIRED
- [x] 3.7 Implementar endpoint `GET /auth/me` que retorna datos del usuario autenticado incluyendo `require_password_change`
- [x] 3.8 Registrar eventos de auditoría para: login exitoso, login fallido, logout, expiración de sesión, cambio de contraseña

## 4. Control de acceso por roles (RBAC)

- [x] 4.1 Definir enum `UserRole` con valores: `admin`, `operator`, `supervisor` y mapa de permisos por recurso/acción
- [x] 4.2 Crear dependencia FastAPI `require_role(*roles)` que verifica el rol del usuario autenticado y retorna 403 si no corresponde
- [x] 4.3 Crear dependencia `require_permission(resource, action)` para verificación granular de permisos
- [x] 4.4 Aplicar dependencias de permisos a todos los routers del sistema
- [x] 4.5 Implementar `GET/POST/PATCH/DELETE /admin/users`: gestión completa de usuarios (solo Administrador)
- [x] 4.6 Registrar en auditoría: creación, modificación y cambio de rol/estado de usuarios

## 5. Catálogo de productos — Categorías

- [x] 5.1 Implementar `GET /categories`: listado con estructura jerárquica, paginado con keyset
- [x] 5.2 Implementar `POST /categories`: crear categoría, validar parent_id existente y activo
- [x] 5.3 Implementar `PATCH /categories/{id}`: editar nombre/descripción, registrar en auditoría
- [x] 5.4 Implementar `DELETE /categories/{id}`: eliminación lógica con validación de hijos activos y productos asignados
- [x] 5.5 Implementar `GET /categories/{id}/attributes`: retornar atributos propios + heredados de la cadena de herencia
- [x] 5.6 Implementar `POST /categories/{id}/attributes`: agregar atributo, validar nombre único en cadena de herencia, validar opciones para tipo select
- [x] 5.7 Implementar `PATCH /categories/{id}/attributes/{attr_id}`: editar atributo existente
- [x] 5.8 Implementar `DELETE /categories/{id}/attributes/{attr_id}`: eliminar atributo, validar que no hay productos con ese valor asignado
- [x] 5.9 Implementar helper `get_inherited_attributes(category_id)` que recorre la cadena de herencia y retorna todos los atributos sin duplicados
- [x] 5.10 Registrar en auditoría: CRUD de categorías y atributos

## 6. Catálogo de productos — Productos

- [x] 6.1 Implementar `GET /products`: listado paginado con filtros por nombre, categoría (recursivo), estado, bajo_stock
- [x] 6.2 Implementar `POST /products`: crear producto, validar campos base, validar atributos de la categoría (obligatorios y tipos), stock_actual = 0, registrar en auditoría
- [x] 6.3 Implementar `GET /products/{id}`: detalle del producto con atributos resueltos y estado bajo_stock
- [x] 6.4 Implementar `PATCH /products/{id}`: editar campos editables (no stock_actual), validar atributos, registrar en auditoría
- [x] 6.5 Implementar `PATCH /products/{id}/status`: activar/desactivar producto, registrar en auditoría
- [x] 6.6 Implementar validación de atributos personalizados: tipo de dato correcto, valores en lista para type=select, obligatorios presentes
- [x] 6.7 Asegurar que `stock_actual` sea ignorado en payloads de creación y edición (nunca modificado directamente)

## 7. Movimientos de inventario — Ingresos (IN) y Egresos (EG)

- [x] 7.1 Implementar helper `generate_document_number(doc_type, year)` con bloqueo a nivel de fila en `document_sequences`
- [x] 7.2 Implementar `POST /inventory/ingresos`: validar productos activos, generar número IN, crear documento + líneas, llamar `update_product_stock`, actualizar Kardex, retornar HTTP 201
- [x] 7.3 Implementar `POST /inventory/egresos`: validar stock suficiente por línea, generar número EG, crear documento + líneas, llamar `update_product_stock`, actualizar Kardex
- [x] 7.4 Implementar `GET /inventory/ingresos` y `GET /inventory/egresos`: listados paginados con filtros por fecha, producto, usuario
- [x] 7.5 Implementar `GET /inventory/ingresos/{id}` y `GET /inventory/egresos/{id}`: detalle completo con líneas
- [x] 7.6 Registrar en auditoría: creación de documentos IN y EG

## 8. Movimientos de inventario — Bajas (BI) y Ajustes (AI)

- [x] 8.1 Implementar `POST /inventory/bajas`: crear solicitud BI en estado `pendiente`, NO modificar stock
- [x] 8.2 Implementar `POST /inventory/ajustes`: crear solicitud AI en estado `pendiente`, NO modificar stock
- [x] 8.3 Implementar `POST /inventory/bajas/{id}/authorization-code` (solo Admin): generar OTP alfanumérico 8 chars, hashear y guardar en `authorization_codes` con TTL 15 min, retornar código en texto plano
- [x] 8.4 Implementar `POST /inventory/ajustes/{id}/authorization-code` (solo Admin): igual que 8.3
- [x] 8.5 Implementar `POST /inventory/bajas/{id}/approve`: validar código OTP vigente y no usado, validar stock suficiente, aprobar BI, actualizar stock, actualizar Kardex, marcar código como usado, registrar en auditoría con solicitante+autorizador+timestamp
- [x] 8.6 Implementar `POST /inventory/ajustes/{id}/approve`: igual que 8.5, soportar incremento y decremento
- [x] 8.7 Implementar `POST /inventory/bajas/{id}/cancel` y `POST /inventory/ajustes/{id}/cancel`: cancelar solicitudes pendientes
- [x] 8.8 Implementar `GET /inventory/bajas` y `GET /inventory/ajustes`: listados paginados con filtros por fecha, estado, usuario
- [x] 8.9 Validar inmutabilidad: retornar 409 DOCUMENT_IS_IMMUTABLE si se intenta modificar un documento aprobado
- [x] 8.10 Registrar en auditoría: creación de solicitudes BI/AI, aprobaciones, cancelaciones y generación de códigos

## 9. Kardex

- [x] 9.1 Implementar servicio `KardexService.record_entry(document, lines)` que crea entradas de Kardex según método activo del sistema
- [x] 9.2 Implementar cálculo PEPS: al registrar un IN crear/actualizar lote en `inventory_lots`; al registrar EG/BI/AI consumir lotes en orden FIFO, crear entradas de Kardex por lote consumido
- [x] 9.3 Implementar cálculo Promedio Ponderado: al registrar IN recalcular costo promedio; al registrar EG/BI/AI valorizar al costo promedio vigente
- [x] 9.4 Implementar `GET /kardex/{product_id}`: retornar entradas de Kardex con filtro de fechas, saldos iniciales del período y resumen de valorización
- [x] 9.5 Implementar validación que impide cambio de método Kardex con movimientos en el ejercicio actual
- [x] 9.6 Implementar `PATCH /admin/params/kardex-method` (solo Admin): cambiar método con validación de ejercicio
- [x] 9.7 Crear job de mantenimiento (script) que genera particiones del mes siguiente en `kardex_entries` y `audit_logs`

## 10. Parámetros del sistema

- [x] 10.1 Implementar `GET /admin/params`: listar todos los parámetros del sistema (solo Admin)
- [x] 10.2 Implementar `PATCH /admin/params/{key}`: actualizar valor de parámetro, registrar en auditoría con valor anterior y nuevo
- [x] 10.3 Crear parámetros iniciales: `session_timeout_minutes` (30), `kardex_method` (PEPS), `max_export_date_range_days` (90)

## 11. Reportes

- [x] 11.1 Implementar `GET /reports/ingresos`: reporte con filtros de fecha, categoría, producto, usuario; paginado
- [x] 11.2 Implementar `GET /reports/egresos`: ídem para EG
- [x] 11.3 Implementar `GET /reports/bajas`: ídem para BI
- [x] 11.4 Implementar `GET /reports/ajustes`: ídem para AI
- [x] 11.5 Implementar `GET /reports/stock`: reporte de stock actual con filtros por categoría, estado bajo_stock
- [x] 11.6 Implementar `GET /reports/stock-valorizado`: inventario valorizado con costo según método Kardex activo, subtotales por categoría, total general; soportar filtro `as_of_date`
- [x] 11.7 Implementar `GET /reports/movimientos-por-usuario`: consolidado por usuario en rango de fechas
- [x] 11.8 Implementar `GET /reports/kardex/{product_id}`: Kardex como reporte exportable
- [x] 11.9 Implementar `GET /reports/consolidado`: métricas ejecutivas del período
- [x] 11.10 Implementar helper `ExportService.to_pdf(report_data, title, filters)` usando ReportLab con encabezado (título, rango de fechas, fecha generación, usuario)
- [x] 11.11 Implementar helper `ExportService.to_excel(report_data, title)` usando openpyxl con formato tabular
- [x] 11.12 Agregar parámetro `format=pdf|excel` a todos los endpoints de reportes para desencadenar exportación
- [x] 11.13 Validar rango de fechas obligatorio en todos los reportes y retornar 422 si falta o está invertido

## 12. Log de auditoría

- [x] 12.1 Implementar `AuditService.log(user, action, entity_type, entity_id, previous, new, request)` como servicio asíncrono que registra en `audit_logs`
- [x] 12.2 Integrar `AuditService.log` en todos los servicios que modifican datos (lista completa definida en spec audit-log)
- [x] 12.3 Implementar `GET /audit`: consulta paginada con filtros obligatorios de fecha y opcionales: usuario, acción, entidad_tipo, entidad_id
- [x] 12.4 Implementar `GET /audit/export?format=excel`: exportar auditoría con validación máximo 90 días
- [x] 12.5 Extraer IP real del cliente considerando header `X-Forwarded-For` en el middleware de autenticación
- [x] 12.6 Asegurar que la tabla `audit_logs` tiene solo permisos INSERT para el usuario de aplicación en PostgreSQL

## 13. Tests

- [x] 13.1 Configurar pytest con base de datos de test (PostgreSQL en Docker), fixtures de sesión async y client de FastAPI
- [x] 13.2 Tests de autenticación: login exitoso, fallido, logout, refresh, expiración de sesión, cambio de contraseña obligatorio
- [x] 13.3 Tests de RBAC: acceso permitido y denegado para cada rol en endpoints críticos
- [x] 13.4 Tests de catálogo: CRUD de categorías con jerarquía, herencia de atributos, validación de duplicados, CRUD de productos con validación de atributos
- [x] 13.5 Tests de movimientos IN/EG: creación exitosa, producto inexistente, stock insuficiente, numeración consecutiva
- [x] 13.6 Tests de flujo BI/AI: creación, generación de código OTP, aprobación exitosa, código expirado, cancelación
- [x] 13.7 Tests de Kardex PEPS: entrada simple, salida con un lote, salida con múltiples lotes
- [x] 13.8 Tests de Kardex Promedio Ponderado: recalculo de promedio tras ingreso, valorización de salida
- [x] 13.9 Tests de reportes: generación con filtros, validación de fechas, exportación PDF y Excel
- [x] 13.10 Tests de auditoría: verificar registro automático en operaciones críticas, consulta con filtros, validación de immutabilidad
- [x] 13.11 Tests del trigger de stock: verificar que UPDATE directo a stock_actual falla en PostgreSQL

## 14. Documentación y entrega

- [x] 14.1 Verificar que OpenAPI spec se genera correctamente en `/docs` con todos los endpoints documentados
- [x] 14.2 Crear `README.md` con instrucciones de setup, variables de entorno requeridas y comandos de desarrollo
- [x] 14.3 Crear `.env.example` con todas las variables de entorno necesarias
- [ ] 14.4 Validar que `docker compose up` levanta el sistema completo correctamente
- [ ] 14.5 Ejecutar suite de tests completa y confirmar que todos pasan
