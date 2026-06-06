## ADDED Requirements

### Requirement: Button visual hierarchy
The application SHALL implement four distinct button variants with clear visual differentiation: primary (filled, brand color), secondary/outline (border only), destructive (red), and ghost (no border, low contrast until hover).

#### Scenario: Primary action is visually prominent
- **WHEN** a page or modal renders with a primary action button (e.g., "Guardar", "Crear", "Confirmar")
- **THEN** it SHALL use the primary variant and be visually the most prominent button on the screen

#### Scenario: Cancel is secondary
- **WHEN** a form or modal renders a cancel action alongside a primary action
- **THEN** the cancel button SHALL use the outline or ghost variant and be visually subordinate to the primary action

#### Scenario: Destructive action is red
- **WHEN** a button triggers an irreversible destructive action (e.g., "Eliminar")
- **THEN** it SHALL use the destructive variant with red background or red text

### Requirement: Button interactive states
All button variants SHALL have distinct visual states for hover, focus-visible, disabled, and loading.

#### Scenario: Disabled button is visually inactive
- **WHEN** a button has `disabled` attribute
- **THEN** it SHALL render with reduced opacity and SHALL NOT respond to hover effects

#### Scenario: Loading button shows spinner
- **WHEN** a button is in loading state (e.g., form submitting)
- **THEN** it SHALL display a spinner icon and SHALL be disabled to prevent double-click

#### Scenario: Focus ring is visible on keyboard navigation
- **WHEN** a button receives focus via keyboard Tab
- **THEN** it SHALL display a visible focus ring meeting WCAG 2.1 AA requirements

### Requirement: Button does not overlap dropdowns
Buttons SHALL never be permanently obscured by open dropdowns or popovers.

#### Scenario: Button is accessible when dropdown is open
- **WHEN** a dropdown opens near a button
- **THEN** the dropdown SHALL not permanently cover the button area; the button SHALL be accessible after the dropdown closes
