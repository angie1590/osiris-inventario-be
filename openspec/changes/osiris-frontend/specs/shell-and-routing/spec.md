## ADDED Requirements

### Requirement: Project structure
The system SHALL be a standalone Vite + React 18 + TypeScript project named `osiris-inventario-fe`, located in a sibling directory to the backend. It SHALL use Tailwind CSS for styling and shadcn/ui for UI components.

#### Scenario: Project initializes without errors
- **WHEN** the developer runs `npm install && npm run dev`
- **THEN** the dev server starts on port 5173 with no TypeScript or lint errors

### Requirement: Client-side routing
The system SHALL use React Router v6 with a route hierarchy that maps to the application's functional areas.

#### Scenario: Unauthenticated user is redirected to login
- **WHEN** an unauthenticated user navigates to any protected route
- **THEN** the system redirects them to `/login`

#### Scenario: Authenticated user cannot access login
- **WHEN** an authenticated user navigates to `/login`
- **THEN** the system redirects them to the dashboard

### Requirement: Role-based route protection
The system SHALL protect routes based on user role. Routes requiring Admin access SHALL redirect Operators and Supervisors to an "access denied" page.

#### Scenario: Operator cannot access admin routes
- **WHEN** a logged-in Operator navigates to `/admin/users`
- **THEN** the system displays a 403 "Sin acceso" page

#### Scenario: Supervisor can access reports
- **WHEN** a logged-in Supervisor navigates to `/reports`
- **THEN** the system renders the reports page without error

### Requirement: App shell with sidebar navigation
The system SHALL render a persistent sidebar showing navigation links filtered by the current user's role. The sidebar SHALL highlight the active route.

#### Scenario: Admin sees all navigation items
- **WHEN** an Admin is logged in
- **THEN** the sidebar shows: Dashboard, Categorías, Productos, Ingresos, Egresos, Bajas, Ajustes, Kardex, Reportes, Auditoría, Usuarios, Parámetros

#### Scenario: Operator sees only operational items
- **WHEN** an Operator is logged in
- **THEN** the sidebar shows: Dashboard, Categorías, Productos, Ingresos, Egresos, Bajas, Ajustes

#### Scenario: Supervisor sees read-only items
- **WHEN** a Supervisor is logged in
- **THEN** the sidebar shows: Dashboard, Productos, Kardex, Reportes, Auditoría

### Requirement: Top bar with user info and logout
The system SHALL display a top navigation bar showing the current user's name and role, and a logout button.

#### Scenario: User clicks logout
- **WHEN** the user clicks the logout button
- **THEN** the system calls `POST /api/v1/auth/logout`, clears local tokens, and redirects to `/login`

### Requirement: API client configuration
The system SHALL configure Axios with a base URL pointing to the backend, automatically attaching the Bearer token to all requests, and handling 401 responses by attempting a token refresh before retrying.

#### Scenario: Access token expires mid-session
- **WHEN** a request returns 401 and a refresh token is available
- **THEN** the system silently refreshes the access token and retries the original request

#### Scenario: Refresh token also invalid
- **WHEN** both access and refresh tokens are invalid
- **THEN** the system redirects the user to `/login`
