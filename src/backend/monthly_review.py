"""Monthly review service."""
from __future__ import annotations

from dataclasses import dataclass

from src.backend.amount_calculation import (
    period_avg_unit_price,
    review_forecast_amount,
)
from src.backend.database import MORDatabase
from src.backend.monthly_review_data import (
    MonthlyReviewDataReader,
    quantity_multiplier as _quantity_multiplier,
)
from src.backend.row_identity import parse_row_id


@dataclass(frozen=True)
class ReviewRow:
    customer_name: str
    product_code: str
    product_name: str
    actual_quantity: float
    forecast_quantity: float
    budget_quantity: float
    last_year_quantity: float
    actual_amount: float
    forecast_amount: float
    budget_amount: float
    last_year_amount: float
    forecast_gap: float
    forecast_accuracy: float | None
    yoy_growth: float | None
    budget_achievement: float | None
    forecast_amount_gap: float
    forecast_amount_accuracy: float | None
    yoy_amount_growth: float | None
    budget_amount_achievement: float | None
    yoy_amount_delta: float
    budget_amount_delta: float


@dataclass(frozen=True)
class MonthlyReviewSummary:
    year: int
    month: int
    closed_at: str
    actual_quantity_total: float
    forecast_quantity_total: float
    budget_quantity_total: float
    last_year_quantity_total: float
    actual_amount_total: float
    forecast_amount_total: float
    budget_amount_total: float
    last_year_amount_total: float
    forecast_accuracy_total: float | None
    yoy_growth_total: float | None
    budget_achievement_total: float | None
    forecast_amount_accuracy_total: float | None
    yoy_amount_growth_total: float | None
    budget_amount_achievement_total: float | None
    rows: list[ReviewRow]


def build_monthly_review(
    db: MORDatabase,
    year: int,
    month: int,
) -> MonthlyReviewSummary:
    reader = MonthlyReviewDataReader(db)
    close_rec = reader.close_record(year, month)
    if close_rec is None:
        raise ValueError(f"{year}/{month:02d} 尚未結月，無法產生月底檢討。")

    price_quantities = reader.price_quantities()
    rows = _merge_rows(
        actuals=reader.actuals_by_row(year, month),
        forecasts=reader.snapshot_forecasts_by_id(close_rec["final_snapshot_id"]),
        budgets=reader.budget_rows(year, month),
        last_year=reader.last_year_rows(year, month, price_quantities),
        name_map=reader.product_names(),
        fallback_prices=reader.fallback_unit_prices(year, month, price_quantities),
        price_quantities=price_quantities,
    )
    return _make_summary(year, month, close_rec["closed_at"], rows)


def list_reviewable_months(db: MORDatabase) -> list[tuple[int, int]]:
    return MonthlyReviewDataReader(db).reviewable_months()


