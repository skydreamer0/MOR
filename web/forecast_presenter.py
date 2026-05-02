from __future__ import annotations

from datetime import date

from forecast_models import ForecastRow, ForecastSummary


def column_schema() -> list[dict]:
    return [
        _column("auto_in_month", "狀態", "status"),
        _column("customer", "客戶", "text"),
        _column("product_code", "商品號", "text"),
        _column("product_name", "商品", "text"),
        _column("latest_order_date", "最近叫貨日", "date"),
        _column("cycle_days", "週期天數", "number", align="right"),
        _column("next_order_date", "推估下次", "date"),
        _column("last_year_same_month_qty", "去年同月量", "number", align="right"),
        _column("this_year_same_month_qty", "今年同月量", "number", align="right"),
        _column("latest_price", "最近單價", "currency", align="right"),
        _column("forecast_quantity", "系統數量", "number", align="right"),
        _column("manual_quantity", "人工數量", "number", align="right", editable=True),
        _column("estimated_amount", "預估金額", "currency", align="right"),
        _column("excluded", "排除", "boolean", editable=True),
    ]


def serialize_summary(summary: ForecastSummary) -> dict:
    return {
        "target": {"year": summary.year, "month": summary.month},
        "summary": {
            "total": summary.total,
            "row_count": summary.row_count,
            "auto_row_count": summary.auto_row_count,
            "included_count": sum(1 for row in summary.rows if not row.excluded),
            "excluded_count": sum(1 for row in summary.rows if row.excluded),
        },
        "columns": column_schema(),
        "rows": [_serialize_row(row) for row in summary.rows],
    }


def _column(key: str, label: str, column_type: str, align: str = "left", editable: bool = False) -> dict:
    return {
        "key": key,
        "label": label,
        "type": column_type,
        "align": align,
        "editable": editable,
    }


def _serialize_row(row: ForecastRow) -> dict:
    return {
        "row_id": row.row_id,
        "customer": row.customer,
        "product_code": row.product_code,
        "product_name": row.product_name,
        "latest_order_date": _date_to_iso(row.latest_order_date),
        "cycle_days": row.cycle_days,
        "next_order_date": _date_to_iso(row.next_order_date),
        "auto_in_month": row.auto_in_month,
        "last_year_same_month_qty": row.last_year_same_month_qty,
        "this_year_same_month_qty": row.this_year_same_month_qty,
        "latest_price": row.latest_price,
        "forecast_quantity": row.forecast_quantity,
        "manual_quantity": row.manual_quantity,
        "effective_quantity": row.effective_quantity,
        "estimated_amount": row.estimated_amount,
        "forecast_basis": row.forecast_basis,
        "excluded": row.excluded,
    }


def _date_to_iso(value: date | None) -> str | None:
    return value.isoformat() if value else None
