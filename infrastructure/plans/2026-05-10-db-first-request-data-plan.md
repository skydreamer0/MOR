# DB-First Request Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. MOR subagents are not required unless the user explicitly approves parallel work.

**Goal:** Make every user-facing request read operational data from `mor_workbench.db`; Excel files remain import/sync sources only.

**Architecture:** Keep Flask routes thin and preserve the existing Jinja + vanilla JS frontend. Move request-time sales loading behind a DB-backed loader that returns the same normalized DataFrame shape currently expected by `forecast_engine`, then update forecast/dashboard/monitor/export flows to use that DB-backed path. Keep Excel parsing inside ETL/upload commands, not page requests.

**Tech Stack:** Flask, SQLite, pandas, pytest, existing MOR backend modules.

---

## Current State

- `sales_records`, `current_month_records`, `budget_targets`, `item_configs`, `forecast_adjustments`, snapshots, daily actuals, and month close records already exist in SQLite.
- Frontend requests do not read files directly; they call Flask routes or htmx/fetch endpoints.
- Main forecast context is not fully DB-first yet:
  - `src/backend/operational_views.py` calls `load_sales_detail(data_base_path, forecast_config)` without `db`.
  - `src/backend/data_loader.py` reads `業績明細*.xlsx` during request-time loading.
  - `src/backend/app.py` export still calls `load_sales_detail(data_base_path, forecast_config)` before building export context.

## In Scope

- Request-time reads for dashboard, forecast, monitor, settings, monthly review, row patch, adjustment save follow-up context, snapshots, and export.
- DB-backed replacement for request-time sales detail loading.
- Tests proving routes do not call `pandas.read_excel` during normal page/export requests.
- Documentation update for the DB-first contract.

## Out of Scope

- Removing Excel import/sync support.
- Changing forecast formulas.
- Replacing pandas inside the forecast engine.
- Adding new third-party dependencies.
- Broad UI changes.

## Target Data Contract

Excel is allowed only in these flows:

- `POST /sync` via `sync_excel_to_db()`.
- `POST /upload/current-month` via SHPB upload/import.
- `POST /monitor/products/import` via daily actual upload.
- Tests/fixtures that intentionally construct Excel inputs.

All normal user-facing page requests must read from SQLite:

- `/`
- `/dashboard/metrics`
- `/forecast`
- `PATCH /forecast/row/<row_id>`
- `/monitor/products`
- `/settings`
- `/monthly-review`
- `/export`
- `/snapshots/save`

## Files Likely Affected

- Modify: `src/backend/data_loader.py`
  - Add DB-backed sales-detail loader that combines `sales_records` and `current_month_records`.
  - Keep Excel loader only for ETL compatibility or rename clearly if needed.
- Modify: `src/backend/operational_views.py`
  - Build `ForecastPageContext` from DB-backed sales data.
- Modify: `src/backend/app.py`
  - Remove request-time Excel fallback in forecast/export context setup.
  - Keep Excel reads only in explicit sync/upload endpoints.
- Modify: `tests/test_current_month_integration.py`
  - Update loader tests from Excel+DB merge to DB-only request loader.
- Modify: `tests/test_app.py`
  - Add route-level guard tests that monkeypatch `pandas.read_excel` to fail during page/export requests.
- Modify: `infrastructure/backend/database_schema.md`
  - Update actual SQLite schema and DB-first request contract.
- Optional Modify: `ROADMAP.md`
  - Add or mark DB-first migration status.

## Phase 1: Add DB-Backed Sales Detail Loader

**Files:**
- Modify: `src/backend/data_loader.py`
- Test: `tests/test_current_month_integration.py`

- [ ] **Step 1: Write failing DB loader tests**

Add tests that seed `sales_records` and `current_month_records`, then assert the new loader returns the normalized Chinese-column DataFrame shape expected by `forecast_engine`:

- `年`
- `月`
- `日`
- `客戶簡稱`
- `商品號`
- `商品簡稱`
- `銷+贈S量`
- `單價NT(淨)`
- `含稅總額(淨)`
- `order_date`

Run:

```bash
python3 -m pytest tests/test_current_month_integration.py -q
```

Expected: FAIL because the DB-only loader does not exist yet.

- [ ] **Step 2: Implement DB loader**

Add a function with a clear request-time name, for example:

```python
def load_sales_detail_from_db(db: MORDatabase) -> pd.DataFrame:
    ...
```

Implementation rules:

- Query `sales_records` and `current_month_records`.
- Normalize to the same DataFrame columns as `prepare_sales_data()`.
- Preserve `normalize_product_code()`.
- Return an empty normalized DataFrame or raise a clear error if DB has no sales rows; choose one behavior and test it.
- Do not read Excel.

- [ ] **Step 3: Keep Excel loader explicit**

Keep existing Excel behavior for ETL/tests, but make naming and docstrings clear:

- Request code should call the DB loader.
- Excel parsing remains import/sync support only.

- [ ] **Step 4: Verify Phase 1**

Run:

```bash
python3 -m pytest tests/test_current_month_integration.py -q
```

Expected: PASS.

## Phase 2: Move Forecast Context To DB Loader

**Files:**
- Modify: `src/backend/operational_views.py`
- Modify: `tests/test_operational_views.py`
- Possibly modify route tests in `tests/test_app.py`

- [ ] **Step 1: Write failing context test**

Add or update a test proving `build_forecast_page_context(..., db, ...)` includes sales rows seeded in `sales_records` and `current_month_records` without relying on Excel fixtures.

Run:

