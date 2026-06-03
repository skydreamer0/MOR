from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

import pandas as pd

from src.backend.forecast_models import ForecastSummary


@dataclass(frozen=True)
class DataHealthSummary:
    order_count: int
    order_start: date | None
    order_end: date | None
    budget_month_count: int
    budget_months: list[tuple[int, int]]
    missing_budget_row_count: int
    zero_price_row_count: int
    no_last_year_row_count: int


def build_data_health_summary(
    sales_data: pd.DataFrame,
    summary: ForecastSummary,
    budget_months: Iterable[tuple[int, int]],
) -> DataHealthSummary:
    order_dates = pd.to_datetime(
        sales_data.get("order_date", pd.Series(dtype="datetime64[ns]")),
        errors="coerce",
    ).dropna()
    normalized_budget_months = sorted(set(budget_months))
    rows = [row for row in summary.rows if not row.excluded]
    return DataHealthSummary(
        order_count=len(sales_data),
        order_start=order_dates.min().date() if not order_dates.empty else None,
        order_end=order_dates.max().date() if not order_dates.empty else None,
        budget_month_count=len(normalized_budget_months),
        budget_months=normalized_budget_months,
        missing_budget_row_count=sum(1 for row in rows if row.budget_quantity <= 0),
        zero_price_row_count=sum(1 for row in rows if row.latest_price <= 0),
        no_last_year_row_count=sum(1 for row in rows if row.last_year_same_month_qty <= 0),
    )
