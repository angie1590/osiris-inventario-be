## ADDED Requirements

### Requirement: Form fields have visible, associated labels
Every form input, select, and textarea SHALL have a visible `<label>` element that is programmatically associated via `htmlFor`/`id`. Labels SHALL use `text-sm font-medium` and meet WCAG AA contrast.

#### Scenario: Label is always visible
- **WHEN** a form field renders
- **THEN** a visible label SHALL appear above or beside the input

#### Scenario: Required fields are marked
- **WHEN** a form field is required
- **THEN** an asterisk (`*`) SHALL appear next to the label with `aria-hidden="true"` so screen readers do not read it redundantly

### Requirement: Inputs have consistent visual appearance
All text inputs, number inputs, and textareas SHALL have a consistent height (minimum 36px), a visible border (`border-input`), a background (`bg-background`), and a visible focus ring (`focus-visible:ring-2`).

#### Scenario: Input border is visible
- **WHEN** an input renders in its default state
- **THEN** it SHALL have a visible border that provides contrast against both white and light gray backgrounds

#### Scenario: Focus ring appears on keyboard interaction
- **WHEN** an input receives focus via keyboard
- **THEN** a clearly visible focus ring SHALL appear around the input

### Requirement: Inline field-level error messages
When a form field has a validation error, an error message SHALL appear directly below the field in red (`text-destructive`). The input SHALL receive `aria-invalid="true"` and `aria-describedby` pointing to the error message element.

#### Scenario: Error message appears below field
- **WHEN** a form field has a validation error
- **THEN** the error message SHALL render immediately below the input, in red, within the same visual group as the label and input

#### Scenario: Input is marked invalid for assistive technology
- **WHEN** a form field has a validation error
- **THEN** the input element SHALL have `aria-invalid="true"` and `aria-describedby` referencing the error message id

### Requirement: Form sections use visual grouping
Multi-section forms SHALL visually group related fields using cards or titled sections with consistent internal padding (`p-4` or `p-6`), a separating border, and a section heading.

#### Scenario: Form sections are distinguishable
- **WHEN** a form has multiple logical sections (e.g., "Información general" and "Precio")
- **THEN** each section SHALL be visually separated with a card border and a section title

### Requirement: Form layout does not cause overlapping elements
Form fields SHALL not overlap with each other or with any dropdown that opens from within the form. The form grid SHALL reserve space for error messages to avoid layout shifts.

#### Scenario: Error message does not shift layout
- **WHEN** a validation error appears on a field
- **THEN** the error message SHALL appear below the input without pushing other fields out of alignment unexpectedly
