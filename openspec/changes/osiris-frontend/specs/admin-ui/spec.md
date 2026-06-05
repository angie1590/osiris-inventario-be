## ADDED Requirements

### Requirement: User management (Admin only)
The system SHALL provide a user management page at `/admin/users` accessible only to Admins. It SHALL display a table of all users with columns: Username, Nombre completo, Rol, Estado, Fecha creación.

#### Scenario: Admin views user list
- **WHEN** an Admin navigates to `/admin/users`
- **THEN** the system calls `GET /api/v1/admin/users` and renders the table

### Requirement: Create user form
The Admin SHALL be able to create new users via a modal form with fields: username, full_name, role (dropdown), password (auto-generated or manual), is_active (checkbox).

#### Scenario: User created
- **WHEN** the Admin fills the form and clicks "Crear"
- **THEN** the system calls `POST /api/v1/admin/users` and refreshes the list

#### Scenario: Duplicate username
- **WHEN** the backend returns a conflict error
- **THEN** the form shows "El nombre de usuario ya existe"

### Requirement: Edit user
The Admin SHALL be able to edit a user's full_name, role, is_active, and must_change_password fields via a modal form.

#### Scenario: User role changed
- **WHEN** the Admin changes a user's role from operator to supervisor
- **THEN** the system calls `PATCH /api/v1/admin/users/:id` and updates the row in the table

### Requirement: System parameters panel
The system SHALL provide a parameters page at `/admin/params` showing all system parameters as key-value pairs editable inline.

#### Scenario: Admin views parameters
- **WHEN** an Admin navigates to `/admin/params`
- **THEN** the system calls `GET /api/v1/admin/params` and shows each param with its current value

#### Scenario: Update kardex method
- **WHEN** the Admin changes `kardex_method` and confirms
- **THEN** the system calls `PATCH /api/v1/admin/params/kardex_method` and shows the updated value

#### Scenario: Kardex method locked by existing movements
- **WHEN** the backend returns an error for changing the Kardex method
- **THEN** the system shows "No se puede cambiar el método Kardex con movimientos registrados en el ejercicio actual"
