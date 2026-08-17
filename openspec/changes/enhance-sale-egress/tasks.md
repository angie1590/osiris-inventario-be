## 1. Contrato y persistencia backend

- [x] 1.1 Añadir catálogos de formas de pago y bancos a CompanyConfig, esquemas, respuestas y servicio con defaults compatibles y permisos de administrador.
- [x] 1.2 Añadir campos de pago, banco, valor recibido y cambio a InventoryDocument, esquemas de creación/respuesta y migración Alembic.
- [x] 1.3 Implementar validación backend de opciones activas, banco obligatorio para transferencia, cálculo Decimal de total/cambio y rechazo de recibido menor con faltante.
- [ ] 1.4 Añadir o actualizar pruebas backend para configuración, validaciones de cobro, compatibilidad de documentos existentes y snapshots históricos.

## 2. Configuración frontend

- [x] 2.1 Extender tipos y hooks de configuración de empresa para administrar formas de pago y bancos.
- [x] 2.2 Añadir en la pantalla de Empresa controles para agregar, editar, activar y desactivar formas de pago y bancos.
- [ ] 2.3 Añadir pruebas de configuración y permisos visibles para los catálogos de venta.

## 3. Formulario y editor de venta

- [x] 3.1 Añadir al formulario de venta forma de pago, banco condicional, valor recibido, cálculo de cambio y advertencia de faltante que bloquee el guardado.
- [x] 3.2 Mostrar resumen separado de total de ítems, total de productos, total monetario, recibido y cambio.
- [x] 3.3 Formatear stock y cantidad según integer/decimal y mostrar la columna única de código según el parámetro habilitado.
- [x] 3.4 Ajustar foco al buscador al crear líneas y soportar lectura exacta por código con incremento automático y siguiente línea preparada.
- [x] 3.5 Mostrar el vendedor en la ventana de egresos de ventas.
- [ ] 3.6 Añadir pruebas frontend para pago, faltante, resumen, código y lectura exacta.

## 4. Detalle, impresión y verificación

- [x] 4.1 Mostrar los nuevos datos de venta en el detalle sin añadirlos a la impresión de la Nota de Venta.
- [x] 4.2 Subir el nombre del vendedor aproximadamente 1 cm en el layout de impresión.
- [ ] 4.3 Ejecutar pruebas backend/frontend, typecheck, lint y validación de migración; corregir regresiones del flujo de venta.
