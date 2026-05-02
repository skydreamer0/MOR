DO NOT USE FOR IMPLEMENTATION

# MOR Frontend Design

## UI Role

The frontend is a monthly forecast review workspace. Its job is to help the user scan many customer/product rows, understand why each row is included, override quantities, exclude rows, and export with confidence.

## Current Screen

The current UI is a single page:

- Sticky header with MOR title and target period controls.
- Summary metric strip.
- Horizontally scrollable forecast table.
- Inline manual quantity inputs.
- Exclusion checkboxes.
- Fixed bottom bar with recalculated total and export action.

This is the right broad shape for v1 because the workflow is review-heavy and table-first.

## Recommended Visual Direction

Use a structured data UI direction similar to Airtable's spreadsheet-database mental model, but quieter and more enterprise-focused for sales operations.

Keep:

- Light neutral background.
- White data surfaces.
- Teal primary action.
- Compact inputs.
- Sticky table header.
- Bottom total/export bar.

Improve next:

- Repair all visible Chinese labels and ensure UTF-8 rendering.
- Add status/filter controls above the table.
- Add row hover and focus states.
- Add visible empty/error states.
- Add clearer distinction between system quantity, manual quantity, and effective amount.

## Component Inventory

| Component | Current State | Recommended Direction |
| --- | --- | --- |
| Header | Compact sticky bar | Keep; add clearer period labels |
| Period controls | Numeric year/month fields | Consider month picker or segmented recent months |
| Metrics | Four cards | Keep; make labels concise and values aligned |
| Forecast table | Main workspace | Add sorting/filtering before adding charts |
| Status badge | Auto/not-due | Keep; use semantic color tokens |
| Manual quantity input | Inline number input | Keep; add validation and edited state |
| Exclusion checkbox | Plain checkbox | Keep; add row visual feedback and count |
| Bottom bar | Fixed total/export | Keep; add changed-row count later |

## Interaction Rules

- Editing quantity should update row amount and grand total immediately.
- Empty manual quantity means use system quantity.
- Excluded rows should show muted styling and amount `0`.
- Export should always recompute server-side from submitted form values.
- UI should never rely only on color to indicate exclusion or status.

## Responsive Rules

- Desktop and tablet: preserve table density and horizontal scroll.
- Mobile: stack header controls and metrics; keep table scroll rather than hiding important columns.
- Touch targets should stay at least 38px high.

## Do Not Add Yet

- Landing page or hero area.
- Decorative charts that do not change decisions.
- Modal-heavy editing.
- Authentication or account menus.
- Client-side framework unless table interactions become too complex for vanilla JS.

