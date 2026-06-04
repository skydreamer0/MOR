from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Iterable

import pandas as pd

from src.backend.data_loader import prepare_sales_data
from src.backend.forecast_config import ForecastConfig
from src.backend.forecast_models import ForecastOptions, ForecastRow, ForecastSummary, ForecastTarget
from src.backend.row_identity import make_row_id

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

        # Global exclusion check
        is_item_excluded = bool(options and product_code in options.excluded_item_ids)

        latest_row = group.iloc[-1]
        latest_price = float(latest_row["單價NT(淨)"] or 0)
        latest_order_date = latest_row["order_date"].date()
        order_history = _order_history_by_date(group)

        cycle_days = _average_cycle_days(order_history["order_date"].tolist(), options.max_cycle_interval_days)
        next_order_date = latest_order_date + timedelta(days=cycle_days) if cycle_days else None
        auto_in_month = bool(next_order_date and target.start <= next_order_date <= target.end)

        # Build pivot tables once per group instead of ~48 individual DataFrame filters.
        qty_pivot = group.groupby(["年", "月"])["銷+贈S量"].sum()
        amt_pivot = group.groupby(["年", "月"])["含稅總額(淨)"].sum()

        def _pqty(year: int, month: int) -> float:
            return float(qty_pivot.get((year, month), 0.0))

        def _pamt(year: int, month: int) -> float:
            return float(amt_pivot.get((year, month), 0.0))

        # New Forecast Logic
        lysm_qty = _pqty(target.year - 1, target.month)
        last_month_year = target.year if target.month > 1 else target.year - 1
        last_month_val = target.month - 1 if target.month > 1 else 12
        lm_qty = _pqty(last_month_year, last_month_val)

        avg_3m_qty = _recent_months_average_from_pivot(qty_pivot, target.year, target.month, 3)
        current_progress = _pqty(target.year, target.month)

        # Full-year monthly breakdown for sidebar detail table and analytics
        ly_monthly = [_pqty(target.year - 1, m) for m in range(1, 13)]
        ty_monthly = [_pqty(target.year, m) for m in range(1, 13)]
        ly_monthly_amount = [_pamt(target.year - 1, m) for m in range(1, 13)]
        ty_monthly_amount = [_pamt(target.year, m) for m in range(1, 13)]
        ly_price = _month_price(group, target.year - 1, target.month)

        # Baseline: recent history only. LySM is retained for risk comparison.
        references = [v for v in [lm_qty, avg_3m_qty] if v > 0]
        baseline_forecast = sum(references) / len(references) if references else 0.0
        
        # If the item is expected due to cycle but baseline is 0, use last 3 orders avg as fallback
        if auto_in_month and baseline_forecast == 0:
            baseline_forecast = float(order_history["銷+贈S量"].tail(3).mean()) if not order_history.empty else 0.0

        if not options.include_all and not auto_in_month and baseline_forecast == 0:
            continue

        forecast_quantity = baseline_forecast
        estimated_amount = 0.0 if is_item_excluded else forecast_quantity * latest_price
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
                last_year_same_month_qty=lysm_qty,
                this_year_same_month_qty=current_progress,
                ly_monthly=ly_monthly,
                ty_monthly=ty_monthly,
                ly_monthly_amount=ly_monthly_amount,
                ty_monthly_amount=ty_monthly_amount,
                ly_price=ly_price,
                latest_price=latest_price,
                system_forecast=forecast_quantity,
                manual_adjustment=None,
                final_forecast=forecast_quantity,
                estimated_amount=estimated_amount,
                forecast_basis="data_driven" if references else ("cycle_fallback" if auto_in_month else "not_due"),
                excluded=is_item_excluded,
            )
        )

    rows = sorted(rows, key=lambda row: (not row.auto_in_month, row.customer, row.product_code))
    return ForecastSummary(year=target.year, month=target.month, rows=rows, total=_total(rows))


def apply_user_adjustments(
    summary: ForecastSummary,
    manual_adjustments: dict[str, float | None],
    excluded_ids: set[str],
) -> ForecastSummary:
    rows = [
        row.with_adjustment(
            manual_adjustment=manual_adjustments[row.row_id] if row.row_id in manual_adjustments else row.manual_adjustment,
            excluded=row.excluded or row.row_id in excluded_ids,
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


def _month_price(group: pd.DataFrame, year: int, month: int) -> float:
    matched = group[(group["年"] == year) & (group["月"] == month)]
    if matched.empty:
        return 0.0
    return float(matched.iloc[-1]["單價NT(淨)"] or 0)


def _latest_nonempty(values: pd.Series) -> str:
    for value in reversed(values.dropna().tolist()):
        if str(value).strip():
            return str(value)
    return ""


def _recent_months_average_from_pivot(
    qty_pivot: pd.Series, target_year: int, target_month: int, n: int
) -> float:
    total_qty = 0.0
    count = 0
    curr_y, curr_m = target_year, target_month
    for _ in range(n):
        curr_m -= 1
        if curr_m == 0:
            curr_m = 12
            curr_y -= 1
        qty = float(qty_pivot.get((curr_y, curr_m), 0.0))
        if qty > 0:
            total_qty += qty
            count += 1
    return total_qty / count if count > 0 else 0.0


def _row_id(customer: object, product_code: object) -> str:
    return make_row_id(customer, product_code)
