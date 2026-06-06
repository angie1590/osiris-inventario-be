## ADDED Requirements

### Requirement: stock_quantity_mode system parameter
The system SHALL include a `SystemParam` row with key `stock_quantity_mode` and allowed values `integer` or `decimal`. The default value at seed time SHALL be `"integer"`. This parameter controls whether stock minimum and movement quantity fields accept decimal values.

#### Scenario: Seed creates the parameter
- **WHEN** the seed script runs on a fresh database
- **THEN** a `SystemParam` row exists with `key="stock_quantity_mode"` and `value="integer"`

#### Scenario: Admin changes the parameter
- **WHEN** an admin updates `stock_quantity_mode` to `"decimal"` via the admin params UI
- **THEN** the new value is persisted and immediately applied to form validations

---

### Requirement: Backend validation of stock quantities per mode
All backend endpoints that accept a quantity or `stock_min` field SHALL validate the value against the current `stock_quantity_mode`. In `integer` mode, decimal values SHALL be rejected with a structured error.

#### Scenario: Integer mode rejects decimal
- **WHEN** `stock_quantity_mode = "integer"` and a request sends `stock_min: 1.5`
- **THEN** the endpoint returns 422 with `code: "INVALID_QUANTITY"` and `errors: { "stock_min": "El stock mínimo debe ser un número entero." }`

#### Scenario: Decimal mode accepts decimal
- **WHEN** `stock_quantity_mode = "decimal"` and a request sends `stock_min: 1.5`
- **THEN** the value is accepted without error

#### Scenario: Integer mode accepts integer
- **WHEN** `stock_quantity_mode = "integer"` and a request sends `stock_min: 5`
- **THEN** the value is accepted without error

---

### Requirement: Frontend enforces stock mode in form validation
The frontend SHALL read `stock_quantity_mode` from the system params and apply the appropriate Zod validation rule to stock minimum and quantity fields.

#### Scenario: Integer mode Zod rule
- **WHEN** `stock_quantity_mode = "integer"` and the user enters 1.5 in the stock mínimo field
- **THEN** the Zod schema rejects the value client-side before the API is called, showing the inline error "El stock mínimo debe ser un número entero"

#### Scenario: Decimal mode Zod rule
- **WHEN** `stock_quantity_mode = "decimal"` and the user enters 1.5
- **THEN** the Zod schema accepts the value

#### Scenario: Mode loaded before form renders
- **WHEN** the product form is about to render the stock mínimo field
- **THEN** the system params query has already resolved; the correct Zod schema is applied from the first render
