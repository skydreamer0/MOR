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
- `ForecastPageContext._patch_target_month_actuals()` — overlays target-month
  `daily_sales_actuals` quantity/amount onto forecast rows for dashboard,
  customer, and product analytics
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
| order_date | DATE NOT NULL | stored as date/datetime text accepted by pandas mixed parsing |
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

### `daily_import_batches`
One row per daily sales import workbook.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| source_filename | TEXT NOT NULL | |
| source_hash | TEXT NOT NULL | |
| sales_year | INTEGER NOT NULL | |
| sales_month | INTEGER NOT NULL | |
| imported_at | TIMESTAMP DEFAULT CURRENT_TIMESTAMP | |
| row_count | INTEGER DEFAULT 0 | |
| date_start | DATE | |
| date_end | DATE | |
| quantity_total | REAL DEFAULT 0 | |
| taxed_amount_total | REAL DEFAULT 0 | |
| status | TEXT DEFAULT `'success'` | |
| message | TEXT | |

### `daily_sales_actuals`
Current-month daily sales imported from monitor workbooks.
For the selected target month, forecast page context overlays these imported
actuals onto `ForecastRow.ty_monthly` and `ForecastRow.ty_monthly_amount` so
customer/product analytics show the same current quantity and taxed amount as
the monitor import.

| Column | Type |
|---|---|
| id | INTEGER PK AUTOINCREMENT |
| sales_year | INTEGER NOT NULL |
| sales_month | INTEGER NOT NULL |
| sales_date | DATE NOT NULL |
| customer_code | TEXT |
| customer_name | TEXT NOT NULL |
| product_code | TEXT NOT NULL |
| product_name | TEXT |
| sales_quantity | REAL DEFAULT 0 |
| gift_quantity | REAL DEFAULT 0 |
| actual_quantity | REAL DEFAULT 0 |
| net_unit_price | REAL DEFAULT 0 |
| taxed_amount | REAL DEFAULT 0 |
| bonus_basis_amount | REAL DEFAULT 0 |
| invoice_number | TEXT |
| shipment_number | TEXT |
| order_type | TEXT |
| performance_type | TEXT |
| import_batch_id | INTEGER |

Indexes: `idx_daily_actuals_month` on `(sales_year, sales_month)`, `idx_daily_actuals_row` on `(customer_name, product_code)`.

### `month_close_records`
Tracks which months have been closed (locked against re-import).

| Column | Type |
|---|---|
| id | INTEGER PK AUTOINCREMENT |
| year | INTEGER NOT NULL |
| month | INTEGER NOT NULL |
| closed_at | TIMESTAMP DEFAULT CURRENT_TIMESTAMP |
| source_batch_id | INTEGER |
| actual_row_count | INTEGER DEFAULT 0 |
| actual_quantity_total | REAL DEFAULT 0 |
| actual_amount_total | REAL DEFAULT 0 |
| note | TEXT |
| final_snapshot_id | INTEGER |

Constraint: `UNIQUE (year, month)`.

### `forecast_snapshots` / `snapshot_items`
Point-in-time forecast saves (Draft / Final / CloseMonth).

**forecast_snapshots**: id, snapshot_name, snapshot_type, year, month, created_by, created_at

**snapshot_items**: id, snapshot_id, customer_name, product_code, system_forecast, manual_adjustment, final_forecast

### `workday_calendar`
Cached workday schedule used for cycle-delay calculations.

| Column | Type |
|---|---|
| date | TEXT PK |
| is_workday | INTEGER NOT NULL DEFAULT 1 |
| holiday_name | TEXT |
| source | TEXT |
| note | TEXT |
