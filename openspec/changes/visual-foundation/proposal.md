## Why

Osiris Inventario's current UI is built on a minimal template that produces a broken, unprofessional visual experience: modals lose contrast, dropdowns overlap content incorrectly, z-index is uncontrolled, and forms lack visual hierarchy — making the application look like a prototype rather than an enterprise inventory system. This must be corrected before any additional feature work lands on top of a broken visual base.

## What Changes

- Replace ad-hoc component styling with a centralized design token system (colors, spacing, radius, shadows, z-index scale)
- Rewrite the global layout shell (sidebar + content area) to use consistent max-width, padding, and grid
- Standardize the page structure pattern: page header → optional description → actions → filters → content → states
- Fix modal component: solid white background, high-contrast text/inputs, correct overlay behavior, scroll-safe footer
- Fix dropdown/popover/select components: solid background, border, shadow, max-height + scroll, correct z-index, keyboard-navigable
- Fix button hierarchy: primary / secondary / destructive / ghost / link with full state coverage (hover, focus, disabled, loading)
- Fix form layout: visible labels, consistent input height/border/focus ring, error and hint message display, required indicator
- Fix card/section containers: white background, subtle border, consistent padding and spacing
- Fix toast notifications: positioned above all layers, no duplicates, four visual variants
- Apply base accessibility: keyboard nav, focus-visible, aria labels, escape-to-close on all overlays
- No business logic, API changes, or new inventory features

## Capabilities

### New Capabilities

- `design-system`: Centralized design tokens, z-index scale, spacing scale, and component-level visual standards for the entire frontend
- `global-layout`: Standardized page shell, content container, page header pattern, and responsive grid
- `modal-component`: Corrected modal with solid background, overlay isolation, internal scroll, accessible footer
- `dropdown-component`: Corrected dropdown/popover/select with layering, max-height scroll, keyboard navigation
- `button-component`: Full button hierarchy with all interactive states
- `form-component`: Standardized form layout with labels, inputs, errors, and required indicators
- `card-component`: Consistent card/section container with borders, padding, and spacing

### Modified Capabilities

- `company-config-ui`: Visual treatment of the company config form aligns with the new form and card component standards (no requirement changes, implementation update only)

## Impact

- Frontend only: `src/index.css`, `src/components/ui/`, `src/components/shared/`, `src/layouts/`, `src/pages/` (styling/structure only)
- No backend changes
- No API contract changes
- No business logic changes
- Existing Tailwind CSS + shadcn/ui component library remains; tokens and class conventions are extended, not replaced
