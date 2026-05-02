# MOR Data Model

## Purpose

This document describes the current domain model and the shape a future persistent store would need to preserve.

## Current Reality

MOR does not use a relational database today.

The active data source is a local Excel workbook, and the app builds an in-memory forecast summary for review and export.

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
- Amounts: `latest_price`, `forecast_quantity`, `manual_quantity`, `effective_quantity`, `estimated_amount`
- Review state: `forecast_basis`, `excluded`

### `ForecastSummary`

Fields:

- `year`
- `month`
- `rows`
- `total`
- UI counts derived from row state

## Future Persistence Notes

If persistence is added later, it should store:

- A stable row identity.
- The selected forecast target month.
- Manual quantities.
- Exclusion state.
- Source workbook metadata or hash.

The persistence layer should extend the domain model, not replace it.
