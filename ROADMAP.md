# MOR Roadmap

Last reviewed: 2026-07-16

This file is the active source of truth for remaining MOR work. Keep it short.
Historical implementation plans, archived docs, and superseded files should not be used as implementation context unless the user explicitly asks.

## Current Direction

MOR is a local Flask/Jinja/SQLite sales forecast workbench. Keep it compact, operational, table-first, and predictable.

Rules for remaining work:

- Keep Flask routes thin: request parsing, response rendering, redirects, and cache invalidation only.
- Preserve forecast logic, Excel schema, Chinese workbook labels, and existing route behavior unless the task explicitly changes them.
- Write focused tests before behavior or contract changes.
- Avoid broad refactors. Finish one seam at a time.

## Remaining Work

Recommended order:

1. **FE-5: Achievement Threshold Decision**
   - YoY decision is complete: customer/product analytics use signed delta (`+10.0%`) and column label `YoY 成長率`; do not return to ratio display (`110.0%`).
   - Remaining decision: unify achievement/budget-rate thresholds.
   - Proposed target: `>=100` success, `90-99` warning, `80-89` caution, `<80` danger.
   - If approved, update `static/js/fmt.js`, `templates/_value_macros.html`, relevant progress bars, product monitor monthly-history cells, and tests.

## Completed Summary

Done and no longer active roadmap material:

- Backend architecture seams through Product Monitor month context extraction.
- `operational_views.py` retirement.
- Forecast workbench context, input loading, page context, write workflow, export workflow, amount calculation, row identity, snapshots, Settings context, Monthly Review data/context, Dashboard analytics, Product Monitor workflow/rows/month context.
- Frontend UI/UX WP1-WP6: header/action separation, confirm dialog/loading, forecast keyboard input, monitor sorting/sticky first column, focus/font polish, empty states/responsive cleanup.
- Frontend architecture FE-1/FE-2: shared analytics table controller and shared semantic formatting.
- FE-3 Forecast row `data-state` contract: calculation fields moved into row JSON state; selector/HTMX hooks stay separate.
- FE-5 YoY display decision: signed delta everywhere for management analytics.
- FE-4 layout behavior deduplication: CSS-driven workbench height plus shared `behaviors.js` scroll-collapse wiring.
- FE-6 accessibility/guidelines backlog: reduced-motion support, polite live regions, Product Monitor keyboard row expansion, Forecast drawer/snapshot modal Escape and focus handling, accessible header upload input, and `items.html` retained for separate route/template cleanup.
- Release packaging: app-data runtime paths, release build scripts, GitHub Actions workflow, release boundary tests, and focused final check.

## Current Module Map

- `src/backend/app.py`: Flask request/response wiring, redirects, cache invalidation, and remaining route-local glue.
- `src/backend/forecast_workbench_context.py`: workbench-ready forecast context.
- `src/backend/forecast_page_context.py`: Forecast page render context, row grouping, totals, review signatures.
- `src/backend/forecast_workbench_inputs.py`: DB input loading and row-facing workbench inputs.
- `src/backend/forecast_write_workflow.py`: forecast row override persistence.
- `src/backend/forecast_export_workflow.py`: export summary preparation.
- `src/backend/amount_calculation.py`: quantity-to-amount rules and amount inclusion.
- `src/backend/row_identity.py`: canonical row identity helpers.
- `src/backend/snapshot_service.py`: forecast snapshot persistence and immutability.
- `src/backend/monthly_review_context.py` and `src/backend/monthly_review_data.py`: Monthly Review assembly and DB read rules.
- `src/backend/settings_context.py`: Settings page context.
- `src/backend/dashboard_analytics_workflow.py`, `src/backend/dashboard_metrics.py`, `src/backend/analytics.py`: dashboard metrics and analytics slices.
- `src/backend/product_monitor_workflow.py`, `src/backend/product_monitor_month_context.py`, `src/backend/product_monitor_rows.py`: Product Monitor page assembly and row/month calculations.
- `static/js/fmt.js`: JS semantic value formatting.
- `templates/_value_macros.html`: Jinja semantic value formatting; keep thresholds in sync with `fmt.js`.
- `static/js/analytics-table.js`: customer/product/dashboard analytics table controller.
- `static/js/analytics-renderer.js`: canvas charting and metrics rendering.

## Validation

Use the smallest relevant command first.

Frontend:

```powershell
node --test tests/js/fmt.test.js tests/js/analytics-table.test.js
D:\AI\python.exe -m pytest tests\test_frontend_js.py tests\test_ui_smoke.py tests\test_app.py -q --basetemp=.pytest-tmp
```

Release packaging:

```powershell
D:\AI\python.exe -m pytest tests\test_release_data_boundary.py tests\test_release_runtime_paths.py tests\test_release_workflow.py tests\test_release_packaging.py -q --basetemp=.pytest-tmp
```

Backend route/service:

```powershell
D:\AI\python.exe -m pytest tests\test_app.py -q --basetemp=.pytest-tmp
D:\AI\python.exe -m pytest tests\test_forecast_workbench_helpers.py tests\test_exporter.py tests\test_snapshot_service.py -q --basetemp=.pytest-tmp
```

Full suite before broad completion claims:

```powershell
D:\AI\python.exe -m pytest -q
```

## Stop Rules

Stop and report before implementation if:

- A task would change forecast math, Excel schema, row identity, or exported workbook shape.
- More than three files need major changes.
- Tests do not clearly describe current behavior.
- Existing dirty user files would be overwritten.
- A historical plan conflicts with this roadmap.
