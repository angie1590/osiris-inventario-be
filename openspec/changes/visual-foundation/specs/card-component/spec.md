## ADDED Requirements

### Requirement: Cards have consistent visual structure
All card and section container components SHALL have a white/`bg-card` background, a subtle border (`border`), a moderate border radius (`rounded-lg`), and consistent internal padding (`p-4` or `p-6`).

#### Scenario: Card is visually distinct from page background
- **WHEN** a card renders on the page
- **THEN** it SHALL be visually distinguishable from the page background through a border and/or subtle shadow, even if page and card background are both white

#### Scenario: Card padding is consistent
- **WHEN** multiple cards render on the same page
- **THEN** all cards SHALL have the same internal padding variant (either all `p-4` or all `p-6` — consistent per context)

### Requirement: Consistent spacing between cards and sections
The vertical and horizontal spacing between adjacent cards or content sections SHALL follow a consistent scale (`gap-4` or `gap-6`), not be defined per-page.

#### Scenario: Cards do not appear visually merged
- **WHEN** two or more cards render in a vertical list
- **THEN** there SHALL be visible space between them — they SHALL never appear to touch or merge

### Requirement: Section titles within cards
When a card represents a named section of a form or content area, it SHALL include a visible section title using `text-base font-semibold` above the content.

#### Scenario: Section title is visible and styled
- **WHEN** a card contains a section title
- **THEN** the title SHALL use a larger or bolder font than the field labels within the card
