## Context

El flujo de venta vive en el formulario de egresos y reutiliza el editor común de líneas. El backend persiste `InventoryDocument` y sus snapshots de producto, mientras que la configuración de empresa es singleton y editable por administradores. El stock y el código mostrado ya tienen parámetros del sistema, pero la venta no tiene datos de cobro ni carga directa por lector.

## Goals / Non-Goals

**Goals:**

- Administrar opciones activas de pago y bancos desde empresa.
- Persistir el método y banco elegidos como texto histórico junto con recibido y cambio.
- Validar en backend la coherencia del cobro y bloquear recibidos menores al total.
- Hacer que el editor respete el modo de cantidad, el código configurado, el foco y la lectura exacta.
- Mantener el histórico de documentos independiente de posteriores cambios de configuración.

**Non-Goals:**

- No emitir comprobantes fiscales ni integrar pasarelas bancarias.
- No imprimir datos de cobro en la Nota de Venta.
- No modificar las búsquedas por nombre para seleccionar automáticamente resultados ambiguos.

## Decisions

- **Opciones en `CompanyConfig`**: guardar listas JSON de formas de pago y bancos con identificador estable, nombre y estado activo. Esto mantiene la administración junto a Empresa y evita una nueva entidad para catálogos pequeños. Las ventas guardarán nombre y banco seleccionados como snapshot.
- **Totales en frontend y backend**: el frontend calcula resumen y cambio en tiempo real; el servicio recalcula el total comercial desde las líneas y valida el recibido antes de persistir, evitando confiar en valores manipulados del cliente.
- **Campos nullable para compatibilidad**: los documentos existentes mantendrán nulos para los nuevos campos; solo las ventas nuevas usarán los datos de pago.
- **Lectura exacta**: el endpoint/listado de productos se consultará con el texto leído y el frontend auto-seleccionará únicamente una coincidencia exacta de código. La coincidencia por nombre seguirá requiriendo selección.
- **Columna única**: el editor recibirá la configuración de código y mostrará barra o interno, manteniendo el snapshot de línea para detalle futuro.
- **Impresión aislada**: el vendedor se moverá en el layout existente aproximadamente 1 cm sin incorporar datos de pago al PDF.

## Risks / Trade-offs

- [Configuraciones antiguas sin listas de pago] -> Resolver con defaults Efectivo/Transferencia y migración idempotente.
- [Cambiar o desactivar una opción usada históricamente] -> Persistir texto snapshot, no FK.
- [Lectores con formatos distintos o sin Enter] -> Mantener Enter como disparador y permitir selección manual como fallback.
- [Redondeo monetario] -> Calcular con Decimal en backend y redondear a centavos; frontend solo refleja el mismo resultado.

## Migration Plan

1. Agregar columnas nullable de venta y columnas/listas de configuración con defaults compatibles.
2. Ejecutar migración Alembic antes de desplegar backend y frontend.
3. Desplegar validaciones y respuestas backend.
4. Desplegar configuración y formulario frontend.
5. Rollback: retirar frontend primero y revertir migración solo si no existen documentos nuevos dependientes; los campos nullable permiten compatibilidad durante despliegues parciales.

## Open Questions

- Ninguna. El recibo inferior al total bloquea el guardado y muestra el faltante.
