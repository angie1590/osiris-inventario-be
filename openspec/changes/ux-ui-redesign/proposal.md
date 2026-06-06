## Why

The current application functions as a basic CRUD but fails as a professional inventory tool: poor contrast, broken date filters that show "select a range" even when dates are loaded, flat dropdowns for hierarchical categories, generic error messages with no actionable detail, duplicate toasts, and no inline form validation. Users working long shifts with thousands of products and documents need a system that reduces errors, minimizes clicks, and communicates clearly when something goes wrong.

## What Changes

- Introduce a Design System with shared tokens (color, spacing, typography) and reusable components (buttons, inputs, tables, modals, toasts, empty/loading/error states) applied consistently across all screens.
- Replace all generic error toasts with inline field-level validation errors and structured backend error responses that identify the exact field and a human-readable explanation.
- Replace all category dropdowns with a hierarchical TreeSelector component (expand/collapse nodes, keyword search, full-path breadcrumb display).
- Redesign the product creation/edit form with logical sections, inline validation, visible required-field indicators (`*`), and no modal-overflow issues.
- Add full edit/deactivate support for dynamic attributes with safe type-change guards.
- Fix date filters across all screens (Audit, Reports, Kardex, Inventory) to auto-execute the initial query when default dates are present and never show contradictory empty states.
- Add login-page inline error feedback (not toast-only).
- Introduce a system parameter to configure whether stock quantities are integers or decimals, applied consistently in forms, validations, and APIs.
- **BREAKING** (backend): All create/update endpoints now return structured `{ code, message, errors: { field: message } }` error responses — any API client that parses raw error strings must be updated.

## Capabilities

### New Capabilities

- `design-system`: Design tokens, shared visual rules, and all reusable UI components (Button, Input, Modal, Drawer, Toast, Table, EmptyState, LoadingState, ErrorState, TreeSelector, Badge, Alert).
- `ux-validation`: Protocol for inline form validation, required-field indicators (`*`), field-level error display, general form error banners, and structured backend error envelope — applies to all forms in the application.
- `category-tree`: Hierarchical tree selector component for browsing, searching, and selecting categories in product forms and category management screens.
- `product-form`: Redesigned product creation and edit flow with sections, dynamic attribute rendering, read-only stock, stock-min integer/decimal enforcement, and accessible layout.
- `attribute-management`: Full lifecycle management for dynamic attributes — create, edit name/type/options/required, deactivate, prevent physical deletion when products are associated, type-change safety guards, audit trail.
- `stock-quantity-config`: System parameter (`stock_quantity_mode`: `integer` | `decimal`) controlling whether stock minimum and quantity fields accept decimals; enforced in frontend controls, Zod schemas, and backend validators.

### Modified Capabilities

- `company-config-ui`: Replace generic "Error al guardar la configuración" toast with field-level inline errors; eliminate duplicate toasts; add required-field `*` indicators; show form-level error banner for non-field errors.
- `company-config`: Return structured `{ code, message, errors }` responses from POST/PATCH `/company`; add field-level validation detail to existing `ValidationAppError`.
- `reports`: Fix date-filter auto-execution — when default date range is present, the report must load immediately without requiring manual "Apply"; add quick-range presets (today, this week, this month, last 30 days).
- `inventory-documents`: Apply new form validation patterns (inline errors, `*` indicators, loading/error/empty states on tables) to Ingresos, Egresos, Bajas, Ajustes creation forms and list views.

## Impact

**Frontend** (`osiris-inventario-fe`):
- New shared components under `src/components/ui/` and `src/components/shared/`.
- Updated Tailwind config / CSS variables for design tokens.
- `CategoriesPage`, `ProductsPage`, product form pages, attribute pages — all refactored.
- All inventory creation pages updated with inline validation.
- Reports, Kardex, Audit pages updated for date filter fix.
- `LoginPage` updated for inline error.
- New `TreeSelector` component replacing all category comboboxes.

**Backend** (`osiris-inventario-be`):
- All validation error responses standardized to `{ code, message, errors }` shape.
- `CompanyService`, `ProductService`, `AttributeService` updated to raise structured errors.
- New `AttributeService` edit/deactivate methods with migration guards.
- New seed entry for `stock_quantity_mode` param.
- Backend validators for decimal vs integer stock quantities.

**Dependencies**: No new packages expected; existing shadcn/ui, Radix UI, React Hook Form, Zod, TanStack Query, and FastAPI/Pydantic cover all requirements.
