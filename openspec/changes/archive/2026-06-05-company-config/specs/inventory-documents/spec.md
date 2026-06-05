## MODIFIED Requirements

### Requirement: Validación de empresa antes de crear documentos
Los endpoints de creación de documentos transaccionales (IN, EG, BI, AI) requieren que la configuración de empresa esté completa antes de procesar la solicitud.

#### Scenario: Empresa no configurada al crear documento
- **WHEN** se llama `POST /api/v1/inventory/ingresos`, `egresos`, `bajas` o `ajustes` y `CompanyConfig` no existe o `is_complete = false`
- **THEN** el sistema responde 422 con código `COMPANY_NOT_CONFIGURED`

#### Scenario: Empresa configurada
- **WHEN** `CompanyConfig` existe y `is_complete = true`
- **THEN** el documento se crea normalmente sin cambios en el flujo

---

### Requirement: Información de empresa en exports de documentos
Cuando un documento transaccional se exporta a PDF, el formato incluye la información de empresa.

#### Scenario: Encabezado en PDF de documento
- **WHEN** se exporta un documento a PDF (si existe ese endpoint)
- **THEN** el PDF incluye logo, razón social, RUC y nombre comercial de la empresa en el encabezado
