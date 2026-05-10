# Database Schema — mor_workbench.db

## DB-First Request Rule

> Page requests and exports read from `mor_workbench.db`.
> Excel is parsed **only** by sync/import endpoints:
> - `POST /sync` via `sync_excel_to_db()`
> - `POST /upload/current-month` via SHPB upload
> - `POST /monitor/products/import` via daily actual upload
> - Tests/fixtures that intentionally construct Excel inputs

All normal user-facing page requests and the export use:
- `load_sales_detail_from_db(db)` — queries `sales_records UNION ALL current_month_records`
- `default_target_from_db(db)` — cheap MAX(order_date) query for default forecast target

---

## Sales Data Tables

Both tables share the same column structure. `load_sales_detail_from_db()` queries them with UNION ALL.

### `sales_records`
Historical sales — populated by `sync_excel_to_db()`, replaced wholesale on each sync.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| order_date | DATE NOT NULL | stored as `'YYYY-MM-DD'` |
| customer_name | TEXT NOT NULL | |
| product_code | TEXT NOT NULL | |
| product_name | TEXT | |
| quantity | REAL DEFAULT 0 | |
| unit_price | REAL DEFAULT 0 | |
| amount | REAL DEFAULT 0 | |

Indexes: `idx_sales_date` on `order_date`, `idx_sales_product` on `product_code`.

### `current_month_records`
Current-month cumulative sales — populated by SHPB upload, replaced per month on re-upload, cleared on sync once the month is covered by `sales_records`.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| order_date | DATETIME | stored as `'YYYY-MM-DD HH:MM:SS'` |
| customer_name | TEXT NOT NULL | |
| product_code | TEXT NOT NULL | |
| product_name | TEXT | |
| quantity | REAL DEFAULT 0 | |
| unit_price | REAL DEFAULT 0 | |
| amount | REAL DEFAULT 0 | |
| imported_at | TIMESTAMP DEFAULT CURRENT_TIMESTAMP | used in cache key |

---

## Configuration / Planning Tables

### `item_configs`
Global product settings (one row per product_code).

| Column | Type | Default |
|---|---|---|
| product_code | TEXT PK | |
| is_excluded | INTEGER | 0 |
| is_budgeted | INTEGER | 1 |
| is_visible | INTEGER | 1 |
| price_quantity | REAL | 0 |
| item_status | TEXT | `'active'` |
| status_label | TEXT | NULL |
| custom_category | TEXT | NULL |

### `budget_targets`
Monthly budget per customer-product pair.

| Column | Type |
|---|---|
| year | INTEGER |
| month | INTEGER |
| customer_name | TEXT |
| product_code | TEXT |
| target_quantity | REAL |
| target_amount | REAL |
| base_target_quantity | REAL |

PK: `(year, month, customer_name, product_code)`

### `forecast_adjustments`
User manual overrides per customer-product pair per month.

| Column | Type | Notes |
|---|---|---|
| year | INTEGER | |
| month | INTEGER | |
| customer_name | TEXT | |
| product_code | TEXT | |
| manual_quantity | REAL | NULL = cleared |
| adjustment_reason | TEXT | |
| updated_by | TEXT DEFAULT 'System' | |
| updated_at | TIMESTAMP | |

PK: `(year, month, customer_name, product_code)`

---

## Operational Tables

### `daily_sales_actuals`
Current-month daily sales imported from monitor workbooks.

| Column | Type |
|---|---|
| id | INTEGER PK |
| import_batch_id | INTEGER |
| sales_year | INTEGER |
| sales_month | INTEGER |
| customer_name | TEXT |
| product_code | TEXT |
| product_name | TEXT |
| actual_quantity | REAL |
| taxed_amount | REAL |
| latest_sales_date | DATE |

### `month_close_records`
Tracks which months have been closed (locked against re-import).

| Column | Type |
|---|---|
| id | INTEGER PK |
| year | INTEGER |
| month | INTEGER |
| closed_at | TIMESTAMP |
| note | TEXT |
| final_snapshot_id | INTEGER |

### `forecast_snapshots` / `snapshot_items`
Point-in-time forecast saves (Draft / Final / CloseMonth).

**forecast_snapshots**: id, year, month, snapshot_name, snapshot_type, created_by, created_at, is_finalized

**snapshot_items**: id, snapshot_id, customer_name, product_code, system_forecast, manual_adjustment, final_forecast

### `workday_calendar`
Cached workday schedule used for cycle-delay calculations.

| Column | Type |
|---|---|
| calendar_date | DATE PK |
| is_workday | INTEGER |
| year | INTEGER |
