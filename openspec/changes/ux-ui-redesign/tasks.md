## 1. Backend — Structured Error Responses

- [x] 1.1 Extend `AppError` base class with optional `field_errors: dict[str, str]` property
- [x] 1.2 Update global exception handler in `app/core/exception_handlers.py` to serialize `field_errors` into `{ code, message, errors }` envelope on 422 responses
- [x] 1.3 Update `CompanyService.create()` and `.update()` to raise structured errors with field-level detail (razon_social, ruc, email)
- [x] 1.4 Add tests: `POST /company` with missing fields returns `errors` object with per-field messages

## 2. Backend — Attribute Management

- [x] 2.1 Add `is_active` column to `attributes` table via Alembic migration (default `true`)
- [x] 2.2 Implement `AttributeService.update()`: allow editing `name`, `is_required`, list options; block `data_type` change if `ProductAttributeValue` rows exist (return `ATTRIBUTE_TYPE_CHANGE_BLOCKED`)
- [x] 2.3 Implement `AttributeService.deactivate()` / `reactivate()`: toggle `is_active`; block physical delete if values exist (return `ATTRIBUTE_IN_USE`)
- [x] 2.4 Add `PATCH /api/v1/attributes/:id` endpoint (admin only) wired to `AttributeService.update()`
- [x] 2.5 Add `POST /api/v1/attributes/:id/deactivate` and `/reactivate` endpoints (admin only)
- [x] 2.6 Exclude `is_active = false` attributes from product form attribute queries
- [x] 2.7 Add audit logging (UPDATE action) in `AttributeService.update()`
- [x] 2.8 Add tests: type change blocked when values exist, deactivate preserves values, delete blocked

## 3. Backend — Stock Quantity Mode

- [x] 3.1 Add `stock_quantity_mode` seed entry in `scripts/seed.py` (key=`stock_quantity_mode`, value=`integer`)
- [x] 3.2 Add FastAPI dependency `get_stock_mode()` that reads `stock_quantity_mode` from SystemParams
- [x] 3.3 Add validator in `ProductService` that rejects decimal `stock_min` when mode is `integer`
- [x] 3.4 Add tests: decimal `stock_min` rejected in integer mode, accepted in decimal mode

## 4. Frontend — Design System Foundation

- [x] 4.1 Audit `globals.css` — verify all color, radius, and spacing tokens are present; add any missing (`--warning`, `--success`, `--info` variants)
- [x] 4.2 Create `<FormField>` wrapper component (`src/components/shared/FormField.tsx`): renders label with optional `*`, slot for input, inline error paragraph, wires `aria-invalid` + `aria-describedby`
- [x] 4.3 Create `<EmptyState>` component (`src/components/shared/EmptyState.tsx`): icon + heading + optional description + optional action button
- [x] 4.4 Create `<ErrorState>` component (`src/components/shared/ErrorState.tsx`): error icon + message + "Reintentar" button
- [x] 4.5 Extend `<DataTable>` (or create if missing) with `isLoading`, `isError`, `onRetry` props that render skeleton, `<ErrorState>`, and `<EmptyState>` uniformly
- [x] 4.6 Add toast deduplication: wrap `useToast` or configure the Toaster to suppress exact-duplicate messages within a 3-second window

## 5. Frontend — TreeSelector Component

- [x] 5.1 Create `<TreeSelector>` component (`src/components/shared/TreeSelector.tsx`): accepts flat `categories` array, renders expandable tree with search, shows full-path breadcrumb in trigger
- [x] 5.2 Implement keyword search inside TreeSelector: filter nodes and keep ancestors visible
- [x] 5.3 Add keyboard navigation (ArrowUp/Down, Enter to select, Escape to close)
- [x] 5.4 Use Radix UI `Popover` with portal rendering for correct z-index inside modals/drawers
- [x] 5.5 Replace all flat `<Select>` category dropdowns in `CategoriesPage` (parent selector) with `<TreeSelector>`
- [x] 5.6 Replace all flat `<Select>` category dropdowns in product form and product filters with `<TreeSelector>`

