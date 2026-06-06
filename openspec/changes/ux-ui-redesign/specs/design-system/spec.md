## ADDED Requirements

### Requirement: Design tokens via CSS custom properties
The system SHALL define all visual design values as CSS custom properties in `globals.css`, including color palette, border radius, spacing scale, typography scale, and shadow levels. All components SHALL reference these tokens exclusively and SHALL NOT define hard-coded color or spacing values.

#### Scenario: Token-based color usage
- **WHEN** any component renders a background, border, or text color
- **THEN** it uses a `--token-name` CSS variable mapped to a Tailwind utility class, not a raw hex or RGB value

#### Scenario: Contrast ratio compliance
- **WHEN** any text is rendered over any background
- **THEN** the contrast ratio SHALL be ≥ 4.5:1 (WCAG AA) for body text and ≥ 3:1 for large text and UI components

---

### Requirement: Shared button component with visual hierarchy
The system SHALL provide a single `<Button>` component with the following variants: `primary`, `secondary`, `destructive`, `ghost`, `link`. Each variant SHALL have distinct visual appearance. Variants SHALL NOT be overridden with ad-hoc classes.

#### Scenario: Primary action button
- **WHEN** a primary action is presented (e.g., "Guardar", "Crear")
- **THEN** it uses the `primary` variant which has a filled background with `bg-primary text-primary-foreground`

#### Scenario: Destructive action button
- **WHEN** a destructive action is presented (e.g., "Eliminar", "Desactivar")
- **THEN** it uses the `destructive` variant which visually differentiates from non-destructive buttons

#### Scenario: Disabled state
- **WHEN** a button is in disabled state
- **THEN** it renders with reduced opacity and `cursor-not-allowed`; it does NOT accept click events

---

### Requirement: Shared input and form control components
The system SHALL provide `<Input>`, `<Textarea>`, `<Select>`, and `<Checkbox>` components with consistent height, border, focus ring, and error state styles. Error state SHALL add a red border and not rely solely on color for accessibility.

#### Scenario: Default input appearance
- **WHEN** an input renders without error
- **THEN** it shows a visible border with `border-input` token and a clear focus ring on focus

#### Scenario: Input error state
- **WHEN** an input has a validation error
- **THEN** the border changes to `border-destructive`, `aria-invalid="true"` is set, and an associated error message element is referenced via `aria-describedby`

---

### Requirement: Table with built-in states
The system SHALL provide a `<DataTable>` component that renders loading, empty, and error states uniformly across all list views.

#### Scenario: Loading state
- **WHEN** data is being fetched
- **THEN** the table area shows a skeleton loader or spinner, not a blank space or stale data

#### Scenario: Empty state
- **WHEN** the query returns zero rows
- **THEN** the table shows an `<EmptyState>` component with a descriptive icon and message relevant to the list context

#### Scenario: Error state
- **WHEN** the data fetch fails
- **THEN** the table shows an `<ErrorState>` component with the error description and a "Reintentar" button

---

### Requirement: Accessible modal and drawer components
The system SHALL provide `<Modal>` and `<Drawer>` components where: focus is trapped inside while open, the Escape key closes them, they have a visible title, content is scrollable independently of the overlay, and the background overlay does NOT reduce the readability of the modal content.

#### Scenario: Focus trap
- **WHEN** a modal or drawer opens
- **THEN** keyboard focus moves inside and Tab key cycles only within the modal or drawer

#### Scenario: Escape to close
- **WHEN** the user presses Escape while a modal or drawer is open
- **THEN** the modal or drawer closes and focus returns to the triggering element

#### Scenario: Overlay legibility
- **WHEN** a modal is open
- **THEN** the modal content area has a solid (not transparent) background and contrast ratio with body text meets WCAG AA

---

### Requirement: Toast notification system without duplicates
The system SHALL show toast notifications for success, info, warning, and error events. The same message SHALL NOT appear more than once concurrently.

#### Scenario: Success notification
- **WHEN** a save or create operation succeeds
- **THEN** a green/success toast appears with a descriptive message and disappears automatically after 4 seconds

#### Scenario: Duplicate prevention
- **WHEN** the same error or event is triggered multiple times in rapid succession
- **THEN** only one toast for that message is shown; additional duplicates are suppressed

#### Scenario: Error toast with context
- **WHEN** an unexpected system error occurs (not a field validation error)
- **THEN** a toast with variant `destructive` appears and includes the error description (not just "Error")
