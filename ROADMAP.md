# MOR Roadmap

## Current Focus

Make MOR a compact multi-page operating tool:

1. Dashboard for quick business overview.
2. Product drop monitor for daily risk review.
3. Forecast adjustment page for manual overrides and export.
4. Settings and data checks page for item rules and source-data health.

## Small Task Queue

1. Finish multi-page UI verification in browser.
2. Add export readback tests for workbook tabs and totals.
3. Improve data health checks for missing budget mappings.
4. Add customer view page after monitor rules stabilize.
5. Add product view page after customer view is useful.

---

## Frontend Improvement Plan

Staged fixes identified from architecture review on 2026-05-09. Do not start a later phase before completing the current one.

### Phase 1 — Correctness (Bug Risk) `priority: high`

These have actual incorrect behaviour under normal usage.

- [x] **Unify row visibility into one mechanism.**
  Currently three competing systems exist in the forecast table:
  `row.hidden` (search/status filter in `recalculate`),
  `tr.style.display` (customer dropdown in `filterRows`), and
  `.forecast-table__row--collapsed` (anomaly view toggle in `applyViewMode`).
  They can layer in unpredictable order; total and count displays show wrong values when more than one filter is active simultaneously.
  Fix: fold `filterRows` into `recalculate` state using a `data-customer` dataset check, and fold `applyViewMode` into the same visible-flag logic, so a single `row.hidden = !visible` pass controls everything.

- [x] **Replace positional `nth-child` column-group borders with class selectors.**
  `mor.css` lines 921–926 use `tbody td:nth-child(9)` and `tbody td:nth-child(13)` for group dividers.
  Adding or removing any column silently shifts the borders to the wrong columns.
  Fix: add `col-group-start` class to the relevant `<td>` cells in `_forecast_row.html` (already applied to `<th>` in the header) and remove the `nth-child` rules.

### Phase 2 — Consistency (Design System Integrity) `priority: medium`

These do not break behaviour but will cause agent and dev errors over time.

- [x] **Sync DESIGN.md token values with `mor.css`.**
  `DESIGN.md` lists `--ink: #16202a` but `mor.css` uses `#0f172a`. Several tokens in the
  "Recommended additions" block have since been implemented in CSS but the doc still marks them as suggestions.
  Fix: update `DESIGN.md` Section 2 to reflect the actual token values in `mor.css`; remove the split between "current" and "recommended" since all tokens now exist.

- [x] **Move hardcoded hover colour into design token.**
  `mor.css` line 511: `background-color: #eef6ff` (blue tint) is the only hardcoded colour
  outside the token system. It conflicts with the teal accent identity.
  Fix: add `--row-hover: #eef6ff` (or convert to an accent-based tint) to `:root` and reference it in the hover rule.

### Phase 3 — Maintainability `priority: low`

Clean-up that makes future changes safer and faster.

- [x] **Unify customer dropdown with the main filter path.**
  The customer `<select>` fires `filterRows()` which bypasses `recalculate()`.
  After Phase 1 is done, fold the customer value into the unified visibility check so search,
  status, customer, and anomaly-only all go through one pass.

- [x] **Extract `<thead>` into a shared partial.**
  Created `templates/_forecast_thead.html`; both main and discontinued tables now include it.
  Also fixed a latent bug: the discontinued thead was missing `col-group-start` on 最後預估 (Phase 1
  replace_all missed it due to different indentation depth).

- [x] **Audit HTMX usage; remove if not actively used.**
  HTMX is actively used in two places — keep the script tag on all pages:
  1. `_forecast_row.html` — `hx-patch` on qty/reason inputs replaces the row `outerHTML` on `change`.
  2. `_header.html` — `hx-get="/dashboard/metrics"` refreshes the metrics zone when the period selector changes.
  3. `_dashboard_metrics.html` — `htmx-indicator` shows a loading state during the metrics fetch.

  ⚠️  Follow-up concern (not yet fixed): `hx-swap="outerHTML"` in `_forecast_row.html` replaces the
  entire `<tr>` DOM node on `change`, which destroys JS event listeners bound by `bindForecastTable()`
  (input recalculate, row-click detail panel, restore button). After a HTMX swap, those interactions
  stop working for that row. Fix options: remove `hx-patch` (rely solely on `saveToServer`), or
  rebind listeners via the `htmx:afterSwap` event.

## Working Rules

- Do one task at a time.
- Read `AGENTS.md`, this roadmap, and only the necessary active docs.
- Keep Flask routes thin.
- Keep calculation rules in testable backend services.
- Update docs when workflows, forecast rules, Excel shape, or UI structure change.
- Run the focused tests first, then the full suite when backend/routes/templates change.

## Recommended Verification

```powershell
D:\AI\python.exe -m pytest -q --basetemp=.test-dbs\pytest-tmp
D:\AI\python.exe -m py_compile app.py src\backend\app.py src\backend\sales_forecast.py src\backend\forecast_config.py src\backend\forecast_models.py src\backend\data_loader.py src\backend\forecast_engine.py src\backend\exporter.py src\backend\web\form_parser.py src\backend\web\forecast_presenter.py src\backend\operational_views.py
```
