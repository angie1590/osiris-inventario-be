## 1. Design Tokens

- [x] 1.1 Add z-index CSS custom property scale to `src/index.css` (`:root`): `--z-base`, `--z-sticky`, `--z-dropdown`, `--z-drawer`, `--z-modal-overlay`, `--z-modal-content`, `--z-toast`, `--z-critical`
- [x] 1.2 Add shadow scale tokens to `src/index.css`: `--shadow-sm`, `--shadow-md`, `--shadow-lg` using CSS `box-shadow` values appropriate for cards, dropdowns, and modals
- [x] 1.3 Verify all semantic color tokens exist in `src/index.css`: `--success`, `--success-foreground`, `--warning`, `--warning-foreground`, `--info`, `--info-foreground`; add any missing
- [x] 1.4 Add a Tailwind CSS plugin or `@layer utilities` block that exposes z-index tokens as utility classes (e.g., `z-dropdown`, `z-modal`) so they can be used in className props

## 2. Global Layout Shell

- [x] 2.1 Audit `src/layouts/` — identify the main authenticated layout component and the sidebar/content split
- [x] 2.2 Wrap the main content slot in a `max-w-screen-xl mx-auto px-6 py-6` container so all pages inherit consistent padding and max-width
- [x] 2.3 Ensure the sidebar uses `z-index: var(--z-sticky)` and the main content scrolls independently without overlapping the sidebar
- [x] 2.4 Define a reusable `<PageHeader>` component (`src/components/shared/PageHeader.tsx`) that accepts `title`, `description?`, and `actions?` (right-aligned slot) and renders the standard page header row

## 3. Modal (Dialog) Component

- [x] 3.1 Open `src/components/ui/dialog.tsx` — ensure `DialogOverlay` and `DialogContent` are DOM siblings inside the portal (not nested)
- [x] 3.2 Set `DialogContent` to have explicit `bg-background text-foreground` classes so it is never affected by the overlay's opacity
- [x] 3.3 Apply `z-index: var(--z-modal-overlay)` to `DialogOverlay` and `z-index: var(--z-modal-content)` to `DialogContent`
- [x] 3.4 Add `overflow-hidden flex flex-col` to `DialogContent` and create inner `DialogBody` (scrollable, `flex-1 overflow-y-auto p-6`) and `DialogFooter` (sticky bottom, `border-t px-6 py-4 flex justify-end gap-2`) sub-sections
- [x] 3.5 Set a default `max-w-2xl w-full` on `DialogContent`; allow override via `className` prop
- [x] 3.6 Verify Radix Dialog's focus trap and Escape key behavior work correctly after the DOM changes

## 4. Dropdown, Select, and Popover Components

- [x] 4.1 Open `src/components/ui/select.tsx` — set `SelectContent` to use `z-index: var(--z-dropdown)`, `bg-popover`, `border`, `shadow-md`, `max-h-64 overflow-y-auto`
- [x] 4.2 Open `src/components/ui/dropdown-menu.tsx` — set `DropdownMenuContent` to use `z-index: var(--z-dropdown)`, `bg-popover`, `border`, `shadow-md`
- [x] 4.3 Open `src/components/ui/popover.tsx` — set `PopoverContent` to use `z-index: var(--z-dropdown)`, `bg-popover`, `border`, `shadow-md`
- [x] 4.4 For components that open inside modals, verify Radix's portal renders at the correct stacking layer; if not, set a higher z-index (e.g., `var(--z-modal-content) + 10`) on the content via `style` prop or wrapper
- [x] 4.5 Verify all three components (Select, DropdownMenu, Popover) close on outside click and on Escape key press

## 5. Button Component

- [x] 5.1 Open `src/components/ui/button.tsx` — audit `cva` variant definitions; ensure `default` (primary), `outline` (secondary), `destructive`, `ghost`, and `link` variants are visually distinct at a glance
- [x] 5.2 Add `loading` variant or prop: when `isLoading` is true, show a spinner (`Loader2` icon with `animate-spin`) and set `disabled` automatically
- [x] 5.3 Verify `disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none` classes are present on all variants
- [x] 5.4 Ensure `focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2` is present on the base button styles for keyboard navigation visibility
- [x] 5.5 Apply `loading` prop (or equivalent) to all submit buttons in forms throughout the app: `IngresoNewPage`, `EgresoNewPage`, `BajaNewPage`, `AjusteNewPage`, `AdminCompanyPage`, `ProductFormPage`

