# MOR Data Contract

## Purpose

This document defines the source Excel columns, DB-first runtime fields, and export-facing row model used by MOR. It is the single place to resolve naming drift between importers, forecast engine, form parser, and exporter code.

## Source Excel Columns

Raw input is read from sales detail workbooks only during explicit sync/import flows. Normal runtime reads use `mor_workbench.db`.

| Raw Excel column | Meaning | Normalized field |
| --- | --- | --- |
| `日期` | Transaction date | `sales_date` |
| `客戶簡稱` | Customer name / short name | `customer_name` |
| `商品號` | Product code | `product_code` |
| `商品名稱` | Product name | `product_name` |
| `數量` | Sold quantity | `quantity` |
| `售價` | Unit price | `unit_price` |

## Runtime Row Shape

Importers normalize raw Excel data into DB rows. Forecast runtime code then reads a stable internal row shape from the workbench DB.

Required fields:

```text
sales_date
customer_name
product_code
product_name
quantity
unit_price
```

Recommended derived fields:

```text
order_date
customer_key
product_key
amount
source_row_index
```

## Forecast Row Model

Forecast rows should expose a clear review model for the UI and exporter.

```text
row_id
customer_name
product_code
product_name
latest_order_date
cycle_days
next_order_date
last_year_same_month_qty
this_year_same_month_qty
latest_price
system_forecast
manual_adjustment
final_forecast
estimated_amount
forecast_basis
adjustment_reason
excluded
auto_in_month
```

## Review State Rules

- `system_forecast` is the generated quantity before user edits.
- `manual_adjustment` is the submitted override quantity, if any.
- `final_forecast` is `manual_adjustment` when present, otherwise `system_forecast`.
- `excluded = true` forces exported amount to zero.
- `estimated_amount` is derived from `final_forecast` and the row amount calculation seam unless excluded.

## Export Shape

The exported workbook should preserve the review state that was submitted from the UI.

- Do not silently rename or recompute reviewed fields during export.
- Do not depend on the browser DOM as the source of truth.
- Do serialize the posted manual quantities and exclusions into the final workbook.

## Compatibility Notes

- This document is a data contract, not a full relational database schema.
- Runtime services should prefer backend context/input interfaces over direct table-shaped maps.
