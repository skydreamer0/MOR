# MOR Local Setup

## Purpose

This document defines the local setup, test, and run workflow for MOR. Use it before changing backend logic, frontend behavior, Excel export, or project documentation.

## Runtime

Preferred local Python runtime:

```powershell
D:\AI\python.exe
```

The Codex bundled runtime may be used for syntax checks, but `D:\AI\python.exe` is the current verified runtime for tests and the Flask app.

## Install Dependencies

Install dependencies from the project root:

```powershell
D:\AI\python.exe -m pip install -r requirements.txt
```

If dependencies must be installed into a local vendor directory for an isolated run:

```powershell
D:\AI\python.exe -m pip install --target .\.vendor -r requirements.txt
```

`.vendor/` is ignored and should not be committed.

## Run Tests

Run all tests:

```powershell
D:\AI\python.exe -m pytest -q
```

If Windows temp permissions block pytest setup, keep the temp directory inside the project:

```powershell
D:\AI\python.exe -m pytest -q --basetemp=.test-dbs\pytest-tmp
```

Run route/template tests:

```powershell
D:\AI\python.exe -m pytest tests/test_app.py -q
```

Run form parser tests:

```powershell
D:\AI\python.exe -m pytest tests/test_form_parser.py -q
```

Run presenter tests:

```powershell
D:\AI\python.exe -m pytest tests/test_forecast_presenter.py -q
```

## Syntax Check

```powershell
D:\AI\python.exe -m py_compile app.py src\backend\app.py src\backend\sales_forecast.py src\backend\forecast_config.py src\backend\forecast_models.py src\backend\data_loader.py src\backend\forecast_engine.py src\backend\exporter.py src\backend\web\form_parser.py src\backend\web\forecast_presenter.py
```

## Run The App

```powershell
D:\AI\python.exe app.py
```

Open:

```text
http://127.0.0.1:5000/
```

MOR does not run on `localhost:9010`; that port may belong to another in-app service.

## Source Data

Expected local Excel files:

- `業績明細202401-20260430-George.xlsx`
- `三年報表-George-20260430.xlsx`
- `2026預算報表-George-20260430.xlsx`

Treat these files as source data. Do not overwrite them unless explicitly requested.

## Browser Verification Checklist

After frontend changes, verify in the browser:

- Chinese labels render correctly.
- Missing-file error renders as an alert.
- Dashboard renders at `/` with quantity and amount metrics.
- Product monitor renders at `/monitor/products` and filters by search/status.
- Forecast adjustment renders at `/forecast`.
- System settings and data checks render at `/settings`.
- Search filters rows without losing input values.
- Status filter works.
- Manual quantity updates row amount and grand total.
- Excluding a row mutes it and sets amount to 0.
- Edited/excluded counters update.
- Invalid manual quantity is blocked client-side and rejected server-side.
- Export downloads an Excel workbook.
