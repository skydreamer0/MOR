# MOR Data Model

## Purpose

This document describes the current runtime data model and the domain objects that must stay stable across DB, UI, and export workflows.

## Current Reality

MOR uses the local SQLite workbench database (`mor_workbench.db`) as the active runtime source.

Excel files are parsed only through explicit sync/import flows. Normal page requests, forecast review, monthly review, settings, dashboard metrics, and exports read from the workbench DB.

## Domain Objects

### `ForecastTarget`

Fields:

- `year`
- `month`
- `start`
- `end`

### `ForecastRow`

Fields:

- Identity: `row_id`, `customer_name`, `product_code`, `product_name`
- Timing: `latest_order_date`, `cycle_days`, `next_order_date`, `auto_in_month`
- History: `last_year_same_month_qty`, `this_year_same_month_qty`
- Amounts: `latest_price`, `system_forecast`, `manual_adjustment`, `final_forecast`, `estimated_amount`
- Review state: `forecast_basis`, `adjustment_reason`, `excluded`
- Budget and item settings: `budget_quantity`, `budget_amount`, `price_quantity`, `item_status`, monthly budget arrays

### `ForecastSummary`

Fields:

- `year`
- `month`
- `rows`
- `total`
- UI counts derived from row state

## Persistence Notes

The SQLite workbench DB stores:

- A stable row identity.
- The selected forecast target month.
- Manual forecast adjustments and reasons.
- Item settings, including exclusion, visibility, budget inclusion, price quantity, and status.
- Budget targets and imported actual sales.
- Forecast snapshots and close-month records.

The domain model should continue to hide DB table shape from templates and routes.
