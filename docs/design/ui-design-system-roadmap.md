# UI Design System Roadmap

## Goal

Unify MOR's interface into a maintainable design system for typography, buttons, form controls, toolbars, panels, and tables while preserving the compact spreadsheet-like workflow.

This is a staged UI cleanup plan. Do not implement all phases in one batch.

## Current Status

- Phase 0 inventory: completed in `docs/design/ui-design-system-phase-0-inventory.md`.
- Phase 1 UI tokens: completed for font stack, control size tokens, app title size, and metric value scale.
- Phase 2 buttons and form controls: completed for base controls, compact toolbar buttons, short inline action buttons, icon-only overrides, and Google Inter removal.
- Phase 3 page toolbars: completed for forecast, monitor, and settings shared toolbar structure.
- Phase 4 panels and table containers: completed for shared workbench panel/table shell classes across dashboard, forecast, monitor, and settings.
- Phase 5 and later phases remain pending.

## Scope

In scope:

- Shared CSS tokens and component rules.
- Button, input, select, checkbox, and toolbar sizing logic.
- Badges, summary rows, detail drawers, modals, `details` summaries, and inline action links.
- Reusable page toolbar structure.
- Panel, workspace, and table container consistency.
- Template cleanup for repeated font loading and stale classes.
- `DESIGN.md` updates when token or component rules change.

Out of scope:

- Forecast calculation changes.
- Excel import/export behavior.
- New frontend framework adoption.
- Dashboard feature redesign beyond component consistency.
- Broad backend refactors.

## Recommended Phases

### Phase 0 — UI Inventory

Map the current interface before changing shared CSS.

Tasks:

- Inventory reusable selectors in `static/css/mor.css`.
- List duplicated toolbar patterns across forecast, monitor, and settings pages.
- Identify legacy or stale patterns such as `items.html`, `.primary-btn`, `.bottom-bar`, inline layout styles, and page-specific toolbar classes.
- Separate necessary dynamic inline styles from removable layout inline styles.
- Note selectors used by JavaScript and HTMX before renaming classes.

Likely files:

- `static/css/mor.css`
- `templates/index.html`
- `templates/forecast.html`
- `templates/product_monitor.html`
- `templates/settings.html`
- `templates/items.html`
- `templates/_dashboard_metrics.html`
- `static/js/forecast-table.js`
- `static/js/monitor-table.js`
- `static/js/item-settings.js`

Verification:

- Produce a short inventory note before Phase 1 starts.
- Do not change CSS or templates in this phase.

### Phase 1 — UI Tokens

Normalize foundational values in `static/css/mor.css`.

Tasks:

- Align the font stack with `DESIGN.md`.
- Review and tighten text size tokens.
- Define shared control heights for normal, compact, and icon controls.
- Keep spacing on the existing 4px grid.
- Confirm radius and shadow tokens match the operational data-tool style.
- Update `DESIGN.md` to match the final token set.

Likely files:

- `static/css/mor.css`
- `DESIGN.md`

Verification:

- Browser check `/`, `/forecast`, `/monitor/products`, `/settings`.
- Confirm Chinese labels and numeric table text remain readable.

### Phase 2 — Buttons And Form Controls

Unify interactive control sizing and variants.

Tasks:

- Consolidate base `button`, `.btn-secondary`, `.btn-danger`, `.btn-link`, `.icon-btn`, and `.btn-toolbar`.
- Remove unnecessary `!important` from toolbar button sizing.
- Standardize input/select height, padding, font size, and focus ring.
- Keep table quantity inputs compact and right-aligned.
- Ensure icon buttons use stable square dimensions.
- Include `details summary`, snapshot controls, discontinued section controls, badges, rates, jump links, drawer close controls, and modal actions in the interaction audit.

Likely files:

- `static/css/mor.css`
- `templates/_header.html`
- `templates/forecast.html`
- `templates/settings.html`

Verification:

