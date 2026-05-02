# MOR Data Contract

## Purpose

This document defines the source Excel columns, normalized field names, and export-facing row model used by MOR. It is the single place to resolve naming drift between loader, forecast engine, form parser, and exporter code.

## Source Excel Columns

Raw input is read from the sales detail workbook.

| Raw Excel column | Meaning | Normalized field |
| --- | --- | --- |
| `日期` | Transaction date | `sales_date` |
| `客戶簡稱` | Customer name / short name | `customer_name` |
| `商品號` | Product code | `product_code` |
| `商品名稱` | Product name | `product_name` |
| `數量` | Sold quantity | `quantity` |
| `售價` | Unit price | `unit_price` |

## Normalized Row Shape

The loader should normalize raw Excel data into a stable internal row shape.

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
forecast_quantity
manual_quantity
effective_quantity
estimated_amount
forecast_basis
excluded
auto_in_month
```

## Review State Rules

- `forecast_quantity` is the system-generated quantity before user edits.
- `manual_quantity` is the submitted override quantity, if any.
- `effective_quantity` is `manual_quantity` when present, otherwise `forecast_quantity`.
- `excluded = true` forces exported amount to zero.
- `estimated_amount` is derived from `effective_quantity * latest_price` unless excluded.

## Export Shape

The exported workbook should preserve the review state that was submitted from the UI.

- Do not silently rename or recompute reviewed fields during export.
- Do not depend on the browser DOM as the source of truth.
- Do serialize the posted manual quantities and exclusions into the final workbook.

## Compatibility Notes

- This document is a data contract, not a relational database schema.
- If persistence is added later, the persistent storage schema should extend this contract rather than redefine it.
