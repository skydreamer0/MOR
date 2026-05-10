# UI Design System Phase 0 Inventory

## Goal

Inventory the current MOR UI before changing shared CSS or template structure.

This note supports `docs/design/ui-design-system-roadmap.md` Phase 0. It is a planning artifact only; no CSS, template, or JavaScript behavior should be changed in this phase.

## Current UI Surface

Primary pages:

- Dashboard: `templates/index.html`, `templates/_dashboard_metrics.html`
- Forecast adjustment: `templates/forecast.html`, `templates/_forecast_row.html`, `templates/_forecast_thead.html`
- Product monitor: `templates/product_monitor.html`
- Settings/data checks: `templates/settings.html`
- Legacy item page: `templates/items.html`
- Shared header: `templates/_header.html`

Primary frontend assets:

- `static/css/mor.css`
- `static/js/forecast-table.js`
- `static/js/monitor-table.js`
- `static/js/item-settings.js`

## CSS Component Groups

Foundational groups:

- Tokens: color, typography, spacing, radius, shadow, transition variables in `:root`.
- Page shell: `body`, `header`, `.app-header`, `.header-main`, `.brand-block`, `main`.
- Navigation and period controls: `nav`, `nav a`, `.nav-action-form`, `.nav-action-btn`, `.toolbar`.
- Global controls: `input`, `select`, `button`, focus states, `.htmx-indicator`.

Forecast groups:

- Summary metrics: `.summary`, `.metric`, `.metric--locked`.
- Forecast toolbar: `.forecast-tools`, `.filter-group`, `.toolbar-divider`, `.btn-toolbar`, `.view-toggle`, `.view-toggle-btn`.
- Forecast table: `.table-wrap`, `.forecast-table`, `.num`, `.col-group-start`, edited/excluded/invalid row states.
- Table inputs: `.qty`, `.qty-wrapper`, `.reason`.
- Row detail drawer: `.row-detail-backdrop`, `.row-detail`, `.row-detail__*`, `.detail-section`, `.detail-row`, `.detail-monthly-table`.
- Snapshot/discontinued controls: `.snapshot-*`, `.discontinued-*`.
- Modal: `.modal-backdrop`, `.modal-card`, `.modal-actions`.

Shared visual groups:

- Alerts and empty states: `.alert`, `.alert-info`, `.empty-state`.
- Badges/status values: `.badge`, `.badge.off`, `.status-*`, `.rate`, `.gap-value`.
- Buttons/links: base `button`, `.btn-secondary`, `.btn-danger`, `.btn-link`, `.link-btn`, `.icon-btn`, `.jump-link`.
- Panels/workspaces: `.panel`, `.management-panel`, `.monitor-workspace`, `.settings-workspace`, `.hero__container`.
- Dashboard groups: `.hero__*`, `.progress-*`, `.sub-metric-*`, `.risk-dashboard`, `.rank-*`, `.dist-*`.
- Monitor groups: `.monitor-toolbar`, `.monitor-table`, `.monitor-sticky-*`, `.monitor-note`.
- Settings groups: `.settings-toolbar`, `.settings-health-*`, `.settings-table-wrap`, `.checkbox-label`.

## Duplicate Or Divergent Patterns

Toolbar patterns:

- Header period toolbar uses `.toolbar`.
- Forecast filters use `.forecast-tools` plus `.filter-group`.
- Monitor uses `.monitor-toolbar` and `.monitor-toolbar__title`.
- Settings uses `.settings-toolbar` and `.settings-toolbar__title`.
- Dashboard uses `.hero__actions` and `.section-header` actions.

Button patterns:

- Base `button` controls normal submit buttons.
- `.btn-toolbar` uses compact overrides and currently depends on `!important`.
- `.nav-action-btn` is a small header button variant.
- `.view-toggle-btn` is a segmented-control button.
- `.icon-btn` is used both for restore/delete and drawer close actions.
- `.btn-link` and `.link-btn` both style link-like actions.
- `templates/items.html` still references `.primary-btn`, but `mor.css` does not define it.

Container patterns:

- `.table-wrap` is the main table container.
- `.monitor-table-wrap` and `.settings-table-wrap` reset parts of `.table-wrap`.
- `.panel`, `.management-panel`, `.monitor-workspace`, `.settings-workspace`, and `.hero__container` overlap as white bordered containers.
- Forecast summary `.metric` and dashboard `.sub-metric` are similar but separate.

## JavaScript And HTMX Selector Contracts

Do not rename or remove these without updating JavaScript and browser verification.

Forecast JavaScript selectors:

