# Spec: reports

## Purpose
Generación y exportación de reportes del sistema (PDF y Excel). Incluye validación de empresa configurada antes de exportar y encabezado corporativo estandarizado en todos los formatos de salida.

## Requirements

### Requirement: Validación de empresa antes de exportar
Los endpoints de exportación de reportes (PDF y Excel) requieren que la configuración de empresa esté completa (`is_complete = true`) antes de procesar la solicitud.

#### Scenario: Empresa no configurada
- **WHEN** se solicita exportar cualquier reporte y `CompanyConfig` no existe o `is_complete = false`
- **THEN** el sistema responde 422 con código `COMPANY_NOT_CONFIGURED` y mensaje descriptivo

#### Scenario: Empresa configurada
- **WHEN** `CompanyConfig` existe y `is_complete = true`
- **THEN** la exportación procede normalmente

---

### Requirement: Encabezado corporativo en todos los reportes
Todos los reportes exportados (PDF y Excel) incluyen un encabezado corporativo estandarizado.

#### Scenario: Contenido del encabezado PDF
- **WHEN** se exporta cualquier reporte como PDF
- **THEN** la primera sección del documento incluye: logo (si está configurado), razón social, nombre comercial (si está configurado), RUC, fecha y hora de generación, y nombre del reporte

#### Scenario: Contenido del encabezado Excel
- **WHEN** se exporta cualquier reporte como Excel
- **THEN** las primeras filas de la hoja incluyen: razón social, nombre comercial, RUC, fecha de generación y nombre del reporte (el logo se omite en Excel por simplicidad)
