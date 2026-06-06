## ADDED Requirements

### Requirement: Modal has solid white background
The modal content box SHALL render with a solid, opaque background color (`bg-background` / white). No darkening, tinting, or reduced opacity SHALL be applied to the modal content area due to the overlay.

#### Scenario: Modal content is legible when open
- **WHEN** a modal is open
- **THEN** all text, labels, and inputs inside the modal SHALL be rendered at full opacity with high contrast against the white modal background

#### Scenario: Overlay does not affect modal content
- **WHEN** the modal overlay (`bg-black/50`) renders
- **THEN** the overlay SHALL be a sibling of the modal content in the DOM (not a parent), so it darkens only the page behind the modal

### Requirement: Modal overlay uses correct z-index
The modal overlay SHALL render at `--z-modal-overlay` and the modal content SHALL render at `--z-modal-content`, ensuring both are above all page content, drawers, and dropdowns that are outside the modal.

#### Scenario: Modal is above all page layers
- **WHEN** a modal opens while a page dropdown or sticky header is visible
- **THEN** the modal SHALL appear in front of all those elements

### Requirement: Modal has defined maximum width and internal scroll
The modal SHALL have a maximum width (no wider than `max-w-2xl` for standard forms) and SHALL support internal scroll for long content, with action buttons always visible in a fixed footer.

#### Scenario: Long modal content scrolls internally
- **WHEN** a modal form content exceeds the viewport height
- **THEN** the content area SHALL scroll internally and the footer with action buttons SHALL remain visible without scrolling

#### Scenario: Action buttons always visible
- **WHEN** a modal is open with a long form
- **THEN** the submit and cancel buttons SHALL be visible without requiring the user to scroll to the bottom of the modal

### Requirement: Modal is keyboard accessible
The modal SHALL trap focus within itself while open, close on Escape key, and return focus to the trigger element on close.

#### Scenario: Escape closes modal
- **WHEN** a modal is open and the user presses Escape
- **THEN** the modal SHALL close

#### Scenario: Focus is trapped inside modal
- **WHEN** a modal is open and the user presses Tab
- **THEN** focus SHALL cycle only through focusable elements inside the modal

### Requirement: Dropdowns inside modal render above modal content
Any dropdown, popover, or select that opens inside a modal SHALL render at a z-index higher than `--z-modal-content` so it is not clipped or hidden behind the modal container.

#### Scenario: Dropdown inside modal is fully visible
- **WHEN** a Select or Popover opens inside a modal
- **THEN** its content panel SHALL be fully visible and not obscured by the modal's own borders or overflow
