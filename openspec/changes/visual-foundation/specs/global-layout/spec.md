## ADDED Requirements

### Requirement: Consistent content container
The application layout shell SHALL constrain the main content area to a maximum width with consistent horizontal and vertical padding. No page SHALL need to define its own outer padding or max-width.

#### Scenario: Content is contained on wide screens
- **WHEN** the application renders on a screen wider than 1280px
- **THEN** the content area SHALL NOT exceed `max-w-screen-xl` and SHALL remain horizontally centered

#### Scenario: Consistent vertical rhythm
- **WHEN** any page renders
- **THEN** the top padding of the content area SHALL be uniform across all pages (at minimum `py-6`)

### Requirement: Standard page structure
Every page in the application SHALL follow the structure: (1) page header with title, (2) optional description, (3) primary action buttons, (4) optional filter bar, (5) main content, (6) loading/empty/error states.

#### Scenario: Page header is always visible
- **WHEN** a page renders
- **THEN** a visible `<h1>` page title SHALL appear at the top of the content area above all other page content

#### Scenario: Primary action is top-right
- **WHEN** a page has a primary action (e.g., "Nuevo producto")
- **THEN** the action button SHALL appear in the same row as the page title, aligned to the right

#### Scenario: Filter bar is visually separated
- **WHEN** a page has filters
- **THEN** the filter controls SHALL appear in a distinct card or bar below the header and above the content table

### Requirement: Responsive layout for laptop and desktop
The layout SHALL be functional and legible on viewport widths from 1024px upward without horizontal scrolling.

#### Scenario: No horizontal overflow on laptop
- **WHEN** the application renders at 1024px viewport width
- **THEN** no content SHALL overflow horizontally or require horizontal scrolling
