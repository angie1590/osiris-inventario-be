## ADDED Requirements

### Requirement: TreeSelector component for hierarchical category navigation
The system SHALL provide a `<TreeSelector>` component that accepts a flat list of categories (with `id`, `name`, `parent_id`) and renders them as an expandable, searchable tree. The component SHALL replace all flat `<Select>` dropdowns used for category selection throughout the application.

#### Scenario: Render root categories
- **WHEN** the TreeSelector renders with a populated category list
- **THEN** root categories (those with `parent_id = null`) are shown as top-level items, each with an expand/collapse control if they have children

#### Scenario: Expand and collapse nodes
- **WHEN** the user clicks the expand control on a parent category
- **THEN** its direct children become visible; clicking again collapses them

#### Scenario: Select a category
- **WHEN** the user clicks a leaf or branch category name
- **THEN** `onChange(categoryId)` is called with the selected id; the trigger button shows the full path (e.g., "Tecnología / Computadoras / Laptops")

#### Scenario: Clear selection
- **WHEN** the user clicks the clear icon on a TreeSelector that has a value
- **THEN** `onChange(null)` is called and the trigger button reverts to the placeholder text

---

### Requirement: Keyword search within TreeSelector
The TreeSelector SHALL include a text input that filters the category tree in real-time. Matching nodes and their ancestors SHALL remain visible; non-matching subtrees SHALL be hidden.

#### Scenario: Keyword match
- **WHEN** the user types "laptop" in the search input
- **THEN** only category nodes whose name contains "laptop" (case-insensitive) are shown, along with their ancestor path so context is preserved

#### Scenario: No match
- **WHEN** the search term matches no categories
- **THEN** the tree area shows "Sin resultados" and the clear search button is available

#### Scenario: Clear search
- **WHEN** the user clears the search input
- **THEN** the full tree is restored to its default expand/collapse state

---

### Requirement: Keyboard navigation inside TreeSelector
The TreeSelector SHALL be fully operable via keyboard.

#### Scenario: Open and navigate
- **WHEN** the trigger button is focused and the user presses Enter or Space
- **THEN** the tree popover opens and focus moves to the search input

#### Scenario: Arrow navigation
- **WHEN** the tree is open and the user presses ArrowDown / ArrowUp
- **THEN** focus moves between visible tree nodes

#### Scenario: Select with keyboard
- **WHEN** a tree node is focused and the user presses Enter
- **THEN** that category is selected, same behavior as clicking

#### Scenario: Close with Escape
- **WHEN** the tree popover is open and the user presses Escape
- **THEN** the popover closes and focus returns to the trigger button

---

### Requirement: Full-path breadcrumb display after selection
After a category is selected, the TreeSelector trigger SHALL display the full ancestry path of the selected category, not just the leaf name.

#### Scenario: Display full path
- **WHEN** the user selects "Laptops" which is under "Computadoras" → "Tecnología"
- **THEN** the trigger displays "Tecnología / Computadoras / Laptops"

#### Scenario: Root category selected
- **WHEN** the user selects a root category with no parent
- **THEN** the trigger displays only that category's name with no separator

---

### Requirement: TreeSelector does not overlap adjacent form fields
The TreeSelector popover SHALL use a portal-based rendering strategy to ensure it always renders above other content and does not visually clip or overlap adjacent form fields in an incorrect way.

#### Scenario: Popover position
- **WHEN** the TreeSelector opens near the bottom of the viewport
- **THEN** the popover repositions upward if needed to remain fully visible

#### Scenario: z-index layering
- **WHEN** the TreeSelector is open inside a modal or drawer
- **THEN** the popover renders above the modal overlay, not behind it
