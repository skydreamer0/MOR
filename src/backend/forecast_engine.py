from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Iterable

import pandas as pd

from src.backend.data_loader import prepare_sales_data
from src.backend.forecast_config import ForecastConfig
from src.backend.forecast_models import ForecastOptions, ForecastRow, ForecastSummary, ForecastTarget

__all__ = [
    "ForecastOptions",
    "ForecastRow",
    "ForecastSummary",
    "ForecastTarget",
    "apply_user_adjustments",
    "build_forecast",
]


def build_forecast(
    data: pd.DataFrame,
    target: ForecastTarget,
    options: ForecastOptions | None = None,
    config: ForecastConfig | None = None,
) -> ForecastSummary:
    config = config or ForecastConfig()
    options = options or ForecastOptions(max_cycle_interval_days=config.max_cycle_interval_days)
    prepared = prepare_sales_data(data, config)
    rows: list[ForecastRow] = []

    for (customer, product_code), group in prepared.groupby(["客戶簡稱", "商品號"], dropna=False):
        group = group.sort_values("order_date")
        product_name = _latest_nonempty(group["商品簡稱"])
        latest_row = group.iloc[-1]
        latest_price = float(latest_row["單價NT(淨)"] or 0)
        latest_order_date = latest_row["order_date"].date()
        order_history = _order_history_by_date(group)

        cycle_days = _average_cycle_days(order_history["order_date"].tolist(), options.max_cycle_interval_days)
        next_order_date = latest_order_date + timedelta(days=cycle_days) if cycle_days else None
        auto_in_month = bool(next_order_date and target.start <= next_order_date <= target.end)
        recent_avg_qty = float(order_history["銷+贈S量"].tail(3).mean()) if not order_history.empty else 0.0

        if not options.include_all and not auto_in_month:
            continue

        forecast_quantity = recent_avg_qty if auto_in_month else 0.0
        estimated_amount = forecast_quantity * latest_price
        rows.append(
            ForecastRow(
                row_id=_row_id(customer, product_code),
                customer=str(customer),
                product_code=str(product_code),
                product_name=str(product_name),
                latest_order_date=latest_order_date,
                cycle_days=cycle_days,
                next_order_date=next_order_date,
                auto_in_month=auto_in_month,
                last_year_same_month_qty=_month_quantity(group, target.year - 1, target.month),
                this_year_same_month_qty=_month_quantity(group, target.year, target.month),
                latest_price=latest_price,
                forecast_quantity=forecast_quantity,
                manual_quantity=None,
                effective_quantity=forecast_quantity,
                estimated_amount=estimated_amount,
                forecast_basis="cycle" if auto_in_month else "not_due",
                excluded=False,
            )
        )

    rows = sorted(rows, key=lambda row: (not row.auto_in_month, row.customer, row.product_code))
    return ForecastSummary(year=target.year, month=target.month, rows=rows, total=_total(rows))


def apply_user_adjustments(
    summary: ForecastSummary,
    manual_quantities: dict[str, float | None],
    excluded_ids: set[str],
) -> ForecastSummary:
    rows = [
        row.with_adjustment(
            manual_quantity=manual_quantities[row.row_id] if row.row_id in manual_quantities else row.manual_quantity,
            excluded=row.row_id in excluded_ids,
        )
        for row in summary.rows
    ]
    return replace(summary, rows=rows, total=_total(rows))


def _total(rows: Iterable[ForecastRow]) -> float:
    return sum(row.estimated_amount for row in rows if not row.excluded)


def _order_history_by_date(group: pd.DataFrame) -> pd.DataFrame:
    return (
        group.groupby("order_date", as_index=False)
        .agg({"銷+贈S量": "sum", "單價NT(淨)": "last"})
        .sort_values("order_date")
    )


def _average_cycle_days(order_dates: list[pd.Timestamp], max_cycle_interval_days: int) -> int | None:
    if len(order_dates) < 2:
        return None

    intervals = [
        (current.date() - previous.date()).days
        for previous, current in zip(order_dates, order_dates[1:])
        if 0 < (current.date() - previous.date()).days <= max_cycle_interval_days
    ]
    if not intervals:
        return None

    return max(1, int(round(sum(intervals) / len(intervals))))


def _month_quantity(group: pd.DataFrame, year: int, month: int) -> float:
    matched = group[(group["年"] == year) & (group["月"] == month)]
    return float(matched["銷+贈S量"].sum())


def _latest_nonempty(values: pd.Series) -> str:
    for value in reversed(values.dropna().tolist()):
        if str(value).strip():
            return str(value)
    return ""


def _row_id(customer: object, product_code: object) -> str:
    return f"{customer}__{product_code}"
