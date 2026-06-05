## ADDED Requirements

### Requirement: Audit log table
The system SHALL provide an audit log view at `/audit` accessible only to Admins and Supervisors. It SHALL display a paginated table with columns: Timestamp, Usuario, Acción, Entidad, ID Entidad, IP, Descripción.

#### Scenario: Audit log loaded with required date range
- **WHEN** the user selects a date range and clicks "Buscar"
- **THEN** the system calls `GET /api/v1/audit?date_from=...&date_to=...` and renders the results

#### Scenario: Missing date range
- **WHEN** the user clicks "Buscar" without selecting dates
- **THEN** the system shows "El rango de fechas es obligatorio"

### Requirement: Audit log filters
The system SHALL provide optional filters for: usuario (dropdown), acción (enum select), tipo de entidad (text), ID de entidad (number).

#### Scenario: Filter by action
- **WHEN** the user selects "LOGIN" from the acción filter
- **THEN** only audit entries with action=LOGIN are shown

### Requirement: Audit log export
The system SHALL provide an "Exportar Excel" button that calls `GET /api/v1/audit/export?format=excel` and triggers a file download. The export SHALL be limited to 90 days.

#### Scenario: Export within 90 days
- **WHEN** the user clicks "Exportar Excel" with a range ≤ 90 days
- **THEN** the system downloads the Excel file

#### Scenario: Export range exceeds 90 days
- **WHEN** the selected date range is more than 90 days
- **THEN** the system shows "El rango de exportación no puede superar 90 días" before calling the API
