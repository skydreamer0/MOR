"""Systemic forecast-bias detector."""
from __future__ import annotations

from dataclasses import dataclass

from src.backend.database import MORDatabase
from src.backend.monthly_review_data import MonthlyReviewDataReader


LOOKBACK_MONTHS = 3
BIAS_THRESHOLD = 0.15
BIAS_LIST_LIMIT = 10


@dataclass(frozen=True)
class BiasRow:
    customer_name: str
    product_code: str
    product_name: str
    avg_accuracy: float
    months_observed: int
    direction: str


@dataclass(frozen=True)
class ForecastBias:
    lookback_months: int
    over_forecast: list[BiasRow]
    under_forecast: list[BiasRow]


def build_forecast_bias(
    db: MORDatabase,
    year: int,
    month: int,
    lookback: int = LOOKBACK_MONTHS,
) -> ForecastBias:
    reader = MonthlyReviewDataReader(db)
    months = reader.closed_months_with_snapshots_ending(year, month, lookback)
    if not months:
        return ForecastBias(lookback_months=lookback, over_forecast=[], under_forecast=[])

    samples: dict[tuple[str, str], list[float]] = {}
    name_map: dict[str, str] = {}
    for y, m in months:
        actuals = reader.actual_amounts_by_pair(y, m)
        forecast = reader.forecast_amounts(y, m)
        for key, forecast_amount in forecast.items():
            if forecast_amount <= 0:
                continue
            actual_amount = actuals.get(key, 0.0)
            samples.setdefault(key, []).append(actual_amount / forecast_amount)
        for (_, product), name in reader.names_for_month(y, m).items():
            if product not in name_map and name:
                name_map[product] = name

    over, under = [], []
    for (customer, product), ratios in samples.items():
        if len(ratios) < lookback:
            continue
        average = sum(ratios) / len(ratios)
        if abs(1 - average) < BIAS_THRESHOLD:
            continue
        row = BiasRow(
            customer_name=customer,
            product_code=product,
            product_name=name_map.get(product, ""),
            avg_accuracy=average,
            months_observed=len(ratios),
            direction="over" if average < 1.0 else "under",
        )
        (over if row.direction == "over" else under).append(row)

    over.sort(key=lambda row: row.avg_accuracy)
    under.sort(key=lambda row: -row.avg_accuracy)
    return ForecastBias(
        lookback_months=lookback,
        over_forecast=over[:BIAS_LIST_LIMIT],
        under_forecast=under[:BIAS_LIST_LIMIT],
    )
