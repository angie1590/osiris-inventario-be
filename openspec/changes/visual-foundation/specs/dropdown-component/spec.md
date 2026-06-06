## ADDED Requirements

### Requirement: Dropdown content has solid background and elevation
All dropdown, select, popover, and combobox content panels SHALL render with a solid white `bg-popover` background, a visible border, and a shadow (`shadow-md`). They SHALL never appear transparent or without visual separation from underlying content.

#### Scenario: Dropdown is visually distinct from background
- **WHEN** a dropdown or select opens over page content
- **THEN** the dropdown panel SHALL have a solid background, a border, and a shadow making it clearly distinct from the underlying content

### Requirement: Dropdown uses correct z-index layer
All dropdown/popover/select content SHALL render at `--z-dropdown` or higher. When inside a modal, dropdown content SHALL render at a z-index higher than `--z-modal-content`.

#### Scenario: Dropdown does not appear behind page content
- **WHEN** a dropdown opens on a page
- **THEN** it SHALL appear in front of all other page content (cards, tables, sticky headers)

#### Scenario: Dropdown inside modal appears above modal
- **WHEN** a dropdown opens inside a modal
- **THEN** it SHALL appear in front of the modal content, not clipped or partially hidden

### Requirement: Dropdown has maximum height with internal scroll
When a dropdown contains more options than fit in the viewport, it SHALL limit its height (max `max-h-64`) and display a scrollbar for overflow content.

#### Scenario: Long option list scrolls
- **WHEN** a select or combobox has more than 8 options
- **THEN** the dropdown panel SHALL constrain to a maximum height and scroll internally

### Requirement: Dropdown is keyboard navigable
Dropdown, select, and combobox components SHALL support keyboard navigation: Arrow keys to move through options, Enter to select, Escape to close, and Tab to leave the control.

#### Scenario: Arrow keys navigate options
- **WHEN** a dropdown is open and the user presses ArrowDown
- **THEN** focus moves to the next option in the list

#### Scenario: Escape closes dropdown
- **WHEN** a dropdown is open and the user presses Escape
- **THEN** the dropdown closes and focus returns to the trigger

### Requirement: Dropdown closes on outside click
Any open dropdown, select, or popover SHALL close when the user clicks outside its content area.

#### Scenario: Outside click closes dropdown
- **WHEN** a dropdown is open and the user clicks anywhere outside the dropdown
- **THEN** the dropdown SHALL close
