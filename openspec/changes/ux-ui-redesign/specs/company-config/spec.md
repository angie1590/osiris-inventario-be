## ADDED Requirements

### Requirement: Structured error responses on company config endpoints
`POST /api/v1/company` and `PATCH /api/v1/company` SHALL return validation errors using the standard envelope `{ code, message, errors }` defined in the `ux-validation` spec. The `errors` dictionary SHALL include an entry for each field that fails validation.

#### Scenario: Missing required field error
- **WHEN** `POST /api/v1/company` is called with `razon_social` absent
- **THEN** the response is 422 with body `{ "code": "VALIDATION_ERROR", "message": "No se pudo guardar la configuración de empresa.", "errors": { "razon_social": "La razón social es obligatoria." } }`

#### Scenario: Multiple field errors
- **WHEN** both `ruc` and `email` fail validation
- **THEN** the `errors` object includes entries for both `ruc` and `email` in a single response

#### Scenario: Non-field conflict error
- **WHEN** `POST /api/v1/company` is called and a company already exists
- **THEN** the response is 409 with `{ "code": "COMPANY_ALREADY_EXISTS", "message": "Ya existe una configuración de empresa." }` (no `errors` key)
