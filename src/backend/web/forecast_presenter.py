from __future__ import annotations

from datetime import date
import re

from src.backend.forecast_models import ForecastRow, ForecastSummary

_ELI_DOSE_PATTERN = re.compile(r"^(ELI|ＥＬＩ)\s*(\d+(?:\.\d+)?)")


def column_schema() -> list[dict]:
    return [
        _column("auto_in_month", "狀態", "status"),
        _column("customer", "醫院 (客戶)", "text"),
        _column("product_name", "品項名稱", "text"),
        _column("trend_6m", "半年趨勢", "sparkline"),
        _column("last_month_actual", "上月實際", "number", align="right"),
        _column("last_month_budget", "上月預算", "number", align="right"),
        _column("last_month_rate", "上月達成率", "percent", align="right"),
        _column("last_month_gap", "上月 GAP", "number", align="right"),
        _column("last_year_same_month_qty", "去年同期量", "number", align="right"),
        _column("this_year_same_month_qty", "實際數量 (本月)", "number", align="right"),
        _column("system_forecast", "系統預估", "number", align="right"),
        _column("manual_adjustment", "人工調整", "number", align="right", editable=True),
        _column("final_forecast", "最終預估", "number", align="right"),
        _column("budget_quantity", "預算目標", "number", align="right"),
        _column("achievement_rate", "達成率", "percent", align="right"),
        _column("diff", "差異", "number", align="right"),
        _column("excluded", "納入計算", "badge", align="right"),
        _column("estimated_amount", "預估金額", "currency", align="right"),
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


def product_display_name(product_name: object) -> str:
    text = str(product_name or "")
    match = _ELI_DOSE_PATTERN.match(text)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return text[:3]


def _column(key: str, label: str, column_type: str, align: str = "left", editable: bool = False) -> dict:
    return {
        "key": key,
        "label": label,
        "type": column_type,
        "align": align,
        "editable": editable,
    }


def _serialize_row(row: ForecastRow) -> dict:
    last_month_rate = (row.last_month_actual / row.last_month_budget * 100) if row.last_month_budget > 0 else 0.0
    return {
        "row_id": row.row_id,
        "customer": row.customer,
        "product_code": row.product_code,
        "product_name": row.product_name,
        "latest_order_date": _date_to_iso(row.latest_order_date),
        "cycle_days": row.cycle_days,
        "next_order_date": _date_to_iso(row.next_order_date),
        "auto_in_month": row.auto_in_month,
        "last_month_actual": row.last_month_actual,
        "last_month_budget": row.last_month_budget,
        "last_month_rate": round(last_month_rate, 1),
        "last_month_gap": round(row.last_month_actual - row.last_month_budget, 2),
        "trend_6m": row.trend_6m or [0.0] * 6,
        "avg_3m": row.avg_3m,
        "last_year_same_month_qty": row.last_year_same_month_qty,
        "this_year_same_month_qty": row.this_year_same_month_qty,
        "latest_price": row.latest_price,
        "system_forecast": row.system_forecast,
        "manual_adjustment": row.manual_adjustment,
        "final_forecast": row.final_forecast,
        "budget_quantity": row.budget_quantity,
        "achievement_rate": (row.final_forecast / row.budget_quantity * 100) if row.budget_quantity > 0 else 0,
        "diff": row.final_forecast - row.budget_quantity,
        "estimated_amount": row.estimated_amount,
        "forecast_basis": row.forecast_basis,
        "excluded": row.excluded,
        "ly_monthly": row.ly_monthly,
        "ty_monthly": row.ty_monthly,
        "budget_monthly": row.budget_monthly,
        "ly_price": row.ly_price,
    }


def _date_to_iso(value: date | None) -> str | None:
    return value.isoformat() if value else None