- Browser check toolbar buttons, header period controls, snapshot controls, export controls, and settings save button.
- Confirm drawer, modal, summary toggles, badge text, and inline action links still feel visually related.

### Phase 3 — Page Toolbars

Make forecast, monitor, and settings toolbar structures consistent.

Tasks:

- Introduce shared classes such as `.workbench-toolbar`, `.toolbar-title`, `.toolbar-controls`, and `.toolbar-actions`.
- Apply the shared toolbar structure to forecast filters, monitor filters, and settings search/save.
- Keep page-specific differences limited to layout needs.
- Preserve dense scanning and avoid marketing-style spacing.

Likely files:

- `static/css/mor.css`
- `templates/forecast.html`
- `templates/product_monitor.html`
- `templates/settings.html`

Verification:

- Browser check each toolbar at desktop and narrow widths.
- Confirm forecast search, customer filter, status filter, anomaly toggle, manual adjustment, restore, and exclude interactions still work.
- Confirm monitor search/status filters and settings search/save still work.

### Phase 4 — Panels And Table Containers

Status: completed.

Unify page workspace containers without changing business behavior.

Tasks:

- Align dashboard panels, monitor workspace, settings workspace, and forecast table wrappers.
- Standardize borders, padding, shadows, and overflow behavior.
- Preserve sticky table headers and horizontal scrolling.
- Avoid nested cards and oversized whitespace.
- Keep row detail drawer, snapshot list, discontinued panel, dashboard risk panels, and settings health panel visually consistent with the same elevation rules.

Likely files:

- `static/css/mor.css`
- `templates/_dashboard_metrics.html`
- `templates/forecast.html`
- `templates/product_monitor.html`
- `templates/settings.html`

Verification:

- Browser check table scrolling, sticky headers, row hover, and fixed-height workspaces.
- Browser check row detail drawer, snapshot details, discontinued details, dashboard panels, and settings health panel.
- Check desktop width around 1280px and narrow width around 390-430px.

### Phase 5 — Template Cleanup

Remove repeated or stale UI scaffolding after the CSS system is stable.

Tasks:

- Remove repeated Google font preload/link tags if no longer needed.
- Consider extracting shared head/layout markup if repeated script and stylesheet tags remain.
- Remove inline layout styles from templates.
- Preserve necessary dynamic inline styles, such as progress or bar widths driven by server data, unless replaced with a safer data-attribute pattern.
- Remove stale or duplicate CSS classes.
- Confirm `DESIGN.md` reflects the implemented component rules.

Likely files:

- `templates/index.html`
- `templates/forecast.html`
- `templates/product_monitor.html`
- `templates/settings.html`
- `templates/items.html`
- `static/css/mor.css`
- `DESIGN.md`

Verification:

- Run syntax checks.
- Run relevant route/template tests.
- Browser check `/`, `/forecast`, `/monitor/products`, `/settings`.
- Confirm HTMX dashboard period refresh still works.

## Suggested First Batch

Start with Phase 0, then Phase 1 and Phase 2 only.

Reason:

- Phase 0 prevents class renames from breaking JavaScript or HTMX selectors.
- They establish the shared sizing logic.
- They reduce visible inconsistency quickly.
- They have low behavior risk if scoped to CSS and template font cleanup.

Do not start Phase 3 until Phase 1 and Phase 2 are verified in the browser.

## Behavior Checks For Every Implementation Batch

Run the smallest relevant checks for each phase, then verify these critical UI flows when touched:

- Dashboard period change updates metrics through HTMX.
- Forecast search, customer filter, status filter, and anomaly toggle combine correctly.
- Forecast manual quantity updates total and row amount.
- Forecast restore and exclude controls still work.
- Snapshot save/finalize/delete controls remain reachable and readable.
- Monitor search and status filters still work.
- Settings search, checkbox states, packaging quantity, status select, and save action still work.
- Tables keep sticky headers, numeric alignment, and horizontal scroll.
