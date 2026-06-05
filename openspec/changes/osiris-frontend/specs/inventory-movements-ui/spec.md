## ADDED Requirements

### Requirement: Ingreso (IN) creation form
The system SHALL provide a form at `/inventory/ingresos/new` for creating an Ingreso with one or more product lines. Each line SHALL include product selector, quantity, and unit cost.

#### Scenario: Add multiple lines
- **WHEN** the user clicks "Agregar línea"
- **THEN** a new row appears with product, quantity, and cost fields

#### Scenario: Ingreso created successfully
- **WHEN** the user submits the form
- **THEN** the system calls `POST /api/v1/inventory/ingresos`, shows a success toast with the document number, and redirects to the list

#### Scenario: Product not found
- **WHEN** the backend returns `PRODUCT_NOT_FOUND`
- **THEN** the form highlights the problematic line with an error message

### Requirement: Egreso (EG) creation form
The system SHALL provide a form at `/inventory/egresos/new` identical in structure to Ingreso but without the unit cost field.

#### Scenario: Insufficient stock error
- **WHEN** the quantity entered exceeds the available stock
- **THEN** the system shows an inline error "Stock insuficiente" on the affected line after submission attempt

### Requirement: Baja (BI) request form
The system SHALL provide a form for creating a Baja Inventario request. Created document SHALL display status "Pendiente" and require Admin approval.

#### Scenario: BI created in pending state
- **WHEN** an Operator submits a BI request
- **THEN** the system calls `POST /api/v1/inventory/bajas`, the returned document has status "pending", and the user sees "Solicitud creada, pendiente de autorización"

### Requirement: Ajuste (AI) request form
The system SHALL provide a form for creating an Ajuste Inventario request with fields for adjust_type (increment/decrement), lines, and notes.

#### Scenario: AI created in pending state
- **WHEN** an Operator submits an AI request
- **THEN** the system calls `POST /api/v1/inventory/ajustes` and the document is shown with status "pending"

### Requirement: OTP authorization flow for BI and AI
The system SHALL provide an Admin-only action to generate an authorization code for pending BI/AI documents, and an approval form that accepts the OTP.

#### Scenario: Admin generates OTP code
- **WHEN** an Admin clicks "Generar código" on a pending BI/AI document
- **THEN** the system calls the authorization-code endpoint and displays the 8-character code in a highlighted modal for copying

#### Scenario: Approval with valid OTP
- **WHEN** an Admin enters a valid OTP and clicks "Aprobar"
- **THEN** the system calls the approve endpoint and the document status changes to "approved"

#### Scenario: Invalid OTP
- **WHEN** the OTP is wrong or expired
- **THEN** the system shows "Código de autorización inválido o vencido"

### Requirement: Document list views
The system SHALL provide paginated list views for each document type (IN, EG, BI, AI) with filters by date range, status, and product. Each row links to the document detail.

#### Scenario: Filter by date range
- **WHEN** the user selects a date range and clicks "Filtrar"
- **THEN** only documents created within that range are shown

#### Scenario: Document detail
- **WHEN** the user clicks on a document row
- **THEN** the system shows the full document with all lines, metadata, and status history
