# MOR Active Backlog

Keep this file limited to work that still needs to be done. Completed or superseded implementation plans belong in `docs/archive/plans/`, not here.

## Next

1. Finish multi-page UI verification in browser.
2. Improve data health checks for missing budget mappings.

## Later

1. Add customer view page after monitor rules stabilize.
2. Add product view page after customer view is useful.
3. Split `operational_views.py` into smaller dashboard, monitor, settings, and forecast context services.
4. Replace inline SQLite schema migrations in `database.py` with a clearer migration convention.
5. Stabilize row identity beyond `customer + "__" + product_code` before adding customer-code workflows.
6. Add focused route guards for any new request-time data path to keep normal pages DB-first.

## Working Rules

- Do one task at a time.
- Read `AGENTS.md`, this backlog, and only the necessary active docs.
- Keep Flask routes thin and forecast logic testable without Flask.
- Update docs when workflows, forecast rules, Excel shape, or UI structure change.

## Recommended Verification

```powershell
D:\AI\python.exe -m pytest -q --basetemp=.test-dbs\pytest-tmp
D:\AI\python.exe -m py_compile app.py src\backend\app.py src\backend\sales_forecast.py src\backend\forecast_config.py src\backend\forecast_models.py src\backend\data_loader.py src\backend\forecast_engine.py src\backend\exporter.py src\backend\web\form_parser.py src\backend\web\forecast_presenter.py src\backend\operational_views.py
```
