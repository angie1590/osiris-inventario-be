## ADDED Requirements

### Requirement: Category tree view
The system SHALL display categories in a collapsible tree structure at `/categories`. Each node SHALL show the category name and a count of direct children.

#### Scenario: Root categories displayed
- **WHEN** the user navigates to `/categories`
- **THEN** the system loads and renders all root categories from `GET /api/v1/categories`

#### Scenario: Expanding a category
- **WHEN** the user clicks the expand arrow on a category
- **THEN** its direct children are shown indented below it

### Requirement: Category CRUD
Admins and Operators SHALL be able to create, edit, and soft-delete categories. Supervisors see read-only view.

#### Scenario: Create category
- **WHEN** an Admin clicks "Nueva Categoría" and submits the form
- **THEN** the system calls `POST /api/v1/categories` and refreshes the tree

#### Scenario: Delete category with active children
- **WHEN** a user tries to delete a category that has active subcategories
- **THEN** the system shows an error toast "No se puede eliminar una categoría con subcategorías activas"

### Requirement: Category attribute management
Admins SHALL be able to manage custom attributes for each category, with attribute types: text, integer, decimal, date, boolean, select.

#### Scenario: Add attribute to category
- **WHEN** an Admin opens a category detail and adds an attribute with type "select"
- **THEN** the form shows an additional field to enter the allowed options

#### Scenario: Inherited attributes shown
- **WHEN** a user views a subcategory's attributes
- **THEN** inherited attributes from parent categories are shown with an "Heredado" badge and are not editable

### Requirement: Product list with filters
The system SHALL display a paginated product list at `/products` with filters: name (text search), category (dropdown), status (active/inactive), bajo_stock (checkbox).

#### Scenario: Filter by low stock
- **WHEN** the user checks "Solo bajo stock"
- **THEN** only products where `stock_actual <= stock_minimo` are shown

#### Scenario: Pagination via cursor
- **WHEN** the user clicks "Siguiente página"
- **THEN** the system calls the API with the last product's id as cursor

### Requirement: Product create and edit form
Operators and Admins SHALL be able to create and edit products. The form SHALL dynamically render custom attribute fields based on the selected category.

#### Scenario: Custom attribute fields rendered
- **WHEN** the user selects a category with custom attributes
- **THEN** the form dynamically shows the required attribute fields with the correct input type

#### Scenario: Required attribute not filled
- **WHEN** the user tries to save without filling a required attribute
- **THEN** the form shows inline validation error per field

#### Scenario: stock_actual not editable
- **WHEN** the user opens the edit product form
- **THEN** the `stock_actual` field is displayed as read-only, not editable

### Requirement: Product detail view
The system SHALL show a product detail page including current stock, minimum stock, bajo_stock badge, all attribute values, and a link to the product's Kardex.

#### Scenario: Bajo stock badge shown
- **WHEN** a product has `stock_actual <= stock_minimo`
- **THEN** the detail page shows a red "Bajo Stock" badge
