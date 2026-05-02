# Database & Data Model Schema

## Overview
Currently, MOR relies heavily on in-memory operations and Excel files rather than a persistent relational database. However, structured Domain Models emulate schema structures. If history/draft versioning is implemented, PostgreSQL or SQLite will be used.

---

## Domain Entity Schemas (snake_case structured)

### 1. forecast_target
Defines the current target period of the forecasting engine.
- `year` (int): Forecasting target year.
- `month` (int): Forecasting target month.
- `start_date` (date): The first day of the target month.
- `end_date` (date): The last day of the target month.

### 2. forecast_row
Represents a unique customer-product combination.
- `row_id` (string): Unique identifier (e.g. `customer_name__product_code`).
- `customer_name` (string): Standardized name of the customer.
- `product_code` (string): Product identifier.
- `product_name` (string): Display name of the product.
- `latest_order_date` (date): Date of their most recent purchase.
- `cycle_days` (int): Calculated average buying cycle in days.
- `next_order_date` (date): `latest_order_date` + `cycle_days`.
- `auto_in_month` (boolean): Flag indicating if the `next_order_date` falls in the target month.
- `last_year_same_month_qty` (int): History reference.
- `latest_price` (float): Discovered price for the product.
- `forecast_quantity` (int): System calculated baseline quantity.
- `manual_quantity` (int, nullable): User override.
- `effective_quantity` (int): Final quantity used (manual if exists, else forecast).
- `excluded` (boolean): Review flag.
- `estimated_amount` (float): `effective_quantity` * `latest_price` (0 if excluded).

### 3. forecast_summary
- `year` (int)
- `month` (int)
- `rows` (list of `forecast_row`)
- `total_amount` (float): Grand total of all `estimated_amount` for included rows.
- `metrics` (dict): Derived data counts (total rows, auto rows, manually edited rows, etc.).

---

## Excel File Schema Requirements

### Input Source: `業績明細 Excel`
- **Required Columns:** `日期`, `客戶簡稱`, `商品號`, `商品名稱`, `數量`, `售價`
- **Row Limits:** Evaluates against recent history to ensure operational speed without running out of memory.

### Output Source: Forecast Workbook
- **Sheet 1:** `預估總覽` (Summary stats and grand totals)
- **Sheet 2:** `預估明細` (Included rows with final quantities and amounts)
- **Sheet 3:** `排除明細` (Rows explicitly flagged as excluded by the user)
