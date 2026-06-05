## ADDED Requirements

### Requirement: Kardex table view
The system SHALL provide a Kardex view at `/kardex/:productId` showing a chronological table of all entries with columns: Fecha, Tipo, Documento, Cantidad Entrada, Costo Entrada, Cantidad Salida, Costo Salida, Saldo Cantidad, Saldo Valor, Costo Promedio.

#### Scenario: Kardex loaded for product
- **WHEN** the user navigates to `/kardex/42`
- **THEN** the system calls `GET /api/v1/kardex/42` and renders the entries table

#### Scenario: Opening balance shown
- **WHEN** the Kardex response includes `opening_balance_quantity` > 0
- **THEN** the first row of the table shows the opening balance with label "Saldo inicial"

### Requirement: Kardex date range filter
The system SHALL allow filtering the Kardex by date range, updating the opening balance and closing balance accordingly.

#### Scenario: Date range applied
- **WHEN** the user selects a date range and clicks "Aplicar"
- **THEN** the Kardex reloads with the filtered entries and recalculated balances

### Requirement: Kardex closing balance summary
The system SHALL display a summary card at the bottom of the Kardex showing closing balance quantity, closing balance value, and current weighted average cost.

#### Scenario: Summary card visible
- **WHEN** the Kardex table is rendered
- **THEN** a summary card shows `closing_balance_quantity`, `closing_balance_value`, and `weighted_avg_cost` from the API response
