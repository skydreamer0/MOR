"""12-month trend series for the monthly review chart."""
from __future__ import annotations

from dataclasses import dataclass, field

from src.backend.database import MORDatabase
from src.backend.monthly_review_data import MonthlyReviewDataReader


TREND_MONTHS = 12


@dataclass(frozen=True)
class TrendPoint:
    year: int
    month: int
    label: str
    actual: float
    forecast: float
    budget: float


@dataclass(frozen=True)
class TrendSeries:
    points: list[TrendPoint]
    previous_year_points: list[TrendPoint] = field(default_factory=list)


def build_trend(
    db: MORDatabase, year: int, month: int, months: int = TREND_MONTHS,
) -> TrendSeries:
    reader = MonthlyReviewDataReader(db)
    target_months = _last_n_months(year, month, months)
    points = [_build_point(reader, y, m) for y, m in target_months]
    previous_year_points = [_build_point(reader, y - 1, m) for y, m in target_months]
    return TrendSeries(points=points, previous_year_points=previous_year_points)


def _last_n_months(year: int, month: int, n: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    y, m = year, month
    for _ in range(n):
        out.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(out))


def _build_point(reader: MonthlyReviewDataReader, year: int, month: int) -> TrendPoint:
    actual = sum(reader.customer_amounts(year, month).values())
    forecast = sum(reader.forecast_amounts(year, month).values())
    budget = sum(row["target_amount"] for row in reader.budget_rows(year, month).values())
    return TrendPoint(
        year=year, month=month,
        label=f"{year % 100:02d}/{month:02d}",
        actual=actual, forecast=forecast, budget=budget,
    )
