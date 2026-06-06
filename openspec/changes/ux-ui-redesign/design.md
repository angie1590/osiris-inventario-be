## Context

Osiris Inventario is a React 18 + Vite + TypeScript frontend backed by FastAPI + PostgreSQL. The current codebase uses shadcn/ui components, Tailwind CSS v3, React Hook Form + Zod, TanStack Query v5, and React Router v6. The design foundation (component library, tokens) already exists as shadcn primitives but lacks systematic application: each page defines its own styles in isolation, error handling is scattered, and category selection uses plain `<Select>` components with no hierarchy.

The redesign is a transversal change — no single feature, but a series of foundational improvements applied uniformly across all screens. Backend involvement is limited to error-response shaping and two new service methods (attribute edit, stock-mode validation).

## Goals / Non-Goals

**Goals:**
- Establish CSS variable tokens for all colors, spacing, and typography, used by every component.
- Enforce a single `FormField` pattern for input + label + required indicator + inline error message everywhere.
- Replace all category `<Select>` components with a single `TreeSelector` component.
- Return structured `{ code, message, errors }` from all backend create/update endpoints.
- Fix date filters to auto-execute on mount when default values are present.
- Add edit/deactivate to dynamic attributes with safety guards.
- Add `stock_quantity_mode` system param enforced in FE and BE.
- Improve login error visibility to be inline, not toast-only.

**Non-Goals:**
- Visual rebrand (no new logo, no color palette change beyond fixing contrast).
- Mobile/tablet layout (only laptop + desktop required).
- Real-time collaboration or WebSocket features.
- Migrating off shadcn/ui or Tailwind to a different library.
- Changing authentication mechanism.

## Decisions

### D1: Design tokens via Tailwind CSS variables

All color, spacing, and radius values come from CSS custom properties already declared in `globals.css` (`--primary`, `--muted`, `--destructive`, etc.). No new token library (no Style Dictionary, no Tokens Studio). Tailwind utility classes remain the build target; `cn()` stays as the merge utility.

**Why not a separate token package**: Zero new dependencies; the existing Tailwind + CSS variables pattern already works and shadcn/ui components already reference these tokens.

### D2: Single `FormField` wrapper component

Introduce `<FormField label required error={...}>` as a thin wrapper that renders:
- `<label>` with optional `*` (red, `text-destructive`)
- `<slot>` for any input control
- `<p className="text-xs text-destructive">` for inline error
- `aria-invalid` and `aria-describedby` wiring on the input

All forms across the app are updated to use this wrapper instead of ad-hoc `Label + Input + error paragraph` patterns.

**Why not React Hook Form's `<FormItem>`**: The project already has RHF + Zod. The `FormField` wrapper is a thin presentation layer on top of RHF's `register()`/`Controller` — compatible, not a replacement.

### D3: TreeSelector is a headless-controlled component backed by the existing categories API

`<TreeSelector value onChange categories={...} />` accepts the flat category tree returned by `GET /categories` (which already includes `parent_id`) and renders it as an expandable tree. Internal state: set of expanded node IDs + search string. On selection, it calls `onChange(categoryId)` and shows the full path (e.g., "Tecnología / Computadoras / Laptops") in a button-like trigger.

**Alternatives considered**:
- Third-party tree library (react-arborist, rc-tree): adds a dependency; our tree is read-only selection only, so a custom 80-line component is sufficient.
- Cascading selects (level 1 → level 2 → level 3): fails at arbitrary depth and poor keyboard UX.

### D4: Structured backend error envelope

All `ValidationAppError` raises in services and all Pydantic validation errors (422) are caught by a single FastAPI exception handler and re-serialized as:

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Human-readable summary.",
  "errors": { "field_name": "Field-specific message." }
}
```

HTTP status remains 422. Existing `AppError` base class already carries `code` + `message`; we add an optional `field_errors: dict[str, str]` property. The global exception handler already exists in `app/core/exception_handlers.py` — it is extended to serialize `field_errors` into the response.

**Why not per-endpoint try/except**: One central handler is already the pattern; extending it avoids N identical error-shaping blocks.

### D5: Date filter auto-execution via `useEffect` + `initialFilters` flag

Each page with a date filter initializes TanStack Query with `enabled: true` from mount (not waiting for a user click). The date range state is initialized from `defaultFilters` (e.g., current month). The "Apply" button only re-fires the query when the user manually changes dates. This eliminates the "select a date range" empty state shown even when dates are already populated.

**Why not always-on `refetchOnMount`**: Pages like Audit can have expensive queries; we want deliberate re-fetch on filter change but automatic first load with defaults.

### D6: Attribute editing — safe type-change rule

Attributes can be edited (name, `is_required`, list options) freely. Changing `data_type` is blocked if any `ProductAttributeValue` rows reference this attribute. The check runs as a pre-condition in `AttributeService.update()` and returns a structured error if blocked. If no rows exist, the type change is allowed.

**Why not soft-lock all type changes**: Newly created attributes with no products should be freely correctable without a migration ceremony.

### D7: `stock_quantity_mode` as a SystemParam

A new `SystemParam` row `stock_quantity_mode` with values `integer` | `decimal` controls:
- Frontend: Zod schema for stock_min uses `z.number().int()` vs `z.number()` based on a cached query of this param.
- Backend: A FastAPI dependency `get_stock_mode()` reads the param and a Pydantic validator checks incoming `stock_min` values accordingly.
- Seed: default value `"integer"`.

**Why SystemParam not an env var**: Consistent with how other operational settings (doc_number_prefix, etc.) are managed; allows runtime change by admin without redeployment.

## Risks / Trade-offs

- **Large surface area**: This change touches many files. Risk of regressions in untouched paths. Mitigation: implement capability-by-capability, run existing test suite after each backend change.
- **TreeSelector performance with large trees**: If categories grow to 1000+ nodes, the in-memory tree rendered with React could be slow. Mitigation: virtualize list if node count exceeds 200 (use `react-virtual` or simple `slice()`-based lazy expand). Defer until real data shows the problem.
- **Structured error envelope is a breaking change**: API consumers that parse raw error strings (existing `catch` blocks in hooks) must be updated. Mitigation: all FE `catch` blocks are updated in the same change; no external API consumers exist yet.
- **Attribute type-change guard**: If a category has hundreds of products, the `EXISTS` check is fast (index on `product_attribute_values.attribute_id`). But we rely on the index existing. Mitigation: confirm index in Alembic migration for this change.

## Migration Plan

1. Backend first: extend error handler → update service raises → add `attribute_management` endpoints → add `stock_quantity_mode` seed and validator.
2. Frontend foundation: CSS token audit → `FormField` component → TreeSelector component.
3. Frontend screens: Update screens in order — Login → Company Config → Categories → Products → Attributes → Inventory → Reports/Audit.
4. No data migration required; no schema changes (attribute editing is service-level; stock mode is a new SystemParam row).

## Open Questions

- Should `stock_quantity_mode` be applied to existing `stock_min` data retroactively (e.g., truncate decimals if switching to integer)? Tentative answer: no — only affect new inputs; leave existing data as-is and document.
- Should the TreeSelector lazy-load children (API call per expand)? Current `GET /categories` returns the full flat list, which is sufficient up to ~500 categories. Defer lazy load.
