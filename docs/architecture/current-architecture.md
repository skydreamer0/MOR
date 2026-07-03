# MOR Current Architecture

Last reviewed: 2026-07-03

This file is the active architecture entry point. Use `ROADMAP.md` for implementation order and backlog decisions.

## Product Shape

MOR is a local Flask/Jinja/SQLite sales forecast workbench.

Core pages:

1. Dashboard: year/month performance, budget progress, risk summary, and analytics slices.
2. Product Monitor: daily current-month sales import and product drop-risk review.
3. Forecast: monthly forecast adjustment, discontinued item review, snapshot save, and Excel export.
4. Settings: item rules, budget coverage, and data health.
5. Customer View: customer-level sales summary.

## Runtime Stack

- Flask route layer in `src/backend/app.py`.
- Jinja templates in `templates/`.
- Vanilla JavaScript in `static/js/`.
- CSS design system in `static/css/mor.css` and `DESIGN.md`.
- SQLite workbench database via `src/backend/database.py`.
- Excel input/output through explicit import/export workflows.

## Backend Boundary

Canonical backend path: `src/backend/`.

Root `app.py` is only the local launch wrapper.

Routes should orchestrate:

- request parsing
- validation handoff
- workflow/service calls
- template rendering
- redirects and cache invalidation

Routes should not own:

- forecast math
- row identity encoding
- export calculations
- data health rules
- product monitor row calculation

## Active Services

- `forecast_workbench_context.py`: workbench context builder and forecast row enrichment.
- `forecast_workbench_inputs.py`: DB input loading and row-facing workbench input interface.
- `forecast_write_workflow.py`: forecast row override persistence.
- `forecast_export_workflow.py`: export summary preparation.
- `forecast_page_context.py`: Forecast page render context, row visibility split, risk levels, and review signature validation.
- `snapshot_service.py`: snapshot persistence and row serialization.
- `item_settings_workflow.py`: settings form normalization.
- `item_settings_repository.py`: item setting persistence.
- `settings_context.py`: Settings page context, data-health issues, and budget coverage.
- `dashboard_analytics_workflow.py`: dashboard template context.
- `dashboard_metrics.py`: dashboard KPI metrics.
- `analytics.py`: reusable analytics slices and dashboard risk/status helpers.
- `data_health_summary.py`: data health summary view model and builder.
- `product_monitor_workflow.py`: product monitor template context.
- `product_monitor_month_context.py`: Product Monitor month-level projection, dashboard, and monitor-row orchestration.
- `product_monitor_rows.py`: product monitor row view models, status labels, and row calculation.
- `row_identity.py`: canonical forecast row identity helpers.
- `monthly_review_context.py`: Monthly Review page/export context assembly.
- `monthly_review_data.py`: Monthly Review DB read seam for closed-month, budget, actual, forecast, product-name, and unit-price reads.

## Data Rule

Normal page requests and exports read from `mor_workbench.db`.

Excel parsing is limited to explicit sync/import flows:

- `POST /sync`
- `POST /upload/current-month`
- `POST /monitor/products/import`
- intentional tests/fixtures

See `docs/architecture/database_schema.md` for table-level details.

## Planning Rule

Use only `ROADMAP.md` for current task order.

Archived plans are historical context and must not be used as implementation instructions unless the user explicitly asks for them.
