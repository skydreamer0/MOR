from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from src.backend.amount_calculation import amount_for_quantity
from src.backend.daily_sales_importer import DailyActualAggregate
from src.backend.forecast_models import ForecastRow
from src.backend.forecast_workbench_inputs import BudgetTarget
from src.backend.product_monitor_rows import is_high_risk_drop
from src.backend.projection_engine import ProjectionResult


@dataclass(frozen=True)
class DashboardMetrics:
    target_quantity: float
    target_amount: float
    actual_quantity: float
    actual_amount: float
    forecast_quantity: float
    forecast_amount: float
    achievement_rate: float
    amount_achievement_rate: float
    quantity_gap: float
    amount_gap: float
    high_risk_product_count: int
    high_risk_customer_count: int


def build_dashboard_metrics(
    rows: Iterable[ForecastRow],
    company_budgets: Iterable[BudgetTarget] | None = None,
    projections: Mapping[str, ProjectionResult] | None = None,
    daily_actuals: Mapping[str, DailyActualAggregate] | None = None,
) -> DashboardMetrics:
    included_rows = [row for row in rows if not row.excluded]
    budgeted_rows = [row for row in included_rows if row.budget_quantity > 0]
    target_quantity, target_amount = _target_totals(budgeted_rows, company_budgets)
    actuals = daily_actuals or {}
    actual_quantity = sum(row.this_year_same_month_qty for row in budgeted_rows)
    actual_amount = sum(
        float(actuals[row.row_id].taxed_amount) if row.row_id in actuals
        else amount_for_quantity(row.this_year_same_month_qty, row)
        for row in budgeted_rows
    )

    projs = projections or {}

    def _eom_qty(row: ForecastRow) -> float:
        return projs[row.row_id].estimated_eom_qty if row.row_id in projs else row.final_forecast

    forecast_quantity = sum(_eom_qty(row) for row in budgeted_rows)
    forecast_amount = sum(amount_for_quantity(_eom_qty(row), row) for row in budgeted_rows)
    high_risk_rows = [row for row in included_rows if is_high_risk_drop(row)]

    return DashboardMetrics(
        target_quantity=target_quantity,
        target_amount=target_amount,
        actual_quantity=actual_quantity,
        actual_amount=actual_amount,
        forecast_quantity=forecast_quantity,
        forecast_amount=forecast_amount,
        achievement_rate=(forecast_quantity / target_quantity * 100) if target_quantity > 0 else 0.0,
        amount_achievement_rate=(forecast_amount / target_amount * 100) if target_amount > 0 else 0.0,
        quantity_gap=forecast_quantity - target_quantity,
        amount_gap=forecast_amount - target_amount,
        high_risk_product_count=len({row.product_code for row in high_risk_rows}),
        high_risk_customer_count=len({row.customer for row in high_risk_rows}),
    )


def _target_totals(
    budgeted_rows: Iterable[ForecastRow],
    company_budgets: Iterable[BudgetTarget] | None,
) -> tuple[float, float]:
    if company_budgets is not None:
        budgets = list(company_budgets)
        return (
            sum(budget.target_quantity for budget in budgets),
            sum(budget.target_amount for budget in budgets),
        )

    rows = list(budgeted_rows)
    return (
        sum(row.budget_quantity for row in rows),
        sum(
            row.budget_amount if row.budget_amount > 0 else amount_for_quantity(row.budget_quantity, row)
            for row in rows
        ),
    )
