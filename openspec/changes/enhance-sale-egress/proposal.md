## Why

El egreso por venta no permite completar el cobro de forma operativa ni agiliza la carga con lector de códigos. Además, la información configurable de pago, códigos y vendedor no se refleja de forma consistente en la venta.

## What Changes

- Permitir administrar formas de pago y bancos desde la configuración de empresa, incluyendo alta, edición, activación y desactivación.
- Incorporar forma de pago, banco, valor recibido y cambio en las ventas.
- Bloquear el guardado cuando el valor recibido sea menor al total e indicar el faltante.
- Mostrar total de líneas, total de productos, valor recibido, cambio y el stock con el formato configurado.
- Mostrar una columna configurable de código de barras o código interno.
- Cargar automáticamente productos con coincidencia exacta al usar un lector y devolver el foco al buscador.
- Mostrar el vendedor en la ventana de productos y ajustar su posición en la impresión de la venta.

## Capabilities

### New Capabilities

- `sale-payment-configuration`: Administración de formas de pago y bancos para ventas.
- `sale-checkout`: Cobro, totales, validaciones y carga rápida del egreso por venta.

### Modified Capabilities

- `inventory-documents`: Persistencia y consulta de datos de pago de las ventas.
- `company-config`: Nuevas opciones configurables para ventas y códigos.

## Impact

- Backend FastAPI: modelos, esquemas, servicios, endpoints y migración Alembic.
- Frontend React: configuración de empresa, formulario de egreso, editor de líneas, detalle e impresión.
- Pruebas unitarias e integración de backend y frontend.
