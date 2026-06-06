## Context

Osiris Inventario is a React 18 + Vite + TypeScript SPA using Tailwind CSS v4, shadcn/ui components, and Radix UI primitives. The current codebase applies Tailwind utility classes directly in component files with no shared token constraints, leading to z-index collisions, inconsistent spacing, broken modal contrast, and dropdown layering issues. The backend is unaffected by this change.

Current pain points diagnosed from the UI:
- Modals use a semi-transparent overlay that darkens their own content
- Dropdowns and popovers lack z-index coordination; they can appear under modal overlays
- No defined z-index scale; values are set ad-hoc per component
- Form layout is flat: inputs at the same visual weight as surrounding page content
- Button hierarchy is not enforced; secondary and primary buttons look similar
- Cards have no consistent border/shadow treatment

## Goals / Non-Goals

**Goals:**
- Centralize design tokens: extend `src/index.css` CSS custom properties for colors, radius, shadows, spacing, and a z-index scale
- Standardize the page shell and per-page layout structure
- Correct modal rendering: overlay isolates from modal content, modal is always white/high-contrast
- Correct dropdown/popover/select layering and overflow behavior
- Define and enforce button visual hierarchy
- Standardize form layout: label + input + error/hint treatment
- Standardize card/section containers
- Ensure accessible keyboard behavior and focus styles on all interactive components

**Non-Goals:**
- No backend changes
- No new inventory workflows, business logic, or API contracts
- No replacement of the Tailwind or shadcn/ui library
- No full design system documentation or Storybook
- No dark mode implementation
- No mobile/tablet layout optimization (laptop + desktop only)

## Decisions

### D1: Extend existing tokens, do not replace the library

**Decision:** Add CSS custom properties to `src/index.css` (inside `:root` and `.dark`) for the new z-index scale, shadow scale, and any missing color/spacing tokens. Do not fork shadcn/ui component files unnecessarily.

**Rationale:** Replacing shadcn/ui would require rewriting all component imports and risk wider regressions. Extending tokens is minimal surface area and the library already relies on CSS vars.

**Alternative considered:** Migrate to a pure Tailwind v4 token-only approach without shadcn/ui. Rejected due to migration cost far exceeding the visual goal.

---

### D2: Centralized z-index scale as CSS custom properties

**Decision:** Define a CSS custom property z-index scale in `src/index.css`:

```css
--z-base: 0;
--z-sticky: 10;
--z-dropdown: 100;
--z-drawer: 200;
--z-modal-overlay: 300;
--z-modal-content: 310;
--z-toast: 400;
--z-critical: 500;
```

Replace all ad-hoc `z-` Tailwind classes in components with these variables via `[--z-...]` or `style={{ zIndex: 'var(--z-modal-content)' }}` patterns.

**Rationale:** A named scale makes layering relationships explicit and correctable without hunting through every component file.

**Alternative considered:** Use Tailwind z-index utilities with a defined `tailwind.config` extension. Rejected because CSS custom properties are directly reusable in Radix UI's `style` prop, which is where most z-index fixes are needed.

---

### D3: Modal overlay must NOT darken the modal itself

**Decision:** The modal overlay is a fixed full-screen element behind the modal content (`z-index: var(--z-modal-overlay)`). The modal content box sits at `z-index: var(--z-modal-content)` with a solid `bg-background` (white). The overlay uses `bg-black/50` but the modal card itself is never a child of the overlay DOM node — they are siblings in the portal.

**Rationale:** The current shadcn/ui `<Dialog>` places `DialogOverlay` and `DialogContent` as siblings inside the portal. The visual bug (modal content appears dark) is caused by `backdrop-filter` or a wrapping dark container. The fix is to ensure `DialogContent` has explicit `bg-background` and no inherited opacity from an ancestor.

---

### D4: Dropdown/popover content uses Portal rendering and correct z-index

**Decision:** All `Select`, `Popover`, `DropdownMenu`, and `Combobox` content must render via Radix portal (already the default for most primitives). Add explicit `z-index: var(--z-dropdown)` to the `Content` component style. When inside a modal, the z-index must be `var(--z-modal-content) + 10` — achieved by setting a higher value in the portal or using Radix's `modal` prop correctly.

**Rationale:** Radix portals already escape the DOM stacking context. The remaining layering issues come from missing z-index declarations on the content itself.

---

### D5: Page layout uses a fixed-width content container

**Decision:** The main content area uses a wrapper `<div className="mx-auto max-w-screen-xl px-6 py-6">` (or equivalent layout class) applied at the layout shell level, not per-page. Each page receives a pre-constrained content zone.

**Rationale:** Per-page width constraints lead to inconsistency. A single layout class guarantees uniform padding and maximum width across all pages.

## Risks / Trade-offs

- **Visual regression on existing pages** → Mitigation: token changes are additive; existing classes that hardcode values (e.g., `z-50`) override the new scale, so regressions are visible immediately and can be patched incrementally.
- **shadcn/ui component internals may resist overrides** → Mitigation: The components expose `className` props; targeted overrides are safe. Only modify what is broken.
- **Radix UI dropdown z-index inside modals** → This is a known Radix issue with nested portals. Mitigation: set `container` prop on portal to the modal's DOM node when needed, or use `z-index` higher than `--z-modal-content` on the dropdown content.
- **Scope creep** → The change must stay visually focused. Any discovered UX flow issues should be filed as a separate change.

## Migration Plan

1. Add token definitions to `src/index.css`
2. Update `src/layouts/` shell components
3. Update `src/components/ui/` base components (Dialog, Select, DropdownMenu, Popover, Button, Input, Card)
4. Update `src/components/shared/` shared components (FormField, DataTable, EmptyState, ErrorState, TreeSelector)
5. Apply page-level layout structure to all `src/pages/` pages
6. No database migrations, no backend deploy, no feature flags required
7. Rollback: revert frontend files; zero backend risk

## Open Questions

- None — scope is fully determined by the visual problems listed in the proposal.
