## ADDED Requirements

### Requirement: Login form
The system SHALL provide a login page at `/login` with username and password fields. It SHALL call `POST /api/v1/auth/login` and store the returned access and refresh tokens in memory (access) and localStorage (refresh).

#### Scenario: Successful login
- **WHEN** the user submits valid credentials
- **THEN** the system stores the tokens and redirects to the dashboard

#### Scenario: Invalid credentials
- **WHEN** the user submits wrong credentials
- **THEN** the system displays the error "Usuario o contraseña incorrectos" without clearing the username field

#### Scenario: Inactive user
- **WHEN** the backend returns a 403 for an inactive user
- **THEN** the system displays "Tu cuenta está desactivada. Contactá al administrador."

### Requirement: Forced password change
The system SHALL detect when the logged-in user has `must_change_password: true` and redirect them to a password-change form before allowing access to any other route.

#### Scenario: First login redirect
- **WHEN** login succeeds and `must_change_password` is `true`
- **THEN** the system redirects to `/change-password` and prevents navigation to other routes

#### Scenario: Successful password change
- **WHEN** the user submits a new password matching the confirmation
- **THEN** the system calls `POST /api/v1/auth/change-password` and redirects to the dashboard

#### Scenario: Passwords do not match
- **WHEN** the new password and confirmation differ
- **THEN** the system shows an inline validation error before submitting

### Requirement: Session inactivity timeout
The system SHALL display a warning modal 2 minutes before the session expires (based on `ACCESS_TOKEN_EXPIRE_MINUTES`), and redirect to login on expiry.

#### Scenario: Inactivity warning
- **WHEN** the session will expire in 2 minutes
- **THEN** the system shows a modal "Tu sesión está por expirar. ¿Querés continuar?"

#### Scenario: Session expired
- **WHEN** the backend returns `SESSION_EXPIRED`
- **THEN** the system clears tokens and redirects to `/login` with a toast notification

### Requirement: Auth context
The system SHALL provide a React context exposing the current user's data (id, username, role, must_change_password) and helper functions (login, logout, refreshToken).

#### Scenario: Auth context available in all routes
- **WHEN** any component calls `useAuth()`
- **THEN** it receives the current user or `null` if unauthenticated
