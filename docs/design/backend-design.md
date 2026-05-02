# MOR Backend Design

## Goals

The backend should stay boring, explicit, and testable. Its main job is to load trusted local Excel files, calculate a forecast summary, accept manual adjustments, and export a workbook.

## Boundaries

| Layer | Owns | Should Not Own |
| --- | --- | --- |
| Flask routes | HTTP request/response, status codes, template context | Forecast math, Excel schemas |
| Data loader | Excel file path, sheet, required columns, normalization | Web form concerns |
| Forecast engine | Customer/product grouping, cycle calculation, totals | Flask, file system, templates |
| Form parser | Request field parsing and validation | Forecast math |
| Exporter | Workbook shape and sheet names | HTTP response details |
| Config | File names, sheet names, column names, limits | Runtime business decisions |

## Public Backend Interfaces

Target interface shape:

```python
load_sales_detail(base_path, config) -> DataFrame
build_forecast(data, target, options, config) -> ForecastSummary
apply_user_adjustments(summary, manual_quantities, excluded_ids) -> ForecastSummary
export_forecast(summary) -> BytesIO
```

## Domain Model

`ForecastTarget`

- `year`
- `month`
- `start`
- `end`

`ForecastRow`

- Identity: `row_id`, `customer`, `product_code`, `product_name`
- Timing: `latest_order_date`, `cycle_days`, `next_order_date`, `auto_in_month`
- History: `last_year_same_month_qty`, `this_year_same_month_qty`
- Amounts: `latest_price`, `forecast_quantity`, `manual_quantity`, `effective_quantity`, `estimated_amount`
- Review state: `forecast_basis`, `excluded`

`ForecastSummary`

- `year`
- `month`
- `rows`
- `total`
- derived counts for UI display

## Error Handling

Backend errors should become user-readable messages:

- Missing Excel file: show source file path and stop rendering data table.
- Missing required columns: list missing columns.
- Invalid year/month: return validation message.
- Invalid manual quantity: reject export with `400` and explain the bad field category.

Do not allow raw tracebacks to become the normal user experience.

## Test Strategy

Required test groups:

- Forecast engine: cycle window, recent average quantity, same-month history, price selection.
- Adjustment logic: manual override, blank override, exclusion total.
- Form parsing: missing values, invalid month, non-numeric and negative quantities.
- Export: workbook has `預估總覽`, `預估明細`, `排除明細`.
- Flask: homepage loads, invalid export returns `400`, missing file renders friendly message.

## Future Backend Fit

If MOR grows, add features in this order:

1. Use `web/forecast_presenter.py` as the JSON-safe presenter for forecast summaries and review-grid column metadata.
2. Expose JSON endpoints only when the frontend needs richer interaction such as async preview or full JSON bootstrapping.
3. Persist monthly forecast drafts as JSON or SQLite.
4. Add budget workbook ingestion as a separate loader.
5. Add comparison services for budget/actual/forecast.

Current API gate: `web/forecast_presenter.py` may exist without public `/api/*` routes. Public API routes should be added only after presenter tests define the payload shape and the frontend has a concrete need.
