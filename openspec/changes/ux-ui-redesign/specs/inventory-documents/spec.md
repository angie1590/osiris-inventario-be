## ADDED Requirements

### Requirement: Inline validation on inventory document creation forms
All inventory document creation forms (Ingresos, Egresos, Bajas, Ajustes) SHALL apply the `ux-validation` spec: required fields show `*`, inline error messages appear below failing fields, the submit button disables during submission, and backend structured errors are mapped to fields.

#### Scenario: Required field validation before submit
- **WHEN** the user submits an Ingreso form without selecting a product
- **THEN** the product field shows a red border and "Selecciona un producto" below it; the API is not called

#### Scenario: Backend error shown inline
- **WHEN** the backend rejects a creation with a structured error naming a specific field
- **THEN** that field displays the backend's error message inline

#### Scenario: Submit button loading state
- **WHEN** the user submits an Egreso form and the API call is in-flight
- **THEN** the submit button shows "Guardando…" and is non-clickable

---

### Requirement: Inventory document list tables with consistent states
All inventory document list pages (Ingresos, Egresos, Bajas, Ajustes) SHALL use the shared `<DataTable>` component and display loading, empty, and error states per the `design-system` spec.

#### Scenario: Loading state on table
- **WHEN** the inventory document list is fetching data
- **THEN** a skeleton loader or spinner is shown in the table area

#### Scenario: Empty list
- **WHEN** no documents exist for the current filters
- **THEN** the `<EmptyState>` component renders with a message like "No hay ingresos registrados"

#### Scenario: Fetch error
- **WHEN** the list fetch fails
- **THEN** the `<ErrorState>` component renders with a "Reintentar" button