def _merge_rows(
    actuals: dict[str, dict],
    forecasts: dict[str, dict],
    budgets: dict[str, dict],
    last_year: dict[str, dict],
    name_map: dict[str, str] | None = None,
    fallback_prices: dict[str, float] | None = None,
    price_quantities: dict[str, float] | None = None,
) -> list[ReviewRow]:
    name_map = name_map or {}
    fallback_prices = fallback_prices or {}
    price_quantities = price_quantities or {}
    all_ids = set(actuals) | set(forecasts) | set(budgets)

    rows = []
    for row_id in all_ids:
        actual = actuals.get(row_id, {})
        forecast = forecasts.get(row_id, {})
        budget = budgets.get(row_id, {})
        last_year_row = last_year.get(row_id, {})

        identity = parse_row_id(row_id)
        product_code = actual.get("product_code", identity.product_code)

        actual_quantity = float(actual.get("qty", 0.0)) * _quantity_multiplier(
            product_code,
            price_quantities,
        )
        actual_amount = float(actual.get("amount", 0.0))
        forecast_quantity = float(forecast.get("final_forecast", 0.0))
        budget_quantity = float(budget.get("target_quantity", 0.0))
        budget_amount = float(budget.get("target_amount", 0.0))
        last_year_quantity = float(last_year_row.get("qty", 0.0))
        last_year_amount = float(last_year_row.get("amount", 0.0))

        product_name = actual.get("product_name") or name_map.get(product_code, "")
        period_price = period_avg_unit_price(actual_quantity, actual_amount)
        forecast_amount = review_forecast_amount(
            forecast_quantity,
            period_unit_price=period_price,
            fallback_unit_price=fallback_prices.get(row_id, 0.0),
        )

        rows.append(ReviewRow(
            customer_name=actual.get("customer_name", identity.customer_name),
            product_code=product_code,
            product_name=product_name,
            actual_quantity=actual_quantity,
            forecast_quantity=forecast_quantity,
            budget_quantity=budget_quantity,
            last_year_quantity=last_year_quantity,
            actual_amount=actual_amount,
            forecast_amount=forecast_amount,
            budget_amount=budget_amount,
            last_year_amount=last_year_amount,
            forecast_gap=actual_quantity - forecast_quantity,
            forecast_accuracy=(
                actual_quantity / forecast_quantity if forecast_quantity > 0 else None
            ),
            yoy_growth=(
                actual_quantity / last_year_quantity if last_year_quantity > 0 else None
            ),
            budget_achievement=(
                actual_quantity / budget_quantity if budget_quantity > 0 else None
            ),
            forecast_amount_gap=actual_amount - forecast_amount,
            forecast_amount_accuracy=(
                actual_amount / forecast_amount if forecast_amount > 0 else None
            ),
            yoy_amount_growth=(
                actual_amount / last_year_amount if last_year_amount > 0 else None
            ),
            budget_amount_achievement=(
                actual_amount / budget_amount if budget_amount > 0 else None
            ),
            yoy_amount_delta=actual_amount - last_year_amount,
            budget_amount_delta=actual_amount - budget_amount,
        ))

    rows.sort(key=lambda row: (row.customer_name, row.product_code))
    return rows


def _make_summary(
    year: int,
    month: int,
    closed_at: str,
    rows: list[ReviewRow],
) -> MonthlyReviewSummary:
    actual_quantity_total = sum(row.actual_quantity for row in rows)
    actual_amount_total = sum(row.actual_amount for row in rows)
    forecast_quantity_total = sum(row.forecast_quantity for row in rows)
    forecast_amount_total = sum(row.forecast_amount for row in rows)
    budget_quantity_total = sum(row.budget_quantity for row in rows)
    budget_amount_total = sum(row.budget_amount for row in rows)
    last_year_quantity_total = sum(row.last_year_quantity for row in rows)
    last_year_amount_total = sum(row.last_year_amount for row in rows)

    return MonthlyReviewSummary(
        year=year,
        month=month,
        closed_at=closed_at,
        actual_quantity_total=actual_quantity_total,
        forecast_quantity_total=forecast_quantity_total,
        budget_quantity_total=budget_quantity_total,
        last_year_quantity_total=last_year_quantity_total,
        actual_amount_total=actual_amount_total,
        forecast_amount_total=forecast_amount_total,
        budget_amount_total=budget_amount_total,
        last_year_amount_total=last_year_amount_total,
        forecast_accuracy_total=(
            actual_quantity_total / forecast_quantity_total
            if forecast_quantity_total > 0 else None
        ),
        yoy_growth_total=(
            actual_quantity_total / last_year_quantity_total
            if last_year_quantity_total > 0 else None
        ),
        budget_achievement_total=(
            actual_quantity_total / budget_quantity_total
            if budget_quantity_total > 0 else None
        ),
        forecast_amount_accuracy_total=(
            actual_amount_total / forecast_amount_total
            if forecast_amount_total > 0 else None
        ),
        yoy_amount_growth_total=(
            actual_amount_total / last_year_amount_total
            if last_year_amount_total > 0 else None
        ),
        budget_amount_achievement_total=(
            actual_amount_total / budget_amount_total
            if budget_amount_total > 0 else None
        ),
        rows=rows,
    )