- Rows and row state: `[data-row]`, `tr[data-row]`, `tr[data-risk]`, `tr[data-risk='high']`
- Row inputs: `[data-manual]`, `[data-reason]`, `[data-restore]`
- Filters: `[data-filter-search]`, `[data-filter-status]`, `[data-filter-customer]`
- Counters/status: `[data-visible-count]`, `[data-edited-count]`, `[data-validation-message]`, `[data-unrendered-total]`, `#top-total`, `#edited-badge`, `#save-status`
- View toggle: `#btn-anomaly-only`, `#btn-show-all`, `.view-toggle`
- Form: `#forecast-form`
- Drawer: `#row-detail`, `#row-detail-backdrop`, `#rd-close`, `#rd-*`
- Snapshot modal buttons: `#btn-save-snapshot`, `#btn-finalize`
- Sparkline: `[data-sparkline]`

Monitor JavaScript selectors:

- `[data-monitor-search]`
- `[data-monitor-status]`
- `[data-monitor-visible]`
- `[data-monitor-row]`

Settings JavaScript selectors:

- `[data-item-search]`
- `[data-item-visible]`
- `[data-item-row]`

HTMX contracts:

- Dashboard period inputs in `_header.html` use `hx-get="/dashboard/metrics"` and target `#metrics-zone`.
- Forecast row manual quantity and reason inputs use `hx-patch`, target the row id, and `hx-swap="outerHTML"`.
- The row swap can replace bound DOM nodes; any future selector or class cleanup should verify row interactions after HTMX replacement.

## Inline Style Inventory

Likely necessary dynamic inline styles:

- `_dashboard_metrics.html` progress fill width: `style="width: {{ [rate, 100] | min }}%"`
- `_dashboard_metrics.html` rank bar width: `style="width: {{ (...) }}%"`

Likely removable layout/style inline rules:

- `_dashboard_metrics.html` status color: `style="color:var(--accent-2)"`
- `_dashboard_metrics.html` empty-state margin: `style="margin:var(--sp-4) 0 0;"`
- `_dashboard_metrics.html` section action layout: `style="display:flex;gap:8px;align-items:center;"`
- `templates/items.html` muted ID color: `style="color: var(--muted);"`

JavaScript-created inline style:

- `forecast-table.js` creates a hidden form with `form.style.display = "none"`.
- `forecast-table.js` hides `.view-toggle` with `style.setProperty("display", "none")` when there are no high-risk rows.

## Stale Or Risky Patterns

- `templates/items.html` appears older than `templates/settings.html` and still uses `.primary-btn`, `.bottom-bar`, direct checkbox text, and inline style.
- `.bottom-bar-actions` exists in CSS, but `.bottom-bar` and `.primary-btn` are not defined in `mor.css`.
- `.btn-toolbar` currently uses `!important`; Phase 2 should remove this by making variants explicit.
- `.link-btn` and `.btn-link` overlap conceptually and should be consolidated or clearly differentiated.
- `.icon-btn` has hover rotation globally; this may be appropriate for close/delete but feels odd for restore actions.
- `DESIGN.md` says the app title is 22px, while `mor.css` currently maps `h1` to `--text-lg` 16px.
- `DESIGN.md` font stack starts with `Microsoft JhengHei`, while `mor.css` currently starts with `Inter` and each template loads Google Inter.
- Responsive rules are concentrated in one media block and may need component-level checks after toolbar/container changes.

## Recommended Next Step

Phase 1 and Phase 2 have been implemented for the shared font stack, control size tokens, base button/input sizing, compact toolbar buttons, short inline action buttons, and removal of Google Inter from templates.

Next, start Phase 3 as a separate batch:

- Unify toolbar structure across forecast, monitor, and settings.
- Avoid renaming `data-*`, `id`, and HTMX attributes unless the related JavaScript is updated in the same batch.
- Preserve all behavior checks listed below.

## Verification Targets

Minimum browser checks after Phase 1 or Phase 2 changes:

- `/`
- `/forecast`
- `/monitor/products`
- `/settings`

Behavior checks when related UI is touched:

- Dashboard period change refreshes `#metrics-zone`.
- Forecast search/customer/status/anomaly filters combine correctly.
- Forecast manual quantity updates row amount and total.
- Forecast restore button still appears and works.
- Forecast drawer opens/closes and displays row details.
- Snapshot buttons open modal and remain readable.
- Monitor search and status filters work.
- Settings search works; checkbox and save controls remain usable.
- Tables preserve sticky headers, right-aligned numbers, and horizontal scrolling.
