# MOR Roadmap

## Current Focus

Make MOR a compact multi-page operating tool:

1. Dashboard for quick business overview.
2. Product drop monitor for daily risk review.
3. Forecast adjustment page for manual overrides and export.
4. Settings and data checks page for item rules and source-data health.

## Small Task Queue

1. Finish multi-page UI verification in browser.
2. Improve data health checks for missing budget mappings.
3. Add customer view page after monitor rules stabilize.
4. Add product view page after customer view is useful.

---

## Future Backlog

Keep this list short. Move large implementation plans to `docs/archive/plans/` once their decisions are absorbed into active docs.

1. Split `operational_views.py` into smaller dashboard, monitor, settings, and forecast context services.
2. Replace inline SQLite schema migrations in `database.py` with a clearer migration convention.
3. Stabilize row identity beyond `customer + "__" + product_code` before adding customer-code workflows.
4. Add focused route guards for any new request-time data path to keep normal pages DB-first.

## Archived Plans

Completed or superseded implementation plans now live in `docs/archive/plans/`.
Do not read archived plans for implementation context unless explicitly researching history.

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
