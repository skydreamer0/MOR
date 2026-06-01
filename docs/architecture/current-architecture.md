# MOR Current Architecture

Last reviewed: 2026-05-29

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

- `forecast_workbench_context.py`: workbench context builder.
- `forecast_write_workflow.py`: forecast row override persistence.
- `forecast_export_workflow.py`: export summary preparation.
- `snapshot_service.py`: snapshot persistence and row serialization.
- `item_settings_workflow.py`: settings form normalization.
- `dashboard_analytics_workflow.py`: dashboard template context.
- `product_monitor_workflow.py`: product monitor template context.
- `row_identity.py`: canonical forecast row identity helpers.
- `operational_views.py`: remaining operational view models, data-loading helpers, and presentation calculations.

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
