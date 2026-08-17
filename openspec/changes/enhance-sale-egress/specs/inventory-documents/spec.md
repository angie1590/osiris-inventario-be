## MODIFIED Requirements

### Requirement: Información de empresa en exports de documentos

Cuando un documento transaccional se exporta a PDF, el formato incluye la información de empresa.

#### Scenario: Encabezado en PDF de documento

- **WHEN** se exporta un documento a PDF (si existe ese endpoint)
- **THEN** el PDF incluye logo, razón social, RUC y nombre comercial de la empresa en el encabezado

#### Scenario: Posición del vendedor en nota de venta

- **WHEN** se genera la impresión de una Nota de Venta
- **THEN** el nombre del vendedor aparece aproximadamente 1 cm más arriba que en el formato actual
