## ADDED Requirements

### Requirement: Design token CSS custom properties
The system SHALL define all color, spacing, radius, shadow, and z-index values as CSS custom properties in `src/index.css` within `:root`. No component SHALL use hardcoded pixel values or arbitrary Tailwind z-index classes for layering.

#### Scenario: Z-index scale is defined
- **WHEN** a developer needs to set a z-index on any component
- **THEN** they SHALL use one of the named CSS custom property values: `--z-base`, `--z-sticky`, `--z-dropdown`, `--z-drawer`, `--z-modal-overlay`, `--z-modal-content`, `--z-toast`, `--z-critical`

#### Scenario: No arbitrary z-index values
- **WHEN** a component renders with a z-index
- **THEN** that z-index SHALL reference a named token, not a hardcoded number

### Requirement: Semantic color tokens for status variants
The system SHALL define semantic color tokens for success, warning, info, and destructive states beyond the shadcn/ui defaults.

#### Scenario: Status color tokens are available
- **WHEN** a component needs to convey success, warning, info, or error status
- **THEN** it SHALL use the defined `--success`, `--warning`, `--info`, or `--destructive` CSS custom properties

### Requirement: Typographic scale consistency
The system SHALL apply a consistent typographic hierarchy across all pages using defined Tailwind text size classes mapped to specific roles: page title, section title, field label, body text, helper text, and caption.

#### Scenario: Page title is visually prominent
- **WHEN** a page renders its primary heading
- **THEN** it SHALL use the `text-2xl font-bold` class (or defined page-title token)

#### Scenario: Field labels are legible
- **WHEN** a form field label renders
- **THEN** it SHALL use `text-sm font-medium` and meet WCAG AA contrast against its background