## 6. Input Component

- [x] 6.1 Open `src/components/ui/input.tsx` — verify `h-9 border border-input bg-background px-3 text-sm` (or equivalent) is on the base input
- [x] 6.2 Add `focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-0` to ensure keyboard focus ring is always visible
- [x] 6.3 Add `aria-invalid` styling: when `aria-invalid="true"`, the input border should become `border-destructive` (use `data-[aria-invalid=true]:border-destructive` or equivalent)

## 7. Card Component

- [x] 7.1 Open `src/components/ui/card.tsx` — verify `Card` has `bg-card text-card-foreground border rounded-lg shadow-sm` as base classes
- [x] 7.2 Ensure `CardHeader`, `CardContent`, and `CardFooter` have consistent padding (`p-6`, `px-6 pb-6`, `px-6 pb-6` respectively)
- [x] 7.3 Create a `<Section>` wrapper (`src/components/shared/Section.tsx`) with `title?: string` prop that renders a titled card section: `<div className="rounded-lg border bg-card p-4 space-y-4"><h2 className="text-base font-semibold">{title}</h2>{children}</div>`

## 8. Page Layout Structure

- [x] 8.1 Update `src/pages/catalog/ProductsPage.tsx` to use `<PageHeader>` for its title + "Nuevo producto" button
- [x] 8.2 Update `src/pages/catalog/ProductDetailPage.tsx` to use `<PageHeader>` for its title + action buttons
- [x] 8.3 Update `src/pages/catalog/CategoriesPage.tsx` to use `<PageHeader>` for its title + action buttons
- [x] 8.4 Update `src/pages/inventory/IngresosPage.tsx`, `EgresosPage.tsx`, `BajasPage.tsx`, `AjustesPage.tsx` to use `<PageHeader>` and wrap filter bars in a `<Section>`
- [x] 8.5 Update `src/pages/reports/ReportsPage.tsx` and `src/pages/AuditPage.tsx` to use `<PageHeader>`
- [x] 8.6 Update `src/pages/admin/AdminCompanyPage.tsx` to use `<PageHeader>` and organize form fields using `<Section>` groupings
- [x] 8.7 Update `src/pages/catalog/ProductFormPage.tsx` to ensure all sections use `<Section>` with consistent spacing; verify the Attributes section doesn't cause layout breaks

## 9. Form and Modal Usage Audit

- [x] 9.1 Audit all modal dialogs in `src/features/catalog/` (CategoryFormModal, AttributeFormModal, AttributeEditModal) — verify `DialogBody`/`DialogFooter` split is applied; check no dropdown clips inside modal
- [x] 9.2 Verify `TreeSelector` popover inside `CategoryFormModal` and `ProductFormPage` opens correctly above modal z-index
- [x] 9.3 Verify that all `<FormField>` usages across the app have the updated `aria-invalid` input styling applied (benefit of task 6.3)
- [x] 9.4 Replace any remaining bare `<div>` filter bars with `<Section>` or a styled filter container (`rounded-lg border bg-card p-3 flex flex-wrap gap-3`)

## 10. Accessibility and Polish

- [x] 10.1 Verify every interactive component (modals, dropdowns, popovers, tree selector) closes on Escape key press
- [x] 10.2 Verify all modals and drawers trap focus correctly and return focus to the trigger on close
- [x] 10.3 Audit all pages for any remaining hardcoded `z-50`, `z-40`, etc. Tailwind z-index classes; replace with `--z-*` token-based approach
- [x] 10.4 Run the app visually and verify: (a) modal backgrounds are white with readable text, (b) dropdowns have solid background and correct layering, (c) form labels are visible, (d) page headers are consistent, (e) no elements overlap each other incorrectly
- [x] 10.5 Fix the `<Toaster>` component position and z-index to use `z-index: var(--z-toast)` so toasts always appear above modals
