from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from src.backend.forecast_models import ForecastRow


def is_amount_included(row: ForecastRow) -> bool:
    return not row.excluded and row.budget_quantity > 0


def amount_for_quantity(quantity: float, row: ForecastRow) -> float:
    price_quantity = latest_price_quantity(row)
    if price_quantity <= 0:
        return quantity * row.latest_price
    return quantity / price_quantity * row.latest_price


def forecast_row_amount(row: ForecastRow) -> float:
    if not is_amount_included(row):
        return 0.0
    return amount_for_quantity(row.final_forecast, row)


def forecast_amount_total(rows: Iterable[ForecastRow]) -> float:
    return sum(forecast_row_amount(row) for row in rows)


def last_year_amount_total(rows: Iterable[ForecastRow]) -> float:
    return sum(amount_for_quantity(row.last_year_same_month_qty, row) for row in rows if not row.excluded)


def recalculate_forecast_amounts(rows: Iterable[ForecastRow]) -> list[ForecastRow]:
    return [replace(row, estimated_amount=forecast_row_amount(row)) for row in rows]


def latest_price_quantity(row: ForecastRow) -> float:
    if row.price_quantity > 0:
        return row.price_quantity
    if row.budget_quantity > 0 and row.base_budget_quantity > 0:
        return row.budget_quantity / row.base_budget_quantity
    return 1.0


# ---------------------------------------------------------------------------
# Monthly review helpers
#
# Monthly review operates on a *closed* month and computes pre-tax (折後業績)
# amounts directly from recorded transaction amounts where available.
# Forecast amount is the only value not stored at close time, so we derive it
# from the period's own average unit price (fallback: most recent sales_records
# unit price before the month).
# ---------------------------------------------------------------------------

def period_avg_unit_price(quantity: float, amount: float) -> float:
    """Average unit price implied by quantity / amount. Returns 0 if qty <= 0."""
    return amount / quantity if quantity > 0 else 0.0


def review_forecast_amount(
    forecast_quantity: float,
    period_unit_price: float,
    fallback_unit_price: float = 0.0,
) -> float:
    """Estimate the amount represented by a stored forecast quantity for a
    closed month review.

    Prefers the period's own unit price; falls back to the most recent
    pre-period unit price when the row had no actual sale that month.
    """
    price = period_unit_price if period_unit_price > 0 else fallback_unit_price
    return forecast_quantity * price if price > 0 else 0.0