## 6. Frontend — Login Inline Error

- [x] 6.1 Update `LoginPage.tsx`: render an inline error `<Alert>` inside the form when authentication fails (in addition to or instead of toast-only)
- [x] 6.2 Clear the inline error when the user modifies credentials and re-submits

## 7. Frontend — Company Config UX Improvements

- [x] 7.1 Update `AdminCompanyPage.tsx` to use `<FormField>` wrapper for all fields (adds `*` and inline errors)
- [x] 7.2 Add form-level error banner (`<Alert variant="destructive">`) at the top of the form, shown when submit fails
- [x] 7.3 Map backend `errors` object to RHF `setError()` so field-level backend errors render inline
- [x] 7.4 Replace the generic toast message "Error al guardar la configuración" with backend-provided `message` text
- [x] 7.5 Add submit-button loading + disable state (already partially done — verify it prevents double-click)

## 8. Frontend — Product Form Redesign

- [x] 8.1 Migrate product create/edit out of modal into a dedicated page or full-height drawer in `ProductsPage` / `ProductDetailPage`
- [x] 8.2 Organize form into sections: Información general, Clasificación (with TreeSelector), Inventario (stock mínimo editable, stock actual read-only), Precio, Atributos, Estado
- [x] 8.3 Apply `<FormField>` wrapper to all product fields with `*` on required fields
- [x] 8.4 Render dynamic attributes with correct control per `data_type` (input, number, date, checkbox, select)
- [x] 8.5 Add stock mínimo integer/decimal enforcement: read `stock_quantity_mode` param, apply correct Zod rule
- [x] 8.6 Show loading skeleton while attributes are fetching after category selection
- [x] 8.7 Show "Esta categoría no tiene atributos definidos" when attributes array is empty

## 9. Frontend — Attribute Management UI

- [x] 9.1 Add Edit button per row in the attributes list; open a `<Drawer>` or modal with the edit form pre-populated
- [x] 9.2 Edit form uses `<FormField>` wrapper; for `data_type` change, show inline warning if attribute has product values
- [x] 9.3 Wire edit form to `PATCH /api/v1/attributes/:id` and invalidate attributes query on success
- [x] 9.4 Add Deactivate/Reactivate toggle button per row with a confirmation dialog
- [x] 9.5 Wire deactivate/reactivate to `/deactivate` and `/reactivate` endpoints

## 10. Frontend — Date Filter Fix (Reports, Audit, Kardex)

- [x] 10.1 Update `ReportsPage` and sub-report pages: initialize date state to current-month range; set TanStack Query `enabled: true` on mount so the first load executes automatically
- [x] 10.2 Update `AuditPage` with same auto-execute pattern
- [x] 10.3 Update `KardexPage` with same auto-execute pattern
- [x] 10.4 Add quick-range preset buttons (Hoy, Esta semana, Este mes, Últimos 30 días) to report pages with date filters
- [x] 10.5 Ensure visible filter dates always match the query dates (no stale display after apply)

## 11. Frontend — Inventory Document Forms

- [x] 11.1 Update `IngresoNewPage`, `EgresoNewPage`, `BajaNewPage`, `AjusteNewPage` to use `<FormField>` wrapper for all fields
- [x] 11.2 Add inline error display and map backend `errors` to RHF `setError()` on each form
- [x] 11.3 Update list pages (`IngresosPage`, `EgresosPage`, `BajasPage`, `AjustesPage`) to use `<DataTable>` with loading/empty/error states

## 12. Tests

- [x] 12.1 Backend: add tests for `ATTRIBUTE_TYPE_CHANGE_BLOCKED` and `ATTRIBUTE_IN_USE` errors
- [x] 12.2 Backend: add tests for `stock_quantity_mode` integer enforcement on product endpoints
- [x] 12.3 Backend: add tests for structured error envelope on company config endpoints
- [x] 12.4 Frontend: add unit tests for `<TreeSelector>` search and keyboard navigation
- [x] 12.5 Frontend: add unit tests for `<FormField>` required indicator and error display
