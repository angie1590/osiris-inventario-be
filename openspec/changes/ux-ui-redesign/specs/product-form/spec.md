## ADDED Requirements

### Requirement: Product creation and edit as dedicated page or drawer
The product creation and edit form SHALL be rendered as a dedicated page (or a full-height drawer for small edits) and SHALL NOT be placed inside a small modal. The form SHALL be scrollable when the field count exceeds the viewport height.

#### Scenario: Create product
- **WHEN** the user navigates to create a new product
- **THEN** a full-page form opens with all fields visible and scrollable; no content is hidden behind an overlay

#### Scenario: Edit product
- **WHEN** the user opens a product for editing
- **THEN** the same full-page or drawer form appears with existing values pre-populated

---

### Requirement: Product form layout with logical sections
The product form SHALL organize fields into clearly labeled visual sections. At minimum: "Información general" (name, description, SKU), "Clasificación" (category via TreeSelector, unit), "Inventario" (stock mínimo; stock actual as read-only), "Precio" (PVP), "Atributos" (dynamic attributes), "Estado" (active/inactive).

#### Scenario: Section headings visible
- **WHEN** the product form renders
- **THEN** each section has a visible heading that separates its content from adjacent sections

#### Scenario: Stock actual is read-only
- **WHEN** the product form renders the stock actual field
- **THEN** it is displayed as a read-only informational value, not an editable input

#### Scenario: Category uses TreeSelector
- **WHEN** the user opens the category field on the product form
- **THEN** the TreeSelector component renders (not a flat dropdown); the full category path is shown after selection

---

### Requirement: Required field indicators on product form
All required product fields SHALL display the asterisk (`*`) indicator per the `ux-validation` spec. The form note about required fields SHALL be visible near the top.

#### Scenario: Nombre is required
- **WHEN** the product form renders
- **THEN** the Nombre field shows "Nombre *" as its label

#### Scenario: Submit without nombre
- **WHEN** the user submits the product form without entering a name
- **THEN** the Nombre field shows a red border and an inline error "El nombre del producto es obligatorio"

---

### Requirement: Dynamic attributes rendered per product category
When a category is selected, the system SHALL query and display the dynamic attributes associated with that category hierarchy. Each attribute is rendered using the appropriate control for its data type (text input, number input, date picker, checkbox, select for list types).

#### Scenario: Attributes load after category selection
- **WHEN** the user selects a category in the product form
- **THEN** the system fetches attributes for that category and renders them in the "Atributos" section; a loading indicator is shown during fetch

#### Scenario: Required attribute marked
- **WHEN** a dynamic attribute has `is_required = true`
- **THEN** its label shows the asterisk indicator

#### Scenario: No attributes for category
- **WHEN** the selected category has no associated attributes
- **THEN** the "Atributos" section shows "Esta categoría no tiene atributos definidos"

#### Scenario: Attribute dropdowns do not overlap other fields
- **WHEN** a list-type attribute dropdown opens
- **THEN** it renders using a portal and does NOT visually clip behind adjacent form fields

---

### Requirement: Stock minimum integer/decimal enforcement on product form
The stock mínimo field SHALL respect the `stock_quantity_mode` system parameter. In `integer` mode the field SHALL be a whole-number input; in `decimal` mode it SHALL accept decimals up to the configured precision.

#### Scenario: Integer mode
- **WHEN** `stock_quantity_mode = "integer"` and the user enters a decimal value (e.g., 1.5) for stock mínimo
- **THEN** the field shows a validation error "El stock mínimo debe ser un número entero"

#### Scenario: Decimal mode
- **WHEN** `stock_quantity_mode = "decimal"` and the user enters a decimal value
- **THEN** the value is accepted without error
