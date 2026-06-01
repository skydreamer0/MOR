from __future__ import annotations

import calendar
from datetime import date

from src.backend.data_validator import validate_health
from src.backend.forecast_workbench_context import ForecastPageContext
from src.backend.operational_views import (
    aggregate_to_analytics,
    build_customer_risk_ranking,
    build_status_distribution,
)


def build_dashboard_template_context(
    context: ForecastPageContext,
    *,
    today: date | None = None,
) -> dict:
    target = context.target
    rows = context.summary.rows
    all_monitor = context.monitor_rows
    high_risk_rows = [row for row in all_monitor if row.status_key == "high"]
    high_risk_rows.sort(key=lambda r: r.amount_impact)

    return {
        "year": target.year,
        "month": target.month,
        "metrics": context.dashboard,
        "health": context.health,
        "monitor_rows": high_risk_rows[:15],
        "remaining_days": _remaining_days_in_target_month(target.year, target.month, today or date.today()),
        "status_dist": build_status_distribution(all_monitor),
        "customer_ranking": build_customer_risk_ranking(all_monitor),
        "data_issues": validate_health(context.health),
        "analytics_total": aggregate_to_analytics(rows, "total", target),
        "analytics_customers": aggregate_to_analytics(rows, "customer", target),
        "analytics_products": aggregate_to_analytics(rows, "product", target),
    }


def _remaining_days_in_target_month(year: int, month: int, today: date) -> int:
    _, last_day = calendar.monthrange(year, month)
    month_start = date(year, month, 1)
    month_end = date(year, month, last_day)
    if today > month_end:
        return 0
    if today < month_start:
        return last_day
    return (month_end - today).days
