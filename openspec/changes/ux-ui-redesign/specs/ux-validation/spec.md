## ADDED Requirements

### Requirement: Required field indicator on all forms
Every form field that is mandatory SHALL render an asterisk (`*`) in `text-destructive` color immediately after the field label. A note "Los campos marcados con * son obligatorios" SHALL appear near the form title or as a legend when the form contains more than two required fields.

#### Scenario: Required field label
- **WHEN** a form renders a required field (e.g., Razón Social)
- **THEN** the label reads "Razón Social *" with the asterisk in red/destructive color

#### Scenario: Optional field label
- **WHEN** a form renders an optional field
- **THEN** no asterisk is shown; no "(opcional)" suffix is required

---

### Requirement: Inline field-level validation errors
Every form field SHALL display its validation error immediately below the field, using a `<p>` element with `text-xs text-destructive` style. The input SHALL show a red border (`border-destructive`) when in error state. Error messages SHALL be specific to the failing condition and SHALL NOT be generic.

#### Scenario: Required field left empty
- **WHEN** the user submits a form leaving a required field blank
- **THEN** that field's input border turns red and a message appears below (e.g., "La razón social es obligatoria")

#### Scenario: Invalid email format
- **WHEN** the user enters text that is not a valid email in an email field
- **THEN** the error message reads specifically "Ingrese un correo electrónico válido" (not "Invalid" or "Error")

#### Scenario: Logo size exceeded
- **WHEN** the user selects an image file larger than 2 MB for a logo field
- **THEN** the error message reads "El archivo debe ser JPG, PNG o WEBP y pesar máximo 2 MB"

#### Scenario: Error clears on correction
- **WHEN** the user corrects the value in a field that was in error
- **THEN** the red border and error message disappear

---

### Requirement: Backend field errors mapped to form fields
When the backend returns a structured error response with `errors: { field: message }`, the frontend SHALL map each entry to the corresponding form field and display the message inline below that field, in addition to showing a general error banner at the top of the form.

#### Scenario: Field error from backend mapped to input
- **WHEN** the backend returns `{ "errors": { "ruc": "El RUC debe tener 13 dígitos." } }`
- **THEN** the RUC field shows a red border and "El RUC debe tener 13 dígitos." below it

#### Scenario: General form error banner
- **WHEN** the backend returns an error (field-level or general)
- **THEN** a dismissible error banner appears at the top of the form summarizing the failure (e.g., "No se pudo guardar la configuración de empresa.")

#### Scenario: Toast as supplement not replacement
- **WHEN** a form submit error occurs
- **THEN** toast MAY appear as a supplementary signal; it SHALL NOT be the only place the error is shown

---

### Requirement: Structured error envelope from backend
All backend create (`POST`) and update (`PUT`, `PATCH`) endpoints SHALL return validation errors in a structured JSON envelope:
```json
{
  "code": "VALIDATION_ERROR",
  "message": "Human-readable summary.",
  "errors": { "field_name": "Field-specific message." }
}
```
HTTP status code SHALL be 422. The `errors` object is optional and omitted when the error is not field-specific.

#### Scenario: Field validation error
- **WHEN** a required field is missing or fails validation
- **THEN** the response body contains `errors` with an entry for each failing field

#### Scenario: Non-field error
- **WHEN** an error is not specific to a single field (e.g., duplicate entity, server failure)
- **THEN** the response contains `code` and `message` but the `errors` key is absent or empty

#### Scenario: No generic messages
- **WHEN** any error is returned
- **THEN** the `message` field SHALL describe what failed and what the user can do (e.g., "No se pudo guardar la configuración porque el RUC no es válido.") and SHALL NOT contain "Error inesperado", "Datos inválidos", or similar non-actionable strings

---

### Requirement: Form submit button state management
Every form submit button SHALL prevent double submission. While a form submission is in-flight, the button SHALL show a loading state and be non-clickable.

#### Scenario: Submit in progress
- **WHEN** the user clicks "Guardar" and the API call is pending
- **THEN** the button shows "Guardando…" text (or spinner icon) and is `disabled`

#### Scenario: Submit failure re-enables button
- **WHEN** the API returns an error
- **THEN** the button returns to its normal enabled state so the user can retry after correcting errors

---

### Requirement: Login page inline error
The login page SHALL display authentication errors (wrong credentials, account locked) as a visible inline message inside the form, not solely as a toast notification.

#### Scenario: Invalid credentials
- **WHEN** the user submits the login form with wrong username or password
- **THEN** an inline error message appears inside the form area reading "Usuario o contraseña incorrectos"

#### Scenario: Error clears on new submission
- **WHEN** the user modifies the credentials and submits again
- **THEN** the previous inline error disappears before the new request completes
