from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Mapping

from src.backend.daily_sales_importer import DailyActualAggregate
from src.backend.dashboard_metrics import DashboardMetrics, build_dashboard_metrics
from src.backend.forecast_models import ForecastRow, ForecastTarget
from src.backend.forecast_workbench_inputs import BudgetTarget
from src.backend.product_monitor_rows import (
    AmountForQuantity,
    ProductMonitorRow,
    build_product_monitor_rows,
)
from src.backend.projection_engine import ProjectionResult, batch_project_eom
from src.backend.workday_calendar import ensure_calendar_year


@dataclass(frozen=True)
class ProductMonitorMonthContext:
    projections: dict[str, ProjectionResult]
    dashboard: DashboardMetrics
    monitor_rows: list[ProductMonitorRow]


def build_product_monitor_month_context(
    *,
    db,
    rows: list[ForecastRow],
    daily_actuals: Mapping[str, DailyActualAggregate],
    company_budgets: Iterable[BudgetTarget],
    target: ForecastTarget,
    today: date,
    amount_for_quantity: AmountForQuantity,
) -> ProductMonitorMonthContext:
    ensure_calendar_year(db, today.year)
    projections = batch_project_eom(
        db,
        rows,
        daily_actuals,
        today,
        target.year,
        target.month,
    )
    return ProductMonitorMonthContext(
        projections=projections,
        dashboard=build_dashboard_metrics(
            rows,
            company_budgets,
            projections,
            daily_actuals,
        ),
        monitor_rows=build_product_monitor_rows(
            rows,
            daily_actuals=daily_actuals,
            db=db,
            today=today,
            projections=projections,
            target_month=target.month,
            amount_for_quantity=amount_for_quantity,
        ),
    )
