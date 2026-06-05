## ADDED Requirements

### Requirement: Reports navigation
The system SHALL provide a reports section at `/reports` with sub-navigation for: Ingresos, Egresos, Bajas, Ajustes, Stock, Stock Valorizado, Movimientos por Usuario, Kardex, Consolidado.

#### Scenario: Reports accessible by Admin and Supervisor
- **WHEN** an Admin or Supervisor navigates to `/reports`
- **THEN** the reports section renders without errors

#### Scenario: Reports inaccessible by Operator
- **WHEN** an Operator navigates to `/reports`
- **THEN** the system shows a 403 "Sin acceso" page

### Requirement: Date range filter (mandatory)
All movement reports SHALL require a date range before fetching data. Submitting without dates SHALL show a validation error.

#### Scenario: Missing date range
- **WHEN** the user clicks "Generar" without selecting dates
- **THEN** the form shows "El rango de fechas es obligatorio"

#### Scenario: Inverted date range
- **WHEN** `date_from` is after `date_to`
- **THEN** the form shows "La fecha inicial debe ser anterior a la fecha final"

### Requirement: Report results table
The system SHALL display report results in a data table with sortable columns and show a total count of results.

#### Scenario: Report rendered
- **WHEN** the user submits valid filters
- **THEN** the system calls the corresponding report endpoint and renders the results in a table

### Requirement: Export to PDF and Excel
Each report SHALL have "Exportar PDF" and "Exportar Excel" buttons that trigger a file download.

#### Scenario: Export PDF
- **WHEN** the user clicks "Exportar PDF"
- **THEN** the system calls the report endpoint with `format=pdf` and triggers a browser file download

#### Scenario: Export Excel
- **WHEN** the user clicks "Exportar Excel"
- **THEN** the system calls the report endpoint with `format=excel` and triggers a browser file download

### Requirement: Consolidado dashboard
The consolidado report SHALL display metric cards (totals per movement type, active products, products below minimum) and a bar chart using Recharts.

#### Scenario: Consolidado loaded
- **WHEN** the user selects a date range and submits
- **THEN** metric cards and a bar chart of movement counts by type are displayed
