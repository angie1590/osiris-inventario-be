## ADDED Requirements

### Requirement: Edit dynamic attribute metadata
The system SHALL allow administrators to edit the `name`, `is_required`, and list `options` of a dynamic attribute at any time. Changes SHALL be audited.

#### Scenario: Edit attribute name
- **WHEN** an admin submits an attribute edit with a new name
- **THEN** `PATCH /api/v1/attributes/:id` updates the attribute record; subsequent product attribute values display the new name

#### Scenario: Edit is_required flag
- **WHEN** an admin changes `is_required` from `false` to `true`
- **THEN** the change is persisted; the product form marks the attribute as required going forward

#### Scenario: Audit on attribute edit
- **WHEN** any attribute field is updated
- **THEN** an audit entry is created with `action=UPDATE`, `entity_type="attribute"`, and a diff of changed fields

---

### Requirement: Safe data type change for attributes
The system SHALL allow changing an attribute's `data_type` only when no `ProductAttributeValue` rows reference the attribute. If rows exist, the endpoint SHALL return a structured error.

#### Scenario: Type change with no product values
- **WHEN** an admin changes `data_type` and no products have values for this attribute
- **THEN** the type is updated and the change is audited

#### Scenario: Type change blocked by existing values
- **WHEN** an admin attempts to change `data_type` and at least one `ProductAttributeValue` references this attribute
- **THEN** the system returns 422 with `code: "ATTRIBUTE_TYPE_CHANGE_BLOCKED"` and `message` explaining that the attribute is in use by N products

---

### Requirement: Deactivate attribute instead of physical delete
The system SHALL provide a deactivate action for attributes. A deactivated attribute is not shown in product forms for new products but existing product attribute values are preserved. Physical deletion SHALL be blocked when any `ProductAttributeValue` row references the attribute.

#### Scenario: Deactivate attribute in use
- **WHEN** an admin deactivates an attribute that has product values
- **THEN** the attribute `is_active` is set to `false`; existing product attribute values are preserved; the attribute no longer appears in the new product form for its category

#### Scenario: Delete blocked when in use
- **WHEN** an admin attempts to delete an attribute that has at least one `ProductAttributeValue` row
- **THEN** the system returns 409 with `code: "ATTRIBUTE_IN_USE"` and suggests deactivation instead

#### Scenario: Reactivate attribute
- **WHEN** an admin reactivates a deactivated attribute
- **THEN** `is_active` is set to `true` and the attribute reappears in product forms for its category

---

### Requirement: Attribute management UI shows edit and deactivate actions
The attributes list page SHALL include an Edit button (opens edit form) and a Deactivate/Reactivate toggle per row, in addition to the existing Create action.

#### Scenario: Edit button opens form
- **WHEN** the admin clicks Edit on an attribute row
- **THEN** a form (modal or drawer) opens with current attribute values pre-populated

#### Scenario: Deactivate button with confirmation
- **WHEN** the admin clicks Deactivate on an active attribute
- **THEN** a confirmation dialog appears; on confirm, the attribute is deactivated and the row reflects the inactive state

#### Scenario: Type change warning in UI
- **WHEN** the admin changes the `data_type` select in the edit form and the attribute has existing product values
- **THEN** the form shows an inline warning "Este atributo tiene valores en productos existentes. Cambiar el tipo puede causar inconsistencias." before the user submits
