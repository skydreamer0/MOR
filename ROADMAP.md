# MOR Roadmap

Last reviewed: 2026-05-31

This file is the active source of truth for MOR planning. Historical implementation plans and architecture review artifacts should not be used as implementation context unless this roadmap explicitly points to them.

## Current Direction

MOR is a local Flask/Jinja/SQLite sales forecast workbench. Keep the product compact, operational, table-first, and predictable.

Architecture direction:

- Keep Flask routes thin: request parsing, response rendering, redirects, and cache invalidation only.
- Move workflow complexity into small backend modules one seam at a time.
- Preserve current external behavior while refactoring.
- Write characterization tests before changing calculation, lookup, export, or row identity behavior.
- Avoid broad rewrites and do not re-inline workflow modules into routes.

## Current Module Boundaries

- `src/backend/forecast_workbench_context.py` builds the workbench-ready forecast context, owns `ForecastPageContext`, and owns summary-local latest-order-date enrichment.
- `src/backend/forecast_workbench_inputs.py` owns DB input loading and budget target records for the forecast workbench context.
- `src/backend/amount_calculation.py` owns forecast row amount inclusion and quantity-to-amount calculation.
- `src/backend/forecast_write_workflow.py` owns forecast row override persistence.
- `src/backend/forecast_export_workflow.py` owns export summary preparation.
- `src/backend/snapshot_service.py` owns snapshot persistence, forecast-row snapshot serialization, and final/close-month snapshot immutability.
- `src/backend/item_settings_workflow.py` owns item/settings request-form parsing and item config payload normalization.
- `src/backend/dashboard_analytics_workflow.py` owns dashboard analytics/template context assembly.
- `src/backend/product_monitor_workflow.py` owns product monitor template context assembly.
- `src/backend/product_monitor_rows.py` owns product monitor row view models, row calculation, status labels, and monthly history lookup.
- `src/backend/row_identity.py` owns canonical forecast row identity make/parse helpers.
- `src/backend/operational_views.py` still owns shared operational view models, analytics helpers, remaining budget/history presentation helpers, and compatibility facades.
- `src/backend/app.py` still owns Flask request/response wiring, redirects, cache invalidation, and remaining route-local workflow glue.

## Completed Architecture Seams

1. Forecast workbench context module.
2. Forecast write workflow refactor.
3. Export summary preparation.
4. Snapshot row serialization.
5. Item/settings write workflow form parsing.
6. Dashboard analytics template context.
7. Product monitor template context.
8. Forecast row identity helper foundation.
9. Forecast row identity lookup migration across operational, history, and projection paths.
10. Product monitor row calculation module extraction.
11. Forecast workbench input-loading and latest-order-date enrichment extraction.
12. Forecast workbench page-context type ownership extraction.
13. Close-month snapshot immutability and Forecast UI delete guard.
14. Forecast workbench input loader ownership cleanup.
15. Amount calculation seam foundation.

## Active Refactor Queue

### 1. Workbench Context Internals

Goal: keep `forecast_workbench_context.py` as the public context builder while moving remaining summary enrichment, health, projection, and monitor assembly details into smaller testable helpers.

Boundary:

- Keep `build(forecast_config, db, target_source, *, today=None)` stable unless a test-protected API change is necessary.
- Do not touch export/write workflows in the same seam.

### 2. Amount Calculation Seam

Goal: expand the new amount calculation seam so monthly review and raw forecast engine behavior cannot diverge silently from dashboard/export calculations.

Boundary:

- Characterize current behavior before changing formulas.
- Treat `exporter.py` primarily as workbook output, not the owner of pricing rules.

### 3. Close-Month Workflow

Goal: move remaining close-month route-local orchestration into a backend workflow/service.

Boundary:

- Snapshot immutability is already owned by `snapshot_service.py`.
- This seam should own route orchestration, validation, close-record creation, cache invalidation points, and redirect/message behavior.

### 4. Context Cache Seam

Goal: extract cache key/invalidation state from `app.py` into a small `ContextCache` seam if cache behavior starts blocking route simplification.

Priority: low. Current helper functions are acceptable until other route seams are quieter.

## Product Backlog

1. Product view page: product-level sales summary, similar in shape to the completed Customer View.

Hold feature work until the active refactor batch is small and verified, unless the user explicitly prioritizes the feature.

## Completed Feature Work

- Browser multi-page UI smoke coverage.
- Budget coverage warning in Settings UI.
- Customer view page (`/customers`) with YTD summary, month expansion, and sparkline.
- Forecast item status layering: discontinued products render in a collapsed section below active forecast rows.
- Path unification: `src/backend/` is the canonical backend implementation path; root `app.py` is only a launch wrapper.

## Closed Historical Plans

The following planning artifacts have been absorbed, completed, or superseded and were moved to archive:

- Forecast item status layering plan — completed and absorbed into feature history.
- MOR stability and hygiene plan — absorbed into this roadmap; remaining work is tracked above.
- Old refactor plan — superseded; its workflow-inlining recommendation conflicts with the current route-thinning direction.
- Path unification plan — completed; canonical path is now documented here and in active architecture docs.
- Roadmap before/after HTML report — review artifact absorbed into this roadmap.
- Old project architecture and implementation plan — superseded by `docs/architecture/current-architecture.md` plus this roadmap.
- Duplicate infrastructure API spec — stale duplicate of API notes; keep `docs/design/api-spec.md` active.
- UI design system Phase 0 inventory — historical UI inventory; keep `DESIGN.md` and `docs/design/ui-design-system-roadmap.md` active for UI work.

If a future task needs historical context, ask the user before reading archived plans.

## Per-Seam Execution Template

For every refactor seam:

1. Inspect only related active files.
2. Write or update characterization tests.
3. Make the smallest extraction or migration.
4. Keep route behavior stable.
5. Run focused validation.
6. Update this roadmap if the next seam changes.

Use subagents only for broad audits, independent investigations, or explicit user requests.

## Validation Matrix

Focused backend route/service validation:

```powershell
D:\AI\python.exe -m pytest tests\test_operational_views.py -q --basetemp=.pytest-tmp
D:\AI\python.exe -m pytest tests\test_app.py -q --basetemp=.pytest-tmp
D:\AI\python.exe -m pytest tests\test_exporter.py tests\test_snapshot_service.py -q --basetemp=.pytest-tmp
```

Quick syntax validation:

```powershell
D:\AI\python.exe -m py_compile app.py src\backend\app.py src\backend\sales_forecast.py src\backend\forecast_config.py src\backend\forecast_models.py src\backend\data_loader.py src\backend\forecast_engine.py src\backend\projection_engine.py src\backend\operational_views.py src\backend\etl.py src\backend\exporter.py src\backend\web\form_parser.py src\backend\web\forecast_presenter.py
```

Full validation before broad backend completion claims:

```powershell
D:\AI\python.exe -m pytest -q
```

## Stop Rules

Stop and report before implementation if:

- A seam touches analytics and write workflows at the same time.
- More than three files need major changes.
- Tests do not clearly describe current behavior.
- Route behavior may change.
- Existing dirty files may be overwritten.
- A historical plan conflicts with this roadmap.