```bash
python3 -m pytest tests/test_operational_views.py tests/test_current_month_integration.py -q
```

Expected: FAIL until context uses the DB loader.

- [ ] **Step 2: Update `build_forecast_page_context()`**

Change its first sales load to DB-backed loading:

```python
data = load_sales_detail_from_db(db)
```

Keep downstream behavior unchanged:

- `default_target_from_data()`
- `build_forecast()`
- item visibility
- adjustments
- budget enrichment
- monitor rows
- health summary

- [ ] **Step 3: Verify Phase 2**

Run:

```bash
python3 -m pytest tests/test_operational_views.py tests/test_current_month_integration.py -q
```

Expected: PASS.

## Phase 3: Remove Request-Time Excel Reads From Routes

**Files:**
- Modify: `src/backend/app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Add route guard tests**

Add tests that monkeypatch `pandas.read_excel` to raise an assertion for normal request routes:

- `GET /`
- `GET /forecast`
- `GET /monitor/products`
- `GET /settings`
- `POST /export`
- `POST /snapshots/save`

Seed required DB rows directly in the isolated test DB.

Run:

```bash
python3 -m pytest tests/test_app.py -q
```

Expected: FAIL on routes that still call Excel loader.

- [ ] **Step 2: Update `_load_context_from_request()`**

Remove the preliminary Excel read in `src/backend/app.py`.

Use the DB-backed sales data only to derive the default target, or let `build_forecast_page_context()` own that responsibility through a small helper if cleaner.

- [ ] **Step 3: Update `/export`**

Remove:

```python
data = load_sales_detail(data_base_path, forecast_config)
default_target = default_target_from_data(data, forecast_config)
```

Derive target from DB-backed context or a DB-loaded sales DataFrame.

- [ ] **Step 4: Confirm allowed Excel routes still work**

Do not block these explicit import routes from using Excel:

- `/sync`
- `/upload/current-month`
- `/monitor/products/import`

- [ ] **Step 5: Verify Phase 3**

Run:

```bash
python3 -m pytest tests/test_app.py -q
```

Expected: PASS.

## Phase 4: Update Tests Away From Monkeypatched Excel Loaders

**Files:**
- Modify: `tests/test_app.py`
- Modify: `tests/test_operational_views.py`
- Modify: any focused tests that monkeypatch `load_sales_detail`

- [ ] **Step 1: Identify route tests using `load_sales_detail` monkeypatches**

Run:

```bash
grep -RIn "monkeypatch.setattr(.*load_sales_detail" tests
```

- [ ] **Step 2: Convert high-value route tests to DB fixtures**

For tests covering real route behavior, seed SQLite tables instead of monkeypatching sales data.

Keep monkeypatches only where the test is explicitly about route orchestration and not data access.

- [ ] **Step 3: Verify Phase 4**

Run:

```bash
python3 -m pytest tests/test_app.py tests/test_operational_views.py -q
```

Expected: PASS.

## Phase 5: Documentation And Guardrails

**Files:**
- Modify: `infrastructure/backend/database_schema.md`
- Optional Modify: `ROADMAP.md`
- Optional Modify: `docs/workflows/local-setup.md` if setup behavior changes

- [ ] **Step 1: Update database schema doc**

Document the actual SQLite tables already created by `src/backend/database.py`, especially:

- `sales_records`
- `current_month_records`
- `budget_targets`
- `item_configs`
- `forecast_adjustments`
- `daily_sales_actuals`
- `month_close_records`
- `forecast_snapshots`
- `snapshot_items`

- [ ] **Step 2: Document DB-first request rule**

Add a short rule:

> Page requests and exports read from `mor_workbench.db`; Excel is parsed only by sync/import endpoints.

- [ ] **Step 3: Verify docs and syntax**

Run:

```bash
python3 -m py_compile app.py src/backend/app.py src/backend/data_loader.py src/backend/operational_views.py src/backend/database.py src/backend/etl.py
python3 -m pytest -q
```

Expected: PASS.

## Phase 6: Final Regression Check

**Files:**
- No planned edits unless regressions are found.

- [ ] **Step 1: Run full test suite**

```bash
python3 -m pytest -q
```

Expected: PASS.

- [ ] **Step 2: Review diff**

```bash
git diff -- src/backend/data_loader.py src/backend/operational_views.py src/backend/app.py tests infrastructure/backend/database_schema.md ROADMAP.md
```

Expected:

- No broad refactors.
- No new dependencies.
- Excel reads remain only in ETL/import paths.
- Route tests protect DB-first behavior.

- [ ] **Step 3: Manual browser smoke test**

Start the app:

```bash
python3 app.py
```

Open and check:

- `/`
- `/forecast`
- `/monitor/products`
- `/settings`
- `/monthly-review`

Expected:

- Pages render from DB data.
- Forecast adjustment saves still persist.
- Export downloads workbook using DB-backed forecast data.

## Risks

- Existing test suite relies heavily on monkeypatching `load_sales_detail`; converting all tests at once may be noisy. Prefer converting route-critical tests first.
- If local `mor_workbench.db` has not been synced, DB-first pages may have no historical data. The UI should show a clear sync-required error rather than silently falling back to Excel.
- `forecast_engine` expects the historical DataFrame shape. The DB loader must preserve that contract exactly before deeper refactors are attempted.

## Recommended Commit Order

1. `test: cover db-backed sales detail loading`
2. `feat: load forecast context from sqlite sales records`
3. `test: guard routes against request-time excel reads`
4. `feat: remove request-time excel reads from routes`
5. `docs: document db-first request data contract`
