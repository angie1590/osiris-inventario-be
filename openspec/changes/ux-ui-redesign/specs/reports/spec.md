## ADDED Requirements

### Requirement: Date filter auto-execution on page load
Report pages that display a default date range SHALL automatically execute the data query on mount using those default dates. The message "Selecciona un rango de fechas" SHALL NOT appear when a valid date range is already present.

#### Scenario: Default dates trigger immediate load
- **WHEN** the user navigates to any report page
- **THEN** the page initializes with default dates (e.g., first and last day of current month) and the data query executes immediately without requiring the user to click "Aplicar"

#### Scenario: No contradictory empty state
- **WHEN** the date range is populated with valid dates and the query returns zero results
- **THEN** the page shows an empty state ("No hay datos para el período seleccionado") not the "Selecciona un rango" prompt

#### Scenario: Apply button re-executes with updated dates
- **WHEN** the user changes the date range and clicks "Aplicar"
- **THEN** the query re-executes with the new dates and results update

---

### Requirement: Quick date range presets
Report pages with date filters SHALL offer quick-select preset buttons: "Hoy", "Esta semana", "Este mes", "Últimos 30 días".

#### Scenario: Preset applies immediately
- **WHEN** the user clicks a preset button (e.g., "Este mes")
- **THEN** the date range inputs are updated to the corresponding range and the query executes automatically

#### Scenario: Custom range coexists with presets
- **WHEN** the user manually enters a custom date range
- **THEN** no preset button is highlighted as active; the custom range is used for the query

---

### Requirement: Date filter consistent state
The visible dates in the filter inputs SHALL always match the dates used by the most recent query execution.

#### Scenario: Filter state matches query
- **WHEN** the user sees report results on screen
- **THEN** the date inputs display exactly the date range that was used to fetch those results
