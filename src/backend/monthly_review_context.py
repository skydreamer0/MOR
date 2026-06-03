from __future__ import annotations

from dataclasses import dataclass

from src.backend.database import MORDatabase
from src.backend.monthly_review import MonthlyReviewSummary, build_monthly_review
from src.backend.monthly_review_actions import ActionLists, build_action_lists
from src.backend.monthly_review_chart import MonthlyReviewTrendChart, build_trend_chart
from src.backend.monthly_review_customers import CustomerSummary, build_customer_summary
from src.backend.monthly_review_forecast_bias import ForecastBias, build_forecast_bias
from src.backend.monthly_review_products import ProductSummary, build_product_summary
from src.backend.monthly_review_trend import TrendSeries, build_trend


@dataclass(frozen=True)
class MonthlyReviewContext:
    summary: MonthlyReviewSummary
    action_lists: ActionLists
    customer_summary: CustomerSummary
    product_summary: ProductSummary
    forecast_bias: ForecastBias
    trend: TrendSeries
    trend_chart: MonthlyReviewTrendChart | None = None


def build_monthly_review_context(
    db: MORDatabase,
    year: int,
    month: int,
    *,
    include_chart: bool = True,
) -> MonthlyReviewContext:
    summary = build_monthly_review(db, year, month)
    action_lists = build_action_lists(db, year, month)
    customer_summary = build_customer_summary(db, year, month)
    product_summary = build_product_summary(db, year, month)
    forecast_bias = build_forecast_bias(db, year, month)
    trend = build_trend(db, year, month)
    return MonthlyReviewContext(
        summary=summary,
        action_lists=action_lists,
        customer_summary=customer_summary,
        product_summary=product_summary,
        forecast_bias=forecast_bias,
        trend=trend,
        trend_chart=build_trend_chart(trend) if include_chart else None,
    )
